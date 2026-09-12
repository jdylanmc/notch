# caveman-review

One-line PR comments. Location, problem, fix. No throat-clearing.

## What it does

Generates code review comments in `L<line>: <severity> <problem>. <fix>.` format. One line per finding. Severity emoji: 🔴 bug, 🟡 risk, 🔵 nit, ❓ question. Drops "I noticed that...", hedging, and restating what the diff already shows. Keeps exact line numbers, backticked symbols, and concrete fixes.

Auto-clarity: drops terse mode for CVE-class security findings, architectural disagreements, and onboarding contexts where the author needs the *why*. Resumes terse for the rest.

Output only — does not approve, request changes, or run linters.

## How to invoke

```
/caveman-review
```

Also triggers on "review this PR", "code review", "review the diff".

## Example output

```
L42: 🔴 bug: user is optional after first(where:). Unwrap with guard let before reading email.
L88-140: 🔵 nit: 50-line fn does 4 things. Extract validate/normalize/persist.
L23: 🟡 risk: no retry on 429. Wrap in withBackoff(3).
L107: ❓ q: why drop the cache here? Reads on next request will miss.
```

## See also

- [`SKILL.md`](./SKILL.md) — full LLM-facing instructions
- [Upstream Caveman README](https://github.com/juliusbrussee/caveman/blob/15581d14007fd01fb3f132016741962f34936ca2/README.md) — source overview, not additional installation instructions
- [Local packet guide](../README.md) — repository routing and boundaries
