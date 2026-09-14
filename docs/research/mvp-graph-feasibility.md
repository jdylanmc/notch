# Microsoft Graph calendar feasibility for the Notch Pocket MVP

**Issue:** [#71](https://github.com/jdylanmc/notch/issues/71)  
**Feeds:** [#31](https://github.com/jdylanmc/notch/issues/31), [#21](https://github.com/jdylanmc/notch/issues/21)  
**Research date:** 2026-09-12  
**Mode:** Public documentation and static-source inspection only. No registration,
sign-in, token, tenant, mailbox, Keychain, calendar, build, or runtime access was
performed.

## Decision

**Supported candidate, with runtime proof still required.**

A native Swift/macOS implementation can use Microsoft Authentication Library
(MSAL) for iOS and macOS as a public client and call Microsoft Graph v1.0 with
delegated calendar permissions. The current MSAL release, 2.15.0, ships a Swift
Package Manager binary whose manifest targets macOS 14, matching Notch Pocket's
deployment target. Microsoft Graph documents both calendar enumeration and
`calendarView` for delegated work/school and personal Microsoft accounts.

The requested `DefaultAzureCredential()`-style experience is **not** available
as a general "reuse whichever Microsoft account is signed in somewhere"
credential chain in the Swift/macOS SDK:

- MSAL can silently reuse accounts already authorized in Notch Pocket's own
  cache.
- On managed Macs, MSAL can discover organizational accounts exposed by the
  Microsoft Enterprise single sign-on (SSO) extension. That extension is
  supplied by Company Portal, requires mobile device management (MDM)
  configuration, and is documented for Microsoft Entra accounts.
- MSAL 2.15.0 exposes device-wide SSO account enumeration on macOS, but its
  source explicitly says an `isSSOAccount` is available only for organizational
  accounts when the Entra SSO plug-in is present.
- On macOS 10.15 and later, interactive MSAL uses
  `ASWebAuthenticationSession` by default and can reuse Safari website state.
  This can reduce credential entry, but still presents Microsoft-controlled
  interaction and does not prove Notch Pocket has calendar consent.
- Shared token caches work only between cooperating apps configured with the
  same client ID, Apple signing relationship, and Keychain access group. They
  do not authorize reading arbitrary Microsoft apps' tokens.
- Azure CLI, .NET, Node, broker, browser, shared-cache, Enterprise SSO, and
  Platform SSO credentials are distinct mechanisms. MSAL for Swift does not
  document a `DefaultAzureCredential` chain or Azure CLI credential source.

Therefore, a safe product must model explicit accounts, let the user choose
each identity, acquire tokens for that exact account, and isolate failures per
account. It must not scrape tokens, select the first identity that happens to
succeed, or substitute an application/service identity.

### Confirmed interaction policy

The owner accepts interactive Microsoft account selection, consent, or
reauthentication when required, but prefers it to be rare. The implementation
should therefore:

1. Attempt silent token acquisition for the exact selected account.
2. Refresh through MSAL without showing UI whenever supported.
3. Mark only that account as requiring attention when MSAL returns
   `interactionRequired` or an equivalent policy/consent condition.
4. Show Microsoft-controlled interaction only after an explicit user action,
   except where the later specification identifies a security-critical reason
   to interrupt.
5. Never substitute another cached or device account.

This is a low-friction target, not a guarantee that tenant policy will permit
indefinite silent refresh. Consent revocation, Conditional Access, password or
device-policy changes, and refresh-token expiry can require interaction.

## Source/version reconciliation

| Evidence | Finding | Classification |
| --- | --- | --- |
| [MSAL 2.15.0 release](https://github.com/AzureAD/microsoft-authentication-library-for-objc/releases/tag/2.15.0), published 2026-08-20 | Latest public release found during this research. | Documented |
| [MSAL 2.15.0 `Package.swift`](https://github.com/AzureAD/microsoft-authentication-library-for-objc/blob/2.15.0/Package.swift) | Swift package declares `.macOS(.v14)` and Swift tools 5.9. | Documented |
| [MSAL repository README at 2.15.0](https://github.com/AzureAD/microsoft-authentication-library-for-objc/blob/2.15.0/README.md) | Browser-delegated MSAL supports work/school and personal Microsoft identities; Swift Package Manager is supported. "Native authentication" is an External ID customer feature and is not the workforce/personal Graph flow required here. | Documented |
| [Customize browsers and WebViews](https://learn.microsoft.com/entra/msal/objc/customize-webviews) and [MSAL 2.15.0 `MSALDefinitions.h`](https://github.com/AzureAD/microsoft-authentication-library-for-objc/blob/2.15.0/MSAL/src/public/MSALDefinitions.h) | Current documentation and source say macOS 10.15+ defaults to `ASWebAuthenticationSession`, which shares Safari website data. | Documented |
| [Configure SSO on macOS and iOS](https://learn.microsoft.com/entra/msal/objc/single-sign-on-macos-ios) | The page's introduction still says Safari SSO is unavailable on macOS and only `WKWebView` is supported, contradicting the current browser-specific page and 2.15.0 source. | Documentation conflict |
| Resolution | Use the versioned 2.15.0 API/source and the current browser-specific page for design; prove actual browser SSO behavior in the separately approved runtime test. Do not make zero-prompt acceptance depend on it. | Recommended |

## Capability matrix

| Required capability | Evidence | Status | Consequence |
| --- | --- | --- | --- |
| Work/school accounts | MSAL supports Microsoft Entra identities; Graph calendar APIs document delegated work/school support. [MSAL README](https://github.com/AzureAD/microsoft-authentication-library-for-objc/blob/2.15.0/README.md), [list calendars](https://learn.microsoft.com/graph/api/user-list-calendars?view=graph-rest-1.0), [calendarView](https://learn.microsoft.com/graph/api/calendar-list-calendarview?view=graph-rest-1.0) | Supported/documented | Use delegated user tokens, not application permissions. |
| Personal Microsoft accounts | The app registration can use `AzureADandPersonalMicrosoftAccount`; both calendar endpoints document delegated personal-account support. [Supported account types](https://learn.microsoft.com/entra/identity-platform/howto-modify-supported-accounts), [list calendars](https://learn.microsoft.com/graph/api/user-list-calendars?view=graph-rest-1.0), [calendarView](https://learn.microsoft.com/graph/api/calendar-list-calendarview?view=graph-rest-1.0) | Supported/documented; tenant/app registration unverified | Registration must include personal accounts. A real personal Outlook calendar must be tested. |
| N accounts, including at least two | `MSALPublicClientApplication` returns account collections, supports lookup by stable account identifier, and can use one application object across tenants. [Public client header](https://github.com/AzureAD/microsoft-authentication-library-for-objc/blob/2.15.0/MSAL/src/public/MSALPublicClientApplication.h), [account header](https://github.com/AzureAD/microsoft-authentication-library-for-objc/blob/2.15.0/MSAL/src/public/MSALAccount.h) | Supported SDK primitive; product flow runtime-unverified | Store explicit account records and never assume a two-account limit or use `accounts.first`. |
| Reuse Notch Pocket's prior authorization | `allAccounts`, account lookup, and `acquireTokenSilent` are documented. Silent acquisition can return `MSALErrorInteractionRequired`. [Acquire tokens](https://learn.microsoft.com/entra/msal/objc/acquire-tokens) | Supported/documented | Try silent acquisition for the selected stored account, then surface a per-account reconnect state. |
| Reuse an organizational account known to managed macOS | `accountsFromDeviceForParameters` includes accounts from the SSO extension on macOS 10.15+; `isSSOAccount` is limited to organizational accounts when the Entra SSO plug-in exists. [Public client header](https://github.com/AzureAD/microsoft-authentication-library-for-objc/blob/2.15.0/MSAL/src/public/MSALPublicClientApplication.h), [account header](https://github.com/AzureAD/microsoft-authentication-library-for-objc/blob/2.15.0/MSAL/src/public/MSALAccount.h) | Supported API; environment-dependent and runtime-unverified | Offer discovered eligible accounts for explicit selection. Company Portal presence alone is insufficient. |
| Enterprise SSO on macOS | Company Portal supplies the plug-in; MDM enrollment and a pushed configuration are required. Default macOS allowlisting favors Apple/Microsoft bundle prefixes, so `com.jdylanmc.notchpocket` may require administrator configuration. [Enterprise SSO plug-in](https://learn.microsoft.com/entra/identity-platform/apple-sso-plugin) | Supported only when tenant/device policy enables it | Treat as an optimization, never the only sign-in route. |
| Platform SSO | MSAL 2.15.0 exposes Platform SSO status and SSO-extension integration, but public evidence does not establish that every Platform SSO login is enumerable or usable by this third-party bundle/client ID. [MSAL definitions](https://github.com/AzureAD/microsoft-authentication-library-for-objc/blob/2.15.0/MSAL/src/public/MSALDefinitions.h), [Enterprise SSO plug-in](https://learn.microsoft.com/entra/identity-platform/apple-sso-plugin) | Incomplete/unknown for this app | Include in managed-Mac runtime proof; do not promise it. |
| Reuse a personal Microsoft login from another app | Device-wide SSO account source is documented as organizational-only. Browser website state may reduce prompts, but is not account/token inheritance. | Not documented as silent device-account reuse | Personal accounts need an interactive browser/account-selection path unless Notch Pocket already cached that account. |
| Reuse Safari sign-in state | Current MSAL browser documentation says macOS 10.15+ uses `ASWebAuthenticationSession` and shares Safari website data. [Customize browsers and WebViews](https://learn.microsoft.com/entra/msal/objc/customize-webviews) | Supported/documented, but interaction and consent can remain | Use the default system session. Do not force `WKWebView`, which does not share Safari data. |
| Reuse another app's shared token cache | Requires cooperating apps with the same client ID, signing relationship, and Keychain group. [Configure SSO](https://learn.microsoft.com/entra/msal/objc/single-sign-on-macos-ios) | Not applicable to arbitrary installed Microsoft apps | Do not inspect or join another vendor's Keychain group. |
| Reuse Azure CLI credentials | No such source exists in the MSAL Objective-C/Swift public API. The official Graph SDK list also has no Swift SDK. [MSAL public client header](https://github.com/AzureAD/microsoft-authentication-library-for-objc/blob/2.15.0/MSAL/src/public/MSALPublicClientApplication.h), [Graph SDK overview](https://learn.microsoft.com/graph/sdks/sdks-overview) | Unsupported for this native design | Do not invoke Azure CLI or reproduce `DefaultAzureCredential`. |
| Account-specific delegated consent | Microsoft states both the client and user must be authorized; existing sign-in does not grant Graph calendar access. [Permissions and consent](https://learn.microsoft.com/entra/identity-platform/permissions-consent-overview) | Required/documented | Consent or admin policy can still block each account independently. |
| Conditional Access | MSAL supports Conditional Access scenarios, but the actual tenant/device challenge is policy-dependent. [MSAL README](https://github.com/AzureAD/microsoft-authentication-library-for-objc/blob/2.15.0/README.md) | Supported by library; tenant outcome unknown | Preserve interaction-required and claims/policy failures instead of converting them to "signed out." |
| Enumerate calendars per account | `GET /me/calendars`; least delegated privilege is `Calendars.ReadBasic` for both account classes. Calendar exposes `id`, `name`, `isDefaultCalendar`, color, owner, and access properties. [List calendars](https://learn.microsoft.com/graph/api/user-list-calendars?view=graph-rest-1.0), [calendar resource](https://learn.microsoft.com/graph/api/resources/calendar?view=graph-rest-1.0) | Supported/documented | Initially select `isDefaultCalendar == true`; persist choices under the owning account key. |
| Read one selected calendar's daily occurrences | `GET /me/calendars/{id}/calendarView?startDateTime=...&endDateTime=...`; both account classes supported. [calendarView](https://learn.microsoft.com/graph/api/calendar-list-calendarview?view=graph-rest-1.0) | Supported/documented | Query each selected calendar and merge locally. |
| Expand recurring events | `calendarView` returns occurrences/exceptions within the range rather than requiring local recurrence expansion. [calendarView](https://learn.microsoft.com/graph/api/calendar-list-calendarview?view=graph-rest-1.0), [event resource](https://learn.microsoft.com/graph/api/resources/event?view=graph-rest-1.0) | Supported/documented | Do not expand recurrence rules locally. |
| Pagination | `calendarView` returns `@odata.nextLink` when results span pages. [calendarView](https://learn.microsoft.com/graph/api/calendar-list-calendarview?view=graph-rest-1.0) | Required/documented | Follow the opaque next link until absent; do not reconstruct it. |
| Local-day boundary | Request offsets in `startDateTime` and `endDateTime` control range interpretation; `Prefer: outlook.timezone` affects returned times, not those range parameters. [calendarView](https://learn.microsoft.com/graph/api/calendar-list-calendarview?view=graph-rest-1.0) | Supported/documented; product boundary unresolved | Compute start/end from one explicit agenda time zone and include offsets. |
| Personal appointments without attendees or links | `calendarView` returns event occurrences; the product must not filter by attendee or online-meeting presence. `subject`, `start`, `end`, and `isAllDay` are event properties. [event resource](https://learn.microsoft.com/graph/api/resources/event?view=graph-rest-1.0) | Supported/documented | Include all timed, non-cancelled events selected by the agreed temporal rules. |
| Least-privilege owned-calendar agenda | `Calendars.ReadBasic` reads events except body, attachments, and extensions and is available to personal accounts without mandatory admin consent in the permissions reference. [Permissions reference](https://learn.microsoft.com/graph/permissions-reference#calendarsreadbasic) | Supported/documented | Recommended initial scope: `Calendars.ReadBasic`; no write scope. |
| Join-link fidelity | Basic access can use structured `onlineMeeting.joinUrl`, `webLink`, and location fields, but cannot inspect the body where some organizers place links. [Event resource](https://learn.microsoft.com/graph/api/resources/event?view=graph-rest-1.0), [permissions reference](https://learn.microsoft.com/graph/permissions-reference#calendarsreadbasic) | Partially supported at basic scope | Escalate to `Calendars.Read` only if body-based link recovery is an accepted requirement. Do not request it preemptively. |
| Shared/delegated calendars | Direct owner-mailbox access is documented with `Calendars.Read.Shared`; shared custom calendars represented in the recipient mailbox have a separate local-copy route. [Shared/delegated calendars](https://learn.microsoft.com/graph/outlook-get-shared-events-calendars), [permissions reference](https://learn.microsoft.com/graph/permissions-reference#calendarsreadshared) | Supported in documented scenarios; discovery and private-item behavior need proof | Keep shared/delegated coverage as a separately tested capability and scope decision. |
| Calendar writes | Not required by #71; `Calendars.ReadWrite` is unnecessary. | Explicitly out of scope | Do not request write permission. |

## Recommended native Swift/macOS approach

### 1. Registration and authentication

Use one project-owned Microsoft identity platform **public client**
registration:

- Supported account type:
  `AzureADandPersonalMicrosoftAccount`.
- Native iOS/macOS redirect URI tied to the preserved bundle identifier:
  `msauth.com.jdylanmc.notchpocket://auth`.
- No client secret in the app.
- Start with delegated `Calendars.ReadBasic` plus the OpenID Connect scopes
  MSAL requires for sign-in/cache behavior. Add no write or app-only permission.
- Pin a reviewed MSAL release rather than tracking `main`. Version 2.15.0 is
  the current candidate and matches macOS 14, but dependency addition belongs
  to a later approved implementation slice.

The registration owner, client ID, publisher-verification choice, redirect
configuration, tenant approval, and release-environment separation are all
currently unknown. No registration was inspected or created.

### 2. Explicit multi-account identity model

Add a deep authentication module rather than spreading MSAL objects through
views:

```text
GraphAccountStore
  listEligibleAccounts()
  connectAccount()
  token(for exactAccount)
  disconnect(exactAccount)

GraphCalendarClient
  calendars(account)
  calendarView(account, calendar, interval)

GraphAgendaProvider
  selected calendars by account
  per-account refresh state
  merged normalized events
```

`GraphAccountStore` should:

1. Load Notch Pocket's cached MSAL accounts.
2. Query `accountsFromDeviceForParameters` for eligible SSO-extension accounts.
3. Deduplicate by MSAL's stable account identifier and environment, preserving
   tenant-profile identity where the selected resource tenant matters.
4. Present the resulting identities to the user. Never automatically select
   the first successful account.
5. For a selected account, try `acquireTokenSilent`.
6. Represent `interactionRequired`, consent denial, tenant policy,
   Conditional Access, network failure, and account removal as distinct
   per-account states.
7. Invoke interactive acquisition only after the affected account reports that
   attention is required and the user chooses to reconnect it.

Store account and calendar identifiers in centralized Defaults, but leave token
storage to MSAL. A calendar selection key must include the owning Graph account;
Graph calendar IDs are not a global namespace for product configuration.
Display names/usernames are labels, not persistence keys.

### 3. Graph transport

Microsoft does not list an official Swift Graph SDK. Use a small typed
`URLSession` client against `https://graph.microsoft.com/v1.0`:

- Inject the bearer token only for the exact account request.
- Decode narrow `Codable` response types.
- Follow each server-provided `@odata.nextLink`.
- Treat 401, 403, 404, 429, transport failures, decode failures, and partial
  multi-account failure explicitly.
- Honor Graph retry guidance, including `Retry-After`, in the implementation
  specification.
- Keep the account boundary on every request/result so one account cannot
  overwrite another account's state.

Calendar enumeration:

```http
GET /v1.0/me/calendars
  ?$select=id,name,color,hexColor,isDefaultCalendar,owner,canEdit,canViewPrivateItems
```

Daily events for every selected calendar:

```http
GET /v1.0/me/calendars/{calendar-id}/calendarView
  ?startDateTime={inclusive-start-with-offset}
  &endDateTime={exclusive-end-with-offset}
  &$select=id,iCalUId,subject,start,end,isAllDay,isCancelled,type,
           seriesMasterId,location,onlineMeeting,webLink,sensitivity,showAs
Prefer: outlook.timezone="{agreed-time-zone}"
```

The exact `$select` must be verified against `Calendars.ReadBasic` in runtime
proof. Do not add `body`, attachments, or extensions under the basic scope.

### 4. Merge and failure behavior

- Fetch accounts independently and retain a result/error state per account.
- A denied, expired, offline, or Conditional Access-blocked account must not
  suppress healthy accounts.
- Merge only after attaching the source account key and calendar key.
- Sort by normalized start time with a deterministic secondary key.
- Exclude cancelled events.
- Do not treat "no attendees" or "no online meeting" as non-events.
- Do not silently deduplicate across accounts or calendars. The same meeting
  can legitimately appear in multiple selected calendars, and Graph IDs are
  scoped to their mailbox/calendar context.
- Cache only normalized event metadata needed by the agreed UI and define its
  lifetime before implementation. Do not persist bearer tokens outside MSAL.

### 5. Existing Notch Pocket seam

Static inspection found an EventKit-specific provider behind
[`CalendarServiceProviding`](../../notchPocket/Providers/CalendarServiceProviding.swift),
with orchestration in
[`CalendarManager`](../../notchPocket/managers/CalendarManager.swift), shared
presentation models in
[`CalendarModel`](../../notchPocket/models/CalendarModel.swift) and
[`EventModel`](../../notchPocket/models/EventModel.swift), and calendar
selection persisted through centralized
[`Constants.swift`](../../notchPocket/models/Constants.swift).

The existing protocol is not sufficient for Graph because it:

- has no account identity or per-account authentication state;
- mixes events and reminders;
- represents authorization as EventKit global status;
- uses calendar IDs without an account namespace;
- returns only arrays, so one provider/account failure cannot be represented;
- includes write behavior for reminder completion, which Graph calendar does
  not require.

Later implementation should introduce a source-neutral agenda/provider boundary
and adapt the retained UI/models deliberately. It should not replace the
EventKit class in place with Graph-specific conditionals or remove existing
calendar/reminder code during the provider slice. The exact coexistence and
migration behavior belongs in the agreed specification.

## Remaining tenant and permission unknowns

These cannot be resolved from public documentation:

1. Who owns and maintains the Notch Pocket app registration.
2. Whether that registration may be multitenant plus personal-account capable.
3. Whether organizational tenants permit user consent to
   `Calendars.ReadBasic`, require admin consent, block unverified publishers,
   or impose other enterprise-app restrictions.
4. Whether the target managed Mac exposes accounts through the Enterprise SSO
   extension to `com.jdylanmc.notchpocket`, including any administrator
   allowlist requirement.
5. Whether Platform SSO on the target Mac makes the intended organizational
   account available to this MSAL client.
6. Which Conditional Access requirements apply to Graph calendar tokens and
   whether the chosen MSAL flow satisfies them.
7. Whether a representative personal Microsoft account has an Outlook calendar
   mailbox and grants the requested delegated scope.
8. Whether `Calendars.ReadBasic` returns every selected field needed by the
   retained Notch presentation and structured join-link path.
9. Which shared/delegated calendar shapes appear in `/me/calendars` for the
   target organizational account and which require
   `Calendars.Read.Shared`.
10. Whether account removal from the SSO extension, tenant revocation, password
    reset, or policy change produces the expected isolated reconnect state.

## Separately approved runtime proof plan

Use disposable/nonessential accounts and synthetic calendar data. Do not use
real workplace or personal appointments in captured evidence.

### Preconditions

- Human-approved development app registration with the proposed account
  audience, redirect URI, and only the candidate delegated scopes.
- One disposable organizational account, one disposable personal Microsoft
  account with Outlook calendar, and a third account of either class.
- For managed-Mac SSO coverage, an administrator-approved test device/profile;
  otherwise record that Enterprise/Platform SSO remains unverified.
- Synthetic calendars containing uniquely named timed events, an all-day event,
  an ongoing event, a cancelled event, a recurring series with an exception,
  enough events to force pagination, an event with no attendees/link, and
  structured/body-only meeting-link variants.

### Proof sequence

1. **Fresh app, organizational account already known to macOS**
   - Enumerate eligible device accounts without reading private calendar data.
   - Verify whether the exact account is exposed by the SSO extension.
   - Select it explicitly; record whether consent or authentication UI appears.
   - Verify the app cannot call Graph before its own delegated consent exists.
2. **Personal account already signed into Safari**
   - Start the default `ASWebAuthenticationSession`.
   - Verify account-selection behavior, consent behavior, cancellation, and
     whether website state reduces credential entry.
   - Do not call this silent device-account reuse.
3. **Third account**
   - Add it without replacing either existing account.
   - Restart and verify all three stable identities and calendar selections.
4. **Calendar selection**
   - Enumerate each account's calendars.
   - Verify the primary/default calendar is initially selected per account.
   - Change selections independently and verify persistence after restart.
5. **Daily view**
   - Query every selected calendar, follow pagination, and verify recurrence
     occurrences/exceptions.
   - Cross a daylight-saving transition and a local-midnight boundary using
     explicit request offsets.
   - Verify personal appointments with no attendees or join link remain.
6. **Failure isolation**
   - Deny consent for one account; other accounts remain usable.
   - Expire/revoke one account; only that account enters reconnect state.
   - Cancel interactive reauthentication; no account is silently substituted.
   - Simulate 401, 403, 404, 429, malformed payload, offline, and partial-page
     failure using a test transport before any real-account run.
7. **Shared/delegated coverage**
   - Test a shared custom calendar visible in the recipient mailbox and, if
     approved, a direct owner-mailbox delegated calendar.
   - Record the exact scope required, private-item redaction, and enumeration
     behavior rather than generalizing from one shape.
8. **Cleanup**
   - Remove synthetic calendar data and revoke the test app's consent.
   - Remove only Notch Pocket's cached test accounts. Do not globally sign out
     other apps or alter production SSO/MDM policy.

### Pass criteria

- At least one organizational and one personal account contribute timed events
  to one merged agenda, and a third account can be added.
- Every event retains its source account/calendar identity.
- Calendar selection persists independently per account.
- Recurrence, pagination, offsets, cancellation, and personal appointments are
  correct.
- One account's denial, expiry, policy block, or network failure does not erase
  or impersonate another account.
- Any prompt-free reuse claim is limited to the exact demonstrated source and
  configuration.

## Unresolved product choices

1. Whether the first release requires shared/delegated calendars or may ship
   owned calendars first while that separately tested capability remains
   pending.
2. Whether structured join links are sufficient under
   `Calendars.ReadBasic`, or body-based link recovery justifies requesting
   broader `Calendars.Read`.
3. Agenda time zone and "today" boundary, especially during travel and
   daylight-saving changes.
4. Whether ongoing events remain visible and whether already-ended events are
   retained for the day.
5. Whether all-day events are shown, hidden, or separately grouped.
6. Duplicate policy across accounts/shared calendars.
7. Partial-failure and stale-cache presentation when one account cannot refresh.
8. Whether widget instances inherit the global selected calendars or can
   override them.

## Confirmed product answer

Interactive Microsoft account selection, consent, and reauthentication are
acceptable when required. The preferred experience is silent operation for
long periods after initial authorization, with a clear per-account reconnect
action when Microsoft or tenant policy requires interaction.

## One recommended next question

**Recommendation:** deliver owned calendars first and keep shared/delegated
calendars as a separately permissioned, runtime-proven follow-up. Their Graph
paths and permission behavior differ, and requesting
`Calendars.Read.Shared` before the user enables that capability would broaden
consent unnecessarily.

**Question for the owner:** Must the first Graph calendar delivery include
shared/delegated calendars, or may it initially support calendars owned by each
connected account?

## Recommended next bounded action

After the owner answers the shared/delegated-calendar question, resolve the
remaining agenda semantics one question at a time and convert the evidence into
one agreed #31/#21 specification. Then split it into dependency-ordered,
test-driven slices beginning with pure account/event identity models and a
mocked Graph transport contract. Keep app registration, real sign-in, consent,
tenant changes, and live mailbox proof as a separately approved runtime slice.
