# Presentation Notes — Institutional Memory Agent (Card A: New-Hire Onboarding)

Running log of talking points for the demo. Updated as we build.

## Talking points so far

1. **The setup was genuinely 5 minutes.** No infra to spin up — `pip install`, export a key, done. Managed Agents handled the agent, the cloud environment, and the memory store as three API calls in `create_agent.py`.

2. **We used Card A as-is — the synthetic data was already shaped for it.** Onboarding handbook, access policy, team directory in round 1; a policy update and re-org in round 2. Zero data authoring needed, which let us get straight to the interesting part: watching the agent reconcile.

3. **The core demo moment: same question, two sessions, visibly different answers.**
   - Session 1 answer: "post in `#sre-access-requests`, get an SRE pairing session, urgent 24-hour exception for tenure < 2 weeks."
   - Session 2 answer: "that whole process was replaced on 2026-05-15 — self-serve via the IAM platform, no SRE, no manager, 3-day tenure minimum."
   - Session 2 *led with the contradiction* instead of burying it — exactly the behavior the system prompt asked for.

4. **The agent didn't just answer differently — it showed its work.** In session 2 you can watch it read its own memory files first (`bash ls /mnt/memory/`, `read prod-access-policy.md`) before even looking at the new docs. That's the "check memory before doing anything else" protocol from the system prompt firing correctly, live, on stream.

5. **Memory was updated in place, not appended.** `inspect_memory.py` shows two files, not four — `prod-access-policy.md` was overwritten with the 2026-05-15 version, explicitly noting it "supersedes the January 2026 version" and citing the incident that triggered the change (PROD-INC-04-2026). That's a much harder trick than "remember more stuff" — it's "know what's obsolete."

6. **Stretch goal: the Memory Curator sub-agent — a second, cheaper agent whose only job is memory hygiene.** This is the "memory as a role, not a feature" pitch: a Haiku-powered agent that reads the main agent's memory store, checks for duplicates/contradictions/staleness, and reports back without touching domain knowledge itself.

7. **The curator surfaced real integration bugs, not just a clean report.** Wiring up `stretch_memory_curator.py` uncovered two actual issues: it was missing the required `environment_id` on session creation, and it never attached the memory store as a session resource — so as shipped, the curator agent had no path to `/mnt/memory/` at all. We fixed both. Good live demo honesty: "here's a rough edge we hit and patched," not just a scripted happy path.

8. **The curator's first report was legitimately boring — and that's the point.** With only two sessions behind it, the store was clean: no duplicates, no contradictions, nothing stale enough to prune. It's a good setup line for "run this again after round 3 lands and watch it actually do work."

9. **Built a lightweight comparison UI instead of just reading raw text files aloud.** `view_outputs.py` parses `outputs/session1.txt` and `outputs/session2.txt` (splitting each on the `Question:` / `--- ANSWER ---` markers), then renders both answers side by side as `outputs/compare.html` — a single shared question banner up top, two panels underneath, markdown rendered client-side via `marked.js` from a CDN so headings, tables, and citations format properly instead of showing raw `#`/`|` characters.

10. **Kept the UI to one dependency-free script on purpose.** No build step, no server — it's a static HTML file the script writes and opens directly in the browser (`webbrowser.open`), so re-running it after any new session output is a single `python view_outputs.py`. That mattered more than it sounds: `osascript`-based auto-open failed under the sandboxed terminal, so we fell back to `open outputs/compare.html` directly — a reminder to keep an escape hatch for auto-launch steps in a demo environment.

## Ideas for what to show live in the room

- Two terminals side by side: session 1 output on the left, session 2 on the right. Read both aloud back to back — the room hears the answer sharpen.
- Third terminal: `python inspect_memory.py` — show the two memory files and point at the "supersedes January 2026" language as proof the agent knows what's stale.
- If time allows, run the curator live and narrate the bug fix as part of the story — it's a more credible demo than a hollow scripted run.

## Open items / next steps

- Consider S3 (adversarial round3 data) or S4 ("what have you learned?" recall test) to give the curator something real to clean up before we present.
- Keep this file updated after each further stretch goal we attempt.
