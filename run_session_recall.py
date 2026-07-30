"""
Recall session (stretch goal S4) — "What have you learned?"

Same agent, same memory store, fresh session. No new documents are uploaded
this time. The only message is a direct request to summarise everything
learned across previous sessions, purely from memory.

This is the most direct demo of what's actually in the memory store — it
shows the agent reading its own memory files and reporting back, with
nothing else to lean on.

Usage:
    python run_session_recall.py
"""

import os
from pathlib import Path

from anthropic import Anthropic


RECALL_PROMPT = (
    "Don't read any new documents — none are being provided this session. "
    "Instead, check your memory store at /mnt/memory/ and summarise "
    "everything you've learned about this domain across our previous "
    "sessions: policies (with effective dates), key people and their roles, "
    "any contradictions you've had to resolve and how you resolved them, "
    "and any recurring questions with your best current answer. Cite which "
    "memory file each fact comes from."
)

OUTPUT_DIR = Path("outputs")


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Set ANTHROPIC_API_KEY before running.")

    for required in (".agent_id", ".environment_id", ".memory_store_id"):
        if not Path(required).exists():
            raise SystemExit(f"Missing {required}. Run create_agent.py first.")

    agent_id = Path(".agent_id").read_text().strip()
    environment_id = Path(".environment_id").read_text().strip()
    memory_store_id = Path(".memory_store_id").read_text().strip()

    client = Anthropic()

    print(f"Starting recall session with memory store {memory_store_id}...")
    session = client.beta.sessions.create(
        agent=agent_id,
        environment_id=environment_id,
        title="Recall session — what have you learned?",
        resources=[
            {
                "type": "memory_store",
                "memory_store_id": memory_store_id,
                "access": "read_write",
                "instructions": (
                    "This is your persistent institutional memory. No new "
                    "documents are provided this session — answer entirely "
                    "from what's stored at /mnt/memory/."
                ),
            }
        ],
    )

    final_text_parts: list[str] = []
    print("\nAgent working...\n")
    with client.beta.sessions.events.stream(session.id) as stream:
        client.beta.sessions.events.send(
            session.id,
            events=[
                {
                    "type": "user.message",
                    "content": [{"type": "text", "text": RECALL_PROMPT}],
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
    out = OUTPUT_DIR / "session_recall.txt"
    out.write_text(
        f"=== RECALL SESSION ===\nQuestion: {RECALL_PROMPT}\n\n--- ANSWER ---\n{final_text}\n"
    )
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
