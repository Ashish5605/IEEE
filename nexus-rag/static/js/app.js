// Nexora frontend logic
// Handles: chat send/receive, sidebar status, language + source selection,
// browser-based voice input (Web Speech API) and text-to-speech.

const chatInner = document.getElementById("chat-inner");
const emptyState = document.getElementById("empty-state");
const questionInput = document.getElementById("question-input");
const sendBtn = document.getElementById("send-btn");
const micBtn = document.getElementById("mic-btn");
const micStatus = document.getElementById("mic-status");
const clearChatBtn = document.getElementById("clear-chat-btn");
const rebuildBtn = document.getElementById("rebuild-btn");
const settingsToggle = document.getElementById("settings-toggle");
const settingsBody = document.getElementById("settings-body");
const settingsChevron = document.getElementById("settings-chevron");
const topkSlider = document.getElementById("topk-slider");
const topkVal = document.getElementById("topk-val");
const thresholdSlider = document.getElementById("threshold-slider");
const thresholdVal = document.getElementById("threshold-val");
const sourceSelector = document.getElementById("source-selector");
const fileInput = document.getElementById("file-input");
const uploadDropzone = document.getElementById("upload-dropzone");
const historyToggle = document.getElementById("history-toggle");
const historyChevron = document.getElementById("history-chevron");
const historyList = document.getElementById("history-list");
const newChatBtn = document.getElementById("new-chat-btn");

const currentLanguage = "en";
let currentSourceFilter = null;

const VOICE_LANG_MAP = { en: "en-IN" };

// ---------- Sidebar: status + settings ----------

async function loadStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();

    document.getElementById("doc-count").textContent = data.documents.length;
    const badge = document.getElementById("index-status-badge");
    if (data.indexed) {
      badge.textContent = `ready · ${data.chunk_count} chunks`;
      badge.className = "text-xs px-2 py-0.5 rounded-full bg-cyber-mint/10 text-cyber-mint border border-cyber-mint/30";
    } else {
      badge.textContent = "not indexed";
      badge.className = "text-xs px-2 py-0.5 rounded-full bg-danger/10 text-danger border border-danger/30 status-pulse";
    }

    // Build knowledge source radio list
    sourceSelector.innerHTML = "";
    sourceSelector.appendChild(sourceOption("All documents", null, true));
    data.documents.forEach((doc) => sourceSelector.appendChild(sourceOption(doc, doc, false)));

    topkSlider.value = data.top_k;
    topkVal.textContent = data.top_k;
    thresholdSlider.value = data.relevance_threshold;
    thresholdVal.textContent = data.relevance_threshold;
  } catch (e) {
    console.error("Failed to load status", e);
  }
}

function sourceOption(label, value, checked) {
  const wrapper = document.createElement("label");
  wrapper.className = "kb-row flex items-center gap-2 text-sm text-on-surface-variant hover:text-on-surface cursor-pointer py-1.5 px-1.5";
  wrapper.innerHTML = `
    <input type="radio" name="source" class="accent-primary-container" ${checked ? "checked" : ""}/>
    <span class="truncate">${label}</span>
  `;
  wrapper.querySelector("input").addEventListener("change", () => {
    currentSourceFilter = value;
  });
  return wrapper;
}

function _openCollapse(body, chevron, maxCap) {
  body.classList.add("open");
  const target = maxCap ? Math.min(body.scrollHeight, maxCap) : body.scrollHeight;
  body.style.maxHeight = target + "px";
  chevron.classList.add("open");
}
function _closeCollapse(body, chevron) {
  body.style.maxHeight = "0px";
  body.classList.remove("open");
  chevron.classList.remove("open");
}

settingsToggle.addEventListener("click", () => {
  const isOpen = settingsBody.classList.contains("open");
  isOpen ? _closeCollapse(settingsBody, settingsChevron) : _openCollapse(settingsBody, settingsChevron);
});
topkSlider.addEventListener("input", () => (topkVal.textContent = topkSlider.value));
thresholdSlider.addEventListener("input", () => (thresholdVal.textContent = thresholdSlider.value));

rebuildBtn.addEventListener("click", async () => {
  rebuildBtn.disabled = true;
  rebuildBtn.querySelector("span:last-child") && (rebuildBtn.innerHTML = `<span class="material-symbols-outlined text-sm animate-spin">progress_activity</span> Rebuilding…`);
  try {
    const res = await fetch("/api/rebuild_index", { method: "POST" });
    const data = await res.json();
    if (data.status === "no_documents") {
      showBanner("warning", data.message || "No documents found to index.");
    }
  } catch (e) {
    showBanner("error", "Couldn't rebuild the knowledge base.");
  }
  rebuildBtn.disabled = false;
  rebuildBtn.innerHTML = `<span class="material-symbols-outlined text-sm">refresh</span> Rebuild knowledge base`;
  loadStatus();
});

clearChatBtn.addEventListener("click", async () => {
  window.speechSynthesis && window.speechSynthesis.cancel();
  activeSpeechBtn = null;
  await fetch("/api/clear_chat", { method: "POST" });
  chatInner.innerHTML = "";
  chatInner.appendChild(emptyState);
  loadStatus();
});

// ---------- Chat ----------

function scrollToBottom() {
  const thread = document.getElementById("chat-thread");
  thread.scrollTop = thread.scrollHeight;
}

function appendUserMessage(text) {
  emptyState.remove();
  const div = document.createElement("div");
  div.className = "msg-in flex justify-end";
  div.innerHTML = `
    <div class="bg-primary-container/80 backdrop-blur-md text-white p-4 rounded-3xl rounded-tr-sm max-w-[75%] shadow-[0_10px_25px_rgba(108,92,231,0.25)]">
      <p class="text-base">${escapeHtml(text)}</p>
    </div>`;
  chatInner.appendChild(div);
  scrollToBottom();
}

function appendThinkingBubble() {
  emptyState.remove && emptyState.parentNode && emptyState.remove();
  const div = document.createElement("div");
  div.className = "msg-in flex justify-start";
  div.id = "thinking-bubble";
  div.innerHTML = `
    <div class="glass-panel px-6 py-4 rounded-3xl rounded-tl-sm shadow-[0_15px_35px_rgba(0,0,0,0.5)] bg-surface-container/60 flex items-center gap-3">
      <div class="nexora-orb nexora-orb--sm nexora-orb--pulse">
        <div class="orb-core"></div>
      </div>
      <span class="thinking-dots"><span></span><span></span><span></span></span>
    </div>`;
  chatInner.appendChild(div);
  scrollToBottom();
  return div;
}

function renderMarkdown(text) {
  if (window.marked) {
    return marked.parse(text || "", { breaks: true });
  }
  return escapeHtml(text);
}

function appendAssistantMessage(data) {
  emptyState.remove && emptyState.parentNode && emptyState.remove();
  const div = document.createElement("div");
  div.className = "msg-in flex justify-start";

  const sourcesHtml = (data.sources && data.sources.length)
    ? data.sources.map(s => `
        <span class="source-chip inline-flex items-center gap-2 bg-obsidian-base/60 border border-glass-stroke px-3 py-1.5 rounded-lg font-mono text-xs text-cyber-mint">
          <span class="material-symbols-outlined text-xs">description</span>
          ${escapeHtml(s.source)}${s.page ? ` — Page ${s.page}` : ""}
        </span>`).join("")
    : "";

  const evidenceHtml = (data.evidence && data.evidence.length)
    ? data.evidence.map(ev => `
        <div class="border-b border-glass-stroke last:border-0 py-3">
          <div class="flex items-center justify-between mb-1">
            <span class="text-xs font-mono text-on-surface">${escapeHtml(ev.source)}${ev.page ? ` · page ${ev.page}` : ""}</span>
            <span class="text-[10px] uppercase tracking-wider relevance-${ev.relevance_label.toLowerCase()}">${ev.relevance_label} relevance</span>
          </div>
          <p class="text-xs text-on-surface-variant leading-relaxed">${escapeHtml(ev.passage)}</p>
        </div>`).join("")
    : `<p class="text-xs text-on-surface-variant py-2">No evidence passages available.</p>`;

  const uid = "msg-" + Math.random().toString(36).slice(2, 9);

  div.innerHTML = `
    <div class="glass-panel p-6 rounded-3xl rounded-tl-sm max-w-[85%] shadow-[0_15px_35px_rgba(0,0,0,0.5)] bg-surface-container/60">
      <div class="flex items-center gap-3 mb-4">
        <div class="nexora-orb nexora-orb--sm">
          <div class="orb-core">
            <span class="material-symbols-outlined text-cyber-mint" style="font-size: 12px; font-variation-settings: 'FILL' 1;">lightbulb</span>
          </div>
        </div>
        <h4 class="text-sm font-bold text-on-surface">Answer</h4>
      </div>
      <div class="text-base text-on-surface mb-5 leading-relaxed answer-markdown" id="${uid}-text">${renderMarkdown(data.answer)}</div>
      ${sourcesHtml ? `
        <div class="mb-4 bg-obsidian-elevated/40 p-4 rounded-2xl border border-glass-stroke">
          <p class="font-mono text-[10px] text-on-surface-variant mb-2 uppercase tracking-wider">Sources</p>
          <div class="flex flex-wrap gap-2">${sourcesHtml}</div>
        </div>` : ""}
      <div class="border-t border-glass-stroke pt-4 flex items-center justify-between">
        <button class="evidence-toggle flex items-center gap-2 text-cyber-mint hover:text-secondary text-sm font-medium transition-colors">
          <span class="material-symbols-outlined chevron-rotate" style="font-size: 18px;" data-evidence-icon>search</span>
          View evidence
        </button>
        <button class="listen-btn text-on-surface-variant hover:text-cyber-mint p-2 rounded-full hover:bg-glass-stroke transition-colors" aria-label="Listen">
          <span class="material-symbols-outlined listen-icon">volume_up</span>
        </button>
      </div>
      <div class="evidence-body mt-2">${evidenceHtml}</div>
    </div>`;

  const evidenceBody = div.querySelector(".evidence-body");
  div.querySelector(".evidence-toggle").addEventListener("click", () => {
    const opening = !evidenceBody.classList.contains("open");
    if (opening) {
      evidenceBody.classList.add("open");
      evidenceBody.style.maxHeight = evidenceBody.scrollHeight + "px";
    } else {
      evidenceBody.style.maxHeight = "0px";
      evidenceBody.classList.remove("open");
    }
  });
  const listenBtn = div.querySelector(".listen-btn");
  listenBtn.addEventListener("click", () => {
    toggleSpeech(data.answer, data.language || "en", listenBtn);
  });

  chatInner.appendChild(div);
  scrollToBottom();
}

function showBanner(variant, text) {
  const colors = {
    warning: "bg-warning/10 text-warning border-warning/30",
    error: "bg-danger/10 text-danger border-danger/30",
    info: "bg-electric-indigo/10 text-electric-indigo border-electric-indigo/30",
  };
  const div = document.createElement("div");
  div.className = `banner-in flex justify-center`;
  div.innerHTML = `<div class="text-xs px-4 py-2 rounded-full border ${colors[variant] || colors.info}">${escapeHtml(text)}</div>`;
  chatInner.appendChild(div);
  scrollToBottom();
}

function escapeHtml(str) {
  const d = document.createElement("div");
  d.textContent = str || "";
  return d.innerHTML;
}

async function sendQuestion(text) {
  const question = (text || questionInput.value).trim();
  if (!question) return;
  questionInput.value = "";
  sendBtn.classList.remove("send-armed");
  appendUserMessage(question);
  const thinkingEl = appendThinkingBubble();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        language: currentLanguage,
        source_filter: currentSourceFilter,
        top_k: topkSlider.value,
        threshold: thresholdSlider.value,
      }),
    });
    const data = await res.json();
    thinkingEl.remove();
    if (!res.ok) {
      showBanner("error", data.error || "Something went wrong.");
      return;
    }
    appendAssistantMessage(data);
  } catch (e) {
    thinkingEl.remove();
    showBanner("error", "The AI service is currently unavailable. Please try again.");
  }
}

sendBtn.addEventListener("click", () => sendQuestion());
questionInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendQuestion();
});
questionInput.addEventListener("input", () => {
  sendBtn.classList.toggle("send-armed", questionInput.value.trim().length > 0);
});

// ---------- Voice input (Web Speech API) ----------

let recognition = null;
let listening = false;

function getSpeechRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  return SR ? new SR() : null;
}

micBtn.addEventListener("click", () => {
  if (listening) {
    recognition && recognition.stop();
    return;
  }
  recognition = getSpeechRecognition();
  if (!recognition) {
    showBanner("warning", "Voice input isn't supported in this browser. Try Chrome, or type your question instead.");
    return;
  }

  recognition.lang = VOICE_LANG_MAP[currentLanguage] || "en-IN";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.onstart = () => {
    listening = true;
    micBtn.classList.add("mic-listening");
    micStatus.textContent = "Listening...";
  };

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    questionInput.value = transcript;
    micStatus.textContent = "Processing...";
  };

  recognition.onerror = () => {
    showBanner("warning", "Speech recognition failed — you can type your question instead.");
    micStatus.textContent = "";
  };

  recognition.onend = () => {
    listening = false;
    micBtn.classList.remove("mic-listening");
    micStatus.textContent = "";
    if (questionInput.value.trim()) sendQuestion();
  };

  recognition.start();
});

// ---------- Text-to-speech ----------

let activeSpeechBtn = null; // the listen-btn currently showing "speaking" state

const EQ_BARS_HTML = `<span class="eq-bars"><span></span><span></span><span></span></span>`;

function _setListenIdle(btn) {
  btn.classList.remove("listen-speaking");
  btn.innerHTML = `<span class="material-symbols-outlined listen-icon">volume_up</span>`;
}

function _setListenSpeaking(btn) {
  btn.classList.add("listen-speaking");
  btn.innerHTML = EQ_BARS_HTML;
}

function _resetActiveSpeechBtn() {
  if (activeSpeechBtn) _setListenIdle(activeSpeechBtn);
  activeSpeechBtn = null;
}

function toggleSpeech(text, langCode, btn) {
  if (!("speechSynthesis" in window)) {
    showBanner("warning", "Text-to-speech isn't supported in this browser.");
    return;
  }

  // Clicking the button that's currently speaking stops it.
  if (activeSpeechBtn === btn) {
    window.speechSynthesis.cancel();
    _resetActiveSpeechBtn();
    return;
  }

  // Switching to a different message's audio, or starting fresh.
  window.speechSynthesis.cancel();
  _resetActiveSpeechBtn();

  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = VOICE_LANG_MAP[langCode] || "en-IN";

  utter.onend = _resetActiveSpeechBtn;
  utter.onerror = _resetActiveSpeechBtn;

  activeSpeechBtn = btn;
  _setListenSpeaking(btn);
  window.speechSynthesis.speak(utter);
}

// ---------- Upload (drag-and-drop + browse) ----------

async function uploadFiles(fileList) {
  const files = [...fileList];
  if (!files.length) return;

  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));

  showBanner("info", `Uploading ${files.length} file${files.length > 1 ? "s" : ""}...`);
  try {
    const res = await fetch("/api/upload", { method: "POST", body: formData });
    const data = await res.json();
    const rejected = (data.results || []).filter(r => r.status === "rejected" || r.status === "error");
    const indexed = (data.results || []).filter(r => r.status === "indexed");
    if (indexed.length) {
      showBanner("info", `Added ${indexed.map(r => r.filename).join(", ")} to the knowledge base.`);
    }
    rejected.forEach(r => showBanner("warning", `${r.filename}: ${r.message || "couldn't be added."}`));
    loadStatus();
  } catch (e) {
    showBanner("error", "Upload failed. Please try again.");
  }
}

fileInput.addEventListener("change", () => uploadFiles(fileInput.files));

["dragenter", "dragover"].forEach(evt =>
  uploadDropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    uploadDropzone.classList.add("dropzone-active");
  })
);
["dragleave", "drop"].forEach(evt =>
  uploadDropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    uploadDropzone.classList.remove("dropzone-active");
  })
);
uploadDropzone.addEventListener("drop", (e) => {
  if (e.dataTransfer && e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files);
});

// Also allow dropping anywhere on the chat thread, not just the sidebar box.
const chatThreadEl = document.getElementById("chat-thread");
["dragenter", "dragover"].forEach(evt =>
  chatThreadEl.addEventListener(evt, (e) => e.preventDefault())
);
chatThreadEl.addEventListener("drop", (e) => {
  e.preventDefault();
  if (e.dataTransfer && e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files);
});

// ---------- History ----------

historyToggle.addEventListener("click", async () => {
  const isOpen = historyList.classList.contains("open");
  if (isOpen) {
    _closeCollapse(historyList, historyChevron);
  } else {
    await loadHistoryList();
    _openCollapse(historyList, historyChevron, 192);
  }
});

async function loadHistoryList() {
  try {
    const res = await fetch("/api/history");
    const data = await res.json();
    historyList.innerHTML = "";
    if (!data.sessions || !data.sessions.length) {
      historyList.innerHTML = `<p class="text-xs text-on-surface-variant py-2">No past conversations yet.</p>`;
      return;
    }
    data.sessions.forEach((s) => {
      const btn = document.createElement("button");
      btn.className = "kb-row text-left text-xs text-on-surface-variant hover:text-on-surface px-2 py-2 truncate";
      btn.textContent = s.title || "Conversation";
      btn.title = `${s.message_count} messages`;
      btn.addEventListener("click", () => loadSessionIntoChat(s.session_id));
      historyList.appendChild(btn);
    });
    // Re-measure now that content changed while open.
    if (historyList.classList.contains("open")) {
      historyList.style.maxHeight = Math.min(historyList.scrollHeight, 192) + "px";
    }
  } catch (e) {
    console.error("Failed to load history", e);
  }
}

async function loadSessionIntoChat(sessionId) {
  try {
    const res = await fetch(`/api/history/${sessionId}`, { method: "POST" });
    const data = await res.json();
    renderTranscript(data.messages || []);
  } catch (e) {
    showBanner("error", "Couldn't load that conversation.");
  }
}

function renderTranscript(messages) {
  chatInner.innerHTML = "";
  if (!messages.length) {
    chatInner.appendChild(emptyState);
    return;
  }
  messages.forEach((m) => {
    if (m.role === "user") {
      appendUserMessage(m.content);
    } else {
      appendAssistantMessage({
        answer: m.content,
        sources: (m.meta && m.meta.sources) || [],
        evidence: (m.meta && m.meta.evidence) || [],
        language: m.meta && m.meta.language,
      });
    }
  });
}

newChatBtn.addEventListener("click", async () => {
  window.speechSynthesis && window.speechSynthesis.cancel();
  activeSpeechBtn = null;
  await fetch("/api/new_session", { method: "POST" });
  chatInner.innerHTML = "";
  chatInner.appendChild(emptyState);
  loadStatus();
});

// ---------- Init ----------
loadStatus();

// Restore the current session's chat on page load, so switching tabs or
// refreshing the browser never loses the conversation.
(async function restoreTranscript() {
  try {
    const res = await fetch("/api/session_transcript");
    const data = await res.json();
    if (data.messages && data.messages.length) {
      renderTranscript(data.messages);
    }
  } catch (e) {
    console.error("Failed to restore transcript", e);
  }
})();
