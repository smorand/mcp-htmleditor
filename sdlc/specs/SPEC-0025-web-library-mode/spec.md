# Web library mode: functional specification

> Id: SPEC-0025
> Nature: FEAT
> Depth: L
> Depth evidence: FEAT / depth L: 9 bounded contexts (sign in and sessions, access control, library, upload and removal, administration, activity, presentation editing, local mode, deployment address), 3 new persisted concepts (folders with member roles, the activity list, sessions) and 74 requirements. Override with --depth.
> Status: designed
> Generated on: 16 November 2026
> Project: existing
> From backlog: BL-0049
> Depends on: none
> Security: internal finding
> CVSS: not scored
> Affected: n/a (new capability: the sign in and the access control it adds are what this increment introduces; the absence of any authentication in the existing local mode and its packaged image stays as recorded in BL-0019)
> Fixed in: unreleased

## 1. Summary

The web library mode is a new way to run the product: a private web application, reached at slides.scm-platform.org, where people sign in with their Google account and find the presentations shared with them, grouped in folders. According to their role in each folder (Admin, RW or RO) they view, present, download, edit, upload or delete presentations; a presentation opens in the same editor as in the local mode. One administrator creates the folders and decides who can enter with which role, and reads a list of who did what. Nothing is public. It answers an immediate need (two conference presentations to share privately, with the presenter window and the editor, which the public static site cannot offer) and it is the first sign in the product has ever had (BL-0019). The local mode, which serves one local file, does not change.

## 2. Current State (MANDATORY, every depth)

### 2.1 What users can do today

- A person runs the product on one local presentation at a time and edits it in a browser: edit mode, undo and redo, full screen, pointer, presenter window with speaker notes, download of the HTML and of the PPTX (rows 10, 12 of Section 14.1).
- Each presentation needs its own running copy of the product: it shows one file at a time, and asking a running copy to open another file only replaces the file it shows (row 1).
- There is no sign in, no notion of person, role, folder or upload: whoever can reach the address has every right on the file. The only protection is that requests coming from other web pages open in the same browser, or addressed through a foreign host name, are refused (rows 2, 3).
- The editor stores each change by itself: 0.8 seconds after typing stops, and at once when the person leaves the edited field; there is no Save control (row 19). When two people change the same file and the second one has typed text not yet stored, that change is stopped by the notice "The file changed on disk. Reload to see the changes, or keep your version." with "Keep mine" and "Reload"; every stored change keeps the previous version in a history (rows 5, 6, 20).
- A packaged version for servers exists; it can be reached from the whole network and, like the local mode, asks for no sign in. This risk was accepted and deferred (BL-0019, row 8).
- The editor and the presentations show their own texts, some in French (for example the toolbar labels "Édition", "Annuler", "Rétablir"), others in English ("Requests", "Ask AI", "Notes") (row 21).
- The two conference presentations are published on a separate public static site, without protection and without editing (ASSUMED: hosted outside this repository, as stated by the owner; row 16 of Section 14.1).

### 2.2 Specs governing this area

- SPEC-0001 Section 7: "Local, single user: no authentication on the preview server". Deviation: in the web library mode every page needs a Google sign in. The local mode keeps the sentence unchanged.
- SPEC-0005/BR-002 (only the local host names and the configured bind name are accepted) and BR-006 (the liveness answer stays open on every host name). Deviation: the web library mode additionally accepts its own host name, slides.scm-platform.org, and only that one for everything but the liveness answer, which stays open on every host name as BR-006 says, but is reduced to "running" and the version (FR-NEW-073); FR-NEW-001 holds for every other address. The local mode keeps BR-002 as is. SPEC-0005 uses the identifiers BR-001 to BR-008; it has no FR-003 or FR-004. SPEC-0001/FR-003 (reload when the file changed on disk) is kept for presentations opened from the library; SPEC-0001/FR-004 (the overlay shown while an agent rewrites the file) does not apply, since no agent opens an update window on a library presentation.
- BL-0019 (authenticate the preview server beyond the loopback address, deferred by user decision on 10 October 2026). This increment answers it for the web library mode only; the local mode and the packaged image started with a single file stay as BL-0019 records them.
- SPEC-0009 (reliable saves: conflict notice, history) is reused unchanged: the conflict behavior between two editors is the one of the local mode (FR-NEW-027).
- SPEC-0007 (the structure checks of a presentation) is reused to decide whether an uploaded file is a valid presentation (FR-NEW-031).
- SPEC-0022 (presenter window, speaker notes, download) is reused unchanged for viewers and editors.
- SPEC-0023/FR-NEW-009 (files next to the open deck) does not apply to the library: a presentation is one file and embeds its pictures.

### 2.3 What is verified today

Tests exercise the storing of a change, the conflict notice and the history of a single served file, the download of that file, the serving of pictures next to a deck with its containment rules, the presenter window and the keyboard shortcuts, and the host and origin checks. No test exercises a sign in, a person, a role, a folder, an upload by a person, a deletion of a presentation, the administration, the activity list or the serving of several presentations at once; none of these exists. Commands and files: Section 14.1.

## 3. Scope

### 3.1 In scope

- A private web application at slides.scm-platform.org with Google account sign in, a 30 day session and "Sign out".
- Three roles: Admin (global, one fixed email address), RW and RO (per folder, per email address).
- The home page listing the accessible folders, the folder page listing the presentations, and the uniform "Access denied." for anything missing or forbidden.
- Opening a presentation in the full editor (RW and Admin) or in a read only form (RO) with full screen, presenter window with notes, and HTML and PPTX download.
- Upload of presentations (.html, at most 25 MB, valid, allowed names) with replacement on name collision, and deletion of presentations.
- The administration panel: create and delete folders, add, change and remove members, read the activity list (the 500 latest successful actions).
- The initial content: the folder "WCBIP Melbourne Décembre 2026" with the two presentations "From Challenges to Change" and "Bridging the Gap" and lamya.chrif@gmail.com as RW.
- Protection of the viewer against the scripts a presentation contains.
- The unchanged behavior of the local mode, stated and tested.
- Texts and figures proposed by this specification, which the owner did not state and can change without touching the rest: the messages "The upload failed. Nothing was changed.", "The library is unavailable. Try again later.", "The name does not match. Nothing was deleted." and "No activity yet."; the three problem texts "the file is not declared as a presentation", "the file has no slide" and "the file is not valid UTF-8 text"; the labels "Read and write", "Read only", "Replace", "Cancel", "Delete" and the activity line texts; the date and size formats; the rule that file names accept Latin letters with accents only while folder names accept every alphabet; the performance figures (2 seconds, 2 minutes at 10 megabits per second); the order of the checks of an upload; the 100 character limit of a file name; the size, date and ordering formats of Section 6 (FR-NEW-015, FR-NEW-018); the progress text; the names of the controls of FR-NEW-067; "This is not a valid role."; the 0.6 and 0.8 second storing delays, which are those of the editor today.

### 3.2 Out of scope, and why

| Item | Why |
|---|---|
| Creating a presentation from a template in the interface | Stated out of scope by the owner (BL-0049, Notes); presentations are made in the local mode and uploaded. Proposal for a future backlog entry, not yet written. |
| Renaming or moving a presentation between folders | Stated out of scope by the owner (BL-0049, Notes). Proposal for a future backlog entry. |
| Several administrators | Stated out of scope by the owner (BL-0049, Notes): one fixed address. Proposal for a future backlog entry. |
| Uploading several files at once, or a folder | Not asked; one file per upload keeps the checks and messages simple. |
| Pictures or other files next to a presentation | A presentation is one self contained file; the two seeded decks already embed their pictures. |
| Documents, websites and mails | The library holds presentations only; other kinds are refused as "not declared as a presentation". |
| Restoring an earlier version from the interface | The history exists and an operator can list and restore it (SPEC-0009); no interface for people is asked. |
| A trash or an undo for deletions | The owner decided deletions are definitive. |
| Sign in methods other than Google, passwords, invitations by email, access requests | Not asked. The administrator adds addresses by hand. |
| Notifications, comments, search, sharing links, quotas per folder | Not asked. |
| Changing the existing public static site | The owner asked that it is not touched. |
| Authenticating the local mode or the single file packaged image | BL-0019 stays deferred for them. |

### 3.3 Constraints imposed by the context

- **Address (imposed by the owner, BL-0049 What):** the web library mode is reached at slides.scm-platform.org through a secure connection.
- **Language (imposed by the owner, BL-0049 What):** the whole interface the mode adds is in English; there is no public page; the editor and the presentations keep their own texts.
- **Sign in (imposed by the owner, BL-0049 What):** Google account sign in. The sign-in credentials are supplied by the operator at deployment.
- **Dependency (to be done at deployment, by the owner; stated in BL-0049 Evidence):** the return address of the sign in for slides.scm-platform.org must be added in the owner's Google console before the first deployment; until then every sign in ends with "Sign-in is unavailable. Try again later." (EXC-023c).
- **Administrator (imposed by the owner, BL-0049 What):** the only administrator is seb.morand@gmail.com, compared without regard to case. It is fixed, not configurable by the interface.
- **Upload limit (stated by the owner when requesting this specification, not recorded in BL-0049):** 25 MB, that is 26 214 400 bytes.
- **Public static site (stated by the owner when requesting this specification, not recorded in BL-0049):** lamya-slides.scm-platform.org is not touched.

## 4. Actors

| Actor | Who | What they can do |
|---|---|---|
| Visitor | Anyone who is not signed in | See the sign in page and choose "Sign in with Google". Nothing else. |
| RO member | A person listed RO in a folder, for that folder | View, present, download HTML and PPTX. |
| RW member | A person listed RW in a folder, for that folder | Everything a RO member can, plus edit (changes are stored by themselves), upload, delete. |
| Admin | seb.morand@gmail.com | Everything a RW member can in every folder, plus the administration panel and the activity list. |
| Google | The external identity provider | Tells the product which account signed in. |
| Presentation script | Code inside a presentation, possibly hostile | Runs while the presentation is shown; must stay confined to the presentation itself. |
| Operator | The owner running the product | Starts and restarts it, reads the history of a presentation, deploys it. |
| Local user | A person using the local mode | Edits one local file; unaffected. |

## 4.5 Bounded contexts (MANDATORY at M and L)

| Context | What it owns | Key concepts |
|---|---|---|
| Sign in and sessions | Who the person is and for how long | Google account, session of 30 days, sign out, sign in page |
| Access control | What a person can do where | Admin, RW, RO, role per folder, "Access denied." |
| Library | What exists and how it is listed | Folder, presentation, home page, folder page, last modified date, size |
| Upload and removal | How presentations get in and out | Upload checks, collision, replacement, deletion, progress |
| Administration | Who decides | Folder creation and deletion, members, roles |
| Activity | What happened | Activity list, 500 latest lines |
| Presentation editing | The editor itself, unchanged | Edit mode, automatic store, history, conflict notice, presenter window, notes |
| Local mode | The existing single file use | Local file, no sign in |
| Deployment address | Where the product lives | Address, secure connection, host name |

## 5. Usage scenarios

### SC-001: Sign in and sign out

**Actor:** A visitor with a Google account.

**Preconditions:** The visitor is signed out. lamya.chrif@gmail.com is RW in "WCBIP Melbourne Décembre 2026"; bob.nobody@gmail.com is in no list.

**Flow:**

1. The visitor opens slides.scm-platform.org → the sign in page shows one action, "Sign in with Google", and nothing about the library.
2. The visitor chooses "Sign in with Google" → Google asks for the account and the consent.
3. The visitor completes it with an authorized account → the home page lists their folders and offers "Sign out".
4. The person chooses "Sign out" → the sign in page is shown again.

**Postconditions:** The person is signed in on the home page, or signed out on the sign in page. The library shows no content to a signed out browser.

**Exceptions:**

- EXC-001a: at step 2 Google cannot be reached → "Sign-in is unavailable. Try again later." on the sign in page, still signed out.
- EXC-001b: at step 2 the visitor cancels the consent → back on the sign in page, still signed out.
- EXC-001c: at step 3 the account is bob.nobody@gmail.com → "Access denied." and a "Sign out" button, no library content.
- EXC-001d: after step 4 the visitor presses the Back button → the sign in page, no folder or presentation name.
- EXC-001e: a visitor requests a presentation file or a download without signing in → the sign in page, no file.
- EXC-001f: at step 2 the answer does not belong to a sign in this browser started, or is used a second time → "Sign-in is unavailable. Try again later.", still signed out.
- EXC-001g: a page of another site tries to show the sign in page or a library page inside a frame → nothing is shown.

**Interactions:** SC-002: how long the sign in lasts. SC-004: direct links when signed out.

### SC-002: Session lifetime

**Actor:** A signed in person.

**Preconditions:** The person signed in some days ago; the session lasts 30 days from the sign in.

**Flow:**

1. The person returns, even after closing the browser, within 30 days → the library opens without Google.
2. The person returns after 30 days → the sign in page is shown; after signing in the person arrives on the page they asked for when allowed.
3. The session ends while the person is editing → the presentation and the unsaved changes stay on screen with "Your session has expired. Sign in again to save."; nothing is saved.
4. The person signs in again in another window and leaves the edited field in the first → the changes are stored.

**Postconditions:** A session is valid for exactly 30 days from the sign in, never extended by use.

**Exceptions:**

- EXC-002a: step 3, the person leaves the edited field before signing in again → the same message, nothing stored, and no other notice (no "Save failed:" prefix, no "Connection to the editor server lost").
- EXC-002b: between expiry and the new sign in the administrator removed the person from every folder → "Access denied." after signing in.
- EXC-002c: step 4, someone else saved the presentation meanwhile → the conflict notice of SC-008.

**Interactions:** SC-008 (conflict notice), SC-017 (rights removed).

### SC-003: Home page: the accessible folders

**Actor:** A signed in person.

**Preconditions:** The library holds "WCBIP Melbourne Décembre 2026", "Cardiology 2027" and "Pneumo Été". dan.rw@example.org is RW in "Cardiology 2027" and RO in "Pneumo Été"; carol.ro@example.org is RO in "Cardiology 2027".

**Flow:**

1. The person signs in or opens the home page → the folders they can access are listed alphabetically without regard to case or accents, each with their role.
2. The administrator opens the home page → every folder is listed with the label "Admin" and an entry "Administration" is shown.
3. The person chooses a folder → the folder page opens (SC-004).

**Postconditions:** The person sees exactly the folders where they hold a role; the administrator sees all.

**Exceptions:**

- EXC-003a: the administrator and no folder exists → "You have no access to any folder yet."
- EXC-003b: the stored library cannot be read → "The library is unavailable. Try again later." and no partial content.
- EXC-003c: the library holds 200 folders → the list is shown within 2 seconds and every folder stays reachable by keyboard.

**Interactions:** SC-004, SC-013.

### SC-004: Folder contents and navigation

**Actor:** A signed in person, or a visitor with a direct link.

**Preconditions:** "Cardiology 2027" holds "Heart Failure Update" (modified 10 Nov 2026 09:15, 2.0 MB), "Arrhythmia Basics" and "Statins Review" (both modified 12 Nov 2026 16:40, 512.0 KB and 1.5 MB).

**Flow:**

1. The person opens a folder → its presentations are listed with name, last modified date and size, most recent first, equal times in alphabetical order, with a way back to the home page.
2. The person chooses a presentation → it opens in the editor (SC-005, SC-006, SC-007).
3. A signed out visitor opens a direct link → the sign in page; after signing in they arrive on the linked page when allowed.

**Postconditions:** The person has reached the page they wanted, or has seen "Access denied."

**Exceptions:**

- EXC-004a: the folder has no presentation → "This folder has no presentations yet."
- EXC-004b: the folder does not exist → "Access denied."
- EXC-004c: the person holds no role in the folder → "Access denied.", identical to EXC-004b.
- EXC-004d: the presentation was deleted since the link was made → "Access denied."
- EXC-004e: after signing in the account has no right on the linked page → "Access denied."

**Interactions:** SC-001, SC-018.

### SC-005: RO role: view, present, download

**Actor:** A person who holds RO in a folder.

**Preconditions:** carol.ro@example.org is RO in "Cardiology 2027".

**Flow:**

1. Carol opens "Heart Failure Update" → the presentation is shown without any control that changes it.
2. Carol shows it full screen and opens the presenter window → the current slide, the next slide and the speaker notes are shown.
3. Carol downloads the HTML and the PPTX → she receives the stored presentation under its own name and a PPTX of the same slides.

**Postconditions:** Carol has viewed, presented and downloaded; nothing stored has changed.

**Exceptions:**

- EXC-005a: the folder page offers no Upload and no Delete; the editor offers no edit mode, undo or redo; the key E does nothing.
- EXC-005b: Carol sends, outside the interface, the storing of a change, a deletion or an upload → "Access denied." and nothing changes.

**Interactions:** SC-017 (role lowered while viewing), SC-019.

### SC-006: RW role: edit, upload, delete

**Actor:** A person who holds RW in a folder, and the administrator.

**Preconditions:** dan.rw@example.org is RW in "Cardiology 2027" and RO in "Pneumo Été".

**Flow:**

1. Dan opens the folder page of "Cardiology 2027" → the Upload control and a Delete control on each row are shown.
2. Dan opens "Arrhythmia Basics", uploaded by someone else → he edits it; the change is stored when he leaves the field (SC-007).
3. Dan opens "Pneumo Été" → no Upload and no Delete are shown there.

**Postconditions:** Dan holds the rights of his role in each folder separately.

**Exceptions:**

- EXC-006a: Dan opens a folder where he holds no role → "Access denied."
- EXC-006b: Dan opens the administration panel → "Access denied."

**Interactions:** SC-009, SC-012, SC-013.

### SC-007: Editor parity

**Actor:** A person who can edit a presentation.

**Preconditions:** dan.rw@example.org is RW in "Cardiology 2027".

**Flow:**

1. Dan opens "Heart Failure Update" → the editor of the local mode is shown with all its options.
2. Dan changes the title of slide 1 and leaves the field (or stops typing for 0.8 seconds) → the new version is stored by itself, there is no Save control, and the previous version is kept in the history.
3. Dan edits the speaker notes, opens the presenter window and downloads the HTML and the PPTX → everything works as in the local mode.

**Postconditions:** The presentation holds Dan's changes; the history holds the earlier version; the activity list is unchanged.

**Exceptions:**

- EXC-007a: storage is full when the change is stored → the editor's usual save failure notice with the reason; the changes stay on screen; nothing stored.
- EXC-007b: the text holds accents, Chinese characters or emoji → it is stored and shown back unchanged.

**Interactions:** SC-008 (concurrent edits), SC-021 (the local mode).

### SC-008: Concurrent editing

**Actor:** Two people who can edit the same presentation.

**Preconditions:** dan.rw@example.org and the administrator both have "Statins Review" open for editing.

**Flow:**

1. The administrator changes the title and leaves the field → it is stored.
2. Dan, who had already typed text that was not stored yet, leaves his field → the notice "The file changed on disk. Reload to see the changes, or keep your version." with "Keep mine" and "Reload" is shown; nothing is stored yet. (A person who had typed nothing sees the stored version appear on their screen within 2 seconds, with no notice.)
3. Dan chooses "Keep mine" → his version is stored and the administrator's version is kept in the history; or Dan chooses "Reload" → the stored version is shown and his unsaved changes are dropped.

**Postconditions:** Exactly one version is stored; the other is in the history or dropped by the person's choice.

**Exceptions:**

- EXC-008a: the presentation was replaced by an upload while Dan edited → the same notice.
- EXC-008b: the presentation was deleted while Dan edited → "Access denied." when his change is stored, the changes stay on screen, nothing is recreated.
- EXC-008c: both leave their edited field at the same second → one is stored, the other gets the notice, no mixed content.

**Interactions:** SC-010, SC-012.

### SC-009: Upload validation

**Actor:** A person with RW in a folder.

**Preconditions:** dan.rw@example.org is RW in "Cardiology 2027".

**Flow:**

1. Dan chooses Upload and picks a file → the file is checked in this order: extension, name, size, validity as a presentation.
2. Every check passes → "Uploaded Quarterly Review." and the presentation is listed first.

**Postconditions:** Only valid presentations of at most 25 MB with an allowed name are stored.

**Exceptions:**

- EXC-009a: not an .html file → "Only .html files are accepted."
- EXC-009b: the name has a path, starts with a dot or uses other characters → "This file name is not allowed."
- EXC-009c: 26 214 401 bytes → "The file is larger than 25 MB."; 26 214 400 bytes is accepted.
- EXC-009d: not declared as a presentation, no slide, or a blocking structure error → "This file is not a valid presentation: <first problem>."
- EXC-009e: a name already in use → SC-010.

**Interactions:** SC-010, SC-011, SC-019.

### SC-010: Name collision and replacement

**Actor:** A person with RW in a folder.

**Preconditions:** "Statins Review" (1.5 MB) exists in "Cardiology 2027".

**Flow:**

1. Dan uploads a valid file called "statins review.HTML" → the question A presentation named "Statins Review" already exists. Replace it? is shown with "Replace" and "Cancel".
2. Dan chooses "Replace" → the presentation is replaced in one step, the previous version is kept in its history and "Uploaded Statins Review." is shown.
3. Or Dan chooses "Cancel" → nothing changes.

**Postconditions:** The folder holds one presentation of that name.

**Exceptions:**

- EXC-010a: the file is also invalid → the validation message only, no question.
- EXC-010b: the same name exists in another folder → no question; the other folder is untouched.
- EXC-010c: two people upload the same new name at the same moment → one presentation.

**Interactions:** SC-008, SC-011.

### SC-011: Upload progress, interruption and double submit

**Actor:** A person with RW in a folder.

**Preconditions:** dan.rw@example.org is RW in "Cardiology 2027"; he uploads a valid 25 MB file.

**Flow:**

1. Dan starts the upload → the file name and a growing percentage are shown.
2. The upload completes → "Uploaded <name>." and the presentation is listed.

**Postconditions:** The presentation is complete or absent, never partial.

**Exceptions:**

- EXC-011a: the connection is lost, or the page is refreshed or closed, midway → no partial presentation; for a replacement the previous version is intact.
- EXC-011b: Dan submits twice → one presentation.
- EXC-011c: the library cannot store the file → "The upload failed. Nothing was changed."
- EXC-011d: the connection is slow (10 megabits per second) → the 25 MB upload still completes within 2 minutes.

**Interactions:** SC-009, SC-010, SC-017.

### SC-012: Delete a presentation

**Actor:** A person with RW in a folder, or the administrator.

**Preconditions:** "Statins Review" exists in "Cardiology 2027"; dan.rw@example.org is RW there.

**Flow:**

1. Dan chooses Delete on "Statins Review" → Delete "Statins Review"? This cannot be undone. with "Delete" and "Cancel".
2. Dan chooses "Delete" → the presentation and its history are removed for good and the list is updated.

**Postconditions:** The presentation no longer exists anywhere, with no trash.

**Exceptions:**

- EXC-012a: Dan chooses "Cancel" → nothing changes.
- EXC-012b: someone else already deleted it → "Access denied." and the list is refreshed.
- EXC-012c: it was the last presentation → "This folder has no presentations yet."

**Interactions:** SC-004 (stale links), SC-008.

### SC-013: Administration access

**Actor:** The administrator, and people who are not.

**Preconditions:** The administrator is seb.morand@gmail.com.

**Flow:**

1. The administrator signs in → "Administration" is shown on the home page.
2. The administrator opens it → folders, members, the activity list and the creation of a folder are available.
3. The administrator acts in a folder where no member entry names them → every action is allowed.

**Postconditions:** Only the administrator reaches the administration; the administrator is never refused.

**Exceptions:**

- EXC-013a: dan.rw@example.org or carol.ro@example.org open the administration, or send a folder creation outside the interface → "Access denied." and nothing is created.
- EXC-013b: the administrator's address is typed differently (Seb.Morand@Gmail.com) → still the administrator.
- EXC-013c: the administrator is listed RO in a folder → still allowed everything.

**Interactions:** SC-014, SC-015, SC-016, SC-022.

### SC-014: Create a folder

**Actor:** The administrator.

**Preconditions:** The library holds "WCBIP Melbourne Décembre 2026", "Cardiology 2027" and "Pneumo Été".

**Flow:**

1. The administrator types "Oncology 2030" and creates the folder → it is listed on the home page, empty, without a member.

**Postconditions:** A new empty folder exists; an activity line is added.

**Exceptions:**

- EXC-014a: the name already exists without regard to case → A folder named "cardiology 2027" already exists.
- EXC-014b: the trimmed name is empty, longer than 60 characters or holds emoji or symbols → "Folder names use 1 to 60 letters, digits, spaces or hyphens."
- EXC-014c: the name is exactly 60 characters, or written in Cyrillic, Arabic or Chinese letters → accepted.

**Interactions:** SC-013, SC-019.

### SC-015: Delete a folder

**Actor:** The administrator.

**Preconditions:** "Pneumo Été" holds "Spirometry Basics" and has dan.rw@example.org as RW.

**Flow:**

1. The administrator chooses to delete "Pneumo Été" → the exact name must be retyped.
2. The administrator retypes "Pneumo Été" → the folder, its presentations with their history and its members are removed.
3. A folder named "Pneumo Été" is created again → it is empty and has no member.

**Postconditions:** The deleted folder leaves nothing behind.

**Exceptions:**

- EXC-015a: the name is retyped as "pneumo été" or left empty → "The name does not match. Nothing was deleted."
- EXC-015b: a former member acts → "Access denied."
- EXC-015c: someone is editing in the folder at that moment → their change is refused with "Access denied."; nothing is recreated.

**Interactions:** SC-017.

### SC-016: Members and roles

**Actor:** The administrator.

**Preconditions:** "Pneumo Été" has no member; "Cardiology 2027" has dan.rw@example.org RW and carol.ro@example.org RO.

**Flow:**

1. The administrator adds dan.rw@example.org with the role RW to "Pneumo Été" → Dan sees the folder at his next action.
2. The administrator changes carol.ro@example.org to RW in "Cardiology 2027" → Carol can edit from her next action.
3. The administrator removes a member → that person loses access to the folder from their next action.

**Postconditions:** Each folder has its own list; a person has at most one entry per folder.

**Exceptions:**

- EXC-016a: the address is not valid ("not-an-email", "carol@", empty, two addresses in one field) → "This is not a valid email address."
- EXC-016b: the address is already listed, in other letter case → the entry is updated, one entry remains.
- EXC-016c: the administrator's own address is listed → nothing changes for the administrator.

**Interactions:** SC-013, SC-017.

### SC-017: Access revoked mid flow

**Actor:** A person whose rights change while they work, and the administrator.

**Preconditions:** dan.rw@example.org is editing "Heart Failure Update" in "Cardiology 2027".

**Flow:**

1. The administrator removes Dan from the folder, lowers him to RO, or deletes the folder → nothing changes on Dan's screen yet.
2. Dan leaves the edited field, downloads or navigates → "Access denied." and nothing is stored.
3. The person has typed nothing unstored and the session or the right ended → the screen stays quiet until the person acts.

**Postconditions:** The change applies to the next action; Dan's unsaved text stays on screen.

**Exceptions:**

- EXC-017a: an upload is being sent → refused at its end, nothing stored.
- EXC-017b: the presenter window is open → the slides already loaded stay; a reload shows "Access denied."
- EXC-017c: the role is raised from RO to RW → the edit controls appear from the next action.
- EXC-017d: the person has typed nothing unstored → the presentation stays on screen with no notice, "Connection to the editor server lost" included; the next action that needs the library gives the sign in page or "Access denied."

**Interactions:** SC-007, SC-011, SC-015, SC-016.

### SC-018: Folder isolation

**Actor:** Any member, and the author of a hostile presentation.

**Preconditions:** Three folders with different members; "Statins Review" exists in two folders.

**Flow:**

1. Each person browses → they see only their folders, never the names, contents or members of others.
2. A presentation runs its scripts while shown → the scripts act only on the presentation itself.

**Postconditions:** No information and no power crosses a folder boundary or the viewer's identity.

**Exceptions:**

- EXC-018a: a person types the address of a presentation of a folder they cannot enter → "Access denied."
- EXC-018b: a presentation's script tries to read what the browser keeps for the library, to list another folder or to delete as the viewer → none of it works.

**Interactions:** SC-004, SC-019.

### SC-019: Hostile input

**Actor:** Any signed in person, with bad intent.

**Preconditions:** carol.ro@example.org is RO, dan.rw@example.org is RW, both in "Cardiology 2027".

**Flow:**

1. The person submits names, files and fields designed to escape the folder, inject text or exhaust the library → each is refused with the exact message of its rule and nothing is stored, created or changed.

**Postconditions:** The library, its folders, members and activity are exactly as before.

**Exceptions:**

- EXC-019a: a file name with a path such as ../../etc/passwd.html → "This file name is not allowed." (RW) or "Access denied." (RO).
- EXC-019b: a 30 MB file → "The file is larger than 25 MB." (RW) or "Access denied." (RO).
- EXC-019c: a folder name ".." → "Folder names use 1 to 60 letters, digits, spaces or hyphens."
- EXC-019d: markup in a name, an email or a check message → shown as written, never interpreted.
- EXC-019e: a page of another site, or a request with no sign of coming from the library's own pages, tries to change something with the person's valid session → "Access denied." and nothing changes.

**Interactions:** SC-005, SC-009, SC-014.

### SC-020: Initial content

**Actor:** The owner, the administrator and lamya.chrif@gmail.com.

**Preconditions:** The web library mode starts for the first time.

**Flow:**

1. The administrator opens the home page → "WCBIP Melbourne Décembre 2026" is listed.
2. Lamya signs in → she sees that folder with "Read and write" and its two presentations "Bridging the Gap" and "From Challenges to Change".

**Postconditions:** The two decks are stored exactly as supplied; the existing public static site is untouched.

**Exceptions:**

- EXC-020a: bob.nobody@gmail.com signs in → "Access denied."
- EXC-020b: Lamya opens the administration → "Access denied."
- EXC-020c: the product restarts after Lamya deleted "Bridging the Gap" → it is not recreated.

**Interactions:** SC-003, SC-004.

### SC-021: The local mode is unchanged

**Actor:** A person using the local mode on their own machine.

**Preconditions:** The local mode serves the file talk.html; the web library mode can run on the same machine.

**Flow:**

1. The person starts the local mode on talk.html → the editor opens at once, with no sign in.
2. The person edits (the change is stored by itself), presents and downloads → everything behaves as before.

**Postconditions:** The local mode is byte for byte the behavior of the previous version.

**Exceptions:**

- EXC-021a: a library page is asked from the local mode → it is not served; the local mode shows its editor only.
- EXC-021b: a request names another host name → refused as before.
- EXC-021c: a local deck holds a script reading what the browser keeps → it works as before (the isolation concerns the web library mode).

**Interactions:** SC-007.

### SC-022: Activity list

**Actor:** The administrator.

**Preconditions:** The library works; people upload, replace, delete, and the administrator manages folders and members.

**Flow:**

1. The administrator opens the activity list → the 500 latest lines are shown, newest first, each with who, when and what.

**Postconditions:** The administrator can tell who did what and when.

**Exceptions:**

- EXC-022a: a person who is not the administrator asks for it → "Access denied."
- EXC-022b: no action yet → "No activity yet."
- EXC-022c: more than 500 actions → the oldest are no longer shown.
- EXC-022d: refused attempts, sign ins and stored changes of an edit → not listed.

**Interactions:** SC-013.

### SC-023: Deployment address

**Actor:** Any person opening the product.

**Preconditions:** The web library mode runs for the owner at slides.scm-platform.org.

**Flow:**

1. A person opens slides.scm-platform.org → the sign in page is shown through a secure connection.
2. A person opens the plain, unencrypted form of the address → they are sent to the same page through the secure connection.

**Postconditions:** The product is reachable only at its address, only securely.

**Exceptions:**

- EXC-023a: the product is asked through another host name → refused, nothing of the library shown.
- EXC-023b: a direct link in plain form → the same link, secure.
- EXC-023c: the Google console lacks the return address for this address → the sign in fails with "Sign-in is unavailable. Try again later." (a deployment condition, Section 3.3).
- EXC-023d: a visitor asks whether the product is running → only "running" and the version; no file, location or presentation name.

**Interactions:** SC-001.

## 6. Functional requirements

Existing project: identifiers are FR-NEW-NNN. Requirements FR-NEW-060 to FR-NEW-065 are non functional and are written in Section 7; the whole series is numbered once. "The product" is the web library mode unless a requirement says the local mode.

### 6.1 New

#### FR-NEW-001 [EARS-U]: Nothing is public

> The web library mode SHALL show a visitor who is not signed in nothing but the sign in page, whose only action is "Sign in with Google", except the liveness answer of FR-NEW-073.

- **Business rules:** No folder name, presentation name, member, activity line, presentation file, download or export is available without signing in. The rule holds for every other address of the web library mode, not only the home page, and for the presentations' own files; an address that names no page also gives the sign in page.
- **User visible text:** "Sign in with Google"
- **Scenario:** SC-001
- **Priority:** Must

#### FR-NEW-002 [EARS-E]: Sign in with a Google account

> WHEN a visitor chooses "Sign in with Google" and completes the Google sign in with an account that is the administrator or holds a role in at least one folder THE web library mode SHALL show the home page of that account.

- **Business rules:** The account is identified by its email address, compared without regard to upper or lower case. The product never asks for a password of its own. When the visitor cancels the consent asked by Google, the sign in page is shown again, still signed out, with no message. Every sign in asks Google to show its account chooser, so that a browser already signed in to one Google account can pick another.
- **User visible text:** none.
- **Scenario:** SC-001
- **Priority:** Must

#### FR-NEW-003 [EARS-O]: Account without any right

> IF the Google account that completed the sign in is not the administrator and holds no role in any folder THEN THE web library mode SHALL show "Access denied." and no library content.

- **Business rules:** The page offers "Sign out". When the administrator later gives that account a role, the person sees the library on the next page they open, without signing in again.
- **User visible text:** "Access denied."; "Sign out"
- **Scenario:** SC-001
- **Priority:** Must

#### FR-NEW-004 [EARS-O]: Google unavailable

> IF Google cannot be reached or reports a failure during the sign in THEN THE web library mode SHALL show "Sign-in is unavailable. Try again later." on the sign in page and keep the visitor signed out.

- **Business rules:** The visitor can try again as soon as Google answers.
- **User visible text:** "Sign-in is unavailable. Try again later."
- **Scenario:** SC-001
- **Priority:** Must

#### FR-NEW-005 [EARS-S]: Session of 30 days

> WHILE less than 30 days have passed since the person signed in THE web library mode SHALL keep them signed in, including after the browser is closed and opened again.

- **Business rules:** The 30 days are counted from the sign in and are never extended by use. Signing in again starts a new period of 30 days.
- **User visible text:** none.
- **Scenario:** SC-002
- **Priority:** Must

#### FR-NEW-006 [EARS-O]: Expired session

> IF 30 days have passed since the person signed in THEN THE web library mode SHALL treat the person as signed out and show the sign in page on their next action.

- **Business rules:** The day 30 limit is exact to the minute: 29 days 23 hours 59 minutes is still signed in, 30 days 1 minute is signed out.
- **User visible text:** none.
- **Scenario:** SC-002
- **Priority:** Must

#### FR-NEW-007 [EARS-O]: Session ends during an edit

> IF the session of a person ends while a presentation is open for editing THEN THE web library mode SHALL keep the presentation and the unsaved changes on screen and, at the next automatic store of a change, show "Your session has expired. Sign in again to save." and store nothing.

- **Business rules:** The notice appears at the first automatic store after the session ended: 0.8 seconds after typing stops, or at once when the person leaves the edited field. It is the only notice: the text "Save failed:" is not put in front of it and "Connection to the editor server lost" is not shown for an ended session, however long the person waits. After the person signs in again in another window, the next automatic store in the first window stores the changes, subject to the conflict notice (FR-NEW-027). When the person has typed nothing that is not stored, FR-NEW-074 applies instead: no notice until the person acts.
- **User visible text:** "Your session has expired. Sign in again to save."
- **Scenario:** SC-002
- **Priority:** Must

#### FR-NEW-008 [EARS-E]: Sign out

> WHEN a person chooses "Sign out" THE web library mode SHALL end their session in that browser and show the sign in page.

- **Business rules:** The "Sign out" button is on the home page, the folder page and the refusal page; the administration page shows "All folders" and "Sign out"; the presentation page adds no control of its own, the person returns with the Back button of the browser. After signing out no library content is shown again in that browser until a new sign in, including through the Back button of the browser. Other browsers where the person is signed in stay signed in.
- **User visible text:** "Sign out"
- **Scenario:** SC-001
- **Priority:** Must

#### FR-NEW-009 [EARS-E]: Direct link while signed out

> WHEN a signed out visitor opens a direct link to a folder or a presentation THE web library mode SHALL show the sign in page and, after a successful sign in, show the linked page when the account has a right on it and "Access denied." when it has none.

- **Business rules:** none beyond the statement.
- **User visible text:** "Access denied."
- **Scenario:** SC-004
- **Priority:** Must

#### FR-NEW-010 [EARS-O]: One refusal for every missing or forbidden target

> IF a link points to a folder or a presentation that does not exist, no longer exists, or belongs to a folder where the person holds no role THEN THE web library mode SHALL show exactly "Access denied." and nothing else.

- **Business rules:** The page is identical in wording and content in the three cases; it shows the text "Access denied." and the "Sign out" button, nothing else: it never names the folder or the presentation and never says whether it exists. The same holds for an action refused for these reasons (storing a change, download, delete, upload). When the refusal reaches a presentation open for editing, the editor shows "Access denied." as its only notice (no "Save failed:" prefix) and keeps the unsaved changes on screen. An address of the product that names no page, asked by a signed in person, gives exactly "Access denied." with the "Sign out" button. A refused download or export shows "Access denied." as its only text, with no prefix such as "Export PPTX échoué :"; no file is received and the presentation stays on screen. When the session ended, the person gets the sign in page, unless they have unsaved text: then FR-NEW-007 applies and no download happens. Any other failure of a download or export shows the editor's usual failure notice with the operating system reason, without any file name or path, never the text of an exception.
- **User visible text:** "Access denied."
- **Scenario:** SC-004
- **Priority:** Must

#### FR-NEW-011 [EARS-S]: The administrator

> WHILE the signed in account is seb.morand@gmail.com (compared without regard to case) THE web library mode SHALL treat the person as Admin: every folder is accessible with every right of RW and the administration panel is available.

- **Business rules:** The role label shown for the administrator is "Admin". The administration panel is reached by an entry labelled "Administration" on the home page.
- **User visible text:** "Admin"; "Administration"
- **Scenario:** SC-013
- **Priority:** Must

#### FR-NEW-012 [EARS-UB]: No other administrator

> The web library mode SHALL NOT give the Admin role to any account other than seb.morand@gmail.com, whatever the member lists contain.

- **Business rules:** The roles that can be given to a member are RW and RO only.
- **User visible text:** none.
- **Scenario:** SC-013
- **Priority:** Must

#### FR-NEW-013 [EARS-O]: Administration is for the administrator only

> IF a person who is not Admin opens the administration panel or attempts any of its actions, including reading the activity list, THEN THE web library mode SHALL show "Access denied." and change nothing.

- **Business rules:** The entry "Administration" is not shown to anyone but the administrator.
- **User visible text:** "Access denied."
- **Scenario:** SC-013
- **Priority:** Must

#### FR-NEW-014 [EARS-UB]: The administrator is never refused

> The web library mode SHALL NOT refuse the administrator any action in any folder because of the content of the member lists.

- **Business rules:** This holds even when the administrator's own address is listed in a folder with the role RO.
- **User visible text:** none.
- **Scenario:** SC-013
- **Priority:** Must

#### FR-NEW-015 [EARS-E]: Home page: the accessible folders

> WHEN a signed in person opens the home page THE web library mode SHALL list the folders that person can access, all folders for the administrator, in alphabetical order without regard to case or accents, each with the person's role.

- **Business rules:** Role labels: "Admin", "Read and write" (RW), "Read only" (RO). Order: accents removed, case ignored, compared by character code; so digits come before Latin letters, and Latin letters before other alphabets. Folder names are unique, so the order is never ambiguous.
- **User visible text:** "Admin"; "Read and write"; "Read only"
- **Scenario:** SC-003
- **Priority:** Must

#### FR-NEW-016 [EARS-O]: Empty home page

> IF the home page has no folder to list THEN THE web library mode SHALL show "You have no access to any folder yet."

- **Business rules:** This happens to the administrator when no folder exists. A person who holds no role anywhere never reaches the home page: they see "Access denied." (FR-NEW-003).
- **User visible text:** "You have no access to any folder yet."
- **Scenario:** SC-003
- **Priority:** Must

#### FR-NEW-017 [EARS-O]: Library unreadable

> IF the stored library cannot be read THEN THE web library mode SHALL show "The library is unavailable. Try again later." and no partial content.

- **Business rules:** The library works again, with all its content, as soon as it can be read.
- **User visible text:** "The library is unavailable. Try again later."
- **Scenario:** SC-003
- **Priority:** Should

#### FR-NEW-018 [EARS-E]: Folder page: the presentations

> WHEN a person opens a folder they can access THE web library mode SHALL list its presentations, each with its name, its last modified date and its size, the most recently modified first, and offer a way back to the home page.

- **Business rules:** Presentations with the same last modified time (compared to the minute) are ordered by the rule of FR-NEW-015 (accents removed, case ignored, by character code), then by exact name by character code; the order is the same each time it is displayed while nothing changes. Date and time are shown in the person's time zone, on a 24 hour clock, day without a leading zero, minutes truncated (seconds dropped), months written with their first three letters (Jan to Dec): "16 Nov 2026 14:32", "5 Nov 2026 09:05". Size: the unit is chosen from the exact number of bytes: 1 byte reads "1 byte", below 1 024 bytes "N bytes", from 1 024 to 1 048 575 bytes in KB (1 KB is 1 024 bytes), from 1 048 576 bytes in MB (1 MB is 1 048 576 bytes). KB and MB show one decimal, rounded half up from the exact value, so 1 048 575 bytes reads "1024.0 KB". The name is shown without the ".html" ending.
- **User visible text:** none.
- **Scenario:** SC-004
- **Priority:** Must

#### FR-NEW-019 [EARS-O]: Empty folder

> IF the folder has no presentation THEN THE web library mode SHALL show "This folder has no presentations yet."

- **Business rules:** none beyond the statement.
- **User visible text:** "This folder has no presentations yet."
- **Scenario:** SC-004
- **Priority:** Must

#### FR-NEW-020 [EARS-UB]: No leak between folders

> The web library mode SHALL NOT reveal to a person the name, content, existence or member list of a folder where they hold no role, nor the email address of any other person.

- **Business rules:** The administrator is excepted. The rule covers lists, messages, prompts and the activity list.
- **User visible text:** none.
- **Scenario:** SC-018
- **Priority:** Must

#### FR-NEW-021 [EARS-UB]: Roles do not travel

> The web library mode SHALL NOT let a role held in one folder grant any right in another folder.

- **Business rules:** none beyond the statement.
- **User visible text:** none.
- **Scenario:** SC-018
- **Priority:** Must

#### FR-NEW-022 [EARS-S]: RO: view, present, download

> WHILE a person holds RO in a folder THE web library mode SHALL let them open its presentations, show them full screen, open the presenter window with the speaker notes, and download each presentation as HTML and as PPTX.

- **Business rules:** The downloaded HTML is the stored presentation unchanged, under its own name. Only the HTML and the PPTX downloads are offered; any other export format, DOCX included, is refused with "Access denied." for everyone.
- **User visible text:** none.
- **Scenario:** SC-005
- **Priority:** Must

#### FR-NEW-023 [EARS-UB]: RO cannot change anything

> The web library mode SHALL NOT let a person who holds only RO in a folder edit, upload or delete in it: the controls are absent and any attempt made outside the interface, including the storing of a change, is refused with "Access denied." and has no effect.

- **Business rules:** Absent for RO: the Upload and Delete controls, edit mode, undo, redo, notes editing, requests, slide and block actions. The key E does nothing. Reading the queued requests and the AI suggestions of a presentation is refused with "Access denied." for a person who holds only RO.
- **User visible text:** "Access denied."
- **Scenario:** SC-005
- **Priority:** Must

#### FR-NEW-024 [EARS-S]: RW: edit, upload, delete

> WHILE a person holds RW in a folder, or is Admin, THE web library mode SHALL additionally let them edit its presentations with every editor option (changes are stored by themselves), upload and delete in that folder.

- **Business rules:** The Upload control is on the folder page; Delete is on each presentation row. Any RW member can change, replace or delete any presentation of the folder, whoever uploaded it.
- **User visible text:** "Upload"; "Delete"
- **Scenario:** SC-006
- **Priority:** Must

#### FR-NEW-025 [EARS-U]: Same editor as the local mode

> The web library mode SHALL give a person who can edit a presentation every option of the editor of the local mode, working as it does there.

- **Business rules:** Options: edit mode, undo, redo, notes, presenter window, full screen, pointer, requests, Ask AI, HTML and PPTX download, keyboard shortcuts, help. A person who holds only RO gets the same screen without any control that changes the presentation (FR-NEW-023).
- **User visible text:** none.
- **Scenario:** SC-007
- **Priority:** Must

#### FR-NEW-026 [EARS-E]: A stored change keeps the previous version

> WHEN a person with RW leaves a field they changed THE web library mode SHALL store the edited version in its folder at once and keep the previous version in the history of the presentation.

- **Business rules:** The same storing happens 0.8 seconds after typing stops (FR-NEW-066). Stored changes are not recorded in the activity list (FR-NEW-051).
- **User visible text:** none.
- **Scenario:** SC-007
- **Priority:** Must

#### FR-NEW-027 [EARS-E]: Conflicting edits

> WHEN a person leaves a field in which they typed text not yet stored, and someone else changed the stored presentation after their screen last showed it, THE web library mode SHALL show the conflict notice with "Keep mine" and "Reload" and store nothing until they choose.

- **Business rules:** Notice text, as in the local mode: "The file changed on disk. Reload to see the changes, or keep your version." "Keep mine" stores the person's version and keeps the other version in the history; "Reload" shows the stored version and drops the unsaved changes. The notice arises only for a person who has unsaved typed text. A person with no unsaved text sees the other person's stored version replace their screen within 2 seconds, with no notice, as in the local mode.
- **User visible text:** "The file changed on disk. Reload to see the changes, or keep your version."; "Keep mine"; "Reload"
- **Scenario:** SC-008
- **Priority:** Must

#### FR-NEW-028 [EARS-E]: Upload a presentation

> WHEN a person with RW uploads a file that passes every upload check THE web library mode SHALL add it to the folder as a presentation and show "Uploaded <name>."

- **Business rules:** <name> is the file name without ".html". The new presentation is listed first, with the current date and time. Checks run in this order and the first failure is the only message: right to upload, extension, file name, size, validity as a presentation, name collision.
- **User visible text:** "Uploaded <name>."
- **Scenario:** SC-009
- **Priority:** Must

#### FR-NEW-029 [EARS-O]: Only .html files

> IF the chosen file name does not end with ".html", whatever the case of the letters, THEN THE web library mode SHALL show "Only .html files are accepted." and store nothing.

- **Business rules:** ".HTML" and ".Html" are accepted.
- **User visible text:** "Only .html files are accepted."
- **Scenario:** SC-009
- **Priority:** Must

#### FR-NEW-030 [EARS-O]: Size limit of 25 MB

> IF the chosen file is larger than 26 214 400 bytes (25 MB) THEN THE web library mode SHALL show "The file is larger than 25 MB." and store nothing.

- **Business rules:** Exactly 26 214 400 bytes is accepted, 26 214 401 bytes is refused.
- **User visible text:** "The file is larger than 25 MB."
- **Scenario:** SC-009
- **Priority:** Must

#### FR-NEW-031 [EARS-O]: Valid presentation

> IF the chosen file is not a valid presentation THEN THE web library mode SHALL show "This file is not a valid presentation: <first problem>." and store nothing.

- **Business rules:** Valid means: valid UTF-8 text, declared as a presentation, at least 1 slide, and no error of any kind reported by the editor's own checks (its structure rules and its charter rules). Warnings of those checks (for example a picture loaded from another site) never block and are never the first problem. <first problem> is the first error in the order the editor lists its findings (whole file first, then slide by slide, then by check code), its message only, without the slide identifier. Verbatim editor examples: "missing attribute data-title"; "TOTAL is 5 but the file has 2 slides"; "expected id \"slide-0\" but found \"a\""; "slide has an image and no source line". A file that is not valid UTF-8 text reads "the file is not valid UTF-8 text" (checked first); an empty file, or a file that is not declared as a presentation, reads "the file is not declared as a presentation"; a declared presentation without slide reads "the file has no slide". No message carries a location: no byte position, line number or server path.
- **User visible text:** "This file is not a valid presentation: <first problem>."
- **Scenario:** SC-009
- **Priority:** Must

#### FR-NEW-032 [EARS-O]: Allowed file names

> IF the name of the chosen file contains a path, starts with a dot, starts or ends with a space, is made only of spaces, exceeds 100 characters before ".html", or contains a character other than letters, digits, spaces, accented letters and . _ - ( ) ' THEN THE web library mode SHALL show "This file name is not allowed." and store nothing.

- **Business rules:** Letters are the Latin-script letters, with or without accents, including ł, ø, œ and ß; the apostrophe is the straight one (') only. Dots inside the name are allowed ("Report.v2.final.html"). The name is first brought to its composed form (an "e" followed by an accent mark counts as the single letter "é") before it is checked, compared or stored. The 100 characters are counted on that composed form, without ".html": 100 are allowed, 101 are refused.
- **User visible text:** "This file name is not allowed."
- **Scenario:** SC-009
- **Priority:** Must

#### FR-NEW-033 [EARS-O]: Name collision

> IF a presentation with the same name already exists in the folder and the file passed every other check THEN THE web library mode SHALL ask: A presentation named "<name>" already exists. Replace it?

- **Business rules:** Names are compared without regard to case and without the ".html" ending, on their composed form; accents make names different. <name> is the name of the existing presentation. The buttons are "Replace" and "Cancel". A validation message always wins over this question. Choosing "Cancel" changes nothing: not the presentation, not its history, not the list, not the activity list.
- **User visible text:** A presentation named "<name>" already exists. Replace it?; "Replace"; "Cancel"
- **Scenario:** SC-010
- **Priority:** Must

#### FR-NEW-034 [EARS-E]: Replace

> WHEN the person confirms "Replace" THE web library mode SHALL replace the presentation by the uploaded file in one step, keep the previous version in its history and show "Uploaded <name>."

- **Business rules:** The existing presentation keeps its name. A replacement keeps the requests queued for the presentation and its AI suggestions.
- **User visible text:** "Uploaded <name>."
- **Scenario:** SC-010
- **Priority:** Must

#### FR-NEW-035 [EARS-S]: Upload progress

> WHILE a file is being sent THE web library mode SHALL show the file name and the progress of the upload.

- **Business rules:** The progress text is "<file name> <percent>%", for example "Big Deck.html 42%", where the percent is a whole number rounded down; it grows until the upload ends and never reads 100% before the upload is complete.
- **User visible text:** "<file name> <percent>%"
- **Scenario:** SC-011
- **Priority:** Must

#### FR-NEW-036 [EARS-O]: Interrupted upload

> IF an upload is interrupted before it completes THEN THE web library mode SHALL leave no partial presentation and leave every existing presentation as it was.

- **Business rules:** Interruptions: connection lost, page closed or refreshed, browser closed.
- **User visible text:** none.
- **Scenario:** SC-011
- **Priority:** Must

#### FR-NEW-037 [EARS-E]: Double submit

> WHEN the same upload is submitted twice in a row THE web library mode SHALL create one presentation.

- **Business rules:** A second submission made while the first is still in progress is ignored. Two people uploading the same new name at the same moment leave one presentation, never two: the upload that finishes second is treated as a name collision and meets the question of FR-NEW-033.
- **User visible text:** none.
- **Scenario:** SC-011
- **Priority:** Must

#### FR-NEW-038 [EARS-O]: Upload cannot be stored

> IF the library cannot store an uploaded file THEN THE web library mode SHALL show "The upload failed. Nothing was changed." and change nothing.

- **Business rules:** Example causes: storage full.
- **User visible text:** "The upload failed. Nothing was changed."
- **Scenario:** SC-011
- **Priority:** Should

#### FR-NEW-039 [EARS-E]: Delete a presentation

> WHEN a person with RW chooses to delete a presentation THE web library mode SHALL ask: Delete "<name>"? This cannot be undone. and, on confirmation, remove the presentation and its history for good.

- **Business rules:** There is no trash and no way back. The buttons are "Delete" and "Cancel"; "Cancel" changes nothing. The requests queued for the presentation and the AI suggestions shown for it are removed with it: a presentation uploaded again under the same name starts with an empty Requests list and no suggestion.
- **User visible text:** Delete "<name>"? This cannot be undone.; "Delete"; "Cancel"
- **Scenario:** SC-012
- **Priority:** Must

#### FR-NEW-040 [EARS-E]: Create a folder

> WHEN the administrator creates a folder with a valid name THE web library mode SHALL add an empty folder without any member and list it on the home page.

- **Business rules:** The name is trimmed of leading and trailing spaces before it is checked and kept. The name has 1 to 60 characters: letters of any alphabet, digits, spaces, hyphens.
- **User visible text:** none.
- **Scenario:** SC-014
- **Priority:** Must

#### FR-NEW-041 [EARS-O]: Folder name rules

> IF the trimmed folder name is empty, longer than 60 characters, or contains anything other than letters of any alphabet, digits, spaces and hyphens THEN THE web library mode SHALL show "Folder names use 1 to 60 letters, digits, spaces or hyphens." and create nothing.

- **Business rules:** Letters are the letters of any alphabet, with their combining marks; digits are the decimal digits; the hyphen is the plain hyphen. Emoji, dots, slashes, underscores and other symbols are refused. The name is brought to its composed form first; the length of 1 to 60 is counted on that form.
- **User visible text:** "Folder names use 1 to 60 letters, digits, spaces or hyphens."
- **Scenario:** SC-014
- **Priority:** Must

#### FR-NEW-042 [EARS-O]: Unique folder names

> IF a folder with the same name, without regard to case, already exists THEN THE web library mode SHALL show A folder named "<name>" already exists. and create nothing.

- **Business rules:** <name> is the trimmed name the administrator typed. Names are compared without regard to case and on their composed form; names that differ by an accent are different names.
- **User visible text:** "A folder named "<name>" already exists."
- **Scenario:** SC-014
- **Priority:** Must

#### FR-NEW-043 [EARS-E]: Delete a folder

> WHEN the administrator deletes a folder after retyping its exact name THE web library mode SHALL remove the folder, all its presentations with their history, and all its members.

- **Business rules:** The retyped name is first brought to its composed form, then compared with the folder name character by character, case sensitive. A folder created later with the same name is empty and has no member. Deleting a folder removes the requests and AI suggestions of all its presentations too: none returns when a folder of the same name is created again.
- **User visible text:** none.
- **Scenario:** SC-015
- **Priority:** Must

#### FR-NEW-044 [EARS-O]: Wrong name retyped

> IF the retyped name differs from the folder name in any character, including case, THEN THE web library mode SHALL show "The name does not match. Nothing was deleted." and delete nothing.

- **Business rules:** none beyond the statement.
- **User visible text:** "The name does not match. Nothing was deleted."
- **Scenario:** SC-015
- **Priority:** Must

#### FR-NEW-045 [EARS-E]: Add a member

> WHEN the administrator adds an email address with the role RW or RO to a folder THE web library mode SHALL give that person that role in that folder.

- **Business rules:** The address is trimmed, stored and shown in lower case. The roles that can be chosen are "Read and write" and "Read only"; any other role is refused with "This is not a valid role." and nothing changes. An address already listed in the folder, without regard to case, is never added twice: with the same role nothing changes and no activity line is added; with the other role the entry is updated and the activity line reads Changed <email> to <role> in "<folder>". The role applies from the person's next action.
- **User visible text:** "This is not a valid role."
- **Scenario:** SC-016
- **Priority:** Must

#### FR-NEW-046 [EARS-O]: Invalid email address

> IF the text typed as an email address is not one valid address THEN THE web library mode SHALL show "This is not a valid email address." and change nothing.

- **Business rules:** Valid means one address of the form local@domain: the local part has letters, digits and . _ % + - ; the domain has letters, digits and hyphens and at least one dot; no spaces or commas. Two addresses in one field are refused.
- **User visible text:** "This is not a valid email address."
- **Scenario:** SC-016
- **Priority:** Must

#### FR-NEW-047 [EARS-E]: Change a role, remove a member

> WHEN the administrator changes the role of a member or removes the member THE web library mode SHALL apply the change to that folder only.

- **Business rules:** The same person's roles in other folders are untouched.
- **User visible text:** none.
- **Scenario:** SC-016
- **Priority:** Must

#### FR-NEW-048 [EARS-E]: Changed rights apply on the next action

> WHEN the administrator removes a person, changes their role, or deletes the folder THE web library mode SHALL apply the change to that person's next action in that folder, refusing it with "Access denied." when it is no longer allowed, and storing nothing.

- **Business rules:** Content already displayed stays on screen; no new content loads. A presentation open for editing keeps its unsaved changes on screen; the refusal appears at the next automatic store as the editor's only notice "Access denied." (no "Save failed:" prefix). An upload still being sent when the right is removed is refused at its end and stores nothing. A raised role (RO to RW) also applies from the next action. When the person has typed nothing that is not stored, FR-NEW-074 applies: no notice until the person acts.
- **User visible text:** "Access denied."
- **Scenario:** SC-017
- **Priority:** Must

#### FR-NEW-049 [EARS-E]: Record successful actions

> WHEN an upload, a replacement or a deletion of a presentation, the creation or deletion of a folder, or the adding, changing or removing of a member succeeds THE web library mode SHALL add a line to the activity list with who did it, when, and what.

- **Business rules:** Line texts: Uploaded "<name>" in "<folder>"; Replaced "<name>" in "<folder>"; Deleted "<name>" from "<folder>"; Created folder "<folder>"; Deleted folder "<folder>"; Added <email> as RW to "<folder>" (or RO); Changed <email> to RO in "<folder>" (or RW); Removed <email> from "<folder>". Who is the email address of the person; when is shown as on the folder page. Who is the email address of the person in lower case, whatever letter case Google returned.
- **User visible text:** none.
- **Scenario:** SC-022
- **Priority:** Must

#### FR-NEW-050 [EARS-E]: Show the activity list

> WHEN the administrator opens the activity list THE web library mode SHALL show the 500 latest lines, the newest first.

- **Business rules:** The 501st and older lines are no longer shown. The initial content (FR-NEW-054) is not recorded. When there is no line the list shows "No activity yet."
- **User visible text:** "No activity yet."
- **Scenario:** SC-022
- **Priority:** Must

#### FR-NEW-051 [EARS-UB]: Refusals, sign ins and stored changes are not recorded

> The web library mode SHALL NOT record in the activity list an attempt that was refused, a sign in, or a stored change.

- **Business rules:** none beyond the statement.
- **User visible text:** none.
- **Scenario:** SC-022
- **Priority:** Must

#### FR-NEW-052 [EARS-UB]: A presentation's scripts have no power over the viewer

> The web library mode SHALL NOT let a script contained in a presentation read what the browser keeps for the library, act with the identity of the person viewing it, or reach another folder.

- **Business rules:** The scripts still run for the presentation itself (navigation, animations), as in the local mode.
- **User visible text:** none.
- **Scenario:** SC-018
- **Priority:** Must

#### FR-NEW-053 [EARS-UB]: Text is never markup

> The web library mode SHALL NOT interpret as markup any text a person or a file supplies (names, email addresses, check messages): it is shown exactly as written.

- **Business rules:** none beyond the statement.
- **User visible text:** none.
- **Scenario:** SC-019
- **Priority:** Must

#### FR-NEW-054 [EARS-E]: Initial content

> WHEN the web library mode starts for the first time, with no library yet, THE web library mode SHALL create the folder "WCBIP Melbourne Décembre 2026" holding the presentations "From Challenges to Change" and "Bridging the Gap", unchanged, with lamya.chrif@gmail.com as RW.

- **Business rules:** The initial content is created once, when the library is first created, and that fact is remembered: later starts neither add nor reset anything, even when every folder was deleted. The two presentations keep the modified time of the supplied files (15 Nov 2026 19:57 UTC). The existing public static site for these two decks is not touched.
- **User visible text:** none.
- **Scenario:** SC-020
- **Priority:** Must

#### FR-NEW-055 [EARS-U]: The local mode is unchanged

> The local mode SHALL keep every behavior it had before this increment.

- **Business rules:** One local file at a time, the same editor, the same options, the same address rules. The web library mode running on the same machine changes nothing in it.
- **User visible text:** none.
- **Scenario:** SC-021
- **Priority:** Must

#### FR-NEW-056 [EARS-UB]: No sign in in the local mode

> The local mode SHALL NOT ask for a sign in or show any library page.

- **Business rules:** none beyond the statement.
- **User visible text:** none.
- **Scenario:** SC-021
- **Priority:** Must

#### FR-NEW-057 [EARS-U]: Reached at its address, securely

> The web library mode SHALL be reached at the address slides.scm-platform.org through a secure connection.

- **Business rules:** The address is imposed by the owner (Section 3.3).
- **User visible text:** none.
- **Scenario:** SC-023
- **Priority:** Must

#### FR-NEW-058 [EARS-E]: Plain address redirected

> WHEN a person opens the address with a plain, unencrypted connection THE web library mode SHALL send them to the same page through the secure connection.

- **Business rules:** The page asked for, including a direct link, is kept.
- **User visible text:** none.
- **Scenario:** SC-023
- **Priority:** Must

#### FR-NEW-059 [EARS-O]: Other host names refused

> IF a request reaches the product through a host name other than the address of the mode in use THEN THE product SHALL refuse it and show nothing of the library, except the liveness answer of FR-NEW-073.

- **Business rules:** In the local mode the accepted names stay the local ones; in the web library mode the accepted name is slides.scm-platform.org. The liveness answer is the only exception: it is given whatever host name the request carries, loopback included, and shows nothing of the library.
- **User visible text:** none.
- **Scenario:** SC-023
- **Priority:** Must

#### FR-NEW-066 [EARS-S]: Changes are stored by themselves

> WHILE a person with RW has a presentation open for editing THE web library mode SHALL store each change 0.8 seconds after the person stops typing, and at once when the person leaves the edited field, and SHALL offer no Save control.

- **Business rules:** As in the local mode there is no Save control and no Save key. A slide or block action (insert, delete, move) is stored 0.6 seconds after the action. When storing fails the editor shows its usual failure notice with the reason and keeps the change on screen. A stored change is accepted up to 52 428 800 bytes, as in the local mode; above that the editor's usual failure notice is shown.
- **User visible text:** none.
- **Scenario:** SC-007
- **Priority:** Must

#### FR-NEW-067 [EARS-U]: Names of the controls the mode adds

> The web library mode SHALL name the controls and prompts it adds exactly as listed in the business rules.

- **Business rules:** Folder page: "All folders" (back to the home page). Administration: sections "Folders" and "Activity"; the field "Folder name" with the button "Create folder"; per folder the button "Delete folder". Deleting a folder: the prompt "Type the folder name to confirm." with the buttons "Delete folder" and "Cancel". Per folder a section "Members": the field "Email address", the chooser "Role" offering "Read and write" and "Read only", the button "Add member"; per member a role chooser and the button "Remove". Upload progress text: "<file name> <percent>%", percent a whole number rounded down. The administration page shows "All folders" and "Sign out". Administration order: folders as on the home page (FR-NEW-015); the members of a folder alphabetical by email address, by character code.
- **User visible text:** "All folders"; "Folders"; "Activity"; "Folder name"; "Create folder"; "Delete folder"; "Type the folder name to confirm."; "Cancel"; "Members"; "Email address"; "Role"; "Read and write"; "Read only"; "Add member"; "Remove"; "Sign out"
- **Scenario:** SC-013
- **Priority:** Must

#### FR-NEW-068 [EARS-O]: Unverified Google address

> IF Google does not state that the email address of the account is verified THEN THE web library mode SHALL show "Sign-in is unavailable. Try again later." and keep the visitor signed out.

- **Business rules:** The message is the same whether or not the address is listed anywhere, so that it reveals nothing about members. A verified address is accepted whatever its letter case.
- **User visible text:** "Sign-in is unavailable. Try again later."
- **Scenario:** SC-001
- **Priority:** Must

#### FR-NEW-069 [EARS-E]: Destination after sign in

> WHEN a visitor signs in through a link that carries a destination THE web library mode SHALL send them to that destination only when it is a page of slides.scm-platform.org, and to the home page otherwise.

- **Business rules:** A destination naming another site, written with another scheme, or starting with two slashes or a backslash is ignored. A destination of the product on which the account has no right gives "Access denied." (FR-NEW-009).
- **User visible text:** none.
- **Scenario:** SC-001
- **Priority:** Must

#### FR-NEW-070 [EARS-O]: A request from another site is refused

> IF a request that changes the library comes from a page of another site, or carries no sign that it comes from the library's own pages, THEN THE web library mode SHALL refuse it with "Access denied." and change nothing, even when it carries a valid session.

- **Business rules:** The rule covers every change: storing a change, upload, delete, folder, member and request actions. A request made by the library's own pages, on slides.scm-platform.org, is never affected.
- **User visible text:** "Access denied."
- **Scenario:** SC-019
- **Priority:** Must

#### FR-NEW-071 [EARS-O]: A sign in answer that this browser did not start

> IF a sign in answer does not belong to a sign in that this browser started, or was already used, THEN THE web library mode SHALL show "Sign-in is unavailable. Try again later." and keep the visitor signed out.

- **Business rules:** The visitor can start a new sign in at once.
- **User visible text:** "Sign-in is unavailable. Try again later."
- **Scenario:** SC-001
- **Priority:** Must

#### FR-NEW-072 [EARS-UB]: No use of a session after sign out, no framing

> The web library mode SHALL NOT accept a session after its person signed out, and SHALL NOT let any library page be shown inside a page of another site.

- **Business rules:** A copy of the credentials of a session made before "Sign out" is refused after it, as for a visitor who is not signed in. The refusal of framing applies to every page, including the sign in page.
- **User visible text:** none.
- **Scenario:** SC-001
- **Priority:** Must

#### FR-NEW-073 [EARS-U]: A liveness answer that reveals nothing

> The web library mode SHALL answer the check "is the product running" without sign in with only that fact and the product's version, and SHALL show the status of a presentation (its change marker) only to a person who has a right on it, without any storage location.

- **Business rules:** The answer carries no file location, process number or presentation name. The operator's health check of the packaged product keeps working without sign in. A person with no right on a presentation, or a visitor, asking its status gets "Access denied." or the sign in page, never a status. The answer is the same whatever host name the request carries, loopback included.
- **User visible text:** "Access denied."
- **Scenario:** SC-023
- **Priority:** Must

#### FR-NEW-074 [EARS-O]: A quiet screen until the person acts

> IF the session of a person ended, or their right was removed, while a presentation is open and nothing they typed is unstored, THEN THE web library mode SHALL keep the presentation on screen and show no notice, including "Connection to the editor server lost", until the person acts.

- **Business rules:** The next action that needs the library gives the sign in page, or "Access denied." when the right was removed. Moving between slides inside the presentation is not such an action.
- **User visible text:** "Access denied."
- **Scenario:** SC-017
- **Priority:** Must

### 6.2 Modified

None. Every existing requirement of the local mode stays as it is. The deviations that apply to the web library mode only (no sign in in SPEC-0001 Section 7, the accepted host names of SPEC-0005/BR-002) are stated in Section 2.2 and are new requirements here, not edits of those specs.

### 6.3 Removed

None.

## 7. Non functional requirements (user observable)

### 7.1 Performance

#### FR-NEW-060 [EARS-S]: Lists stay fast

> WHILE the library holds 200 folders, or a folder holds 100 presentations, THE web library mode SHALL display that list within 2 seconds on a 50 megabit per second connection.

- **Business rules:** Every entry stays reachable. The 2 seconds are counted from the person's request until the whole list can be read and used.
- **User visible text:** none.
- **Scenario:** SC-003
- **Priority:** Must

#### FR-NEW-061 [EARS-E]: A 25 MB upload completes

> WHEN a person uploads a valid file of 25 MB THE web library mode SHALL complete the upload within 2 minutes on a 10 megabit per second connection and finish with "Uploaded <name>."

- **Business rules:** none beyond the statement.
- **User visible text:** "Uploaded <name>."
- **Scenario:** SC-011
- **Priority:** Must

### 7.2 Security and access

Carried by: FR-NEW-001 (Nothing is public), FR-NEW-003 (Account without any right), FR-NEW-068 (Unverified Google address), FR-NEW-069 (Destination after sign in), FR-NEW-070 (A request from another site is refused), FR-NEW-071 (A sign in answer that this browser did not start), FR-NEW-072 (No use of a session after sign out, no framing), FR-NEW-073 (A liveness answer that reveals nothing), FR-NEW-074 (A quiet screen until the person acts), FR-NEW-010 (One refusal for every missing or forbidden target), FR-NEW-011 (The administrator), FR-NEW-012 (No other administrator), FR-NEW-013 (Administration is for the administrator only), FR-NEW-020 (No leak between folders), FR-NEW-021 (Roles do not travel), FR-NEW-023 (RO cannot change anything), FR-NEW-048 (Changed rights apply on the next action), FR-NEW-052 (A presentation's scripts have no power over the viewer), FR-NEW-053 (Text is never markup), FR-NEW-057 (Reached at its address, securely), FR-NEW-059 (Other host names refused). Measurable by an actor: a visitor sees only the sign in action; a person without a role gets the identical message "Access denied." for a missing and a forbidden target; no refused attempt changes anything another member or the administrator can observe.

### 7.3 Privacy and compliance

Carried by: FR-NEW-020 (No leak between folders), FR-NEW-050 (Show the activity list), FR-NEW-013 (Administration is for the administrator only). Measurable by an actor: no member sees the email address of another person or the name of a folder where they hold no role; only the administrator reads the activity list; nothing is public, including presentation files and downloads.

### 7.4 Usability and accessibility

#### FR-NEW-064 [EARS-U]: Keyboard and labels

> The web library mode SHALL make every action of the library pages reachable with the keyboard alone and give every control a visible label or an accessible name.

- **Business rules:** none beyond the statement.
- **User visible text:** none.
- **Scenario:** SC-003
- **Priority:** Should

#### FR-NEW-065 [EARS-U]: English for what the mode adds

> The web library mode SHALL show every page, message and control that it adds in English, and SHALL show the editor and the presentations with the texts they have in the local mode.

- **Business rules:** Added by the mode, in English: the sign in page, the home page, the folder page, upload, delete, the administration, the activity list and every refusal. Kept as in the local mode, not translated: the editor's toolbar labels (for example "Édition", "Annuler", "Rétablir", "Mode présentation plein écran", "Présenter avec le pointeur", "Vue présentateur", "Télécharger en PPTX", "Télécharger le fichier HTML", "Raccourcis clavier", and in English "Requests", "Ask AI", "Notes"), the editor's own notices and the text of the presentations.
- **User visible text:** none.
- **Scenario:** SC-003
- **Priority:** Must

### 7.5 Reliability

#### FR-NEW-062 [EARS-U]: Nothing is lost on restart

> The web library mode SHALL keep every folder, presentation, history, member, activity line and signed in session after the product is restarted.

- **Business rules:** A person signed in before a restart is still signed in after it, for the rest of the 30 days counted from their sign in.
- **User visible text:** none.
- **Scenario:** SC-003
- **Priority:** Must

#### FR-NEW-063 [EARS-U]: Never half a presentation

> The web library mode SHALL show a person, at any instant, either the complete previous or the complete new version of a presentation that is being saved or replaced, never a mix and never an empty file.

- **Business rules:** none beyond the statement.
- **User visible text:** none.
- **Scenario:** SC-010
- **Priority:** Must

Also carried by: FR-NEW-036 (Interrupted upload), FR-NEW-037 (Double submit), FR-NEW-038 (Upload cannot be stored), FR-NEW-017 (Library unreadable).

### 7.6 Operability

Carried by: FR-NEW-049 (Record successful actions), FR-NEW-050 (Show the activity list), FR-NEW-051 (Refusals, sign ins and stored changes are not recorded). Measurable by the operator: for any successful upload, replacement, deletion, folder or member change, the administrator can read who did it, when, and what, among the 500 latest; an operator can list and restore the earlier versions of a presentation through the existing history capability (SPEC-0009).

## 8. Edge cases

| Category | Case | Expected behavior | Test |
|---|---|---|---|
| Empty states | First start holds only the initial content | Lists and messages as specified; "No activity yet." for the activity list | E2E-128, E2E-143 |
| Empty states | The administrator and no folder | "You have no access to any folder yet." | E2E-015 |
| Empty states | A folder without presentation, or emptied by deletions | "This folder has no presentations yet." | E2E-022, E2E-083 |
| Empty states | A recreated folder | Empty, without any member | E2E-103 |
| Empty states | A signed in account that holds no role anywhere | "Access denied." and no content | E2E-002, E2E-129 |
| Empty states | Every folder deleted, then a restart | The library stays empty: the initial content is not created again | E2E-159 |
| Boundary values | 25 MB: exactly 26 214 400 bytes and one byte more | Accepted; "The file is larger than 25 MB." | E2E-062, E2E-056 |
| Boundary values | Folder name of 1, 60 and 61 characters; blank name | 1 and 60 accepted; 61 and blank refused with the rule message | E2E-096, E2E-094, E2E-093 |
| Boundary values | 30 days less 1 minute and 30 days plus 1 minute | Signed in; signed out | E2E-012, E2E-008, E2E-009 |
| Boundary values | 500 and 501 activity lines | The 500 latest are shown | E2E-142 |
| Boundary values | File names of 100 and 101 characters, spaces at the ends, only spaces; folder names of 60 and 61 characters counted after the composed form | 100 and 60 accepted; the others refused with the rule message | E2E-162, E2E-163 |
| Boundary values | Sizes of 1 byte, 1 075, 1 076, 1 048 575 bytes; times at 09:05:59 and 23:59:59 | "1 byte", "1.0 KB", "1.1 KB", "1024.0 KB"; minutes truncated on a 24 hour clock | E2E-028, E2E-164 |
| Boundary values | Progress at 33.87 and 99.998 percent | Whole numbers rounded down: 33% and 99% | E2E-158 |
| Boundary values | 200 folders, 100 presentations, 0 slides, size units | Lists within 2 seconds; "the file has no slide"; "900 bytes", "1.0 KB", "1.0 MB" | E2E-017, E2E-104, E2E-058, E2E-028 |
| Concurrent actions | Two people change the same presentation | Conflict notice for the second; "Keep mine" or "Reload" | E2E-049, E2E-050, E2E-051, E2E-048 |
| Concurrent actions | A replacement or a deletion while someone edits | Conflict notice; "Access denied." without recreation | E2E-052, E2E-053 |
| Concurrent actions | Double submit; two uploads of the same new name | One presentation | E2E-075, E2E-070 |
| Concurrent actions | A right removed while an upload is sent | Refused at the end, nothing stored | E2E-120 |
| Concurrent actions | Both people leave their field in the same second; a change after signing in again that meets another person's change | One version stored, conflict notice for the other | E2E-189, E2E-188 |
| Slow or lost connectivity | A link of 10 megabits per second with 25 MB | Completes within 2 minutes with visible progress | E2E-076, E2E-071 |
| Slow or lost connectivity | The connection drops midway, for a new file and for a replacement | No partial presentation; the previous version intact | E2E-072, E2E-073 |
| Slow or lost connectivity | Google does not answer | "Sign-in is unavailable. Try again later." | E2E-003 |
| Access states | Signed out, expired, each role, revoked mid flow | Sign in page; sign in page; role specific controls; "Access denied." on the next action | E2E-004, E2E-009, E2E-032, E2E-036, E2E-084, E2E-117, E2E-118, E2E-116 |
| Access states | A session that ends in the middle of an edit | Content stays; "Your session has expired. Sign in again to save." | E2E-010, E2E-013 |
| Access states | The product restarts while people are signed in; a session that ended 10 seconds ago | Still signed in with the remaining days; one notice only, soon, and no lost connection notice | E2E-166, E2E-167, E2E-170 |
| Access states | Session ended or right removed with nothing unstored; slide navigation | Quiet screen until the person acts; then the sign in page or "Access denied." | E2E-173, E2E-177, E2E-178 |
| Access states | Session credentials copied before Sign out; Sign out in another tab | Refused afterwards; the other tab shows the sign in page | E2E-SEC-020, E2E-185 |
| Access states | A liveness check without sign in; a status of a presentation without a right | Only running and version; sign in page or "Access denied." | E2E-186, E2E-187, E2E-SEC-021 |
| Access states | An unverified Google address; a sign in link with a destination on another site | Sign-in unavailable message; the home page of the product | E2E-171, E2E-172, E2E-SEC-015, E2E-SEC-016, E2E-SEC-017, E2E-SEC-018, E2E-SEC-019, E2E-SEC-020, E2E-SEC-021, E2E-SEC-022, E2E-SEC-023, E2E-SEC-024, E2E-SEC-025 |
| Data variations | Accents, apostrophes, parentheses, dots in names | Accepted and shown as written | E2E-018, E2E-069, E2E-125, E2E-144, E2E-035 |
| Data variations | A file that is not UTF-8 text or is empty; Latin letters like ł ø œ ß; a curly apostrophe; an email with + or with no dot | Refused with the problem text or accepted as ruled | E2E-174, E2E-179, E2E-175, E2E-176 |
| Data variations | A look alike site, a foreign or reused sign in answer, a page in a frame, a copied session | Access denied. or Sign-in is unavailable.; nothing displayed or changed | E2E-182, E2E-184, E2E-SEC-017, E2E-SEC-018, E2E-SEC-019, E2E-SEC-024 |
| Data variations | A name typed with an accent mark after the letter, against the same name with the single accented letter | Treated as the same name: the collision question; the same folder name is refused as a duplicate | E2E-162, E2E-163 |
| Data variations | Emoji, symbols, Chinese, Cyrillic, Arabic (right to left) | Refused in folder names when emoji or symbols; other alphabets accepted and displayed correctly | E2E-095, E2E-097, E2E-046 |
| Data variations | Markup and injection looking text, encoded and look alike names | Refused with the rule message or shown as written, never interpreted | E2E-111, E2E-126, E2E-127, E2E-SEC-004, E2E-SEC-003, E2E-SEC-001, E2E-SEC-002, E2E-SEC-005 |
| Navigation | Back after sign out; direct link signed out; stale link; plain address link | No content after sign out; sign in then arrival; "Access denied."; secure form of the link | E2E-006, E2E-021, E2E-025, E2E-148, E2E-149 |
| Partial operations | Replacement cancelled; consent cancelled; deletion cancelled | Nothing changes; sign in page | E2E-067, E2E-005, E2E-080 |
| Partial operations | Storage full on upload and when a change is stored | "The upload failed. Nothing was changed."; the editor's failure notice; nothing stored | E2E-074, E2E-043 |
| Partial operations | A change typed continuously; a change that cannot be stored | Stored once at the end; the failure notice and the text kept on screen | E2E-153, E2E-152 |
| Dependency failures | Google down; the stored library unreadable | The two messages; no partial content | E2E-003, E2E-016 |
| Ordering and timing | Equal modified times; stored order stable between displays | Alphabetical, same order each time | E2E-027, E2E-020 |
| Ordering and timing | Folders named with digits, Latin letters and other alphabets | Digits, then Latin letters (accents and case ignored), then other alphabets | E2E-165 |
| Ordering and timing | Time zones | Dates are shown in the person's time zone; the other tests fix it to UTC | E2E-029, E2E-020 |
| Exhaustion | 200 folders, 100 presentations, a 30 MB attempt, 501 activity lines | Lists stay usable; the attempt is refused without storing or slowing others; the oldest line drops | E2E-017, E2E-104, E2E-SEC-006, E2E-SEC-007, E2E-142 |
| Exhaustion | An upload announcing 100 bytes then sending 30 MB; hand sent requests of a RO member | Refused without storing anything | E2E-SEC-025, E2E-SEC-023, E2E-SEC-022 |

## 9. Acceptance tests (the contract)

> Behavioral and technology agnostic. /sdlc-design maps each test to a driver. An implementing agent uses this as its definition of done.

**Standard library** (the state each test starts from unless it says otherwise; the person's time zone is UTC; "the administrator" is seb.morand@gmail.com):

- Folder "WCBIP Melbourne Décembre 2026": member lamya.chrif@gmail.com RW; presentations "From Challenges to Change" (3 901 499 bytes, 18 slides) and "Bridging the Gap" (3 278 888 bytes, 15 slides), both modified 15 Nov 2026 19:57 UTC.
- Folder "Cardiology 2027": members dan.rw@example.org RW and carol.ro@example.org RO; presentations "Heart Failure Update" (2 097 152 bytes, 8 slides, modified 10 Nov 2026 09:15; slide 1 titled "Heart Failure Update" with the speaker notes "Welcome and objectives", slide 2 titled "Epidemiology"), "Arrhythmia Basics" (524 288 bytes, 5 slides, modified 12 Nov 2026 16:40), "Statins Review" (1 572 864 bytes, 6 slides, modified 12 Nov 2026 16:40).
- Folder "Pneumo Été": no member, no presentation. Where a test says dan.rw@example.org or carol.ro@example.org holds a role there, that is stated in the test.
- bob.nobody@gmail.com is in no member list. "Quarterly Review.html" is a valid presentation of 3 slides, 1 258 291 bytes. A "valid presentation" fixture is declared as a presentation, has at least 1 slide and no structure error.

### 9.1 Summary

| Test | Action | Category | Scenario | Requirements | Priority |
|---|---|---|---|---|---|
| E2E-001 A member signs in and signs out | New | happy | SC-001 | FR-NEW-001, FR-NEW-002, FR-NEW-003, FR-NEW-004, FR-NEW-008, FR-NEW-015, FR-NEW-024, FR-NEW-068, FR-NEW-071, FR-NEW-072 | Critical |
| E2E-002 An account with no right is refused after Google | New | failure | SC-001 | FR-NEW-001, FR-NEW-002, FR-NEW-003, FR-NEW-008, FR-NEW-020, FR-NEW-065, FR-NEW-068 | Critical |
| E2E-003 Google cannot be reached | New | failure | SC-001 | FR-NEW-002, FR-NEW-004 | High |
| E2E-004 A visitor who is signed out sees only the sign in action | New | failure | SC-001 | FR-NEW-001, FR-NEW-009, FR-NEW-020 | Critical |
| E2E-005 The visitor cancels the Google consent | New | edge | SC-001 | FR-NEW-002 | Medium |
| E2E-006 The Back button after signing out shows no library content | New | edge | SC-001 | FR-NEW-001, FR-NEW-008, FR-NEW-072 | High |
| E2E-007 A cancelled consent gives no access to a direct link | New | failure | SC-001 | FR-NEW-001, FR-NEW-002, FR-NEW-009 | High |
| E2E-008 A session of 29 days 23 hours is still valid after closing the browser | New | happy | SC-002 | FR-NEW-005, FR-NEW-006, FR-NEW-015 | High |
| E2E-009 A session older than 30 days sends the person to the sign in page | New | failure | SC-002 | FR-NEW-001, FR-NEW-005, FR-NEW-006, FR-NEW-009 | Critical |
| E2E-010 The session ends in the middle of an edit | New | failure | SC-002 | FR-NEW-006, FR-NEW-007, FR-NEW-026, FR-NEW-066 | Critical |
| E2E-011 A person removed while their session was expired is refused after signing in again | New | failure | SC-002 | FR-NEW-003, FR-NEW-006, FR-NEW-048 | High |
| E2E-012 The 30 day limit is exact and never extended by use | New | edge | SC-002 | FR-NEW-005, FR-NEW-006 | High |
| E2E-013 Signing in again in another window lets the change be stored | New | edge | SC-002 | FR-NEW-002, FR-NEW-007, FR-NEW-026 | High |
| E2E-014 The administrator sees every folder and the Administration entry | New | happy | SC-003 | FR-NEW-011, FR-NEW-012, FR-NEW-014, FR-NEW-015, FR-NEW-016, FR-NEW-017, FR-NEW-020, FR-NEW-060 | Critical |
| E2E-015 The administrator with no folder sees the empty message | New | failure | SC-003 | FR-NEW-014, FR-NEW-015, FR-NEW-016 | Medium |
| E2E-016 The stored library cannot be read | New | failure | SC-003 | FR-NEW-017, FR-NEW-060, FR-NEW-062 | Medium |
| E2E-017 A library of 200 folders stays usable | New | edge | SC-003 | FR-NEW-015, FR-NEW-060, FR-NEW-064 | Medium |
| E2E-018 Folders are ordered without regard to case or accents | New | edge | SC-003 | FR-NEW-015, FR-NEW-065 | Medium |
| E2E-019 An unreadable library on a folder page shows no partial list | New | edge | SC-003 | FR-NEW-017, FR-NEW-018, FR-NEW-062 | Medium |
| E2E-020 A folder lists its presentations newest first | New | happy | SC-004 | FR-NEW-015, FR-NEW-018, FR-NEW-024 | Critical |
| E2E-021 A direct link works after signing in | New | happy | SC-004 | FR-NEW-002, FR-NEW-009, FR-NEW-010, FR-NEW-022, FR-NEW-069 | High |
| E2E-022 An empty folder says so | New | failure | SC-004 | FR-NEW-018, FR-NEW-019 | Medium |
| E2E-023 A folder that does not exist is refused | New | failure | SC-004 | FR-NEW-010, FR-NEW-020 | Critical |
| E2E-024 A folder the person cannot enter gives the same page as a missing one | New | failure | SC-004 | FR-NEW-010, FR-NEW-020, FR-NEW-021 | Critical |
| E2E-025 A link to a deleted presentation is refused | New | failure | SC-004 | FR-NEW-010, FR-NEW-039 | High |
| E2E-026 A direct link after signing in with an unauthorized account | New | failure | SC-004 | FR-NEW-003, FR-NEW-009, FR-NEW-010 | High |
| E2E-027 Presentations with equal times keep a stable order | New | edge | SC-004 | FR-NEW-018, FR-NEW-026 | Medium |
| E2E-028 Sizes are shown in bytes, KB and MB | New | edge | SC-004 | FR-NEW-018, FR-NEW-030 | Low |
| E2E-029 Dates follow the person's time zone | New | edge | SC-004 | FR-NEW-018 | Medium |
| E2E-030 A RO member views and presents | New | happy | SC-005 | FR-NEW-022, FR-NEW-023, FR-NEW-025, FR-NEW-052, FR-NEW-064 | Critical |
| E2E-031 A RO member downloads the HTML and the PPTX | New | happy | SC-005 | FR-NEW-022, FR-NEW-025 | High |
| E2E-032 A RO member has no control that changes anything | New | failure | SC-005 | FR-NEW-023, FR-NEW-025, FR-NEW-064 | Critical |
| E2E-033 Roles are per folder: RO in one, RW in another | New | edge | SC-005 | FR-NEW-015, FR-NEW-021, FR-NEW-023, FR-NEW-024 | High |
| E2E-034 A RO viewer sees a writer's saved change without gaining controls | New | edge | SC-005 | FR-NEW-022, FR-NEW-025, FR-NEW-026 | Medium |
| E2E-035 A download keeps an accented name with an apostrophe | New | edge | SC-005 | FR-NEW-022, FR-NEW-053 | Low |
| E2E-036 A RW member sees the upload and delete controls in their folder | New | happy | SC-006 | FR-NEW-024, FR-NEW-025, FR-NEW-028, FR-NEW-039 | Critical |
| E2E-037 A RW member cannot enter a folder where they hold no role | New | failure | SC-006 | FR-NEW-010, FR-NEW-020, FR-NEW-021 | Critical |
| E2E-038 A RW member has no administration | New | failure | SC-006 | FR-NEW-013, FR-NEW-024 | Critical |
| E2E-039 A RW member edits a presentation uploaded by someone else | New | edge | SC-006 | FR-NEW-024, FR-NEW-026 | Medium |
| E2E-040 A RW member does everything with the keyboard | New | edge | SC-006 | FR-NEW-024, FR-NEW-028, FR-NEW-064 | Medium |
| E2E-041 A RW member edits and the change is stored by itself | New | happy | SC-007 | FR-NEW-007, FR-NEW-025, FR-NEW-026, FR-NEW-051, FR-NEW-066 | Critical |
| E2E-042 Every option of the local editor is present | New | happy | SC-007 | FR-NEW-024, FR-NEW-025 | High |
| E2E-043 A change cannot be written | New | failure | SC-007 | FR-NEW-025, FR-NEW-026 | High |
| E2E-044 Leaving a field stores the change at once | New | edge | SC-007 | FR-NEW-025, FR-NEW-026, FR-NEW-051, FR-NEW-066 | Medium |
| E2E-045 A deck with embedded pictures displays them | New | edge | SC-007 | FR-NEW-025, FR-NEW-054 | Medium |
| E2E-046 Accents, Chinese characters and emoji survive a stored change | New | edge | SC-007 | FR-NEW-025, FR-NEW-026, FR-NEW-053 | Medium |
| E2E-047 A change above the 50 MB limit is refused like in the local mode | New | failure | SC-007 | FR-NEW-025, FR-NEW-026, FR-NEW-066 | Medium |
| E2E-048 Two people editing one after the other meet no conflict | New | happy | SC-008 | FR-NEW-024, FR-NEW-026, FR-NEW-027 | High |
| E2E-049 Leaving a field after someone else's stored change shows the conflict notice | New | failure | SC-008 | FR-NEW-026, FR-NEW-027 | Critical |
| E2E-050 Keep mine stores the person's version and keeps the other in history | New | failure | SC-008 | FR-NEW-026, FR-NEW-027 | High |
| E2E-051 Reload shows the stored version and drops the unsaved change | New | edge | SC-008 | FR-NEW-027 | Medium |
| E2E-052 An upload replacement during an edit triggers the notice | New | edge | SC-008 | FR-NEW-027, FR-NEW-034 | High |
| E2E-053 Saving a deleted presentation is refused | New | edge | SC-008 | FR-NEW-010, FR-NEW-026, FR-NEW-039 | High |
| E2E-054 A valid presentation is uploaded | New | happy | SC-009 | FR-NEW-024, FR-NEW-028, FR-NEW-029, FR-NEW-030, FR-NEW-031, FR-NEW-032, FR-NEW-037, FR-NEW-038, FR-NEW-049 | Critical |
| E2E-055 A file that is not .html is refused | New | failure | SC-009 | FR-NEW-028, FR-NEW-029 | High |
| E2E-056 A file one byte over 25 MB is refused | New | failure | SC-009 | FR-NEW-030, FR-NEW-061 | High |
| E2E-057 An ordinary web page is not a presentation | New | failure | SC-009 | FR-NEW-031 | High |
| E2E-058 A presentation without any slide is refused | New | failure | SC-009 | FR-NEW-031 | High |
| E2E-059 A blocking structure error names its first problem | New | failure | SC-009 | FR-NEW-031, FR-NEW-053 | High |
| E2E-060 A file name that carries a folder path is refused | New | failure | SC-009 | FR-NEW-032 | High |
| E2E-061 Names starting with a dot or using other characters are refused | New | failure | SC-009 | FR-NEW-032 | High |
| E2E-062 A file of exactly 25 MB is accepted | New | edge | SC-009 | FR-NEW-028, FR-NEW-030, FR-NEW-061 | High |
| E2E-063 Warnings do not block an upload | New | edge | SC-009 | FR-NEW-028, FR-NEW-031 | Medium |
| E2E-064 The first problem is the whole file one, before slide ones | New | edge | SC-009 | FR-NEW-031 | Medium |
| E2E-065 The extension is checked before the name and the size | New | edge | SC-009 | FR-NEW-029, FR-NEW-030, FR-NEW-032 | Medium |
| E2E-066 A same name upload asks, and Replace replaces | New | happy | SC-010 | FR-NEW-033, FR-NEW-034, FR-NEW-049, FR-NEW-063 | Critical |
| E2E-067 Cancel changes nothing | New | failure | SC-010 | FR-NEW-033, FR-NEW-051 | High |
| E2E-068 A validation message wins over the question | New | failure | SC-010 | FR-NEW-031, FR-NEW-033 | High |
| E2E-069 Names that differ by an accent are different | New | edge | SC-010 | FR-NEW-028, FR-NEW-033 | Medium |
| E2E-070 Two uploads of the same new name leave one presentation | New | edge | SC-010 | FR-NEW-033, FR-NEW-037, FR-NEW-063 | High |
| E2E-071 A 25 MB upload shows progress and completes | New | happy | SC-011 | FR-NEW-028, FR-NEW-030, FR-NEW-035, FR-NEW-036, FR-NEW-061, FR-NEW-067 | High |
| E2E-072 A lost connection leaves no partial presentation | New | failure | SC-011 | FR-NEW-035, FR-NEW-036, FR-NEW-063 | Critical |
| E2E-073 An interrupted replacement keeps the previous version | New | failure | SC-011 | FR-NEW-034, FR-NEW-036, FR-NEW-063 | Critical |
| E2E-074 A library that cannot store the file says so | New | failure | SC-011 | FR-NEW-038 | Medium |
| E2E-075 A double click uploads once | New | happy | SC-011 | FR-NEW-037, FR-NEW-049 | High |
| E2E-076 A slow link still completes within 2 minutes | New | edge | SC-011 | FR-NEW-035, FR-NEW-061 | Medium |
| E2E-077 Confirming Replace twice replaces once | New | failure | SC-011 | FR-NEW-034, FR-NEW-037, FR-NEW-049 | High |
| E2E-078 A replacement that cannot be stored keeps the previous version | New | edge | SC-011 | FR-NEW-034, FR-NEW-038, FR-NEW-063 | High |
| E2E-079 A RW member deletes a presentation | New | happy | SC-012 | FR-NEW-024, FR-NEW-039, FR-NEW-049 | Critical |
| E2E-080 Cancel keeps the presentation | New | failure | SC-012 | FR-NEW-039 | High |
| E2E-081 Confirming the deletion of an already deleted presentation is refused | New | failure | SC-012 | FR-NEW-010, FR-NEW-039 | Medium |
| E2E-082 A deleted name can be uploaded again without a question | New | edge | SC-012 | FR-NEW-028, FR-NEW-033, FR-NEW-039 | Medium |
| E2E-083 The question shows an accented name with an apostrophe as written | New | edge | SC-012 | FR-NEW-019, FR-NEW-039, FR-NEW-053 | Low |
| E2E-084 The administrator opens the administration | New | happy | SC-013 | FR-NEW-011, FR-NEW-014, FR-NEW-050, FR-NEW-067 | Critical |
| E2E-085 The administrator acts in a folder where they have no member entry | New | happy | SC-013 | FR-NEW-014, FR-NEW-024, FR-NEW-025, FR-NEW-028, FR-NEW-039 | High |
| E2E-086 RW and RO members are refused the administration | New | failure | SC-013 | FR-NEW-013 | Critical |
| E2E-087 The administrator address is compared without regard to case | New | edge | SC-013 | FR-NEW-002, FR-NEW-011 | High |
| E2E-088 A member entry cannot reduce the administrator | New | edge | SC-013 | FR-NEW-012, FR-NEW-014, FR-NEW-045 | Medium |
| E2E-089 Only RW and RO can be given | New | edge | SC-013 | FR-NEW-012, FR-NEW-045, FR-NEW-067 | Medium |
| E2E-090 An address that looks like the administrator's is not the administrator | New | failure | SC-013 | FR-NEW-003, FR-NEW-011, FR-NEW-012 | Critical |
| E2E-091 The administrator creates a folder | New | happy | SC-014 | FR-NEW-015, FR-NEW-019, FR-NEW-040, FR-NEW-041, FR-NEW-042, FR-NEW-049 | Critical |
| E2E-092 A folder name that exists without regard to case is refused | New | failure | SC-014 | FR-NEW-015, FR-NEW-042 | High |
| E2E-093 An empty or blank folder name is refused | New | failure | SC-014 | FR-NEW-040, FR-NEW-041 | High |
| E2E-094 A folder name of 61 characters is refused | New | failure | SC-014 | FR-NEW-041 | High |
| E2E-095 Emoji and symbols in a folder name are refused | New | failure | SC-014 | FR-NEW-041, FR-NEW-053 | High |
| E2E-096 A name of exactly 60 characters or a single hyphen is accepted | New | edge | SC-014 | FR-NEW-040, FR-NEW-041 | Medium |
| E2E-097 Names in other alphabets are accepted | New | edge | SC-014 | FR-NEW-015, FR-NEW-040, FR-NEW-053 | Medium |
| E2E-098 Duplicate checks ignore case and surrounding spaces but not accents | New | edge | SC-014 | FR-NEW-040, FR-NEW-042 | Medium |
| E2E-099 The administrator deletes a folder after retyping its name | New | happy | SC-015 | FR-NEW-043, FR-NEW-044, FR-NEW-049, FR-NEW-062 | Critical |
| E2E-100 A retyped name with a different case is refused | New | failure | SC-015 | FR-NEW-043, FR-NEW-044 | Critical |
| E2E-101 An empty retyped name is refused | New | failure | SC-015 | FR-NEW-044 | High |
| E2E-102 A former member is refused after the folder is deleted | New | failure | SC-015 | FR-NEW-010, FR-NEW-043, FR-NEW-048 | High |
| E2E-103 A recreated folder is empty and has no member | New | edge | SC-015 | FR-NEW-040, FR-NEW-043, FR-NEW-048 | High |
| E2E-104 A folder of 100 presentations is deleted entirely | New | edge | SC-015 | FR-NEW-043, FR-NEW-060 | Medium |
| E2E-105 Saving into a deleted folder is refused | New | edge | SC-015 | FR-NEW-026, FR-NEW-043, FR-NEW-048 | High |
| E2E-106 Deleting the last folder leaves the empty home page | New | edge | SC-015 | FR-NEW-016, FR-NEW-043, FR-NEW-049 | Medium |
| E2E-107 A retyped name without its accent is refused | New | edge | SC-015 | FR-NEW-043, FR-NEW-044 | Medium |
| E2E-108 The administrator adds a member | New | happy | SC-016 | FR-NEW-024, FR-NEW-045, FR-NEW-046, FR-NEW-049 | Critical |
| E2E-109 The administrator changes a role and removes a member | New | happy | SC-016 | FR-NEW-047, FR-NEW-048, FR-NEW-049 | Critical |
| E2E-110 Invalid addresses are refused | New | failure | SC-016 | FR-NEW-045, FR-NEW-046 | High |
| E2E-111 Two addresses in one field are refused | New | failure | SC-016 | FR-NEW-046, FR-NEW-053 | High |
| E2E-112 A RW member adds himself as Admin by hand | New | failure | SC-016 | FR-NEW-012, FR-NEW-013, FR-NEW-045 | High |
| E2E-113 An address already listed in other letter case with another role updates the entry | New | edge | SC-016 | FR-NEW-045, FR-NEW-047 | High |
| E2E-114 The administrator's own address can be listed | New | edge | SC-016 | FR-NEW-012, FR-NEW-014, FR-NEW-045 | Low |
| E2E-115 A trimmed address gives access without a new sign in | New | edge | SC-016 | FR-NEW-003, FR-NEW-022, FR-NEW-045, FR-NEW-046 | Medium |
| E2E-116 A raised role applies on the next action | New | happy | SC-017 | FR-NEW-024, FR-NEW-047, FR-NEW-048 | High |
| E2E-117 A removed member's change is refused | New | failure | SC-017 | FR-NEW-010, FR-NEW-026, FR-NEW-047, FR-NEW-048, FR-NEW-074 | Critical |
| E2E-118 A lowered role blocks the next stored change | New | failure | SC-017 | FR-NEW-023, FR-NEW-026, FR-NEW-047, FR-NEW-048 | Critical |
| E2E-119 A download after the folder was deleted is refused | New | failure | SC-017 | FR-NEW-010, FR-NEW-022, FR-NEW-048 | High |
| E2E-120 A right removed during an upload stops it | New | edge | SC-017 | FR-NEW-028, FR-NEW-036, FR-NEW-048 | High |
| E2E-121 An open presenter window keeps what it loaded | New | edge | SC-017 | FR-NEW-022, FR-NEW-048 | Medium |
| E2E-122 Each member sees only their own folders | New | happy | SC-018 | FR-NEW-015, FR-NEW-020, FR-NEW-021 | Critical |
| E2E-123 A presentation of another folder cannot be reached by typing its address | New | failure | SC-018 | FR-NEW-010, FR-NEW-020, FR-NEW-021 | Critical |
| E2E-124 Two folders each hold a "Statins Review" | New | edge | SC-018 | FR-NEW-020, FR-NEW-021, FR-NEW-033 | Medium |
| E2E-125 Dots, parentheses and apostrophes inside a name are accepted | New | happy | SC-019 | FR-NEW-028, FR-NEW-032, FR-NEW-053 | Medium |
| E2E-126 Markup inside a check message is shown as written | New | failure | SC-019 | FR-NEW-031, FR-NEW-053 | High |
| E2E-127 Encoded and look alike names are refused | New | edge | SC-019 | FR-NEW-032, FR-NEW-053 | High |
| E2E-128 The initial content is there | New | happy | SC-020 | FR-NEW-015, FR-NEW-018, FR-NEW-024, FR-NEW-054 | Critical |
| E2E-129 Other accounts see nothing of the initial content | New | failure | SC-020 | FR-NEW-010, FR-NEW-020, FR-NEW-054 | Critical |
| E2E-130 The seeded member is not an administrator | New | failure | SC-020 | FR-NEW-013, FR-NEW-054 | High |
| E2E-131 A restart does not reset or recreate the initial content | New | edge | SC-020 | FR-NEW-054, FR-NEW-062 | High |
| E2E-132 The seeded decks are unchanged and pass the upload checks | New | edge | SC-020 | FR-NEW-022, FR-NEW-031, FR-NEW-054 | High |
| E2E-133 The local mode edits one file with no sign in | New | happy | SC-021 | FR-NEW-025, FR-NEW-055, FR-NEW-056 | Critical |
| E2E-134 The local mode and the web library mode run side by side | New | failure | SC-021 | FR-NEW-055, FR-NEW-056, FR-NEW-057 | High |
| E2E-135 No library page exists in the local mode | New | failure | SC-021 | FR-NEW-055, FR-NEW-056 | High |
| E2E-136 The local mode keeps refusing other host names | New | edge | SC-021 | FR-NEW-055, FR-NEW-056, FR-NEW-059 | Medium |
| E2E-137 A local deck's script behaves as before | New | edge | SC-021 | FR-NEW-052, FR-NEW-055 | Low |
| E2E-138 The activity list records every kind of successful action | New | happy | SC-022 | FR-NEW-013, FR-NEW-049, FR-NEW-050 | Critical |
| E2E-139 A member cannot read the activity list | New | failure | SC-022 | FR-NEW-013, FR-NEW-020, FR-NEW-050 | Critical |
| E2E-140 Refused attempts are not recorded | New | failure | SC-022 | FR-NEW-003, FR-NEW-023, FR-NEW-049, FR-NEW-051 | High |
| E2E-141 Saves are not recorded | New | failure | SC-022 | FR-NEW-026, FR-NEW-051 | High |
| E2E-142 Only the 500 latest lines are shown | New | edge | SC-022 | FR-NEW-049, FR-NEW-050 | Medium |
| E2E-143 An empty activity list says so | New | edge | SC-022 | FR-NEW-050, FR-NEW-054 | Low |
| E2E-144 Accented names with apostrophes are shown as written | New | edge | SC-022 | FR-NEW-032, FR-NEW-049, FR-NEW-053 | Low |
| E2E-145 The address shows the sign in page securely | New | happy | SC-023 | FR-NEW-001, FR-NEW-057, FR-NEW-058, FR-NEW-059, FR-NEW-065 | Critical |
| E2E-146 The plain address is sent to the secure one | New | failure | SC-023 | FR-NEW-057, FR-NEW-058 | Critical |
| E2E-147 Another host name is refused | New | failure | SC-023 | FR-NEW-001, FR-NEW-057, FR-NEW-059 | High |
| E2E-148 A plain direct link keeps its destination | New | edge | SC-023 | FR-NEW-009, FR-NEW-058 | Medium |
| E2E-149 Any other page gives the sign in page when signed out and Access denied when signed in | New | edge | SC-023 | FR-NEW-001, FR-NEW-010, FR-NEW-013, FR-NEW-057 | Medium |
| E2E-150 Google reports a failure after the person chose an account | New | edge | SC-023 | FR-NEW-002, FR-NEW-004, FR-NEW-057 | High |
| E2E-151 A change is stored 0.8 seconds after typing stops | New | happy | SC-007 | FR-NEW-024, FR-NEW-026, FR-NEW-066 | Critical |
| E2E-152 A change that cannot be stored shows the notice and is kept on screen | New | failure | SC-007 | FR-NEW-017, FR-NEW-026, FR-NEW-066 | High |
| E2E-153 Typing without a pause of 0.8 seconds is stored once at the end | New | edge | SC-007 | FR-NEW-025, FR-NEW-026, FR-NEW-066 | Medium |
| E2E-154 An error of the editor's charter rules blocks an upload | New | failure | SC-009 | FR-NEW-028, FR-NEW-031 | High |
| E2E-155 A warning listed first is never the first problem | New | edge | SC-009 | FR-NEW-031 | High |
| E2E-156 The controls the mode adds carry their exact names | New | edge | SC-013 | FR-NEW-011, FR-NEW-040, FR-NEW-045, FR-NEW-067 | High |
| E2E-157 The folder deletion prompt can be cancelled | New | failure | SC-015 | FR-NEW-043, FR-NEW-044, FR-NEW-067 | High |
| E2E-158 The progress percent is a whole number rounded down | New | edge | SC-011 | FR-NEW-035, FR-NEW-067 | Medium |
| E2E-159 A library whose every folder was deleted is not seeded again | New | edge | SC-020 | FR-NEW-016, FR-NEW-054, FR-NEW-062 | High |
| E2E-160 Adding the same address with the same role changes nothing | New | edge | SC-016 | FR-NEW-045 | Medium |
| E2E-161 A role other than the two offered is refused | New | failure | SC-016 | FR-NEW-012, FR-NEW-045 | High |
| E2E-162 File names: composed form, 100 characters, edge spaces | New | edge | SC-010 | FR-NEW-032, FR-NEW-033 | High |
| E2E-163 Folder names: composed form and length counted after it | New | edge | SC-014 | FR-NEW-040, FR-NEW-041, FR-NEW-042 | Medium |
| E2E-164 Rounding of sizes and display of times | New | edge | SC-004 | FR-NEW-018 | Medium |
| E2E-165 Folders are ordered digits, Latin letters, other alphabets | New | edge | SC-003 | FR-NEW-015 | Medium |
| E2E-166 A signed in person stays signed in after a restart | New | edge | SC-002 | FR-NEW-005, FR-NEW-062 | High |
| E2E-167 An ended session shows one notice, soon, and no connection notice | New | failure | SC-002 | FR-NEW-006, FR-NEW-007 | High |
| E2E-168 A folder of 100 presentations lists within 2 seconds | New | happy | SC-004 | FR-NEW-018, FR-NEW-060 | Medium |
| E2E-169 Sign ins and sign outs are not recorded | New | edge | SC-022 | FR-NEW-049, FR-NEW-051 | Medium |
| E2E-170 A notice added inside the editor is in English next to French labels | New | failure | SC-007 | FR-NEW-010, FR-NEW-048, FR-NEW-065 | Medium |
| E2E-171 An unverified address of an unlisted account gives the same message | New | edge | SC-001 | FR-NEW-003, FR-NEW-068 | High |
| E2E-172 Destinations that leave the product are ignored | New | edge | SC-001 | FR-NEW-009, FR-NEW-069 | High |
| E2E-173 A session that ended gives a quiet screen until the person acts | New | happy | SC-017 | FR-NEW-007, FR-NEW-048, FR-NEW-074 | High |
| E2E-174 A file that is not valid UTF-8 text is refused with no location | New | failure | SC-009 | FR-NEW-028, FR-NEW-031, FR-NEW-053 | High |
| E2E-175 File names accept Latin-script letters and the straight apostrophe only | New | edge | SC-009 | FR-NEW-028, FR-NEW-032 | Medium |
| E2E-176 Email address forms: plus sign accepted, apostrophe and missing dot refused | New | failure | SC-016 | FR-NEW-045, FR-NEW-046 | Medium |
| E2E-177 A removed right gives a quiet screen, then Access denied on the next action | New | failure | SC-017 | FR-NEW-010, FR-NEW-048, FR-NEW-074 | High |
| E2E-178 Moving between slides is not an action that needs the library | New | edge | SC-017 | FR-NEW-074 | Medium |
| E2E-179 An empty file is refused as not declared | New | edge | SC-009 | FR-NEW-028, FR-NEW-031 | Medium |
| E2E-180 Library controls per page | New | edge | SC-001 | FR-NEW-008, FR-NEW-067 | Medium |
| E2E-181 Changes made from the library's own pages are accepted | New | happy | SC-019 | FR-NEW-024, FR-NEW-028, FR-NEW-070 | High |
| E2E-182 A look alike site is another site | New | edge | SC-019 | FR-NEW-070 | High |
| E2E-183 Two sign ins started in two tabs each complete | New | happy | SC-001 | FR-NEW-002, FR-NEW-071 | Medium |
| E2E-184 A sign in answer cannot be used twice | New | edge | SC-001 | FR-NEW-071 | High |
| E2E-185 Signing out in one tab ends the session in the other tab | New | edge | SC-001 | FR-NEW-008, FR-NEW-072 | Medium |
| E2E-186 The health check works without sign in and shows little | New | happy | SC-023 | FR-NEW-059, FR-NEW-073 | High |
| E2E-187 A presentation's status is shown only to a person with a right on it | New | edge | SC-023 | FR-NEW-010, FR-NEW-073 | High |
| E2E-188 A change stored after signing in again meets the conflict notice when someone else changed the presentation | New | edge | SC-002 | FR-NEW-007, FR-NEW-027 | Medium |
| E2E-189 Two people leaving their fields in the same second leave one stored version | New | edge | SC-008 | FR-NEW-026, FR-NEW-027 | Medium |
| E2E-SEC-001 A RO member uploads a path traversal name | New | security | SC-019 | FR-NEW-010, FR-NEW-021, FR-NEW-023, FR-NEW-032 | Critical |
| E2E-SEC-002 A RW member uploads a path traversal name | New | security | SC-019 | FR-NEW-021, FR-NEW-032, FR-NEW-053 | Critical |
| E2E-SEC-003 A name that looks like a data erasing command is refused | New | security | SC-019 | FR-NEW-032, FR-NEW-053 | Critical |
| E2E-SEC-004 A name carrying a script tag is refused | New | security | SC-019 | FR-NEW-032, FR-NEW-053 | Critical |
| E2E-SEC-005 A folder named two dots is refused | New | security | SC-019 | FR-NEW-021, FR-NEW-041, FR-NEW-053 | Critical |
| E2E-SEC-006 A RO member sends a 30 MB file | New | security | SC-019 | FR-NEW-010, FR-NEW-023, FR-NEW-030, FR-NEW-060 | Critical |
| E2E-SEC-007 A RW member sends a 30 MB file | New | security | SC-019 | FR-NEW-030, FR-NEW-038 | Critical |
| E2E-SEC-008 A RO member stores a change by hand | New | security | SC-005 | FR-NEW-010, FR-NEW-023, FR-NEW-026 | Critical |
| E2E-SEC-009 A RO member deletes by hand | New | security | SC-005 | FR-NEW-010, FR-NEW-023, FR-NEW-039 | Critical |
| E2E-SEC-010 A RO member uploads by hand | New | security | SC-005 | FR-NEW-010, FR-NEW-023, FR-NEW-028 | Critical |
| E2E-SEC-011 A RW member creates a folder by hand | New | security | SC-013 | FR-NEW-013, FR-NEW-040 | Critical |
| E2E-SEC-012 A visitor without a session cannot download a presentation | New | security | SC-001 | FR-NEW-001, FR-NEW-020, FR-NEW-022 | Critical |
| E2E-SEC-013 A presentation's script cannot read what the browser keeps for the library | New | security | SC-018 | FR-NEW-021, FR-NEW-052, FR-NEW-053 | Critical |
| E2E-SEC-014 A presentation's script cannot act as the viewer or reach other folders | New | security | SC-018 | FR-NEW-020, FR-NEW-023, FR-NEW-052 | Critical |
| E2E-SEC-015 A Google account claiming the administrator address without verifying it | New | security | SC-001 | FR-NEW-011, FR-NEW-012, FR-NEW-068 | Critical |
| E2E-SEC-016 A sign in link carrying a destination on another site | New | security | SC-001 | FR-NEW-009, FR-NEW-069 | Critical |
| E2E-SEC-017 A page of another site deletes with the visitor's session | New | security | SC-019 | FR-NEW-023, FR-NEW-039, FR-NEW-070 | Critical |
| E2E-SEC-018 A request with the administrator's copied session and no sign of coming from the library | New | security | SC-019 | FR-NEW-013, FR-NEW-040, FR-NEW-070 | Critical |
| E2E-SEC-019 A sign in answer made for someone else is planted in a visitor's browser | New | security | SC-001 | FR-NEW-002, FR-NEW-020, FR-NEW-071 | Critical |
| E2E-SEC-020 A session copied before Sign out is used after it | New | security | SC-001 | FR-NEW-001, FR-NEW-008, FR-NEW-072 | Critical |
| E2E-SEC-021 A visitor reads the liveness and status answers | New | security | SC-023 | FR-NEW-001, FR-NEW-010, FR-NEW-073 | Critical |
| E2E-SEC-022 A presentation's script reaches the machine while its PPTX is built | New | security | SC-018 | FR-NEW-020, FR-NEW-022, FR-NEW-052 | Critical |
| E2E-SEC-023 A RO member sends the other changing requests by hand | New | security | SC-005 | FR-NEW-010, FR-NEW-023, FR-NEW-070 | Critical |
| E2E-SEC-024 A page of another site shows a library page inside a frame | New | security | SC-001 | FR-NEW-001, FR-NEW-020, FR-NEW-072 | Critical |
| E2E-SEC-025 An upload that announces 100 bytes and sends 30 MB | New | security | SC-019 | FR-NEW-030, FR-NEW-038, FR-NEW-063 | Critical |

Coverage: 214 tests: happy 35, failure 71, edge 83, security 25. Tagged inside those: side effect 85, state transition 41. Happy to failure ratio 1:2.7 (failure and security tests together: 96 against 35 happy; must beat 1:1).

### 9.2 New tests

#### E2E-001: A member signs in and signs out

- **Category:** happy (side effect, state transition)
- **Scenario:** SC-001
- **Requirements:** FR-NEW-001, FR-NEW-002, FR-NEW-003, FR-NEW-004, FR-NEW-008, FR-NEW-015, FR-NEW-024, FR-NEW-068, FR-NEW-071, FR-NEW-072
- **Given** lamya.chrif@gmail.com is RW in "WCBIP Melbourne Décembre 2026" and has no session; Google will return her account as "Lamya.Chrif@Gmail.COM".
- **When** She opens slides.scm-platform.org, chooses "Sign in with Google", completes the Google sign in, then chooses "Sign out".
- **Then** After the sign in the home page lists one folder, "WCBIP Melbourne Décembre 2026", with the role "Read and write", and shows "Sign out" but no "Administration". After "Sign out" the sign in page shows only "Sign in with Google".
- **And** The product asked for no password of its own.
- **And** Opening the address again in the same browser shows the sign in page and no folder name.
- **And** No "Access denied." and no "Sign-in is unavailable. Try again later." message appeared.
- **And** In another run she cancels the Google consent first: the sign in page is shown again with no message, and a second attempt succeeds.
- **And** The sign in answer belonged to the sign in this browser started, so no "Sign-in is unavailable. Try again later." appeared.
- **And** Lamya's own upload of "Quarterly Review.html", done in this session, appears in the administrator's activity list as attributed to lamya.chrif@gmail.com in lower case, not "Lamya.Chrif@Gmail.COM".
- **Priority:** Critical

#### E2E-002: An account with no right is refused after Google

- **Category:** failure (state transition)
- **Scenario:** SC-001
- **Requirements:** FR-NEW-001, FR-NEW-002, FR-NEW-003, FR-NEW-008, FR-NEW-020, FR-NEW-065, FR-NEW-068
- **Given** bob.nobody@gmail.com is in no member list and is not the administrator.
- **When** He signs in with Google using bob.nobody@gmail.com.
- **Then** He sees "Access denied." and a "Sign out" button; no folder name and no presentation name appears anywhere.
- **And** After the administrator adds bob.nobody@gmail.com as RO in "Cardiology 2027", Bob opens a page without signing in again and sees the home page with "Cardiology 2027".
- **And** He chooses "Sign out" and the sign in page is shown; every text he saw was in English.
- **And** In a second run, Bob's browser is already signed in to lamya.chrif@gmail.com at Google; he signs in again: Google shows its account chooser, he picks bob.nobody@gmail.com and sees "Access denied."; picking lamya.chrif@gmail.com shows her folders.
- **Priority:** Critical

#### E2E-003: Google cannot be reached

- **Category:** failure
- **Scenario:** SC-001
- **Requirements:** FR-NEW-002, FR-NEW-004
- **Given** A visitor with a Google account; Google does not answer.
- **When** The visitor chooses "Sign in with Google".
- **Then** The sign in page shows "Sign-in is unavailable. Try again later." and the visitor stays signed out.
- **And** When Google answers again, choosing "Sign in with Google" again signs lamya.chrif@gmail.com in.
- **And** The same message is shown when the Google console does not know the return address of slides.scm-platform.org (EXC-023c).
- **Priority:** High

#### E2E-004: A visitor who is signed out sees only the sign in action

- **Category:** failure
- **Scenario:** SC-001
- **Requirements:** FR-NEW-001, FR-NEW-009, FR-NEW-020
- **Given** A visitor with no session.
- **When** The visitor opens the home page, the folder "Cardiology 2027" and the presentation "Heart Failure Update" by their direct links.
- **Then** Each time the sign in page is shown, with the single action "Sign in with Google".
- **And** None of the three pages shows a folder name, a presentation name, a member or a slide.
- **Priority:** Critical

#### E2E-005: The visitor cancels the Google consent

- **Category:** edge
- **Scenario:** SC-001
- **Requirements:** FR-NEW-002
- **Given** A visitor on the Google consent screen for lamya.chrif@gmail.com.
- **When** The visitor cancels the consent.
- **Then** The sign in page is shown, signed out, without any message.
- **And** Choosing "Sign in with Google" again starts a fresh sign in that can succeed.
- **Priority:** Medium

#### E2E-006: The Back button after signing out shows no library content

- **Category:** edge (state transition)
- **Scenario:** SC-001
- **Requirements:** FR-NEW-001, FR-NEW-008, FR-NEW-072
- **Given** dan.rw@example.org is signed in and looking at the folder page of "Cardiology 2027".
- **When** He chooses "Sign out" and then presses the Back button of the browser.
- **Then** The sign in page is shown; "Cardiology 2027", "Heart Failure Update", "Arrhythmia Basics" and "Statins Review" are not visible.
- **And** Dan's session in a second browser, where he did not sign out, is still signed in.
- **Priority:** High

#### E2E-007: A cancelled consent gives no access to a direct link

- **Category:** failure
- **Scenario:** SC-001
- **Requirements:** FR-NEW-001, FR-NEW-002, FR-NEW-009
- **Given** carol.ro@example.org holds the link to "Heart Failure Update" and has no session; she cancels the Google consent.
- **When** She then opens the link again.
- **Then** The sign in page is shown, not the presentation.
- **And** No folder name and no presentation name was shown at any step.
- **Priority:** High

#### E2E-008: A session of 29 days 23 hours is still valid after closing the browser

- **Category:** happy
- **Scenario:** SC-002
- **Requirements:** FR-NEW-005, FR-NEW-006, FR-NEW-015
- **Given** lamya.chrif@gmail.com signed in 29 days 23 hours ago and closed her browser.
- **When** She opens slides.scm-platform.org in a new browser window.
- **Then** The home page with "WCBIP Melbourne Décembre 2026" is shown without any Google step.
- **And** Her 30 day period still ends 1 hour from now, not later.
- **And** One hour later the same action sends her to the sign in page.
- **Priority:** High

#### E2E-009: A session older than 30 days sends the person to the sign in page

- **Category:** failure (state transition)
- **Scenario:** SC-002
- **Requirements:** FR-NEW-001, FR-NEW-005, FR-NEW-006, FR-NEW-009
- **Given** lamya.chrif@gmail.com signed in 30 days 1 minute ago.
- **When** She opens the link to the folder "WCBIP Melbourne Décembre 2026".
- **Then** The sign in page is shown, not the folder.
- **And** After she signs in again the folder page opens, and her new session lasts 30 days from now.
- **Priority:** Critical

#### E2E-010: The session ends in the middle of an edit

- **Category:** failure (side effect)
- **Scenario:** SC-002
- **Requirements:** FR-NEW-006, FR-NEW-007, FR-NEW-026, FR-NEW-066
- **Given** dan.rw@example.org is editing "Heart Failure Update"; he typed the title of slide 1 as "Heart Failure Update 2027" and has not left its field; his session reaches 30 days.
- **When** He leaves the edited field.
- **Then** "Your session has expired. Sign in again to save." is shown within 2 seconds of the field being left, as the only notice: "Save failed:" is not put in front of it and "Connection to the editor server lost" is not shown. The edited title and the whole presentation stay on screen.
- **And** carol.ro@example.org opens "Heart Failure Update" and sees the title "Heart Failure Update": nothing was saved.
- **And** The history of the presentation still has no new version.
- **Priority:** Critical

#### E2E-011: A person removed while their session was expired is refused after signing in again

- **Category:** failure (state transition)
- **Scenario:** SC-002
- **Requirements:** FR-NEW-003, FR-NEW-006, FR-NEW-048
- **Given** dan.rw@example.org's session expired; the administrator then removed him from every folder where he was a member.
- **When** He signs in with Google again.
- **Then** "Access denied." is shown and no folder is listed.
- **And** The administrator's member list of "Cardiology 2027" shows only carol.ro@example.org.
- **Priority:** High

#### E2E-012: The 30 day limit is exact and never extended by use

- **Category:** edge (state transition)
- **Scenario:** SC-002
- **Requirements:** FR-NEW-005, FR-NEW-006
- **Given** dan.rw@example.org signed in 29 days 23 hours 59 minutes ago and used the library every day; carol.ro@example.org signed in 30 days 1 minute ago and used it yesterday.
- **When** Both open the home page.
- **Then** Dan sees his folders; Carol sees the sign in page.
- **And** One minute later Dan opens the home page again and sees the sign in page.
- **Priority:** High

#### E2E-013: Signing in again in another window lets the change be stored

- **Category:** edge (side effect, state transition)
- **Scenario:** SC-002
- **Requirements:** FR-NEW-002, FR-NEW-007, FR-NEW-026
- **Given** dan.rw@example.org has "Heart Failure Update" open with the unsaved title "Heart Failure Update 2027" and the message "Your session has expired. Sign in again to save." on screen.
- **When** He signs in again in a second window, returns to the first window, types "!" at the end of the title and leaves the field.
- **Then** The change is stored with no notice and the expiry message disappears.
- **And** carol.ro@example.org opening the presentation sees the title "Heart Failure Update 2027!".
- **And** The history of the presentation holds the previous version with the title "Heart Failure Update".
- **Priority:** High

#### E2E-014: The administrator sees every folder and the Administration entry

- **Category:** happy
- **Scenario:** SC-003
- **Requirements:** FR-NEW-011, FR-NEW-012, FR-NEW-014, FR-NEW-015, FR-NEW-016, FR-NEW-017, FR-NEW-020, FR-NEW-060
- **Given** The standard library; seb.morand@gmail.com has no member entry anywhere.
- **When** He signs in and opens the home page.
- **Then** Three folders are listed in this order: "Cardiology 2027", "Pneumo Été", "WCBIP Melbourne Décembre 2026", each labelled "Admin"; "Administration" and "Sign out" are shown.
- **And** carol.ro@example.org, on the same moment, sees only "Cardiology 2027" labelled "Read only".
- **And** The page is ready within 2 seconds, with no "The library is unavailable. Try again later." and no "You have no access to any folder yet."
- **Priority:** Critical

#### E2E-015: The administrator with no folder sees the empty message

- **Category:** failure (state transition, side effect)
- **Scenario:** SC-003
- **Requirements:** FR-NEW-014, FR-NEW-015, FR-NEW-016
- **Given** The administrator deleted the three folders of the standard library.
- **When** seb.morand@gmail.com opens the home page.
- **Then** "You have no access to any folder yet." is shown, with "Administration" and "Sign out".
- **And** After he creates the folder "Oncology 2030" the home page lists it and the message is gone.
- **Priority:** Medium

#### E2E-016: The stored library cannot be read

- **Category:** failure (side effect, state transition)
- **Scenario:** SC-003
- **Requirements:** FR-NEW-017, FR-NEW-060, FR-NEW-062
- **Given** dan.rw@example.org is signed in; the library holds 200 folders; the stored library cannot be read at this moment.
- **When** He opens the home page.
- **Then** "The library is unavailable. Try again later." is shown; no folder name and no partial list.
- **And** When the library can be read again, the home page lists "Cardiology 2027" and "Pneumo Été" with all their presentations intact.
- **Priority:** Medium

#### E2E-017: A library of 200 folders stays usable

- **Category:** edge
- **Scenario:** SC-003
- **Requirements:** FR-NEW-015, FR-NEW-060, FR-NEW-064
- **Given** The administrator, and 200 folders named "Folder 001" to "Folder 200".
- **When** seb.morand@gmail.com opens the home page on a 50 megabit per second connection, then reaches "Folder 200" using the keyboard only.
- **Then** All 200 folders are listed within 2 seconds of the request, "Folder 001" first and "Folder 200" last, and "Folder 200" opens with the Enter key.
- **And** Every folder entry has a visible name that a screen reader announces.
- **Priority:** Medium

#### E2E-018: Folders are ordered without regard to case or accents

- **Category:** edge
- **Scenario:** SC-003
- **Requirements:** FR-NEW-015, FR-NEW-065
- **Given** The administrator, and folders "zeta", "Éclair Study", "Cardiology 2027", "alpha trial", "Pneumo Été".
- **When** He opens the home page.
- **Then** The order is "alpha trial", "Cardiology 2027", "Éclair Study", "Pneumo Été", "zeta".
- **And** Every label and message that the mode adds on the page is in English.
- **Priority:** Medium

#### E2E-019: An unreadable library on a folder page shows no partial list

- **Category:** edge (side effect)
- **Scenario:** SC-003
- **Requirements:** FR-NEW-017, FR-NEW-018, FR-NEW-062
- **Given** dan.rw@example.org has the folder page of "Cardiology 2027" open; the stored library then cannot be read.
- **When** He refreshes the page.
- **Then** "The library is unavailable. Try again later." is shown and none of the 3 presentations is listed.
- **And** When the library can be read again the refresh lists the same 3 presentations with their sizes.
- **Priority:** Medium

#### E2E-020: A folder lists its presentations newest first

- **Category:** happy
- **Scenario:** SC-004
- **Requirements:** FR-NEW-015, FR-NEW-018, FR-NEW-024
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; time zone UTC.
- **When** He opens "Cardiology 2027" from the home page.
- **Then** Three rows in this order: "Arrhythmia Basics", 12 Nov 2026 16:40, 512.0 KB; "Statins Review", 12 Nov 2026 16:40, 1.5 MB; "Heart Failure Update", 10 Nov 2026 09:15, 2.0 MB.
- **And** A way back to the home page is shown and works.
- **And** The two rows with the same time are in alphabetical order.
- **Priority:** Critical

#### E2E-021: A direct link works after signing in

- **Category:** happy (state transition)
- **Scenario:** SC-004
- **Requirements:** FR-NEW-002, FR-NEW-009, FR-NEW-010, FR-NEW-022, FR-NEW-069
- **Given** carol.ro@example.org has no session and holds the link to "Heart Failure Update" in "Cardiology 2027".
- **When** She opens the link and completes the Google sign in.
- **Then** "Heart Failure Update" is shown to her, in the read only form.
- **And** She is not asked to go through the home page first.
- **And** The page shown for an allowed target carries no "Access denied."
- **Priority:** High

#### E2E-022: An empty folder says so

- **Category:** failure
- **Scenario:** SC-004
- **Requirements:** FR-NEW-018, FR-NEW-019
- **Given** The administrator; "Pneumo Été" holds no presentation.
- **When** He opens "Pneumo Été".
- **Then** "This folder has no presentations yet." is shown, with the way back to the home page.
- **And** No list header or empty table is shown instead of the message.
- **Priority:** Medium

#### E2E-023: A folder that does not exist is refused

- **Category:** failure
- **Scenario:** SC-004
- **Requirements:** FR-NEW-010, FR-NEW-020
- **Given** dan.rw@example.org is signed in; no folder "Oncology 2030" exists.
- **When** He opens the link to the folder "Oncology 2030".
- **Then** The text "Access denied." and the "Sign out" button are shown, nothing else.
- **And** A screenshot of this page is the reference for the next test.
- **Priority:** Critical

#### E2E-024: A folder the person cannot enter gives the same page as a missing one

- **Category:** failure
- **Scenario:** SC-004
- **Requirements:** FR-NEW-010, FR-NEW-020, FR-NEW-021
- **Given** carol.ro@example.org holds a role only in "Cardiology 2027".
- **When** She opens the link to the folder "WCBIP Melbourne Décembre 2026", then the link to the missing folder "Oncology 2030".
- **Then** Both pages show the text "Access denied." and the "Sign out" button and nothing else; the two pages are identical in wording and content.
- **And** Neither page names a folder, a presentation or a member.
- **And** The two answers are identical on the wire: same status, same headers except the date, same body.
- **Priority:** Critical

#### E2E-025: A link to a deleted presentation is refused

- **Category:** failure (state transition, side effect)
- **Scenario:** SC-004
- **Requirements:** FR-NEW-010, FR-NEW-039
- **Given** carol.ro@example.org kept the link to "Statins Review"; dan.rw@example.org then deleted "Statins Review".
- **When** Carol opens her link.
- **Then** "Access denied." is shown.
- **And** The folder page of "Cardiology 2027" now lists two presentations.
- **Priority:** High

#### E2E-026: A direct link after signing in with an unauthorized account

- **Category:** failure
- **Scenario:** SC-004
- **Requirements:** FR-NEW-003, FR-NEW-009, FR-NEW-010
- **Given** bob.nobody@gmail.com has no session and holds the link to "Heart Failure Update".
- **When** He opens the link and signs in with Google.
- **Then** "Access denied." is shown, with no slide and no folder name.
- **Priority:** High

#### E2E-027: Presentations with equal times keep a stable order

- **Category:** edge
- **Scenario:** SC-004
- **Requirements:** FR-NEW-018, FR-NEW-026
- **Given** "Arrhythmia Basics" and "Statins Review" were both modified 12 Nov 2026 16:40.
- **When** dan.rw@example.org opens the folder page 5 times, refreshing each time; then he changes the title of "Statins Review" at 17:30 and leaves the field.
- **Then** The first 5 displays show "Arrhythmia Basics" before "Statins Review"; after the change "Statins Review" is first, with 12 Nov 2026 17:30.
- **And** Two other presentations modified in the same minute, "éclair" and "Eclair", are listed "Eclair" then "éclair": same sorting key, then exact name by character code.
- **Priority:** Medium

#### E2E-028: Sizes are shown in bytes, KB and MB

- **Category:** edge
- **Scenario:** SC-004
- **Requirements:** FR-NEW-018, FR-NEW-030
- **Given** Presentations of 1 byte, 900 bytes, 1 023 bytes, 1 024 bytes, 1 048 576 bytes and 26 214 400 bytes in one folder.
- **When** A member opens the folder.
- **Then** The sizes read "1 byte", "900 bytes", "1023 bytes", "1.0 KB", "1.0 MB" and "25.0 MB".
- **Priority:** Low

#### E2E-029: Dates follow the person's time zone

- **Category:** edge
- **Scenario:** SC-004
- **Requirements:** FR-NEW-018
- **Given** carol.ro@example.org's browser is set to the Melbourne time zone (UTC plus 11 hours in November); dan.rw@example.org's browser is set to UTC.
- **When** Each opens the folder page of "Cardiology 2027".
- **Then** Dan sees "Arrhythmia Basics" modified 12 Nov 2026 16:40; Carol sees the same instant as 13 Nov 2026 03:40.
- **And** The order of the rows is the same for both.
- **Priority:** Medium

#### E2E-030: A RO member views and presents

- **Category:** happy
- **Scenario:** SC-005
- **Requirements:** FR-NEW-022, FR-NEW-023, FR-NEW-025, FR-NEW-052, FR-NEW-064
- **Given** carol.ro@example.org is RO in "Cardiology 2027"; slide 1 of "Heart Failure Update" is titled "Heart Failure Update" and carries the speaker notes "Welcome and objectives"; slide 2 is titled "Epidemiology".
- **When** She opens "Heart Failure Update", enters full screen with the key F, then opens the presenter window with the key S.
- **Then** Full screen shows slide 1. The presenter window shows slide 1 with its title "Heart Failure Update", slide 2 "Epidemiology" as the next slide preview, the notes "Welcome and objectives", the slide counter and the timer; the arrow keys move both windows.
- **And** Every control she used is reachable and named for the keyboard.
- **And** The presentation's own navigation and animations work as in the local mode.
- **And** No Upload, Delete or edit mode control was shown.
- **Priority:** Critical

#### E2E-031: A RO member downloads the HTML and the PPTX

- **Category:** happy (side effect)
- **Scenario:** SC-005
- **Requirements:** FR-NEW-022, FR-NEW-025
- **Given** carol.ro@example.org is RO in "Cardiology 2027"; "Heart Failure Update" has 8 slides and is 2 097 152 bytes.
- **When** She chooses the HTML download, then the PPTX download.
- **Then** She receives "Heart Failure Update.html" of 2 097 152 bytes identical to the stored presentation, and a PPTX of 8 slides.
- **And** The stored presentation and its history are unchanged.
- **Priority:** High

#### E2E-032: A RO member has no control that changes anything

- **Category:** failure
- **Scenario:** SC-005
- **Requirements:** FR-NEW-023, FR-NEW-025, FR-NEW-064
- **Given** carol.ro@example.org is RO in "Cardiology 2027".
- **When** She opens the folder page, then "Statins Review", and presses the key E.
- **Then** The folder page has no Upload and no Delete; the presentation shows no edit mode, undo, redo, notes editing, requests or slide actions; the key E does nothing.
- **And** The controls that exist are: navigation, full screen, pointer, presenter window, HTML and PPTX download, help.
- **And** Each control that exists is reachable with the keyboard and has a label.
- **Priority:** Critical

#### E2E-033: Roles are per folder: RO in one, RW in another

- **Category:** edge (side effect)
- **Scenario:** SC-005
- **Requirements:** FR-NEW-015, FR-NEW-021, FR-NEW-023, FR-NEW-024
- **Given** carol.ro@example.org is RO in "Cardiology 2027" and RW in "Pneumo Été".
- **When** She opens each folder, then uploads the valid file "Spirometry Basics.html" in "Pneumo Été".
- **Then** In "Cardiology 2027" there is no Upload and no Delete; in "Pneumo Été" both exist and "Uploaded Spirometry Basics." is shown. The home page labels the two folders "Read only" and "Read and write".
- **And** The administrator sees "Spirometry Basics" in "Pneumo Été" only.
- **Priority:** High

#### E2E-034: A RO viewer sees a writer's saved change without gaining controls

- **Category:** edge
- **Scenario:** SC-005
- **Requirements:** FR-NEW-022, FR-NEW-025, FR-NEW-026
- **Given** carol.ro@example.org has "Heart Failure Update" open; dan.rw@example.org changes the title to "Heart Failure Update 2027" and leaves the field.
- **When** Carol's page follows the change, as the local mode follows a changed file.
- **Then** Carol sees the title "Heart Failure Update 2027".
- **And** Her screen still has no editing control.
- **Priority:** Medium

#### E2E-035: A download keeps an accented name with an apostrophe

- **Category:** edge
- **Scenario:** SC-005
- **Requirements:** FR-NEW-022, FR-NEW-053
- **Given** "Cardiology 2027" holds "L'été (v2)"; carol.ro@example.org is RO there.
- **When** She downloads its HTML.
- **Then** She receives a file named "L'été (v2).html".
- **Priority:** Low

#### E2E-036: A RW member sees the upload and delete controls in their folder

- **Category:** happy
- **Scenario:** SC-006
- **Requirements:** FR-NEW-024, FR-NEW-025, FR-NEW-028, FR-NEW-039
- **Given** dan.rw@example.org is RW in "Cardiology 2027".
- **When** He opens the folder page and then "Heart Failure Update".
- **Then** "Upload" is shown on the folder page and "Delete" on each of the three rows; the presentation opens in the full editor with edit mode available.
- **Priority:** Critical

#### E2E-037: A RW member cannot enter a folder where they hold no role

- **Category:** failure
- **Scenario:** SC-006
- **Requirements:** FR-NEW-010, FR-NEW-020, FR-NEW-021
- **Given** dan.rw@example.org holds roles in "Cardiology 2027" and "Pneumo Été" only.
- **When** He opens the link to "WCBIP Melbourne Décembre 2026".
- **Then** "Access denied." is shown; no presentation name of that folder appears.
- **Priority:** Critical

#### E2E-038: A RW member has no administration

- **Category:** failure
- **Scenario:** SC-006
- **Requirements:** FR-NEW-013, FR-NEW-024
- **Given** dan.rw@example.org is signed in.
- **When** He looks at the home page and opens the administration link he was told about.
- **Then** The home page has no "Administration" entry; the link shows "Access denied."
- **And** No folder, member or activity line was shown to him.
- **Priority:** Critical

#### E2E-039: A RW member edits a presentation uploaded by someone else

- **Category:** edge (side effect)
- **Scenario:** SC-006
- **Requirements:** FR-NEW-024, FR-NEW-026
- **Given** The administrator uploaded "Arrhythmia Basics" into "Cardiology 2027".
- **When** dan.rw@example.org changes the title of slide 1 and leaves the field.
- **Then** The change is stored.
- **And** The previous version is in the history of "Arrhythmia Basics".
- **Priority:** Medium

#### E2E-040: A RW member does everything with the keyboard

- **Category:** edge
- **Scenario:** SC-006
- **Requirements:** FR-NEW-024, FR-NEW-028, FR-NEW-064
- **Given** dan.rw@example.org uses the keyboard only; the valid file "Quarterly Review.html" is ready.
- **When** He tabs to "Upload", chooses the file and confirms, then tabs to "Delete" on that row, confirms, and leaves with "Sign out".
- **Then** "Uploaded Quarterly Review." is shown, then the presentation is gone, then the sign in page is shown.
- **And** Every control he used has a visible label.
- **Priority:** Medium

#### E2E-041: A RW member edits and the change is stored by itself

- **Category:** happy (side effect)
- **Scenario:** SC-007
- **Requirements:** FR-NEW-007, FR-NEW-025, FR-NEW-026, FR-NEW-051, FR-NEW-066
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; "Heart Failure Update" has the title "Heart Failure Update" on slide 1.
- **When** He turns edit mode on, changes the title to "Heart Failure Update 2027" and leaves the field.
- **Then** No notice is shown and the editor offers no Save control. Carol opening the presentation sees "Heart Failure Update 2027".
- **And** The history of the presentation lists the previous version with the title "Heart Failure Update".
- **And** The administrator's activity list has no line for this stored change.
- **And** No session message was shown: the session was still valid.
- **Priority:** Critical

#### E2E-042: Every option of the local editor is present

- **Category:** happy
- **Scenario:** SC-007
- **Requirements:** FR-NEW-024, FR-NEW-025
- **Given** dan.rw@example.org has "Heart Failure Update" open.
- **When** He looks at the toolbar and tries each option.
- **Then** The toolbar shows, with the labels of the local mode: "Édition", "Annuler", "Rétablir", "Mode présentation plein écran", "Présenter avec le pointeur", "Vue présentateur", "Notes", "Requests", "Ask AI", "Télécharger en PPTX", "Télécharger le fichier HTML" and "Raccourcis clavier"; the keys F, P, S, E and ? work as in the local mode.
- **And** The notes panel for slide 1 accepts "Mention the 2026 guideline" and the open presenter window shows that text.
- **And** The labels are not translated into English; every notice that the library mode adds in the editor is in English.
- **And** A DOCX export requested by hand by dan.rw@example.org (RW) is refused with "Access denied." and no file is received, as for everyone.
- **Priority:** High

#### E2E-043: A change cannot be written

- **Category:** failure (side effect)
- **Scenario:** SC-007
- **Requirements:** FR-NEW-025, FR-NEW-026
- **Given** dan.rw@example.org edited the title of slide 1; the library has no space left.
- **When** He leaves the edited field.
- **Then** The editor's usual save failure notice is shown with the reason; his change stays on screen.
- **And** carol.ro@example.org opening the presentation sees the old title; the file is not truncated.
- **Priority:** High

#### E2E-044: Leaving a field stores the change at once

- **Category:** edge (side effect)
- **Scenario:** SC-007
- **Requirements:** FR-NEW-025, FR-NEW-026, FR-NEW-051, FR-NEW-066
- **Given** dan.rw@example.org has changed the text of slide 2 of "Statins Review" to "First line therapy" and is still in the field.
- **When** He clicks outside the field.
- **Then** The text is stored at once, without waiting for 0.8 seconds of silence.
- **And** carol.ro@example.org reloading sees "First line therapy".
- **And** The administrator's activity list has no line for it.
- **Priority:** Medium

#### E2E-045: A deck with embedded pictures displays them

- **Category:** edge
- **Scenario:** SC-007
- **Requirements:** FR-NEW-025, FR-NEW-054
- **Given** "From Challenges to Change" (3 901 499 bytes, 18 slides, pictures embedded) is in "WCBIP Melbourne Décembre 2026".
- **When** lamya.chrif@gmail.com opens it and goes through the 18 slides.
- **Then** Every picture is displayed; no slide shows a broken picture.
- **Priority:** Medium

#### E2E-046: Accents, Chinese characters and emoji survive a stored change

- **Category:** edge (side effect)
- **Scenario:** SC-007
- **Requirements:** FR-NEW-025, FR-NEW-026, FR-NEW-053
- **Given** dan.rw@example.org edits "Statins Review".
- **When** He types "Cœur, insuffisance 心臓 😀" in the title of slide 1, leaves the field, then reloads.
- **Then** The title reads "Cœur, insuffisance 心臓 😀" exactly.
- **Priority:** Medium

#### E2E-047: A change above the 50 MB limit is refused like in the local mode

- **Category:** failure (side effect)
- **Scenario:** SC-007
- **Requirements:** FR-NEW-025, FR-NEW-026, FR-NEW-066
- **Given** dan.rw@example.org inserted pictures that make "Statins Review" 60 MB.
- **When** He leaves the edited field.
- **Then** The editor's usual save failure notice is shown with the reason; his changes stay on screen.
- **And** "Statins Review" still opens as the stored version of 1 572 864 bytes.
- **And** A change of 52 428 800 bytes is accepted, 52 428 801 refused, as in the local mode.
- **Priority:** Medium

#### E2E-048: Two people editing one after the other meet no conflict

- **Category:** happy (side effect)
- **Scenario:** SC-008
- **Requirements:** FR-NEW-024, FR-NEW-026, FR-NEW-027
- **Given** dan.rw@example.org saved "Statins Review" with the title "Statins 2027"; the administrator opens the presentation afterwards.
- **When** The administrator changes the title to "Statins 2028" and leaves the field.
- **Then** The change is stored with no notice.
- **And** Both previous versions are in the history.
- **And** In another run Dan, who has typed nothing, has "Statins Review" open while the administrator's change is stored: within 2 seconds Dan's screen shows "Statins 2028" with no notice.
- **Priority:** High

#### E2E-049: Leaving a field after someone else's stored change shows the conflict notice

- **Category:** failure (side effect, state transition)
- **Scenario:** SC-008
- **Requirements:** FR-NEW-026, FR-NEW-027
- **Given** dan.rw@example.org and seb.morand@gmail.com both have "Statins Review" open; Dan has typed the title "Statins B" and has not left its field; the administrator changes the title to "Statins A" and leaves his field, so "Statins A" is stored.
- **When** Dan leaves his field.
- **Then** The notice "The file changed on disk. Reload to see the changes, or keep your version." is shown with "Keep mine" and "Reload".
- **And** carol.ro@example.org opening the presentation sees "Statins A": Dan's change is not stored.
- **Priority:** Critical

#### E2E-050: Keep mine stores the person's version and keeps the other in history

- **Category:** failure (side effect, state transition)
- **Scenario:** SC-008
- **Requirements:** FR-NEW-026, FR-NEW-027
- **Given** The conflict of the previous kind: dan.rw@example.org typed "Statins B", the administrator stored "Statins A" meanwhile, Dan left his field and the conflict notice is on his screen.
- **When** He chooses "Keep mine".
- **Then** His title "Statins B" is stored.
- **And** The history lists the version with the title "Statins A".
- **And** carol.ro@example.org sees "Statins B".
- **Priority:** High

#### E2E-051: Reload shows the stored version and drops the unsaved change

- **Category:** edge (state transition)
- **Scenario:** SC-008
- **Requirements:** FR-NEW-027
- **Given** The same conflict notice is on the screen of dan.rw@example.org; his unsaved title is "Statins B" and the stored title is "Statins A".
- **When** He chooses "Reload".
- **Then** The editor shows the stored title "Statins A".
- **And** His text "Statins B" is nowhere in the stored presentation or its history.
- **Priority:** Medium

#### E2E-052: An upload replacement during an edit triggers the notice

- **Category:** edge (side effect)
- **Scenario:** SC-008
- **Requirements:** FR-NEW-027, FR-NEW-034
- **Given** dan.rw@example.org has typed "Statins C" in the title of slide 2 of "Statins Review" and has not left the field; the administrator uploads a valid "Statins Review.html" and confirms "Replace".
- **When** Dan leaves the field.
- **Then** The conflict notice is shown; nothing is stored until he chooses.
- **And** The replaced content is the one carol.ro@example.org sees.
- **Priority:** High

#### E2E-053: Saving a deleted presentation is refused

- **Category:** edge (side effect)
- **Scenario:** SC-008
- **Requirements:** FR-NEW-010, FR-NEW-026, FR-NEW-039
- **Given** dan.rw@example.org is editing "Statins Review"; the administrator deletes it.
- **When** Dan leaves the edited field.
- **Then** "Access denied." is shown as the editor's only notice; his text stays on screen.
- **And** "Statins Review" is not recreated: the folder lists 2 presentations.
- **Priority:** High

#### E2E-054: A valid presentation is uploaded

- **Category:** happy (side effect)
- **Scenario:** SC-009
- **Requirements:** FR-NEW-024, FR-NEW-028, FR-NEW-029, FR-NEW-030, FR-NEW-031, FR-NEW-032, FR-NEW-037, FR-NEW-038, FR-NEW-049
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; the file "Quarterly Review.HTML" is a valid presentation of 3 slides, 1 258 291 bytes.
- **When** He chooses Upload and picks the file.
- **Then** "Uploaded Quarterly Review." is shown; the folder page lists "Quarterly Review" first, with the current date and time and the size "1.2 MB".
- **And** carol.ro@example.org opens "Quarterly Review" and sees its 3 slides.
- **And** The administrator's activity list gains the line "Uploaded "Quarterly Review" in "Cardiology 2027"" attributed to dan.rw@example.org.
- **And** A single Upload action produced one presentation and one activity line; no "The upload failed. Nothing was changed." appeared.
- **Priority:** Critical

#### E2E-055: A file that is not .html is refused

- **Category:** failure (side effect)
- **Scenario:** SC-009
- **Requirements:** FR-NEW-028, FR-NEW-029
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; the file "Quarterly Review.pdf" exists.
- **When** He uploads it.
- **Then** "Only .html files are accepted." is shown.
- **And** The folder still lists 3 presentations.
- **And** The activity list has no new line.
- **Priority:** High

#### E2E-056: A file one byte over 25 MB is refused

- **Category:** failure (side effect)
- **Scenario:** SC-009
- **Requirements:** FR-NEW-030, FR-NEW-061
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; "Big Deck.html" is a valid presentation of 26 214 401 bytes.
- **When** He uploads it.
- **Then** "The file is larger than 25 MB." is shown.
- **And** The folder still lists 3 presentations; no "Big Deck" exists.
- **Priority:** High

#### E2E-057: An ordinary web page is not a presentation

- **Category:** failure
- **Scenario:** SC-009
- **Requirements:** FR-NEW-031
- **Given** dan.rw@example.org; "About Us.html" is a web page with a heading "Hello" and no declaration as a presentation.
- **When** He uploads it.
- **Then** "This file is not a valid presentation: the file is not declared as a presentation." is shown.
- **And** Nothing is added to the folder.
- **And** In another run "Undeclared Deck.html", which has 2 well formed slides but no declaration as a presentation, shows the same message "the file is not declared as a presentation" and is refused.
- **Priority:** High

#### E2E-058: A presentation without any slide is refused

- **Category:** failure
- **Scenario:** SC-009
- **Requirements:** FR-NEW-031
- **Given** dan.rw@example.org; "Empty Deck.html" is declared as a presentation and has 0 slides.
- **When** He uploads it.
- **Then** "This file is not a valid presentation: the file has no slide." is shown.
- **And** Nothing is added to the folder.
- **Priority:** High

#### E2E-059: A blocking structure error names its first problem

- **Category:** failure
- **Scenario:** SC-009
- **Requirements:** FR-NEW-031, FR-NEW-053
- **Given** dan.rw@example.org; "Broken Deck.html" is declared as a presentation, has 2 slides, and the second slide has no title attribute.
- **When** He uploads it.
- **Then** "This file is not a valid presentation: missing attribute data-title." is shown.
- **And** Nothing is added to the folder.
- **Priority:** High

#### E2E-060: A file name that carries a folder path is refused

- **Category:** failure
- **Scenario:** SC-009
- **Requirements:** FR-NEW-032
- **Given** dan.rw@example.org; the valid file is named "2026/Quarterly Review.html".
- **When** He uploads it.
- **Then** "This file name is not allowed." is shown.
- **And** No "Quarterly Review" appears in any folder, seen by the administrator.
- **Priority:** High

#### E2E-061: Names starting with a dot or using other characters are refused

- **Category:** failure
- **Scenario:** SC-009
- **Requirements:** FR-NEW-032
- **Given** dan.rw@example.org; valid files named ".hidden.html", "Report #1.html" and "Rapport@2026.html".
- **When** He uploads each in turn.
- **Then** Each time "This file name is not allowed." is shown.
- **And** The folder still lists 3 presentations.
- **Priority:** High

#### E2E-062: A file of exactly 25 MB is accepted

- **Category:** edge (side effect)
- **Scenario:** SC-009
- **Requirements:** FR-NEW-028, FR-NEW-030, FR-NEW-061
- **Given** dan.rw@example.org; "Big Deck.html" is a valid presentation of exactly 26 214 400 bytes.
- **When** He uploads it.
- **Then** "Uploaded Big Deck." is shown; the folder page lists it with the size "25.0 MB".
- **Priority:** High

#### E2E-063: Warnings do not block an upload

- **Category:** edge (side effect)
- **Scenario:** SC-009
- **Requirements:** FR-NEW-028, FR-NEW-031
- **Given** dan.rw@example.org; "Web Pictures.html" is a valid presentation of 2 slides with a picture loaded from another site, which the editor's checks report as a warning only.
- **When** He uploads it.
- **Then** "Uploaded Web Pictures." is shown.
- **And** carol.ro@example.org opens it and sees both slides.
- **Priority:** Medium

#### E2E-064: The first problem is the whole file one, before slide ones

- **Category:** edge
- **Scenario:** SC-009
- **Requirements:** FR-NEW-031
- **Given** dan.rw@example.org; "Mismatch.html" declares a slide total of 5 while it has 3 slides, and its second slide also lacks its title attribute.
- **When** He uploads it.
- **Then** "This file is not a valid presentation: TOTAL is 5 but the file has 3 slides." is shown.
- **And** Only that one problem is shown.
- **Priority:** Medium

#### E2E-065: The extension is checked before the name and the size

- **Category:** edge
- **Scenario:** SC-009
- **Requirements:** FR-NEW-029, FR-NEW-030, FR-NEW-032
- **Given** dan.rw@example.org; "notes.txt" is 30 MB; "a/b.html" is 30 MB.
- **When** He uploads each in turn.
- **Then** The first shows "Only .html files are accepted."; the second shows "This file name is not allowed."
- **And** Neither shows "The file is larger than 25 MB."
- **Priority:** Medium

#### E2E-066: A same name upload asks, and Replace replaces

- **Category:** happy (side effect, state transition)
- **Scenario:** SC-010
- **Requirements:** FR-NEW-033, FR-NEW-034, FR-NEW-049, FR-NEW-063
- **Given** dan.rw@example.org; "Statins Review" (1 572 864 bytes) exists in "Cardiology 2027"; he holds "statins review.HTML", a valid presentation of 2 slides, 307 200 bytes.
- **When** He uploads it and, on the question, chooses "Replace".
- **Then** The question A presentation named "Statins Review" already exists. Replace it? is shown first; then "Uploaded Statins Review." and the row "Statins Review" shows 300.0 KB.
- **And** The history of "Statins Review" lists the previous version of 1 572 864 bytes.
- **And** The folder still lists 3 presentations; the name keeps its capital letters.
- **And** The activity list gains one line "Replaced "Statins Review" in "Cardiology 2027"".
- **And** "Cancel" was offered next to "Replace".
- **And** A request queued on "Statins Review" before the replacement is still in its Requests list afterwards.
- **Priority:** Critical

#### E2E-067: Cancel changes nothing

- **Category:** failure (side effect, state transition)
- **Scenario:** SC-010
- **Requirements:** FR-NEW-033, FR-NEW-051
- **Given** dan.rw@example.org uploaded a valid "statins review.HTML" of 307 200 bytes and the question A presentation named "Statins Review" already exists. Replace it? is shown to him; "Statins Review" is 1 572 864 bytes.
- **When** He chooses "Cancel".
- **Then** The folder page is shown again; "Statins Review" still has 1.5 MB.
- **And** The history has no new version.
- **And** The activity list has no new line.
- **Priority:** High

#### E2E-068: A validation message wins over the question

- **Category:** failure
- **Scenario:** SC-010
- **Requirements:** FR-NEW-031, FR-NEW-033
- **Given** dan.rw@example.org; "Statins Review.html" is declared as a presentation and has 0 slides.
- **When** He uploads it.
- **Then** "This file is not a valid presentation: the file has no slide." is shown and no question is asked.
- **And** "Statins Review" is unchanged, 1.5 MB.
- **Priority:** High

#### E2E-069: Names that differ by an accent are different

- **Category:** edge (side effect)
- **Scenario:** SC-010
- **Requirements:** FR-NEW-028, FR-NEW-033
- **Given** dan.rw@example.org uploaded a valid "Cafe Study.html" into "Cardiology 2027".
- **When** He uploads a valid "Café Study.html".
- **Then** No question is asked; "Uploaded Café Study." is shown.
- **And** The folder lists "Cafe Study" and "Café Study" as two presentations.
- **Priority:** Medium

#### E2E-070: Two uploads of the same new name leave one presentation

- **Category:** edge (side effect)
- **Scenario:** SC-010
- **Requirements:** FR-NEW-033, FR-NEW-037, FR-NEW-063
- **Given** dan.rw@example.org and seb.morand@gmail.com each upload a valid "Lipids Update.html" to "Cardiology 2027" at the same moment; no such presentation exists.
- **When** Both submit within the same second.
- **Then** One upload ends with "Uploaded Lipids Update."; the other, which finishes second, is treated as a name collision and shows A presentation named "Lipids Update" already exists. Replace it?
- **And** Whatever the second person chooses, the folder lists exactly one "Lipids Update" and it opens as a complete presentation.
- **And** If the second person chooses "Cancel", the first upload's content is the one that opens.
- **Priority:** High

#### E2E-071: A 25 MB upload shows progress and completes

- **Category:** happy (side effect)
- **Scenario:** SC-011
- **Requirements:** FR-NEW-028, FR-NEW-030, FR-NEW-035, FR-NEW-036, FR-NEW-061, FR-NEW-067
- **Given** dan.rw@example.org uploads "Big Deck.html", a valid presentation of 26 214 400 bytes, on a 10 megabit per second connection.
- **When** He starts the upload.
- **Then** The text "Big Deck.html <percent>%" is shown with a whole number growing from 0 (for example "Big Deck.html 37%"); within 2 minutes "Uploaded Big Deck." appears.
- **And** The percentage never goes down and never reads 100% before the upload is complete.
- **Priority:** High

#### E2E-072: A lost connection leaves no partial presentation

- **Category:** failure (side effect)
- **Scenario:** SC-011
- **Requirements:** FR-NEW-035, FR-NEW-036, FR-NEW-063
- **Given** dan.rw@example.org uploads "Big Deck.html"; his connection drops at 40 percent.
- **When** The upload stops.
- **Then** No "Big Deck" is listed once the page is reloaded.
- **And** The administrator's view of "Cardiology 2027" lists 3 presentations; the library holds no fragment of "Big Deck".
- **And** The progress stopped at 40 percent and no "Uploaded Big Deck." message appeared.
- **Priority:** Critical

#### E2E-073: An interrupted replacement keeps the previous version

- **Category:** failure (side effect)
- **Scenario:** SC-011
- **Requirements:** FR-NEW-034, FR-NEW-036, FR-NEW-063
- **Given** dan.rw@example.org replaces "Statins Review" and confirms "Replace"; his connection drops at 70 percent.
- **When** The upload stops.
- **Then** "Statins Review" opens as the complete previous version of 1 572 864 bytes.
- **And** The history has no new version and the activity list no new line.
- **Priority:** Critical

#### E2E-074: A library that cannot store the file says so

- **Category:** failure (side effect)
- **Scenario:** SC-011
- **Requirements:** FR-NEW-038
- **Given** dan.rw@example.org; the library has no space left; "Quarterly Review.html" is valid.
- **When** He uploads it.
- **Then** "The upload failed. Nothing was changed." is shown.
- **And** No "Quarterly Review" is listed; the activity list has no new line.
- **Priority:** Medium

#### E2E-075: A double click uploads once

- **Category:** happy (side effect)
- **Scenario:** SC-011
- **Requirements:** FR-NEW-037, FR-NEW-049
- **Given** dan.rw@example.org; "Quarterly Review.html" is valid.
- **When** He presses Upload twice within half a second.
- **Then** One "Uploaded Quarterly Review." is shown.
- **And** The folder lists one "Quarterly Review".
- **And** The activity list has one upload line.
- **Priority:** High

#### E2E-076: A slow link still completes within 2 minutes

- **Category:** edge
- **Scenario:** SC-011
- **Requirements:** FR-NEW-035, FR-NEW-061
- **Given** dan.rw@example.org on a link limited to 10 megabits per second uploads a valid file of 26 214 400 bytes.
- **When** He starts the upload and waits.
- **Then** "Uploaded <name>." appears no later than 2 minutes after the start.
- **And** Meanwhile lamya.chrif@gmail.com browses her folder without noticeable delay.
- **Priority:** Medium

#### E2E-077: Confirming Replace twice replaces once

- **Category:** failure (side effect)
- **Scenario:** SC-011
- **Requirements:** FR-NEW-034, FR-NEW-037, FR-NEW-049
- **Given** dan.rw@example.org uploaded a valid "Statins Review.html" and the question A presentation named "Statins Review" already exists. Replace it? is shown.
- **When** He presses "Replace" twice within half a second.
- **Then** One "Uploaded Statins Review." is shown.
- **And** The history of "Statins Review" gains one version, the 1 572 864 byte one; the activity list gains one "Replaced" line.
- **Priority:** High

#### E2E-078: A replacement that cannot be stored keeps the previous version

- **Category:** edge (side effect)
- **Scenario:** SC-011
- **Requirements:** FR-NEW-034, FR-NEW-038, FR-NEW-063
- **Given** dan.rw@example.org confirms "Replace" on "Statins Review"; the library has no space left.
- **When** The upload ends.
- **Then** "The upload failed. Nothing was changed." is shown.
- **And** "Statins Review" opens as the complete previous version of 1 572 864 bytes; its history and the activity list are unchanged.
- **Priority:** High

#### E2E-079: A RW member deletes a presentation

- **Category:** happy (side effect, state transition)
- **Scenario:** SC-012
- **Requirements:** FR-NEW-024, FR-NEW-039, FR-NEW-049
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; "Statins Review" has 2 versions in its history.
- **When** He chooses Delete on "Statins Review" and confirms with "Delete".
- **Then** The question Delete "Statins Review"? This cannot be undone. is shown first; then the list shows 2 presentations.
- **And** carol.ro@example.org's list shows 2 presentations.
- **And** The history of "Statins Review" is gone: the operator's listing of its history shows nothing.
- **And** The activity list gains "Deleted "Statins Review" from "Cardiology 2027"".
- **And** "Cancel" was offered next to "Delete".
- **Priority:** Critical

#### E2E-080: Cancel keeps the presentation

- **Category:** failure (side effect)
- **Scenario:** SC-012
- **Requirements:** FR-NEW-039
- **Given** The question Delete "Statins Review"? This cannot be undone. is shown to dan.rw@example.org.
- **When** He chooses "Cancel".
- **Then** The folder page still lists "Statins Review".
- **And** Its history is intact; no activity line was added.
- **Priority:** High

#### E2E-081: Confirming the deletion of an already deleted presentation is refused

- **Category:** failure (side effect)
- **Scenario:** SC-012
- **Requirements:** FR-NEW-010, FR-NEW-039
- **Given** dan.rw@example.org shows the delete question for "Statins Review"; the administrator deletes it first.
- **When** Dan confirms.
- **Then** "Access denied." is shown and the refreshed list has 2 presentations.
- **And** The activity list holds one deletion line, the administrator's.
- **Priority:** Medium

#### E2E-082: A deleted name can be uploaded again without a question

- **Category:** edge (side effect)
- **Scenario:** SC-012
- **Requirements:** FR-NEW-028, FR-NEW-033, FR-NEW-039
- **Given** "Statins Review" was deleted by dan.rw@example.org.
- **When** He uploads a valid "Statins Review.html".
- **Then** "Uploaded Statins Review." is shown with no question.
- **And** The history of the new presentation is empty: no version of the deleted one comes back.
- **And** Before the deletion "Statins Review" had a queued request "Make the title shorter" and an AI suggestion; after the new upload its Requests list is empty and no suggestion is shown.
- **Priority:** Medium

#### E2E-083: The question shows an accented name with an apostrophe as written

- **Category:** edge (side effect)
- **Scenario:** SC-012
- **Requirements:** FR-NEW-019, FR-NEW-039, FR-NEW-053
- **Given** "Pneumo Été" holds only "L'été (v2)"; the administrator is signed in.
- **When** He chooses Delete on it, chooses "Cancel", chooses Delete again and confirms.
- **Then** The question reads Delete "L'été (v2)"? This cannot be undone. exactly; afterwards "This folder has no presentations yet." is shown.
- **Priority:** Low

#### E2E-084: The administrator opens the administration

- **Category:** happy
- **Scenario:** SC-013
- **Requirements:** FR-NEW-011, FR-NEW-014, FR-NEW-050, FR-NEW-067
- **Given** seb.morand@gmail.com is signed in.
- **When** He chooses "Administration".
- **Then** He sees the section "Folders", where each folder shows its "Members" and a "Delete folder" button, the field "Folder name" with the button "Create folder", and the section "Activity".
- **Priority:** Critical

#### E2E-085: The administrator acts in a folder where they have no member entry

- **Category:** happy (side effect)
- **Scenario:** SC-013
- **Requirements:** FR-NEW-014, FR-NEW-024, FR-NEW-025, FR-NEW-028, FR-NEW-039
- **Given** seb.morand@gmail.com is in no member list; "Pneumo Été" is empty; "Spirometry Basics.html" is valid.
- **When** He uploads it into "Pneumo Été", edits it (the change is stored by itself), then deletes "Statins Review" from "Cardiology 2027".
- **Then** "Uploaded Spirometry Basics." is shown, the edit is stored, and the deletion succeeds.
- **And** dan.rw@example.org sees 2 presentations in "Cardiology 2027".
- **Priority:** High

#### E2E-086: RW and RO members are refused the administration

- **Category:** failure
- **Scenario:** SC-013
- **Requirements:** FR-NEW-013
- **Given** dan.rw@example.org (RW) and carol.ro@example.org (RO) are signed in.
- **When** Each opens the administration link and the activity list link.
- **Then** Each time "Access denied." is shown.
- **And** No home page of either shows "Administration".
- **Priority:** Critical

#### E2E-087: The administrator address is compared without regard to case

- **Category:** edge
- **Scenario:** SC-013
- **Requirements:** FR-NEW-002, FR-NEW-011
- **Given** Google returns the account as "Seb.Morand@Gmail.com".
- **When** He signs in.
- **Then** He is the administrator: "Administration" is shown and all 3 folders are listed with "Admin".
- **Priority:** High

#### E2E-088: A member entry cannot reduce the administrator

- **Category:** edge (side effect)
- **Scenario:** SC-013
- **Requirements:** FR-NEW-012, FR-NEW-014, FR-NEW-045
- **Given** The administrator is listed RO in "Cardiology 2027".
- **When** He deletes "Arrhythmia Basics" there.
- **Then** The deletion succeeds.
- **And** His label on the home page is still "Admin".
- **Priority:** Medium

#### E2E-089: Only RW and RO can be given

- **Category:** edge
- **Scenario:** SC-013
- **Requirements:** FR-NEW-012, FR-NEW-045, FR-NEW-067
- **Given** The administrator opens the add member form of "Pneumo Été".
- **When** He looks at the "Members" of "Pneumo Été", fills the field "Email address" with dan.rw@example.org, chooses "Read and write" in "Role" and presses "Add member".
- **Then** The chooser "Role" offers "Read and write" and "Read only" and nothing else; no "Admin".
- **And** Dan's home page labels the folder "Read and write" and shows no "Administration".
- **Priority:** Medium

#### E2E-090: An address that looks like the administrator's is not the administrator

- **Category:** failure
- **Scenario:** SC-013
- **Requirements:** FR-NEW-003, FR-NEW-011, FR-NEW-012
- **Given** Google accounts "sebmorand@gmail.com" and "seb.morand@googlemail.com", listed in no folder.
- **When** Each signs in.
- **Then** Each sees "Access denied."; neither sees "Administration" nor any folder.
- **And** The administrator's activity list and folder list are unchanged.
- **Priority:** Critical

#### E2E-091: The administrator creates a folder

- **Category:** happy (side effect)
- **Scenario:** SC-014
- **Requirements:** FR-NEW-015, FR-NEW-019, FR-NEW-040, FR-NEW-041, FR-NEW-042, FR-NEW-049
- **Given** seb.morand@gmail.com is signed in; the standard library.
- **When** He types "  Oncology 2030  " (two spaces on each side) and creates the folder.
- **Then** The home page lists 4 folders, "Cardiology 2027", "Oncology 2030", "Pneumo Été", "WCBIP Melbourne Décembre 2026"; opening "Oncology 2030" shows "This folder has no presentations yet."
- **And** The member list of "Oncology 2030" is empty.
- **And** The activity list gains "Created folder "Oncology 2030"".
- **And** No "Folder names use 1 to 60 letters, digits, spaces or hyphens." and no duplicate message appeared.
- **Priority:** Critical

#### E2E-092: A folder name that exists without regard to case is refused

- **Category:** failure
- **Scenario:** SC-014
- **Requirements:** FR-NEW-015, FR-NEW-042
- **Given** The standard library.
- **When** The administrator creates a folder named "cardiology 2027".
- **Then** A folder named "cardiology 2027" already exists. is shown.
- **And** The home page still lists 3 folders.
- **Priority:** High

#### E2E-093: An empty or blank folder name is refused

- **Category:** failure
- **Scenario:** SC-014
- **Requirements:** FR-NEW-040, FR-NEW-041
- **Given** The administrator.
- **When** He creates a folder with an empty name, then with 3 spaces.
- **Then** Each time "Folder names use 1 to 60 letters, digits, spaces or hyphens." is shown.
- **And** The home page still lists 3 folders.
- **Priority:** High

#### E2E-094: A folder name of 61 characters is refused

- **Category:** failure
- **Scenario:** SC-014
- **Requirements:** FR-NEW-041
- **Given** The administrator.
- **When** He creates a folder named with 61 letters "A".
- **Then** "Folder names use 1 to 60 letters, digits, spaces or hyphens." is shown.
- **And** No folder was added.
- **Priority:** High

#### E2E-095: Emoji and symbols in a folder name are refused

- **Category:** failure
- **Scenario:** SC-014
- **Requirements:** FR-NEW-041, FR-NEW-053
- **Given** The administrator.
- **When** He creates in turn "Pneumo 🫁", "Cardio/Rhythm", "Cardio_2027", "R&D" and "Study.2027".
- **Then** Each time "Folder names use 1 to 60 letters, digits, spaces or hyphens." is shown.
- **And** The home page still lists 3 folders.
- **Priority:** High

#### E2E-096: A name of exactly 60 characters or a single hyphen is accepted

- **Category:** edge (side effect)
- **Scenario:** SC-014
- **Requirements:** FR-NEW-040, FR-NEW-041
- **Given** The administrator.
- **When** He creates a folder named with 60 letters "B" and a folder named "-".
- **Then** Both are created and listed; the 60 letter name is shown in full without hiding any control.
- **Priority:** Medium

#### E2E-097: Names in other alphabets are accepted

- **Category:** edge (side effect)
- **Scenario:** SC-014
- **Requirements:** FR-NEW-015, FR-NEW-040, FR-NEW-053
- **Given** The administrator.
- **When** He creates "Кардиология 2027", "أمراض الرئة" and "心臓病学".
- **Then** The three folders are listed with their names displayed correctly, the Arabic one reading right to left.
- **Priority:** Medium

#### E2E-098: Duplicate checks ignore case and surrounding spaces but not accents

- **Category:** edge (side effect)
- **Scenario:** SC-014
- **Requirements:** FR-NEW-040, FR-NEW-042
- **Given** The standard library.
- **When** The administrator creates "  CARDIOLOGY 2027 " (spaces around), then "Pneumo Ete" (no accent).
- **Then** The first shows A folder named "CARDIOLOGY 2027" already exists.; the second is created.
- **And** The home page lists 4 folders, with "Pneumo Ete" and "Pneumo Été" as two different folders.
- **Priority:** Medium

#### E2E-099: The administrator deletes a folder after retyping its name

- **Category:** happy (side effect, state transition)
- **Scenario:** SC-015
- **Requirements:** FR-NEW-043, FR-NEW-044, FR-NEW-049, FR-NEW-062
- **Given** "Pneumo Été" holds "Spirometry Basics" and has dan.rw@example.org as RW.
- **When** The administrator chooses to delete "Pneumo Été" and retypes "Pneumo Été".
- **Then** The home page lists 2 folders.
- **And** The operator's view of the library holds no trace of "Spirometry Basics" nor of its history, and no member of the deleted folder.
- **And** The activity list gains "Deleted folder "Pneumo Été"".
- **And** The exact retyped name was accepted: no "The name does not match. Nothing was deleted." appeared.
- **Priority:** Critical

#### E2E-100: A retyped name with a different case is refused

- **Category:** failure
- **Scenario:** SC-015
- **Requirements:** FR-NEW-043, FR-NEW-044
- **Given** "Pneumo Été" holds "Spirometry Basics" and has dan.rw@example.org as RW; the administrator has chosen to delete "Pneumo Été" and is asked to retype its name.
- **When** He retypes "pneumo été".
- **Then** "The name does not match. Nothing was deleted." is shown.
- **And** "Pneumo Été" and "Spirometry Basics" are still there.
- **Priority:** Critical

#### E2E-101: An empty retyped name is refused

- **Category:** failure
- **Scenario:** SC-015
- **Requirements:** FR-NEW-044
- **Given** "Pneumo Été" holds "Spirometry Basics" and has dan.rw@example.org as RW; the administrator has chosen to delete "Pneumo Été" and is asked to retype its name.
- **When** He confirms with nothing typed.
- **Then** "The name does not match. Nothing was deleted." is shown.
- **And** The folder is intact.
- **Priority:** High

#### E2E-102: A former member is refused after the folder is deleted

- **Category:** failure (state transition)
- **Scenario:** SC-015
- **Requirements:** FR-NEW-010, FR-NEW-043, FR-NEW-048
- **Given** "Pneumo Été" was deleted; dan.rw@example.org still had its folder page open.
- **When** He chooses a presentation of it.
- **Then** "Access denied." is shown.
- **And** His home page lists only "Cardiology 2027".
- **Priority:** High

#### E2E-103: A recreated folder is empty and has no member

- **Category:** edge (state transition)
- **Scenario:** SC-015
- **Requirements:** FR-NEW-040, FR-NEW-043, FR-NEW-048
- **Given** "Pneumo Été", which held "Spirometry Basics" and had dan.rw@example.org as RW, was deleted by the administrator.
- **When** The administrator creates a folder named "Pneumo Été" again.
- **Then** The folder is listed and opens with "This folder has no presentations yet."
- **And** Its member list is empty; dan.rw@example.org opening it sees "Access denied."
- **And** No request or AI suggestion of the 'Spirometry Basics' deck returns: its Requests list does not exist anywhere in the new folder.
- **Priority:** High

#### E2E-104: A folder of 100 presentations is deleted entirely

- **Category:** edge (side effect)
- **Scenario:** SC-015
- **Requirements:** FR-NEW-043, FR-NEW-060
- **Given** "Pneumo Été" holds 100 presentations "Deck 001" to "Deck 100".
- **When** The administrator opens it, then deletes it with the exact name.
- **Then** The folder page lists the 100 presentations within 2 seconds; after the deletion the folder is gone.
- **And** Recreating "Pneumo Été" shows an empty folder: none of the 100 decks returns.
- **And** None of the requests queued on the 100 presentations returns after the folder is created again.
- **Priority:** Medium

#### E2E-105: Saving into a deleted folder is refused

- **Category:** edge (side effect)
- **Scenario:** SC-015
- **Requirements:** FR-NEW-026, FR-NEW-043, FR-NEW-048
- **Given** dan.rw@example.org is editing "Spirometry Basics" in "Pneumo Été" (he is RW there); the administrator deletes the folder.
- **When** Dan leaves the edited field.
- **Then** "Access denied." is shown as the editor's only notice; his edited text stays on screen.
- **And** No folder "Pneumo Été" and no presentation are recreated.
- **Priority:** High

#### E2E-106: Deleting the last folder leaves the empty home page

- **Category:** edge (side effect, state transition)
- **Scenario:** SC-015
- **Requirements:** FR-NEW-016, FR-NEW-043, FR-NEW-049
- **Given** The administrator, and the only folder "Pneumo Été" (the two others were deleted before).
- **When** He deletes "Pneumo Été" by retyping its exact name and opens the home page.
- **Then** "You have no access to any folder yet." is shown.
- **And** The activity list holds "Deleted folder "Pneumo Été"" as its newest line.
- **Priority:** Medium

#### E2E-107: A retyped name without its accent is refused

- **Category:** edge
- **Scenario:** SC-015
- **Requirements:** FR-NEW-043, FR-NEW-044
- **Given** "Pneumo Été" holds "Spirometry Basics".
- **When** The administrator retypes "Pneumo Ete", then "Pneumo Été " (a space at the end).
- **Then** Each time "The name does not match. Nothing was deleted." is shown (for "Pneumo Ete" and for the name with a trailing space).
- **And** "Pneumo Été" and "Spirometry Basics" are intact.
- **And** In a further run, retyping "Pneumo Été" (accents as separate marks) is accepted and deletes the folder, because the retyped name is brought to its composed form first.
- **Priority:** Medium

#### E2E-108: The administrator adds a member

- **Category:** happy (side effect, state transition)
- **Scenario:** SC-016
- **Requirements:** FR-NEW-024, FR-NEW-045, FR-NEW-046, FR-NEW-049
- **Given** "Pneumo Été" has no member; dan.rw@example.org holds no role there.
- **When** The administrator adds dan.rw@example.org with the role RW.
- **Then** Dan's next page shows "Pneumo Été" labelled "Read and write" with "Upload" available.
- **And** The activity list gains "Added dan.rw@example.org as RW to "Pneumo Été"".
- **And** Adding dan.rw@example.org again with RW leaves one entry in the member list of "Pneumo Été".
- **Priority:** Critical

#### E2E-109: The administrator changes a role and removes a member

- **Category:** happy (side effect, state transition)
- **Scenario:** SC-016
- **Requirements:** FR-NEW-047, FR-NEW-048, FR-NEW-049
- **Given** "Cardiology 2027" has dan.rw@example.org RW and carol.ro@example.org RO.
- **When** The administrator changes Carol to RW, then removes Dan.
- **Then** Carol's next action shows the edit controls; Dan's next action is refused with "Access denied."
- **And** The activity list gains "Changed carol.ro@example.org to RW in "Cardiology 2027"" and "Removed dan.rw@example.org from "Cardiology 2027"".
- **Priority:** Critical

#### E2E-110: Invalid addresses are refused

- **Category:** failure
- **Scenario:** SC-016
- **Requirements:** FR-NEW-045, FR-NEW-046
- **Given** The administrator is adding a member to "Pneumo Été".
- **When** He types in turn "not-an-email", "carol@", an empty field.
- **Then** Each time "This is not a valid email address." is shown.
- **And** The member list of "Pneumo Été" is still empty.
- **Priority:** High

#### E2E-111: Two addresses in one field are refused

- **Category:** failure
- **Scenario:** SC-016
- **Requirements:** FR-NEW-046, FR-NEW-053
- **Given** The administrator.
- **When** He types "dan.rw@example.org, carol.ro@example.org" and, then, "<b>x</b>@example.org".
- **Then** Each time "This is not a valid email address." is shown; the second text is displayed as written, not in bold.
- **And** Neither address became a member.
- **Priority:** High

#### E2E-112: A RW member adds himself as Admin by hand

- **Category:** failure (side effect)
- **Scenario:** SC-016
- **Requirements:** FR-NEW-012, FR-NEW-013, FR-NEW-045
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; he sends by hand the adding of dan.rw@example.org with the role "Admin" to "Pneumo Été".
- **When** He sends it with his own session.
- **Then** "Access denied." is returned.
- **And** The member list of "Pneumo Été", seen by the administrator, is still empty and no "Administration" entry appears for Dan.
- **Priority:** High

#### E2E-113: An address already listed in other letter case with another role updates the entry

- **Category:** edge (side effect)
- **Scenario:** SC-016
- **Requirements:** FR-NEW-045, FR-NEW-047
- **Given** "Cardiology 2027" lists dan.rw@example.org RW.
- **When** The administrator adds "DAN.RW@Example.org" with the role "Read only".
- **Then** The list shows one entry, dan.rw@example.org in lower case, with the role RO.
- **And** Dan's next action in the folder is read only.
- **And** The activity list gains the line Changed dan.rw@example.org to RO in "Cardiology 2027".
- **Priority:** High

#### E2E-114: The administrator's own address can be listed

- **Category:** edge (side effect)
- **Scenario:** SC-016
- **Requirements:** FR-NEW-012, FR-NEW-014, FR-NEW-045
- **Given** The administrator.
- **When** He adds seb.morand@gmail.com as RO to "Pneumo Été".
- **Then** The entry is added; his label stays "Admin" and he can still upload there.
- **Priority:** Low

#### E2E-115: A trimmed address gives access without a new sign in

- **Category:** edge (state transition)
- **Scenario:** SC-016
- **Requirements:** FR-NEW-003, FR-NEW-022, FR-NEW-045, FR-NEW-046
- **Given** bob.nobody@gmail.com is signed in and sees "Access denied."
- **When** The administrator adds " bob.nobody@gmail.com " (with spaces around) as RO to "Cardiology 2027".
- **Then** The next page Bob opens is the home page with "Cardiology 2027" labelled "Read only".
- **And** The spaces around the address did not make it invalid.
- **And** The address is shown in lower case, "bob.nobody@gmail.com", without the spaces.
- **Priority:** Medium

#### E2E-116: A raised role applies on the next action

- **Category:** happy (side effect, state transition)
- **Scenario:** SC-017
- **Requirements:** FR-NEW-024, FR-NEW-047, FR-NEW-048
- **Given** carol.ro@example.org is viewing "Statins Review" as RO.
- **When** The administrator changes her to RW; Carol reloads.
- **Then** The edit controls appear and she changes a title and leaves the field: the change is stored.
- **And** The history of "Statins Review" lists the previous version.
- **Priority:** High

#### E2E-117: A removed member's change is refused

- **Category:** failure (side effect, state transition)
- **Scenario:** SC-017
- **Requirements:** FR-NEW-010, FR-NEW-026, FR-NEW-047, FR-NEW-048, FR-NEW-074
- **Given** dan.rw@example.org edits "Statins Review"; the administrator removes him from "Cardiology 2027" and from "Pneumo Été".
- **When** Dan leaves the edited field.
- **Then** "Access denied." is shown as the editor's only notice (no "Save failed:" in front); his edited text stays on screen.
- **And** carol.ro@example.org still sees the old text.
- **Priority:** Critical

#### E2E-118: A lowered role blocks the next stored change

- **Category:** failure (side effect, state transition)
- **Scenario:** SC-017
- **Requirements:** FR-NEW-023, FR-NEW-026, FR-NEW-047, FR-NEW-048
- **Given** dan.rw@example.org edits "Statins Review"; the administrator changes him to RO.
- **When** Dan leaves the edited field, then reloads.
- **Then** The first step shows "Access denied."; after the reload the editing controls are absent.
- **And** The stored text is unchanged.
- **Priority:** Critical

#### E2E-119: A download after the folder was deleted is refused

- **Category:** failure (state transition)
- **Scenario:** SC-017
- **Requirements:** FR-NEW-010, FR-NEW-022, FR-NEW-048
- **Given** carol.ro@example.org views "Heart Failure Update"; the administrator deletes "Cardiology 2027".
- **When** She chooses the PPTX download.
- **Then** "Access denied." is shown as the only text, with no "Export PPTX échoué :" in front of it, and no file is received.
- **And** The slide on her screen is still displayed.
- **And** The presentation stays on screen.
- **Priority:** High

#### E2E-120: A right removed during an upload stops it

- **Category:** edge (side effect)
- **Scenario:** SC-017
- **Requirements:** FR-NEW-028, FR-NEW-036, FR-NEW-048
- **Given** dan.rw@example.org is uploading a valid 25 MB "Big Deck.html"; at 50 percent the administrator removes him from "Cardiology 2027".
- **When** The upload ends.
- **Then** "Access denied." is shown.
- **And** No "Big Deck" is listed to the administrator; the activity list has no upload line.
- **Priority:** High

#### E2E-121: An open presenter window keeps what it loaded

- **Category:** edge (state transition)
- **Scenario:** SC-017
- **Requirements:** FR-NEW-022, FR-NEW-048
- **Given** carol.ro@example.org has the presenter window open on "Heart Failure Update"; the administrator removes her.
- **When** She moves through the 8 slides, then reloads the window.
- **Then** The slides already loaded still change; the reload shows "Access denied."
- **Priority:** Medium

#### E2E-122: Each member sees only their own folders

- **Category:** happy
- **Scenario:** SC-018
- **Requirements:** FR-NEW-015, FR-NEW-020, FR-NEW-021
- **Given** The library holds "WCBIP Melbourne Décembre 2026" (lamya.chrif@gmail.com RW), "Cardiology 2027" (dan.rw@example.org RW, carol.ro@example.org RO) and "Pneumo Été" (dan.rw@example.org RO).
- **When** dan.rw@example.org, carol.ro@example.org and lamya.chrif@gmail.com each open the home page and every page they can reach.
- **Then** Dan sees exactly "Cardiology 2027" and "Pneumo Été"; Carol sees only "Cardiology 2027"; Lamya sees only "WCBIP Melbourne Décembre 2026". No page of one shows a name of a folder or presentation of another, nor an email address of another person.
- **Priority:** Critical

#### E2E-123: A presentation of another folder cannot be reached by typing its address

- **Category:** failure
- **Scenario:** SC-018
- **Requirements:** FR-NEW-010, FR-NEW-020, FR-NEW-021
- **Given** dan.rw@example.org is RW in "Cardiology 2027" only; "Bridging the Gap" is in "WCBIP Melbourne Décembre 2026".
- **When** He types the address of "Bridging the Gap" in the folder "WCBIP Melbourne Décembre 2026", then the same presentation name under "Cardiology 2027".
- **Then** Both show "Access denied.", identical to each other.
- **And** No slide and no title of "Bridging the Gap" appears.
- **Priority:** Critical

#### E2E-124: Two folders each hold a "Statins Review"

- **Category:** edge (side effect)
- **Scenario:** SC-018
- **Requirements:** FR-NEW-020, FR-NEW-021, FR-NEW-033
- **Given** "Cardiology 2027" and "Pneumo Été" each hold a "Statins Review" with different content; dan.rw@example.org is RW in both.
- **When** He opens each in turn.
- **Then** Each opens its own folder's content; saving one leaves the other unchanged.
- **And** The administrator sees two distinct presentations.
- **Priority:** Medium

#### E2E-125: Dots, parentheses and apostrophes inside a name are accepted

- **Category:** happy (side effect)
- **Scenario:** SC-019
- **Requirements:** FR-NEW-028, FR-NEW-032, FR-NEW-053
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; valid files "Report.v2.final.html" and "L'été (v2).html".
- **When** He uploads both.
- **Then** "Uploaded Report.v2.final." and "Uploaded L'été (v2)." are shown; the folder lists both names exactly as written.
- **Priority:** Medium

#### E2E-126: Markup inside a check message is shown as written

- **Category:** failure
- **Scenario:** SC-019
- **Requirements:** FR-NEW-031, FR-NEW-053
- **Given** dan.rw@example.org; "Markup Deck.html" is declared as a presentation; its slides 1 and 2 both carry the identifier <b>x</b>.
- **When** He uploads it.
- **Then** The message This file is not a valid presentation: expected id "slide-0" but found "<b>x</b>". is shown with the characters <b>x</b> visible, not in bold.
- **And** No dialog and no formatting appears.
- **Priority:** High

#### E2E-127: Encoded and look alike names are refused

- **Category:** edge
- **Scenario:** SC-019
- **Requirements:** FR-NEW-032, FR-NEW-053
- **Given** dan.rw@example.org; valid files named "%2e%2e%2fsecret.html", "..\..\secret.html", "Report‮txt.html" (right to left override character) and a name containing a NUL character.
- **When** He uploads each in turn.
- **Then** Each time "This file name is not allowed." is shown.
- **And** The folder still lists 3 presentations.
- **Priority:** High

#### E2E-128: The initial content is there

- **Category:** happy (side effect)
- **Scenario:** SC-020
- **Requirements:** FR-NEW-015, FR-NEW-018, FR-NEW-024, FR-NEW-054
- **Given** The web library mode started for the first time.
- **When** seb.morand@gmail.com, then lamya.chrif@gmail.com, open the home page and the folder.
- **Then** Both see "WCBIP Melbourne Décembre 2026" (Lamya labelled "Read and write"); the folder lists "Bridging the Gap" (3.1 MB) before "From Challenges to Change" (3.7 MB), both with the modified time of the supplied files, 15 Nov 2026 19:57.
- **And** The activity list holds "No activity yet."
- **And** Opening "From Challenges to Change" shows 18 slides and "Bridging the Gap" 15.
- **Priority:** Critical

#### E2E-129: Other accounts see nothing of the initial content

- **Category:** failure
- **Scenario:** SC-020
- **Requirements:** FR-NEW-010, FR-NEW-020, FR-NEW-054
- **Given** The initial content is loaded; bob.nobody@gmail.com is in no list and carol.ro@example.org is RO in "Cardiology 2027" only.
- **When** Bob signs in; Carol opens the link to "Bridging the Gap".
- **Then** Bob sees "Access denied."; Carol sees "Access denied."
- **And** No title of the two decks appears to either.
- **Priority:** Critical

#### E2E-130: The seeded member is not an administrator

- **Category:** failure
- **Scenario:** SC-020
- **Requirements:** FR-NEW-013, FR-NEW-054
- **Given** lamya.chrif@gmail.com is signed in.
- **When** She opens the administration link.
- **Then** "Access denied." is shown.
- **Priority:** High

#### E2E-131: A restart does not reset or recreate the initial content

- **Category:** edge (side effect, state transition)
- **Scenario:** SC-020
- **Requirements:** FR-NEW-054, FR-NEW-062
- **Given** lamya.chrif@gmail.com deleted "Bridging the Gap" and changed the title of slide 1 of "From Challenges to Change"; the product restarts.
- **When** She opens her folder.
- **Then** Only "From Challenges to Change", with her changed title, is listed.
- **And** The administrator's activity list shows her deletion line, and no creation line from the restart.
- **Priority:** High

#### E2E-132: The seeded decks are unchanged and pass the upload checks

- **Category:** edge (side effect)
- **Scenario:** SC-020
- **Requirements:** FR-NEW-022, FR-NEW-031, FR-NEW-054
- **Given** "From Challenges to Change" and "Bridging the Gap" as seeded.
- **When** lamya.chrif@gmail.com downloads both HTML files, then the administrator uploads them into "Pneumo Été".
- **Then** The downloads are byte for byte the supplied decks (3 901 499 and 3 278 888 bytes); both uploads end with "Uploaded From Challenges to Change." and "Uploaded Bridging the Gap.", with no validation problem.
- **And** The public static site of these decks is still reachable without sign in and is unchanged.
- **Priority:** High

#### E2E-133: The local mode edits one file with no sign in

- **Category:** happy (side effect)
- **Scenario:** SC-021
- **Requirements:** FR-NEW-025, FR-NEW-055, FR-NEW-056
- **Given** An operator runs the local mode on talk.html, a presentation of 3 slides on their machine.
- **When** They open the editor, change the title of slide 1 to "Hello" (stored by itself), undo, open the presenter window and download the PPTX.
- **Then** No sign in is asked; everything works as in the previous version; the file talk.html holds "Hello".
- **And** The history of talk.html holds the previous version.
- **Priority:** Critical

#### E2E-134: The local mode and the web library mode run side by side

- **Category:** failure
- **Scenario:** SC-021
- **Requirements:** FR-NEW-055, FR-NEW-056, FR-NEW-057
- **Given** The web library mode runs at slides.scm-platform.org; the local mode runs on talk.html at the machine's own address.
- **When** The operator edits talk.html in the local mode (the change is stored by itself), then opens the library.
- **Then** The library asks for a Google sign in and shows nothing of talk.html; the local mode never asked for a sign in.
- **And** The library's folders and presentations are unchanged.
- **Priority:** High

#### E2E-135: No library page exists in the local mode

- **Category:** failure
- **Scenario:** SC-021
- **Requirements:** FR-NEW-055, FR-NEW-056
- **Given** The local mode on talk.html.
- **When** The operator asks the local address for a folder page and for the home page of the library.
- **Then** The local mode shows its own editor for talk.html only; no sign in page, no folder list.
- **Priority:** High

#### E2E-136: The local mode keeps refusing other host names

- **Category:** edge
- **Scenario:** SC-021
- **Requirements:** FR-NEW-055, FR-NEW-056, FR-NEW-059
- **Given** The local mode on talk.html.
- **When** A request reaches it through the host name slides.scm-platform.org.
- **Then** It is refused and nothing of talk.html is shown, as before this increment.
- **And** No sign in page was shown either.
- **Priority:** Medium

#### E2E-137: A local deck's script behaves as before

- **Category:** edge
- **Scenario:** SC-021
- **Requirements:** FR-NEW-052, FR-NEW-055
- **Given** talk.html carries a script that reads what the browser keeps for the local address.
- **When** The operator opens it in the local mode.
- **Then** The script works exactly as in the previous version.
- **Priority:** Low

#### E2E-138: The activity list records every kind of successful action

- **Category:** happy (side effect)
- **Scenario:** SC-022
- **Requirements:** FR-NEW-013, FR-NEW-049, FR-NEW-050
- **Given** A fresh library. dan.rw@example.org uploads "Quarterly Review", replaces it, deletes it; the administrator creates "Oncology 2030", adds dan.rw@example.org RW, changes him to RO, removes him, and deletes the folder.
- **When** The administrator opens the activity list.
- **Then** 8 lines are shown, newest first, each with its time and its email address in lower case: seb.morand@gmail.com for the 5 folder and member lines, dan.rw@example.org for the 3 presentation lines: Deleted folder "Oncology 2030"; Removed dan.rw@example.org from "Oncology 2030"; Changed dan.rw@example.org to RO in "Oncology 2030"; Added dan.rw@example.org as RW to "Oncology 2030"; Created folder "Oncology 2030"; Deleted "Quarterly Review" from "Cardiology 2027"; Replaced "Quarterly Review" in "Cardiology 2027"; Uploaded "Quarterly Review" in "Cardiology 2027".
- **Priority:** Critical

#### E2E-139: A member cannot read the activity list

- **Category:** failure
- **Scenario:** SC-022
- **Requirements:** FR-NEW-013, FR-NEW-020, FR-NEW-050
- **Given** dan.rw@example.org is signed in.
- **When** He asks for the activity list.
- **Then** "Access denied." is shown; no line is displayed.
- **Priority:** Critical

#### E2E-140: Refused attempts are not recorded

- **Category:** failure
- **Scenario:** SC-022
- **Requirements:** FR-NEW-003, FR-NEW-023, FR-NEW-049, FR-NEW-051
- **Given** carol.ro@example.org attempts by hand an upload and a deletion; bob.nobody@gmail.com signs in and is refused; then dan.rw@example.org successfully uploads "Quarterly Review" into "Cardiology 2027".
- **When** The administrator opens the activity list.
- **Then** The list holds exactly one line, Uploaded "Quarterly Review" in "Cardiology 2027", attributed to dan.rw@example.org; no line about Carol's attempts nor Bob's sign in.
- **And** The list does not show "No activity yet."
- **Priority:** High

#### E2E-141: Saves are not recorded

- **Category:** failure
- **Scenario:** SC-022
- **Requirements:** FR-NEW-026, FR-NEW-051
- **Given** dan.rw@example.org changes the title of "Statins Review" 3 times, leaving the field each time.
- **When** The administrator opens the activity list.
- **Then** The list has no line about these stored changes.
- **Priority:** High

#### E2E-142: Only the 500 latest lines are shown

- **Category:** edge
- **Scenario:** SC-022
- **Requirements:** FR-NEW-049, FR-NEW-050
- **Given** 501 successful actions were done, the first being the creation of the folder "Folder 001" and the last the creation of "Folder 501".
- **When** The administrator opens the activity list.
- **Then** 500 lines are shown, the first being "Created folder "Folder 501"" and the last "Created folder "Folder 002""; no line about "Folder 001".
- **Priority:** Medium

#### E2E-143: An empty activity list says so

- **Category:** edge
- **Scenario:** SC-022
- **Requirements:** FR-NEW-050, FR-NEW-054
- **Given** A library that holds only its initial content.
- **When** The administrator opens the activity list.
- **Then** "No activity yet." is shown.
- **Priority:** Low

#### E2E-144: Accented names with apostrophes are shown as written

- **Category:** edge
- **Scenario:** SC-022
- **Requirements:** FR-NEW-032, FR-NEW-049, FR-NEW-053
- **Given** dan.rw@example.org uploads "L'été (v2).html" into "Pneumo Été".
- **When** The administrator opens the activity list.
- **Then** The line reads Uploaded "L'été (v2)" in "Pneumo Été" exactly, attributed to dan.rw@example.org.
- **Priority:** Low

#### E2E-145: The address shows the sign in page securely

- **Category:** happy
- **Scenario:** SC-023
- **Requirements:** FR-NEW-001, FR-NEW-057, FR-NEW-058, FR-NEW-059, FR-NEW-065
- **Given** A visitor with no session.
- **When** He opens slides.scm-platform.org through a secure connection.
- **Then** The sign in page is shown with the single action "Sign in with Google"; every text of the page is in English.
- **And** The browser shows no security warning.
- **Priority:** Critical

#### E2E-146: The plain address is sent to the secure one

- **Category:** failure (side effect)
- **Scenario:** SC-023
- **Requirements:** FR-NEW-057, FR-NEW-058
- **Given** A visitor with no session.
- **When** He opens the plain, unencrypted form of slides.scm-platform.org.
- **Then** He lands on the sign in page through the secure connection, never served in the clear.
- **And** No library content was sent over the plain connection.
- **Priority:** Critical

#### E2E-147: Another host name is refused

- **Category:** failure
- **Scenario:** SC-023
- **Requirements:** FR-NEW-001, FR-NEW-057, FR-NEW-059
- **Given** The product answers on the same machine under the name evil.example.
- **When** A request reaches it through the host name evil.example.
- **Then** It is refused and nothing of the library, not even the sign in page, is shown, except the liveness answer, which stays available and shows nothing of the library.
- **Priority:** High

#### E2E-148: A plain direct link keeps its destination

- **Category:** edge (state transition)
- **Scenario:** SC-023
- **Requirements:** FR-NEW-009, FR-NEW-058
- **Given** carol.ro@example.org has no session and opens the plain form of the link to "Heart Failure Update".
- **When** She follows it and signs in.
- **Then** She is sent to the secure form of the same link and, after signing in, sees "Heart Failure Update".
- **Priority:** Medium

#### E2E-149: Any other page gives the sign in page when signed out and Access denied when signed in

- **Category:** edge
- **Scenario:** SC-023
- **Requirements:** FR-NEW-001, FR-NEW-010, FR-NEW-013, FR-NEW-057
- **Given** A visitor with no session.
- **When** He opens two addresses of the site that name no page: one made up, and one reading "admin".
- **Then** Each shows the sign in page, no different from the home address.
- **And** After dan.rw@example.org signs in, the same two addresses each show exactly "Access denied." with the "Sign out" button and nothing else.
- **Priority:** Medium

#### E2E-150: Google reports a failure after the person chose an account

- **Category:** edge (state transition)
- **Scenario:** SC-023
- **Requirements:** FR-NEW-002, FR-NEW-004, FR-NEW-057
- **Given** The sign in return address of slides.scm-platform.org is not registered in the owner's Google console; a visitor has no session.
- **When** He chooses "Sign in with Google" and picks lamya.chrif@gmail.com.
- **Then** The sign in page is shown with "Sign-in is unavailable. Try again later." and he stays signed out.
- **And** After the owner registers the return address, the same steps sign him in and show "WCBIP Melbourne Décembre 2026".
- **Priority:** High

#### E2E-151: A change is stored 0.8 seconds after typing stops

- **Category:** happy (side effect)
- **Scenario:** SC-007
- **Requirements:** FR-NEW-024, FR-NEW-026, FR-NEW-066
- **Given** dan.rw@example.org has "Heart Failure Update" open in edit mode, carol.ro@example.org has it open in view.
- **When** Dan types "Heart Failure Update 2027" as the title of slide 1, stays in the field and waits 1 second.
- **Then** The change is stored: Carol, reloading, sees "Heart Failure Update 2027".
- **And** The editor shows no Save control and no notice; the history holds the previous version titled "Heart Failure Update".
- **Priority:** Critical

#### E2E-152: A change that cannot be stored shows the notice and is kept on screen

- **Category:** failure (side effect, state transition)
- **Scenario:** SC-007
- **Requirements:** FR-NEW-017, FR-NEW-026, FR-NEW-066
- **Given** dan.rw@example.org is editing "Heart Failure Update"; at this moment the stored library cannot be written.
- **When** He types "Heart Failure Update 2027" and waits 1 second.
- **Then** The editor shows its usual failure notice with the reason; the typed title stays on screen.
- **And** Carol, reloading, still sees "Heart Failure Update".
- **And** When the library can be written again, Dan types "!" and waits 1 second: the title "Heart Failure Update 2027!" is stored, the notice disappears.
- **Priority:** High

#### E2E-153: Typing without a pause of 0.8 seconds is stored once at the end

- **Category:** edge (side effect)
- **Scenario:** SC-007
- **Requirements:** FR-NEW-025, FR-NEW-026, FR-NEW-066
- **Given** dan.rw@example.org is editing "Statins Review".
- **When** He types 40 characters over 5 seconds, never pausing more than 0.5 seconds, and then stops.
- **Then** While he types, a reload by carol.ro@example.org still shows the old text; 1 second after he stops, the whole text is stored.
- **And** The history of "Statins Review" gains exactly one version.
- **And** In another run he leaves the field 0.2 seconds after typing: the text is stored at once.
- **Priority:** Medium

#### E2E-154: An error of the editor's charter rules blocks an upload

- **Category:** failure (side effect)
- **Scenario:** SC-009
- **Requirements:** FR-NEW-028, FR-NEW-031
- **Given** dan.rw@example.org; "Medical Deck.html" is declared as a presentation of the medical charter with 1 slide that holds a picture and no source line.
- **When** He uploads it.
- **Then** "This file is not a valid presentation: slide has an image and no source line." is shown.
- **And** Nothing is added to the folder; the activity list has no new line.
- **Priority:** High

#### E2E-155: A warning listed first is never the first problem

- **Category:** edge
- **Scenario:** SC-009
- **Requirements:** FR-NEW-031
- **Given** dan.rw@example.org; "Logo Deck.html" has a picture loaded from https://example.org/logo.png outside every slide (the editor lists that warning first) and 2 slides, the second lacking its title attribute.
- **When** He uploads it.
- **Then** "This file is not a valid presentation: missing attribute data-title." is shown.
- **And** The message does not mention the picture and does not name the slide.
- **Priority:** High

#### E2E-156: The controls the mode adds carry their exact names

- **Category:** edge
- **Scenario:** SC-013
- **Requirements:** FR-NEW-011, FR-NEW-040, FR-NEW-045, FR-NEW-067
- **Given** seb.morand@gmail.com is signed in; carol.ro@example.org is RO in "Cardiology 2027".
- **When** He opens "Cardiology 2027" from the home page, then "Administration".
- **Then** The folder page offers "All folders". The administration shows "Folders" and "Activity"; the field "Folder name" with "Create folder"; for "Cardiology 2027" the button "Delete folder" and the "Members" with the field "Email address", the chooser "Role" ("Read and write", "Read only"), the button "Add member"; for the member carol.ro@example.org a role chooser showing "Read only" and the button "Remove".
- **And** Pressing "All folders" returns to the home page.
- **And** With members dan.rw@example.org, carol.ro@example.org and Alice.RO@example.org (stored as alice.ro@example.org) in "Cardiology 2027", the members are listed alice.ro@example.org, carol.ro@example.org, dan.rw@example.org; the folders are listed as on the home page.
- **Priority:** High

#### E2E-157: The folder deletion prompt can be cancelled

- **Category:** failure (side effect)
- **Scenario:** SC-015
- **Requirements:** FR-NEW-043, FR-NEW-044, FR-NEW-067
- **Given** seb.morand@gmail.com is on the administration; "Pneumo Été" holds "Spirometry Basics".
- **When** He presses "Delete folder" next to "Pneumo Été", then "Cancel".
- **Then** The prompt "Type the folder name to confirm." with the buttons "Delete folder" and "Cancel" is shown first; after "Cancel" the prompt is gone.
- **And** "Pneumo Été" and "Spirometry Basics" are intact; the activity list has no new line.
- **Priority:** High

#### E2E-158: The progress percent is a whole number rounded down

- **Category:** edge
- **Scenario:** SC-011
- **Requirements:** FR-NEW-035, FR-NEW-067
- **Given** dan.rw@example.org uploads "Big Deck.html" (26 214 400 bytes) on a slow connection.
- **When** He watches the progress when 8 880 000 bytes (33.87 percent) and when 26 214 000 bytes (99.998 percent) have been sent.
- **Then** The texts read "Big Deck.html 33%" and "Big Deck.html 99%".
- **And** "Big Deck.html 100%" is shown only together with, or after, "Uploaded Big Deck."
- **Priority:** Medium

#### E2E-159: A library whose every folder was deleted is not seeded again

- **Category:** edge (state transition)
- **Scenario:** SC-020
- **Requirements:** FR-NEW-016, FR-NEW-054, FR-NEW-062
- **Given** The initial content was created; the administrator then deleted "WCBIP Melbourne Décembre 2026", the only folder.
- **When** The product restarts and seb.morand@gmail.com opens the home page.
- **Then** "You have no access to any folder yet." is shown.
- **And** lamya.chrif@gmail.com signs in and sees "Access denied." (she holds no role anywhere).
- **Priority:** High

#### E2E-160: Adding the same address with the same role changes nothing

- **Category:** edge (side effect)
- **Scenario:** SC-016
- **Requirements:** FR-NEW-045
- **Given** "Pneumo Été" has no member.
- **When** The administrator adds "Dan.RW@Example.ORG" as "Read and write", then adds "dan.rw@example.org" as "Read and write" again.
- **Then** The list shows one entry, dan.rw@example.org in lower case, "Read and write".
- **And** The activity list holds one line, Added dan.rw@example.org as RW to "Pneumo Été"; the second addition adds no line.
- **Priority:** Medium

#### E2E-161: A role other than the two offered is refused

- **Category:** failure (side effect)
- **Scenario:** SC-016
- **Requirements:** FR-NEW-012, FR-NEW-045
- **Given** seb.morand@gmail.com is on the administration; "Pneumo Été" has no member; from a command line tool outside the editor he sends the addition of dan.rw@example.org with the role "Admin".
- **When** He sends it.
- **Then** "This is not a valid role." is returned.
- **And** The member list of "Pneumo Été" is still empty and the activity list has no new line; Dan's home page has no "Administration".
- **Priority:** High

#### E2E-162: File names: composed form, 100 characters, edge spaces

- **Category:** edge (side effect)
- **Scenario:** SC-010
- **Requirements:** FR-NEW-032, FR-NEW-033
- **Given** dan.rw@example.org; "Café Study" (the é as one letter) exists in "Cardiology 2027"; valid files exist named with the e followed by an accent mark ("Café Study.html"), with 100 letters "A" before ".html", with 101, " Lead.html" (space first), "Tail .html" (space before the dot) and "   .html" (only spaces).
- **When** He uploads each in turn.
- **Then** The first meets the question A presentation named "Café Study" already exists. Replace it?; the 100 letter name is accepted ("Uploaded <name>."); the 101 letter name, " Lead.html", "Tail .html" and "   .html" each show "This file name is not allowed."
- **And** The folder holds one "Café Study" and the 100 letter presentation, nothing else added.
- **Priority:** High

#### E2E-163: Folder names: composed form and length counted after it

- **Category:** edge (side effect)
- **Scenario:** SC-014
- **Requirements:** FR-NEW-040, FR-NEW-041, FR-NEW-042
- **Given** The administrator; "Pneumo Été" exists.
- **When** He creates "Pneumo Été" (accents as separate marks), then a name of 60 letters "é" each written as e plus a mark, then 61 such letters.
- **Then** The first shows A folder named "Pneumo Été" already exists.; the second is created; the third shows "Folder names use 1 to 60 letters, digits, spaces or hyphens."
- **And** The home page lists the folders with the composed names.
- **Priority:** Medium

#### E2E-164: Rounding of sizes and display of times

- **Category:** edge
- **Scenario:** SC-004
- **Requirements:** FR-NEW-018
- **Given** A folder holds presentations of 1 075, 1 076, 1 048 575 and 1 572 864 bytes; they were modified 5 Nov 2026 09:05:59 UTC, 12 Nov 2026 23:59:59 UTC, 1 Dec 2026 00:00:00 UTC and 30 Sep 2026 12:00:00 UTC respectively; person in UTC.
- **When** A member opens the folder.
- **Then** The sizes read "1.0 KB" (1 075 bytes, exact value 1.0498), "1.1 KB" (1 076), "1024.0 KB" (1 048 575) and "1.5 MB"; the times read "5 Nov 2026 09:05", "12 Nov 2026 23:59", "1 Dec 2026 00:00" and "30 Sep 2026 12:00" (24 hour clock, no leading zero on the day, seconds dropped).
- **Priority:** Medium

#### E2E-165: Folders are ordered digits, Latin letters, other alphabets

- **Category:** edge
- **Scenario:** SC-003
- **Requirements:** FR-NEW-015
- **Given** The administrator, and folders "Кардиология", "Zeta", "Éclair", "2027 Review", "alpha", "Été".
- **When** He opens the home page.
- **Then** The order is "2027 Review", "alpha", "Éclair", "Été", "Zeta", "Кардиология".
- **Priority:** Medium

#### E2E-166: A signed in person stays signed in after a restart

- **Category:** edge (state transition)
- **Scenario:** SC-002
- **Requirements:** FR-NEW-005, FR-NEW-062
- **Given** lamya.chrif@gmail.com signed in 10 days ago; the product restarts.
- **When** She opens the home page.
- **Then** "WCBIP Melbourne Décembre 2026" is listed with no Google step.
- **And** Her session still ends 20 days from now, not 30.
- **Priority:** High

#### E2E-167: An ended session shows one notice, soon, and no connection notice

- **Category:** failure (side effect)
- **Scenario:** SC-002
- **Requirements:** FR-NEW-006, FR-NEW-007
- **Given** dan.rw@example.org is editing "Heart Failure Update"; his session ended 10 seconds ago and he has typed nothing since.
- **When** He types "!" at the end of a title and waits.
- **Then** Within 2 seconds of the typing stopping, "Your session has expired. Sign in again to save." is shown; neither "Save failed:" nor "Connection to the editor server lost" appears in the following 10 seconds.
- **And** The typed "!" stays on screen; carol.ro@example.org's view is unchanged.
- **Priority:** High

#### E2E-168: A folder of 100 presentations lists within 2 seconds

- **Category:** happy
- **Scenario:** SC-004
- **Requirements:** FR-NEW-018, FR-NEW-060
- **Given** "Cardiology 2027" holds 100 presentations "Deck 001" to "Deck 100"; carol.ro@example.org on a 50 megabit per second connection.
- **When** She opens the folder.
- **Then** All 100 presentations are listed, within 2 seconds, newest first, each with its name, date and size.
- **Priority:** Medium

#### E2E-169: Sign ins and sign outs are not recorded

- **Category:** edge
- **Scenario:** SC-022
- **Requirements:** FR-NEW-049, FR-NEW-051
- **Given** A library with the initial content; dan.rw@example.org signs in and out 3 times and uploads "Quarterly Review" once.
- **When** The administrator opens the activity list.
- **Then** Exactly one line is shown, Uploaded "Quarterly Review" in "Cardiology 2027".
- **Priority:** Medium

#### E2E-170: A notice added inside the editor is in English next to French labels

- **Category:** failure
- **Scenario:** SC-007
- **Requirements:** FR-NEW-010, FR-NEW-048, FR-NEW-065
- **Given** dan.rw@example.org is editing "Statins Review"; the administrator removes him from "Cardiology 2027".
- **When** He leaves the edited field.
- **Then** The notice reads "Access denied." (English) while the toolbar still reads "Édition", "Annuler" and "Rétablir".
- **Priority:** Medium

#### E2E-171: An unverified address of an unlisted account gives the same message

- **Category:** edge
- **Scenario:** SC-001
- **Requirements:** FR-NEW-003, FR-NEW-068
- **Given** Google returns the account bob.nobody@gmail.com, who is in no list, with the address marked not verified; and lamya.chrif@gmail.com, who is listed, also marked not verified.
- **When** Each signs in.
- **Then** Both see "Sign-in is unavailable. Try again later." and stay signed out; neither sees "Access denied.".
- **And** After Google marks lamya.chrif@gmail.com verified she signs in normally.
- **Priority:** High

#### E2E-172: Destinations that leave the product are ignored

- **Category:** edge
- **Scenario:** SC-001
- **Requirements:** FR-NEW-009, FR-NEW-069
- **Given** carol.ro@example.org has no session.
- **When** She opens the sign in link with the destinations //evil.example/x, \evil.example, javascript:alert(1), https://slides.scm-platform.org@evil.example/x, /\evil.example and "slides.scm-platform.org.evil.example" in turn, and signs in each time.
- **Then** Each time she arrives on the home page of slides.scm-platform.org with "Cardiology 2027" listed.
- **Priority:** High

#### E2E-173: A session that ended gives a quiet screen until the person acts

- **Category:** happy (state transition)
- **Scenario:** SC-017
- **Requirements:** FR-NEW-007, FR-NEW-048, FR-NEW-074
- **Given** dan.rw@example.org has "Heart Failure Update" open in edit mode and has typed nothing; his session reaches 30 days.
- **When** He waits 60 seconds without touching anything.
- **Then** The presentation stays on screen with no notice at all: neither "Your session has expired. Sign in again to save." nor "Connection to the editor server lost".
- **And** He chooses the HTML download: the sign in page is shown, and nothing was stored.
- **And** In a variant where he has typed "!" unstored, the PPTX download is not made and "Your session has expired. Sign in again to save." is shown; with nothing unstored, choosing the PPTX download shows the sign in page and no file is received.
- **Priority:** High

#### E2E-174: A file that is not valid UTF-8 text is refused with no location

- **Category:** failure (side effect)
- **Scenario:** SC-009
- **Requirements:** FR-NEW-028, FR-NEW-031, FR-NEW-053
- **Given** dan.rw@example.org; "Latin Deck.html" is an otherwise valid presentation saved in a Western single byte encoding, with the letter é written as the single byte E9, 1 258 291 bytes.
- **When** He uploads it.
- **Then** "This file is not a valid presentation: the file is not valid UTF-8 text." is shown.
- **And** The message carries no byte position, line number or server path.
- **And** Nothing is added to the folder.
- **Priority:** High

#### E2E-175: File names accept Latin-script letters and the straight apostrophe only

- **Category:** edge (side effect)
- **Scenario:** SC-009
- **Requirements:** FR-NEW-028, FR-NEW-032
- **Given** dan.rw@example.org; valid files named "Łódź Study.html", "Øresund Plan.html", "Cœur Étude.html", "Straße Report.html" and "Dan’s Deck.html" (curly apostrophe).
- **When** He uploads each in turn.
- **Then** The first four end with "Uploaded <name>."; the last shows "This file name is not allowed."
- **And** The folder lists the four accepted names exactly as written.
- **Priority:** Medium

#### E2E-176: Email address forms: plus sign accepted, apostrophe and missing dot refused

- **Category:** failure (side effect)
- **Scenario:** SC-016
- **Requirements:** FR-NEW-045, FR-NEW-046
- **Given** The administrator is adding members to "Pneumo Été".
- **When** He adds "dan+rw@example.org" (Read and write), then "o'brien@example.org", "dan@localhost" and "dan rw@example.org".
- **Then** The first is added; each of the other three shows "This is not a valid email address."
- **And** The member list holds only dan+rw@example.org.
- **Priority:** Medium

#### E2E-177: A removed right gives a quiet screen, then Access denied on the next action

- **Category:** failure (state transition)
- **Scenario:** SC-017
- **Requirements:** FR-NEW-010, FR-NEW-048, FR-NEW-074
- **Given** dan.rw@example.org has "Statins Review" open in edit mode and has typed nothing; the administrator removes him from "Cardiology 2027".
- **When** He waits 60 seconds, then chooses the PPTX download.
- **Then** The screen stays quiet for the 60 seconds (no notice); the download then shows "Access denied." and no file is received.
- **And** The presentation was never altered and carol.ro@example.org still sees it unchanged.
- **Priority:** High

#### E2E-178: Moving between slides is not an action that needs the library

- **Category:** edge (state transition)
- **Scenario:** SC-017
- **Requirements:** FR-NEW-074
- **Given** carol.ro@example.org has "Heart Failure Update" open; the administrator deletes "Cardiology 2027".
- **When** She moves from slide 1 to slide 3 with the arrow keys, then chooses the HTML download.
- **Then** The slides change with no notice; the download then shows "Access denied."
- **Priority:** Medium

#### E2E-179: An empty file is refused as not declared

- **Category:** edge (side effect)
- **Scenario:** SC-009
- **Requirements:** FR-NEW-028, FR-NEW-031
- **Given** dan.rw@example.org; "Nothing.html" has 0 bytes.
- **When** He uploads it.
- **Then** "This file is not a valid presentation: the file is not declared as a presentation." is shown.
- **And** Nothing is added to the folder.
- **Priority:** Medium

#### E2E-180: Library controls per page

- **Category:** edge
- **Scenario:** SC-001
- **Requirements:** FR-NEW-008, FR-NEW-067
- **Given** seb.morand@gmail.com is signed in.
- **When** He opens the home page, the folder page of "Cardiology 2027", "Administration", a presentation, then presses the Back button of the browser.
- **Then** The home page and the folder page show "Sign out"; the folder page also shows "All folders"; the administration shows "All folders" and "Sign out"; the presentation shows no library control of its own; Back returns to the folder page.
- **Priority:** Medium

#### E2E-181: Changes made from the library's own pages are accepted

- **Category:** happy (side effect)
- **Scenario:** SC-019
- **Requirements:** FR-NEW-024, FR-NEW-028, FR-NEW-070
- **Given** dan.rw@example.org is signed in on slides.scm-platform.org.
- **When** He uploads "Quarterly Review.html" and then deletes it, both from the library's pages.
- **Then** "Uploaded Quarterly Review." is shown, then the presentation is gone.
- **And** No "Access denied." appeared.
- **Priority:** High

#### E2E-182: A look alike site is another site

- **Category:** edge (side effect)
- **Scenario:** SC-019
- **Requirements:** FR-NEW-070
- **Given** dan.rw@example.org is signed in; a page at https://slides.scm-platform.org.evil.example submits the deletion of "Statins Review" in his browser.
- **When** The page loads.
- **Then** "Access denied." is returned to the page.
- **And** The administrator's view of "Cardiology 2027" still lists "Statins Review".
- **Priority:** High

#### E2E-183: Two sign ins started in two tabs each complete

- **Category:** happy (state transition)
- **Scenario:** SC-001
- **Requirements:** FR-NEW-002, FR-NEW-071
- **Given** carol.ro@example.org has no session and starts a sign in in two tabs of the same browser.
- **When** She completes the sign in in the second tab, then in the first.
- **Then** Each tab ends on the home page listing "Cardiology 2027" with no "Sign-in is unavailable. Try again later."
- **Priority:** Medium

#### E2E-184: A sign in answer cannot be used twice

- **Category:** edge
- **Scenario:** SC-001
- **Requirements:** FR-NEW-071
- **Given** carol.ro@example.org signed in once; a copy of the address that carried the answer of that sign in is kept; she then signed out.
- **When** The copy is opened in her browser.
- **Then** "Sign-in is unavailable. Try again later." is shown and she stays signed out.
- **And** Opening the home page shows the sign in page.
- **Priority:** High

#### E2E-185: Signing out in one tab ends the session in the other tab

- **Category:** edge (state transition)
- **Scenario:** SC-001
- **Requirements:** FR-NEW-008, FR-NEW-072
- **Given** carol.ro@example.org is signed in with two tabs of the folder page of "Cardiology 2027".
- **When** She chooses "Sign out" in the first tab, then chooses "Heart Failure Update" in the second.
- **Then** The second tab shows the sign in page, not the presentation.
- **Priority:** Medium

#### E2E-186: The health check works without sign in and shows little

- **Category:** happy
- **Scenario:** SC-023
- **Requirements:** FR-NEW-059, FR-NEW-073
- **Given** The product runs; the operator's health check has no session.
- **When** It asks whether the product is running.
- **Then** The answer says the product is running and gives its version, 1 field of each; it succeeds.
- **And** The answer holds no file location, process number or presentation name.
- **And** The answer is the same when the check reaches the product as 127.0.0.1 and as evil.example.
- **Priority:** High

#### E2E-187: A presentation's status is shown only to a person with a right on it

- **Category:** edge
- **Scenario:** SC-023
- **Requirements:** FR-NEW-010, FR-NEW-073
- **Given** carol.ro@example.org is RO in "Cardiology 2027" only.
- **When** She asks the status of "Heart Failure Update", then of "Bridging the Gap" in "WCBIP Melbourne Décembre 2026".
- **Then** The first status shows the change marker and no storage location; the second shows "Access denied."
- **And** A visitor with no session asking either gets the sign in page.
- **Priority:** High

#### E2E-188: A change stored after signing in again meets the conflict notice when someone else changed the presentation

- **Category:** edge (state transition)
- **Scenario:** SC-002
- **Requirements:** FR-NEW-007, FR-NEW-027
- **Given** dan.rw@example.org has typed "Statins B" in "Statins Review" and his session ended; he signs in again in another window; meanwhile the administrator stored the title "Statins A".
- **When** Dan leaves the field in the first window.
- **Then** The notice "The file changed on disk. Reload to see the changes, or keep your version." is shown with "Keep mine" and "Reload".
- **And** Nothing of Dan's is stored until he chooses.
- **Priority:** Medium

#### E2E-189: Two people leaving their fields in the same second leave one stored version

- **Category:** edge (side effect)
- **Scenario:** SC-008
- **Requirements:** FR-NEW-026, FR-NEW-027
- **Given** dan.rw@example.org and seb.morand@gmail.com have typed "Statins B" and "Statins A" in the title of "Statins Review" and are about to leave their fields.
- **When** Both leave their fields within the same second.
- **Then** One title is stored; the other person is shown the conflict notice.
- **And** The stored title is exactly one of "Statins A" or "Statins B", never a mix, and the history holds the earlier version.
- **Priority:** Medium

### 9.3 Exploit tests

#### E2E-SEC-001: A RO member uploads a path traversal name

- **Category:** security
- **Covers:** Class A occurrences #3 and #5
- **Red before the fix because:** the file is written one level above the folder; the assertion "no entry named passwd anywhere in the library storage" fails.
- **Scenario:** SC-019
- **Requirements:** FR-NEW-010, FR-NEW-021, FR-NEW-023, FR-NEW-032
- **Given** carol.ro@example.org is RO in "Cardiology 2027"; she sends by hand the upload of a valid presentation named "../../etc/passwd.html" with her own session.
- **When** She sends it.
- **Then** "Access denied." is returned.
- **And** The operator's listing of everything the library stores, every folder and every history, contains no entry named "passwd" and nothing outside the folders.
- **And** The administrator's view of "Cardiology 2027" is unchanged: 3 presentations; the activity list has no new line.
- **Priority:** Critical

#### E2E-SEC-002: A RW member uploads a path traversal name

- **Category:** security
- **Covers:** Class A occurrences #3 and #5
- **Red before the fix because:** the name is cleaned to "passwd.html" and stored; the assertion "no entry named passwd" fails.
- **Scenario:** SC-019
- **Requirements:** FR-NEW-021, FR-NEW-032, FR-NEW-053
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; the file named "../../etc/passwd.html" is a valid presentation.
- **When** He uploads it.
- **Then** "This file name is not allowed." is shown.
- **And** The operator's listing of everything the library stores contains no entry named "passwd" and nothing outside the folders.
- **And** The administrator's view lists the same 3 presentations in "Cardiology 2027" and the same folders; lamya.chrif@gmail.com still sees her 2 presentations.
- **Priority:** Critical

#### E2E-SEC-003: A name that looks like a data erasing command is refused

- **Category:** security
- **Covers:** Class A occurrence #3
- **Red before the fix because:** a build that accepts any name stores "a'; DROP TABLE users;--"; the assertion "no presentation with that name in any folder, seen by the administrator" fails.
- **Scenario:** SC-019
- **Requirements:** FR-NEW-032, FR-NEW-053
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; the valid file is named "a'; DROP TABLE users;--.html".
- **When** He uploads it.
- **Then** "This file name is not allowed." is shown.
- **And** The administrator's view of every folder is unchanged, with the same members and roles; no presentation with that name exists.
- **And** lamya.chrif@gmail.com and carol.ro@example.org can still sign in and see their folders.
- **Priority:** Critical

#### E2E-SEC-004: A name carrying a script tag is refused

- **Category:** security
- **Covers:** Class A occurrence #3
- **Red before the fix because:** the name is stored and shown without escaping; the assertion "no dialog appears on the administrator's folder page" fails.
- **Scenario:** SC-019
- **Requirements:** FR-NEW-032, FR-NEW-053
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; the valid file is named "<script>alert(1)</script>.html".
- **When** He uploads it, then opens the folder page.
- **Then** "This file name is not allowed." is shown.
- **And** The administrator's folder page and activity list show no such name and display no alert dialog.
- **And** carol.ro@example.org's folder page shows no dialog either.
- **Priority:** Critical

#### E2E-SEC-005: A folder named two dots is refused

- **Category:** security
- **Covers:** Class A occurrence #3
- **Red before the fix because:** a folder named ".." is created and later uploads land one level up; the assertion "3 folders listed and nothing outside the folders" fails.
- **Scenario:** SC-019
- **Requirements:** FR-NEW-021, FR-NEW-041, FR-NEW-053
- **Given** seb.morand@gmail.com is signed in.
- **When** He creates a folder named "..".
- **Then** "Folder names use 1 to 60 letters, digits, spaces or hyphens." is shown.
- **And** The home page still lists 3 folders.
- **And** The operator's listing of everything the library stores shows no new area and nothing outside the folders; uploading "Quarterly Review.html" by dan.rw@example.org into "Cardiology 2027" afterwards still lands only there.
- **Priority:** Critical

#### E2E-SEC-006: A RO member sends a 30 MB file

- **Category:** security
- **Covers:** Classes B occurrence #1 and D occurrence #1
- **Red before the fix because:** the whole 30 MB is received and stored; the assertion "the administrator lists 3 presentations" fails.
- **Scenario:** SC-019
- **Requirements:** FR-NEW-010, FR-NEW-023, FR-NEW-030, FR-NEW-060
- **Given** carol.ro@example.org is RO in "Cardiology 2027"; she sends by hand the upload of "Huge.html" of 31 457 280 bytes (30 MB) with her own session.
- **When** She sends it.
- **Then** "Access denied." is returned, without waiting for the whole file to be sent.
- **And** The library stores nothing: the administrator's view lists 3 presentations; the free space of the library is unchanged.
- **And** lamya.chrif@gmail.com browses her folder without delay during the attempt.
- **Priority:** Critical

#### E2E-SEC-007: A RW member sends a 30 MB file

- **Category:** security
- **Covers:** Class D occurrence #1
- **Red before the fix because:** the 30 MB presentation is stored; the assertion "no Huge listed to the administrator" fails.
- **Scenario:** SC-019
- **Requirements:** FR-NEW-030, FR-NEW-038
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; "Huge.html" is a valid presentation of 31 457 280 bytes (30 MB).
- **When** He uploads it.
- **Then** "The file is larger than 25 MB." is shown.
- **And** The administrator's view lists 3 presentations and no "Huge"; the free space of the library is unchanged.
- **And** lamya.chrif@gmail.com browses her folder without delay during the attempt.
- **Priority:** Critical

#### E2E-SEC-008: A RO member stores a change by hand

- **Category:** security
- **Covers:** Class B occurrences #1 and #6
- **Red before the fix because:** the change is stored; the assertion "the title seen by dan.rw@example.org is Heart Failure Update" fails and shows HACKED.
- **Scenario:** SC-005
- **Requirements:** FR-NEW-010, FR-NEW-023, FR-NEW-026
- **Given** carol.ro@example.org is signed in and RO in "Cardiology 2027"; with her own signed in session, from a command line tool outside the editor, she sends the request the editor sends when it stores a change to "Heart Failure Update" in "Cardiology 2027", the full text of the presentation having the title of slide 1 replaced by "HACKED".
- **When** She sends that request.
- **Then** "Access denied." is returned and nothing is saved.
- **And** dan.rw@example.org opens "Heart Failure Update" and sees the title "Heart Failure Update"; its size is still 2 097 152 bytes.
- **And** The history lists no new version.
- **Priority:** Critical

#### E2E-SEC-009: A RO member deletes by hand

- **Category:** security
- **Covers:** Class B occurrence #1
- **Red before the fix because:** the presentation is removed; the assertion "Statins Review is still listed to the administrator" fails.
- **Scenario:** SC-005
- **Requirements:** FR-NEW-010, FR-NEW-023, FR-NEW-039
- **Given** carol.ro@example.org is RO in "Cardiology 2027"; with her own signed in session, from a command line tool outside the editor, she sends the request the library sends when a RW member deletes "Statins Review" from "Cardiology 2027".
- **When** She sends it.
- **Then** "Access denied." is returned.
- **And** The administrator's view of "Cardiology 2027" still lists "Statins Review" (1.5 MB) and its history.
- **And** The activity list has no deletion line.
- **Priority:** Critical

#### E2E-SEC-010: A RO member uploads by hand

- **Category:** security
- **Covers:** Class B occurrence #1
- **Red before the fix because:** the file is stored; the assertion "3 presentations are listed to the administrator" fails with 4.
- **Scenario:** SC-005
- **Requirements:** FR-NEW-010, FR-NEW-023, FR-NEW-028
- **Given** carol.ro@example.org is RO in "Cardiology 2027"; with her own signed in session, from a command line tool outside the editor, she sends the request the library sends when a RW member uploads the valid file "Quarterly Review.html" (3 slides, 1 258 291 bytes) into "Cardiology 2027".
- **When** She sends it.
- **Then** "Access denied." is returned.
- **And** The administrator's view of "Cardiology 2027" still lists 3 presentations and no "Quarterly Review".
- **And** The activity list has no upload line.
- **Priority:** Critical

#### E2E-SEC-011: A RW member creates a folder by hand

- **Category:** security
- **Covers:** Class B occurrence #1
- **Red before the fix because:** the folder is created; the assertion "the administrator sees 3 folders" fails with 4.
- **Scenario:** SC-013
- **Requirements:** FR-NEW-013, FR-NEW-040
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; with his own signed in session, from a command line tool outside the editor, he sends the request the administration sends when the administrator creates a folder named "Backdoor".
- **When** He sends it.
- **Then** "Access denied." is returned.
- **And** The administrator's home page lists the same 3 folders and no "Backdoor".
- **And** The activity list has no folder creation line.
- **Priority:** Critical

#### E2E-SEC-012: A visitor without a session cannot download a presentation

- **Category:** security
- **Covers:** Class B occurrences #2 and #5
- **Red before the fix because:** a naive build that serves the stored file to anyone knowing the address fails the assertion "the visitor's download folder holds no file": it holds Heart Failure Update.html of 2 097 152 bytes.
- **Scenario:** SC-001
- **Requirements:** FR-NEW-001, FR-NEW-020, FR-NEW-022
- **Given** A visitor with no session who knows the exact download addresses of "Heart Failure Update" in "Cardiology 2027", HTML and PPTX, copied from carol.ro@example.org's earlier session.
- **When** The visitor requests the HTML download address, then the PPTX download address, with no sign in.
- **Then** Each answer is the sign in page, never a file.
- **And** The visitor's download folder holds no file, and the text "Heart Failure Update" appears in nothing the visitor received.
- **And** The administrator's view of "Cardiology 2027" is unchanged: 3 presentations.
- **Priority:** Critical

#### E2E-SEC-013: A presentation's script cannot read what the browser keeps for the library

- **Category:** security
- **Covers:** Class C occurrences #1, #2, #5
- **Red before the fix because:** the script reads the identity data kept for the library; the assertion "the slide shows no email address" fails and shows carol.ro@example.org.
- **Scenario:** SC-018
- **Requirements:** FR-NEW-021, FR-NEW-052, FR-NEW-053
- **Given** "Cardiology 2027" holds the presentation "Heart Failure Update" whose slide 1 carries this script: <script>document.getElementById('probe').textContent = 'stored: ' + document.cookie + ' | ' + JSON.stringify(localStorage) + ' | ' + JSON.stringify(sessionStorage);</script> and an element with the identifier "probe"; carol.ro@example.org is signed in.
- **When** Carol opens "Heart Failure Update" and shows slide 1.
- **Then** The element "probe" reads "stored:  | {} | {}": nothing about her, no email address, no sign in information, no folder name.
- **And** The administrator, who also opens the slide, sees the same: the text "carol.ro@example.org" and "seb.morand@gmail.com" appear nowhere on the slide.
- **And** Carol is still signed in as herself and her pages work normally.
- **Priority:** Critical

#### E2E-SEC-014: A presentation's script cannot act as the viewer or reach other folders

- **Category:** security
- **Covers:** Class C occurrences #1, #2, #4, #6 and #7
- **Red before the fix because:** the script deletes "Statins Review" with Dan's rights; the assertion "Statins Review is still listed to the administrator" fails.
- **Scenario:** SC-018
- **Requirements:** FR-NEW-020, FR-NEW-023, FR-NEW-052
- **Given** The presentation "Heart Failure Update" carries this script on slide 1: <script>fetch(LIST_OF_WCBIP_ADDRESS).then(r => r.text()).then(t => { probe.textContent = 'list: ' + t.slice(0, 200); }); fetch(DELETE_STATINS_REVIEW_ADDRESS, {method: 'DELETE'}).then(r => { probe.textContent += ' delete: ' + r.status; });</script> where the two addresses are the real ones of the library, filled in by the test, and an element "probe"; carol.ro@example.org (RO) opens it, then dan.rw@example.org (RW) opens it.
- **When** Each shows slide 1.
- **Then** The element "probe" shows no name from "WCBIP Melbourne Décembre 2026" and no deletion happens for either of them.
- **And** The administrator's view of "Cardiology 2027" still lists "Statins Review" and its history.
- **And** The activity list has no deletion line.
- **And** Carol then downloads the PPTX of the presentation: it is delivered and its text holds no name from "WCBIP Melbourne Décembre 2026" (the product opening the presentation to build it gives the script no more power).
- **Priority:** Critical

#### E2E-SEC-015: A Google account claiming the administrator address without verifying it

- **Category:** security
- **Covers:** Class E occurrence #1
- **Red before the fix because:** a build that trusts the claimed address signs the visitor in as the administrator; the assertion "the visitor sees the sign in page when opening Administration" fails and shows the administration with 3 folders.
- **Scenario:** SC-001
- **Requirements:** FR-NEW-011, FR-NEW-012, FR-NEW-068
- **Given** A Google account whose address reads seb.morand@gmail.com but which Google marks as not verified (the identity provider fixture returns that claim).
- **When** The visitor signs in with it.
- **Then** "Sign-in is unavailable. Try again later." is shown and the visitor stays signed out.
- **And** From the same browser, opening "Administration" and the home page shows the sign in page: no "Administration" entry, no folder.
- **And** The administrator's own session and activity list show no new line; the folder list is unchanged (3 folders).
- **Priority:** Critical

#### E2E-SEC-016: A sign in link carrying a destination on another site

- **Category:** security
- **Covers:** Class F occurrence #1
- **Red before the fix because:** the browser is sent to https://evil.example/phish; the assertion "the listener of evil.example recorded 0 visits" fails with 1.
- **Scenario:** SC-001
- **Requirements:** FR-NEW-009, FR-NEW-069
- **Given** carol.ro@example.org has no session; a link to the sign in carries the destination https://evil.example/phish; the fixture runs a listener that records every visit to evil.example.
- **When** She follows the link and signs in with Google.
- **Then** She arrives on the home page of slides.scm-platform.org, listing "Cardiology 2027".
- **And** The listener of evil.example recorded 0 visits and the browser never left slides.scm-platform.org.
- **And** The same result with the destination //evil.example/phish.
- **And** The same result with the destinations javascript:alert(1), https://slides.scm-platform.org@evil.example/x and /\evil.example.
- **Priority:** Critical

#### E2E-SEC-017: A page of another site deletes with the visitor's session

- **Category:** security
- **Covers:** Class G occurrences #2 and #3
- **Red before the fix because:** the deletion is accepted because the browser attached Dan's session; the assertion "Statins Review is still listed to the administrator" fails.
- **Scenario:** SC-019
- **Requirements:** FR-NEW-023, FR-NEW-039, FR-NEW-070
- **Given** dan.rw@example.org is signed in (RW in "Cardiology 2027"); in the same browser he opens the page https://evil.example/win that, on load, submits a form to the library's deletion of "Statins Review" from "Cardiology 2027".
- **When** The page loads.
- **Then** The library answers "Access denied.".
- **And** The administrator's view of "Cardiology 2027" still lists "Statins Review" (1.5 MB) and its history.
- **And** The activity list has no deletion line.
- **Priority:** Critical

#### E2E-SEC-018: A request with the administrator's copied session and no sign of coming from the library

- **Category:** security
- **Covers:** Class G occurrences #2 and #3
- **Red before the fix because:** the request is accepted since a request with no Origin evidence passes the gate; the assertion "the administrator lists 3 folders" fails with 4.
- **Scenario:** SC-019
- **Requirements:** FR-NEW-013, FR-NEW-040, FR-NEW-070
- **Given** The administrator's session credentials were copied; from a command line tool, with no sign of coming from the library's pages, the copy requests the creation of a folder named "Backdoor".
- **When** The tool sends the request.
- **Then** "Access denied." is returned.
- **And** The administrator's home page, in his real browser, lists the same 3 folders and no "Backdoor".
- **And** The activity list has no folder creation line.
- **Priority:** Critical

#### E2E-SEC-019: A sign in answer made for someone else is planted in a visitor's browser

- **Category:** security
- **Covers:** Class G occurrence #7
- **Red before the fix because:** Carol's browser becomes signed in as dan.rw@example.org; the assertion "the home page shows the sign in page" fails and lists "Cardiology 2027".
- **Scenario:** SC-001
- **Requirements:** FR-NEW-002, FR-NEW-020, FR-NEW-071
- **Given** A third party completed a Google sign in as dan.rw@example.org and kept the address carrying the answer; carol.ro@example.org's browser never started a sign in.
- **When** The third party makes Carol's browser open that address.
- **Then** "Sign-in is unavailable. Try again later." is shown and Carol stays signed out.
- **And** Carol's browser opening the home page shows the sign in page, not Dan's folders "Cardiology 2027" and "Pneumo Été".
- **And** The activity list shows no line.
- **Priority:** Critical

#### E2E-SEC-020: A session copied before Sign out is used after it

- **Category:** security
- **Covers:** Class G occurrence #8
- **Red before the fix because:** the copy is still accepted after Sign out; the assertion "the tool received no byte of Heart Failure Update" fails with 2 097 152 bytes.
- **Scenario:** SC-001
- **Requirements:** FR-NEW-001, FR-NEW-008, FR-NEW-072
- **Given** carol.ro@example.org is signed in; the credentials of her session are copied by someone else; Carol then chooses "Sign out".
- **When** From a command line tool, the copy asks for "Heart Failure Update" and its HTML download.
- **Then** Each answer is the sign in page, never a file.
- **And** The tool received no byte of "Heart Failure Update".
- **And** Carol's browser still shows the sign in page; no session of hers appears anywhere.
- **Priority:** Critical

#### E2E-SEC-021: A visitor reads the liveness and status answers

- **Category:** security
- **Covers:** Class B occurrences #3 and #7
- **Red before the fix because:** the liveness answer names the loaded file; the assertion "nothing received holds a file location or Heart Failure Update" fails and shows the path.
- **Scenario:** SC-023
- **Requirements:** FR-NEW-001, FR-NEW-010, FR-NEW-073
- **Given** A visitor with no session; the product holds "Heart Failure Update" in "Cardiology 2027".
- **When** He asks whether the product is running, then asks the status of "Heart Failure Update" in "Cardiology 2027".
- **Then** The first answer says the product is running and its version only; the second is the sign in page.
- **And** Nothing the visitor received holds a file location, a process number, "Heart Failure Update" or "Cardiology 2027".
- **And** The operator's health check, run afterwards, still succeeds.
- **Priority:** Critical

#### E2E-SEC-022: A presentation's script reaches the machine while its PPTX is built

- **Category:** security
- **Covers:** Class C occurrence #6 and Class A occurrences #8 and #9
- **Red before the fix because:** the PPTX is built from files outside the folder and the WebSocket is not aborted; the assertion "the PPTX holds no picture equal to secret.png" fails because the delivered PPTX contains secret.png.
- **Scenario:** SC-018
- **Requirements:** FR-NEW-020, FR-NEW-022, FR-NEW-052
- **Given** "Cardiology 2027" holds the presentation "Heart Failure Update" whose slide 1 carries <script>new WebSocket('ws://127.0.0.1:9/probe');</script>, <img src="file:///<fixture dir>/secret.png"> and <img src="../secret.png">; secret.png is a real PNG picture stored in the fixture directory, outside every folder of the library; a listener on the machine's loopback port 9 records every connection; carol.ro@example.org is RO.
- **When** Carol chooses the PPTX download.
- **Then** The PPTX is delivered with its slides.
- **And** The listener recorded 0 connections.
- **And** The PPTX holds no picture equal to secret.png.
- **Priority:** Critical

#### E2E-SEC-023: A RO member sends the other changing requests by hand

- **Category:** security
- **Covers:** Class B occurrence #1 and Class G occurrence #3
- **Red before the fix because:** the requests are accepted and the lists are readable; the assertion "Carol's reading of the Requests list is refused" fails and returns "Check the 2026 guideline".
- **Scenario:** SC-005
- **Requirements:** FR-NEW-010, FR-NEW-023, FR-NEW-070
- **Given** dan.rw@example.org queued the request "Check the 2026 guideline" on "Heart Failure Update"; carol.ro@example.org is RO in "Cardiology 2027"; with her own signed in session, from a command line tool outside the editor, she sends in turn: the request that recomputes the layout of the diagrams of "Heart Failure Update", the request that adds a request "Make the title shorter" to its Requests list, the request that deletes a request of that list, the request that applies an AI suggestion to it, the request that reads the Requests list and the AI suggestions, and the request for its DOCX export.
- **When** She sends the six requests.
- **Then** Each answer is "Access denied.", the reading of the Requests list included; no file is received for the DOCX request.
- **And** dan.rw@example.org opens "Heart Failure Update": its size is still 2 097 152 bytes and its Requests list holds exactly the request "Check the 2026 guideline".
- **And** The history lists no new version.
- **Priority:** Critical

#### E2E-SEC-024: A page of another site shows a library page inside a frame

- **Category:** security
- **Covers:** Class G occurrence #5
- **Red before the fix because:** the library page is displayed in the frame; the assertion "the frame shows no presentation name" fails and shows "Heart Failure Update".
- **Scenario:** SC-001
- **Requirements:** FR-NEW-001, FR-NEW-020, FR-NEW-072
- **Given** carol.ro@example.org is signed in; she opens https://evil.example/frame, which shows the folder page of "Cardiology 2027" and the sign in page of the library each inside a frame, under a button of its own.
- **When** The page loads.
- **Then** Both frames stay empty: no folder name, no presentation name, no button of the library.
- **And** Opened on its own in a tab, the same folder page still shows "Cardiology 2027" to Carol.
- **And** No library action was done by the click on the button of the other site.
- **And** The administrator's own view of the folder page, opened in a tab at the same moment, lists the same presentations of "Cardiology 2027" and shows no click made on his behalf.
- **Priority:** Critical

#### E2E-SEC-025: An upload that announces 100 bytes and sends 30 MB

- **Category:** security
- **Covers:** Class D occurrence #1
- **Red before the fix because:** the extra bytes are read and stored; the assertion "only the declared 100 bytes are read and the connection is closed" fails.
- **Scenario:** SC-019
- **Requirements:** FR-NEW-030, FR-NEW-038, FR-NEW-063
- **Given** dan.rw@example.org is RW in "Cardiology 2027"; from a command line tool he sends, with his own session, the upload of "Huge.html" announcing a length of 100 bytes and then sending 31 457 280 bytes (30 MB).
- **When** He sends it.
- **Then** Only the declared 100 bytes are read, the upload is refused with "This file is not a valid presentation: the file is not declared as a presentation." and the connection is closed.
- **And** The administrator's view lists 3 presentations and no "Huge".
- **And** The free space of the library is unchanged and lamya.chrif@gmail.com browses her folder without delay.
- **And** In a second run with no declared length, the sending is cut at 26 214 401 bytes and "The file is larger than 25 MB." is returned.
- **Priority:** Critical

### 9.4 Modified tests

None. The existing tests of the local mode stay as they are: they are the evidence that the local mode is unchanged (FR-NEW-055).

### 9.5 Removed tests

None.

## 10. Traceability

| Scenario | Requirements | Happy | Failure | Edge |
|---|---|---|---|---|
| SC-001 | FR-NEW-001, FR-NEW-002, FR-NEW-003, FR-NEW-004, FR-NEW-008, FR-NEW-009, FR-NEW-011, FR-NEW-012, FR-NEW-015, FR-NEW-020, FR-NEW-022, FR-NEW-024, FR-NEW-065, FR-NEW-067, FR-NEW-068, FR-NEW-069, FR-NEW-071, FR-NEW-072 | E2E-001, E2E-183 | E2E-002, E2E-003, E2E-004, E2E-SEC-012, E2E-007, E2E-SEC-015, E2E-SEC-016, E2E-SEC-019, E2E-SEC-020, E2E-SEC-024 | E2E-005, E2E-006, E2E-171, E2E-172, E2E-180, E2E-184, E2E-185 |
| SC-002 | FR-NEW-001, FR-NEW-002, FR-NEW-003, FR-NEW-005, FR-NEW-006, FR-NEW-007, FR-NEW-009, FR-NEW-015, FR-NEW-026, FR-NEW-027, FR-NEW-048, FR-NEW-062, FR-NEW-066 | E2E-008 | E2E-009, E2E-010, E2E-011, E2E-167 | E2E-012, E2E-013, E2E-166, E2E-188 |
| SC-003 | FR-NEW-011, FR-NEW-012, FR-NEW-014, FR-NEW-015, FR-NEW-016, FR-NEW-017, FR-NEW-018, FR-NEW-020, FR-NEW-060, FR-NEW-062, FR-NEW-064, FR-NEW-065 | E2E-014 | E2E-015, E2E-016 | E2E-017, E2E-018, E2E-019, E2E-165 |
| SC-004 | FR-NEW-002, FR-NEW-003, FR-NEW-009, FR-NEW-010, FR-NEW-015, FR-NEW-018, FR-NEW-019, FR-NEW-020, FR-NEW-021, FR-NEW-022, FR-NEW-024, FR-NEW-026, FR-NEW-030, FR-NEW-039, FR-NEW-060, FR-NEW-069 | E2E-020, E2E-021, E2E-168 | E2E-022, E2E-023, E2E-024, E2E-025, E2E-026 | E2E-027, E2E-028, E2E-029, E2E-164 |
| SC-005 | FR-NEW-010, FR-NEW-015, FR-NEW-021, FR-NEW-022, FR-NEW-023, FR-NEW-024, FR-NEW-025, FR-NEW-026, FR-NEW-028, FR-NEW-039, FR-NEW-052, FR-NEW-053, FR-NEW-064, FR-NEW-070 | E2E-030, E2E-031 | E2E-032, E2E-SEC-008, E2E-SEC-009, E2E-SEC-010, E2E-SEC-023 | E2E-033, E2E-034, E2E-035 |
| SC-006 | FR-NEW-010, FR-NEW-013, FR-NEW-020, FR-NEW-021, FR-NEW-024, FR-NEW-025, FR-NEW-026, FR-NEW-028, FR-NEW-039, FR-NEW-064 | E2E-036 | E2E-037, E2E-038 | E2E-039, E2E-040 |
| SC-007 | FR-NEW-007, FR-NEW-010, FR-NEW-017, FR-NEW-024, FR-NEW-025, FR-NEW-026, FR-NEW-048, FR-NEW-051, FR-NEW-053, FR-NEW-054, FR-NEW-065, FR-NEW-066 | E2E-041, E2E-042, E2E-151 | E2E-043, E2E-047, E2E-152, E2E-170 | E2E-044, E2E-045, E2E-046, E2E-153 |
| SC-008 | FR-NEW-010, FR-NEW-024, FR-NEW-026, FR-NEW-027, FR-NEW-034, FR-NEW-039 | E2E-048 | E2E-049, E2E-050 | E2E-051, E2E-052, E2E-053, E2E-189 |
| SC-009 | FR-NEW-024, FR-NEW-028, FR-NEW-029, FR-NEW-030, FR-NEW-031, FR-NEW-032, FR-NEW-037, FR-NEW-038, FR-NEW-049, FR-NEW-053, FR-NEW-061 | E2E-054 | E2E-055, E2E-056, E2E-057, E2E-058, E2E-059, E2E-060, E2E-061, E2E-154, E2E-174 | E2E-062, E2E-063, E2E-064, E2E-065, E2E-155, E2E-175, E2E-179 |
| SC-010 | FR-NEW-028, FR-NEW-031, FR-NEW-032, FR-NEW-033, FR-NEW-034, FR-NEW-037, FR-NEW-049, FR-NEW-051, FR-NEW-063 | E2E-066 | E2E-067, E2E-068 | E2E-069, E2E-070, E2E-162 |
| SC-011 | FR-NEW-028, FR-NEW-030, FR-NEW-034, FR-NEW-035, FR-NEW-036, FR-NEW-037, FR-NEW-038, FR-NEW-049, FR-NEW-061, FR-NEW-063, FR-NEW-067 | E2E-071, E2E-075 | E2E-072, E2E-073, E2E-074, E2E-077 | E2E-076, E2E-078, E2E-158 |
| SC-012 | FR-NEW-010, FR-NEW-019, FR-NEW-024, FR-NEW-028, FR-NEW-033, FR-NEW-039, FR-NEW-049, FR-NEW-053 | E2E-079 | E2E-080, E2E-081 | E2E-082, E2E-083 |
| SC-013 | FR-NEW-002, FR-NEW-003, FR-NEW-011, FR-NEW-012, FR-NEW-013, FR-NEW-014, FR-NEW-024, FR-NEW-025, FR-NEW-028, FR-NEW-039, FR-NEW-040, FR-NEW-045, FR-NEW-050, FR-NEW-067 | E2E-084, E2E-085 | E2E-086, E2E-SEC-011, E2E-090 | E2E-087, E2E-088, E2E-089, E2E-156 |
| SC-014 | FR-NEW-015, FR-NEW-019, FR-NEW-040, FR-NEW-041, FR-NEW-042, FR-NEW-049, FR-NEW-053 | E2E-091 | E2E-092, E2E-093, E2E-094, E2E-095 | E2E-096, E2E-097, E2E-098, E2E-163 |
| SC-015 | FR-NEW-010, FR-NEW-016, FR-NEW-026, FR-NEW-040, FR-NEW-043, FR-NEW-044, FR-NEW-048, FR-NEW-049, FR-NEW-060, FR-NEW-062, FR-NEW-067 | E2E-099 | E2E-100, E2E-101, E2E-102, E2E-157 | E2E-103, E2E-104, E2E-105, E2E-106, E2E-107 |
| SC-016 | FR-NEW-003, FR-NEW-012, FR-NEW-013, FR-NEW-014, FR-NEW-022, FR-NEW-024, FR-NEW-045, FR-NEW-046, FR-NEW-047, FR-NEW-048, FR-NEW-049, FR-NEW-053 | E2E-108, E2E-109 | E2E-110, E2E-111, E2E-112, E2E-161, E2E-176 | E2E-113, E2E-114, E2E-115, E2E-160 |
| SC-017 | FR-NEW-007, FR-NEW-010, FR-NEW-022, FR-NEW-023, FR-NEW-024, FR-NEW-026, FR-NEW-028, FR-NEW-036, FR-NEW-047, FR-NEW-048, FR-NEW-074 | E2E-116, E2E-173 | E2E-117, E2E-118, E2E-119, E2E-177 | E2E-120, E2E-121, E2E-178 |
| SC-018 | FR-NEW-010, FR-NEW-015, FR-NEW-020, FR-NEW-021, FR-NEW-022, FR-NEW-023, FR-NEW-033, FR-NEW-052, FR-NEW-053 | E2E-122 | E2E-123, E2E-SEC-013, E2E-SEC-014, E2E-SEC-022 | E2E-124 |
| SC-019 | FR-NEW-010, FR-NEW-013, FR-NEW-021, FR-NEW-023, FR-NEW-024, FR-NEW-028, FR-NEW-030, FR-NEW-031, FR-NEW-032, FR-NEW-038, FR-NEW-039, FR-NEW-040, FR-NEW-041, FR-NEW-053, FR-NEW-060, FR-NEW-063, FR-NEW-070 | E2E-125, E2E-181 | E2E-SEC-001, E2E-SEC-002, E2E-SEC-003, E2E-SEC-004, E2E-SEC-005, E2E-SEC-006, E2E-SEC-007, E2E-126, E2E-SEC-017, E2E-SEC-018, E2E-SEC-025 | E2E-127, E2E-182 |
| SC-020 | FR-NEW-010, FR-NEW-013, FR-NEW-015, FR-NEW-016, FR-NEW-018, FR-NEW-020, FR-NEW-022, FR-NEW-024, FR-NEW-031, FR-NEW-054, FR-NEW-062 | E2E-128 | E2E-129, E2E-130 | E2E-131, E2E-132, E2E-159 |
| SC-021 | FR-NEW-025, FR-NEW-052, FR-NEW-055, FR-NEW-056, FR-NEW-057, FR-NEW-059 | E2E-133 | E2E-134, E2E-135 | E2E-136, E2E-137 |
| SC-022 | FR-NEW-003, FR-NEW-013, FR-NEW-020, FR-NEW-023, FR-NEW-026, FR-NEW-032, FR-NEW-049, FR-NEW-050, FR-NEW-051, FR-NEW-053, FR-NEW-054 | E2E-138 | E2E-139, E2E-140, E2E-141 | E2E-142, E2E-143, E2E-144, E2E-169 |
| SC-023 | FR-NEW-001, FR-NEW-002, FR-NEW-004, FR-NEW-009, FR-NEW-010, FR-NEW-013, FR-NEW-057, FR-NEW-058, FR-NEW-059, FR-NEW-065, FR-NEW-073 | E2E-145, E2E-186 | E2E-146, E2E-147, E2E-SEC-021 | E2E-148, E2E-149, E2E-150, E2E-187 |

Requirement coverage (every requirement has a happy, a failure and an edge test):

| Requirement | Happy | Failure or security | Edge |
|---|---|---|---|
| FR-NEW-001 Nothing is public | E2E-001, E2E-145 | E2E-002, E2E-004, E2E-007, E2E-009, E2E-147, E2E-SEC-012, E2E-SEC-020, E2E-SEC-021, E2E-SEC-024 | E2E-006, E2E-149 |
| FR-NEW-002 Sign in with a Google account | E2E-001, E2E-021, E2E-183 | E2E-002, E2E-003, E2E-007, E2E-SEC-019 | E2E-005, E2E-013, E2E-087, E2E-150 |
| FR-NEW-003 Account without any right | E2E-001 | E2E-002, E2E-011, E2E-026, E2E-090, E2E-140 | E2E-115, E2E-171 |
| FR-NEW-004 Google unavailable | E2E-001 | E2E-003 | E2E-150 |
| FR-NEW-005 Session of 30 days | E2E-008 | E2E-009 | E2E-012, E2E-166 |
| FR-NEW-006 Expired session | E2E-008 | E2E-009, E2E-010, E2E-011, E2E-167 | E2E-012 |
| FR-NEW-007 Session ends during an edit | E2E-041, E2E-173 | E2E-010, E2E-167 | E2E-013, E2E-188 |
| FR-NEW-008 Sign out | E2E-001 | E2E-002, E2E-SEC-020 | E2E-006, E2E-180, E2E-185 |
| FR-NEW-009 Direct link while signed out | E2E-021 | E2E-004, E2E-007, E2E-009, E2E-026, E2E-SEC-016 | E2E-148, E2E-172 |
| FR-NEW-010 One refusal for every missing or forbidden target | E2E-021 | E2E-023, E2E-024, E2E-025, E2E-026, E2E-037, E2E-081, E2E-102, E2E-117, E2E-119, E2E-123, E2E-129, E2E-170, E2E-177, E2E-SEC-001, E2E-SEC-006, E2E-SEC-008, E2E-SEC-009, E2E-SEC-010, E2E-SEC-021, E2E-SEC-023 | E2E-053, E2E-149, E2E-187 |
| FR-NEW-011 The administrator | E2E-014, E2E-084 | E2E-090, E2E-SEC-015 | E2E-087, E2E-156 |
| FR-NEW-012 No other administrator | E2E-014 | E2E-090, E2E-112, E2E-161, E2E-SEC-015 | E2E-088, E2E-089, E2E-114 |
| FR-NEW-013 Administration is for the administrator only | E2E-138 | E2E-038, E2E-086, E2E-112, E2E-130, E2E-139, E2E-SEC-011, E2E-SEC-018 | E2E-149 |
| FR-NEW-014 The administrator is never refused | E2E-014, E2E-084, E2E-085 | E2E-015 | E2E-088, E2E-114 |
| FR-NEW-015 Home page: the accessible folders | E2E-001, E2E-008, E2E-014, E2E-020, E2E-091, E2E-122, E2E-128 | E2E-015, E2E-092 | E2E-017, E2E-018, E2E-033, E2E-097, E2E-165 |
| FR-NEW-016 Empty home page | E2E-014 | E2E-015 | E2E-106, E2E-159 |
| FR-NEW-017 Library unreadable | E2E-014 | E2E-016, E2E-152 | E2E-019 |
| FR-NEW-018 Folder page: the presentations | E2E-020, E2E-128, E2E-168 | E2E-022 | E2E-019, E2E-027, E2E-028, E2E-029, E2E-164 |
| FR-NEW-019 Empty folder | E2E-091 | E2E-022 | E2E-083 |
| FR-NEW-020 No leak between folders | E2E-014, E2E-122 | E2E-002, E2E-004, E2E-023, E2E-024, E2E-037, E2E-123, E2E-129, E2E-139, E2E-SEC-012, E2E-SEC-014, E2E-SEC-019, E2E-SEC-022, E2E-SEC-024 | E2E-124 |
| FR-NEW-021 Roles do not travel | E2E-122 | E2E-024, E2E-037, E2E-123, E2E-SEC-001, E2E-SEC-002, E2E-SEC-005, E2E-SEC-013 | E2E-033, E2E-124 |
| FR-NEW-022 RO: view, present, download | E2E-021, E2E-030, E2E-031 | E2E-119, E2E-SEC-012, E2E-SEC-022 | E2E-034, E2E-035, E2E-115, E2E-121, E2E-132 |
| FR-NEW-023 RO cannot change anything | E2E-030 | E2E-032, E2E-118, E2E-140, E2E-SEC-001, E2E-SEC-006, E2E-SEC-008, E2E-SEC-009, E2E-SEC-010, E2E-SEC-014, E2E-SEC-017, E2E-SEC-023 | E2E-033 |
| FR-NEW-024 RW: edit, upload, delete | E2E-001, E2E-020, E2E-036, E2E-042, E2E-048, E2E-054, E2E-079, E2E-085, E2E-108, E2E-116, E2E-128, E2E-151, E2E-181 | E2E-038 | E2E-033, E2E-039, E2E-040 |
| FR-NEW-025 Same editor as the local mode | E2E-030, E2E-031, E2E-036, E2E-041, E2E-042, E2E-085, E2E-133 | E2E-032, E2E-043, E2E-047 | E2E-034, E2E-044, E2E-045, E2E-046, E2E-153 |
| FR-NEW-026 A stored change keeps the previous version | E2E-041, E2E-048, E2E-151 | E2E-010, E2E-043, E2E-047, E2E-049, E2E-050, E2E-117, E2E-118, E2E-141, E2E-152, E2E-SEC-008 | E2E-013, E2E-027, E2E-034, E2E-039, E2E-044, E2E-046, E2E-053, E2E-105, E2E-153, E2E-189 |
| FR-NEW-027 Conflicting edits | E2E-048 | E2E-049, E2E-050 | E2E-051, E2E-052, E2E-188, E2E-189 |
| FR-NEW-028 Upload a presentation | E2E-036, E2E-054, E2E-071, E2E-085, E2E-125, E2E-181 | E2E-055, E2E-154, E2E-174, E2E-SEC-010 | E2E-040, E2E-062, E2E-063, E2E-069, E2E-082, E2E-120, E2E-175, E2E-179 |
| FR-NEW-029 Only .html files | E2E-054 | E2E-055 | E2E-065 |
| FR-NEW-030 Size limit of 25 MB | E2E-054, E2E-071 | E2E-056, E2E-SEC-006, E2E-SEC-007, E2E-SEC-025 | E2E-028, E2E-062, E2E-065 |
| FR-NEW-031 Valid presentation | E2E-054 | E2E-057, E2E-058, E2E-059, E2E-068, E2E-126, E2E-154, E2E-174 | E2E-063, E2E-064, E2E-132, E2E-155, E2E-179 |
| FR-NEW-032 Allowed file names | E2E-054, E2E-125 | E2E-060, E2E-061, E2E-SEC-001, E2E-SEC-002, E2E-SEC-003, E2E-SEC-004 | E2E-065, E2E-127, E2E-144, E2E-162, E2E-175 |
| FR-NEW-033 Name collision | E2E-066 | E2E-067, E2E-068 | E2E-069, E2E-070, E2E-082, E2E-124, E2E-162 |
| FR-NEW-034 Replace | E2E-066 | E2E-073, E2E-077 | E2E-052, E2E-078 |
| FR-NEW-035 Upload progress | E2E-071 | E2E-072 | E2E-076, E2E-158 |
| FR-NEW-036 Interrupted upload | E2E-071 | E2E-072, E2E-073 | E2E-120 |
| FR-NEW-037 Double submit | E2E-054, E2E-075 | E2E-077 | E2E-070 |
| FR-NEW-038 Upload cannot be stored | E2E-054 | E2E-074, E2E-SEC-007, E2E-SEC-025 | E2E-078 |
| FR-NEW-039 Delete a presentation | E2E-036, E2E-079, E2E-085 | E2E-025, E2E-080, E2E-081, E2E-SEC-009, E2E-SEC-017 | E2E-053, E2E-082, E2E-083 |
| FR-NEW-040 Create a folder | E2E-091 | E2E-093, E2E-SEC-011, E2E-SEC-018 | E2E-096, E2E-097, E2E-098, E2E-103, E2E-156, E2E-163 |
| FR-NEW-041 Folder name rules | E2E-091 | E2E-093, E2E-094, E2E-095, E2E-SEC-005 | E2E-096, E2E-163 |
| FR-NEW-042 Unique folder names | E2E-091 | E2E-092 | E2E-098, E2E-163 |
| FR-NEW-043 Delete a folder | E2E-099 | E2E-100, E2E-102, E2E-157 | E2E-103, E2E-104, E2E-105, E2E-106, E2E-107 |
| FR-NEW-044 Wrong name retyped | E2E-099 | E2E-100, E2E-101, E2E-157 | E2E-107 |
| FR-NEW-045 Add a member | E2E-108 | E2E-110, E2E-112, E2E-161, E2E-176 | E2E-088, E2E-089, E2E-113, E2E-114, E2E-115, E2E-156, E2E-160 |
| FR-NEW-046 Invalid email address | E2E-108 | E2E-110, E2E-111, E2E-176 | E2E-115 |
| FR-NEW-047 Change a role, remove a member | E2E-109, E2E-116 | E2E-117, E2E-118 | E2E-113 |
| FR-NEW-048 Changed rights apply on the next action | E2E-109, E2E-116, E2E-173 | E2E-011, E2E-102, E2E-117, E2E-118, E2E-119, E2E-170, E2E-177 | E2E-103, E2E-105, E2E-120, E2E-121 |
| FR-NEW-049 Record successful actions | E2E-054, E2E-066, E2E-075, E2E-079, E2E-091, E2E-099, E2E-108, E2E-109, E2E-138 | E2E-077, E2E-140 | E2E-106, E2E-142, E2E-144, E2E-169 |
| FR-NEW-050 Show the activity list | E2E-084, E2E-138 | E2E-139 | E2E-142, E2E-143 |
| FR-NEW-051 Refusals, sign ins and stored changes are not recorded | E2E-041 | E2E-067, E2E-140, E2E-141 | E2E-044, E2E-169 |
| FR-NEW-052 A presentation's scripts have no power over the viewer | E2E-030 | E2E-SEC-013, E2E-SEC-014, E2E-SEC-022 | E2E-137 |
| FR-NEW-053 Text is never markup | E2E-125 | E2E-059, E2E-095, E2E-111, E2E-126, E2E-174, E2E-SEC-002, E2E-SEC-003, E2E-SEC-004, E2E-SEC-005, E2E-SEC-013 | E2E-035, E2E-046, E2E-083, E2E-097, E2E-127, E2E-144 |
| FR-NEW-054 Initial content | E2E-128 | E2E-129, E2E-130 | E2E-045, E2E-131, E2E-132, E2E-143, E2E-159 |
| FR-NEW-055 The local mode is unchanged | E2E-133 | E2E-134, E2E-135 | E2E-136, E2E-137 |
| FR-NEW-056 No sign in in the local mode | E2E-133 | E2E-134, E2E-135 | E2E-136 |
| FR-NEW-057 Reached at its address, securely | E2E-145 | E2E-134, E2E-146, E2E-147 | E2E-149, E2E-150 |
| FR-NEW-058 Plain address redirected | E2E-145 | E2E-146 | E2E-148 |
| FR-NEW-059 Other host names refused | E2E-145, E2E-186 | E2E-147 | E2E-136 |
| FR-NEW-060 Lists stay fast | E2E-014, E2E-168 | E2E-016, E2E-SEC-006 | E2E-017, E2E-104 |
| FR-NEW-061 A 25 MB upload completes | E2E-071 | E2E-056 | E2E-062, E2E-076 |
| FR-NEW-062 Nothing is lost on restart | E2E-099 | E2E-016 | E2E-019, E2E-131, E2E-159, E2E-166 |
| FR-NEW-063 Never half a presentation | E2E-066 | E2E-072, E2E-073, E2E-SEC-025 | E2E-070, E2E-078 |
| FR-NEW-064 Keyboard and labels | E2E-030 | E2E-032 | E2E-017, E2E-040 |
| FR-NEW-065 English for what the mode adds | E2E-145 | E2E-002, E2E-170 | E2E-018 |
| FR-NEW-066 Changes are stored by themselves | E2E-041, E2E-151 | E2E-010, E2E-047, E2E-152 | E2E-044, E2E-153 |
| FR-NEW-067 Names of the controls the mode adds | E2E-071, E2E-084 | E2E-157 | E2E-089, E2E-156, E2E-158, E2E-180 |
| FR-NEW-068 Unverified Google address | E2E-001 | E2E-002, E2E-SEC-015 | E2E-171 |
| FR-NEW-069 Destination after sign in | E2E-021 | E2E-SEC-016 | E2E-172 |
| FR-NEW-070 A request from another site is refused | E2E-181 | E2E-SEC-017, E2E-SEC-018, E2E-SEC-023 | E2E-182 |
| FR-NEW-071 A sign in answer that this browser did not start | E2E-001, E2E-183 | E2E-SEC-019 | E2E-184 |
| FR-NEW-072 No use of a session after sign out, no framing | E2E-001 | E2E-SEC-020, E2E-SEC-024 | E2E-006, E2E-185 |
| FR-NEW-073 A liveness answer that reveals nothing | E2E-186 | E2E-SEC-021 | E2E-187 |
| FR-NEW-074 A quiet screen until the person acts | E2E-173 | E2E-117, E2E-177 | E2E-178 |

## 11. Open questions

None. The texts and figures that the owner did not state are decided in the requirements and listed at the end of Section 3.1 so that they can be confirmed; none blocks the design.

## 12. Glossary (MANDATORY)

| Term | Definition | Context |
|---|---|---|
| Access denied. | The exact message shown when a person asks for something they have no right to or that does not exist; identical in both cases | Access control |
| Activity list | The administrator's list of the 500 latest successful actions: who, when, what | Activity |
| Admin | The single administrator, seb.morand@gmail.com; all folders and the administration | Access control |
| Administration | The panel (entry labelled "Administration") where the administrator manages folders, members and the activity list | Administration |
| Automatic store | The editor storing a change by itself: 0.8 seconds after typing stops, at once when the person leaves the edited field; there is no Save control | Presentation editing |
| Collision | An upload whose name equals, without regard to case and without the ".html" ending, on the composed form, the name of a presentation already in the folder | Upload and removal |
| Another site | Any web page whose address is not slides.scm-platform.org | Access control |
| Liveness answer | The reply to the check that the product is running: running and the version only | Deployment address |
| Quiet screen | A presentation left on screen with no notice while nothing the person typed is unstored, even though their session or right ended | Presentation editing |
| Composed form | A name written with each accented letter as one letter (an "e" followed by an accent mark becomes "é"); names are checked and compared on it | Upload and removal |
| Destination | The page a sign in link asks to show after the sign in | Sign in and sessions |
| Unsaved text | Text a person typed in a field that the editor has not stored yet | Presentation editing |
| Verified address | An email address that Google states it has verified for the account | Sign in and sessions |
| Conflict notice | The notice "The file changed on disk. Reload to see the changes, or keep your version." with "Keep mine" and "Reload" | Presentation editing |
| First problem | The first error of the editor's checks for an uploaded file (warnings never count), message only, shown after "This file is not a valid presentation:" | Upload and removal |
| Folder | A named group of presentations with its own list of members | Library |
| Folder page | The page listing the presentations of one folder | Library |
| Full screen | The presentation shown alone on the whole screen | Presentation editing |
| Google account | The identity the person signs in with; identified by its email address | Sign in and sessions |
| History | The earlier versions of a presentation kept by the product when it is saved or replaced; listed and restored by an operator | Presentation editing |
| Home page | The page listing the folders a person can access | Library |
| Library | Everything the web library mode holds: folders, presentations, members, activity | Library |
| Local mode | The existing way to run the product on one local file, with no sign in | Local mode |
| Member | A person listed in a folder with the role RW or RO | Administration |
| Operator | The owner running the product | Deployment address |
| Presentation | One .html file holding slides, shown and edited by the editor; its name is the file name without ".html" | Library |
| Presenter window | The second window showing the current slide, the next slide, the speaker notes, the timer | Presentation editing |
| RO | Role per folder: view, present, download HTML and PPTX (label "Read only") | Access control |
| Role | What a person can do in a folder: Admin, RW or RO | Access control |
| RW | Role per folder: RO plus edit, upload, delete (label "Read and write") | Access control |
| Session | The period of 30 days from a sign in during which the person stays signed in in that browser, restarts of the product included | Sign in and sessions |
| Sign in page | The only page shown to a visitor: one action, "Sign in with Google" | Sign in and sessions |
| Speaker notes | The text for the presenter attached to a slide, shown in the presenter window | Presentation editing |
| Structure checks | The editor's own checks of a presentation: its structure rules (declaration, slides, identifiers, counters, template text) and its charter rules (classes, widths, sources); they report errors and warnings | Upload and removal |
| Valid presentation | A file declared as a presentation, with at least 1 slide and no error of any kind reported by the editor's checks | Upload and removal |
| Web library mode | The new way to run the product: a private web library of folders and presentations at slides.scm-platform.org | All |
| Replace | The confirmed overwriting of an existing presentation by an uploaded file, the previous version kept in the history | Upload and removal |

## 13. Implementability gate (MANDATORY)

| Round | F | A | Verdict |
|---|---|---|---|
| 1 | 16 | 6 | NOT-IMPLEMENTABLE |
| 2 | 7 | 7 | NOT-IMPLEMENTABLE |
| 3 | 6 | 13 | NOT-IMPLEMENTABLE |

**Verdict:** after round 3 the gate read NOT-IMPLEMENTABLE; every finding of the three rounds was then amended by the owner's decision "applique" (round 3 applied on 16 November 2026). The final verification is the writer's own consistency script (ids, at least 3 tests per requirement, at least 5 per scenario, failures outnumber happy tests, EARS patterns, no implementation detail outside attacker payloads); no fourth audit was run.
**Amendments applied:** every F and A finding of rounds 1, 2 and 3
**No implementation detail outside Section 14:** PASS (self check, Phase 10, see the report of the writer)

## 14. Evidence appendix (for /sdlc-design and the auditor, not for the product owner)

### 14.1 Current State evidence

Counts were recounted by the writer on the branch `feat/0049-web-library-mode` on 16 November 2026.

| # | Claim (Section 2) | Evidence |
|---|---|---|
| 1 | One process serves one deck; a second start only switches the file | `src/mcp_htmleditor/http_server.py:1111-1160` (`start_http_server`), `:1144-1147` (already running: `state.set_file`), `:1152`; `src/mcp_htmleditor/state.py:177-181` (`set_file`, one `current_file` per process); `src/mcp_htmleditor/cli.py:181-215` (`serve` takes one file) |
| 2 | No sign in, no person, no role: only host and origin are checked | `src/mcp_htmleditor/http_server.py:240-262` (`_refuse_untrusted_request`), `:1045-1050` (`_trusted_host_names`: loopback names plus the bind host), `:1053-1060` (`_is_same_origin`: scheme must be `http`); `sdlc/specs/SPEC-0001-mcp-htmleditor/spec.md:137-140` |
| 3 | No OAuth, cookie or session code in `src` | `grep -rniE "oauth|set-cookie|\bcookie|google|authorization" src --include=*.py` returns only `tracing.py:6`, `:212` (outbound bearer header of the trace export) and `http_server.py:79`, `:967` (browser extension attributes); `grep -rniE "session" src --include=*.py` returns 5 hits, none about a sign in (`render/service.py:103`, `:115`, `http_server.py:718`, `export/pptx_paint.py:89`, `mcp_server.py:610`) |
| 4 | The liveness answer is open to any host and names the loaded file | `src/mcp_htmleditor/http_server.py:281-283` (answered before the gate), `:873-890` (`health_payload`: `file`, `pid`, `port`); SPEC-0005/BR-006 (`sdlc/specs/SPEC-0005-cross-origin-requests/spec.md:133-136`) |
| 5 | Second save stopped by the conflict notice; "Keep mine" and "Reload" | `src/mcp_htmleditor/http_server.py:833-839` (`check_conflict`), `:842-851` (`write_save`); `src/mcp_htmleditor/static/editor.html:89-93` (notice text and the two buttons), `src/mcp_htmleditor/static/editor-save.js:112` (`onSaveConflict`); test `tests/test_save_safety_e2e.py:92` (`test_e2e_007_conflict_refused`) |
| 6 | Every save keeps the previous version in a history | `src/mcp_htmleditor/fileio.py:49-57` (`atomic_write` with a `reason` keeps the previous content, leaves no temporary file on failure); `src/mcp_htmleditor/history.py:156-175` (`list_versions`, `restore_version`) |
| 7 | Files next to the open deck are served with containment rules | `src/mcp_htmleditor/deck_files.py:1-80`; exploit tests `tests/test_http_deck_files_e2e.py` |
| 8 | The container image listens on all interfaces, no sign in, one file | `Dockerfile:33` (`HTMLEDITOR_HOST=0.0.0.0`), `:59` (`USER appuser:appgroup`), `:61` (`EXPOSE 7842`), `:63-64` (healthcheck on `/health`), `:66-68` (`ENTRYPOINT` and `CMD serve --no-browser /data/document.html`); `docker-compose.yml:12-13` (published port), `:16`; `docker-compose.prod.yml:14`; `sdlc/backlog/BL-0019-container-port-unauthenticated.md` |
| 9 | Settings come from one class, none about sign in | `src/mcp_htmleditor/config.py:91-117` (`Settings`, prefix `HTMLEDITOR_` at `:100`, fields `host`, `port`, `poll_interval`, `otel_*`, directories) |
| 10 | HTML download and PPTX export of the served file | `src/mcp_htmleditor/http_server.py:297-302` (dispatch of `/download`, `/export/pptx`, `/export/docx`), `:409-430` (`_serve_download`), `:432-492` (`_export_pptx`, `_export_docx`); tests `tests/test_toolbar_icons_e2e.py:75`, `:92`, `:163` |
| 11 | The editor shows the deck in a frame that lets its scripts run in the editor's origin | `src/mcp_htmleditor/static/editor.html:145` (`sandbox="allow-scripts allow-same-origin ..."`), `src/mcp_htmleditor/http_server.py:389-407` (`_serve_content_frame` serves the stored HTML unmodified) |
| 12 | Presenter window and previews are built from the deck's own HTML | `templates/bootstrap/slides-empty.html:861-863` (`window.open`, name `deck-presenter`), `:814` (`srcdoc = DECK_HTML`); tests `tests/test_help_shortcuts_e2e.py` |
| 13 | The editor's own structure checks and their order | `src/mcp_htmleditor/deck/lint.py:51-57` (`lint_deck`: whole file first, then slide index, then code), `:60-67`, `:304-313` (file rules L002 L003 L004; slide rules L001 L005 L006, all errors; remote pictures L010 is a warning, `:78-95`); `src/mcp_htmleditor/deck/__init__.py:76-83` (`detect_doc_type`: a file with slides and no declaration is read as a presentation) |
| 14 | Save requests are capped at 50 MB, other requests at 1 MB | `src/mcp_htmleditor/http_server.py:85` (`MAX_SAVE_BYTES = 52_428_800`), `:615-620` (`_read_declared_body`, refusal before reading), `:788` (`parse_content_length`); `src/mcp_htmleditor/request_service.py:40` (`BODY_MAX_BYTES = 1_048_576`) |
| 15 | The two conference decks pass the editor's checks | run from the repository: `.venv/bin/python -c "from mcp_htmleditor.deck.lint import lint_file; r = lint_file(<deck>); print(r['errors'], r['warnings'])"` prints `0 0` for both decks (18 and 15 slides, `data-doc-type="presentation"`, 3 901 499 and 3 278 888 bytes, pictures embedded) |
| 16 | The existing public static site is outside this repository | ASSUMED: hosted at lamya-slides.scm-platform.org, as stated by the owner when asking for this specification; `sdlc/backlog/BL-0049-web-library-mode.md:18-19` only says the public static site has no protection and no editing |
| 17 | The sign in credentials of the owner have no return address for the new host name | ASSUMED: stated in `sdlc/backlog/BL-0049-web-library-mode.md:25-26`; not verified by the writer (the credentials file was not opened) |
| 18 | The deployment target exists | ASSUMED: described in the owner's deployment instructions (remote host with a reverse proxy, an external shared container network, persistent data under a per application directory); not verifiable from this repository |
| 19 | The editor stores each change by itself: 0.8 s after typing stops, at once on leaving the field, 0.6 s after a structural action; no Save control; failures show "Save failed: <reason>"; the lost connection notice appears after repeated failed polls | `src/mcp_htmleditor/static/editor-save.js:4-6` (timers 800, immediate, 600), `:135-138` (`showSaveError`, prefix `Save failed: `), `:161` (`POLL_FAILURE_LIMIT` shows `connection-lost`); `src/mcp_htmleditor/static/editor.html:95` (text `Connection to the editor server lost`); no save button in `editor.html:18-51` |
| 20 | The conflict notice only arises for a person who has unsaved typed text; otherwise the page reloads to the stored version at the next poll (1000 ms) | `src/mcp_htmleditor/static/editor.js:442-471` (`externalChange` requires `!hasPendingChanges`, then `reloadFrame`; `baseMtime` kept while edits are pending), `src/mcp_htmleditor/static/editor-save.js:112-118` (`onSaveConflict`), `src/mcp_htmleditor/config.py:48` (`DEFAULT_POLL_INTERVAL = 1000`) |
| 21 | The editor's labels are French in part (`Édition`, `Annuler`, `Rétablir`, `Mode présentation plein écran`, `Présenter avec le pointeur`, `Vue présentateur`, `Télécharger en PPTX`, `Télécharger le fichier HTML`, `Raccourcis clavier`) and English in part (`Requests`, `Ask AI`, `Notes`); the deck carries `Pointeur` | `src/mcp_htmleditor/static/editor.html:27-51`, `:57`; `templates/bootstrap/slides-empty.html:294` |
| 22 | The two seeded decks: 18 and 15 slides (`const TOTAL = 18`, `const TOTAL = 15`), 3 901 499 and 3 278 888 bytes, modified 2026-11-15 19:57:19 UTC and 19:57:18 UTC (20:57 in Paris) | `stat -c "%y"` of `/Users/sebastien/projects/lamya/presentations/WCBIP_WIIP_2026-12_Melbourne/deck/wiip2026.html` and `.../WABIP_2026-12_Melbourne/deck/wcbip2026-v1.html`; `load_deck` reports 18 slides (charter `breathe`) and 15 slides (charter `medical`) |
| 23 | The editor's findings are ordered whole file first (a warning outside every slide has no slide index and sorts first), then by slide, then by code; charter errors L007 to L009 exist and run only for a known charter; example messages recorded from the linter: `missing attribute data-title`, `TOTAL is 5 but the file has 2 slides`, `expected id "slide-0" but found "a"`, `slide has an image and no source line`, `remote image https://example.org/logo.png is not exported` (warning) | `src/mcp_htmleditor/deck/lint.py:51-57`, `:78-95`; `src/mcp_htmleditor/deck/charter_rules.py:134-141`, `:185-190`; linter run on four sample files on 16 November 2026 |
| 24 | No protection against being shown in a frame of another site, no cookie or sign in credential exists; a request without an Origin header passes the gate | `grep -nE "Origin|Sec-Fetch|SameSite|Set-Cookie|frame-ancestors|X-Frame-Options" src/mcp_htmleditor/http_server.py` returns only `:90`, `:218`, `:245`, `:255`; `src/mcp_htmleditor/http_server.py:255-259` (a missing Origin is accepted, a present one must equal the host) |
| 25 | Other state changing requests of the editor exist besides the save | `src/mcp_htmleditor/http_server.py:319-328` (`/content`, `/arch-layout`, `/requests`, `/requests/delete`, `/review/apply`) |

Test command: `make test ARGS='-k "save_safety or http_deck_files or help_shortcuts or toolbar_icons or http_origin"'`. Gate: `make check`.

### 14.2 Class sweep

Four classes, each with its own searches. Occurrence numbers are per class (A#n, B#n, C#n, D#n); the tests cite them.

**Class A:** names typed or uploaded by a person reach the place where presentations are stored (path traversal, CWE-22).

**Searches run (from the repository root, then from `src/mcp_htmleditor`):**

1. `grep -rnE "resolve\(|is_relative_to|unquote\(|\.\./" src/mcp_htmleditor --include=*.py | grep -v "^src/mcp_htmleditor/\(export\|render\|breathe\|arch\)"` (path normalisation and containment idioms; 22 hits; the 7 that concern a name reaching a stored file are tabled below, the others resolve directories or files already chosen by the operator: `config.py:197-198`, `templates.py:25-26`, `skill_audit.py:160`, `cli.py:219`, `mcp_server.py:77`, `:142`, `:205`, `:224`, `request_service.py:305`, `deck/patch.py:178`).
2. `grep -rnE "\.(read_bytes|write_bytes|write_text|read_text|unlink|mkdir|rename|replace)\(|shutil\.|os\.(replace|rename|remove)" --include=*.py .` (file system operations on a name; run in `src/mcp_htmleditor`, 43 hits outside `export`, `render`, `breathe`, `arch*`; the ones that read or write a deck named by a path are tabled, the others write logs, state records, temporary export files or skill and template files chosen by the operator).

Idiom 3 (extraction and external commands), `grep -rn "subprocess\|zipfile\|tarfile\|shutil.unpack" --include=*.py src/mcp_htmleditor` outside `render/`: 17 hits, `tracing.py:14` (a comment), `export/reference_docx.py:33`, `:36`, `:364`, `:379`, `:389`, `:403`, `:408`, `:714`, `:720`, `:745`, `:746` (the reference document built by the product from its own files, no person's name), `export/to_docx.py:39`, `:109`, `:154` (pandoc run on a staged copy with `--resource-path` set to the folder of the presentation, see A#10), `deck/tools.py:10`, `:109` (the DOCX export wrapper, a fixed argument list). Idiom 4 (a picture address inside a presentation read as a file), `grep -rnE "Path\(src\)|base_dir /|urlparse\(src\)|url2pathname" --include=*.py src/mcp_htmleditor/export`: 6 hits, tabled as A#8, A#9 and the `pptx_paint.py:157` hit of C#6. Idioms not searched: none else that applies.

| # | Occurrence | Verdict | Disposition |
|---|---|---|---|
| A#1 | `src/mcp_htmleditor/deck_files.py:54-62` | safe: `target.is_relative_to(base)` and the hidden segment test reject any location outside the deck's folder, links followed | none; reuse as a model (Section 14.3) |
| A#2 | `src/mcp_htmleditor/deck_files.py:65-76` | safe: the path is decoded once, normalised on its text, then refused when it climbs (`..`), starts with a reserved segment, holds a hidden segment or a NUL; exploit tests in `tests/test_http_deck_files_e2e.py` | none |
| A#3 | `src/mcp_htmleditor/fileio.py:62` (`Path(path).resolve()` in `atomic_write`) | vulnerable when fed a name from a person: follows links, accepts any path | FR-NEW-032, FR-NEW-041, FR-NEW-021; E2E-SEC-001 to E2E-SEC-005 |
| A#4 | `src/mcp_htmleditor/deck/tools.py:62` (`dest.parent.mkdir(parents=True, ...)` in the new file tool) | vulnerable if exposed: creates directories on a given path; not reachable by a person of the library (only the local operator or agent calls it) | design input: never expose (Section 14.3), FR-NEW-032 |
| A#5 | `src/mcp_htmleditor/state.py:179` (`set_file` resolves any path and serves it) | vulnerable if a person's name is mapped to it | FR-NEW-032, FR-NEW-021; E2E-SEC-001, E2E-SEC-002 |
| A#6 | `src/mcp_htmleditor/http_server.py:355-362` (`_serve_deck_file`) | safe: reads only what `deck_file` returns, control at `deck_files.py:54-62` | none |
| A#7 | `src/mcp_htmleditor/history.py:159`, `:170` (history keyed by the resolved file) | vulnerable if two folders or a deleted then recreated name resolve to one history | FR-NEW-039, FR-NEW-043, FR-NEW-021; E2E-082, E2E-103 |
| A#8 | `src/mcp_htmleditor/export/pptx_images.py:112-117` (a picture address that is not remote is read as an absolute path, or joined to the presentation's folder, so `../secret.png` and `/any/path.png` are read when the PPTX is built) | vulnerable: a stored presentation makes the PPTX hold a file outside every folder | FR-NEW-052, FR-NEW-021; E2E-SEC-022 |
| A#9 | `src/mcp_htmleditor/export/pptx_paint_shapes.py:196-200` (a `file:` address or a relative path is read from disk with `read_bytes`) | vulnerable: same, through the painted export | FR-NEW-052, FR-NEW-021; E2E-SEC-022 |
| A#10 | `src/mcp_htmleditor/export/to_docx.py:135-154` (pandoc is given `--resource-path` set to the folder of the presentation, so it embeds files found there or above) | vulnerable if exposed: the DOCX download is not offered in the web library mode | FR-NEW-022 (only HTML and PPTX offered, any other export refused); E2E-SEC-023 |

Search 1 also hits `state.py:213` (the `resolve()` that feeds the hashed key of `_file_dir`): safe, the key is a digest of the path, never a person's text, and the path itself comes from `set_file` (A#5).

Disposition of the 43 hits of search 2 (every one, in the order of the search; "state directory" means a location the product derives from a hash of the resolved file path, never from a person's text; "operator" means a path or name typed by the person running the product, never by a person of the library):

| Hit | Verdict | Disposition |
|---|---|---|
| `tracing.py:64` | safe: trace file path from the operator's settings | none |
| `logging_config.py:111` | safe: log directory from the operator's settings | none |
| `http_server.py:108`, `:109` | safe: only rewrite characters of a download name into a header value, no file access | none |
| `http_server.py:362` | safe: reads what `deck_file` returned, control `deck_files.py:54-62` | none |
| `http_server.py:383`, `:403`, `:417`, `:993` | vulnerable if the served file is chosen from a person's text (same as A#5) | FR-NEW-021, FR-NEW-032 |
| `http_server.py:447`, `:453`, `:473`, `:479` | safe: temporary export files the product itself names | none |
| `http_server.py:695` | safe: `_send_file` serves package files by base name (SPEC-0005 class sweep row for `/static`) | none |
| `cli.py:385`, `:499` | safe: operator command line argument, no person of the library | none |
| `skill_audit.py:167`, `:185` | safe: skill file of the product; a string rewrite | none |
| `request_store.py:96`, `:136`, `:140` | safe: state directory; but the records of a deleted presentation or folder must be deleted with it | FR-NEW-039, FR-NEW-043 (Section 14.3 item 3) |
| `skill_content.py:91`, `:101` | safe: fixed file names; the topic is checked against a closed list at `:97-98` | none |
| `fileio.py:40` | safe: string rewrite of backslashes | none |
| `fileio.py:46`, `:71`, `:88` | `:46` and `:71` vulnerable when the destination comes from a person's name (A#3); `:88` safe (its own temporary file) | FR-NEW-032, FR-NEW-041, FR-NEW-021 |
| `deck/patch.py:308`, `deck/renumber.py:184`, `:185` | safe: string escaping | none |
| `deck/tools.py:48` | safe: template name checked against the closed list at `:43-45` | none |
| `deck/tools.py:62` | vulnerable if exposed (A#4) | FR-NEW-032, FR-NEW-041 |
| `deck/__init__.py:53` | vulnerable when the path comes from a person's text (A#5) | FR-NEW-032 |
| `state.py:110`, `:228`, `:239`, `:249`, `:251` | safe: state directory, hashed keys | none |
| `history.py:74`, `:92`, `:106`, `:140` | safe: state directory, hashed keys | none |
| `history.py:110` | vulnerable if the history of a deleted name survives and is met again by a new presentation of that name (A#7) | FR-NEW-039, FR-NEW-043 |

**Class B:** a request made without the right to make it (not signed in, or with an insufficient role) reaches an action that reads, changes or deletes library content (missing authentication and authorization, CWE-306 and CWE-862).

**Searches run (`src/mcp_htmleditor/http_server.py`):**

1. `grep -nE "def do_(GET|POST|OPTIONS)|_refuse_untrusted_request\(\)|\"/(content|download|requests|review|arch-layout|export)" http_server.py` (the entry points and their gate).
2. `grep -nE "atomic_write|write_save|\.unlink|request_store|apply_review|layout_arch|set_file|def _(list_requests|create_request|delete_request|apply_review|arch_layout|serve_content|serve_status)" http_server.py` (the actions that read or change the stored document).

Idioms not searched: the agent tool server (`mcp_server.py`) and the command line, reachable only by the local operator over standard input and output, not by a person over the network.

| # | Occurrence | Verdict | Disposition |
|---|---|---|---|
| B#1 | `http_server.py:312-330` (`do_POST`: save, layout, requests, review) | vulnerable: the only gate is the host and origin check, no identity, no role | FR-NEW-001, FR-NEW-013, FR-NEW-023, FR-NEW-048; E2E-SEC-006, E2E-SEC-008 to E2E-SEC-011 |
| B#2 | `http_server.py:276-308` (`do_GET`: content, frame, status, download, exports, requests) | vulnerable: reads and downloads for anyone who reaches the address | FR-NEW-001, FR-NEW-020, FR-NEW-022; E2E-SEC-012 |
| B#3 | `http_server.py:281-283`, `:873-890` (`/health` answered to any host, names the loaded file) | vulnerable once files live in the library: discloses a stored file's absolute location | FR-NEW-001, FR-NEW-020; design input (Section 14.3) |
| B#4 | `http_server.py:265-271` (`do_OPTIONS`) | safe: answers 405 with no cross origin permission | none |
| B#5 | `http_server.py:240-262` (`_refuse_untrusted_request`) | insufficient alone: stops other web pages and foreign host names (SPEC-0005), not a direct request from a person with no role | FR-NEW-001, FR-NEW-059 |
| B#6 | `http_server.py:625-640`, `:842-851` (save and write) | vulnerable as an unauthenticated write | FR-NEW-023, FR-NEW-048; E2E-SEC-008 |
| B#7 | `http_server.py:493-508` (`/status` returns the absolute file name) | vulnerable once files live in the library | FR-NEW-020 |
| B#8 | `http_server.py:419-420` (download), `:448-450` (PPTX export), `:474-476` (DOCX export): on failure the answer carries `str(exc)`, which can hold a file name or a storage path; `static/editor.js:425` shows it behind `Export <format> échoué :` | vulnerable once files live in the library: a path reaches the person | FR-NEW-010, FR-NEW-020; E2E-119, E2E-173 |

**Class C:** the content of a stored presentation runs in the browser with the rights and identity of the person viewing it (stored script execution, CWE-79).

**Searches run:**

1. `grep -rnE "sandbox|allow-same-origin|srcdoc|document.write|postMessage|window\.open" src/mcp_htmleditor/static templates/bootstrap src/mcp_htmleditor/http_server.py` (how stored HTML is embedded in frames and windows): 46 hits, tabled as C#1 to C#4, C#8 to C#10 and the safe C#11.
2. `grep -n "Content-Security-Policy\|X-Frame\|frame-ancestors" src/mcp_htmleditor/http_server.py src/mcp_htmleditor/deck_files.py` (headers that confine served content; only the SVG policy exists) and `grep -nE "def _serve_content" -A12 src/mcp_htmleditor/http_server.py` (how the stored HTML is answered).

3. `grep -rnE "chromium\.launch|page\.goto|as_uri|\.goto\(" --include=*.py src/mcp_htmleditor` (places where the product itself opens a stored presentation in a browser: 4 hits, `render/service.py:170`, `:211`, `export/pptx_paint.py:136`, `:157`).

Idioms not searched: stored markup rendered into the editor shell by script (`innerHTML`), outside what this increment adds; the library's own pages are new and must escape text (FR-NEW-053).

| # | Occurrence | Verdict | Disposition |
|---|---|---|---|
| C#1 | `src/mcp_htmleditor/static/editor.html:145` (frame allows scripts and the editor's own origin) | vulnerable: a deck's script acts with the viewer's identity | FR-NEW-052; E2E-SEC-013, E2E-SEC-014 |
| C#2 | `src/mcp_htmleditor/http_server.py:389-407` (`_serve_content_frame`) | vulnerable: stored HTML served unmodified from the editor's origin | FR-NEW-052; E2E-SEC-013, E2E-SEC-014 |
| C#3 | `src/mcp_htmleditor/deck_files.py:46-47`, `http_server.py:370-371` | safe: SVG files are answered with `sandbox; script-src 'none'` | none |
| C#4 | `templates/bootstrap/slides-empty.html:814`, `:861-863` (presenter window and previews replay the deck HTML) | vulnerable if the replay shares the library's origin | FR-NEW-052; E2E-SEC-014 |
| C#6 | `src/mcp_htmleditor/export/pptx_paint.py:136`, `:157` (the PPTX download opens the stored presentation in a headless browser on the machine running the product, scripts included); only requests whose address starts with http or https are aborted (`pptx_paint.py:156`, pattern `pptx_paint.py:51`), a WebSocket connection and a `file:` address are not | vulnerable: a hostile script can open a connection to the product's own loopback or read a local file reference while the PPTX is built | FR-NEW-052; E2E-SEC-014, E2E-SEC-022 |
| C#7 | `src/mcp_htmleditor/render/service.py:170`, `:211` (the picture render does the same) | vulnerable if exposed to a person of the library; not offered by this increment | FR-NEW-052 (not exposed); E2E-SEC-014 |
| C#8 | `templates/bootstrap/slides-empty.html:861-867` and the three sibling decks (`slides-breathe-empty.html:990-996`, `slides-medical-empty.html:1026-1032`, `slides-ei-empty.html`) open a window by script and write a page into it (`window.open`, `document.write`) | vulnerable if that window shares the library's origin: the presenter page runs with the viewer's identity | FR-NEW-052; E2E-SEC-013, E2E-SEC-014 |
| C#9 | `templates/bootstrap/slides-empty.html:814`, `:943` (breathe), `:979` (medical), `:783` (ei): the two preview frames replay the deck HTML with `srcdoc` | vulnerable if the replay inherits the library's origin | FR-NEW-052; E2E-SEC-014 |
| C#10 | `templates/bootstrap/slides-empty.html:705`, `:790`, `:919`, `:940` and siblings: messages posted with target origin `*` between deck, presenter and editor | vulnerable to a foreign window if the receiver does not check its sender; SPEC-0022 checks `event.source` | FR-NEW-052; E2E-SEC-024 |
| C#11 | `static/editor.css:275` (a comment) | safe | none |
| C#5 | `src/mcp_htmleditor/http_server.py:376-387` (`_serve_content` returns the stored HTML as a page) | vulnerable: visiting it runs the deck's scripts at the editor's origin | FR-NEW-052; E2E-SEC-013 |

**Class D:** a request body larger than the product accepts reaches storage or memory (uncontrolled resource consumption, CWE-770).

**Searches run:**

1. `grep -nE "MAX_SAVE_BYTES|BODY_MAX_BYTES|_read_declared_body|def _read_save_request|Content-Length" src/mcp_htmleditor/http_server.py src/mcp_htmleditor/request_service.py`.
2. `grep -nE "\.read\(|rfile" src/mcp_htmleditor/http_server.py` (every place a body is read).

Idioms not searched: the temporary files of the exports (sized by the product's own output).

| # | Occurrence | Verdict | Disposition |
|---|---|---|---|
| D#1 | `http_server.py:85`, `:649-650`, `:788` (a save can declare up to 50 MB and is then read whole) | vulnerable for uploads: the upload limit is 25 MB and the role must be known before the body is read | FR-NEW-030, FR-NEW-023; E2E-SEC-006, E2E-SEC-007 |
| D#2 | `http_server.py:615-620` (`_read_declared_body`) | safe for the other routes: a declared length above the limit is refused before any read | none |

**Class E:** the identity or address claimed by the sign-in provider reaches the decision of who the person is and what they may do without being verified (improper authentication, CWE-287).

**Searches run (from the repository root):**

1. `grep -rniE "email_verified|id_token|userinfo|openid|jwt|verified" src --include=*.py --include=*.js` (the claims of a sign in answer): 5 hits, none about a sign in (`http_server.py:219` a Host header carrying userinfo; `static/editor-undo.js:55`, `static/editor.js:334`, `:483` comments on browser behavior; `export/docx_header_footer.py:17` a comment).
2. `grep -rniE "authoriz|identity|principal|current_user|whoami" src --include=*.py --include=*.js` (any place that decides who the caller is): 6 hits, all disposed in the table below.

Idioms not searched: none left that apply; no sign in code exists (Section 14.1 row 3).

| # | Occurrence | Verdict | Disposition |
|---|---|---|---|
| E#1 | no occurrence in `src` decides who a person is: the sign in is new in this increment | not applicable today; the class is introduced by the feature | FR-NEW-068; E2E-SEC-015 (also E2E-171) |
| E#2 | `tracing.py:6`, `:212` (outbound bearer header of the trace export) | safe: an outgoing credential of the product, no person's claim | none |
| E#3 | `static/doc-blocks.js:19`; `static/slide-layouts.js:43`, `:370`, `:496` | safe: the French word "principal" in template text, no identity decision | none |

**Class F:** a destination carried by a request link reaches the redirect that follows a sign in (open redirect, CWE-601).

**Searches run (from the repository root):**

1. `grep -rnE "Location|send_response\(30|next=|return_to|redirect_uri|window\.location|location\.href|location\.assign" src --include=*.py --include=*.js`: 0 hits.
2. `grep -rnE "(open|replace|assign)\(.*(http|//)|\.href *=|\.src *= *[a-z]|send_header\(.Refresh" src --include=*.js --include=*.py` outside export and render: 3 hits, `cli.py:236` (opens the product's own local address in the operator's browser, no request data), `static/editor.js:420` (the address of a file the editor itself fetched, for a download), `static/slide-layouts.js:17` (a text rewrite, not a destination).

Idioms not searched: none that apply (no redirect exists today).

| # | Occurrence | Verdict | Disposition |
|---|---|---|---|
| F#1 | no occurrence in `src`: the sign in redirect is new in this increment | not applicable today; the class is introduced by the feature | FR-NEW-069; E2E-SEC-016 (also E2E-172) |

**Class G:** a request made by another web page with the visitor's browser credentials changes the library, or a library page is shown to the visitor inside a page of another site (cross site request forgery and clickjacking, CWE-352 and CWE-1021).

**Searches run (from the repository root):**

1. `grep -nE "Origin|Sec-Fetch|SameSite|Set-Cookie|frame-ancestors|X-Frame-Options" src/mcp_htmleditor/http_server.py` (the origin gate and any frame or cookie protection): 4 hits, `:90`, `:218`, `:245`, `:255`.
2. `grep -nE "def do_(GET|POST|OPTIONS)|_refuse_untrusted_request\(\)|check_content_type\(" src/mcp_htmleditor/http_server.py` (every entry point and its gate): 9 hits.
3. `grep -rnE "Origin|Sec-Fetch|SameSite|Set-Cookie|frame-ancestors|X-Frame-Options" src --include=*.py --include=*.js --include=*.html` outside `http_server.py`, `export` and `render`: 0 hits.

Idioms not searched: the agent tool server and the command line (not reachable by a web page).

| # | Occurrence | Verdict | Disposition |
|---|---|---|---|
| G#1 | `http_server.py:90`, `:218` (header parsing lists `Origin` among single headers) | safe: parsing hygiene only | none |
| G#2 | `http_server.py:245`, `:255` (`_refuse_untrusted_request`: a foreign Origin is refused, a missing Origin is accepted) | insufficient once a session credential exists: a request with no Origin evidence passes | FR-NEW-070; E2E-SEC-017, E2E-SEC-018 |
| G#3 | `http_server.py:312-330` (`do_POST`: gate at `:317`, then save, layout, request queue, review) | vulnerable once a credential exists: the gate is the only protection | FR-NEW-070, FR-NEW-023; E2E-SEC-017, E2E-SEC-023 |
| G#4 | `http_server.py:610`, `:612`, `:650`, `:793-796` (`check_content_type`: JSON only) | safe against a plain page form; not a substitute for the origin rule | none |
| G#5 | `http_server.py:276-308` (`do_GET`: no frame protection header, no `Sec-Fetch` check) | vulnerable: a library page can be framed by another site | FR-NEW-072; E2E-SEC-024 |
| G#6 | `http_server.py:265-271` (`do_OPTIONS`: 405, no cross origin permission) | safe | none |
| G#7 | no occurrence: the sign in answer handling is new in this increment | not applicable today; the class is introduced by the feature | FR-NEW-071; E2E-SEC-019 |
| G#8 | no occurrence: sign out and the end of a session are new | not applicable today; introduced by the feature | FR-NEW-072; E2E-SEC-020 |

### 14.3 Design inputs

These are technical facts and questions found while writing; they are inputs, not decisions.

1. Serving several presentations. One process holds one `current_file` (`state.py:177-181`, `http_server.py:1144-1152`) and every request handler reads it. Web mode needs the deck chosen per request and per person. HOW question: one process resolving the deck per request, or one process per deck behind a router (the current port range `7840-7849` allows 10, `http_server.py` `PORT_RANGE_START`, `:1105-1109`, so the second option does not reach 200 folders). Detection signal: E2E-124 fails when the content of one folder's "Statins Review" is shown for the other; E2E-017 fails when 200 folders are not listed.
2. Sign in protocol and session store. Nothing exists (row 3). Needed: a Google sign in whose client credentials come from `Settings` (`config.py:91-117`, prefix `HTMLEDITOR_`; no `os.environ` elsewhere, AGENTS.md), a session of exactly 30 days from sign in that survives a restart (`FR-NEW-005`, `FR-NEW-062`), sign out per browser, and a role check on every request, not stored in the session, so that revocation applies to the next action (`FR-NEW-048`). The administrator address is a constant or a setting (`FR-NEW-011`). Detection signal: E2E-008, E2E-009 and E2E-012 fail when the 30 days are not exact or are extended by use; E2E-116 and E2E-117 fail when a role is cached past the next action; E2E-166 fails when a restart ends sessions.
3. Storage layout and history. A folder holds its presentations as files; a presentation is one file with a history. `fileio.py:49-57` (`atomic_write` with a reason) and `history.py:117-175` already do atomic replacement and history; the state directory key is the hash of the resolved path (`state.py:211-214`), so two paths never share a history, but deletion of a presentation or a folder must also delete its history and its request records (`FR-NEW-039`, `FR-NEW-043`). Collisions without regard to case must be enforced by the product (a Linux file system is case sensitive, a macOS one is not). Detection signal: E2E-082 fails when a deleted name's history comes back; E2E-103 fails when a recreated folder keeps members or decks; E2E-162 fails when composed and decomposed names are not one name; E2E-SEC-002 fails when a traversal name leaves the folder.
4. Hostile script isolation. The frame allows `allow-same-origin` (`editor.html:145`); the stored HTML is served from the editor's origin (`http_server.py:376-407`); the presenter window and previews replay the deck HTML (`slides-empty.html:814`, `:861-863`) and the shell and frame talk by messages checked against `event.source` (SPEC-0022). Options include serving decks from a second origin, a sandbox without the same origin, or both; each must keep the presenter window, full screen, keys and the editor's save working (`FR-NEW-052`, `FR-NEW-025`). Detection signal: E2E-SEC-013 and E2E-SEC-014 fail when the viewer's identity data or another folder's list reaches the script; E2E-SEC-024 fails when a library page can be framed by another site; E2E-030 and E2E-042 fail when the presenter window or the editor stop working.
5. Upload validation. Reuse `deck/lint.py` (`lint_deck`, `:51-57`): the first problem is the first error of the sorted list (whole file, then slide, then code); warnings (L010) pass. The two product texts "the file is not declared as a presentation" and "the file has no slide" are new: `lint_deck` runs the structure rules only when the type is `presentation` (`:53-54`) and `detect_doc_type` reads a file that has slides and no declaration as a presentation (`deck/__init__.py:76-83`), whereas this specification requires an explicit declaration (both seeded decks carry one).
6. Body limits. Saves allow 50 MB (`http_server.py:85`, `:788`), other bodies 1 MB (`request_service.py:40`); uploads need 26 214 400 bytes, refused before reading when declared larger, and refused before reading when the role is missing (`E2E-SEC-006`, `E2E-SEC-007`). A client that lies about its length must also be bounded. Detection signal: E2E-062 fails when exactly 26 214 400 bytes is refused; E2E-SEC-006, E2E-SEC-007 and E2E-SEC-025 fail when more than that is stored or the declared length is trusted.
7. Deployment on the owner's remote host. Reuse the packaging (`Dockerfile`, `docker-compose.prod.yml`); the host deployment pattern is the owner's: deployment scripts under `/app/vps-management`, an external shared network named `proxy-network`, the port exposed and not published, environment from a per application data file, persistent data under the application's data directory so that folders, members, history, sessions and the activity list survive a redeploy (`FR-NEW-062`). The image today starts `serve` on one file (`Dockerfile:66-68`) and its healthcheck calls the liveness answer on `127.0.0.1` (`:63-64`).
8. Reverse proxy and the trust gate. TLS ends at the proxy, so the product sees plain connections. `_trusted_host_names` accepts loopback names plus the bind host unless it is a wildcard (`http_server.py:1045-1050`); the web mode must accept `slides.scm-platform.org` and nothing else (`FR-NEW-059`), and the same origin test requires the scheme `http` (`:1060`), which a browser using the secure address does not send; the real scheme and host come from the proxy. The plain address must be redirected at the proxy (`FR-NEW-058`). Detection signal: E2E-145 and E2E-146 fail when the secure address does not work or the plain one is not redirected; E2E-147 fails when another host name is served; E2E-SEC-016 fails when a destination leaves the product.
9. Google console. The owner's credentials (project `scm-pwd`, per `BL-0049:25-26`) need the return address of the sign in for `slides.scm-platform.org` added before the first deployment; without it every sign in ends with the unavailable message (`EXC-023c`).
10. Seed content. The two decks are shipped with the product as seed files (`/Users/sebastien/projects/lamya/presentations/WCBIP_WIIP_2026-12_Melbourne/deck/wiip2026.html`, 3 901 499 bytes, 18 slides, becomes "From Challenges to Change"; `/Users/sebastien/projects/lamya/presentations/WABIP_2026-12_Melbourne/deck/wcbip2026-v1.html`, 3 278 888 bytes, 15 slides, becomes "Bridging the Gap"). On the first creation of the library the product creates the folder "WCBIP Melbourne Décembre 2026", copies both files unchanged, adds `lamya.chrif@gmail.com` as RW, and records that the seeding happened, so no later start repeats it (`FR-NEW-054`). A copy stamps the copy time, so the modified times of the supplied files (19:57:19 and 19:57:18 UTC, row 22 of 14.1) are carried over explicitly; after the minutes are truncated both read 19:57 and the order is alphabetical. The seeding is not an activity line (`FR-NEW-050`). Detection signal: E2E-128 and E2E-159 fail if the times are the import time or if the seeding is repeated.
11. Status and liveness answers name the absolute file (`http_server.py:493-508`, `:873-890`); in web mode they must not disclose where library files are stored (B#3, B#7).
12. The request loop (Requests panel, Ask AI) writes records beside the deck's state (`request_store.py:96-140`, `state.py:211-214`); in the library they belong to the presentation and follow its deletion. Whether an assistant processes them in the web mode is outside this specification (the options exist as in the local mode, `FR-NEW-025`).
13. Tests need a fake Google identity provider (none exists; the e2e fixtures serve one deck on a loopback port, `tests/conftest.py:245-270`), a clock that can move by days (30 day session, `FR-NEW-005`, `FR-NEW-006`), a way to cut a connection midway, a way to fill the storage, and an operator view of the stored library and of the history for the "absence of effect" assertions of Section 9.3. Browser tests follow `tests/browser_wait.py` and `tests/stdio_support.py` (AGENTS.md).
14. Time display in the person's time zone needs the browser's zone; the server must not guess it (`FR-NEW-018`). Detection signal: E2E-029 fails when the server's zone is shown instead of the person's; E2E-164 fails on truncation or rounding.
15. Names. A presentation's name is the file name without `.html`, brought to its composed (NFC) form; the collision key is that form lower cased, without `.html`, so a case sensitive file system must be given an explicit key, and `Café` and `Café` are one name (`FR-NEW-033`). A replacement keeps the existing name (`FR-NEW-034`). The allowed characters are a closed list: Latin-script letters (ł ø œ ß included), digits, spaces and . _ - ( ) and the straight apostrophe, at most 100 characters, no edge space (`FR-NEW-032`); folder names are letters of any alphabet with combining marks, digits, spaces and the plain hyphen, 1 to 60 after composition (`FR-NEW-041`). Detection signal: E2E-162 and E2E-163 fail when the composed and decomposed forms are two names; E2E-069 fails when an accent is ignored; E2E-175 fails on the curly apostrophe.
16. Automatic store and notices (`FR-NEW-066`, `FR-NEW-007`, `FR-NEW-010`). The editor stores 0.8 s after typing stops and at once on leaving a field (`editor-save.js:4-6`), shows failures as `Save failed: <reason>` (`:135-138`) and shows `Connection to the editor server lost` after repeated failed polls (`:161`, `editor.html:95`). An ended session or a refusal must give the dedicated texts alone: the answer to a store and to a poll must be distinguishable as "session ended" and "refused" so the editor shows neither the prefix nor the lost connection notice. Detection signal: E2E-010, E2E-167 and E2E-170 fail when the notice starts with `Save failed:` or when the lost connection notice appears within 10 seconds.
17. Conflict notice (`FR-NEW-027`). It only arises for a person with unsaved typed text (`editor.js:454-463`: `externalChange` needs `!hasPendingChanges`; otherwise the frame reloads at the next 1000 ms poll). The library must expose the stored version's modification marker per presentation to the editor's poll and to the store request, as the single file server does (`state.py` `get_mtime`, `http_server.py:493-508`). Detection signal: E2E-048 (second And), E2E-049 to E2E-052 fail if a person without unsaved text sees the notice, or if a person with unsaved text is not shown it.
18. Labels (`FR-NEW-065`). The editor and the presentations keep their labels (Section 14.1 row 21); only the pages and messages the mode adds are English. Detection signal: E2E-042 and E2E-170 fail when a French label is translated or a notice added by the mode is not English.
19. Upload validity (`FR-NEW-031`). `lint_deck` returns warnings and errors in one list ordered whole file first (`lint.py:57`), so the first element can be a warning; the check must keep only severity `error` before taking the first, drop the slide identifier, and add the two product texts of `FR-NEW-031`. Charter errors only run for a known charter (`charter_rules.py:134-137`). Detection signal: E2E-057 fails if an undeclared deck with 2 well formed slides is accepted; E2E-155 fails if the warning is reported; E2E-154 fails if the charter error is ignored; E2E-057 and E2E-058 fail if the two product texts are wrong.
20. Seeded times (`FR-NEW-054`). Covered by item 10: the modified times are carried explicitly. Detection signal: E2E-128 fails if the copy stamps its own time.
21. Stored scripts on the machine running the product (`FR-NEW-052`). The PPTX download opens the stored presentation in a headless browser (`export/pptx_paint.py:136`, `:157`) and aborts only http and https requests (`:156`, `:51`): WebSocket and `file:` addresses are not blocked; the picture render does the same (`render/service.py:170`, `:211`). A hostile script runs there with the product's loopback and file reach. Options include a browser with no network and no file access beyond the one presentation, building the PPTX without running scripts (the flow engine of AGENTS.md is the degraded form), or an exporter that reads only picture data already inside the presentation (data URIs) and refuses every file address and relative path (A#8, A#9). Detection signal: E2E-SEC-014 (last And) and E2E-SEC-022 fail when the PPTX of a presentation carrying the hostile script holds library data, a picture read from outside the folder, or the product's loopback listener records a connection.
22. Sign in claims (`FR-NEW-068`, `FR-NEW-069`). The identity provider's answer must be checked for signature, audience and a verified address before the address is read, the address lower cased, and the post sign in destination restricted to the product's own address. Detection signal: E2E-SEC-015 and E2E-SEC-016 (red on a build that trusts the claim or follows any destination).
23. Failure texts of downloads and exports (`FR-NEW-010`, `FR-NEW-020`). The failure answers carry the exception text (`http_server.py:419-420`, `:448-450`, `:474-476`) and the editor shows it as `Export <FORMAT> échoué : <text>` in an alert (`static/editor.js:425`). In the library mode the refusal text must be the single text `Access denied.` with no prefix and no file, a lost session must give the sign in page, and any other failure must show the operating system reason with no file name or path. Detection signal: E2E-119 and E2E-173 (PPTX variant) fail when the prefix, a path or a file name appears.

