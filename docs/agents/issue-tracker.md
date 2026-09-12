# Issue tracker: GitHub

Issues and specs live in `jdylanmc/notch`. Use `--repo jdylanmc/notch` for
`gh issue` and `gh pr` commands. For `gh api`, use explicit
`repos/jdylanmc/notch/...` endpoints; it does not accept `--repo`.
Never infer the historical upstream as the destination.

Read issue bodies, labels and relevant comments before acting. Search for
duplicates before creating issues. Publishing a spec means creating a GitHub
issue, within the current task's write authorization.

PRs target `pocket`. PRs as a request surface: no.

Before applying a configured label, check that it exists. Setup records label
names but does not create them. Missing labels require an explicit approved
creation or a reported blocker, not a successful-looking partial publication.

## Wayfinding operations

Maps use `wayfinder:map`; child tickets use `wayfinder:<type>` for research,
prototype, grilling or task. Preserve existing issue relationships.

Use native GitHub sub-issues and blocking dependencies. Dependency API writes
require the blocker's numeric database ID, not its issue number or node ID.
If the tracker lacks these capabilities, document explicit task-list and
`Blocked by` relationships instead; do not disguise API failures as success.

Choose unassigned, unblocked children in map order. Claim, comment, close and
update the map only within authorized scope. Labels and issue closure do not
replace acceptance evidence or the foundation gate.

Closing a blocking issue does not by itself establish #54: new-feature work
also requires the user's foundation acceptance. Readiness labels identify
specified work, not authorization to begin it.
