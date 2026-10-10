# SPEC-0005 design issues

## 2026-10-10: BR-002 port check contradicts the remapped container port edge case
- Spec: SPEC-0005, Requirement(s): BR-002, BT-012, edge case row "container: HTMLEDITOR_HOST=0.0.0.0 ..."
- Problem: BR-002 refuses a `Host` "whose port is not the bound port" and BT-012 asserts `Host: 127.0.0.1:Q` (Q not the bound port) gets `403 {"error": "forbidden host"}`. The edge case table expects `http://localhost:7999/` to be served when the container port 7842 is published as 7999, "port check uses the port in the URL the user typed". The server only knows its bound port (7842); the browser sends `Host: localhost:7999`. Reading 1 (BR-002): 403, the documented container setup breaks. Reading 2 (edge case): served, BR-002 and BT-012 are wrong.
- Evidence: `.agent_docs/docker.md:54` documents `docker run -p 7999:7842`; bound port `Dockerfile:34` (`HTMLEDITOR_PORT=7842`); spec section 2 BR-002, section 3 last row, section 4.2 BT-012.
- Needed: does the host check compare the port at all?
- Recommendation: compare the host name only, accept any port. DNS rebinding is stopped by the name (the attacker controls the name, not the loopback name list); the port adds no protection and breaks port publishing. Amend BR-002 ("whose name is not ..." without the port clause) and BT-012 (keep `Host: 127.0.0.1` without port served, drop the wrong port case), via `/sdlc-spec`.
