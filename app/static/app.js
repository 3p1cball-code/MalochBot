function mbSetTheme(value) {
  try {
    localStorage.setItem("mb-theme", value);
    document.documentElement.setAttribute("data-theme", value);
  } catch (e) {}
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

  function activeJobs() {
    const q = (document.getElementById("f-q").value || "").toLowerCase();
    const checkedStatus = {};
    statusBoxes.forEach(function (c) { if (c.checked) checkedStatus[c.value] = 1; });
    const source = document.getElementById("f-source").value;
    const remote = document.getElementById("f-remote").value;
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
      const badge = '<span class="badge" style="background:' + (colors[j.status] || "#94a3b8") + '">' +
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
    const badge = '<span class="badge" style="background:' + (colors[j.status] || "#94a3b8") + '">' +
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
    if (j.phase) {
      const d = (j.response_at || "").slice(0, 10);
      addEntry(d, (j.response_at || "") + "T13:00:00", "phase",
        "Status: <strong>" + mbEsc(j.phase) + "</strong>" + (j.app_notes ? " – " + mbEsc(j.app_notes) : ""));
    }
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

  ["f-q", "f-source", "f-remote", "f-fit", "f-from", "f-to", "f-sort"].forEach(function (id) {
    const el = document.getElementById(id);
    el.addEventListener("input", renderList);
    el.addEventListener("change", renderList);
  });
  statusBoxes.forEach(function (el) { el.addEventListener("change", renderList); });

  window.mbResetFilters = function () {
    ["f-q", "f-source", "f-remote", "f-from", "f-to"].forEach(function (id) {
      document.getElementById(id).value = "";
    });
    statusBoxes.forEach(function (c) { c.checked = true; });
    document.getElementById("f-fit").value = window.MB_FIT_THRESHOLD || 0;
    document.getElementById("f-sort").value = "found";
    renderList();
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
function mbDonut(container, items) {
  if (!container) return;
  const total = items.reduce(function (a, b) { return a + b.n; }, 0) || 1;
  let acc = 0; const stops = [];
  items.forEach(function (it) {
    const start = acc / total * 100; acc += it.n; const end = acc / total * 100;
    stops.push((it.color || "#94a3b8") + " " + start + "% " + end + "%");
  });
  container.innerHTML = '<div class="donut-wrap"><div class="donut" style="background:conic-gradient(' +
    stops.join(",") + ')"></div>' +
    '<ul class="legend">' + items.map(function (it) {
      return '<li><span class="dot" style="background:' + (it.color || "#94a3b8") + '"></span>' +
        mbEsc(it.label) + " <b>" + it.n + "</b></li>";
    }).join("") + "</ul></div>";
}

function mbBars(container, items, color) {
  if (!container) return;
  const max = Math.max.apply(null, [1].concat(items.map(function (i) { return i.n; })));
  container.innerHTML = items.map(function (it) {
    return '<div class="bar-row"><span class="bar-label">' + mbEsc(it.label) + "</span>" +
      '<span class="bar"><span class="bar-fill" style="width:' + (it.n / max * 100) +
      "%;background:" + (color || "var(--accent)") + '"></span></span>' +
      '<span class="bar-num">' + it.n + "</span></div>";
  }).join("") || '<p class="muted">—</p>';
}

(function initStats() {
  const s = window.MB_STATS;
  if (!s || !document.getElementById("stat-cards")) return;
  const LBL = window.MB_STATS_LABELS || {};
  const cards = [
    [LBL.total || "Jobs gesamt", s.total, "#64748b"],
    [LBL.applied || "Beworben (bestätigt)", s.applied, "#6366f1"],
    [LBL.interviews || "Interviews", s.interviews, "#14b8a6"],
    [LBL.rejections || "Absagen", s.rejections, "#ef4444"]
  ];
  document.getElementById("stat-cards").innerHTML = cards.map(function (c) {
    return '<div class="card stat"><div class="num" style="color:' + c[2] + '">' + c[1] +
      '</div><div class="lbl">' + c[0] + "</div></div>";
  }).join("");
  const sc = s.status_counts, sl = s.status_labels, scol = s.status_colors;
  const statusItems = Object.keys(sc).filter(function (k) { return sc[k] > 0; }).map(function (k) {
    return { label: sl[k] || k, n: sc[k], color: scol[k] || "#94a3b8" };
  });
  mbDonut(document.getElementById("chart-status"), statusItems);
  const pcol = { "Interview-Prozess": "#14b8a6", "Absage": "#ef4444", "Eingangsbestaetigung": "#6366f1", "Warte auf Rueckmeldung": "#eab308", "Ohne Rueckmeldung": "#94a3b8" };
  mbDonut(document.getElementById("chart-phases"), (s.phases || []).map(function (p) {
    return { label: p.label, n: p.n, color: pcol[p.label] || "#94a3b8" };
  }));
  mbBars(document.getElementById("chart-months"), s.months || [], "var(--accent)");
  mbBars(document.getElementById("chart-fit"), s.fit || [], "var(--accent)");
  mbBars(document.getElementById("chart-sources"), s.sources || [], "var(--accent)");
})();
