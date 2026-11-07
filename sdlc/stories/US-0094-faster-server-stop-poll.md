# US-0094: Faster server stop poll

> Spec: SPEC-0014 (sdlc/specs/SPEC-0014-lifecycle-test-reliability/)
> Nature: BUG
> Priority: P2
> Depends on: US-0090
> min_tier: 2
> Files touched: 2
> Closes spec: no

## Objective

Inserted by the orchestrator (drift, Section 6): the gate test step reached 326.5 s against the 330 s cap of
SPEC-0014/BT-022 because every browser test pays up to 0.5 s at server stop (`socketserver` default
`poll_interval` of `serve_forever`, `src/mcp_htmleditor/http_server.py:1101`). A shorter poll interval recovers
that time without changing behavior.

## Requirements covered

- SPEC-0014/BR-001 (partial: the stop returns promptly): WHEN the editor server is stopped THE editor server SHALL stop accepting connections and return within 2 seconds.

## Independent Test

`make test ARGS='-k stop_returns_promptly'`: with no connection open, `stop_http_server` returns in under 0.25 s (red before: about 0.5 s).

## Paths

| Path | Action |
|---|---|
| `src/mcp_htmleditor/http_server.py` | modify: `serve_forever(poll_interval=0.05)` |
| `tests/test_server_lifecycle.py` | modify: add the timing test |

## Definition of done

- [ ] RED then GREEN; `make check` green; gate test step shorter than before (report seconds).
- [ ] One commit `US-0094: Faster server stop poll`.
