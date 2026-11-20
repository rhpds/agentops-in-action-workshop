# 06 — Provenance: making the evidence layer answer "who asked?"

Identity at the gateway solves authorization. It does not by itself solve attribution — and
attribution is what this lab actually runs on. Every module from 1 to 6 asks participants to prove
something from a trace, a tool result, or plant state. None of those records a principal today.

This is Uber's second problem: "execution context (originating user, intermediate agents) is
dropped across agent hops."

## The target

One value, created once, at the only place that has verified both principals — the gateway — and
carried from there into every durable record.

```mermaid
flowchart LR
    GW["MCP Gateway<br/>Authorino"]
    H["actor + jti<br/><i>created here</i>"]
    MCP["MCP servers"]
    PA["plant-api<br/>audit row + work order"]
    ML["MLflow<br/>trace tags"]
    LOG["Authorino log<br/>decision record"]

    GW ==> H
    H ==>|"injected header"| MCP
    MCP ==>|"forwarded"| PA
    H -.->|"same jti"| LOG
    H -.->|"same jti"| ML

    classDef key fill:#f2fbf4,stroke:#27ae60,color:#000
    class H key
```

`jti` — the token's unique id, already present in today's token — is the join key. One tool call
produces a gateway decision, an MCP server log line, a plant-api audit row and an MLflow trace, and
`jti` is what proves they are the same event. That single property is what turns four separate logs
into an audit trail.

## Where the actor is created

Authorino can inject a computed value into the upstream request. On the **internal `mcps`
listener**, because that is the last hop before the MCP server and it is where both principals have
been verified:

```yaml
response:
  success:
    headers:
      x-waterplant-actor:
        plain:
          expression: >
            '{"chain":[' +
              '{"role":"subject","sub":"' + (has(auth.identity.preferred_username)
                 ? auth.identity.preferred_username
                 : (has(auth.identity.sub) ? auth.identity.sub : 'anonymous')) + '"},' +
              '{"role":"agent","sub":"' + (has(auth.identity.azp)
                 ? auth.identity.azp : 'none') + '"}' +
            '],"jti":"' + (has(auth.identity.jti) ? auth.identity.jti : '') + '"}'
```

Three things about that expression:

- **It emits a list, not two fields.** This is the decision from
  [04](04-keycloak-upgrade-path.md): when a real `act` claim becomes available, only this expression
  changes — it walks `act` instead of reading `sub` and `azp`. Every consumer downstream is
  untouched. Modelling it as `subject=…;agent=…` would make that a schema migration.
- **`has()` guards are mandatory.** The `anonymous` authentication rule leaves `auth.identity`
  empty for protocol traffic (`initialize`, `tools/list`, pings), and an unguarded field access is a
  CEL error, not an empty string.
- **`preferred_username` is preferred over `sub`.** A UUID in an audit row is useless to a
  participant reading it. Whether `sub` is even available is an open question — see
  [08](08-open-questions.md) — and the expression degrades gracefully either way.

## How the MCP servers receive it — a better option than expected

Phase 0 turned up something the earlier design missed. The three MCP servers run **mcp 2.x**, which
has a first-class identity surface:

```
mcp.server.request_state exposes: get_access_token, authenticated_principal,
                                  principal_components, ServerRequestContext
mcp.server.auth                 also present
```

So there are two routes, and they imply different things:

| Route | Mechanism | Trade-off |
|---|---|---|
| **A. Injected header** | Read `x-waterplant-actor` from the request, forward it to plant-api | The server records an opinion formed at the gateway. It verifies nothing and decides nothing — which keeps the lab's stated principle intact. |
| **B. Native SDK identity** | Configure a token verifier and read `authenticated_principal` / `get_access_token()` | More idiomatic and self-verifying. But it means the MCP servers validate tokens, which moves a security function into the application. |

**Recommend A.** Route B is tempting and more modern, but it contradicts the design record the lab
is built on:

> "Authorization belongs to MCP Gateway. Putting a check here would move enforcement into the
> application and defeat the point of the lab (§D8)."
> — `mcp-telemetry/src/telemetry_mcp/client.py:8-10`, byte-identical in all three servers

Route A records provenance without taking on enforcement. Route B is worth revisiting only if the
gateway turns out not to propagate the header (see [08](08-open-questions.md)) — in which case
reading the token the agent already sends is the natural fallback, and the servers would verify
without authorizing.

Note also that the servers run `stateless_http=True`, so there is no session to hang an identity
on; it must be per-request either way.

## Killing `raised_by: "unknown"` — the sharpest demo here

Today, `plant-api/src/plant_api/api.py:298`:

```python
raised_by: Annotated[str, Field(max_length=80, description="Identity of the requester.")] = "unknown"
```

An ordinary tool argument. **The model decides who raised the work order.** It defaults to
`"unknown"`, and the seeded records carry plausible human handles — `a.okafor`, `s.bramley` — so a
model-invented value is indistinguishable from a real one in the same column.

**Keep `raised_by` and add `raised_by_verified` beside it.** Do not overwrite it, and do not remove
the tool argument.

That is a deliberate choice. The pair is the teaching artifact:

| Field | Value | Meaning |
|---|---|---|
| `raised_by` | whatever the model wrote — perhaps `a.okafor` | What the agent *claimed* |
| `raised_by_verified` | `subject=operator; agent=hermes-agent; jti=…` | What the platform *established* |

An agent asserting a plausible human name next to a verified actor that says otherwise is the
entire lesson about self-asserted identity, visible in two columns of one record. Removing the
argument would hide it; overwriting it would erase the comparison. It also means the tool schema
the agent's SOUL was written against does not change.

## Control actions need an actor at all

Work orders at least have a field. Control actions have nothing: `set_pump_speed`, `start_pump`,
`stop_pump`, `set_valve`, `emergency_shutdown` each mutate state under a lock and return an
`ActionResult`, with no actor, no timestamp, and no log line anywhere in `plant-api`.

So "who stopped pump 4?" is currently unanswerable from the plant's own records. Proposed: a
bounded in-memory audit list on the same state object plant-api already holds, exposed as
`GET /audit`, with the actor chain and `jti` per entry. plant-api **stays single-replica**
(`strategy: Recreate`, state is an in-process object behind an asyncio lock), so this is one more
field on an object that is already the single source of truth — not new infrastructure.

## Traces

`ui/src/waterplant_ui/traces.py` already resolves a turn's trace id and already speaks the MLflow 3
API. Adding tags there — `waterplant.actor`, `waterplant.source` (`console` / `probe`),
`waterplant.jti` — gives traces a subject **without forking the pinned `hermes-otel` plugin**,
which is fetched by commit and sha256 in `hermes-openshell/Containerfile` and is the expensive
alternative.

It also replaces the current correlation method, which is comparing a casefolded 120-character
prefix of `request_preview` against the message the console sent. That works, and it is a clever
piece of engineering, but it is a heuristic standing in for an identifier. `jti` is the identifier.

## Making the probes distinguishable — and being honest about the limit

`plant_state.py:14-20` already specifies the fix:

> "Recommend a distinct `attack-runner` user rather than reusing `operator`: reusing it would make
> attack traffic indistinguishable from the participant's own in every trace they inspect, which is
> precisely what modules 4 and 5 are teaching them to tell apart."

**In scope and cheap:** an `attack-runner` realm user; probe turns tagged
`waterplant.source=probe`; the console's own direct plant-api calls attributed to it. That already
fixes the stated problem — the participant can tell the two apart in the evidence they are asked to
inspect.

**The honest limit:** probe tool calls reach the plant *through the same Hermes* as the human, and
Hermes holds one token file. So at the gateway, a probe's tool call and a human's are the same
identity, and no header trick changes that — there is no per-request identity reaching the agent.
Distinguishing them at the gateway would need a second agent instance (`hermes-probe`) with its own
broker running as `attack-runner`, which costs a pod against the participant's CPU quota and a
second stream of calls into a MaaS endpoint that already returns 429s under light load at 30
tenants. **Worth documenting as a stretch; not worth enabling by default.**

## What this does not fix

- **Retrieved content is still untrusted.** A compromised document inside an allowed path can still
  influence the agent. Provenance records that the agent acted; it does not judge why.
- **The agent can still misreport.** The SOUL says it never describes an action it did not take,
  and the trace is what proves otherwise. Provenance strengthens that, it does not replace it.
- **One human per tenant.** With no participant login, `subject` is a constant within a tenant. The
  value is in distinguishing *agent from human* and *probe from operator*, not one person from
  another.
