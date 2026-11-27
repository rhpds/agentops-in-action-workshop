"""Attach the gateway's verified actor into the agent's own MLflow trace.

The problem. A tool call produces two traces that cannot be joined in the
request path, and both breaks were measured rather than assumed:

  * the agent emits no W3C trace context, so hop 1 starts its own trace; and
  * the MCP broker forwards no unknown headers at all -- a marker injected on
    hop 1 arrives absent on hop 2 -- so neither traceparent nor a smuggled
    correlation id can cross it. The broker is a vendor image whose binary
    carries no otelhttp, so it has no HTTP instrumentation to propagate with.

Normally every hop extracts traceparent, emits its span under the same trace
id, and injects an updated traceparent downstream. One hop here refuses, so
the context is re-attached afterwards instead. That is possible because
MLflow's trace id IS the OTel trace id: a span POSTed to /v1/traces carrying
an existing trace's id is filed into that trace.

Why this holds spans in memory rather than reading them back out of MLflow.
An earlier version let the collector write gateway spans to MLflow and then
folded and deleted them. It worked, but every tool call briefly produced a
loose trace in the participant's experiment -- measured at ~6s visible, and
~12s before the provenance span appeared. Receiving the spans directly means
no loose trace is ever created and the arrival of the span is itself the
trigger, so there is no poll interval in the path.

Two things this gives up, both deliberate:
  * a span held here is in memory only. If the pod dies the record is lost
    from MLflow -- though never from the gateway access log, which is the
    durable copy and is why that log stays.
  * a span whose turn never materialises is emitted as its own trace after
    UNMATCHED_TIMEOUT rather than dropped, so it is visible rather than
    silently missing.
"""
import base64, gzip, json, os, ssl, threading, time, urllib.error, urllib.request
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.environ["MLFLOW_API_URL"].rstrip("/")
NS = os.environ["NAMESPACE"]
EXP = open("/shared/experiment-id").read().strip()
GW_SERVICE = os.environ["GATEWAY_SERVICE_NAME"]
PORT = int(os.environ.get("STITCH_RECEIVER_PORT", "4319"))
TICK = float(os.environ.get("STITCH_TICK_SECONDS", "1"))
UNMATCHED_TIMEOUT = float(os.environ.get("STITCH_UNMATCHED_TIMEOUT_SECONDS", "300"))
HOST_CACHE_SECONDS = float(os.environ.get("STITCH_HOST_CACHE_SECONDS", "3"))
CTX = ssl.create_default_context(cafile="/etc/mlflow-ca/service-ca.crt")
TOKEN_FILE = "/var/run/secrets/kubernetes.io/serviceaccount/token"

PENDING = deque()
LOCK = threading.Lock()


def log(msg):
    print("%s stitcher: %s" % (datetime.now(timezone.utc).isoformat(), msg), flush=True)


def headers(extra=None):
    # Re-read per call: the projection rotates, exactly as traces.py notes.
    h = {"Authorization": "Bearer " + open(TOKEN_FILE).read().strip(),
         "X-MLflow-Workspace": NS, "Content-Type": "application/json"}
    if extra:
        h.update(extra)
    return h


def api(method, path, body=None, extra=None):
    req = urllib.request.Request(
        BASE + path, method=method, headers=headers(extra),
        data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
        raw = r.read()
    return json.loads(raw) if raw else {}


def as_hex(v):
    """OTLP/JSON may encode ids as hex or base64 depending on the producer."""
    if not v:
        return None
    try:
        int(v, 16)
        return v
    except (ValueError, TypeError):
        try:
            return base64.b64decode(v).hex()
        except Exception:
            return None


def flatten_attrs(attrs):
    out = {}
    for a in attrs or []:
        val = a.get("value") or {}
        out[a.get("key")] = (val.get("stringValue") or val.get("intValue")
                             or val.get("boolValue") or "")
    return out


class Receiver(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        # The otlphttp exporter gzips by default, so this is the normal path
        # rather than an edge case -- without it every payload fails to
        # decode as UTF-8 and the spans are silently dropped.
        if (self.headers.get("Content-Encoding") or "").lower() == "gzip":
            try:
                raw = gzip.decompress(raw)
            except Exception as e:
                log("receiver: gunzip failed (%s)" % e)
                raw = b"{}"
        accepted = 0
        try:
            doc = json.loads(raw)
            for rs in doc.get("resourceSpans") or []:
                res = flatten_attrs((rs.get("resource") or {}).get("attributes"))
                for ss in rs.get("scopeSpans") or []:
                    for sp in ss.get("spans") or []:
                        attrs = flatten_attrs(sp.get("attributes"))
                        attrs.update({k: v for k, v in res.items()
                                      if k.startswith("waterplant.")})
                        if attrs.get("waterplant.mcp_method") != "tools/call":
                            continue
                        with LOCK:
                            PENDING.append({
                                "received": time.time(),
                                "trace_id": as_hex(sp.get("traceId")),
                                "start_ns": int(sp.get("startTimeUnixNano") or 0),
                                "end_ns": int(sp.get("endTimeUnixNano") or 0),
                                "attrs": attrs,
                            })
                        accepted += 1
        except Exception as e:
            log("receiver: bad payload (%s)" % e)
        # OTLP wants a JSON body; an empty 200 makes the collector retry.
        body = b"{}"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


_hosts = {"at": 0.0, "rows": []}


def hosts():
    """Recent non-gateway traces, briefly cached so a burst is one search."""
    now = time.time()
    if now - _hosts["at"] < HOST_CACHE_SECONDS:
        return _hosts["rows"]
    body = {"locations": [{"type": "MLFLOW_EXPERIMENT",
                           "mlflow_experiment": {"experiment_id": EXP}}],
            "max_results": 50, "order_by": ["timestamp_ms DESC"],
            "filter": "attributes.timestamp > %d" % int((now - 1800) * 1000)}
    rows = []
    for t in api("POST", "/mlflow/api/3.0/mlflow/traces/search", body).get("traces") or []:
        i = t.get("trace_info") or t
        tags = i.get("tags") or {}
        if tags.get("service.name", "").startswith("mcp-gateway"):
            continue
        try:
            start = datetime.fromisoformat(
                (i.get("request_time") or "").replace("Z", "+00:00")).timestamp()
            dur = float(str(i.get("execution_duration") or "0").rstrip("s"))
        except ValueError:
            continue
        rows.append({"id": i["trace_id"], "start": start, "end": start + dur,
                     "service": tags.get("service.name") or "hermes-agent"})
    _hosts.update(at=now, rows=rows)
    return rows


def parent_span(trace_id, tool):
    """The agent's own span for this tool call, else the trace root.

    get-trace-artifact is the endpoint the MLflow UI uses; the documented API
    returns trace_info with no spans at all, so there is no supported
    alternative. Best-effort: on failure the span still attaches, at the root.
    """
    try:
        d = api("GET", "/mlflow/ajax-api/2.0/mlflow/get-trace-artifact?request_id=" + trace_id)
    except Exception as e:
        log("span fetch failed for %s: %s" % (trace_id, e))
        return None
    spans = d.get("spans") or []
    for s in spans:  # hermes_otel names these tool.mcp_gateway_<prefix>_<tool>
        if tool and s.get("name", "").endswith(tool):
            return as_hex(s.get("span_id"))
    for s in spans:
        if not s.get("parent_span_id"):
            return as_hex(s.get("span_id"))
    return None


def emit(trace_hex, parent_hex, item, service):
    attrs = [{"key": k, "value": {"stringValue": str(v)}}
             for k, v in sorted(item["attrs"].items()) if k.startswith("waterplant.")]
    span = {"traceId": trace_hex,
            "spanId": os.urandom(8).hex(),
            "name": "gateway verified: %s" % (item["attrs"].get("waterplant.tool") or "tool"),
            "kind": 1,
            "startTimeUnixNano": str(item["start_ns"]),
            "endTimeUnixNano": str(item["end_ns"] or item["start_ns"] + 1_000_000),
            "attributes": attrs,
            "status": {"code": 1}}
    if parent_hex:
        span["parentSpanId"] = parent_hex
    # service.name must be the HOST trace's. MLflow derives a trace's tags
    # from the resource of the spans it ingests, so sending the gateway's
    # here relabels the agent's whole trace -- observed doing exactly that.
    payload = {"resourceSpans": [{
        "resource": {"attributes": [
            {"key": "service.name", "value": {"stringValue": service}}]},
        "scopeSpans": [{"scope": {"name": "waterplant-provenance"},
                        "spans": [span]}]}]}
    req = urllib.request.Request(
        BASE + "/v1/traces", data=json.dumps(payload).encode(), method="POST",
        headers=headers({"x-mlflow-experiment-id": EXP}))
    with urllib.request.urlopen(req, timeout=30, context=CTX):
        pass


def tag(trace_id, key, value):
    try:
        api("PATCH", "/mlflow/api/3.0/mlflow/traces/%s/tags" % trace_id,
            {"key": key, "value": str(value)[:7500]})
    except Exception as e:
        log("tag %s on %s failed: %s" % (key, trace_id, e))


def drain():
    with LOCK:
        if not PENDING:
            return
        batch = list(PENDING)
    rows = hosts()
    now = time.time()
    done, attached, orphaned = [], 0, 0
    for item in batch:
        start = item["start_ns"] / 1e9
        host = next((h for h in rows if h["start"] <= start <= h["end"] + 1.0), None)
        if host is None:
            if now - item["received"] < UNMATCHED_TIMEOUT:
                continue  # its turn may still be being written
            # Visible rather than silently missing: keep its own trace id.
            emit(item["trace_id"], None, item, "waterplant-unmatched")
            done.append(item); orphaned += 1
            continue
        emit(host["id"][3:], parent_span(host["id"], item["attrs"].get("waterplant.tool")),
             item, host["service"])
        # Span attributes are not searchable from the trace list; tags are.
        tag(host["id"], "waterplant.actor", item["attrs"].get("waterplant.actor", ""))
        done.append(item); attached += 1
    if done:
        with LOCK:
            for d in done:
                try:
                    PENDING.remove(d)
                except ValueError:
                    pass
    if attached or orphaned:
        log("attached %d, orphaned %d, pending %d" % (attached, orphaned, len(PENDING)))


def worker():
    while True:
        try:
            drain()
        except urllib.error.HTTPError as e:
            log("HTTP %s: %s" % (e.code, e.read()[:200]))
        except Exception as e:
            log("%s: %s" % (type(e).__name__, e))
        time.sleep(TICK)


log("starting: experiment=%s gateway_service=%s port=%d tick=%ss unmatched_timeout=%ss"
    % (EXP, GW_SERVICE, PORT, TICK, UNMATCHED_TIMEOUT))
threading.Thread(target=worker, daemon=True).start()
ThreadingHTTPServer(("0.0.0.0", PORT), Receiver).serve_forever()
