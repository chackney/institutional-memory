"""
Per-tenant memory session (stretch goal S5).

Scopes memory by a `customer_id` so the agent has separate, isolated memory
per tenant instead of one shared store. Each tenant gets its own memory
store (tagged with `customer_id` in metadata) mounted at the same
/mnt/memory/ path inside its own session — the agent never sees more than
one tenant's memory in a given session, so facts can't leak across tenants.

Reuses the main agent and environment created by create_agent.py; creates
(and caches) one memory store per tenant the first time it's used.

Usage:
    python run_session_tenant.py --tenant acme --round 1
    python run_session_tenant.py --tenant acme --round 2
    python run_session_tenant.py --tenant globex --round 1
    python run_session_tenant.py --tenant globex --round 2

Then check isolation:
    python run_session_tenant.py --tenant acme --round 2 --question \
        "What do we know about this customer's leadership and contract?"
    python run_session_tenant.py --tenant globex --round 2 --question \
        "What do we know about this customer's leadership and contract?"
The Acme answer must not mention Globex facts (or vice versa).
"""

import argparse
import os
from pathlib import Path

from anthropic import Anthropic

DEFAULT_QUESTION = (
    "Summarise what we should know about this customer going into our next "
    "conversation with them: contract status, key contacts, and anything "
    "that changed recently."
)

DOCS_ROOT = Path("synthetic-data/tenants")
OUTPUT_DIR = Path("outputs")


def load_docs_as_context(docs_dir: Path) -> str:
    blocks = []
    for path in sorted(docs_dir.glob("*.md")):
        print(f"  including {path.name}")
        blocks.append(f"=====  DOCUMENT: {path.name}  =====\n{path.read_text()}")
    return "\n\n".join(blocks)


def get_or_create_tenant_memory_store(client: Anthropic, tenant: str) -> str:
    store_id_path = Path(f".memory_store_id_{tenant}")
    if store_id_path.exists():
        store_id = store_id_path.read_text().strip()
        print(f"Reusing memory store for tenant '{tenant}': {store_id}")
        return store_id

    store = client.beta.memory_stores.create(
        name=f"Institutional Memory — {tenant}",
        description=(
            f"Per-tenant memory scoped to customer_id={tenant}. Contains only "
            f"facts learned about this specific customer. Must never be "
            f"shared with, or read by, sessions for a different customer_id."
        ),
        metadata={"customer_id": tenant},
    )
    store_id_path.write_text(store.id)
    print(f"Created memory store for tenant '{tenant}': {store.id}")
    return store.id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", required=True, help="Customer ID, e.g. acme or globex")
    parser.add_argument("--round", required=True, type=int, choices=[1, 2])
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Set ANTHROPIC_API_KEY before running.")

    for required in (".agent_id", ".environment_id"):
        if not Path(required).exists():
            raise SystemExit(f"Missing {required}. Run create_agent.py first.")

    agent_id = Path(".agent_id").read_text().strip()
    environment_id = Path(".environment_id").read_text().strip()

    docs_dir = DOCS_ROOT / args.tenant
    doc_file = docs_dir / f"round{args.round}-update.md" if args.round == 2 else docs_dir / "round1-account-summary.md"
    if not doc_file.exists():
        raise SystemExit(f"No docs found for tenant '{args.tenant}' round {args.round} at {doc_file}")

    client = Anthropic()
    memory_store_id = get_or_create_tenant_memory_store(client, args.tenant)

    print(f"Loading tenant '{args.tenant}' round {args.round} docs...")
    context = f"=====  DOCUMENT: {doc_file.name}  =====\n{doc_file.read_text()}"

    print(f"\nStarting session for tenant '{args.tenant}' with memory store {memory_store_id}...")
    session = client.beta.sessions.create(
        agent=agent_id,
        environment_id=environment_id,
        title=f"Tenant session — {args.tenant} round {args.round}",
        metadata={"customer_id": args.tenant},
        resources=[
            {
                "type": "memory_store",
                "memory_store_id": memory_store_id,
                "access": "read_write",
                "instructions": (
                    f"This memory store is scoped exclusively to customer_id="
                    f"{args.tenant}. Only store and recall facts about this "
                    f"customer here. Never reference or assume facts about "
                    f"any other customer."
                ),
            }
        ],
    )

    user_message = (
        f"This session is about customer_id={args.tenant} only. I'm including "
        "an account document below. Please:\n"
        "1. Check your memory store at /mnt/memory/ for what you already "
        f"know about {args.tenant}.\n"
        "2. Read the document below and update memory with anything new or "
        "changed (don't just append — update existing entries).\n"
        "3. Answer the question, using only facts about this customer.\n\n"
        f"{context}\n\n"
        "==================================================\n"
        f"QUESTION: {args.question}"
    )

    final_text_parts: list[str] = []
    print("\nAgent working...\n")
    with client.beta.sessions.events.stream(session.id) as stream:
        client.beta.sessions.events.send(
            session.id,
            events=[
                {
                    "type": "user.message",
                    "content": [{"type": "text", "text": user_message}],
                }
            ],
        )
        for event in stream:
            if event.type == "agent.message":
                for block in event.content:
                    if getattr(block, "type", None) == "text":
                        final_text_parts.append(block.text)
                        print(block.text, end="", flush=True)
            elif event.type == "agent.tool_use":
                name = getattr(event, "name", "?")
                inp = getattr(event, "input", {}) or {}
                target = inp.get("path") or inp.get("file_path") or inp.get("command") or ""
                if "/mnt/memory" in str(target):
                    print(f"\n  [memory: {name}  {target}]", flush=True)
                else:
                    print(f"\n  [{name}]", flush=True)
            elif event.type == "session.status_idle":
                print("\n\n[agent finished]")
                break

    final_text = "".join(final_text_parts)
    OUTPUT_DIR.mkdir(exist_ok=True)
    out = OUTPUT_DIR / f"tenant_{args.tenant}_round{args.round}.txt"
    out.write_text(
        f"=== TENANT SESSION: {args.tenant} (round {args.round}) ===\n"
        f"Question: {args.question}\n\n--- ANSWER ---\n{final_text}\n"
    )
    print(f"\nSaved to {out}")
    print(
        "\nIsolation check: run this for both tenants at round 2, then diff "
        "the outputs — Acme facts must not appear in the Globex answer, and "
        "vice versa."
    )


if __name__ == "__main__":
    main()
