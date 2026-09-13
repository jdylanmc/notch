# Apple Notes-backed quick notes feasibility

**Issue:** [#72](https://github.com/jdylanmc/notch/issues/72)

**Research date:** 2026-09-13

**Repository baseline:** `585b9415a5146bc206427f1c74cc9d53c39b8eb9`

**Decision context:** [MVP product direction](https://github.com/jdylanmc/notch/issues/68#issuecomment-5649878256), [developer-ready foundation](https://github.com/jdylanmc/notch/issues/54#issuecomment-5649837337)

## Verdict

Apple Notes is a **supported candidate source of truth through its public
Apple Events scripting interface**, but the documented interface is not
evidence of lossless general-purpose editing.

The safest staged candidate is:

1. let the user select one Notes folder after Automation authorization;
2. identify accounts, folders and notes by the dictionary's read-only `id`;
3. list and open notes;
4. allow quick capture by creating a new, app-owned note in that folder; and
5. refuse in-Notch write-back for locked, shared, attachment-bearing or
   unproven rich-content notes.

That candidate does **not** satisfy the confirmed full product direction by
itself. Existing-note editing, autosave and collection management remain gated
on disposable-note runtime evidence and explicit product acceptance of any
unsupported-content behavior.

Direct access to the Notes database, containers or account files is not a
supported alternative. No such access was performed in this research.

## Evidence scope and confidence

| Evidence | Provenance | Source confidence | Runtime confidence |
| --- | --- | --- | --- |
| Notes scripting objects and properties | Static `/System/Applications/Notes.app/Contents/Resources/Notes.sdef`; Notes 4.13 (3146.141.6), bundle `com.apple.Notes`, file modified 2026-08-12, inspected 2026-09-13 on macOS 26.6.2 | High for this installed version | None; Notes was not launched or queried |
| Standard `make`, `delete`, `duplicate`, `exists`, `move` commands | Static `/System/Library/ScriptingDefinitions/CocoaStandard.sdef`, included by `Notes.sdef` | High for declared terminology | None; declaration does not prove every object accepts every command safely |
| Sandbox and Automation requirements | Apple entitlement and macOS Help documentation, accessed 2026-09-13 | High | None for Notch Pocket's Notes target |
| Repository integration gaps | Static source at the stated baseline | High | None |
| Rich-content preservation, autosave and conflict behavior | No public contract found in the scripting dictionary or cited Apple documentation | High confidence that it is undocumented here | Unknown until separately approved disposable-data checks |

The local source is newer than the app's macOS 14 deployment target. It proves
what Notes 4.13 and the macOS 26.5 Software Development Kit (SDK) declare, not
that every declaration behaves identically on macOS 14. Any implementation
must compile against the selected current SDK while preserving the project's
macOS 14 deployment target, then run the same disposable contract on macOS 14
and the current supported host.

## Documented approaches

| Approach | Documented capability | Fit |
| --- | --- | --- |
| In-process Apple Events through Scripting Bridge (`SBApplication`) | Apple describes Scripting Bridge as an Objective-C interface generated from an app's scripting dictionary. It sends Apple Events to the target app. | Candidate. Typed generated wrappers can centralize Notes terminology, errors and test seams. Swift interoperability and generated-interface maintenance need an implementation proof. |
| In-process AppleScript through `NSAppleScript` | Compiles and executes AppleScript, which sends Apple Events according to the target dictionary. | Technically possible, but string-built scripts add quoting, type and error-mapping risk. Do not use shell `osascript`; it adds no capability and was prohibited for this pass. |
| Direct Apple Event construction | Lowest-level use of four-character event/class/property codes from the dictionary. | Possible but unnecessarily error-prone unless Scripting Bridge cannot express a required operation. |
| `open note location` / `show` | Notes declares `open note location` and `show` commands. | Good for handing unsupported notes to Notes without rewriting content. `show` may activate or present Notes and needs separate user-approved interaction testing. |
| Notes database/container access | No public Notes data framework or database schema was identified. App Sandbox file access does not create a supported Notes data API. | Unsupported; do not implement. |
| Shortcuts or UI automation | Not a documented data API for stable folder/note identity or lossless editing. Accessibility/System Events would operate UI rather than the Notes data model. | Not recommended and outside this task. |

Primary Apple background: [How Mac scripting works](https://developer.apple.com/library/archive/documentation/LanguagesUtilities/Conceptual/MacAutomationScriptingGuide/HowMacScriptingWorks.html),
[Scripting Bridge Programming Guide](https://developer.apple.com/library/archive/documentation/Cocoa/Conceptual/ScriptingBridgeConcepts/Introduction/Introduction.html).
These are archived Apple documents; the installed Notes dictionary is the
current first-party capability declaration inspected here.

## Exact Notes dictionary capability

The installed dictionary declares:

- application elements: `account`, `folder`, `note`, `attachment`;
- `account`: writable `name`, read-only `id`, `default folder`, child folders
  and notes;
- `folder`: writable `name`, read-only `id`, read-only `shared`, read-only
  `container`, child folders and notes;
- `note`: writable `name`, read-only `id`, read-only `container`, writable
  `body`, read-only `plaintext`, creation/modification dates, read-only
  `password protected`, read-only `shared`, and attachment elements;
- `attachment`: read-only name, `id`, container, content identifier, dates,
  URL and shared state; hidden file `contents` supports creation and the
  attachment responds to the standard `save` command;
- `show` for accounts, folders, notes and attachments; and
- `open note location` for a text URL, with scripting access group
  `com.apple.Notes.openlocation`.

Static citations:

- `/System/Applications/Notes.app/Contents/Resources/Notes.sdef:10-31`
- `/System/Applications/Notes.app/Contents/Resources/Notes.sdef:57-108`
- `/System/Applications/Notes.app/Contents/Resources/Notes.sdef:110-142`
- `/System/Applications/Notes.app/Contents/Resources/Notes.sdef:145-195`
- `/System/Library/ScriptingDefinitions/CocoaStandard.sdef:120-169`

### Capability matrix

| Operation | Documented surface | Feasibility and hard boundary |
| --- | --- | --- |
| Enumerate accounts/folders/notes | Declared elements and readable properties | Candidate after Automation authorization. The Automation grant is to control Notes; the selected-folder boundary must be enforced by Notch Pocket, not assumed from the OS grant. |
| Select a folder | Read folder/account `id`, name and container | Candidate. Persist IDs, but validate the object still exists and remains in the expected account whenever used. The dictionary calls IDs unique but does not document lifetime across account removal, migration or OS versions. |
| Read note | `body` HTML, read-only `plaintext`, dates and metadata | Candidate for display/indexing. HTML is an interchange representation, not a documented lossless archive of Notes' internal model. |
| Create note | Standard `make` plus folder note elements and writable note properties | Candidate for disposable proof. Create directly in the selected folder and retain the returned note `id`; never report saved before re-reading the created object. |
| Rename note | Writable `name` | Declared, but Notes says the name is normally the first line of `body`. The interaction between setting `name` and body content is unverified. |
| Update existing note | Writable `body` HTML | Declared but unsafe to enable generally. No preservation contract was found for formatting, links, lists/checklists, tables, drawings, scans, embeds or attachment placement. |
| Open in Notes | `show`; `open note location` | Candidate escape hatch for unsupported content. UI activation/presentation is runtime behavior, not statically proven. |
| Move/delete/duplicate | Cocoa Standard commands are included | Declared generic commands, but destructive semantics, supported object combinations and conflict behavior are unverified. Defer. |
| Locked note | `password protected` is read-only | Detectable. No unlock command or safe edit contract is declared. Treat as open-in-Notes only. |
| Shared note/folder | read-only `shared` | Detectable. Collaboration/conflict semantics are not declared. Treat as open-in-Notes only until proven and approved. |
| Attachments | metadata, hidden creation contents, attachment `save` | Presence can be detected. The dictionary does not expose a lossless note-body/attachment round trip. Do not rewrite an attachment-bearing note. |

## Authorization and sandbox implications

Apple states that a sandboxed app cannot send Apple Events to another app
unless it has a `com.apple.security.scripting-targets` entitlement or the
`com.apple.security.temporary-exception.apple-events` entitlement. Apple calls
`scripting-targets` preferred when the target publishes access groups and says
the temporary exception is used when it does not.

The inspected Notes dictionary publishes an access group only for
`open note location`. It does not publish an access group for general account,
folder, note or attachment access. General Notes scripting therefore appears
to require the temporary Apple Events exception for `com.apple.Notes`; this is
a strong static inference, not a signing/runtime proof.

Notch Pocket currently:

- enables App Sandbox and `com.apple.security.automation.apple-events`;
- lists only `com.spotify.client` and `com.apple.Music` under
  `com.apple.security.temporary-exception.apple-events`; and
- uses the music-specific `NSAppleEventsUsageDescription` text
  `"This app uses AppleEvents to control music"`.

Repository citations:

- `notchPocket/notchPocket.entitlements:5-32`
- `notchPocket.xcodeproj/project.pbxproj:1461-1501`
- `notchPocket.xcodeproj/project.pbxproj:1530-1569`

An implementation would require separately approved entitlement and purpose
string changes. The system Automation consent names the controlling app and
controlled app. It does not constrain Notes access to the folder selected
inside Notch Pocket. Notch Pocket must enforce that narrower scope and explain
it honestly.

Primary sources:

- [Apple Events entitlement](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.automation.apple-events)
- [`NSAppleEventsUsageDescription`](https://developer.apple.com/documentation/bundleresources/information-property-list/nsappleeventsusagedescription)
- [App Sandbox temporary Apple Event exception](https://developer.apple.com/library/archive/documentation/Miscellaneous/Reference/EntitlementKeyReference/Chapters/AppSandboxTemporaryExceptionEntitlements.html)
- [macOS Automation consent](https://support.apple.com/guide/mac-help/allow-apps-to-automate-and-control-other-apps-mchl108e1718/mac)

## Fidelity, autosave and conflict boundaries

No cited public source specifies:

- which Notes HTML constructs are accepted or emitted;
- whether a write to `body` preserves unsupported internal structures;
- how links, checklists, tables, drawings, scans, files and inline attachments
  round-trip;
- how a locked note behaves before or after Notes is unlocked;
- shared-note conflict or collaboration semantics;
- atomic compare-and-swap, revision tokens or merge behavior;
- whether setting `name` rewrites the first body line;
- whether Apple Events return before Notes/iCloud persistence; or
- what happens when a note is moved, deleted or edited externally during a
  Notch Pocket autosave.

`modification date` is useful as an optimistic preflight signal but is not a
documented revision token. A safe implementation must never overwrite when the
last-read modification date or body fingerprint changed. It must retain the
user's draft locally as recovery material while clearly stating that the draft
was **not saved to Apple Notes**. That recovery buffer is not a second
authoritative notes database.

## Can quick capture be separated safely?

**Yes, as a proof and staged capability, not as a replacement product
decision.**

Creating a new note in the selected folder avoids reading and rewriting an
existing note's unsupported structures. The operation can be verified by the
returned note ID, container ID and a read-back of the submitted plain content.
If creation fails or permission is denied, the capture text must remain an
explicit unsaved draft.

This does not establish safe editing of existing notes, rich quick capture,
shared-folder behavior or collection-management semantics. Shipping only this
subset requires explicit product acceptance; it cannot be called completion of
#28 or #72 by inference.

## Recommended bounded implementation/TDD slice

No source, entitlement or dependency changes are authorized by this research.
For a future approved slice:

1. Add a `NotesGateway` protocol with typed account, folder, note snapshot and
   operation-result values. Keep Apple Event details behind one adapter.
2. Add a pure `NoteEditPolicy` that returns explicit capabilities such as
   `list`, `openInNotes`, `createPlainNote`, `editInNotch`,
   `blockedLocked`, `blockedShared`, `blockedAttachments`,
   `blockedRichContent`, `conflict`, `permissionDenied` and `unavailable`.
3. Test with fixtures only: duplicate folder names in different accounts,
   missing IDs, moved/deleted notes, changed modification dates, locked/shared
   flags, attachment metadata and representative HTML constructs.
4. Implement read-only folder/note listing plus `show`.
5. Implement plain-text creation only, with returned-ID/container validation
   and read-back. Keep existing-note mutation disabled.

Existing tab seams are `NotchViews` at
`notchPocket/enums/generic.swift:21-24` and the current Home/Shelf tab list at
`notchPocket/components/Tabs/TabSelectionView.swift:10-20`. Those citations
identify future integration surfaces; this pass made no product-source edits.

## Separately human-approved runtime checks

Use a disposable local Notes account/folder and disposable notes only:

1. verify denied and later granted Automation states without changing privacy
   settings programmatically;
2. select a folder with a duplicate-named sibling in another account and prove
   ID/container scoping;
3. create, read back, rename, move and delete disposable plain notes;
4. test external edits between read and autosave and prove no overwrite;
5. test note deletion/move while open and preserve an explicit unsaved draft;
6. compare before/after content for links, styles, lists/checklists, tables and
   attachments without using personal data;
7. verify locked/shared notes are refused and handed to Notes; and
8. repeat the accepted contract on macOS 14 and the current host.

These checks require separate authorization because they launch/control Notes,
create data and may prompt for Automation permission.

## Product questions and approvals still required

1. **Recommended:** accept a staged MVP rule where app-created plain notes can
   be edited in Notch Pocket, while locked, shared, attachment-bearing and
   unproven rich notes are open-in-Notes only until fidelity is demonstrated.
   Without that acceptance, the feature remains blocked on full fidelity.
2. Decide whether shared folders are eligible for selection. Recommendation:
   exclude them from the first implementation/runtime proof.
3. Decide whether collection management includes destructive move/delete and
   rename operations. Recommendation: first slice is list/open/create; add each
   destructive operation only after dedicated disposable-data proof.
4. Approve future Notes entitlement/purpose-string changes and the disposable
   Automation runtime plan. This research grants neither.

## Conclusion

#72 has a public-API candidate but not a completed feasibility proof for broad
editing. Quick capture can be isolated safely enough for a bounded proof.
General in-Notch editing remains blocked by undocumented fidelity and conflict
behavior plus the product approvals above.
