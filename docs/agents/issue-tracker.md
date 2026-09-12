# Issue tracker: GitHub

Issues and specs live in `jdylanmc/notch`. Use the `gh` CLI with explicit
`--repo jdylanmc/notch`; never infer the historical upstream as the destination.

Read issue bodies, labels and relevant comments before acting. Search for
duplicates before creating issues. Publishing a spec means creating a GitHub
issue, within the current task's write authorization.

PRs target `pocket`. PRs as a request surface: no.

## Wayfinding

Maps use `wayfinder:map`; child tickets use `wayfinder:<type>` for research,
prototype, grilling or task. Preserve existing issue relationships.

Use native GitHub sub-issues and blocking dependencies. Dependency API writes
require the blocker's numeric database ID, not its issue number or node ID.
If the tracker lacks these capabilities, document explicit task-list and
`Blocked by` relationships instead; do not disguise API failures as success.

Choose unassigned, unblocked children in map order. Claim, comment, close and
update the map only within authorized scope. Labels and issue closure do not
replace acceptance evidence or the foundation gate.
