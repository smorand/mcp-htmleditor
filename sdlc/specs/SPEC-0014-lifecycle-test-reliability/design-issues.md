# SPEC-0014 design issues

Both entries below are non blocking: the spec was designed (`Status: designed`); the normative requirement text
was followed. They are recorded for the spec owner to amend the spec in `/sdlc-spec` if the reading chosen here is
not the intended one.

## 2026-11-06 11:59: edge case row "mid body" contradicts BR-003 and BR-004 (non blocking)
- Spec: SPEC-0014, Requirement(s): BR-003, BR-004 (section 3, row "Stop while a save `POST /content` is mid body")
- Problem: the row says such a connection is "closed without answer, file unchanged" and cites BR-003. BR-003
  closes only connections "on which it had not yet received a complete request line and headers"; BR-004 answers
  "a request whose line and headers were fully received before the stop". A request mid body has complete headers,
  so by the EARS text it is answered (BR-004), not closed.
- Evidence: spec BR-003, BR-004 and section 3; no acceptance test covers the mid body case (BT-011 covers the full
  request and the header only connection).
- Needed: confirm that BR-004 governs the mid body case, or amend BR-003/BR-004 to say "complete request line,
  headers and body".
- Recommendation: BR-004 as written (DEC-006): the request is answered normally; when the body never completes, the
  SPEC-0013 wait bound answers `408` and the file is unchanged, which keeps the row's "file unchanged".

## 2026-11-06 11:59: section 4.4 keeps `test_two_presentations_get_two_different_ports`, which BT-018 cannot pass (non blocking)
- Spec: SPEC-0014, Requirement(s): BR-015, BT-018 (section 4.4 row "Kept ... already machine independent (E18)")
- Problem: with every port 7839 to 7849 held by another process (BT-018 expects `4 passed`), the unchanged test calls
  `find_free_port("127.0.0.1", 7840)`, which raises `RuntimeError`; the test fails. The "Kept" row and BT-018
  cannot both hold.
- Evidence: `tests/test_port_range.py:34` to `:45`; `src/mcp_htmleditor/http_server.py:997` to `:1006`.
- Needed: confirm that BR-015 and BT-018 govern over the 4.4 row.
- Recommendation: BR-015 governs (DEC-015): the test runs on a block of free ports found at run time, with its
  assertions unchanged (US-0083).
