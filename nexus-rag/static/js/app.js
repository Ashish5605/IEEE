// Nexora frontend — three-pane shell.
// Left rail: conversations, knowledge scope, upload, language.
// Center:    chat thread + composer.
// Right:     information panel — semantic map + retrieved-evidence table.

const $ = (id) => document.getElementById(id);

const chatInner = $("chat-inner");
const emptyState = $("empty-state");
const questionInput = $("question-input");
const sendBtn = $("send-btn");
const regenBtn = $("regen-btn");
const micBtn = $("mic-btn");
const micStatus = $("mic-status");
const clearChatBtn = $("clear-chat-btn");
const rebuildBtn = $("rebuild-btn");
const newChatBtn = $("new-chat-btn");
const settingsToggle = $("settings-toggle");
const settingsBody = $("settings-body");
const settingsChevron = $("settings-chevron");
const topkSlider = $("topk-slider");
const topkVal = $("topk-val");
const thresholdSlider = $("threshold-slider");
const thresholdVal = $("threshold-val");
const sourceSelector = $("source-selector");
const historyList = $("history-list");
const scopeAllBtn = $("scope-all");
const scopeFilesBtn = $("scope-files");
const plotSvg = $("semantic-plot");
const evidenceBody = $("evidence-body");
const topScore = $("top-score");
const bannerSlot = $("banner-slot");
const infoToggle = $("info-toggle");
const infoPanel = $("info-panel");
const appShell = $("app-shell");

let lastAnswerLanguage = "en";
let currentSourceFilter = null;
let scopeMode = "all";          // "all" | "files"
let lastQuestion = null;        // for Regen
let corpusPoints = [];
let activeSpeechBtn = null;

const VOICE_LANG_MAP = { en: "en-IN" };

function setStatus(text, loading) {
  const dot = $("status-dot"), label = $("status-text");
  if (!dot || !label) return;
  label.textContent = text;
  dot.className = "dot " + (loading ? "dot--load" : "dot--ready");
}

// ---------- Banners ----------
function showBanner(kind, text) {
  const tones = { info: "var(--retrieval)", warning: "var(--signal)", error: "var(--danger)" };
  const el = document.createElement("div");
  el.className = "glass px-4 py-2.5 text-[12px] mb-2 msg-in";
  el.style.color = tones[kind] || tones.info;
  el.setAttribute("role", "status");
  el.textContent = text;
  bannerSlot.appendChild(el);
  setTimeout(() => el.remove(), 6000);
}

// ---------- Status ----------
async function loadStatus() {
  try {
    const data = await (await fetch("/api/status")).json();
    $("doc-count").textContent = data.documents.length;

    const badge = $("index-status-badge");
    if (data.indexed) {
      badge.textContent = `${data.chunk_count} chunks`;
      badge.className = "pill pill--on";
      setStatus("ready");
    } else {
      badge.textContent = "not indexed";
      badge.className = "pill pill--off";
      setStatus("no index");
    }

    sourceSelector.innerHTML = "";
    data.documents.forEach((doc) => sourceSelector.appendChild(sourceRow(doc)));
    applyScopeMode();

    topkSlider.value = data.top_k;      topkVal.textContent = data.top_k;
    thresholdSlider.value = data.relevance_threshold;
    thresholdVal.textContent = data.relevance_threshold;
  } catch (e) {
    console.error("status failed", e);
  }
}

function sourceRow(name) {
  const row = document.createElement("label");
  row.className = "src-row";
  row.innerHTML = `<input type="radio" name="source" class="w-3 h-3"/><span class="truncate mono" title="${escapeAttr(name)}">${escapeHtml(name)}</span>`;
  row.querySelector("input").addEventListener("change", () => {
    // Choosing a document implies scoping to it.
    currentSourceFilter = name;
    scopeMode = "files";
    applyScopeMode();
    row.querySelector("input").checked = true;
  });
  return row;
}

function applyScopeMode() {
  const filesMode = scopeMode === "files";
  scopeAllBtn.classList.toggle("active", !filesMode);
  scopeFilesBtn.classList.toggle("active", filesMode);
  // The document list always shows — it is the substance of the Knowledge tab.
  // "All files" simply means no single-source filter is applied.
  sourceSelector.style.display = "flex";
  sourceSelector.classList.toggle("scope-inactive", !filesMode);
  if (!filesMode) {
    currentSourceFilter = null;
    sourceSelector.querySelectorAll("input[type=radio]").forEach((r) => { r.checked = false; });
  }
}
scopeAllBtn.addEventListener("click", () => { scopeMode = "all"; applyScopeMode(); });
scopeFilesBtn.addEventListener("click", () => { scopeMode = "files"; applyScopeMode(); });

// ---------- Semantic map ----------
async function loadCorpusPoints() {
  try {
    const data = await (await fetch("/api/semantic_map")).json();
    corpusPoints = data.points || [];
    skies().forEach((sky) => sky.setPoints(corpusPoints));
  } catch (e) { console.error("map failed", e); }
}

// One sky now (the info-panel map); __sky aliases it for compatibility.
function skies() { return [...new Set([window.__sky, window.__mini].filter(Boolean))]; }

function renderPlot(retrievedIds, queryPoint, grounded, scores) {
  // The map is the Vector Sky canvas: matched stars brighten and a constellation
  // draws from the query point out to each. When the search found nothing above
  // threshold, the same points render as dashed near-misses instead.
  skies().forEach((sky) => sky.showConstellation(retrievedIds, queryPoint, grounded, scores));
}

function clearPlot() { skies().forEach((sky) => sky.clearConstellation()); }

// ---------- Evidence table ----------
function renderEvidence(evidence) {
  if (!evidence || !evidence.length) {
    evidenceBody.innerHTML = `<tr><td colspan="2" class="text-center py-9" style="color:var(--dim)">No passages cleared the threshold.</td></tr>`;
    topScore.textContent = "";
    return;
  }
  topScore.textContent = `top ${evidence[0].relevance_score}`;
  evidenceBody.innerHTML = evidence.map((e) => `
    <tr class="ev-row">
      <td>
        <div class="ev-source" title="${escapeAttr(e.source)}">${escapeHtml(e.source)}</div>
        <div class="mt-1 mono score-${(e.relevance_label || "").toLowerCase()}">${e.relevance_score}${e.page ? " · p." + e.page : ""}</div>
      </td>
      <td><div class="ev-passage" title="${escapeAttr(e.passage)}">${escapeHtml(e.passage)}</div></td>
    </tr>`).join("");
}

function escapeAttr(s) { return escapeHtml(s).replace(/\n/g, " "); }

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ---------- Messages ----------
function hideEmptyState() {
  if (!emptyState || !emptyState.parentNode) return;
  emptyState.remove();
}

function addUserMessage(text) {
  hideEmptyState();
  const el = document.createElement("div");
  el.className = "flex justify-end msg-in";
  el.innerHTML = `<div class="msg-user">${escapeHtml(text)}</div>`;
  chatInner.appendChild(el);
  scrollDown();
}

function addThinking() {
  hideEmptyState();
  const el = document.createElement("div");
  el.id = "thinking";
  el.className = "mono msg-in";
  el.style.color = "var(--dim)";
  el.textContent = "retrieving\u2026";
  chatInner.appendChild(el);
  scrollDown();
  return el;
}

function addAssistantMessage(data) {
  hideEmptyState();
  const wrap = document.createElement("div");
  wrap.className = "msg-in";
  const body = window.marked ? marked.parse(data.answer || "") : escapeHtml(data.answer || "");
  const sources = (data.sources || []).map((s) =>
    `<span class="chip">${s.source}${s.page ? " p." + s.page : ""}</span>`).join("");

  wrap.innerHTML = `
    <div class="msg-bot">
      <div class="prose-answer">${body}</div>
      ${sources ? `<div class="flex flex-wrap gap-1.5 mt-3 pt-3" style="border-top:1px solid var(--line)">${sources}</div>` : ""}
      <div class="flex items-center gap-0.5 mt-2">
        <button class="copy-btn icon-btn" aria-label="Copy answer" title="Copy"><span class="material-symbols-outlined text-[15px]">content_copy</span></button>
        <button class="listen-btn icon-btn" aria-label="Read answer aloud" title="Listen"><span class="material-symbols-outlined text-[15px]">volume_up</span></button>
        ${data.grounded === false ? `<span class="ml-1.5 text-[10.5px]" style="color:var(--warn)">not grounded</span>` : ""}
      </div>
    </div>`;

  wrap.querySelector(".copy-btn").addEventListener("click", () => {
    navigator.clipboard.writeText(data.answer || "");
    showBanner("info", "Answer copied.");
  });
  const listenBtn = wrap.querySelector(".listen-btn");
  listenBtn.addEventListener("click", () => toggleSpeech(data.answer, data.language || "en", listenBtn));

  chatInner.appendChild(wrap);
  scrollDown();
}

function scrollDown() {
  const thread = $("chat-thread");
  thread.scrollTop = thread.scrollHeight;
}

// ---------- Ask ----------
function setResolving(on) {
  sendBtn.disabled = on;
  sendBtn.innerHTML = on ? '<span class="orbit"></span>' : "Send";
  setStatus(on ? "retrieving" : "ready", on);
}

async function ask(question) {
  if (!question || !question.trim()) return;
  lastQuestion = question;
  addUserMessage(question);
  questionInput.value = "";
  const thinking = addThinking();
  setResolving(true);

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        source_filter: currentSourceFilter,
        top_k: topkSlider.value,
        threshold: thresholdSlider.value,
      }),
    });
    const data = await res.json();
    thinking.remove();
    setResolving(false);

    if (data.error) {
      showBanner("error", data.error);
      // Retrieval ran before the LLM did, so its results are still worth showing.
      if (data.evidence) renderEvidence(data.evidence);
      if (data.retrieved_ids) renderPlot(data.retrieved_ids, data.query_point, data.grounded_ids !== false, (data.evidence || []).map((e) => e.relevance_score));
      return;
    }

    lastAnswerLanguage = data.language || "en";
    addAssistantMessage(data);
    renderEvidence(data.evidence);
    renderPlot(data.retrieved_ids, data.query_point, data.grounded_ids !== false && data.grounded !== false, (data.evidence || []).map((e) => e.relevance_score));
  } catch (e) {
    thinking.remove();
    setResolving(false);
    showBanner("error", "Couldn't reach the assistant.");
  }
}

sendBtn.addEventListener("click", () => ask(questionInput.value));
questionInput.addEventListener("keydown", (e) => { if (e.key === "Enter") ask(questionInput.value); });
regenBtn.addEventListener("click", () => { if (lastQuestion) ask(lastQuestion); else showBanner("warning", "Nothing to regenerate yet."); });

// ---------- Settings ----------
settingsToggle.addEventListener("click", () => {
  const open = settingsBody.classList.toggle("open");
  settingsChevron.textContent = open ? "expand_less" : "expand_more";
  settingsToggle.setAttribute("aria-expanded", String(open));
});
topkSlider.addEventListener("input", () => (topkVal.textContent = topkSlider.value));
thresholdSlider.addEventListener("input", () => (thresholdVal.textContent = thresholdSlider.value));

infoToggle.addEventListener("click", () => {
  appShell.classList.toggle("info-hidden");
  infoPanel.classList.toggle("collapsed");
});

// ---------- Collapsible sidebar ----------
const railToggle = $("rail-toggle");
const RAIL_KEY = "nexora-rail-hidden";

function paintRail() {
  const hidden = appShell.classList.contains("rail-hidden");
  railToggle.querySelector("span").textContent = hidden ? "left_panel_open" : "left_panel_close";
  railToggle.setAttribute("aria-expanded", String(!hidden));
  try { localStorage.setItem(RAIL_KEY, hidden ? "1" : "0"); } catch (e) {}
}
try { if (localStorage.getItem(RAIL_KEY) === "1") appShell.classList.add("rail-hidden"); } catch (e) {}
if (railToggle) {
  paintRail();
  railToggle.addEventListener("click", () => { appShell.classList.toggle("rail-hidden"); paintRail(); });
}


// ---------- Nav tabs ----------
document.querySelectorAll(".nav-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".nav-tab").forEach((t) => {
      t.classList.remove("active"); t.setAttribute("aria-selected", "false");
    });
    tab.classList.add("active"); tab.setAttribute("aria-selected", "true");

    showView(tab.dataset.tab);
  });
});

// ---------- Views ----------
function showView(which) {
  const map = { chat: "view-chat", knowledge: "view-knowledge", settings: "view-settings" };
  Object.entries(map).forEach(([key, id]) => {
    const el = $(id);
    if (el) el.hidden = key !== which;
  });
  // The lattice belongs to the chat surface only. Hiding the container also
  // stops it doing work: a zero-size container makes every pointer position
  // fall outside it, so nothing energises while another tab is open.
  const grid = $("grid-bg");
  if (grid) {
    grid.hidden = which !== "chat";
    if (window.__grid) which === "chat" ? window.__grid._wake() : window.__grid.stop();
  }
}
showView("chat");

// The Settings view mirrors the composer's inline sliders; keep both in sync so
// the value is the same wherever you change it.
function linkSliders(a, aVal, b, bVal) {
  const A = $(a), B = $(b), AV = $(aVal), BV = $(bVal);
  if (!A || !B) return;
  const sync = (from, to, fromVal, toVal) => {
    to.value = from.value;
    if (fromVal) fromVal.textContent = from.value;
    if (toVal) toVal.textContent = from.value;
  };
  A.addEventListener("input", () => sync(A, B, AV, BV));
  B.addEventListener("input", () => sync(B, A, BV, AV));
}
linkSliders("topk-slider", "topk-val", "topk-slider-2", "topk-val-2");
linkSliders("threshold-slider", "threshold-val", "threshold-slider-2", "threshold-val-2");

// ---------- Rebuild / clear / new ----------
rebuildBtn.addEventListener("click", async () => {
  rebuildBtn.disabled = true;
  showBanner("info", "Rebuilding knowledge base…");
  try {
    const data = await (await fetch("/api/rebuild_index", { method: "POST" })).json();
    if (data.status === "no_documents") showBanner("warning", data.message || "No documents found.");
    else showBanner("info", `Rebuilt · ${data.chunks} chunks.`);
  } catch (e) { showBanner("error", "Rebuild failed."); }
  rebuildBtn.disabled = false;
  await loadStatus(); await loadCorpusPoints();
});

clearChatBtn.addEventListener("click", async () => {
  window.speechSynthesis && window.speechSynthesis.cancel();
  await fetch("/api/clear_chat", { method: "POST" });
  chatInner.innerHTML = "";
  if (emptyState) chatInner.appendChild(emptyState);
  renderEvidence([]); clearPlot();
  await loadStatus(); await loadCorpusPoints(); await loadHistory();
});

newChatBtn.addEventListener("click", async () => {
  await fetch("/api/new_session", { method: "POST" });
  chatInner.innerHTML = "";
  if (emptyState) chatInner.appendChild(emptyState);
  renderEvidence([]); clearPlot();
  await loadStatus(); await loadCorpusPoints(); await loadHistory();
});

function relTime(ts) {
  if (!ts) return "";
  const secs = Math.max(0, Date.now() / 1000 - ts);
  if (secs < 60) return "now";
  if (secs < 3600) return Math.floor(secs / 60) + "m";
  if (secs < 86400) return Math.floor(secs / 3600) + "h";
  return Math.floor(secs / 86400) + "d";
}

// ---------- History ----------
async function loadHistory() {
  try {
    const data = await (await fetch("/api/history")).json();
    historyList.innerHTML = "";
    if (!data.sessions.length) {
      historyList.innerHTML = `<p class="text-[12px] py-1" style="color:var(--dim)">No conversations yet.</p>`;
      return;
    }
    data.sessions.forEach((s) => {
      const row = document.createElement("button");
      row.className = "conv-row";
      row.innerHTML = `<span class="truncate">${escapeHtml(s.title || "New conversation")}</span>` +
                      `<span class="mono shrink-0" style="color:var(--dim)">${relTime(s.last_updated)}</span>`;
      row.title = `${s.message_count} messages`;
      row.addEventListener("click", async () => {
        const t = await (await fetch(`/api/history/${s.session_id}`, { method: "POST" })).json();
        chatInner.innerHTML = "";
        t.messages.forEach((m) => {
          if (m.role === "user") addUserMessage(m.content);
          else addAssistantMessage({ answer: m.content, sources: (m.meta || {}).sources || [], language: (m.meta || {}).language, grounded: true });
        });
        await loadStatus(); await loadCorpusPoints();
      });
      historyList.appendChild(row);
    });
  } catch (e) { console.error("history failed", e); }
}

// Uploads are disabled: Nexora answers from a fixed set of official college
// policy documents. Re-enable via UPLOADS_ENABLED in src/config.py.

// ---------- Voice input ----------
let recognition = null, listening = false;
function getSpeechRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  return SR ? new SR() : null;
}
micBtn.addEventListener("click", () => {
  if (listening) { recognition && recognition.stop(); return; }
  recognition = getSpeechRecognition();
  if (!recognition) { showBanner("warning", "Voice input needs Chrome. Type your question instead."); return; }

  recognition.lang = "en-IN";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  recognition.onstart = () => { listening = true; micBtn.classList.add("mic-listening"); micStatus.textContent = "Listening…"; };
  recognition.onresult = (event) => {
    const text = event.results[0][0].transcript;
    questionInput.value = text;
    ask(text);
  };
  recognition.onerror = () => showBanner("warning", "Didn't catch that.");
  recognition.onend = () => { listening = false; micBtn.style.color = ""; micStatus.innerHTML = ""; };
  recognition.start();
});

// ---------- Text to speech ----------
function toggleSpeech(text, langCode, btn) {
  if (!window.speechSynthesis) { showBanner("warning", "Speech isn't supported here."); return; }
  if (activeSpeechBtn === btn) { window.speechSynthesis.cancel(); resetSpeechBtn(btn); activeSpeechBtn = null; return; }
  if (activeSpeechBtn) resetSpeechBtn(activeSpeechBtn);
  window.speechSynthesis.cancel();

  const utter = new SpeechSynthesisUtterance(String(text).replace(/[#*`_>]/g, ""));
  utter.lang = VOICE_LANG_MAP[langCode] || "en-IN";
  utter.onend = () => { resetSpeechBtn(btn); activeSpeechBtn = null; };
  btn.innerHTML = `<span class="material-symbols-outlined text-[15px]">stop_circle</span>`;
  btn.style.color = "var(--retrieval)";
  activeSpeechBtn = btn;
  window.speechSynthesis.speak(utter);
}
function resetSpeechBtn(btn) {
  btn.style.color = "";
  btn.innerHTML = `<span class="material-symbols-outlined text-[15px]">volume_up</span>`;
}

window.addEventListener("sky-ready", () => {
  if (corpusPoints.length) skies().forEach((sky) => sky.setPoints(corpusPoints));
});

if (window.NexoraTheme) window.NexoraTheme.mount($("theme-toggle"));

// ---------- Restore ----------
(async function init() {
  await loadStatus();
  await loadCorpusPoints();
  await loadHistory();
  try {
    const t = await (await fetch("/api/session_transcript")).json();
    if (t.messages && t.messages.length) {
      t.messages.forEach((m) => {
        if (m.role === "user") addUserMessage(m.content);
        else addAssistantMessage({ answer: m.content, sources: (m.meta || {}).sources || [], language: (m.meta || {}).language, grounded: true });
      });
    }
  } catch (e) {}
})();
