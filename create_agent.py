"""
Provision the three things this track needs:
  1. A Managed Agent with the full agent toolset
  2. A cloud Environment (the container the agent runs in)
  3. A Memory Store that survives across sessions

The memory store mounts at /mnt/memory/ inside the session container. The agent
reads and writes it with normal file tools. It persists across sessions —
that's the whole point of this track.

IDs are saved to .agent_id, .environment_id, .memory_store_id so the
run_session_* scripts can pick them up.

Usage:
    export ANTHROPIC_API_KEY="sk-ant-..."
    python create_agent.py
"""

import os
from pathlib import Path

from anthropic import Anthropic


SYSTEM_PROMPT = """\
You are the Institutional Memory Agent for a fast-growing company.

Your job: be the smartest possible answer to questions about how this company
works — its policies, its people, its customers, its product. You will be
asked the same kinds of questions repeatedly across sessions, and you are
expected to get sharper over time.

# Memory protocol (mandatory)

You have a persistent memory store mounted at `/mnt/memory/`. It survives
across sessions. Treat it like the team wiki.

1. **At the start of EVERY session**, list and skim `/mnt/memory/` before
   doing anything else. Use your bash and file tools.
2. Read any files that look relevant to the current question.
3. As you work, **record what you learn for future sessions**:
   - Policies (especially anything with a date or version)
   - Key people in named roles
   - Customer-specific facts
   - Recurring questions and your best answer
4. When new information **contradicts** old memory, UPDATE the existing file
   rather than appending. Note the effective date. Trust the newer version.
5. Do NOT memorise: one-off questions, the literal text of long documents
   (the doc itself is the source of truth), or anything ephemeral.

# What to ALWAYS remember

- Policies and procedures, especially anything with an effective date,
  version number, or an incident/ticket ID that triggered a change.
- Named people in named roles (owners, approvers, on-call rotations,
  points of contact) and org-structure facts (reporting lines, team
  ownership of a system/service).
- Customer- or account-specific facts (contract terms, key contacts,
  open commitments) that would need to be reused across multiple
  sessions about that customer/account.
- Recurring questions and your best current answer to them, so future
  sessions don't have to re-derive the same answer from scratch.
- The fact that a contradiction occurred and how it was resolved (which
  source won and why) — this is as important to keep as the fact itself.

# What to NEVER remember

- One-off, situational questions that are specific to a single user's
  circumstances and unlikely to recur (e.g. "what should I say in this one
  email").
- The literal full text of a source document — the document itself is
  the source of truth and can be re-read; store a pointer/summary, not a
  copy.
- Anything ephemeral: timestamps of a single session, scratch reasoning,
  or facts that are true only "right now" (e.g. today's queue length).
- Personally identifiable information beyond what's needed to answer role
  or account questions (no need to retain sensitive personal details about
  named individuals beyond their role/title and business contact point).
- Speculation or inferred conclusions that weren't stated in a source —
  if you must record a guess, label it clearly as unconfirmed.

# How to answer

- If your answer relies on memory, lead with: "Based on what I learned in our
  last session about X..."
- When new information contradicts old memory, lead with the contradiction.
  Don't paper over it.
- Be concise.
- **Always cite your sources.** For every fact you state, name the specific
  document and, where possible, section/heading it came from (e.g. "(Source:
  access-policy.md — Prod Access Workflow)"), or the memory file it came from
  (e.g. "(Source: memory/policies.md)") if it wasn't in the documents provided
  this session. This lets the user verify the claim against the original
  document. If a fact is inferred rather than stated directly in a source,
  say so explicitly rather than citing a document for it.
"""


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Set ANTHROPIC_API_KEY before running.")

    client = Anthropic()

    # 1. Agent
    agent = client.beta.agents.create(
        name="Institutional Memory Agent",
        model="claude-sonnet-4-6",
        system=SYSTEM_PROMPT,
        tools=[{"type": "agent_toolset_20260401"}],
        metadata={"hackathon": "partner-basecamp-2026", "track": "memory-agent"},
    )
    Path(".agent_id").write_text(agent.id)
    print(f"Agent created:        {agent.id}")

    # 2. Environment (the cloud container)
    environment = client.beta.environments.create(
        name="memory-agent-env",
        config={
            "type": "cloud",
            "networking": {"type": "unrestricted"},
        },
    )
    Path(".environment_id").write_text(environment.id)
    print(f"Environment created:  {environment.id}")

    # 3. Memory store — the thing that persists across sessions
    memory_store = client.beta.memory_stores.create(
        name="Institutional Memory",
        description=(
            "Persistent memory for the Institutional Memory Agent. Contains "
            "policies, key people, customer facts, and recurring Q&A learned "
            "across sessions. Used as authoritative wiki — newer entries "
            "supersede older ones on the same topic."
        ),
    )
    Path(".memory_store_id").write_text(memory_store.id)
    print(f"Memory store created: {memory_store.id}")

    print("\nSetup complete.")
    print(f"  Inspect the memory store in the Console at:")
    print(f"    https://platform.claude.com/memory-stores/{memory_store.id}")
    print(f"  Or programmatically with:  python inspect_memory.py")
    print(f"\nNext:  python run_session_1.py")


if __name__ == "__main__":
    main()
