| Story | Spec | Title | Depends on | Tier | Status | Branch | Base |
|---|---|---|---|---|---|---|---|
| US-0001 | SPEC-0004 | autosave serializes a clone and never moves focus | main | 2 | landed | story/US-0001-autosave-serializes-a-clone | 50969dedefa9c2b0ef43acdc43669d60d02eb27b |
| US-0002 | SPEC-0005 | refuse foreign origins and host names, drop cors | main | 2 | landed | story/US-0002-refuse-foreign-origins-and-hosts | da1681aa86218fc2f8d94b115ea7a25a37900bb7 |
| US-0003 | SPEC-0005 | json only saves, refused preflight, editor non regression | US-0002 | 2 | landed | story/US-0003-json-only-saves-and-refused-preflight | cbf109a283ff53c5b8bc4250fb1bb9d44608250b |
| US-0068 | SPEC-0011 | resync the euro-information reference deck with its generated bootstrap | main | 2 | landed | story/US-0068-resync-ei-reference-with-bootstrap | main |
| US-0004 | SPEC-0011 | `--check` mode for both generators | main | 2 | landed | story/US-0004-check-mode-for-both-generators | story/US-0068-resync-ei-reference-with-bootstrap |
| US-0005 | SPEC-0011 | `make check-generated` in the quality gate and docs | US-0004 | 2 | landed | story/US-0005-make-check-generated-in-the-gate | story/US-0004-check-mode-for-both-generators |
| US-0006 | SPEC-0012 | record golden slide xml hashes and detector table | US-0005 | 2 | landed | story/US-0006-record-golden-slide-xml-hashes-and | story/US-0005-make-check-generated-in-the-gate |
| US-0007 | SPEC-0012 | charter registry, templates and detectors read it | US-0006 | 2 | landed | story/US-0007-charter-registry-templates-and-detectors | story/US-0006-record-golden-slide-xml-hashes-and |
| US-0008 | SPEC-0012 | pptx_model.py with types, constants, base class | US-0007 | 2 | landed | story/US-0008-pptx-model-py-with-types-constants-base | story/US-0007-charter-registry-templates-and-detectors |
| US-0009 | SPEC-0012 | extract text and primitives mixin | US-0008 | 2 | landed | story/US-0009-extract-text-and-primitives-mixin | story/US-0008-pptx-model-py-with-types-constants-base |
| US-0010 | SPEC-0012 | extract images and arch mixins | US-0009 | 2 | landed | story/US-0010-extract-images-and-arch-mixins | story/US-0009-extract-text-and-primitives-mixin |
| US-0011 | SPEC-0012 | extract gantt and blocks mixins | US-0010 | 2 | landed | story/US-0011-extract-gantt-and-blocks-mixins | story/US-0010-extract-images-and-arch-mixins |
| US-0012 | SPEC-0012 | extract flow and chrome mixins | US-0011 | 2 | landed | story/US-0012-extract-flow-and-chrome-mixins | story/US-0011-extract-gantt-and-blocks-mixins |
| US-0013 | SPEC-0012 | extract node and block drag script | US-0012 | 2 | landed | story/US-0013-extract-node-and-block-drag-script | story/US-0012-extract-flow-and-chrome-mixins |
| US-0014 | SPEC-0012 | extract blocks and slides scripts | US-0013 | 2 | landed | story/US-0014-extract-blocks-and-slides-scripts | story/US-0013-extract-node-and-block-drag-script |
| US-0015 | SPEC-0012 | extract save and menus scripts | US-0014 | 2 | landed | story/US-0015-extract-save-and-menus-scripts | story/US-0014-extract-blocks-and-slides-scripts |
| US-0016 | SPEC-0012 | extract format and edit scripts | US-0015 | 2 | landed | story/US-0016-extract-format-and-edit-scripts | story/US-0015-extract-save-and-menus-scripts |
| US-0017 | SPEC-0012 | extract undo script, order and serving tests | US-0016 | 2 | landed | story/US-0017-extract-undo-script-order-and-serving | story/US-0016-extract-format-and-edit-scripts |
| US-0018 | SPEC-0012 | fix skill documents naming moved methods | US-0012 | 2 | landed | story/US-0018-fix-skill-documents-naming-moved-methods | story/US-0017-extract-undo-script-order-and-serving |
| US-0019 | SPEC-0012 | update readme, agents and agent docs | US-0017, US-0018 | 2 | landed | story/US-0019-update-readme-agents-and-agent-docs | story/US-0018-fix-skill-documents-naming-moved-methods |
| US-0020 | SPEC-0012 | size caps, remaining mentions, full gate | US-0019 | 2 | landed | story/US-0020-size-caps-remaining-mentions-full-gate | story/US-0019-update-readme-agents-and-agent-docs |
| US-0021 | SPEC-0006 | topic engine and `skill --type/--all` | US-0020 | 2 | landed | story/US-0021-topic-engine-and-skill-type-all | story/US-0020-size-caps-remaining-mentions-full-gate |
| US-0022 | SPEC-0006 | `get_skill` tool and checklist fallback | US-0021 | 2 | landed | story/US-0022-get-skill-tool-and-checklist-fallback | story/US-0021-topic-engine-and-skill-type-all |
| US-0023 | SPEC-0006 | `skill-audit` sizes, budgets, missing items, json | US-0022 | 2 | landed | story/US-0023-skill-audit-sizes-and-budgets | main |
| US-0024 | SPEC-0006 | audit tool list check and stale statement check | US-0023 | 2 | landed | story/US-0024-audit-tool-list-and-stale-checks | story/US-0023-skill-audit-sizes-and-budgets |
| US-0025 | SPEC-0006 | core text, routing skill, shipped content gates | US-0024 | 2 | landed | story/US-0025-core-text-routing-skill-and-gates | story/US-0024-audit-tool-list-and-stale-checks |
| US-0026 | SPEC-0006 | topics slides-carbon and slides-ei | US-0025 | 2 | landed | story/US-0026-topics-slides-carbon-and-slides-ei | story/US-0025-core-text-routing-skill-and-gates |
| US-0027 | SPEC-0006 | topics medical and medical-sources | US-0025 | 2 | landed | story/US-0027-topics-medical-and-medical-sources | story/US-0026-topics-slides-carbon-and-slides-ei |
| US-0028 | SPEC-0006 | topics create and export | US-0025 | 2 | landed | story/US-0028-topics-create-and-export | story/US-0027-topics-medical-and-medical-sources |
| US-0029 | SPEC-0006 | topics document and mail | US-0025 | 2 | landed | story/US-0029-topics-document-and-mail | story/US-0028-topics-create-and-export |
| US-0030 | SPEC-0006 | topics website and tables | US-0025 | 2 | landed | story/US-0030-topics-website-and-tables | story/US-0029-topics-document-and-mail |
| US-0031 | SPEC-0006 | topics gantt and annotated-image | US-0025 | 2 | landed | story/US-0031-topics-gantt-and-annotated-image | story/US-0030-topics-website-and-tables |
| US-0032 | SPEC-0006 | topics arch-diagram and templates | US-0025 | 2 | landed | story/US-0032-topics-arch-diagram-and-templates | story/US-0031-topics-gantt-and-annotated-image |
| US-0033 | SPEC-0006 | topic arch-qa and the cut shipped checklist | US-0025 | 2 | landed | story/US-0033-topic-arch-qa-and-cut-checklist | story/US-0032-topics-arch-diagram-and-templates |
| US-0069 | SPEC-0006 | render the checklist in the arch-qa topic output | US-0033 | 2 | landed | story/US-0069-render-the-checklist-in-the-arch-qa-topic | story/US-0033-topic-arch-qa-and-cut-checklist |
| US-0034 | SPEC-0006 | clean real audit, all 15 topics enforced, documentation | US-0026, US-0027, US-0028, US-0029, US-0030, US-0031, US-0032, US-0033 | 2 | landed | story/US-0034-clean-real-audit-and-documentation | story/US-0069-render-the-checklist-in-the-arch-qa-topic |
| US-0035 | SPEC-0007 | `outline` on the command line | US-0034 | 2 | landed | story/US-0035-outline-on-the-command-line | main |
| US-0036 | SPEC-0007 | `get-slide` on the command line and the scanner | US-0035 | 2 | landed | story/US-0036-get-slide-command-and-scanner | story/US-0035-outline-on-the-command-line |
| US-0037 | SPEC-0007 | `outline` and `get_slide` tools | US-0036, US-0025 | 2 | landed | story/US-0037-outline-and-get-slide-tools | story/US-0036-get-slide-command-and-scanner |
| US-0038 | SPEC-0007 | `patch` with `set_text`, atomic write, path guard | US-0036 | 2 | landed | story/US-0038-patch-set-text-atomic-write-path-guard | story/US-0037-outline-and-get-slide-tools |
| US-0039 | SPEC-0007 | `delete_slide`, renumbering, dry run | US-0038 | 2 | landed | story/US-0039-delete-slide-renumbering-and-dry-run | story/US-0038-patch-set-text-atomic-write-path-guard |
| US-0040 | SPEC-0007 | `insert_slide`, `move_slide`, `replace_slide` | US-0039 | 2 | landed | story/US-0040-insert-move-and-replace-slide | story/US-0039-delete-slide-renumbering-and-dry-run |
| US-0041 | SPEC-0007 | `patch` tool and editor flag | US-0040, US-0025 | 2 | landed | story/US-0041-patch-tool-and-editor-flag | story/US-0040-insert-move-and-replace-slide |
| US-0042 | SPEC-0007 | `lint` command and structure rules | US-0038 | 2 | landed | story/US-0042-lint-command-and-structure-rules | story/US-0041-patch-tool-and-editor-flag |
| US-0043 | SPEC-0007 | charter rules l007 to l011 | US-0042 | 2 | landed | story/US-0043-charter-rules-l007-to-l011 | story/US-0042-lint-command-and-structure-rules |
| US-0044 | SPEC-0007 | lint problems in `outline` and `patch` | US-0040, US-0043 | 2 | landed | story/US-0044-lint-problems-in-outline-and-patch | story/US-0043-charter-rules-l007-to-l011 |
| US-0045 | SPEC-0007 | template, new and export services on the command line | US-0034 | 2 | landed | story/US-0045-template-new-and-export-services | story/US-0044-lint-problems-in-outline-and-patch |
| US-0046 | SPEC-0007 | `lint`, `list_templates`, `new_file`, `export` tools | US-0043, US-0045, US-0041, US-0025 | 2 | landed | story/US-0046-lint-templates-new-and-export-tools | story/US-0045-template-new-and-export-services |
| US-0047 | SPEC-0009 | state per file in the state directory, expiring update flag | US-0046 | 3 | landed | story/US-0047-state-per-file-expiring-update-flag | main |
| US-0048 | SPEC-0009 | atomic, guarded, conflict aware browser save (server side) | US-0047, US-0038 | 2 | landed | story/US-0048-atomic-guarded-conflict-aware-save | story/US-0047-state-per-file-expiring-update-flag |
| US-0049 | SPEC-0009 | conflict choice, save failures and server loss in the editor | US-0048, US-0017 | 2 | landed | story/US-0049-conflict-choice-and-save-failure-ui | story/US-0048-atomic-guarded-conflict-aware-save |
| US-0050 | SPEC-0009 | history snapshots, `history` and `restore` commands | US-0048, US-0049 | 2 | landed | story/US-0050-history-snapshots-and-restore-command | story/US-0049-conflict-choice-and-save-failure-ui |
| US-0051 | SPEC-0009 | `history` and `restore` tools, patch snapshots, docs and deployment | US-0050, US-0025, US-0041 | 2 | landed | story/US-0051-history-restore-tools-and-deploy-docs | story/US-0050-history-snapshots-and-restore-command |
| US-0052 | SPEC-0010 | store, queue endpoints and the requests command | US-0051 | 2 | landed | story/US-0052-store-queue-endpoints-requests-command | main |
| US-0053 | SPEC-0010 | agent lists and completes requests (tools) | US-0052 | 2 | landed | story/US-0053-agent-lists-and-completes-requests | story/US-0052-store-queue-endpoints-requests-command |
| US-0054 | SPEC-0010 | complete from the command line and the apply workflow | US-0053, US-0025, US-0028 | 2 | landed | story/US-0054-complete-from-the-command-line | story/US-0053-agent-lists-and-completes-requests |
| US-0055 | SPEC-0010 | ask ai panel and the requests side list | US-0053, US-0017 | 2 | landed | story/US-0055-ask-ai-panel-and-requests-side-list | story/US-0054-complete-from-the-command-line |
| US-0056 | SPEC-0010 | live refresh of the side list | US-0055 | 2 | landed | story/US-0056-live-refresh-of-the-side-list | story/US-0055-ask-ai-panel-and-requests-side-list |
| US-0057 | SPEC-0010 | write and read the ai review (tool and command) | US-0053 | 2 | landed | story/US-0057-write-and-read-the-ai-review | story/US-0056-live-refresh-of-the-side-list |
| US-0058 | SPEC-0010 | show the ai suggestions and apply one | US-0056, US-0057 | 2 | landed | story/US-0058-show-the-ai-suggestions-and-apply-one | story/US-0057-write-and-read-the-ai-review |
| US-0059 | SPEC-0010 | documentation and no file next to the user's file | US-0058 | 2 | landed | story/US-0059-documentation-and-no-file-next-to-the | story/US-0058-show-the-ai-suggestions-and-apply-one |
| US-0070 | SPEC-0010 | write_review answers the product message for a non list on the tool | US-0059 | 2 | landed | story/US-0070-write-review-non-list-same-message-on-the-tool | story/US-0059-documentation-and-no-file-next-to-the |
| US-0060 | SPEC-0008 | optional render extra, install-browser and fixtures | US-0059 | 2 | landed | story/US-0060-optional-render-extra-install-browser | main |
| US-0061 | SPEC-0008 | render the first slide to a picture | US-0060, US-0035, US-0038 | 2 | landed | story/US-0061-render-the-first-slide-to-a-picture | story/US-0060-optional-render-extra-install-browser |
| US-0062 | SPEC-0008 | choose a slide and a scale | US-0061 | 2 | landed | story/US-0062-choose-a-slide-and-a-scale | story/US-0061-render-the-first-slide-to-a-picture |
| US-0063 | SPEC-0008 | layout report for one slide | US-0062 | 2 | landed | story/US-0063-layout-report-for-one-slide | story/US-0062-choose-a-slide-and-a-scale |
| US-0064 | SPEC-0008 | report only across the deck | US-0063 | 2 | landed | story/US-0064-report-only-across-the-deck | story/US-0063-layout-report-for-one-slide |
| US-0065 | SPEC-0008 | font, script and image problems | US-0064 | 2 | landed | story/US-0065-font-script-and-image-problems | story/US-0064-report-only-across-the-deck |
| US-0066 | SPEC-0008 | json output and the render tool | US-0065, US-0024, US-0025, US-0037, US-0047 | 2 | landed | story/US-0066-json-output-and-the-render-tool | story/US-0065-font-script-and-image-problems |
| US-0067 | SPEC-0008 | large decks and documentation | US-0066 | 2 | landed | story/US-0067-large-decks-and-documentation | story/US-0066-json-output-and-the-render-tool |
| US-0071 | SPEC-0013 | refuse ambiguous identity and framing headers | main | 2 | done | story/US-0071-refuse-ambiguous-headers | main |
| US-0072 | SPEC-0013 | validate and cap the layout route length | US-0071 | 2 | done | story/US-0072-validate-and-cap-the-layout-length | story/US-0071-refuse-ambiguous-headers |
| US-0073 | SPEC-0013 | shared encodability check and the save refusal | US-0072 | 2 | done | story/US-0073-encodability-check-and-save-refusal | story/US-0072-validate-and-cap-the-layout-length |
| US-0074 | SPEC-0013 | patch and record writers refuse unencodable text | US-0073 | 2 | todo | | |
| US-0075 | SPEC-0013 | tracing and logging never break on unencodable text | US-0073 | 2 | todo | | |
| US-0076 | SPEC-0013 | deck services refuse unencodable path arguments | US-0075 | 2 | todo | | |
| US-0077 | SPEC-0013 | record, server and bind address arguments refused | US-0076 | 2 | todo | | |
| US-0078 | SPEC-0013 | wait bound, idle close and send side bound | US-0072 | 1 | todo | | |
| US-0079 | SPEC-0013 | total request bound, slow suite and documentation | US-0074, US-0077, US-0078 | 2 | todo | | |
