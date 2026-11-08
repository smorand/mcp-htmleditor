# BL-0038: Pointer for decks created before SPEC-0017

Nature: FEAT
Origin: deferred from SPEC-0017 (pointer in presentation mode).

## What

A deck created before SPEC-0017 carries its own navigation script without the pointer. Offer a way to
bring the pointer to such a deck (for example an agent or editor action that adds it to the file on
request), or have the editor provide the pointer itself for those decks.

## Why

SPEC-0017 gives the pointer to every presentation template, hence to every new deck; existing decks show
no Pointeur control and ignore L (SPEC-0017 section 3.2, E2E-035).

## Evidence

- `templates/bootstrap/slides-empty.html:396` (each deck carries its own key handler, copied at creation).
