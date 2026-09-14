# MVP calendar core specification

**Issues:** [#71](https://github.com/jdylanmc/notch/issues/71),
[#31](https://github.com/jdylanmc/notch/issues/31),
[#21](https://github.com/jdylanmc/notch/issues/21)  
**Status:** Bounded core implemented locally with injected tests; pending
independent review and coordinator reconciliation. Not integrated into the
EventKit presentation or any live Microsoft path.  
**Evidence:** [Microsoft Graph feasibility research](../research/mvp-graph-feasibility.md)

## Problem Statement

Notch Pocket's current calendar path is built around one process-wide EventKit
store. Calendar identifiers are treated as globally unique, authorization is a
single EventKit status, events and reminders share one provider, and provider
methods return arrays that cannot distinguish "empty" from "failed."

The Microsoft Graph product direction requires multiple explicit Microsoft
accounts, independent calendars under each account, independent failures, and
event data that can later be merged into one agenda. Authentication, tenant
consent, daily boundary policy, shared-calendar launch scope, and presentation
replacement are not ready to implement.

The first implementation slice must create a small, testable calendar core that
can represent the required identities and data without accessing Microsoft,
EventKit, user preferences, or live calendar content. It must establish the
Graph wire boundary and failure contracts without changing working calendar,
reminder, settings, or presentation behavior.

## Solution

Add an isolated calendar-core module with:

1. Explicit, validated provider/account/calendar/event identities.
2. A caller-supplied half-open time interval.
3. Narrow Graph calendar and event payload decoding.
4. Deterministic pagination with typed failures.
5. An account-scoped provider interface and a coordinator that preserves one
   result per requested account.
6. Injected page transport suitable for XCTest fakes.

The slice does not add Microsoft Authentication Library (MSAL), perform
authentication, create an app registration, send real network requests, read
EventKit, persist selections, or wire Graph into the current user interface.

## User Stories

1. As a user with multiple Microsoft accounts, I want every calendar to retain
   its owning account identity, so that calendars with identical provider IDs
   cannot collide.
2. As a user with multiple calendars, I want every event to retain its source
   calendar and account, so that the combined agenda never attributes an event
   to the wrong identity.
3. As a user adding a third or later account, I want the model to remain
   unbounded, so that the implementation does not encode a two-account limit.
4. As a user whose one account fails to refresh, I want other account results
   preserved, so that one tenant or network failure does not erase my whole
   agenda.
5. As a user with a personal appointment, I want an event with no attendees or
   online-meeting data to decode normally, so that personal events are not
   treated as invalid.
6. As a user with cancelled, all-day, ongoing, or recurring events, I want the
   wire data preserved without premature product filtering, so that later
   agenda policy can make explicit decisions.
7. As a caller that already chose a requested interval, I want the provider to
   use that exact interval, so that the core does not silently decide what
   "today" means.
8. As a caller fetching a large calendar, I want all Graph pages loaded in
   order, so that later pages are not omitted.
9. As a user encountering a later-page failure, I want an explicit failure
   rather than a success-shaped partial result, so that incomplete agenda data
   is not presented as complete.
10. As a developer, I want malformed identities, timestamps, links, and paging
    URLs rejected explicitly, so that attacker-influenced event data cannot
    enter the domain as valid.
11. As a developer, I want protocol-driven fake transports, so that tests never
    access live Microsoft accounts, calendars, tokens, preferences, or the
    network.
12. As a maintainer, I want the existing EventKit provider and reminder
    behavior left untouched, so that this preparatory slice cannot regress the
    current product.

## Implementation Decisions

### 1. Calendar core is provider-neutral

The domain types must not import EventKit, MSAL, SwiftUI, AppKit, or a Graph SDK.
Foundation value types are permitted.

The module will use one provider namespace value plus provider-issued
identifiers. "Graph" is one provider namespace, not an assumption embedded in
calendar or event identity.

### 2. Identity hierarchy

The core will define validated, `Hashable`, `Codable`, and `Sendable` values:

- **Provider identity:** stable namespace for a calendar provider.
- **Account identity:** provider identity plus the provider-issued stable
  account identifier.
- **Calendar identity:** account identity plus provider calendar identifier.
- **Event identity:** calendar identity plus provider event identifier.

Every raw identifier must reject empty or whitespace-only values. Display
names, usernames, email addresses, calendar names, and colors are metadata and
must never participate in identity.

This hierarchy intentionally makes identical Graph calendar or event IDs under
different accounts unequal. It also prevents an EventKit identifier from
colliding with a Graph identifier.

Tenant-profile identity may later be encoded in the provider-issued account
identifier by the authentication adapter. The core does not interpret MSAL
accounts or tenants.

### 3. Requested interval is passed through

The core will represent one half-open interval:

- inclusive start;
- exclusive end;
- start must be earlier than end.

No method in this slice computes start of day, end of day, "upcoming," the
current time zone, or daylight-saving behavior. The caller supplies concrete
`Date` values, and provider requests must preserve them exactly.

This leaves the unresolved agenda-day policy outside the core while making the
future Graph query deterministic and testable.

### 4. Narrow domain records

The core calendar record contains:

- calendar identity;
- display name;
- whether the provider marks it as the default calendar;
- optional provider color metadata.

The core event record contains:

- event identity;
- title;
- start and end `Date`;
- all-day flag;
- cancelled flag;
- optional location label;
- optional structured online-meeting join URL;
- optional provider web URL;
- optional series-master provider identifier;
- provider event type, sensitivity, and availability as forward-compatible raw
  values rather than closed enums.

Attendees, body, attachments, extensions, write metadata, and reminders are not
part of this slice.

The decoder preserves cancelled and all-day events. Filtering them is a later
product-policy decision. It also preserves provider order and duplicate
records; cross-account or cross-calendar deduplication remains unresolved.

### 5. Narrow Graph wire records

Graph wire types remain internal to the Graph adapter and decode only fields
needed by the core:

- Calendar page: `value`, optional `@odata.nextLink`.
- Calendar item: `id`, `name`, `isDefaultCalendar`, optional `color` and
  `hexColor`.
- Event page: `value`, optional `@odata.nextLink`.
- Event item: `id`, `subject`, `start`, `end`, `isAllDay`, `isCancelled`,
  optional `location`, `onlineMeeting`, `webLink`, `seriesMasterId`, `type`,
  `sensitivity`, and `showAs`.

Unknown JSON properties are ignored. Missing or malformed required properties
produce a decoding/invalid-payload failure; they do not become empty strings,
epoch dates, or omitted records.

An event with no attendees, no online meeting, no location, and no web URL is
valid.

### 6. Date-time normalization

Graph `dateTimeTimeZone` values are decoded as a pair of raw date-time and time
zone strings before conversion.

For this slice, the Graph request contract asks for response times in UTC. The
normalizer accepts Graph's documented fractional-second variations tagged as
UTC and produces absolute `Date` values. It rejects malformed values.

The request interval still carries its caller-supplied offsets; requesting UTC
response values must not change or recompute the requested interval.

Mapping arbitrary Windows time-zone identifiers to Foundation zones is outside
this slice. The raw provider time-zone value may be retained internally for
diagnostics but is not a product time-zone decision.

### 7. Page transport is injected

The Graph adapter depends on a small asynchronous page-transport protocol. The
transport receives a value describing:

- the account identity;
- the initial Graph-relative resource and query;
- or the validated next-page URL.

The transport returns response bytes plus an HTTP response description. It
does not acquire tokens. Authentication and bearer injection are future
adapters outside this slice.

Tests use deterministic in-memory fakes. No `URLProtocol`, live `URLSession`,
network server, credential, Keychain, or account fixture is necessary for this
core.

### 8. Pagination is complete or failed

The page runner:

1. loads the first page;
2. decodes records in response order;
3. validates and follows the opaque `@odata.nextLink`;
4. stops only when no next link remains;
5. rejects a repeated next link as a pagination cycle;
6. rejects non-HTTPS next links or links outside
   `graph.microsoft.com`;
7. returns no success value if any page fails.

It does not rebuild next links, deduplicate records, hide later-page errors, or
return a partial success.

### 9. Typed errors

The Graph adapter exposes errors that callers can distinguish:

- invalid account/calendar/event identity;
- invalid requested interval;
- transport failure;
- non-success HTTP status;
- unauthorized (`401`);
- forbidden/consent-or-policy failure (`403`);
- not found (`404`);
- throttled (`429`) with parsed `Retry-After` when present;
- decoding failure;
- invalid payload;
- invalid next-page URL;
- pagination cycle.

The core preserves the underlying status and safe diagnostic context without
including access tokens, response bodies containing private event data, or
personally identifying account labels.

Retry execution is not implemented in this slice. The typed throttling contract
allows a later policy layer to schedule retries without hiding the original
failure.

### 10. Account-scoped provider seam

The new provider interface operates on exactly one account per call:

- list calendars for an account;
- list events for an account, a set of calendar identities owned by that
  account, and an exact interval.

Passing a calendar identity owned by another account is an explicit validation
failure before transport is called.

A small coordinator may invoke the provider for multiple accounts and returns
an ordered collection of account outcomes. Each outcome contains either that
account's records or that account's typed failure. It does not flatten failures
into one global error and does not substitute another account.

Concurrency policy is deliberately not fixed in this slice. Tests assert
result isolation and deterministic output ordering, not whether calls execute
serially or concurrently.

### 11. Reconciliation with existing EventKit code

The existing `CalendarServiceProviding` seam remains unchanged. Its access
request, EventKit calendar/reminder enumeration, event conversion, reminder
completion, and current `CalendarManager` wiring remain the production path.

The new core is additive because the existing seam:

- uses EventKit types in its authorization API;
- has no explicit provider or account identity;
- mixes events and reminders;
- treats calendar IDs as unscoped strings;
- returns arrays without failure information;
- includes reminder write behavior.

This slice does not retrofit the existing protocol, inject the new provider
into `CalendarManager`, migrate Defaults, change settings, or adapt core records
to the existing presentation models. Those changes require an agreed provider
integration specification after the core contract is proven.

### 12. No shared-calendar claim

Core identities can represent any calendar owned by an account context, but
this slice does not identify a calendar as shared/delegated, request shared
permissions, construct owner-mailbox paths, or claim shared-calendar support.

The open shared/delegated launch-scope decision does not block this core. It
blocks later permission selection, enumeration semantics, and acceptance
criteria for shared calendars.

## Testing Decisions

Tests use XCTest and `@testable import notchPocket`, following existing pure
logic tests. They assert externally visible values and errors, not private
method calls or concrete task scheduling.

All fixtures are inline synthetic JSON or in-memory fake transport responses.
They contain invented identifiers, names, URLs, and timestamps. They do not
read live calendars, preferences, files outside a test-owned temporary
directory, credentials, Keychain, location, devices, or the network.

### Red phase: identity and interval

The first test run must fail to compile or fail assertions because the new core
types do not exist.

1. Two account identities with the same external account ID but different
   providers are unequal.
2. Two calendar identities with the same provider calendar ID but different
   accounts are unequal.
3. Two event identities with the same provider event ID but different
   calendars are unequal.
4. Identity values round-trip through `Codable` without losing hierarchy.
5. Changing display metadata does not change identity.
6. Empty and whitespace-only provider/account/calendar/event IDs are rejected.
7. A valid interval preserves exact start and end instants.
8. Equal or reversed interval bounds are rejected.

### Green phase 1: identity and interval

Implement only the validated identity hierarchy and interval needed to pass
the first tests. Do not add Graph, EventKit, Defaults, or UI behavior.

### Red phase: Graph decoding

1. A minimal calendar payload decodes ID, name, default status, and optional
   color metadata while ignoring unknown fields.
2. A minimal personal appointment with no attendees, online meeting, location,
   or web URL decodes successfully.
3. An event decodes UTC start/end values with and without fractional seconds.
4. All-day and cancelled flags are preserved, not filtered.
5. Optional structured join and web URLs decode when valid.
6. Unknown event type, sensitivity, and availability values are preserved.
7. Missing calendar ID/name or event ID/start/end produces an explicit failure.
8. Empty required IDs and malformed date-time values produce an invalid-payload
   failure.
9. A malformed optional URL produces an invalid-payload failure rather than
   being silently discarded.
10. Unknown extra properties do not break decoding.

### Green phase 2: Graph decoding

Implement narrow wire records and a mapper into the provider-neutral domain.
Do not add authentication, a real network client, body parsing, attendees,
reminders, or presentation-model conversion.

### Red phase: pagination and HTTP errors

1. A page without `@odata.nextLink` makes one fake transport request.
2. Three pages produce all records once and in page order.
3. The second request uses the exact opaque next link returned by page one.
4. A repeated next link produces `paginationCycle`.
5. An HTTP next link, a different host, or a malformed URL produces
   `invalidNextPageURL` before transport is called.
6. A page-two transport failure produces one failure and no partial records.
7. `401`, `403`, and `404` map to their distinct typed errors.
8. `429` preserves a numeric or HTTP-date `Retry-After` value when valid.
9. Invalid JSON produces `decoding`.
10. A structurally valid page containing an invalid required record produces
    `invalidPayload`; it does not drop only that record and report success.

### Green phase 3: pagination and errors

Implement the injected page transport contract, response validation, page
runner, safe next-link validation, and typed errors. Do not implement automatic
retry or real authorization.

### Red phase: provider isolation

1. Calendar listing sends the exact requested account identity to the fake
   transport.
2. Event listing forwards the exact caller-supplied interval unchanged.
3. Event listing forwards only the requested provider calendar IDs.
4. A calendar belonging to another account fails before transport.
5. Two accounts with identical provider calendar IDs produce separate
   identities and outcomes.
6. Account A success plus account B failure returns both independent outcomes.
7. Account A failure does not erase account B records.
8. Coordinator output order follows input account order regardless of fake
   completion order.
9. Duplicate event payloads are preserved; this slice does not invent a
   deduplication policy.

### Green phase 4: provider and coordinator

Implement the account-scoped Graph provider over the tested decoder/page
runner, plus the smallest multi-account result coordinator. Do not wire it to
`CalendarManager` or existing views.

### Refactor phase

After all targeted tests are green:

- remove duplicated fixture builders;
- keep protocol surfaces minimal;
- keep Graph wire types internal;
- preserve typed errors and identity validation;
- avoid adding abstractions not required by a red test.

### Validation after coordinator authorizes implementation

Use the repository's canonical targeted XCTest command with this worktree's
private derived-data/TMPDIR configuration as directed by the coordinator.
Then run the smallest build and changed-file lint gates covering the core.
Do not run live app, account, Graph, EventKit, or permission probes.

The parent coordinates final full-suite validation after sibling work is
reconciled.

## Dependency-Ordered Implementation Scope

1. **Core identity and interval**
   - Add tests first.
   - Add provider/account/calendar/event identities and interval validation.
   - No dependencies on Graph or existing calendar code.
2. **Graph fixture decoder**
   - Add synthetic JSON tests first.
   - Add internal wire records and domain mapping.
   - Depends only on core identity/interval.
3. **Pagination and typed failure runner**
   - Add fake-transport tests first.
   - Add transport protocol, response contract, next-link validation, and
     complete-or-failed page loading.
   - Depends on the decoder.
4. **Account-scoped Graph provider**
   - Add account/calendar ownership and exact-interval forwarding tests first.
   - Add provider implementation over injected page transport.
   - Depends on identities, decoder, and pagination.
5. **Multi-account outcome coordinator**
   - Add independent-result and deterministic-order tests first.
   - Add the smallest coordinator returning one outcome per account.
   - Depends on the provider protocol, not on MSAL or UI.
6. **Reconciliation checkpoint**
   - Review complete new/changed files against this specification and
     repository standards.
   - Stop before EventKit integration, Defaults migration, authentication, or
     UI wiring.

Each step must be independently reviewable and leave existing runtime behavior
unchanged.

## Acceptance Criteria

1. Provider, account, calendar, and event identities are explicit, validated,
   codable, sendable, and collision-safe across accounts/providers.
2. The core accepts and forwards an exact valid interval without computing a
   day boundary.
3. Synthetic Graph calendar/event payloads decode into narrow provider-neutral
   records, including personal appointments without meeting metadata.
4. Required malformed data fails explicitly.
5. Pagination follows safe opaque Graph next links, detects cycles, and never
   reports partial pages as complete.
6. HTTP/auth/policy/throttle/decoding/payload failures remain distinguishable.
7. One account's failure is isolated from every other account outcome.
8. Cross-account calendar identities are rejected before transport.
9. Tests use only injected fakes and synthetic fixtures.
10. No MSAL dependency, app registration, token acquisition, live Graph call,
    EventKit replacement, Defaults migration, or UI behavior change is present.
11. Existing calendar/reminder source and presentation files are unchanged by
    the bounded core slice.

## Out of Scope

- MSAL dependency or account APIs.
- App registration, client ID, redirect URI, consent, tokens, Keychain,
  Enterprise SSO, Platform SSO, or browser interaction.
- A real `URLSession` Graph transport or bearer-token injection.
- Live Microsoft Graph, mailbox, calendar, or tenant access.
- Shared/delegated calendar permissions or support claims.
- EventKit replacement, adapter, migration, or permission changes.
- Reminder reads/writes.
- Defaults schema or calendar-selection migration.
- Calendar settings or agenda UI.
- Day boundary, travel time zone, all-day, ongoing/past, duplicate, stale-cache,
  refresh, or widget-filtering product policies.
- Body-based meeting-link recovery or `Calendars.Read` scope.
- Automatic throttling retry.
- Runtime app launch or feature proof.

## Further Notes

### Confirmed product decision

The owner accepts interactive Microsoft sign-in, consent, or reauthentication
when required, but prefers it to happen rarely. That decision shapes the later
authentication adapter, not this core slice.

### Exact unresolved implementation decision

There is **no missing decision blocking this core slice**.

The unresolved product question remains whether the first Graph calendar
delivery must include shared/delegated calendars or may initially support only
calendars owned by each connected account. The core must remain capable of
account-scoped identity either way, but must not add shared-calendar paths,
permissions, metadata, or claims until that question is answered and runtime
evidence exists.
