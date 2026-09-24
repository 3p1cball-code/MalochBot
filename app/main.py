import asyncio
import hashlib
import json
import os
import queue
import shutil
import signal
import threading
import time

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import (
    HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse, FileResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import config, db, logbus, providers, secrets, i18n
from .engines import search as search_engine
from .engines import tracking as tracking_engine
from .engines import documents as documents_engine
from . import import_legacy
from . import opencode_adapter

config.ensure_dirs()
db.init_db()

app = FastAPI(title=config.APP_NAME, version=config.VERSION)
app.mount("/static", StaticFiles(directory=str(config.BASE_DIR / "app" / "static")), name="static")
templates = Jinja2Templates(directory=str(config.BASE_DIR / "app" / "templates"))
templates.env.globals["t"] = lambda key: i18n.tr(db.get_setting("language", "de"), key)


def _build_id() -> str:
    digest = hashlib.sha256()
    for path in sorted((config.BASE_DIR / "app").rglob("*")):
        if path.is_file() and path.suffix in (".py", ".html", ".css", ".js"):
            digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


BUILD_ID = _build_id()
STARTED_AT = time.time()


def tr(name: str, context: dict):
    request = context.pop("request")
    return templates.TemplateResponse(request, name, context)


def _shutdown():
    time.sleep(0.6)
    os.kill(os.getpid(), signal.SIGTERM)


def _ctx(request: Request, **kwargs):
    lang = db.get_setting("language", "de")
    base = {
        "request": request,
        "app_name": config.APP_NAME,
        "version": config.VERSION,
        "donate_email": config.DONATE_EMAIL,
        "donate_paypal": config.DONATE_PAYPAL,
        "statuses": config.JOB_STATUSES,
        "status_labels": config.status_labels(lang),
        "status_colors": config.STATUS_COLORS,
        "doc_labels": config.doc_labels(lang),
        "lang": lang,
        "languages": i18n.LANGUAGES,
        "model": db.get_setting("model", config.DEFAULT_MODEL),
        "setup_done": db.get_setting("setup_done", "0") == "1",
    }
    base.update(kwargs)
    return base


def start_background(kind: str, func) -> int:
    model = db.get_setting("model", config.DEFAULT_MODEL)
    run_id = logbus.start(kind, model)

    def worker():
        try:
            result = func(run_id, model)
            logbus.finish(run_id, "ok", json.dumps(result, ensure_ascii=False))
        except Exception as exc:
            logbus.log(run_id, "error", "Fehler: %s" % exc)
            logbus.finish(run_id, "fehler", str(exc))

    threading.Thread(target=worker, daemon=True).start()
    return run_id


# ---------------------------------------------------------------- Jobs (Startseite)
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    rows = db.query(
        "SELECT j.*, a.phase AS phase, a.response_at AS response_at, "
        "a.notes AS app_notes, a.channel AS channel "
        "FROM jobs j LEFT JOIN applications a ON a.job_id = j.id "
        "ORDER BY j.found_at DESC, j.id DESC")
    emails = db.query(
        "SELECT job_id, date, from_addr, subject FROM emails WHERE job_id IS NOT NULL "
        "ORDER BY date DESC")
    by_job = {}
    for mail in emails:
        by_job.setdefault(mail["job_id"], []).append(mail)
    events = db.query("SELECT job_id, ts, kind, text FROM events ORDER BY ts")
    events_by_job = {}
    for ev in events:
        events_by_job.setdefault(ev["job_id"], []).append(
            {"date": (ev["ts"] or "")[:10], "ts": ev["ts"] or "",
             "kind": ev["kind"], "text": ev["text"]})
    for row in rows:
        row["emails"] = by_job.get(row["id"], [])
        row["events"] = events_by_job.get(row["id"], [])
        if row.get("cover_letter"):
            row["cover_letter_name"] = os.path.basename(row["cover_letter"])
    sources = sorted({r["source"] for r in rows if r["source"]})
    return tr("jobs.html", _ctx(
        request, jobs_json=json.dumps(rows, ensure_ascii=False),
        sources=sources, opencode_ok=opencode_adapter.available(),
        counts=_counts(),
        fit_threshold=int(db.get_setting("fit_threshold", "0") or 0)))


def _counts():
    rows = db.query("SELECT status, COUNT(*) AS n FROM jobs GROUP BY status")
    counts = {s: 0 for s in config.JOB_STATUSES}
    for row in rows:
        counts[row["status"]] = row["n"]
    counts["gesamt"] = sum(counts.values())
    return counts


@app.get("/jobs")
def jobs_redirect():
    return RedirectResponse("/", status_code=303)


@app.post("/jobs/{job_id}/status")
def job_set_status(job_id: int, status: str = Form(...), note: str = Form("")):
    if status in config.JOB_STATUSES:
        db.execute("UPDATE jobs SET status=? WHERE id=?", (status, job_id))
        label = config.STATUS_LABELS.get(status, status)
        text = "Status: " + label + ((" – " + note.strip()) if note.strip() else "")
        db.execute("INSERT INTO events(job_id, ts, kind, text) VALUES(?,?,?,?)",
                   (job_id, db.now_iso(), "status", text))
        if status == "beworben" and not db.one("SELECT id FROM applications WHERE job_id=?", (job_id,)):
            db.execute("INSERT INTO applications(job_id, phase, notes, channel, updated_at) "
                       "VALUES(?,?,?,?,?)", (job_id, "Ohne Rueckmeldung", note, "manuell", db.now_iso()))
    return RedirectResponse("/?job=%d" % job_id, status_code=303)


@app.post("/jobs/{job_id}/cover-letter")
def job_cover_letter(job_id: int):
    run_id = start_background("anschreiben", lambda rid, model: {
        "datei": documents_engine.generate_cover_letter(job_id, rid, model)})
    return RedirectResponse("/log/%d" % run_id, status_code=303)


@app.post("/jobs/search")
def jobs_search(extra: str = Form("")):
    run_id = start_background("suche", lambda rid, model: search_engine.run_search(rid, model, extra))
    return RedirectResponse("/log/%d" % run_id, status_code=303)


@app.post("/jobs/add")
async def jobs_add(request: Request):
    form = await request.form()
    company = str(form.get("company", "")).strip()
    title = str(form.get("title", "")).strip()
    if not company or not title:
        return RedirectResponse("/", status_code=303)
    try:
        score = int(str(form.get("score", "") or "0").strip() or 0)
    except ValueError:
        score = 0
    status = str(form.get("status", "gefunden") or "gefunden")
    if status not in config.JOB_STATUSES:
        status = "gefunden"
    job = {
        "company": company, "title": title,
        "location": str(form.get("location", "")).strip(),
        "remote": bool(form.get("remote")),
        "url": str(form.get("url", "")).strip(),
        "company_url": str(form.get("company_url", "")).strip(),
        "score": score, "status": status,
        "rationale": str(form.get("rationale", "")).strip(),
        "description": str(form.get("description", "")).strip(),
        "source": "manuell",
    }
    jid, _ = db.upsert_job(job)
    return RedirectResponse("/?job=%d" % jid, status_code=303)


@app.post("/applications/update")
def applications_update():
    run_id = start_background("tracking", tracking_engine.run_tracking)
    return RedirectResponse("/log/%d" % run_id, status_code=303)


# ---------------------------------------------------------------- Statistiken
@app.get("/stats", response_class=HTMLResponse)
def stats(request: Request):
    status_counts = {s: 0 for s in config.JOB_STATUSES}
    for row in db.query("SELECT status, COUNT(*) n FROM jobs GROUP BY status"):
        status_counts[row["status"]] = row["n"]
    phase_rows = db.query("SELECT phase, COUNT(*) n FROM applications GROUP BY phase ORDER BY n DESC")
    months = db.query("SELECT substr(found_at,1,7) m, COUNT(*) n FROM jobs "
                      "WHERE found_at<>'' GROUP BY m ORDER BY m")
    fit = {"0-49": 0, "50-59": 0, "60-69": 0, "70-79": 0, "80-89": 0, "90-100": 0}
    for row in db.query("SELECT score FROM jobs"):
        s = row["score"] or 0
        key = ("0-49" if s < 50 else "50-59" if s < 60 else "60-69" if s < 70
               else "70-79" if s < 80 else "80-89" if s < 90 else "90-100")
        fit[key] += 1
    sources = db.query("SELECT source, COUNT(*) n FROM jobs GROUP BY source ORDER BY n DESC")
    lang = db.get_setting("language", "de")
    total = sum(status_counts.values())
    applied = sum(v for k, v in status_counts.items()
                  if k in ("beworben", "interview", "angebot", "abgelehnt"))
    data = {
        "total": total, "applied": applied,
        "with_response": db.one("SELECT COUNT(*) n FROM applications")["n"],
        "interviews": status_counts.get("interview", 0),
        "rejections": status_counts.get("abgelehnt", 0),
        "found": status_counts.get("gefunden", 0),
        "status_counts": status_counts,
        "status_labels": config.status_labels(lang),
        "status_colors": config.STATUS_COLORS,
        "phases": [{"label": r["phase"], "n": r["n"]} for r in phase_rows],
        "months": [{"label": r["m"], "n": r["n"]} for r in months],
        "fit": [{"label": k, "n": v} for k, v in fit.items()],
        "sources": [{"label": r["source"] or "?", "n": r["n"]} for r in sources],
    }
    return tr("stats.html", _ctx(request, stats_json=json.dumps(data, ensure_ascii=False)))


# ---------------------------------------------------------------- Unterlagen
@app.get("/documents", response_class=HTMLResponse)
def documents(request: Request):
    docs = db.query("SELECT * FROM documents ORDER BY kind, name")
    selected = _selected_doc_ids()
    return tr("documents.html", _ctx(
        request, docs=docs, kinds=config.DOC_KINDS,
        selected_docs=selected, active_photo=_active_photo_id(),
        backend=secrets.store.backend()))


def _is_image_name(name: str) -> bool:
    return (name or "").lower().endswith((".png", ".jpg", ".jpeg", ".webp"))


def _selected_doc_ids() -> set:
    raw = db.get_setting("search_doc_ids", "") or ""
    ids = {int(x) for x in raw.split(",") if x.strip().isdigit()}
    if ids:
        return ids
    return {d["id"] for d in db.query("SELECT id, name FROM documents") if not _is_image_name(d["name"])}


def _active_photo_id() -> int:
    value = db.get_setting("active_photo", "") or ""
    if value.isdigit():
        return int(value)
    for d in db.query("SELECT id, name FROM documents ORDER BY created_at DESC"):
        if _is_image_name(d["name"]):
            return d["id"]
    return 0


@app.post("/api/documents/{doc_id}/use")
def api_doc_use(doc_id: int, use: int = Form(1)):
    doc = db.one("SELECT id, name FROM documents WHERE id=?", (doc_id,))
    if doc and _is_image_name(doc["name"]):
        if use:
            db.set_setting("active_photo", str(doc_id))
        elif (db.get_setting("active_photo", "") or "") == str(doc_id):
            db.set_setting("active_photo", "")
        return JSONResponse({"active_photo": db.get_setting("active_photo", "")})
    ids = _selected_doc_ids()
    if use:
        ids.add(doc_id)
    else:
        ids.discard(doc_id)
    db.set_setting("search_doc_ids", ",".join(str(i) for i in sorted(ids)))
    return JSONResponse({"selected": sorted(ids)})


@app.post("/documents/upload")
async def documents_upload(kind: str = Form("sonstiges"), notes: str = Form(""),
                           file: UploadFile = File(...)):
    name = os.path.basename(file.filename or "datei")
    target = config.UPLOAD_DIR / name
    stem, ext = os.path.splitext(name)
    counter = 1
    while target.exists():
        target = config.UPLOAD_DIR / ("%s_%d%s" % (stem, counter, ext))
        counter += 1
    with open(target, "wb") as fh:
        shutil.copyfileobj(file.file, fh)
    db.execute("INSERT INTO documents(name, kind, path, size, created_at, notes) "
               "VALUES(?,?,?,?,?,?)",
               (name, kind, str(target), target.stat().st_size, db.now_iso(), notes))
    return RedirectResponse("/documents", status_code=303)


@app.post("/documents/{doc_id}/kind")
def documents_kind(doc_id: int, kind: str = Form(...)):
    db.execute("UPDATE documents SET kind=? WHERE id=?", (kind, doc_id))
    return RedirectResponse("/documents", status_code=303)


@app.post("/documents/{doc_id}/delete")
def documents_delete(doc_id: int):
    doc = db.one("SELECT * FROM documents WHERE id=?", (doc_id,))
    if doc:
        try:
            if doc["path"] and os.path.exists(doc["path"]):
                os.remove(doc["path"])
        except OSError:
            pass
        db.execute("DELETE FROM documents WHERE id=?", (doc_id,))
    return RedirectResponse("/documents", status_code=303)


@app.post("/documents/{doc_id}/evaluate")
def documents_evaluate(doc_id: int):
    run_id = start_background("bewertung", lambda rid, model: {
        "bewertung": documents_engine.evaluate_document(doc_id, rid, model)})
    return RedirectResponse("/log/%d" % run_id, status_code=303)


@app.post("/documents/{doc_id}/improve")
def documents_improve(doc_id: int):
    run_id = start_background("verbesserung", lambda rid, model: {
        "ergebnis": documents_engine.improve_document(doc_id, rid, model)})
    return RedirectResponse("/log/%d" % run_id, status_code=303)


@app.get("/documents/{doc_id}/download")
def documents_download(doc_id: int):
    doc = db.one("SELECT * FROM documents WHERE id=?", (doc_id,))
    if not doc:
        return HTMLResponse("Nicht gefunden", status_code=404)
    path = documents_engine.resolve_path(doc)
    if not os.path.exists(path):
        return HTMLResponse("Nicht gefunden", status_code=404)
    return FileResponse(path, filename=doc["name"])


IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")


@app.get("/documents/{doc_id}/raw")
def documents_raw(doc_id: int):
    doc = db.one("SELECT * FROM documents WHERE id=?", (doc_id,))
    if not doc:
        return HTMLResponse("Nicht gefunden", status_code=404)
    path = documents_engine.resolve_path(doc)
    if not os.path.exists(path):
        return HTMLResponse("Nicht gefunden", status_code=404)
    return FileResponse(path)


@app.get("/documents/{doc_id}/crop", response_class=HTMLResponse)
def documents_crop(request: Request, doc_id: int):
    doc = db.one("SELECT * FROM documents WHERE id=?", (doc_id,))
    if not doc or not doc["name"].lower().endswith(IMAGE_EXT):
        return HTMLResponse("Zuschneiden ist nur für Bilder möglich.", status_code=404)
    return tr("crop.html", _ctx(request, doc=doc, image_url="/documents/%d/raw" % doc_id))


@app.post("/documents/{doc_id}/crop")
def documents_crop_apply(doc_id: int, x: int = Form(...), y: int = Form(...),
                         w: int = Form(...), h: int = Form(...)):
    doc = db.one("SELECT * FROM documents WHERE id=?", (doc_id,))
    if not doc:
        return RedirectResponse("/documents", status_code=303)
    path = documents_engine.resolve_path(doc)
    stem, ext = os.path.splitext(doc["name"])
    if ext.lower() not in IMAGE_EXT or not os.path.exists(path):
        return RedirectResponse("/documents", status_code=303)
    try:
        from PIL import Image, ImageOps
        img = ImageOps.exif_transpose(Image.open(path))
        left, top = max(0, x), max(0, y)
        right = min(img.width, x + w)
        bottom = min(img.height, y + h)
        if right - left < 10 or bottom - top < 10:
            return RedirectResponse("/documents", status_code=303)
        img = img.crop((left, top, right, bottom))
        if ext.lower() == ".webp":
            ext = ".png"
        out = config.UPLOAD_DIR / ("%s_zuschnitt%s" % (stem, ext))
        if ext.lower() in (".jpg", ".jpeg") and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(str(out))
    except Exception as exc:
        logbus.log(None, "error", "Zuschneiden fehlgeschlagen: %s" % exc)
        return RedirectResponse("/documents", status_code=303)
    db.execute("INSERT INTO documents(name, kind, path, size, version, created_at, notes) "
               "VALUES(?,?,?,?,?,?,?)",
               (out.name, doc["kind"], str(out), out.stat().st_size,
                (doc["version"] or 1) + 1, db.now_iso(),
                "Zuschnitt von %s" % doc["name"]))
    return RedirectResponse("/documents", status_code=303)


# ---------------------------------------------------------------- Einstellungen
@app.get("/settings", response_class=HTMLResponse)
def settings(request: Request, saved: str = ""):
    values = db.all_settings()
    models = opencode_adapter.list_models()
    models_by_provider = {}
    for name in models:
        provider = name.split("/", 1)[0]
        models_by_provider.setdefault(provider, []).append(name)
    documents = db.query("SELECT id, name, kind FROM documents ORDER BY kind, name")
    return tr("settings.html", _ctx(
        request, values=values, mail_providers=providers.PROVIDERS,
        models=models, models_by_provider=models_by_provider,
        secret_backend=secrets.store.backend(),
        has_mail_password=bool(secrets.store.get("mail_password", "")),
        saved=saved))


@app.post("/settings")
async def settings_save(request: Request):
    form = await request.form()
    for key in ("model", "profile", "preferences", "search_extra", "fit_threshold",
                "mail_provider", "mail_email", "mail_host", "mail_port", "mail_folders",
                "mail_since"):
        if key in form:
            db.set_setting(key, str(form.get(key, "")))
    password = form.get("mail_password", "")
    if password:
        secrets.store.set("mail_password", password)
    if form.get("clear_password"):
        secrets.store.delete("mail_password")
    db.set_setting("setup_done", "1")
    return RedirectResponse("/settings?saved=1", status_code=303)


@app.post("/settings/test-mail")
def settings_test_mail():
    run_id = start_background("mailtest", _test_mail)
    return RedirectResponse("/log/%d" % run_id, status_code=303)


def _test_mail(run_id, model):
    client = tracking_engine._connect()
    try:
        folders = tracking_engine._list_folders(client)
        logbus.log(run_id, "info", "Verbindung erfolgreich. Ordner: %s" % ", ".join(folders[:12]))
    finally:
        try:
            client.logout()
        except Exception:
            pass
    return {"status": "ok", "ordner": len(folders)}


@app.post("/settings/import")
def settings_import():
    run_id = start_background("import", lambda rid, model: import_legacy.import_legacy(rid))
    return RedirectResponse("/log/%d" % run_id, status_code=303)


@app.post("/language")
def set_language(lang: str = Form(...), next: str = Form("/")):
    if lang in i18n.LANGUAGES:
        db.set_setting("language", lang)
    if not next.startswith("/"):
        next = "/"
    return RedirectResponse(next, status_code=303)


# ---------------------------------------------------------------- Log
@app.get("/log", response_class=HTMLResponse)
def log_index(request: Request):
    runs = db.query("SELECT * FROM runs ORDER BY id DESC LIMIT 50")
    return tr("log.html", _ctx(request, run=None, logs=[], runs=runs, running=False))


@app.get("/log/{run_id}", response_class=HTMLResponse)
def log_run(request: Request, run_id: int):
    run = db.one("SELECT * FROM runs WHERE id=?", (run_id,))
    logs = db.query("SELECT * FROM logs WHERE run_id=? ORDER BY id", (run_id,))
    runs = db.query("SELECT * FROM runs ORDER BY id DESC LIMIT 50")
    return tr("log.html", _ctx(
        request, run=run, logs=logs, runs=runs, running=logbus.is_running(run_id)))


@app.get("/api/events/{run_id}")
async def api_events(run_id: int):
    q = logbus.subscribe(run_id)

    async def generator():
        try:
            while True:
                try:
                    entry = q.get_nowait()
                    yield "data: %s\n\n" % json.dumps(entry)
                except queue.Empty:
                    if not logbus.is_running(run_id) and q.empty():
                        yield "event: done\ndata: {}\n\n"
                        break
                    await asyncio.sleep(0.4)
        finally:
            logbus.unsubscribe(run_id, q)

    return StreamingResponse(generator(), media_type="text/event-stream")


# ---------------------------------------------------------------- About / API
@app.get("/about", response_class=HTMLResponse)
def about(request: Request):
    return tr("about.html", _ctx(
        request, secret_backend=secrets.store.backend(),
        opencode_ok=opencode_adapter.available()))


@app.post("/api/jobs/{job_id}/cover-letter")
def api_cover_letter(job_id: int, lang: str = Form("")):
    rid = start_background("anschreiben", lambda r, m: {
        "datei": documents_engine.generate_cover_letter(job_id, r, m, lang)})
    return JSONResponse({"run_id": rid})


@app.post("/api/jobs/{job_id}/cover-letter/improve")
def api_cover_improve(job_id: int, feedback: str = Form(...), lang: str = Form("")):
    rid = start_background("anschreiben+", lambda r, m: {
        "datei": documents_engine.improve_cover_letter(job_id, feedback, r, m, lang)})
    return JSONResponse({"run_id": rid})


@app.post("/api/jobs/search")
def api_search(extra: str = Form("")):
    rid = start_background("suche", lambda r, m: search_engine.run_search(r, m, extra))
    return JSONResponse({"run_id": rid})


@app.post("/api/applications/update")
def api_applications_update():
    rid = start_background("tracking", tracking_engine.run_tracking)
    return JSONResponse({"run_id": rid})


@app.post("/api/documents/{doc_id}/evaluate")
def api_doc_evaluate(doc_id: int):
    rid = start_background("bewertung", lambda r, m: {
        "bewertung": documents_engine.evaluate_document(doc_id, r, m)})
    return JSONResponse({"run_id": rid})


@app.post("/api/documents/{doc_id}/improve")
def api_doc_improve(doc_id: int, instruction: str = Form("")):
    rid = start_background("verbesserung", lambda r, m: {
        "ergebnis": documents_engine.improve_document(doc_id, r, m, instruction)})
    return JSONResponse({"run_id": rid})


@app.get("/api/runs/{run_id}")
def api_run(run_id: int):
    run = db.one("SELECT * FROM runs WHERE id=?", (run_id,))
    if not run:
        return JSONResponse({"error": "not found"}, status_code=404)
    result = {}
    if run["summary"]:
        try:
            result = json.loads(run["summary"])
        except Exception:
            result = {"text": run["summary"]}
    return JSONResponse({"id": run_id, "kind": run["kind"], "status": run["status"],
                         "model": run["model"], "result": result})


@app.get("/generated/{name}")
def generated_file(name: str):
    path = config.GENERATED_DIR / os.path.basename(name)
    if not path.exists():
        return HTMLResponse("Nicht gefunden", status_code=404)
    return FileResponse(str(path), filename=path.name)


@app.post("/shutdown")
def shutdown():
    threading.Thread(target=_shutdown, daemon=True).start()
    return HTMLResponse(
        "<html><body style='font-family:sans-serif;padding:40px'>"
        "<h2>MalochBot wird beendet.</h2><p>Du kannst dieses Fenster schließen.</p>"
        "</body></html>")


@app.get("/api/health")
def health():
    return JSONResponse({
        "app": config.APP_NAME, "version": config.VERSION,
        "build": BUILD_ID,
        "db": str(config.DB_PATH), "opencode": opencode_adapter.available(),
        "model": db.get_setting("model", config.DEFAULT_MODEL),
        "secret_backend": secrets.store.backend(),
    })
