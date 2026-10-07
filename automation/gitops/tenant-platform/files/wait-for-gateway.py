# Waits until the MCP gateway lists tools from every expected server.
#
# Same check as tenant-platform's plain Hermes Deployment. A TCP check is not
# enough: Hermes lists tools once at start-up and never refreshes, and a fresh
# gateway accepts connections before its broker has discovered any server.
import json, os, sys, time
import urllib.request as u

GW = os.environ["MCP_GATEWAY_URL"]
PREFIXES = [p for p in os.environ["MCP_PREFIXES"].split(",") if p]
TOKEN_FILE = os.path.join(os.environ["HERMES_HOME"], "mcp-tokens", "gateway.json")
DEADLINE = time.time() + float(os.environ["MCP_WAIT_SECONDS"])

def post(body, sid, token):
    headers = {"content-type": "application/json",
               "accept": "application/json, text/event-stream",
               "authorization": "Bearer " + token}
    if sid:
        headers["mcp-session-id"] = sid
    r = u.urlopen(u.Request(GW, data=json.dumps(body).encode(), headers=headers), timeout=15)
    raw = r.read().decode()
    sid = r.headers.get("mcp-session-id") or sid
    msgs = [json.loads(line[5:]) for line in raw.splitlines() if line.startswith("data:")]
    if not msgs and raw.strip().startswith("{"):
        msgs = [json.loads(raw)]
    return sid, msgs

last = "not attempted"
while time.time() < DEADLINE:
    try:
        token = json.load(open(TOKEN_FILE))["access_token"]
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                           "clientInfo": {"name": "wait-for-gateway", "version": "1"}}}
        sid, _ = post(init, None, token)
        post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid, token)
        _, msgs = post({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, sid, token)
        names = [t["name"] for t in (msgs[0].get("result", {}).get("tools", []) if msgs else [])]
        missing = [p for p in PREFIXES if not any(n.startswith(p) for n in names)]
        if not missing:
            print("gateway ready: %d tools" % len(names), flush=True)
            sys.exit(0)
        last = "%d tools listed, still waiting for %s" % (len(names), missing)
    except Exception as exc:
        last = "%s: %s" % (type(exc).__name__, exc)
    print(last, flush=True)
    time.sleep(5)
sys.exit("MCP gateway not ready after %ss: %s" % (os.environ["MCP_WAIT_SECONDS"], last))
