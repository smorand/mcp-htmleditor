# BL-0027: A save whose html holds a lone surrogate gets no HTTP answer

Nature: BUG
Origin: US-0048 (SPEC-0009), found by its reviewer.

## Evidence

`POST /content` with body `{"html":"<html>\ud800"}`: `atomic_write` raises `UnicodeEncodeError` at `src/mcp_htmleditor/fileio.py:46`
(encoding str data as UTF-8). It is not an `OSError`, so the handler closes the connection with no answer
(`RemoteDisconnected` on the client). The pre-change `write_text` failed the same way, so it is not a regression.

## Proposal

Catch `ValueError` around the encode in the save path and answer 400 `{"error":"Invalid JSON body"}` (or 500), with one E2E test.
