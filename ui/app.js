const els = {
  status: document.getElementById("status"),
  ids: document.getElementById("ids"),
  log: document.getElementById("log"),
  session1: document.getElementById("session1"),
  session2: document.getElementById("session2"),
  citations1: document.getElementById("citations1"),
  citations2: document.getElementById("citations2"),
  diff: document.getElementById("diff"),
  memory: document.getElementById("memory"),
};

function escapeHtml(value) {
  return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;");
}

function renderCitations(el, citations) {
  if (!citations || !citations.length) {
    el.textContent = "No citations recorded.";
    return;
  }
  el.innerHTML = citations
    .map(
      (c) =>
        `<div class="cite cite-${escapeHtml(c.kind)}">` +
        `<span class="cite-index">[${escapeHtml(c.index)}]</span> ` +
        `<span class="cite-source">${escapeHtml(c.source)}</span> ` +
        `<span class="cite-kind">${escapeHtml(c.kind)} · ${escapeHtml(c.count)}×</span>` +
        `</div>`
    )
    .join("");
}

const runButtons = Array.from(document.querySelectorAll("button[data-script]"));
const memoryButton = document.getElementById("btn-memory");

let pollTimer = null;

function setText(el, value, fallback) {
  el.textContent = value && value.trim() ? value : fallback;
}

function renderIds(ids, apiKeyPresent) {
  const rows = [
    ["agent", ids.agent],
    ["environment", ids.environment],
    ["memory store", ids.memoryStore],
  ].map(([label, value]) => `<span>${label}: ${value || "—"}</span>`);

  if (!apiKeyPresent) {
    rows.push('<span class="error">ANTHROPIC_API_KEY not set</span>');
  }
  els.ids.innerHTML = rows.join("");
}

function renderDiff(diff) {
  if (!diff || !diff.trim()) {
    els.diff.textContent = "No differences yet — run both sessions.";
    return;
  }
  els.diff.innerHTML = diff
    .split("\n")
    .map((line) => {
      const safe = line.replace(/&/g, "&amp;").replace(/</g, "&lt;");
      if (line.startsWith("+++") || line.startsWith("---") || line.startsWith("@@")) {
        return `<span class="meta">${safe}</span>`;
      }
      if (line.startsWith("+")) return `<span class="add">${safe}</span>`;
      if (line.startsWith("-")) return `<span class="del">${safe}</span>`;
      return safe;
    })
    .join("\n");
}

function renderJob(job) {
  if (job.lines && job.lines.length) {
    els.log.textContent = job.lines.join("\n");
    els.log.scrollTop = els.log.scrollHeight;
  }

  runButtons.forEach((btn) => {
    btn.disabled = Boolean(job.running);
  });

  if (job.running) {
    els.status.textContent = `Running ${job.key}…`;
  } else if (job.exitCode === 0) {
    els.status.textContent = `${job.key} finished.`;
  } else if (typeof job.exitCode === "number") {
    els.status.textContent = `${job.key} failed (exit ${job.exitCode}).`;
  }

  return Boolean(job.running);
}

async function refreshState() {
  try {
    const res = await fetch("/api/state");
    const state = await res.json();

    setText(els.session1, state.session1, "Not run yet.");
    setText(els.session2, state.session2, "Not run yet.");
    renderCitations(els.citations1, state.citations1);
    renderCitations(els.citations2, state.citations2);
    renderDiff(state.diff);
    renderIds(state.ids, state.apiKeyPresent);
    return renderJob(state.job);
  } catch (err) {
    els.status.textContent = `UI error: ${err.message}`;
    return false;
  }
}

function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(async () => {
    const stillRunning = await refreshState();
    if (!stillRunning) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }, 1200);
}

runButtons.forEach((btn) => {
  btn.addEventListener("click", async () => {
    els.status.textContent = "Starting…";
    try {
      const res = await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ script: btn.dataset.script }),
      });
      const data = await res.json();
      els.status.textContent = data.message;
      await refreshState();
      startPolling();
    } catch (err) {
      els.status.textContent = `Failed to start: ${err.message}`;
    }
  });
});

memoryButton.addEventListener("click", async () => {
  els.memory.textContent = "Loading…";
  try {
    const res = await fetch("/api/memory");
    const data = await res.json();

    if (data.error) {
      els.memory.innerHTML = `<div class="error">${data.error}</div>`;
      return;
    }
    if (!data.memories || !data.memories.length) {
      els.memory.textContent = "Memory store is empty.";
      return;
    }

    els.memory.innerHTML = data.memories
      .map((item) => {
        const path = item.path.replace(/&/g, "&amp;").replace(/</g, "&lt;");
        if (item.isDir) {
          return `<div class="memory-item"><div class="memory-path">[dir] ${path}</div></div>`;
        }
        const content = (item.content || "")
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;");
        return `<div class="memory-item"><div class="memory-path">${path}</div><pre>${content}</pre></div>`;
      })
      .join("");
  } catch (err) {
    els.memory.innerHTML = `<div class="error">${err.message}</div>`;
  }
});

refreshState();
