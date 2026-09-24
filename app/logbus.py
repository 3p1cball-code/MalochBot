"""Live-Logbus: verteilt Prozessmeldungen an die Oberflaeche und speichert sie.

Engines laufen in Threads, die Oberflaeche liest asynchron (SSE). Der Bus ist
thread-sicher und puffert Meldungen, damit ein spaeter verbundener Client alles sieht.
"""

import json
import queue
import threading
from collections import defaultdict

from . import config, db

_lock = threading.Lock()
_subscribers = defaultdict(list)
_buffers = defaultdict(list)
_running = {}
MAX_BUFFER = 500


def start(kind: str, model: str) -> int:
    run_id = db.start_run(kind, model)
    with _lock:
        _running[run_id] = True
        _buffers[run_id] = []
    log(run_id, "info", "Lauf gestartet (%s)" % kind)
    return run_id


def finish(run_id: int, status: str = "ok", summary: str = "") -> None:
    db.finish_run(run_id, status, summary)
    log(run_id, "info", "Lauf beendet (%s)." % status)
    with _lock:
        _running.pop(run_id, None)


def is_running(run_id: int) -> bool:
    with _lock:
        return run_id in _running


def any_running() -> bool:
    with _lock:
        return bool(_running)


def log(run_id, level: str, message: str) -> None:
    entry = {"run_id": run_id, "level": level, "message": message}
    db.add_log(run_id, level, message)
    with _lock:
        _buffers[run_id].append(entry)
        if len(_buffers[run_id]) > MAX_BUFFER:
            _buffers[run_id] = _buffers[run_id][-MAX_BUFFER:]
        subs = list(_subscribers[run_id])
    for q in subs:
        try:
            q.put_nowait(entry)
        except queue.Full:
            pass


def subscribe(run_id):
    q = queue.Queue(maxsize=1000)
    with _lock:
        _subscribers[run_id].append(q)
        backlog = list(_buffers.get(run_id, []))
    for entry in backlog:
        try:
            q.put_nowait(entry)
        except queue.Full:
            break
    return q


def unsubscribe(run_id, q) -> None:
    with _lock:
        if q in _subscribers[run_id]:
            _subscribers[run_id].remove(q)
