# One file, two services: SERVICE=shop or SERVICE=payments
import json, logging, os, random, sys, time, urllib.error, urllib.request, uuid
from datetime import datetime, timezone
import flask.cli
from flask import Flask, g, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

SERVICE = os.environ.get("SERVICE", "shop")
VERSION = os.environ.get("APP_VERSION", "1.0.0")
PAYMENTS_URL = os.environ.get("PAYMENTS_URL", "http://payments:8000")

app = Flask(__name__)

REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "route", "status"])
LATENCY = Histogram("http_request_duration_seconds", "Request latency", ["method", "route"],
                    buckets=(0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 1, 2.5, 5))


class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                "level": record.levelname, "service": SERVICE, "version": VERSION,
                "msg": record.getMessage()}
        data.update(getattr(record, "fields", {}))
        return json.dumps(data)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
log = logging.getLogger(SERVICE)
log.addHandler(handler)
log.setLevel(logging.INFO)
logging.getLogger("werkzeug").disabled = True
flask.cli.show_server_banner = lambda *args: None


@app.before_request
def start():
    g.start = time.perf_counter()
    g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
    g.extra = {}


@app.after_request
def observe(response):
    route = request.url_rule.rule if request.url_rule else "unmatched"
    if route == "/metrics":
        return response
    elapsed = time.perf_counter() - g.start
    REQUESTS.labels(request.method, route, str(response.status_code)).inc()
    LATENCY.labels(request.method, route).observe(elapsed)
    response.headers["X-Request-ID"] = g.request_id
    level = logging.ERROR if response.status_code >= 500 else logging.INFO
    log.log(level, "request", extra={"fields": {
        "request_id": g.request_id, "method": request.method, "path": request.path,
        "status": response.status_code, "duration_ms": round(elapsed * 1000, 1), **g.extra}})
    return response


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": SERVICE, "version": VERSION}


@app.get("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


# ---------- shop ----------
@app.get("/api/search")
def search():
    q = request.args.get("q", "")
    g.extra["query"] = q
    time.sleep(random.uniform(0.02, 0.06))
    if len(q) > 20:
        time.sleep(random.uniform(0.9, 1.4))
    if random.random() < 0.005:
        return {"error": "try again"}, 500
    return {"q": q, "results": random.randint(0, 30)}


@app.post("/api/checkout")
def checkout():
    order = request.get_json(force=True)
    g.extra["card"] = order.get("card")
    req = urllib.request.Request(f"{PAYMENTS_URL}/api/pay", data=json.dumps(order).encode(),
                                 headers={"Content-Type": "application/json",
                                          "X-Request-ID": g.request_id})  # pass it on!
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            return {"order": "accepted", "payment": json.load(r)}
    except urllib.error.HTTPError as e:
        g.extra["upstream_status"] = e.code
        return {"order": "failed", "error": "payment failed"}, 502
    except OSError as e:
        g.extra["upstream_error"] = str(e)
        return {"order": "failed", "error": "payments unreachable"}, 502


# ---------- payments ----------
@app.post("/api/pay")
def pay():
    p = request.get_json(force=True)
    g.extra.update(card=p.get("card"), amount=p.get("amount"))
    if VERSION == "1.1.0":
        g.extra["card_number"] = p.get("card_number")
    time.sleep(random.uniform(0.03, 0.08))
    if VERSION == "1.1.0" and p.get("card") == "unionpay":
        log.error("currency KZT not supported by the new unionpay client",
                  extra={"fields": {"request_id": g.request_id}})
        return {"error": "internal error"}, 500
    return {"paid": p.get("amount"), "card": p.get("card")}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, threaded=True)
