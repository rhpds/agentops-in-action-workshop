import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exdraw import Scene
s = Scene()
C = {'人': s.GREY, 'ui': s.GREY, 'sbx': s.GREEN, 'spire': s.VIOLET, 'gw': s.BLUE,
     'kc': s.AMBER, 'pol': s.RED, 'mcp': s.BLUE, 'api': s.GREY}

s.text(40, 26, "One tool call, end to end", 30)
s.text(40, 74, "What is on the wire at every hop, why it is there, and how it changes. "
               "Verified on a live tenant, 2026-11-26.", 16, s.GREY)

X0, W0 = 40, 300      # hop
X1, W1 = 360, 940     # on the wire
X2, W2 = 1330, 620    # why / what changed
y = 130

s.text(X0 + 8, y, "HOP", 13, s.GREY)
s.text(X1 + 8, y, "WHAT IS ON THE WIRE", 13, s.GREY)
s.text(X2 + 8, y, "WHY, AND WHAT CHANGED", 13, s.GREY)
y += 26

def row(n, hop, wire, why, colour, fill):
    global y
    lines = max(wire.count("\n"), why.count("\n")) + 1
    h = 30 + lines * 17.5
    s.box(X0, y, W0, h, colour, fill)
    s.box(X1, y, W1, h, colour, "#ffffff")
    s.box(X2, y, W2, h, colour, "#ffffff")
    s.text(X0 + 12, y + 12, n, 17, colour)
    s.text(X0 + 44, y + 15, hop, 13, s.INK)
    s.text(X1 + 12, y + 14, wire, 13, s.INK)
    s.text(X2 + 12, y + 14, why, 13, s.INK)
    y += h + 10

row("1", "participant's browser\n  -> water-plant-ui",
    'POST /api/chat    {"message": "what is the reservoir level?"}\nno Authorization header',
    'There is no login anywhere in this lab. The "Operator"\npersona is a string the UI sends, not an identity.',
    C['ui'], "#f8f9fa")

row("2", "water-plant-ui\n  -> hermes-agent svc :8787",
    'POST /v1/chat/completions\nAuthorization: Bearer $API_SERVER_KEY   (resolves EMPTY at baseline)',
    "One static service credential, shared and unattested.\nNothing downstream can tell which human asked.",
    C['ui'], "#f8f9fa")

row("3", "relay-proxy (nginx)\n  -> OpenShell gateway\n  -> sandbox supervisor",
    'the same JSON-RPC body, relayed to\ndefault--hermie--openai.openshell.localhost',
    "The sandbox has no inbound route of its own. The bridge\nrelays, so the agent stays inside the sandbox boundary.",
    C['sbx'], "#ebfbee")

row("4", "Hermie (in the sandbox)\n  decides to call a tool",
    'needs:  Authorization: Bearer <something>  for the MCP gateway\nreads:  $HERMES_HOME/mcp-tokens/gateway.json',
    "The agent never mints anything. It reads a file, which is\nthe only seam the identity design has to change.",
    C['sbx'], "#ebfbee")

row("5", "supervisor -> SPIRE\n  (Workload API socket)",
    'FetchJWTSVID(audience = <realm issuer>)\n-> JWT-SVID  sub=spiffe://…/sa/<user>-openshell-sandbox  exp=+5min',
    "No credential is presented: the kernel tells SPIRE which pod\nopened the socket. Being the workload IS the proof.",
    C['spire'], "#f3f0ff")

row("6", "supervisor\n  -> OpenShell gateway",
    'ask for an INTERMEDIATE token, presenting the sandbox SVID',
    "The gateway holds the operator's credential; the sandbox is\nnot trusted with it. So the sandbox has to ask.",
    C['gw'], "#e7f5ff")

row("7", "gateway -> SPIRE,\n  then -> Keycloak\n  (hop A of the exchange)",
    'grant_type=token-exchange\nclient_assertion_type=…jwt-spiffe\nclient_assertion=<GATEWAY SVID>        <- who is asking\nsubject_token=<stored operator token>  <- on whose behalf\naudience=spiffe://…/sa/<user>-openshell-sandbox',
    "Two separate facts in one request. --credential supplies only\nthe subject; the SVID is what replaces the client secret.\nThe audience is fixed by OpenShell and cannot be configured.",
    C['kc'], "#fff9db")

row("8", "Keycloak -> gateway\n  (the intermediate)",
    'azp = delegation-broker                 (the broker client)\naud = spiffe://…/sa/<user>-openshell-sandbox\n-> useless to any other sandbox: the audience names this one',
    "A voucher made out to one bearer. This is what stops a\nsandbox redeeming a token minted for a different sandbox.",
    C['kc'], "#fff9db")

row("9", "supervisor -> Keycloak\n  (hop B of the exchange)",
    'subject_token=<the intermediate>\nclient_assertion=<SANDBOX SVID>        <- a different signer\nscope=tool-get_reservoir_level         <- just this one tool',
    "The second signer is why there are two Keycloak clients.\nThe scope is the per-tool blast radius.",
    C['kc'], "#fff9db")

row("10", "Keycloak -> supervisor\n  THE FINAL TOKEN",
    'sub              = 959d8fef-…   <- the OPERATOR, the principal\npreferred_username = operator     <- a readable actor, not just a uuid\nazp              = spiffe://…/sa/<user>-openshell-sandbox\naud              = http://mcp-gateway-…:8080/mcp\nresource_access  = { telemetry-mcp: [ tool:get_reservoir_level ] }  <- ONE role',
    "One signed token asserting BOTH: the operator is the\nprincipal, the attested sandbox is the actor. Roles are\nalready (operator's roles ∩ what the agent may be delegated),\nnarrowed to the single tool asked for. No secret involved.",
    C['kc'], "#fff9db")

row("11", "Hermie -> MCP gateway\n  (swapped at egress)",
    'POST /mcp   {"method":"tools/call","params":{"name":"get_reservoir_level"}}\nAuthorization: Bearer ${MCP_GATEWAY_TOKEN}   <- a PLACEHOLDER\nthe supervisor substitutes the real token on the way out',
    "The agent never holds the Bearer, so a prompt-injected agent\nhas nothing to leak. Resolved only for the endpoints the\nprovider profile declares.",
    C['sbx'], "#ebfbee")

row("12", "MCP broker (Envoy)\n  adds routing headers",
    'x-mcp-servername: <user>-agentops/telemetry-mcp\nx-mcp-toolname:   get_reservoir_level\nrouted to listener `mcps` on *.mcp.local',
    "These headers are what the policy reads. Their PRESENCE is\nalso the switch that turns authentication on at all.",
    C['mcp'], "#e7f5ff")

row("13", "Authorino\n  mcp-authz-policy\n  AUTHENTICATION",
    'anonymous                 when !headers.exists(h, h == "x-mcp-toolname")\nwaterplant-<user> (JWT)   when  headers.exists(h, h == "x-mcp-toolname")\n-> validates signature, iss and aud against the realm',
    "Authorino's authentication rules are OR-ed, so the two `when`\nclauses make them exclusive: handshake traffic stays\nanonymous, and only real tool calls must carry a token.",
    C['pol'], "#fff5f5")

row("14", "Authorino\n  mcp-authz-policy\n  AUTHORIZATION",
    "tool-access-check, both predicates AND-ed:\n  ('tool:' + x-mcp-toolname) in resource_access[x-mcp-servername].roles\n  azp == 'spiffe://…/sa/<user>-openshell-sandbox'",
    "Predicate 1: may this human do this, right now.\nPredicate 2: is the caller the attested agent.\nNeither alone is sufficient — that is the intersection.",
    C['pol'], "#fff5f5")

row("15", "broker -> MCP server\n  telemetry-mcp",
    'the JSON-RPC body, forwarded unchanged\nthe Bearer is NOT forwarded, and the server does not read it',
    "Authorization ends at the gateway. The MCP server trusts\nthat anything reaching it was already allowed.",
    C['mcp'], "#e7f5ff")

row("16", "telemetry-mcp\n  -> plant-api",
    'GET $PLANT_API_URL/…      no Authorization header at all\nplant-api has no auth env: it is UNAUTHENTICATED',
    "The honest gap. Identity stops one hop short of the data, so\nthe plant's own audit cannot name the actor. Stage 9.",
    C['api'], "#f8f9fa")

row("17", "response path\n  back to the participant",
    'plant-api JSON -> MCP server -> broker -> supervisor -> Hermie -> UI\nno token is re-checked on the way back',
    "Authorization happened once, on the way in. The answer the\nparticipant reads carries no identity at all.",
    C['ui'], "#f8f9fa")

row("18", "DENIED path\n  (either predicate false)",
    '403 + {"jsonrpc":"2.0","error":{"code":-32600,\n        "message":"Forbidden: Insufficient permissions for this tool."}}',
    'Hermie reports this to the participant as "I don\'t have\nsufficient permissions" — which is the teaching moment, and\nbetter than the "network issue" it used to claim.',
    C['pol'], "#fff5f5")

# footer
s.box(X0, y + 10, W0 + W1 + W2 + 60, 150, s.VIOLET, "#faf8ff")
s.text(X0 + 22, y + 30, "The three transformations that matter", 16, s.VIOLET)
s.text(X0 + 22, y + 64,
 "1.  NOTHING becomes A HUMAN.  Steps 1-2 carry no identity at all; the operator becomes a real subject only at step 10.\n"
 "2.  A SECRET becomes AN ATTESTED WORKLOAD.  Steps 5-9 replace \"knows a string\" with \"is this pod\" -- twice, two SVIDs.\n"
 "3.  EIGHTEEN PERMISSIONS become ONE.  Step 10 intersects the human's roles with what the agent may be delegated, then\n"
 "    narrows to the single tool in flight. Steps 13-14 only check what is already there.", 14)

print("elements:", s.save(sys.argv[1]))
