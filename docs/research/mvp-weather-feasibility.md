# MVP weather feasibility

**Status:** research complete; WeatherKit selected by the owner. No entitlement,
credential, live weather request, location request, source change, or runtime
validation was performed.

**Issue:** [#36 — Discover weather conditions and forecasts](https://github.com/jdylanmc/notch/issues/36)

**Product record:** [Agreed MVP product direction](https://github.com/jdylanmc/notch/issues/68#issuecomment-5649878256)

**Research date:** 2026-09-12

## Executive recommendation

Use Apple's native **WeatherKit** as the first provider. On 2026-09-12, the
owner confirmed the Apple Developer account and answered yes to the WeatherKit
recommendation, accepting:

- Apple Developer Program and App ID capability setup;
- the WeatherKit entitlement on the existing app identity;
- the shared 500,000-calls-per-month included allowance and paid tiers if a
  future user base exceeds it;
- required Apple Weather attribution and legal notice;
- WeatherKit's temporary-and-limited caching restriction.

WeatherKit is the best fit for the bounded macOS 14 MVP because it is a native
Swift API available from macOS 13, provides current/hourly/daily forecasts, and
does not require distributing a third-party API key in the app. Its commercial
terms and fixed included allowance are clearer for a future distributable app
than Open-Meteo's non-commercial free endpoint.

Open-Meteo is the strongest practical documented alternative. It is useful for
evaluation and offers first-party geocoding, but its free endpoint is
non-commercial, rate-limited, has no uptime guarantee, and requires attribution
next to displayed location data. Commercial use requires a paid customer API
key; safely distributing and rotating that key in a native client would be a
new operational/security problem unless the provider explicitly supports that
model or Notch Pocket adds a backend.

## Confirmed product requirements

The owner-approved product record establishes:

- current conditions and a useful forecast;
- multiple independently configured weather widgets;
- a manually selected location or opt-in current location for each widget;
- weather is independent of Microsoft Graph;
- shared dashboard/tab/layout code belongs to the widget lane, not this feature
  slice.

The following remain product decisions, not implementation assumptions:

- whether exact current coordinates may be persisted;
- final widget footprints and presentation.

## Focused provider comparison

| Concern | Apple WeatherKit | Open-Meteo |
| --- | --- | --- |
| macOS 14 support | Native WeatherKit types were introduced in macOS 13, so the repository's macOS 14 target is supported. | HTTPS JSON API; no operating-system dependency. |
| Setup | Apple Developer Program membership, WeatherKit enabled for the App ID, and the WeatherKit app capability/entitlement. | Free endpoint needs no signup/key. Commercial customer endpoint requires subscription, account, and API key. |
| Credential distribution | Native framework access is tied to the app identity/capability; no third-party secret needs to be embedded in the app. The REST variant would require signed developer tokens and is unnecessary for this native slice. | The commercial endpoint uses an `apikey` query parameter. Embedding one shared paid key in a distributed macOS client creates extraction, abuse, quota, and rotation risk. |
| Included cost/limits | Apple Developer Program membership includes 500,000 calls/month. Published paid tiers currently start at US$49.99/month for 1 million calls and rise by volume. Unused calls do not roll over. | Free endpoint is non-commercial and limited to 600/minute, 5,000/hour, 10,000/day, and 300,000/month with no uptime guarantee. Commercial plans provide 1M, 5M, or 50M+ monthly budgets; exact checkout price must be confirmed by the owner without signing up during research. |
| Commercial/redistribution terms | May be used in apps and value-added products under the Apple Developer Program agreement. Original Apple Weather Data cannot be sublicensed, bulk-downloaded, scraped, or used as a secondary database. The app may not charge specifically for untransformed original weather data. | Free API is expressly non-commercial. Paid subscription grants commercial use. API data remain CC BY 4.0, allowing adaptation and redistribution with attribution. |
| Attribution | Publishing software must provide the Apple Weather mark and legal attribution page/text returned by WeatherKit. | A linked “Weather data by Open-Meteo.com” attribution must appear next to every location where its data is displayed, plus CC BY 4.0 compliance and modification disclosure. |
| Location lookup | Weather requests accept `CLLocation`; weather retrieval does not itself provide a city search. Manual place search/geocoding needs a separate narrow Apple location-search/geocoding seam. Current location uses Core Location. | Separate Geocoding API searches names/postal codes and returns coordinates, timezone, and administrative metadata. |
| Weather data | Native aggregate exposes current weather plus hourly, daily, minute, alerts, and availability metadata. Minute forecasts and alerts can be regionally unsupported or temporarily unavailable; Apple says current weather is expected globally. | Forecast API supports current, hourly, and daily variables and automatically selects applicable model output. The API documents multi-day forecast controls and many selectable variables. |
| Caching/offline | Agreement permits caching/prefetch/storage only temporarily and on a limited basis to improve WeatherKit API performance. A durable offline weather database is not permitted by default. | Terms do not impose the same temporary-only cache wording, but data attribution remains attached and accuracy/availability are not guaranteed. |
| Privacy | A weather request necessarily resolves weather for coordinates. Current device location is separately protected by Core Location authorization. Apple's public WeatherKit pages reviewed here do not state a WeatherKit-specific coordinate-log retention period. | Open-Meteo says API logs may contain sensitive information such as geographic coordinates and deletes individual logs after 90 days. Paid usage is associated with the subscription. |
| Failure/service semantics | WeatherKit exposes data-availability metadata; the agreement disclaims interruption/accuracy guarantees. | Free endpoint has no uptime guarantee. Paid plans advertise reserved servers and a 99.9% uptime target, not an unconditional guarantee. |
| MVP fit | **Recommended.** Native, typed, no new package, no third-party client secret, and commercially clearer for this app. | Viable fallback if the owner rejects Apple capability/cost terms and explicitly approves non-commercial-only use or a paid-key distribution architecture. |

## Cost and refresh implications

The product has multiple widgets, but provider work should be keyed by resolved
location rather than widget identity. Widgets pointing to the same coordinate
must share one snapshot and one in-flight refresh.

Illustrative WeatherKit budget, assuming one provider call per refresh and a
continuously running app:

| Refresh cadence | Calls per distinct location per 30 days |
| --- | ---: |
| 15 minutes | 2,880 |
| 30 minutes | 1,440 |
| 60 minutes | 720 |

These figures are planning arithmetic, not measured WeatherKit accounting.
Public distribution multiplies consumption across installations. For example,
1,000 active installations with two distinct locations refreshed every 30
minutes would request about 2.88 million calls/month before foreground,
sleep/wake, network, and deduplication behavior is considered. The coordinator
must therefore choose an initial refresh budget and require instrumentation or
account usage review before public scale; the local MVP alone does not establish
production cost.

## Location and permission behavior

Manual locations and current location must remain separate choices:

- **Manual:** resolve a user-entered place to a stable display name, coordinate,
  and timezone. This path must not request device location permission.
- **Current:** request Core Location permission only after the user selects
  “Current Location” for a widget. Apple recommends requesting authorization
  immediately before the feature needs it, not at app launch. On macOS,
  When-in-Use and Always authorizations are functionally equivalent because a
  launched Mac app can continue running in the background, so the implementation
  should use the least-privileged request, obtain a bounded location update, and
  stop updates.
- **Denied/restricted:** affect only widgets configured for current location.
  Manual widgets continue working and the affected widget offers a manual
  location path; it must not repeatedly prompt.
- **Persistence:** persist manual location identity/coordinate/timezone. Do not
  persist exact current coordinates until the owner explicitly chooses that
  privacy behavior; they can be resolved per authorized session instead.

Adding current-location support later requires the macOS location usage
description and an authorized project/entitlement change. The current app
entitlements contain network-client access but no WeatherKit entitlement, and
the project contains no location usage-description setting.

## Proposed data and failure semantics

These are recommended inputs to the product specification, not accepted
decisions:

1. A snapshot contains the resolved location, provider timestamp, fetch time,
   current conditions, a bounded hourly series, a bounded daily series, units,
   and attribution.
2. `fresh`: display the snapshot normally.
3. `refreshing`: retain the last snapshot and indicate refresh without replacing
   content with a spinner.
4. `stale`: after a transient network/provider failure, retain only a
   policy-compliant in-memory snapshot and show its age explicitly.
5. `unavailable`: use this when there is no usable snapshot, the provider/account
   is misconfigured, the selected location cannot resolve, or current-location
   permission is denied. Never synthesize zero-valued weather.
6. WeatherKit's regional minute/alert availability does not make current/hourly/
   daily weather unavailable. The MVP should not depend on minute forecasts or
   alerts.
7. For the first WeatherKit slice, use memory-only caching. It supports
   deduplication and short transient outages while staying conservatively within
   the agreement's temporary-cache language. Offline-after-relaunch behavior is
   therefore explicitly unavailable unless later legal/product review approves a
   bounded disk cache.

The accepted 6-hour stale interval remains an injected policy value rather than
a hidden networking default.

## Minimal independent implementation slices

These slices deliberately stop before dashboard/tab/layout integration. The
widget author owns shared placement, sizing, tab, and configuration UI.

### Slice 1 — weather domain and refresh policy

Test-drive pure Swift models and one narrow provider seam:

- `WeatherLocation`: stable manual location or resolved current coordinate;
- `WeatherSnapshot`: provider-neutral current/hourly/daily values and
  attribution metadata;
- `WeatherSnapshotState`: unavailable, loading, fresh, refreshing, stale;
- a small `WeatherProviding` interface for one selected provider, not a general
  plug-in framework;
- a repository/actor that deduplicates simultaneous requests by resolved
  location, shares data across widget instances, enforces the chosen refresh
  interval, and applies the chosen stale cutoff.

Tests should cover concurrent deduplication, distinct-location independence,
refresh suppression, stale transition, explicit provider failure, and no
success-shaped empty forecast.

### Slice 2 — selected provider adapter

For the recommended route:

- add the WeatherKit capability/entitlement only after owner approval;
- adapt `WeatherService` current/hourly/daily results into the domain snapshot;
- retrieve and carry WeatherKit attribution;
- classify provider/availability errors without swallowing them;
- add adapter tests at the mapping boundary where constructible fixtures permit,
  keeping service calls behind a fake in unit tests.

No external package is needed.

### Slice 3 — location resolution

- manual place search/resolution with no location authorization;
- an opt-in, one-shot Core Location source for current-location widgets;
- permission state as explicit model data;
- shared current-location resolution for multiple current-location widgets;
- no repeated prompt and no failure impact on manual widgets.

Tests should cover manual operation with denied location permission, permission
denial/restriction, location failure, independently configured widget locations,
and coordinate sharing only where configurations resolve to the same location.

### Slice 4 — feature-owned presentation model

Expose a small observable presentation model that accepts a widget's weather
configuration and emits display-ready weather state. It may own weather-specific
settings and formatting, but it must not add or modify shared dashboard tabs,
layout, snapping, widget identity, or persistence owned by #33.

Native runtime evidence for entitlement provisioning, an actual WeatherKit
response, location prompting, denial recovery, sleep/wake refresh, and
attribution display requires a separately authorized real-machine phase. Unit
tests cannot prove those integrations.

## Exact unresolved choices

1. **Current-location persistence:** whether exact coordinates are retained
   between launches.

## Provider decision

**Resolved 2026-09-12:** use native WeatherKit for the MVP. The owner confirmed
an Apple Developer account is available and accepted the recommendation,
including App ID setup, required Apple Weather attribution and legal notice,
the shared 500,000-call monthly allowance, and temporary-only weather caching.

## Forecast decision

**Resolved 2026-09-12:** the owner accepted the proposed current, 24-hour, and
7-day contract with “yes, whatever is easily available.”

The bounded interpretation is:

- guarantee current condition, temperature, feels-like temperature, today's
  high/low, and precipitation chance;
- guarantee the next 24 hourly entries with condition, temperature, and
  precipitation chance;
- retain up to 7 daily entries total, preserving provider order, with condition,
  high/low, and precipitation chance when available; do not assume today is
  always present;
- retain other directly available WeatherKit values only when they serve the
  agreed presentation without another endpoint, entitlement, permission, or
  speculative provider abstraction;
- do not expand the MVP to minute forecasts, alerts, air quality, historical
  data, or a promise to display every WeatherKit property.

## Units decision

**Resolved 2026-09-12:** each widget supports Automatic, Metric, or Imperial
units. Automatic is the default and follows the system locale. The weather
domain retains typed `Measurement` values; conversion and formatting happen at
the presentation boundary.

## Refresh decision

**Resolved 2026-09-12:** use a visibility-driven 30-minute refresh policy:

- refresh when a weather surface becomes visible and its shared snapshot is at
  least 30 minutes old;
- refresh every 30 minutes while at least one surface using that location
  remains visible;
- refresh after wake or network recovery only when visible and stale;
- perform no weather polling while all weather surfaces are hidden;
- deduplicate identical resolved locations and all concurrent in-flight work;
- permit manual refresh subject to the same deduplication and rate protection.

## Stale-data decision

**Resolved 2026-09-12:** after a refresh failure, retain an in-memory snapshot
for up to 6 hours and label it with its age. After 6 hours, show unavailable
with retry. Weather data does not persist across app relaunch.

Current-coordinate persistence remains the final product question in this
bounded weather flow. It should not reopen the confirmed provider,
manual/current-per-widget, forecast, units, refresh, or stale decisions.

## Next bounded action

Resolve whether exact current-location coordinates persist between launches.
Then reconcile and independently review the completed pure weather core before
authorizing a separate WeatherKit adapter/location slice. That later slice owns
provider mapping and permission behavior; it must not touch shared
dashboard/tab/layout code.

## Primary sources

### Product and repository

- [Issue #36](https://github.com/jdylanmc/notch/issues/36)
- [Agreed MVP product direction](https://github.com/jdylanmc/notch/issues/68#issuecomment-5649878256)
- [Decision map #70](https://github.com/jdylanmc/notch/issues/70)
- [Accepted local developer-ready checkpoint](https://github.com/jdylanmc/notch/issues/54#issuecomment-5649837337)

### Apple

- [WeatherKit requirements and pricing](https://developer.apple.com/weatherkit/)
- [WeatherKit framework](https://developer.apple.com/documentation/weatherkit)
- [Weather model: current, hourly, daily, minute, alerts, and availability](https://developer.apple.com/documentation/weatherkit/weather)
- [Weather availability](https://developer.apple.com/documentation/weatherkit/weatheravailability)
- [Weather attribution](https://developer.apple.com/documentation/weatherkit/weatherattribution)
- [WeatherKit data-source attribution](https://developer.apple.com/weatherkit/data-source-attribution/)
- [Apple Developer Program License Agreement, Attachment 8](https://developer.apple.com/support/terms/apple-developer-program-license-agreement/#A8)
- [Core Location authorization guidance](https://developer.apple.com/documentation/corelocation/requesting-authorization-to-use-location-services)

### Open-Meteo

- [Forecast API documentation](https://open-meteo.com/en/docs)
- [Geocoding API documentation](https://open-meteo.com/en/docs/geocoding-api)
- [Pricing and rate-limit comparison](https://open-meteo.com/en/pricing)
- [Terms and privacy](https://open-meteo.com/en/terms)
- [CC BY 4.0 attribution requirements](https://open-meteo.com/en/licence)
