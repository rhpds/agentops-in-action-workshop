import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exdraw import Scene
s = Scene()

s.text(40, 28, "How a tool call is narrowed down to one permission", 28)
s.text(40, 72, "Stage 8b, Decisions 2 and 3 — where each narrowing happens, and who does it", 16, s.GREY)

TOP = 150
H = 300
def stage(x, w, n, title, body, stroke, fill, who):
    s.box(x, TOP, w, H, stroke, fill)
    s.text(x + 20, TOP + 18, n, 22, stroke)
    s.text(x + 56, TOP + 22, title, 16, stroke)
    s.text(x + 20, TOP + 70, body, 14)
    s.text(x + 20, TOP + H - 46, who, 13, s.GREY)

stage(40, 400, "1", "The human's roles", 
      "operator holds 18 tool roles\n\n  telemetry-mcp   6\n  maintenance-mcp 5\n  control-mcp     7\n\nGranted and revoked in the\nKeycloak admin console —\nthis is the module-3 exercise",
      s.BLUE, "#e7f5ff", "set by: the participant")

stage(500, 400, "2", "∩ what may be delegated",
      "the agent client has\nfullScopeAllowed: false\nplus its own scope mappings\n\nToken roles become\n  operator's roles\n  ∩ agent's scope mappings\n\nNeither side can grant\nwhat the other lacks",
      s.VIOLET, "#f3f0ff", "computed by: KEYCLOAK, at mint time")

stage(960, 400, "3", "↓ the one tool in flight",
      "the exchange requests\n  scope=tool-get_reservoir_level\n\nToken carries exactly that\none role — nothing else\n\nA requested scope can only\nNARROW, never grant: ask for\none the operator lacks and it\nis silently dropped",
      s.AMBER, "#fff9db", "requested by: the token grant")

stage(1420, 440, "4", "the check at the door",
      "AuthPolicy on mcp-authz-policy:\n\n  ('tool:' + x-mcp-toolname)\n     in resource_access[...].roles\n  AND azp == 'spiffe://…sandbox'\n\nUnchanged by any of the above —\nit reads ONE role set, which is\nalready the intersection",
      s.RED, "#fff5f5", "enforced by: Authorino")

for x in (448, 908, 1368):
    s.arrow([(x, TOP + H/2), (x + 44, TOP + H/2)], s.GREY)

# the clarification band
CY = TOP + H + 60
s.box(40, CY, 1820, 168, s.VIOLET, "#faf8ff")
s.text(66, CY + 18, "Where the intersection actually happens — worth being precise about", 15, s.VIOLET)
s.text(66, CY + 52,
 "The AuthPolicy does NOT check the operator and the agent separately. It cannot: the token carries one role set, not two.\n"
 "Keycloak has already intersected them at step 2, so by the time Authorino sees the token, a role present in it means BOTH\n"
 "the operator holds it AND the agent may be delegated it. Same guarantee, enforced one hop earlier — and the reason no\n"
 "AuthPolicy change is needed. The flip side: if fullScopeAllowed were ever set back to true, the agent-side limit would\n"
 "silently disappear and the policy would not notice. That boolean is load-bearing.", 14)

# worked example
EY = CY + 200
s.box(40, EY, 1820, 190, s.GREY, "#f8f9fa")
s.text(66, EY + 18, "Worked example — proven on the cluster 2026-11-26, then reverted", 15, s.GREY)
rows = [
 ("operator holds", "agent may be delegated", "token carries", ""),
 ("all 18", "— (no scope mappings)", "0 roles", "the agent can do nothing"),
 ("all 18", "3 telemetry roles", "exactly those 3", "the agent narrows the human"),
 ("17 (one revoked)", "the same 3", "2 roles", "the human narrows the agent"),
]
for i, r in enumerate(rows):
    y = EY + 56 + i * 30
    col = s.INK if i else s.GREY
    s.text(80, y, r[0], 14, col)
    s.text(420, y, r[1], 14, col)
    s.text(840, y, r[2], 14, col)
    s.text(1150, y, r[3], 14, s.GREY if i else s.GREY)

print("elements:", s.save(sys.argv[1]))
