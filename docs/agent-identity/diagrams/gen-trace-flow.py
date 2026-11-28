import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exdraw import Scene
s = Scene()
INK, G, B, A, R, V, GY = s.INK, s.GREEN, s.BLUE, s.AMBER, s.RED, s.VIOLET, s.GREY

s.text(40, 26, "How one tool call's identity reaches MLflow", 30)
s.text(40, 74, "The gateway knows WHO made each tool call. Getting that fact into the agent's own MLflow trace "
               "takes three stages, because nothing in the request path carries the agent's trace context forward.", 16, GY)
s.text(40, 100, "Measured on a live tenant, 2026-11-28.", 16, GY)

def node(x, y, w, h, title, body, col, fill, tsize=15):
    s.box(x, y, w, h, col, fill)
    s.text(x + 16, y + 12, title, tsize, col)
    if body: s.text(x + 16, y + 12 + tsize * 1.7, body, 13, INK)

def band(y, n, t):
    s.text(40, y, "%s  %s" % (n, t), 19, INK)

# ============ BAND 1 — the request ==========================================
band(170, "STAGE 1", "— the tool call travels left to right. Trace context does NOT survive it.")

node(40, 215, 330, 165, "Hermes (the agent)",
     "In the sandbox. Decides to\ncall a tool.\n\nWrites its OWN MLflow trace\nwhen the turn ends.", G, "#ebfbee")
node(440, 215, 380, 165, "Envoy — hop 1   listener `mcp`",
     "The public entrance.\nAuthenticates the caller.\n\nNo tool name exists yet,\nand no actor is injected.", B, "#e7f5ff")
node(880, 215, 330, 165, "MCP broker",
     "Decides which MCP server\nthe call belongs to, then\nre-sends it to the gateway.\n\nVendor image.", GY, "#f8f9fa")
node(1270, 215, 430, 165, "Envoy — hop 2   listener `mcps`",
     "The internal hop, one per tool call.\nAuthorino has now verified BOTH\nthe human and the agent, and injects\nthe actor as a header.", B, "#e7f5ff")
node(1760, 215, 300, 165, "MCP server",
     "telemetry-mcp,\ncontrol-mcp, …\n\nRuns the tool.", B, "#e7f5ff")

for x0, x1 in [(370, 436), (820, 876), (1210, 1266), (1700, 1756)]:
    s.arrow([(x0, 297), (x1, 297)], B)

s.text(40, 400, "BREAK 1 — the agent never sends a `traceparent` header, so hop 1 starts a brand new trace\n"
                "instead of continuing the agent's.", 13, R)
s.text(880, 400, "BREAK 2 — the broker forwards NO unknown headers. Anything hop 1 knew is gone.\n"
                 "Upstream cut this from scope deliberately (Kuadrant/mcp-gateway issue #575).", 13, R)

# ============ BAND 2 — what Envoy records ===================================
band(480, "STAGE 2", "— each hop writes a span. Only one of them is worth keeping.")

node(360, 525, 400, 150, "hop 1's span",
     "waterplant.tool   = none\nwaterplant.actor  = none\n\nNothing useful: no tool name,\nno actor at this point.", GY, "#f8f9fa")
node(1240, 525, 440, 215, "hop 2's span   <- the real record",
     "waterplant.actor  = {\"chain\":[\n   {subject: operator},\n   {agent: spiffe://…/sandbox}]}\nwaterplant.tool    = get_reservoir_level\nwaterplant.server  = …/telemetry-mcp\nwaterplant.mcp_method = tools/call", B, "#e7f5ff")
node(1760, 525, 430, 215, "gateway access log",
     "The same facts as a log line.\nThe DURABLE copy: it also keeps\nthe 401s and protocol traffic that\nnever reach MLflow.\n\nSurvives everything below failing.", GY, "#f8f9fa")

s.arrow([(560, 382), (560, 521)], GY)
s.arrow([(1460, 382), (1460, 521)], B)
s.arrow([(1640, 382), (1640, 470), (1975, 470), (1975, 521)], GY)

s.arrow([(560, 679), (560, 735)], R, dashed=True)
s.text(360, 745, "X  dropped — the collector keeps only mcp_method = tools/call.\n"
                 "(Opening a session costs 3 requests and the broker stamps\n"
                 "ALL of them with the same tool name, so filtering on the tool\n"
                 "name alone would record one call three times.)", 13, R)

# ============ BAND 3 — into MLflow ==========================================
band(880, "STAGE 3", "— the span is carried to MLflow and attached INSIDE the agent's trace.")

node(40, 925, 380, 175, "hermes_otel (in the agent)",
     "Same pod as Hermes, top left.\nExports the agent's own trace to\nMLflow when the turn ends.\n\nThis is the trace the\nparticipant actually opens.", G, "#ebfbee")

node(1240, 925, 440, 265, "collector  (per tenant)",
     "Red Hat OpenTelemetry Collector.\n\nfilter        keep only tools/call\ngroupbyattrs  span attrs -> resource\n              attrs, so MLflow shows\n              them as trace TAGS\nresource      service.name\nbatch         flush after 1s", A, "#fff9db")

node(1760, 925, 480, 265, "stitcher  (sidecar)",
     "Holds the span in memory, then:\n\n1. finds the agent turn whose\n   time window contains it\n2. reads that trace's spans and\n   picks the matching tool.* span\n3. re-emits the span with the\n   AGENT's trace id + that parent", A, "#fff9db")

node(2320, 880, 680, 400, "MLflow",
     "A trace id here IS the OTel trace id — which is why a span\n"
     "sent with the agent's trace id lands inside that trace.\n\n"
     "   agent\n"
     "     llm.qwen3-…\n"
     "       tool.mcp_gateway_telemetry_get_reservoir_level\n"
     "         gateway verified: get_reservoir_level   <- WHO\n"
     "       tool.mcp_gateway_control_stop_pump\n"
     "         gateway verified: stop_pump\n\n"
     "One trace per turn. No loose gateway traces are ever created.", V, "#f3f0ff")

s.arrow([(1460, 744), (1460, 921)], B)
s.arrow([(1684, 1057), (1756, 1057)], A)
s.arrow([(2244, 1057), (2316, 1057)], A)
s.text(1694, 1026, "OTLP", 12, A)
s.text(2254, 1026, "OTLP", 12, A)

s.arrow([(230, 1104), (230, 1345), (2660, 1345), (2660, 1284)], G)
s.text(620, 1308, "the agent's own trace — written independently, and already in MLflow before the gateway's span arrives", 13, G)

# ============ footer: the two identifiers ===================================
s.box(40, 1420, 1560, 155, INK, "#ffffff")
s.text(58, 1436, "Which identifier means what — they are not interchangeable", 15, INK)
s.text(58, 1470, "jti              identifies the TOKEN. OpenShell caches it, so every call in that window shares one jti.\n"
                 "x-request-id     identifies the CALL. Envoy generates one per request — this is the join key.\n"
                 "trace id         identifies the TURN. Shared by the agent's spans and, after stage 3, the gateway's.", 13, INK)

print("elements:", s.save(sys.argv[1]))
