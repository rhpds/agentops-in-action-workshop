import json, itertools
_id = itertools.count(1)
def nid(p): return f"{p}{next(_id)}"
els = []
def base(**kw):
    d = dict(angle=0, fillStyle="solid", strokeWidth=2, strokeStyle="solid", roughness=1,
             opacity=100, groupIds=[], frameId=None, roundness=None, seed=1000+next(_id)*7919,
             version=1, versionNonce=2000+next(_id)*104729, isDeleted=False, boundElements=[],
             updated=1, link=None, locked=False, backgroundColor="transparent",
             strokeColor="#1e1e1e")
    d.update(kw); return d
CW = 0.56   # char width / fontSize
def text(x, y, s, size=16, color="#1e1e1e", align="left"):
    lines = s.split("\n")
    w = max(len(l) for l in lines) * CW * size
    h = len(lines) * 1.25 * size
    els.append(base(id=nid("t"), type="text", x=x, y=y, width=w, height=h,
                    strokeColor=color, text=s, fontSize=size, fontFamily=2,
                    textAlign=align, verticalAlign="top", containerId=None,
                    originalText=s, lineHeight=1.25, roundness=None))
    return w, h
def box(x, y, w, h, stroke, fill, dashed=False):
    els.append(base(id=nid("r"), type="rectangle", x=x, y=y, width=w, height=h,
                    strokeColor=stroke, backgroundColor=fill,
                    strokeStyle="dashed" if dashed else "solid",
                    roundness={"type": 3}))
def arrow(pts, color="#1971c2", start=None, end="arrow", sharp=False):
    x0, y0 = pts[0]
    rel = [[px - x0, py - y0] for px, py in pts]
    xs = [p[0] for p in rel]; ys = [p[1] for p in rel]
    els.append(base(id=nid("a"), type="arrow", x=x0, y=y0,
                    width=max(xs) - min(xs), height=max(ys) - min(ys),
                    strokeColor=color, roundness=None if sharp else {"type": 2}, points=rel,
                    lastCommittedPoint=None, startBinding=None, endBinding=None,
                    startArrowhead=start, endArrowhead=end))

GREEN, BLUE, AMBER, RED, GREY = "#2f9e44", "#1971c2", "#f08c00", "#e03131", "#868e96"

# ---- header
text(40, 28, "Why the agent needs two badges", 28)
text(40, 72, "OpenShell token_exchange — the sandbox can never hold the operator's credential", 16, GREY)

TOP, BOT = 140, 520
# ---- columns
box(40, TOP, 470, BOT - TOP, GREEN, "#ebfbee", dashed=True)
text(62, TOP + 16, "SANDBOX POD — untrusted", 15, GREEN)
box(64, TOP + 48, 422, 74, GREEN, "#ffffff")
text(82, TOP + 62, "Agent (Hermie)\nholds a placeholder, never a credential", 14, "#1e1e1e")
box(64, TOP + 140, 422, 96, BLUE, "#ffffff")
text(82, TOP + 154, "Supervisor  (PID 1, egress proxy)\nBADGE  spiffe://…/sa/<user>-openshell-sandbox\n\"I am the contractor this voucher names\"", 14)
box(64, TOP + 256, 422, 52, GREY, "#f1f3f5")
text(82, TOP + 272, "Workload API socket  (csi.spiffe.io)", 14, GREY)

GX = 760
box(GX, TOP, 450, BOT - TOP, BLUE, "#e7f5ff")
text(GX + 22, TOP + 16, "OpenShell GATEWAY — trusted", 15, BLUE)
text(GX + 22, TOP + 62, "BADGE  spiffe://…/sa/<user>-openshell\n\"I may ask on a human's behalf\"", 14)
box(GX + 20, TOP + 140, 410, 96, AMBER, "#fff9db")
text(GX + 38, TOP + 162, "HOLDS the operator's credential\n— the letter, kept in the drawer", 14)
box(GX + 20, TOP + 256, 410, 52, GREY, "#f1f3f5")
text(GX + 38, TOP + 272, "Workload API socket  (csi.spiffe.io)", 14, GREY)

KX = 1500
box(KX, TOP, 430, BOT - TOP + 120, AMBER, "#fff9db")
text(KX + 22, TOP + 16, "KEYCLOAK  (HR)", 15, AMBER)
text(KX + 22, TOP + 62,
     "Verifies each badge against\nSPIRE's published JWKS, then issues:", 14)
text(KX + 22, TOP + 352, "the agent client has fullScopeAllowed: false,\nso the roles are already the intersection\nof what the operator holds and what the\nagent may be delegated  (Decision 2)", 13, GREY)
text(KX + 22, TOP + 130, "VOUCHER (intermediate)\naud = the sandbox's badge\n— useless to anyone else", 14, "#1e1e1e")
text(KX + 22, TOP + 232, "DAY PASS (final)\nsub = operator\nazp = delegation-broker\nroles = operator \u2229 agent's\n        delegable set", 14, "#1e1e1e")

MX = 2060
box(MX, TOP, 430, 270, RED, "#fff5f5")
text(MX + 22, TOP + 16, "MCP GATEWAY  (Authorino)", 15, RED)
text(MX + 22, TOP + 62, "allow only if:\n  tool:X in the token's roles\n  AND azp == spiffe://…sandbox\n\nUnchanged \u2014 it reads ONE role set,\nwhich Keycloak already intersected.\nWith per-tool scope that set holds\nexactly the tool in flight  (Decision 3)", 14)

# ---- steps 1-3 (vertical, inside columns)
arrow([(275, TOP + 240), (275, TOP + 252)], BLUE)
text(290, TOP + 236, "1  fetch my badge", 13, BLUE)
arrow([(GX + 225, TOP + 240), (GX + 225, TOP + 252)], BLUE)
text(GX + 240, TOP + 236, "3  fetch my own badge", 13, BLUE)

# ---- step 2 / 6 in gutter 1 (labels ABOVE and BELOW their own arrows, clear of boxes)
arrow([(512, TOP + 170), (756, TOP + 170)], BLUE)
text(520, TOP + 136, "2  show badge,\n    ask for a voucher", 13, BLUE)
arrow([(756, TOP + 215), (512, TOP + 215)], BLUE)
text(520, TOP + 222, "6  voucher only —\n    the letter never leaves", 13, BLUE)

# ---- step 4 / 5 in gutter 2
arrow([(1214, TOP + 170), (1496, TOP + 170)], AMBER)
text(1222, TOP + 136, "4  the letter +\n    GATEWAY badge", 13, AMBER)
arrow([(1496, TOP + 215), (1214, TOP + 215)], AMBER)
text(1222, TOP + 222, "5  the voucher", 13, AMBER)

# ---- step 7: supervisor -> Keycloak, below the boxes
Y7 = BOT + 190
arrow([(230, BOT + 2), (230, Y7), (1680, Y7), (1680, BOT + 122)], AMBER, sharp=True)
text(470, Y7 + 14, "7  voucher + SANDBOX badge  \u2192  the day pass  (sub = operator, azp = the sandbox SPIFFE ID, roles = operator \u2229 delegable set)", 14, AMBER)

# ---- step 8: supervisor -> MCP gateway, lower still
Y8 = BOT + 290
arrow([(330, BOT + 2), (330, Y8), (MX + 215, Y8), (MX + 215, TOP + 272)], RED, sharp=True)
text(760, Y8 + 16, "8  tools/call  +  Bearer day pass, injected by the supervisor at egress", 14, RED)

# ---- footer
FY = Y8 + 70
box(40, FY, 1560, 150, GREY, "#f8f9fa")
text(66, FY + 20, "The one-line reason there are two badges", 15, GREY)
text(66, FY + 56,
     "An SVID only says \"I am this software\" — it names no human. So a badge alone can never buy a token that names the operator;\n"
     "Keycloak needs the operator's credential too. Whoever holds that credential must NOT be the sandbox, or a prompt-injected agent\n"
     "could mint anything the operator can do. So the gateway holds it — and must prove who IT is before Keycloak will act on it.", 14)

scene = {"type": "excalidraw", "version": 2,
         "source": "https://github.com/rhpds/agentops-in-action-workshop",
         "elements": els, "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"},
         "files": {}}
import sys
json.dump(scene, open(sys.argv[1], "w"), indent=1)
print("elements:", len(els))
