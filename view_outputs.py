"""
Generate a side-by-side HTML view of the session outputs.

The left panel is always Session 1 (the baseline). The right panel has a
dropdown to switch between whichever of Session 2, Session 3 (adversarial),
and the recall session ("what have you learned?") are available in
outputs/ — each has its own question, since the recall session doesn't ask
the same question as the others.

Reads outputs/session1.txt (required). Any of outputs/session2.txt,
outputs/session3.txt, outputs/session_recall.txt that exist are added as
options in the right-hand panel's dropdown, and rendered client-side via
marked.js from a CDN. Output is written to outputs/compare.html.

Usage:
    python view_outputs.py
    open outputs/compare.html
"""

import json
import webbrowser
from pathlib import Path

OUTPUT_DIR = Path("outputs")
BASELINE_FILE = OUTPUT_DIR / "session1.txt"
BASELINE_TITLE = "Session 1 — Baseline"

COMPARISON_FILES = {
    "Session 2 — After new context": OUTPUT_DIR / "session2.txt",
    "Session 3 — Adversarial round": OUTPUT_DIR / "session3.txt",
    "Recall — What have you learned?": OUTPUT_DIR / "session_recall.txt",
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
    --accent-3: #cf222e;
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
    margin: 12px 22px 0 22px;
    padding: 10px 14px;
    background: #fff8c5;
    border: 1px solid #d4a72c;
    border-radius: 6px;
    font-size: 0.88rem;
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
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }}
  .panel-left .panel-header {{ background: var(--accent-2); }}
  .panel-right .panel-header {{ background: var(--accent); }}
  .panel-right.adversarial .panel-header {{ background: var(--accent-3); }}
  .panel-header select {{
    font-size: 0.85rem;
    padding: 4px 8px;
    border-radius: 5px;
    border: none;
    background: rgba(255, 255, 255, 0.9);
    color: #1f2328;
    font-weight: 500;
  }}
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
  <p>Baseline on the left. Pick a comparison session on the right — each may ask a different question.</p>
</header>
<div class="columns">
  <div class="panel panel-left">
    <div class="panel-header"><span>{baseline_title}</span></div>
    <div class="question-banner"><strong>Question:</strong> {baseline_question}</div>
    <div class="panel-body" data-key="{baseline_title}"></div>
  </div>
  <div class="panel panel-right">
    <div class="panel-header">
      <span>Compare with:</span>
      <select id="session-select">
{options}
      </select>
    </div>
    <div class="question-banner" id="right-question"></div>
    <div class="panel-body" id="right-body"></div>
  </div>
</div>
<script>
  const answers = {answers_json};
  const questions = {questions_json};
  const adversarialKeys = {adversarial_keys_json};

  document.querySelectorAll('.panel-body[data-key]').forEach((el) => {{
    const key = el.dataset.key;
    el.innerHTML = marked.parse(answers[key] || '');
  }});

  const select = document.getElementById('session-select');
  const rightBody = document.getElementById('right-body');
  const rightQuestion = document.getElementById('right-question');
  const rightPanel = document.querySelector('.panel-right');

  function renderRight(key) {{
    rightBody.innerHTML = marked.parse(answers[key] || '');
    rightQuestion.innerHTML = '<strong>Question:</strong> ' + (questions[key] || '');
    rightPanel.classList.toggle('adversarial', adversarialKeys.includes(key));
  }}

  select.addEventListener('change', (e) => renderRight(e.target.value));
  renderRight(select.value);
</script>
</body>
</html>
"""

OPTION_TEMPLATE = '        <option value="{key}">{title}</option>'


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
    if not BASELINE_FILE.exists():
        raise SystemExit(f"Missing {BASELINE_FILE}. Run run_session_1.py first.")

    available = {}
    for title, path in COMPARISON_FILES.items():
        if path.exists():
            available[title] = path
        else:
            print(f"  (skipping {title}: {path} not found)")
    if not available:
        raise SystemExit(
            "No comparison sessions found. Run run_session_2.py, run_session_3.py, "
            "or run_session_recall.py first."
        )

    baseline_question, baseline_answer = parse_session_file(BASELINE_FILE)

    answers = {BASELINE_TITLE: baseline_answer}
    questions = {BASELINE_TITLE: baseline_question}
    options = []
    adversarial_keys = []
    for title, path in available.items():
        q, a = parse_session_file(path)
        answers[title] = a
        questions[title] = q
        options.append(OPTION_TEMPLATE.format(key=title, title=title))
        if "Adversarial" in title:
            adversarial_keys.append(title)

    html = HTML_TEMPLATE.format(
        baseline_title=BASELINE_TITLE,
        baseline_question=baseline_question,
        options="\n".join(options),
        answers_json=json.dumps(answers),
        questions_json=json.dumps(questions),
        adversarial_keys_json=json.dumps(adversarial_keys),
    )

    out_path = OUTPUT_DIR / "compare.html"
    out_path.write_text(html)
    print(f"Wrote {out_path}")

    webbrowser.open(out_path.resolve().as_uri())


if __name__ == "__main__":
    main()
