"""
Generate a side-by-side HTML view of the session1 vs session2 outputs.

Reads outputs/session1.txt and outputs/session2.txt, splits each into its
question and answer, and renders them side by side in outputs/compare.html
(markdown rendered client-side via marked.js from a CDN).

Usage:
    python view_outputs.py
    open outputs/compare.html
"""

import json
import webbrowser
from pathlib import Path

OUTPUT_DIR = Path("outputs")
SESSION_FILES = {
    "Session 1 — Baseline": OUTPUT_DIR / "session1.txt",
    "Session 2 — After new context": OUTPUT_DIR / "session2.txt",
}

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Institutional Memory Agent — Session Comparison</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
  :root {{
    color-scheme: light dark;
    --border: #d0d7de;
    --bg-panel: #ffffff;
    --bg-page: #f6f8fa;
    --accent: #6e40c9;
    --accent-2: #0969da;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: var(--bg-page);
    color: #1f2328;
  }}
  header {{
    padding: 20px 32px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-panel);
  }}
  header h1 {{
    margin: 0 0 4px 0;
    font-size: 1.4rem;
  }}
  header p {{
    margin: 0;
    color: #57606a;
    font-size: 0.9rem;
  }}
  .question-banner {{
    margin: 16px 32px 0 32px;
    padding: 12px 16px;
    background: #fff8c5;
    border: 1px solid #d4a72c;
    border-radius: 6px;
    font-size: 0.95rem;
  }}
  .columns {{
    display: flex;
    gap: 20px;
    padding: 20px 32px 40px 32px;
    align-items: flex-start;
  }}
  .panel {{
    flex: 1 1 0;
    min-width: 0;
    background: var(--bg-panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
  }}
  .panel-header {{
    padding: 12px 18px;
    font-weight: 600;
    color: #fff;
    font-size: 0.95rem;
  }}
  .panel:nth-child(1) .panel-header {{ background: var(--accent-2); }}
  .panel:nth-child(2) .panel-header {{ background: var(--accent); }}
  .panel-body {{
    padding: 18px 22px;
    line-height: 1.55;
    font-size: 0.92rem;
    max-height: 75vh;
    overflow-y: auto;
  }}
  .panel-body h1, .panel-body h2, .panel-body h3 {{ margin-top: 1.2em; }}
  .panel-body table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
  .panel-body th, .panel-body td {{
    border: 1px solid var(--border);
    padding: 6px 10px;
    text-align: left;
    font-size: 0.85rem;
  }}
  .panel-body code {{
    background: #eef0f2;
    padding: 1px 5px;
    border-radius: 4px;
    font-size: 0.85em;
  }}
  .panel-body blockquote {{
    border-left: 3px solid var(--border);
    margin: 8px 0;
    padding: 2px 14px;
    color: #57606a;
  }}
  @media (max-width: 900px) {{
    .columns {{ flex-direction: column; }}
  }}
</style>
</head>
<body>
<header>
  <h1>Institutional Memory Agent — Session Comparison</h1>
  <p>Same question, asked before and after new/contradicting context was introduced.</p>
</header>
<div class="question-banner"><strong>Question:</strong> {question}</div>
<div class="columns">
{panels}
</div>
<script>
  const answers = {answers_json};
  document.querySelectorAll('.panel-body').forEach((el) => {{
    const key = el.dataset.key;
    el.innerHTML = marked.parse(answers[key] || '');
  }});
</script>
</body>
</html>
"""

PANEL_TEMPLATE = """  <div class="panel">
    <div class="panel-header">{title}</div>
    <div class="panel-body" data-key="{key}"></div>
  </div>
"""


def parse_session_file(path: Path) -> tuple[str, str]:
    text = path.read_text()
    question = ""
    answer = text
    if "Question:" in text:
        after_q = text.split("Question:", 1)[1]
        question, _, rest = after_q.partition("--- ANSWER ---")
        question = question.strip()
        answer = rest.strip() if rest else after_q.strip()
    return question, answer


def main() -> None:
    for path in SESSION_FILES.values():
        if not path.exists():
            raise SystemExit(f"Missing {path}. Run the session scripts first.")

    question = ""
    answers = {}
    panels = []
    for title, path in SESSION_FILES.items():
        q, a = parse_session_file(path)
        question = question or q
        answers[title] = a
        panels.append(PANEL_TEMPLATE.format(title=title, key=title))

    html = HTML_TEMPLATE.format(
        question=question,
        panels="".join(panels),
        answers_json=json.dumps(answers),
    )

    out_path = OUTPUT_DIR / "compare.html"
    out_path.write_text(html)
    print(f"Wrote {out_path}")

    webbrowser.open(out_path.resolve().as_uri())


if __name__ == "__main__":
    main()
