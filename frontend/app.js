// ============================================================
// AI Newsletter Writer — frontend logic
// Talks to the FastAPI backend at BACKEND_URL.
// ============================================================

const BACKEND_URL = "http://localhost:8000";
document.getElementById("backend-url-display").textContent = BACKEND_URL;

// In-memory store of extracted content items, keyed by source identifier.
// Shape: { source, title, text, error }
const extractedSources = new Map();

let currentDraftMarkdown = "";

// ---------- Tabs ----------
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    document.querySelector(`.tab-panel[data-panel="${tab.dataset.tab}"]`).classList.add("active");
  });
});

// ---------- Pipeline / stamp helpers ----------
const stages = ["extract", "clean", "summarize", "draft"];
const stampEl = document.getElementById("stamp");

function setStage(stageName, state) {
  // state: "active" | "done" | reset
  const el = document.querySelector(`.stage[data-stage="${stageName}"]`);
  if (!el) return;
  el.classList.remove("active", "done");
  if (state) el.classList.add(state);
}

function resetPipeline() {
  stages.forEach((s) => setStage(s, null));
  stampEl.textContent = "READY";
  stampEl.classList.remove("working", "error");
}

function stampWorking(text) {
  stampEl.textContent = text;
  stampEl.classList.add("working");
  stampEl.classList.remove("error");
}

function stampError(text) {
  stampEl.textContent = text;
  stampEl.classList.add("error");
  stampEl.classList.remove("working");
}

function stampDone(text) {
  stampEl.textContent = text;
  stampEl.classList.remove("working", "error");
}

// ---------- Status hint ----------
const statusHint = document.getElementById("status-hint");
function setHint(text, isError = false) {
  statusHint.textContent = text;
  statusHint.classList.toggle("error", isError);
}

// ---------- Source list rendering ----------
function renderSourceList() {
  const container = document.getElementById("source-list");
  container.innerHTML = "";
  extractedSources.forEach((item, key) => {
    const row = document.createElement("div");
    row.className = "source-item" + (item.error ? " has-error" : "");

    const label = document.createElement("span");
    label.className = "source-name";
    label.textContent = (item.title ? item.title + " — " : "") + key + (item.error ? ` (${item.error})` : "");
    label.title = label.textContent;

    const removeBtn = document.createElement("button");
    removeBtn.className = "source-remove";
    removeBtn.setAttribute("aria-label", "Remove source");
    removeBtn.textContent = "✕";
    removeBtn.addEventListener("click", () => {
      extractedSources.delete(key);
      renderSourceList();
    });

    row.appendChild(label);
    row.appendChild(removeBtn);
    container.appendChild(row);
  });
}

// ---------- URL extraction ----------
document.getElementById("fetch-urls-btn").addEventListener("click", async () => {
  const raw = document.getElementById("url-input").value.trim();
  if (!raw) {
    setHint("Add at least one URL first.", true);
    return;
  }
  const urls = raw.split("\n").map((u) => u.trim()).filter(Boolean);

  setStage("extract", "active");
  stampWorking("FETCHING…");
  setHint(`Fetching ${urls.length} URL(s)…`);

  try {
    const resp = await fetch(`${BACKEND_URL}/extract/urls`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ urls }),
    });
    if (!resp.ok) throw new Error(`Server responded ${resp.status}`);
    const data = await resp.json();
    data.items.forEach((item) => extractedSources.set(item.source, item));
    renderSourceList();
    setStage("extract", "done");
    stampDone("EXTRACTED");
    setHint(`Extracted ${data.items.filter((i) => !i.error).length}/${data.items.length} URLs successfully.`);
  } catch (err) {
    setStage("extract", null);
    stampError("FETCH FAILED");
    setHint(`Could not reach backend: ${err.message}. Is it running at ${BACKEND_URL}?`, true);
  }
});

// ---------- File extraction ----------
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");

dropzone.addEventListener("click", () => fileInput.click());

["dragover", "dragenter"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add("drag-over");
  })
);
["dragleave", "drop"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove("drag-over");
  })
);
dropzone.addEventListener("drop", (e) => {
  const files = e.dataTransfer.files;
  if (files.length) handleFiles(files);
});
fileInput.addEventListener("change", (e) => {
  if (e.target.files.length) handleFiles(e.target.files);
});

async function handleFiles(fileList) {
  setStage("extract", "active");
  stampWorking("UPLOADING…");
  setHint(`Uploading ${fileList.length} file(s)…`);

  let successCount = 0;
  for (const file of fileList) {
    const formData = new FormData();
    formData.append("file", file);
    try {
      const resp = await fetch(`${BACKEND_URL}/extract/file`, {
        method: "POST",
        body: formData,
      });
      if (!resp.ok) throw new Error(`Server responded ${resp.status}`);
      const data = await resp.json();
      data.items.forEach((item) => {
        extractedSources.set(item.source, item);
        if (!item.error) successCount++;
      });
    } catch (err) {
      extractedSources.set(file.name, { source: file.name, text: "", error: err.message });
    }
  }
  renderSourceList();
  setStage("extract", "done");
  stampDone("EXTRACTED");
  setHint(`Parsed ${successCount}/${fileList.length} file(s) successfully.`);
}

// ---------- Generate newsletter ----------
document.getElementById("generate-btn").addEventListener("click", generateNewsletter);

async function generateNewsletter() {
  const notes = document.getElementById("notes-input").value.trim();
  const contents = Array.from(extractedSources.values()).filter((i) => !i.error && i.text.trim());

  if (contents.length === 0 && !notes) {
    setHint("Add at least one URL, file, or manual note before generating.", true);
    return;
  }

  const payload = {
    contents: contents,
    notes: notes || null,
    newsletter_title: document.getElementById("title-input").value.trim() || null,
    tone: document.getElementById("tone-select").value,
    audience: document.getElementById("audience-input").value.trim() || null,
    num_sections: parseInt(document.getElementById("sections-input").value, 10) || 4,
    include_cta: document.getElementById("cta-toggle").checked,
    cta_text: document.getElementById("cta-input").value.trim() || null,
  };

  const generateBtn = document.getElementById("generate-btn");
  generateBtn.disabled = true;

  // Grok-via-Drive is polling-based and can take minutes, not seconds —
  // check which provider is active so we can set expectations honestly.
  try {
    const healthResp = await fetch(`${BACKEND_URL}/health`);
    if (healthResp.ok) {
      const health = await healthResp.json();
      if (health.active_provider === "grok_drive") {
        setHint("Active provider is Grok (via Drive) — this can take several minutes while it waits for the scheduled task to run. Please don't close this tab.");
      }
    }
  } catch (_) {
    // Non-fatal — just skip the heads-up if /health isn't reachable yet.
  }

  setStage("clean", "active");
  stampWorking("CLEANING…");
  await sleep(300);

  setStage("clean", "done");
  setStage("summarize", "active");
  stampWorking("SUMMARIZING…");
  setHint("Summarizing sources with the LLM…");

  try {
    const resp = await fetch(`${BACKEND_URL}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    setStage("summarize", "done");
    setStage("draft", "active");
    stampWorking("DRAFTING…");

    if (!resp.ok) {
      const errBody = await resp.json().catch(() => ({}));
      throw new Error(errBody.detail || `Server responded ${resp.status}`);
    }

    const data = await resp.json();
    renderDraft(data.draft);
    currentDraftMarkdown = data.draft.markdown;

    setStage("draft", "done");
    stampDone("FILED");
    setHint(`Draft ready — built from ${data.key_points_used.length} key point(s).`);
  } catch (err) {
    stampError("GENERATION FAILED");
    setHint(`Error: ${err.message}`, true);
  } finally {
    generateBtn.disabled = false;
  }
}

function sleep(ms) {
  return new Promise((res) => setTimeout(res, ms));
}

// ---------- Render draft ----------
function renderDraft(draft) {
  const sheet = document.getElementById("proof-sheet");
  sheet.innerHTML = "";

  const subject = document.createElement("div");
  subject.className = "proof-subject";
  subject.textContent = `Subject: ${draft.subject_line}`;
  sheet.appendChild(subject);

  const headline = document.createElement("h3");
  headline.className = "headline";
  headline.textContent = draft.headline;
  sheet.appendChild(headline);

  const intro = document.createElement("p");
  intro.className = "intro";
  intro.textContent = draft.intro;
  sheet.appendChild(intro);

  draft.sections.forEach((section) => {
    const sec = document.createElement("div");
    sec.className = "newsletter-section";

    const h4 = document.createElement("h4");
    h4.textContent = section.heading;
    sec.appendChild(h4);

    const p = document.createElement("p");
    p.textContent = section.body;
    sec.appendChild(p);

    if (section.source) {
      const tag = document.createElement("span");
      tag.className = "src-tag";
      tag.textContent = `Source: ${section.source}`;
      sec.appendChild(tag);
    }

    sheet.appendChild(sec);
  });

  if (draft.cta) {
    const cta = document.createElement("div");
    cta.className = "cta";
    cta.textContent = draft.cta;
    sheet.appendChild(cta);
  }
}

// ---------- Copy / download ----------
document.getElementById("copy-btn").addEventListener("click", async () => {
  if (!currentDraftMarkdown) {
    setHint("Nothing to copy yet — generate a newsletter first.", true);
    return;
  }
  await navigator.clipboard.writeText(currentDraftMarkdown);
  setHint("Markdown copied to clipboard.");
});

document.getElementById("download-btn").addEventListener("click", () => {
  if (!currentDraftMarkdown) {
    setHint("Nothing to download yet — generate a newsletter first.", true);
    return;
  }
  const blob = new Blob([currentDraftMarkdown], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "newsletter.md";
  a.click();
  URL.revokeObjectURL(url);
});

// ---------- Admin panel ----------
// The admin token is kept only in memory (never localStorage/sessionStorage)
// so it doesn't linger on disk between sessions. Regular users never see
// this panel unless they click "Admin" AND know the token — the backend
// enforces this too via the X-Admin-Token header on /admin/provider.
let adminToken = null;

document.getElementById("admin-toggle").addEventListener("click", () => {
  const panel = document.getElementById("admin-panel");
  const isHidden = panel.hasAttribute("hidden");
  if (isHidden) {
    panel.removeAttribute("hidden");
  } else {
    panel.setAttribute("hidden", "");
  }
});

function setAdminHint(text, isError = false) {
  const hint = document.getElementById("admin-hint");
  hint.textContent = text;
  hint.classList.toggle("error", isError);
}

document.getElementById("admin-unlock-btn").addEventListener("click", async () => {
  const token = document.getElementById("admin-token-input").value.trim();
  if (!token) {
    setAdminHint("Enter a token first.", true);
    return;
  }

  try {
    const resp = await fetch(`${BACKEND_URL}/admin/provider`, {
      headers: { "X-Admin-Token": token },
    });
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      throw new Error(body.detail || (resp.status === 401 ? "Invalid admin token." : `Server responded ${resp.status}`));
    }
    const data = await resp.json();

    adminToken = token;
    const select = document.getElementById("provider-select");
    select.value = data.active_provider;
    document.getElementById("admin-controls").removeAttribute("hidden");
    setAdminHint(`Unlocked. Current provider: ${data.active_provider}`);
  } catch (err) {
    setAdminHint(err.message, true);
  }
});

document.getElementById("admin-save-btn").addEventListener("click", async () => {
  if (!adminToken) {
    setAdminHint("Unlock with the admin token first.", true);
    return;
  }
  const provider = document.getElementById("provider-select").value;

  try {
    const resp = await fetch(`${BACKEND_URL}/admin/provider`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Admin-Token": adminToken },
      body: JSON.stringify({ provider }),
    });
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      throw new Error(body.detail || `Server responded ${resp.status}`);
    }
    const data = await resp.json();
    setAdminHint(`Saved. Active provider is now: ${data.active_provider}`);
  } catch (err) {
    setAdminHint(err.message, true);
  }
});

// ---------- Init ----------
resetPipeline();
