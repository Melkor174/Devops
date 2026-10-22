"""Учебное приложение «Notes». Код менять не нужно: ваша работа — всё вокруг него.

Зависимости: PostgreSQL (хранит заметки) и Redis (счётчик посещений).
Настройка только через переменные окружения (см. README).
"""
import logging
import os
import time
from contextlib import closing
from functools import wraps

import psycopg2
import redis
from flask import Flask, Response, jsonify, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("notes")

app = Flask(__name__)

DB = dict(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5432")),
    dbname=os.getenv("DB_NAME", "notes"),
    user=os.getenv("DB_USER", "notes"),
    password=os.getenv("DB_PASSWORD", "notes"),
    connect_timeout=3,
)
R = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    socket_timeout=2,
)
CHAOS = os.getenv("CHAOS_ENABLED", "false").lower() == "true"

REQS = Counter("notes_http_requests_total", "HTTP requests", ["method", "path", "status"])
LAT = Histogram("notes_http_request_seconds", "Request latency", ["path"])
_leak = []


def query(sql, args=None):
    with closing(psycopg2.connect(**DB)) as conn:
        with conn, conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchall() if cur.description else None


def init_db():
    for i in range(30):
        try:
            query(
                "CREATE TABLE IF NOT EXISTS notes ("
                "id SERIAL PRIMARY KEY, text TEXT NOT NULL, "
                "created_at TIMESTAMPTZ DEFAULT now())"
            )
            log.info("database ready")
            return
        except Exception as e:  # noqa: BLE001
            log.warning("database not ready (%d/30): %s", i + 1, e)
            time.sleep(2)
    log.error("database unavailable, starting anyway")


init_db()


@app.before_request
def _start():
    request._t = time.time()


@app.after_request
def _end(resp):
    dt = time.time() - request._t
    LAT.labels(request.path).observe(dt)
    REQS.labels(request.method, request.path, resp.status_code).inc()
    if request.path != "/metrics":
        log.info("%s %s %s %.0fms", request.method, request.path, resp.status_code, dt * 1000)
    return resp


@app.get("/")
def index():
    hits = R.incr("hits")
    return f"<h1>Notes</h1><p>Visits: {hits}</p><p>API: /api/notes, /health, /metrics</p>"


@app.get("/api/notes")
def list_notes():
    rows = query("SELECT id, text, created_at FROM notes ORDER BY id DESC LIMIT 50")
    return jsonify([{"id": r[0], "text": r[1], "created_at": r[2].isoformat()} for r in rows])


@app.post("/api/notes")
def add_note():
    text = ((request.get_json(silent=True) or {}).get("text") or "").strip()
    if not text:
        return jsonify(error="text is required"), 400
    rows = query("INSERT INTO notes(text) VALUES (%s) RETURNING id", (text,))
    return jsonify(id=rows[0][0]), 201


@app.get("/health")
def health():
    status, code = {}, 200
    try:
        query("SELECT 1")
        status["db"] = "ok"
    except Exception as e:  # noqa: BLE001
        status["db"], code = f"error: {e}", 503
    try:
        R.ping()
        status["redis"] = "ok"
    except Exception as e:  # noqa: BLE001
        status["redis"], code = f"error: {e}", 503
    return jsonify(status), code


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


# ---------- «Ломалки» (работают только при CHAOS_ENABLED=true) ----------

def chaos_only(f):
    @wraps(f)
    def wrapper(*a, **k):
        if not CHAOS:
            return jsonify(error="chaos disabled"), 404
        return f(*a, **k)
    return wrapper


@app.get("/chaos/slow")
@chaos_only
def chaos_slow():
    time.sleep(float(request.args.get("sec", 5)))
    return jsonify(ok=True)


@app.get("/chaos/error")
@chaos_only
def chaos_error():
    log.error("simulated failure")
    return jsonify(error="boom"), 500


@app.get("/chaos/leak")
@chaos_only
def chaos_leak():
    mb = int(request.args.get("mb", 50))
    _leak.append(b"x" * mb * 1024 * 1024)
    return jsonify(leaked_mb=sum(len(x) for x in _leak) // 1024 // 1024)


@app.get("/chaos/reset")
@chaos_only
def chaos_reset():
    _leak.clear()
    return jsonify(ok=True)


@app.get("/chaos/cpu")
@chaos_only
def chaos_cpu():
    end = time.time() + float(request.args.get("sec", 10))
    while time.time() < end:
        sum(i * i for i in range(10000))
    return jsonify(ok=True)
