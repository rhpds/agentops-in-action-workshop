import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exdraw import Scene
s = Scene()

s.text(40, 28, "Stage 8b — two Keycloak clients, and the one credential kept at rest", 28)
s.text(40, 72, "Which SVID signs which hop, what is stored where, and the two costs that come with it", 16, s.GREY)

TOP = 150
# --- left: who signs what
s.box(40, TOP, 780, 330, s.BLUE, "#e7f5ff")
s.text(62, TOP + 18, "TWO SIGNERS, SO TWO FEDERATED CLIENTS", 15, s.BLUE)
s.text(62, TOP + 58,
 "Keycloak resolves a federated client by matching the assertion's\n"
 "subject against jwt.credential.sub, and requires exactly ONE match.\n"
 "Two SVIDs sign, so there must be two clients.", 14)

s.box(62, TOP + 140, 350, 160, s.AMBER, "#fff9db")
s.text(80, TOP + 156, "the BROKER — delegation-broker", 14, s.AMBER)
s.text(80, TOP + 186,
 "jwt.credential.sub =\n  …/sa/<user>-openshell\n     (the gateway)\n\nsigns hop 2, the intermediate", 13)

s.box(442, TOP + 140, 358, 160, s.GREEN, "#ebfbee")
s.text(460, TOP + 156, "the AGENT client", 14, s.GREEN)
s.text(460, TOP + 186,
 "jwt.credential.sub =\n  …/sa/<user>-openshell-sandbox\n     (the sandbox)\n\nsigns hop 3 — so its id is the azp", 13)

# --- right: what is stored
GX = 880
s.box(GX, TOP, 700, 330, s.VIOLET, "#f3f0ff")
s.text(GX + 22, TOP + 18, "THE GATEWAY'S PROVIDER STORE", 15, s.VIOLET)
s.box(GX + 22, TOP + 56, 656, 112, s.AMBER, "#fff9db")
s.text(GX + 40, TOP + 72,
 "operator_token      AT REST   ← set with --credential\n"
 "the human's authorisation. Cannot be derived from an SVID,\n"
 "so it is the one thing that must be stored. Broker-only:\n"
 "never injected into the sandbox.", 13)
s.box(GX + 22, TOP + 188, 656, 96, s.GREEN, "#ebfbee")
s.text(GX + 40, TOP + 204,
 "gateway_token       NEVER STORED\n"
 "minted on demand by the profile's token_grant block.\n"
 "This is what --runtime-credentials would have meant — and why\n"
 "that flag cannot be used here: it would store nothing at all.", 13)

# --- cost 1: the re-stamp loop
LY = TOP + 400
s.box(40, LY, 780, 230, s.RED, "#fff5f5")
s.text(62, LY + 18, "COST 1 — the stored credential expires and cannot refresh itself", 15, s.RED)
s.text(62, LY + 56,
 "accessTokenLifespan is 1800s, and a broker-only credential \"cannot\n"
 "declare workload injection metadata such as env vars, static\n"
 "placement, refresh, or token grant metadata\". So something outside\n"
 "must re-stamp it on a timer.", 14)
s.box(62, LY + 150, 740, 60, s.GREY, "#ffffff")
s.text(80, LY + 166,
 "bridge supervisor, every <30 min:   openshell provider update --credential operator_token=<fresh>", 13)
s.text(62, LY + 215, "", 13)

# --- cost 2: the open audience question
s.box(880, LY, 700, 230, s.AMBER, "#fff9db")
s.text(902, LY + 18, "COST 2 — unverified: the intermediate audience is not ours to choose", 15, s.AMBER)
s.text(902, LY + 56,
 "\"the gateway intermediate exchange ALWAYS uses the verified\n"
 "supervisor SVID subject as its audience\", and audience_overrides\n"
 "\"do not affect the gateway intermediate exchange\".\n\n"
 "So hop 3's subject token carries aud = a spiffe:// URI. If Keycloak\n"
 "still demands the requesting client be in aud, the AGENT client's\n"
 "clientId may have to BE that SPIFFE ID — which moves azp off\n"
 "a friendly name and makes the policy value tenant-specific.", 13)

# arrow from the open question up to the agent client it threatens
s.arrow([(1000, LY - 6), (700, LY - 6), (700, TOP + 304)], s.AMBER, dashed=True)

FY = LY + 262
s.box(40, FY, 1540, 118, s.GREY, "#f8f9fa")
s.text(66, FY + 18, "Test this before building item 4 — two calls, no OpenShell needed", 15, s.GREY)
s.text(66, FY + 52,
 "Create a client whose clientId is the sandbox SPIFFE ID; mint a token with audience=<that client id> to stand in for the\n"
 "intermediate token; exchange it as that client. If it is refused, Decision 1's client layout changes before any of it is built.", 14)

print("elements:", s.save(sys.argv[1]))
