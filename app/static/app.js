function mbSetTheme(value) {
  try {
    localStorage.setItem("mb-theme", value);
    document.documentElement.setAttribute("data-theme", value);
  } catch (e) {}
}

function mbToggleTheme() {
  const cur = document.documentElement.getAttribute("data-theme") || "hell";
  mbSetTheme(cur === "dunkel" ? "hell" : "dunkel");
}

(function () {
  const box = document.getElementById("log-box");
  if (box && box.dataset.runId) {
    const runId = box.dataset.runId;
    const dot = document.getElementById("log-dot");
    const status = document.getElementById("log-status");
    if (status) status.textContent = "läuft";

    function append(entry) {
      const line = document.createElement("span");
      line.className = "log-line " + (entry.level || "info");
      const ts = new Date().toLocaleTimeString();
      line.textContent = "[" + ts + "] " + entry.message;
      box.appendChild(line);
      box.scrollTop = box.scrollHeight;
    }

    const source = new EventSource("/api/events/" + runId);
    source.onmessage = function (ev) {
      try { append(JSON.parse(ev.data)); } catch (e) { /* ignore */ }
    };
    source.addEventListener("done", function () {
      source.close();
      if (status) status.textContent = "fertig";
      if (dot) dot.style.background = "#22c55e";
    });
    source.onerror = function () {
      if (status) status.textContent = "getrennt";
    };
  }
})();

function mbApplyProvider(select) {
  const data = window.MB_PROVIDERS || {};
  const preset = data[select.value];
  if (!preset) return;
  const host = document.getElementById("mail_host");
  const port = document.getElementById("mail_port");
  const note = document.getElementById("mail-note");
  if (preset.imap && host) host.value = preset.imap;
  if (preset.port && port) port.value = preset.port;
  if (note) note.textContent = preset.note || "";
}

/* ---------- Jobs: Master-Detail mit Echtzeit-Filter ---------- */
function mbEsc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

(function initJobs() {
  if (!window.MB_JOBS || !document.getElementById("job-rows")) return;
  const jobs = window.MB_JOBS;
  const labels = window.MB_STATUS_LABELS || {};
  const colors = window.MB_STATUS_COLORS || {};
  const statusList = window.MB_STATUS_LIST || [];
  let currentId = null;
  const I18N = window.MB_I18N || {};
  const L = function (key, fallback) { return I18N[key] || fallback; };

  const statusBoxes = Array.prototype.slice.call(document.querySelectorAll(".f-status"));

  const FILTER_KEYS = ["f-q", "f-source", "f-remote", "f-loc", "f-fit", "f-from", "f-to", "f-sort"];
  function saveFilters() {
    const st = {};
    FILTER_KEYS.forEach(function (id) {
      const el = document.getElementById(id);
      if (el) st[id] = el.value;
    });
    st.status = statusBoxes.filter(function (c) { return c.checked; }).map(function (c) { return c.value; });
    try { localStorage.setItem("mb-filters", JSON.stringify(st)); } catch (e) {}
  }
  function loadFilters() {
    let st = null;
    try { st = JSON.parse(localStorage.getItem("mb-filters") || "null"); } catch (e) {}
    if (!st) return;
    FILTER_KEYS.forEach(function (id) {
      const el = document.getElementById(id);
      if (el && st[id] !== undefined) el.value = st[id];
    });
    if (Array.isArray(st.status)) {
      statusBoxes.forEach(function (c) { c.checked = st.status.indexOf(c.value) >= 0; });
    }
  }
  loadFilters();

  function activeJobs() {
    const q = (document.getElementById("f-q").value || "").toLowerCase();
    const checkedStatus = {};
    statusBoxes.forEach(function (c) { if (c.checked) checkedStatus[c.value] = 1; });
    const source = document.getElementById("f-source").value;
    const remote = document.getElementById("f-remote").value;
    const loc = (document.getElementById("f-loc") ? document.getElementById("f-loc").value : "").toLowerCase();
    const fit = parseInt(document.getElementById("f-fit").value || "0", 10);
    const from = document.getElementById("f-from").value;
    const to = document.getElementById("f-to").value;
    const sort = document.getElementById("f-sort").value;

    let out = jobs.filter(function (j) {
      const blob = (j.company + " " + j.title + " " + (j.location || "") + " " + (j.rationale || "")).toLowerCase();
      if (q && blob.indexOf(q) === -1) return false;
      if (!checkedStatus[j.status]) return false;
      if (source && j.source !== source) return false;
      if (remote === "1" && !j.remote) return false;
      if (loc && (j.location || "").toLowerCase().indexOf(loc) === -1) return false;
      if (fit > 0 && (j.score || 0) < fit) return false;
      const d = (j.found_at || "").slice(0, 10);
      if (from && d < from) return false;
      if (to && d > to) return false;
      return true;
    });
    out.sort(function (a, b) {
      if (sort === "score") return (b.score || 0) - (a.score || 0);
      if (sort === "company") return a.company.localeCompare(b.company);
      if (sort === "status") return String(a.status).localeCompare(String(b.status));
      return String(b.found_at).localeCompare(String(a.found_at));
    });
    return out;
  }

  function renderList() {
    const tbody = document.getElementById("job-rows");
    const items = activeJobs();
    document.getElementById("job-count").textContent = "(" + items.length + ")";
    tbody.innerHTML = items.map(function (j) {
      const badge = '<span class="badge" style="--bc:' + (colors[j.status] || "#94a3b8") + '">' +
        (labels[j.status] || j.status) + "</span>";
      return '<tr class="' + (j.id === currentId ? "active" : "") + '" data-id="' + j.id + '">' +
        '<td class="co">' + mbEsc(j.company) + "</td>" +
        '<td class="ti">' + mbEsc(j.title) + "</td>" +
        '<td class="ort">' + (j.location ? mbEsc(j.location) : "–") +
          (j.remote ? ' <span class="remote">· remote</span>' : "") + "</td>" +
        '<td class="fit">' + (j.score || "–") + "</td>" +
        "<td>" + badge + "</td>" +
        '<td class="date">' + mbEsc((j.found_at || "").slice(0, 10)) + "</td>" +
        "</tr>";
    }).join("") || '<tr><td colspan="6" class="muted" style="padding:20px">' + L("none", "Keine Jobs.") + "</td></tr>";

    tbody.querySelectorAll("tr[data-id]").forEach(function (el) {
      el.addEventListener("click", function () { showDetail(parseInt(el.dataset.id, 10)); });
    });
  }

  function showDetail(id) {
    currentId = id;
    const j = jobs.find(function (x) { return x.id === id; });
    const box = document.getElementById("job-detail");
    if (!j) return;
    const badge = '<span class="badge" style="--bc:' + (colors[j.status] || "#94a3b8") + '">' +
      (labels[j.status] || j.status) + "</span>";
    const links = [];
    if (j.url) links.push('<a class="btn btn-sm" href="' + mbEsc(j.url) + '" target="_blank" rel="noopener">' + L("job", "Stellenanzeige") + "</a>");
    if (j.company_url) links.push('<a class="btn btn-sm" href="' + mbEsc(j.company_url) + '" target="_blank" rel="noopener">' + L("company", "Unternehmen") + "</a>");

    const events = [];
    function addEntry(displayDate, sortKey, kind, text) {
      events.push({ date: displayDate || "", sort: sortKey || "", kind: kind, text: text });
    }
    if (j.found_at) addEntry((j.found_at || "").slice(0, 10), j.found_at, "gefunden", "Stelle gefunden");
    (j.emails || []).forEach(function (m) {
      const d = (m.date || "").slice(0, 10);
      addEntry(d, d + "T12:00:00", "mail", mbEsc(m.from_addr) + " – " + mbEsc(m.subject));
    });
    (j.events || []).forEach(function (e) {
      const d = (e.date || "").slice(0, 10);
      addEntry(d, e.ts || (d + "T12:30:00"), "status", mbEsc(e.text));
    });
    events.sort(function (a, b) {
      if (!a.sort) return 1; if (!b.sort) return -1;
      return a.sort < b.sort ? -1 : (a.sort > b.sort ? 1 : 0);
    });
    const timeline = events.map(function (e) {
      return '<li class="tl-' + e.kind + '"><span class="tl-date">' + (e.date || "–") + "</span>" +
        '<span class="tl-text">' + e.text + "</span></li>";
    }).join("");

    const statusOptions = statusList.map(function (s) {
      return '<option value="' + s + '"' + (s === j.status ? " selected" : "") + ">" + (labels[s] || s) + "</option>";
    }).join("");

    box.innerHTML =
      "<h2>" + mbEsc(j.title) + "</h2>" +
      '<p class="subtitle" style="margin-top:2px"><strong>' + mbEsc(j.company) + "</strong>" +
        (j.location ? " · " + mbEsc(j.location) : "") + (j.remote ? ' · <span class="remote">remote</span>' : "") + "</p>" +
      '<div class="filters" style="margin-bottom:12px">' + badge +
        (j.manual ? '<span class="tag" style="border-color:#f59e0b;color:#b45309">manuell gesetzt</span>' : "") +
        (j.score ? '<span class="pill">Fit ' + j.score + (j.fit ? " · " + mbEsc(j.fit) : "") + "</span>" : "") +
        '<span class="tag">Quelle: ' + mbEsc(j.source) + "</span>" +
        (j.published_at ? '<span class="tag">Veröffentlicht: ' + mbEsc(j.published_at) + "</span>" : "") +
        '<span class="tag">Gefunden: ' + mbEsc((j.found_at || "").slice(0, 10)) + "</span>" +
        links.join(" ") + "</div>" +
      "<h3>" + L("why", "Warum der Job passt") + "</h3><p>" + (mbEsc(j.rationale) || "<span class='muted'>—</span>") + "</p>" +
      "<h3>" + L("what", "Was die Position ausmacht") + "</h3><p>" + (mbEsc(j.description) || "<span class='muted'>—</span>") + "</p>" +
      (j.phase ? "<h3>" + L("appstatus", "Bewerbungsstatus") + '</h3><p><span class="pill">' + mbEsc(j.phase) + "</span> " +
        (j.response_at ? '<span class="small muted">Antwort: ' + mbEsc(j.response_at) + "</span>" : "") +
        (j.app_notes ? "<br><span class=\"small\">" + mbEsc(j.app_notes) + "</span>" : "") + "</p>" : "") +
      "<h3>" + L("history", "Verlauf & Mailverlauf") + "</h3>" +
      (timeline ? '<ul class="timeline">' + timeline + "</ul>" : "<p class=\"muted\">—</p>") +
      "<h3>" + L("actions", "Aktionen") + "</h3>" +
      '<form method="post" action="/jobs/' + j.id + '/status" class="filters" style="align-items:flex-end">' +
        '<div class="field"><label>' + L("statuschange", "Status") + '</label><select name="status">' + statusOptions + "</select></div>" +
        '<div class="field" style="flex:1;min-width:160px"><label>' + L("notec", "Notiz") + '</label><input name="note" placeholder="' + L("optional", "optional") + '"></div>' +
        '<button class="btn btn-primary" type="submit">' + L("save", "Speichern") + "</button></form>" +
      (j.manual ? '<form method="post" action="/jobs/' + j.id + '/unlock" class="inline-form" style="margin-top:8px">' +
        '<button class="btn btn-sm" type="submit">Automatische Status-Updates wieder aktivieren</button></form>' : "") +
      '<div style="margin-top:16px">' +
        '<div class="field" style="margin-bottom:10px;max-width:260px"><label>Sprache des Anschreibens</label>' +
          '<select id="cover-lang">' +
            '<option value="">Automatisch' + (j.language ? " (" + mbEsc(j.language) + ")" : "") + "</option>" +
            '<option value="de">Deutsch</option><option value="en">English</option>' +
          "</select></div>" +
        (j.cover_letter_name
          ? '<a class="btn btn-primary" style="font-weight:700;padding:10px 16px" href="/generated/' + mbEsc(j.cover_letter_name) + '" download>Anschreiben herunterladen (PDF)</a> ' +
            '<button class="btn" type="button" onclick="mbMakeCover(' + j.id + ')">Neu erzeugen</button>'
          : '<button class="btn btn-primary" type="button" onclick="mbMakeCover(' + j.id + ')">' + L("cover", "Anschreiben erzeugen") + "</button>") +
        (j.cover_letter_name
          ? '<div style="margin-top:14px">' +
            '<label class="small">Anschreiben verbessern – was soll geändert werden?</label>' +
            '<textarea id="cover-feedback" rows="2" placeholder="z. B. kürzer, konkreter auf die Rolle eingehen"></textarea>' +
            '<button class="btn" type="button" style="margin-top:6px" onclick="mbImproveCover(' + j.id + ')">Feedback einbauen</button></div>'
          : "") +
      "</div>";
    renderList();
  }

  function onFilterChange() { renderList(); saveFilters(); }
  ["f-q", "f-source", "f-remote", "f-loc", "f-fit", "f-from", "f-to", "f-sort"].forEach(function (id) {
    const el = document.getElementById(id);
    el.addEventListener("input", onFilterChange);
    el.addEventListener("change", onFilterChange);
  });
  statusBoxes.forEach(function (el) { el.addEventListener("change", onFilterChange); });

  window.mbResetFilters = function () {
    ["f-q", "f-source", "f-remote", "f-loc", "f-from", "f-to"].forEach(function (id) {
      document.getElementById(id).value = "";
    });
    statusBoxes.forEach(function (c) { c.checked = true; });
    document.getElementById("f-fit").value = window.MB_FIT_THRESHOLD || 0;
    document.getElementById("f-sort").value = "found";
    renderList();
    saveFilters();
  };

  const layout = document.querySelector(".jobs-layout");
  const splitter = document.getElementById("splitter");
  if (layout && splitter) {
    const saved = localStorage.getItem("mb-list-w");
    if (saved) layout.style.setProperty("--list-w", saved);
    let dragging = false;
    splitter.addEventListener("pointerdown", function (e) {
      dragging = true;
      splitter.classList.add("dragging");
      try { splitter.setPointerCapture(e.pointerId); } catch (err) {}
      e.preventDefault();
    });
    splitter.addEventListener("pointermove", function (e) {
      if (!dragging) return;
      const rect = layout.getBoundingClientRect();
      let px = e.clientX - rect.left;
      px = Math.max(280, Math.min(rect.width - 320, px));
      layout.style.setProperty("--list-w", px + "px");
    });
    const stopDrag = function () {
      if (!dragging) return;
      dragging = false;
      splitter.classList.remove("dragging");
      try { localStorage.setItem("mb-list-w", layout.style.getPropertyValue("--list-w")); } catch (e) {}
    };
    splitter.addEventListener("pointerup", stopDrag);
    splitter.addEventListener("pointercancel", stopDrag);
  }

  renderList();
  const pre = window.MB_PRESELECT ? parseInt(window.MB_PRESELECT, 10) : null;
  if (pre && jobs.some(function (j) { return j.id === pre; })) {
    showDetail(pre);
    const el = document.querySelector('tr[data-id="' + pre + '"]');
    if (el) el.scrollIntoView({ block: "nearest" });
  }
  window.mbJobs = jobs;
  window.mbShowDetail = showDetail;
  window.mbRenderList = renderList;
  window.mbSaveFilters = saveFilters;
})();

/* ---------- Inline-Laufstatus (statt Log-Fokus) ---------- */
function mbRunBar(text, kind) {
  const bar = document.getElementById("runbar");
  if (!bar) return;
  if (!text) { bar.hidden = true; bar.textContent = ""; return; }
  bar.hidden = false;
  bar.className = "runbar " + (kind || "info");
  bar.textContent = text;
}

async function mbRun(url, body, opts) {
  opts = opts || {};
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams(body || {}),
    });
    const data = await res.json();
    if (!data.run_id) { mbRunBar(opts.error || "Start fehlgeschlagen.", "error"); return; }
    mbRunBar(opts.running || "Verarbeitung läuft ...", "info");
    const timer = setInterval(async () => {
      try {
        const run = await (await fetch("/api/runs/" + data.run_id)).json();
        if (run.status === "ok") {
          clearInterval(timer);
          mbRunBar(opts.done || "Fertig.", "success");
          if (opts.onDone) opts.onDone(run);
        } else if (run.status === "fehler") {
          clearInterval(timer);
          const msg = (run.result && (run.result.text || run.result.error)) || "unbekannter Fehler";
          mbRunBar((opts.error || "Fehler: ") + msg, "error");
        }
      } catch (e) { /* weiter pollen */ }
    }, 1500);
  } catch (e) {
    mbRunBar("Netzwerkfehler.", "error");
  }
}

function mbModelName() { return window.MB_MODEL || "LLM"; }

window.mbJobSearch = function () {
  const el = document.getElementById("search-extra");
  mbRun("/api/jobs/search", { extra: el ? el.value : "" }, {
    running: "Neue Jobs werden gesucht (LLM: " + mbModelName() + ") ...",
    done: "Suche abgeschlossen.", error: "Suche fehlgeschlagen: ",
    onDone: function () { location.reload(); },
  });
};

window.mbStatusUpdate = function () {
  mbRun("/api/applications/update", {}, {
    running: "Status wird aktualisiert – Mails werden geprüft (LLM: " + mbModelName() + ") ...",
    done: "Status aktualisiert.", error: "Aktualisierung fehlgeschlagen: ",
    onDone: function () { location.reload(); },
  });
};

window.mbMakeCover = function (id) {
  const j = (window.mbJobs || []).find(function (x) { return x.id === id; }) || {};
  const langEl = document.getElementById("cover-lang");
  const lang = langEl ? langEl.value : "";
  mbRun("/api/jobs/" + id + "/cover-letter", { lang: lang }, {
    running: "Anschreiben wird erzeugt (LLM: " + mbModelName() + ") ...",
    error: "Anschreiben fehlgeschlagen: ",
    onDone: function (run) {
      const name = (run.result && run.result.datei || "").split("/").pop();
      if (name) j.cover_letter_name = name;
      mbRunBar("Anschreiben für " + (j.company || "den Job") + " wurde erzeugt.", "success");
      if (window.mbShowDetail) window.mbShowDetail(id);
    },
  });
};

window.mbImproveCover = function (id) {
  const ta = document.getElementById("cover-feedback");
  const feedback = ta ? ta.value : "";
  if (!feedback.trim()) { mbRunBar("Bitte Feedback eingeben.", "error"); return; }
  const j = (window.mbJobs || []).find(function (x) { return x.id === id; }) || {};
  const langEl = document.getElementById("cover-lang");
  const lang = langEl ? langEl.value : "";
  mbRun("/api/jobs/" + id + "/cover-letter/improve", { feedback: feedback, lang: lang }, {
    running: "Anschreiben wird überarbeitet (LLM: " + mbModelName() + ") ...",
    error: "Überarbeitung fehlgeschlagen: ",
    onDone: function (run) {
      const name = (run.result && run.result.datei || "").split("/").pop();
      if (name) j.cover_letter_name = name;
      mbRunBar("Anschreiben für " + (j.company || "den Job") + " wurde überarbeitet.", "success");
      if (window.mbShowDetail) window.mbShowDetail(id);
    },
  });
};

window.mbQuickCity = function () {
  const el = document.getElementById("f-loc");
  if (el) { el.value = window.MB_HOME_CITY || "Berlin"; if (window.mbRenderList) window.mbRenderList(); if (window.mbSaveFilters) window.mbSaveFilters(); }
};

function updateUseLabels() {
  document.querySelectorAll(".use-toggle").forEach(function (lab) {
    const inp = lab.querySelector("input");
    if (!inp) return;
    lab.classList.toggle("on", inp.checked);
    lab.classList.toggle("off", !inp.checked);
    const s = lab.querySelector(".use-label");
    if (!s) return;
    if (inp.type === "radio") s.textContent = inp.checked ? "aktiv (Anschreiben)" : "nicht aktiv";
    else s.textContent = inp.checked ? "verwendet" : "nicht verwendet";
  });
}

window.mbUseDoc = function (id, checked, el) {
  fetch("/api/documents/" + id + "/use", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ use: checked ? 1 : 0 }),
  }).then(function (r) { return r.json(); }).then(function () {
    updateUseLabels();
    mbRunBar(checked ? "Gespeichert." : "Gespeichert.", "success");
    setTimeout(function () { mbRunBar(""); }, 1500);
  }).catch(function () {
    mbRunBar("Speichern fehlgeschlagen.", "error");
    if (el) el.checked = !checked;
    updateUseLabels();
  });
};

window.mbDocEval = function (id) {
  mbRun("/api/documents/" + id + "/evaluate", {}, {
    running: "Dokument wird bewertet (LLM: " + mbModelName() + ") ...",
    done: "Bewertung fertig.", error: "Bewertung fehlgeschlagen: ",
    onDone: function () { location.reload(); },
  });
};

window.mbDocImprove = function (id) {
  const hint = window.prompt("Was soll verbessert oder ergänzt werden? (optional)\nz. B. \"mehr Kenntnisse mit opencode und Claude Code ergänzen\"", "");
  if (hint === null) return;
  mbRun("/api/documents/" + id + "/improve", { instruction: hint }, {
    running: "Verbesserte Kopie wird erzeugt (LLM: " + mbModelName() + ") ...",
    done: "Verbesserte Kopie erstellt.", error: "Erstellung fehlgeschlagen: ",
    onDone: function () { location.reload(); },
  });
};

/* ---------- Statistiken ---------- */
function mbCssVar(name, fallback) {
  try {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  } catch (e) { return fallback; }
}

function mbHexLerp(a, b, t) {
  function p(h) { h = h.replace("#", ""); if (h.length === 3) h = h.split("").map(function (c) { return c + c; }).join(""); return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]; }
  const A = p(a), B = p(b);
  const c = A.map(function (v, i) { return Math.round(v + (B[i] - v) * t); });
  return "rgb(" + c.join(",") + ")";
}

function mbNiceCeil(v) {
  v = Math.max(1, v || 1);
  if (v <= 5) return Math.ceil(v);
  const pow = Math.pow(10, Math.floor(Math.log10(v)));
  const cands = [1, 2, 2.5, 5, 10];
  for (let i = 0; i < cands.length; i++) { const m = cands[i] * pow; if (m >= v) return m; }
  return 10 * pow;
}

/* Liniendiagramm: x = Datum, y = Treffer (und optional Antworten). Reines SVG. */
function mbLineChart(container, points, opts) {
  if (!container) return;
  opts = opts || {};
  const labels = opts.labels || {};
  const shortDate = function (d) { return d ? d.slice(8, 10) + "." + d.slice(5, 7) + "." : ""; };
  const fullDate = function (d) { return d ? d.slice(8, 10) + "." + d.slice(5, 7) + "." + d.slice(0, 4) : ""; };
  function render() {
    const n = points.length;
    if (!n) { container.innerHTML = '<p class="muted">Keine Daten.</p>'; return; }
    const w = Math.max(320, container.clientWidth || 680);
    const h = opts.height || 260;
    const pad = { l: 40, r: 16, t: 18, b: 30 };
    const iw = w - pad.l - pad.r, ih = h - pad.t - pad.b;
    let maxv = 1;
    points.forEach(function (p) { maxv = Math.max(maxv, p.found || 0, opts.second ? (p.responses || 0) : 0); });
    const yMax = mbNiceCeil(maxv);
    const X = function (i) { return n === 1 ? pad.l + iw / 2 : pad.l + i * iw / (n - 1); };
    const Y = function (v) { return pad.t + ih - (v / yMax) * ih; };
    const uid = "ln" + Math.random().toString(36).slice(2, 8);
    const colA = opts.color || "#4f46e5";
    const colB = opts.secondColor || "#14b8a6";
    let s = '<svg class="chart-svg" viewBox="0 0 ' + w + " " + h + '" width="' + w + '" height="' + h + '">';
    s += '<defs><linearGradient id="' + uid + '" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0%" stop-color="' + colA + '" stop-opacity="0.30"/>' +
      '<stop offset="100%" stop-color="' + colA + '" stop-opacity="0"/></linearGradient></defs>';
    const steps = 4;
    for (let i = 0; i <= steps; i++) {
      const v = Math.round(yMax * i / steps); const yy = Y(v);
      s += '<line class="grid" x1="' + pad.l + '" y1="' + yy + '" x2="' + (w - pad.r) + '" y2="' + yy + '"/>';
      s += '<text class="axis y" x="' + (pad.l - 8) + '" y="' + (yy + 4) + '">' + v + "</text>";
    }
    const seen = {};
    const ticks = Math.min(n, 7);
    for (let k = 0; k < ticks; k++) {
      const i = Math.round(k * (n - 1) / (ticks - 1 || 1));
      if (seen[i]) continue; seen[i] = 1;
      s += '<text class="axis x" x="' + X(i) + '" y="' + (h - 9) + '">' + shortDate(points[i].d) + "</text>";
    }
    const path = function (key) {
      let d = "";
      points.forEach(function (p, i) { d += (i ? "L" : "M") + X(i) + " " + Y(p[key] || 0) + " "; });
      return d;
    };
    s += '<path class="area" d="' + path("found") + "L" + X(n - 1) + " " + (pad.t + ih) + " L" + X(0) + " " + (pad.t + ih) + ' Z" fill="url(#' + uid + ')"/>';
    if (opts.second) s += '<path class="line-b" d="' + path("responses") + '" style="stroke:' + colB + '"/>';
    s += '<path class="line-a" d="' + path("found") + '" style="stroke:' + colA + '"/>';
    if (n <= 48) {
      points.forEach(function (p, i) {
        if ((p.found || 0) > 0) s += '<circle class="dot-a" cx="' + X(i) + '" cy="' + Y(p.found) + '" r="2.8" style="fill:' + colA + '"/>';
        if (opts.second && (p.responses || 0) > 0) s += '<circle class="dot-b" cx="' + X(i) + '" cy="' + Y(p.responses) + '" r="2.5" style="fill:' + colB + '"/>';
      });
    }
    s += '<line class="hover-guide" x1="0" y1="' + pad.t + '" x2="0" y2="' + (pad.t + ih) + '" style="opacity:0"/>';
    s += '<circle class="hover-a" r="4.5" style="opacity:0"/>';
    if (opts.second) s += '<circle class="hover-b" r="4" style="opacity:0"/>';
    s += '<rect class="hover-capture" x="' + pad.l + '" y="' + pad.t + '" width="' + iw + '" height="' + ih + '" fill="transparent"/>';
    s += "</svg>";
    s += '<div class="chart-tip"></div>';
    container.innerHTML = s;
    const svg = container.querySelector("svg");
    const guide = svg.querySelector(".hover-guide");
    const ha = svg.querySelector(".hover-a");
    const hb = svg.querySelector(".hover-b");
    const tip = container.querySelector(".chart-tip");
    const capture = svg.querySelector(".hover-capture");
    capture.addEventListener("mousemove", function (ev) {
      const r = svg.getBoundingClientRect();
      const scale = r.width / w;
      const mx = (ev.clientX - r.left) / scale;
      let i = Math.round((mx - pad.l) / (iw / (n - 1 || 1)));
      i = Math.max(0, Math.min(n - 1, i));
      const p = points[i]; const xx = X(i);
      guide.setAttribute("x1", xx); guide.setAttribute("x2", xx); guide.style.opacity = 1;
      ha.setAttribute("cx", xx); ha.setAttribute("cy", Y(p.found || 0)); ha.style.opacity = 1;
      if (hb) { hb.setAttribute("cx", xx); hb.setAttribute("cy", Y(p.responses || 0)); hb.style.opacity = 1; }
      let html = "<b>" + fullDate(p.d) + "</b>";
      html += '<span class="tip-row"><i style="background:' + colA + '"></i>' + (labels.found || "Gefunden") + "<b>" + (p.found || 0) + "</b></span>";
      if (opts.second) html += '<span class="tip-row"><i style="background:' + colB + '"></i>' + (labels.responses || "Antworten") + "<b>" + (p.responses || 0) + "</b></span>";
      tip.innerHTML = html;
      tip.style.opacity = 1;
      let left = xx * scale + 12;
      if (left > r.width - 150) left = xx * scale - 150;
      tip.style.left = Math.max(4, left) + "px";
    });
    capture.addEventListener("mouseleave", function () {
      guide.style.opacity = 0; ha.style.opacity = 0; if (hb) hb.style.opacity = 0; tip.style.opacity = 0;
    });
  }
  render();
  if (window._mbLineResize) window.removeEventListener("resize", window._mbLineResize);
  let to;
  window._mbLineResize = function () { clearTimeout(to); to = setTimeout(render, 150); };
  window.addEventListener("resize", window._mbLineResize);
}

function mbDonut(container, items, center) {
  if (!container) return;
  const total = items.reduce(function (a, b) { return a + b.n; }, 0);
  if (!total) { container.innerHTML = '<p class="muted">—</p>'; return; }
  let acc = 0; const stops = [];
  items.forEach(function (it) {
    const start = acc / total * 100; acc += it.n;
    stops.push((it.color || "#94a3b8") + " " + start + "% " + (acc / total * 100) + "%");
  });
  container.innerHTML = '<div class="donut-wrap"><div class="donut" style="background:conic-gradient(' +
    stops.join(",") + ')"><div class="donut-center"><b>' + total + "</b><span>" + mbEsc(center || "") + "</span></div></div>" +
    '<ul class="legend">' + items.map(function (it) {
      const pct = Math.round(it.n / total * 100);
      return '<li><span class="dot" style="background:' + (it.color || "#94a3b8") + '"></span>' +
        mbEsc(it.label) + '<span class="legend-pct">' + pct + "%</span><b>" + it.n + "</b></li>";
    }).join("") + "</ul></div>";
}

function mbBars(container, items, opts) {
  if (!container) return;
  opts = opts || {};
  const color = opts.color || "var(--accent)";
  const max = Math.max.apply(null, [1].concat(items.map(function (i) { return i.n; })));
  container.innerHTML = items.map(function (it, i) {
    const c = opts.colorFn ? opts.colorFn(it, i, items.length) : color;
    return '<div class="bar-row"><span class="bar-label">' + mbEsc(it.label) + "</span>" +
      '<span class="bar"><span class="bar-fill" style="width:' + (it.n / max * 100) + "%;background:" + c + '"></span></span>' +
      '<span class="bar-num">' + it.n + "</span></div>";
  }).join("") || '<p class="muted">—</p>';
}

function mbFunnel(container, items) {
  if (!container) return;
  const top = Math.max(1, items.length ? items[0].n : 1);
  container.innerHTML = '<div class="funnel">' + items.map(function (it) {
    const pct = it.n / top * 100;
    const width = it.n ? Math.max(9, pct) : 0;
    return '<div class="funnel-row"><div class="funnel-bar" style="width:' + width + "%;background:" + it.color + '">' +
      "<span>" + mbEsc(it.label) + "</span><b>" + it.n + "</b></div>" +
      '<span class="funnel-pct">' + Math.round(pct) + "%</span></div>";
  }).join("") + "</div>";
}

(function initStats() {
  const s = window.MB_STATS;
  if (!s || !document.getElementById("stat-cards")) return;
  const LBL = window.MB_STATS_LABELS || {};
  const accent = mbCssVar("--accent", "#4f46e5");
  const muted = mbCssVar("--muted", "#94a3b8");
  const teal = "#14b8a6";

  const cards = [
    { v: s.total, l: LBL.total || "Jobs gesamt", c: muted, sub: "" },
    { v: s.applied, l: LBL.applied || "Beworben (bestätigt)", c: "#6366f1", sub: s.total ? Math.round(s.applied / s.total * 100) + "% " + (LBL.from || "von") + " " + s.total : "" },
    { v: s.interviews, l: LBL.interviews || "Interviews", c: teal, sub: (LBL.response_rate || "Antwortquote") + " " + (s.response_rate || 0) + "%" },
    { v: s.rejections, l: LBL.rejections || "Absagen", c: "#ef4444", sub: s.applied ? Math.round(s.rejections / s.applied * 100) + "% " + (LBL.per_application || "") : "" },
  ];
  document.getElementById("stat-cards").innerHTML = cards.map(function (c) {
    return '<div class="card stat" style="--sc:' + c.c + '"><div class="num">' + c.v +
      '</div><div class="lbl">' + c.l + '</div>' + (c.sub ? '<div class="sub muted">' + c.sub + "</div>" : "") + "</div>";
  }).join("");

  // Tages-Liniendiagramm (nur Tage mit Suchlauf)
  const daily = s.daily || [];
  mbLineChart(document.getElementById("chart-daily"), daily, { color: accent, labels: LBL, height: 260 });
  const sub = document.getElementById("daily-sub");
  if (sub && daily.length) {
    const sum = daily.reduce(function (a, p) { return a + (p.found || 0); }, 0);
    const mx = Math.max.apply(null, daily.map(function (p) { return p.found || 0; }));
    sub.textContent = daily.length + " Suchtage · " + sum + " " + (LBL.found || "Treffer") +
      " · Ø " + (sum / daily.length).toFixed(1) + " · max " + mx;
  }

  const sc = s.status_counts, sl = s.status_labels, scol = s.status_colors;
  const statusItems = Object.keys(sc).filter(function (k) { return sc[k] > 0; }).map(function (k) {
    return { label: sl[k] || k, n: sc[k], color: scol[k] || "#94a3b8" };
  });
  mbDonut(document.getElementById("chart-status"), statusItems, LBL.total || "Jobs");

  const fmap = { found: LBL.found || "Gefunden", applied: LBL.applied || "Beworben", response: LBL.responses || "Antwort", interview: LBL.interviews || "Interview", offer: LBL.offers || "Angebot" };
  const fcol = { found: muted, applied: "#6366f1", response: accent, interview: teal, offer: "#eab308" };
  mbFunnel(document.getElementById("chart-funnel"), (s.funnel || []).map(function (f) {
    return { label: fmap[f.key] || f.key, n: f.n, color: fcol[f.key] || accent };
  }));

  const pcol = { "Interview-Prozess": teal, "Absage": "#ef4444", "Eingangsbestaetigung": "#6366f1", "Warte auf Rueckmeldung": "#eab308", "Ohne Rueckmeldung": muted };
  mbDonut(document.getElementById("chart-phases"), (s.phases || []).map(function (p) {
    return { label: p.label, n: p.n, color: pcol[p.label] || muted };
  }), LBL.responses || "Antworten");

  const fitItems = s.fit || [];
  mbBars(document.getElementById("chart-fit"), fitItems, {
    colorFn: function (it, i, len) { return mbHexLerp(mbCssVar("--faint", "#a1a1aa"), accent, len <= 1 ? 0 : i / (len - 1)); },
  });
  const fm = document.getElementById("fit-meta");
  if (fm) fm.textContent = (LBL.fit_avg || "Ø Fit") + " " + s.fit_avg + " · " + (LBL.fit_median || "Median") + " " + s.fit_median + " · " + s.fit_n + " " + (LBL.fit_scored || "bewertet");
})();
