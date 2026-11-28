import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exdraw import Scene
s = Scene()
INK, G, B, A, R, V, GY = s.INK, s.GREEN, s.BLUE, s.AMBER, s.RED, s.VIOLET, s.GREY

s.text(40, 26, "One tool call — the flow", 30)
s.text(40, 74, "Every arrow is labelled with what is actually on it. Verified on a live tenant: identity 2026-11-26, tracing 2026-11-28.", 16, GY)

def node(x, y, w, h, title, body, col, fill, tsize=15):
    s.box(x, y, w, h, col, fill)
    s.text(x + 16, y + 12, title, tsize, col)
    if body: s.text(x + 16, y + 12 + tsize * 1.6, body, 13, INK)

def lbl(x, y, t, col, size=12):
    s.text(x, y, t, size, col)

# ---------------- SPIRE band -------------------------------------------------
node(1540, 110, 560, 150, "SPIRE  (installed by ZTWIM)",
     "Issues a 5-minute JWT-SVID to whichever pod opens the socket.\n"
     "No credential is presented — the kernel identifies the caller.\n"
     "Publishes its JWKS at spire-oidc.<apps-domain>/keys", V, "#f3f0ff")
node(2150, 110, 300, 150, "SPIRE OIDC provider",
     "the only thing Keycloak\nneeds to understand:\na JWKS URL", V, "#f3f0ff")
s.arrow([(2100, 185), (2146, 185)], V)

# ---------------- row 1: human -> sandbox -> gateway -> keycloak -------------
node(40, 380, 300, 170, "Participant + console",
     "water-plant-ui\n\nno login exists;\n\"Operator\" is a UI string", GY, "#f8f9fa")

node(430, 340, 420, 400, "SANDBOX POD — untrusted", "", G, "#ebfbee")
node(452, 392, 376, 92, "Hermie (the agent)", "reads one file:\nmcp-tokens/gateway.json", G, "#ffffff", 14)
node(452, 508, 376, 110, "Supervisor  (PID 1)", "OpenShell's own process.\nFetches SVIDs, brokers tokens,\nrewrites credentials at egress.", B, "#ffffff", 14)
node(452, 640, 376, 56, "Workload API socket", "", GY, "#f1f3f5", 13)

node(1240, 380, 380, 230, "OPENSHELL GATEWAY — trusted",
     "Holds the operator's stored\ncredential. The only party\ntrusted with it.\n\nHas its own Workload API socket.", B, "#e7f5ff")

node(1760, 380, 440, 330, "KEYCLOAK  (the realm)",
     "TWO federated clients:\n\n  delegation-broker\n    = the BROKER, bound to the\n      gateway's SPIFFE ID\n\n  spiffe://…/sa/…-openshell-sandbox\n    = the AGENT, bound to the\n      sandbox's SPIFFE ID", A, "#fff9db")

# ---------------- row 2: enforcement and data --------------------------------
node(430, 1000, 520, 250, "MCP GATEWAY   Envoy + Authorino",
     "mcp-authz-policy on listener `mcps`\n\nAUTHENTICATION (rules are OR-ed)\n  anonymous   when no x-mcp-toolname\n  realm JWT   when x-mcp-toolname present\n\nAUTHORIZATION  tool-access-check (AND-ed)\n  ('tool:'+toolname) in resource_access[server]\n  azp == 'spiffe://…/sa/…-openshell-sandbox'", R, "#fff5f5")

node(1100, 1000, 320, 140, "MCP server",
     "telemetry-mcp\n\nnever reads the Bearer:\nthe gate already decided", B, "#e7f5ff")

node(1570, 1000, 340, 140, "plant-api",
     "UNAUTHENTICATED.\nIdentity stops one hop\nshort of the data. (Stage 9)", GY, "#f8f9fa")

# ---------------- arrows ------------------------------------------------------
# 1 browser -> sandbox
s.arrow([(344, 452), (426, 452)], GY)
lbl(190, 556, '1  POST /api/chat\n   no Authorization header', GY)
lbl(190, 600, '2  Bearer $API_SERVER_KEY\n   (resolves EMPTY)', GY)

# 3 supervisor -> socket -> SPIRE
s.arrow([(640, 622), (640, 636)], V)
lbl(654, 614, "3  FetchJWTSVID", V)
s.arrow([(852, 668), (872, 668), (872, 300), (1600, 300), (1600, 266)], V, sharp=True)
lbl(430, 762, '3  -> sandbox SVID    sub = spiffe://…/sa/<user>-openshell-sandbox  ,  aud = realm issuer  ,  exp +5min', V)

# 4 supervisor -> OS gateway
s.arrow([(852, 520), (1236, 520)], B)
lbl(900, 476, '4  "give me an intermediate"  +  the sandbox SVID', B)

# 5 OS gateway -> SPIRE
s.arrow([(1430, 376), (1430, 320), (1700, 320), (1700, 266)], B, sharp=True)
lbl(1200, 328, '5  FetchJWTSVID -> the GATEWAY\'s own SVID', B)

# 6 OS gateway -> Keycloak
s.arrow([(1624, 430), (1756, 430)], A)
lbl(900, 626, '6  grant_type=token-exchange\n   client_assertion = GATEWAY SVID        <- which software is asking\n   subject_token    = stored operator token <- that a human authorised it\n   audience         = the sandbox SPIFFE ID  <- fixed by OpenShell', A)

# 7 Keycloak -> OS gateway (intermediate)
s.arrow([(1756, 486), (1624, 486)], A)
lbl(900, 706, '7  INTERMEDIATE  azp = delegation-broker , aud = …/sa/<user>-openshell-sandbox\n   a voucher made out to ONE bearer — useless to any other sandbox', A)

# 8 OS gateway -> supervisor (intermediate only)
s.arrow([(1236, 566), (852, 566)], B)
lbl(900, 540, '8  the intermediate ONLY — the stored credential never leaves', B)

# 9 supervisor -> Keycloak direct
s.arrow([(852, 612), (1680, 612), (1680, 690), (1756, 690)], A, sharp=True)
lbl(900, 790, '9  subject_token = the intermediate\n   client_assertion = SANDBOX SVID   <- a DIFFERENT signer, hence a second client\n   scope = tool-get_reservoir_level  <- just the one tool in flight', A)

# 10 Keycloak -> supervisor (final)
s.arrow([(1760, 650), (1710, 650), (1710, 880), (700, 880), (700, 724)], A, sharp=True)
lbl(900, 892, '10  THE FINAL TOKEN   sub = <operator uuid>  ·  preferred_username = operator\n    azp = spiffe://…/sa/<user>-openshell-sandbox  ·  aud = …:8080/mcp\n    resource_access = operator roles \u2229 agent delegable set', A)

# 11 Hermie -> supervisor, in pod
s.arrow([(640, 488), (640, 504)], G)
lbl(466, 489, '11  tools/call + Bearer ${MCP_GATEWAY_TOKEN}  <- a PLACEHOLDER, not a token', G, 11)

# 12 supervisor -> MCP gateway
s.arrow([(560, 744), (560, 996)], G)
lbl(574, 830, '12  the same call, with the real Bearer\n    substituted at egress — only for the\n    endpoints the provider profile declares', G)

# 13 broker header injection (inside the gateway)
lbl(452, 1262, '13  Envoy adds  x-mcp-servername: <user>-agentops/telemetry-mcp   and   x-mcp-toolname: get_reservoir_level\n    Their PRESENCE is also the switch that turns authentication on at all.', R)

# 14 gateway -> MCP server
s.arrow([(956, 1060), (1094, 1060)], B)
lbl(960, 1150, '14  JSON-RPC body,\n    forwarded unchanged.\n    Bearer NOT forwarded', B)

# 15 MCP server -> plant-api
s.arrow([(1426, 1060), (1564, 1060)], GY)
lbl(1430, 1150, '15  GET $PLANT_API_URL/…\n    no Authorization at all', GY)

# 16 response path
s.arrow([(1740, 1146), (1740, 1310), (300, 1310), (300, 560)], GY, sharp=True)
lbl(700, 1318, '16  the answer travels back unchecked — no token is re-validated, and the reply carries no identity', GY)

# JWKS
s.arrow([(2300, 266), (2300, 350), (2150, 350), (2150, 376)], V, sharp=True, dashed=True)
lbl(2060, 300, 'Keycloak validates every SVID against\nthis JWKS — and knows nothing else\nabout SPIFFE', V)

# denial
node(40, 1000, 340, 250, "DENIED  (either predicate false)",
     "403 +\n{\"jsonrpc\":\"2.0\",\n \"error\":{\"code\":-32600,\n  \"message\":\"Forbidden:\n   Insufficient permissions\n   for this tool.\"}}\n\nHermie says \"I don't have\nsufficient permissions\"", R, "#fff5f5")
s.arrow([(426, 1100), (386, 1100)], R)

# ============================================================================
# THE TRACING PATH — added 2026-11-28
# ============================================================================
s.text(40, 1378, "THE TRACING PATH — how \"who did it\" reaches MLflow", 22, INK)
s.text(40, 1412, "Steps 17 and 18 happen at the SAME INSTANT as step 13 — the allow\ndecision is what produces the actor. Steps 19 to 21 happen afterwards.", 14, GY)

node(40, 1510, 340, 250, "hermes_otel",
     "Same pod as the sandbox\nabove.\n\nWhen the turn ends it sends\nthe AGENT's own trace to\nMLflow. That trace already\nhas a tool.* span per call —\nbut no identity on it.", G, "#ebfbee")

node(430, 1510, 560, 250, "17  Authorino — on ALLOW",
     "The same check as step 13. When it allows the\ncall it ALSO returns a header, which Envoy copies\nonto the request going upstream:\n\n  x-waterplant-actor = {\"chain\":[\n      {subject: operator},\n      {agent: spiffe://…/sandbox}]}", R, "#fff5f5")

node(1040, 1510, 460, 250, "18  Envoy writes a span",
     "Tagged from the headers it now\nhas — nothing re-derives them:\n\n  waterplant.actor   = …as above\n  waterplant.tool    = get_reservoir_level\n  waterplant.server  = …/telemetry-mcp\n  waterplant.mcp_method = tools/call", B, "#e7f5ff")

node(1550, 1510, 470, 250, "19  collector  (per tenant)",
     "Keeps ONLY mcp_method = tools/call.\nHop 1 and the session handshake carry\nthe same tool name, so without this one\ncall is recorded three times.\n\nPromotes waterplant.* so MLflow shows\nthem as trace tags.", A, "#fff9db")

node(2070, 1510, 500, 250, "20  stitcher  (sidecar)",
     "Holds the span in memory, then:\n\n 1. finds the agent turn whose time\n    window contains it\n 2. picks that trace's matching tool.* span\n 3. re-emits it with the AGENT's trace id\n    and that span as its parent", A, "#fff9db")

node(2620, 1470, 560, 330, "21  MLflow — what the participant opens",
     "A trace id here IS the OTel trace id, so a span sent\nwith the agent's id lands inside the agent's trace:\n\n  agent\n    llm.qwen3-…\n      tool.mcp_gateway_telemetry_get_reservoir_level\n        gateway verified: get_reservoir_level  <- WHO\n\nOne trace per turn. No loose traces are created.", V, "#f3f0ff")

# gateway -> step 17  (routed left of the step-13 label, clear of the denial box)
s.arrow([(430, 1230), (400, 1230), (400, 1352), (700, 1352), (700, 1506)], R, sharp=True)
lbl(412, 1326, "the allow decision", R)

s.arrow([(994, 1635), (1036, 1635)], B)
s.arrow([(1504, 1635), (1546, 1635)], A)
s.arrow([(2024, 1635), (2066, 1635)], A)
s.arrow([(2574, 1635), (2616, 1635)], A)
lbl(2075, 1772, "step 20 is needed only because the broker, between steps 12 and 13, dropped the trace context", GY)

# the agent's own trace reaches MLflow independently
s.arrow([(210, 1764), (210, 1880), (2900, 1880), (2900, 1804)], G, sharp=True)
lbl(900, 1852, "the agent's own trace — written independently, and already in MLflow before the gateway's span arrives", G)

print("elements:", s.save(sys.argv[1]))
