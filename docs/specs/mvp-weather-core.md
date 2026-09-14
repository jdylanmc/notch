# MVP weather core

**Issue:** [#36](https://github.com/jdylanmc/notch/issues/36)

**Status:** bounded implementation contract. Provider calls, location access,
dashboard integration, capabilities, entitlements, persistence, and live
runtime validation are excluded.

## Confirmed decisions

- Provider: native WeatherKit; an Apple Developer account is available.
- Locations: every widget independently selects a manual location or opt-in
  current location.
- Forecast: current conditions, up to 24 hourly records, and up to 7 daily
  records. Carry readily available WeatherKit values only when they support this
  contract; do not expand into minute forecasts, alerts, air quality, or
  historical weather.
- Units: every widget selects Automatic, Metric, or Imperial. Automatic follows
  the system locale.
- Refresh: a visible weather surface refreshes data at least 30 minutes old,
  continues at 30-minute intervals while visible, refreshes after wake/network
  recovery when visible and stale, performs no polling while hidden, and
  deduplicates identical locations and concurrent work. Manual refresh uses the
  same deduplication/rate protection.

After a refresh failure, an in-memory snapshot remains stale-but-displayable for
up to 6 hours with its age visible. After 6 hours it becomes unavailable with
retry. Weather snapshots do not persist across relaunch. Persistence of exact
current coordinates remains unresolved.

## Core interface

The core is an immutable value module. Callers pass identity, weather values,
unit preference, timestamps, and policy thresholds explicitly.

### Identity

- `WeatherWidgetID` distinguishes repeated widget instances even when they use
  the same location.
- `WeatherLocation` contains an explicit stable location ID, display name,
  latitude, longitude, and timezone identifier.
- The core does not discover, geocode, or persist a location.

### Weather values

- Temperatures remain `Measurement<UnitTemperature>` values internally.
- Current, hourly, and daily records represent unavailable provider values with
  optionals rather than invented defaults.
- A snapshot is usable when at least one supported current, hourly, or daily
  weather value is present. Provider/fetch timestamps and date-only forecast
  records do not make an otherwise empty snapshot usable. Any supported partial
  forecast remains usable.
- Condition text and symbol names are provider-adapter inputs; the core does
  not invent a parallel WeatherKit condition enum.
- A snapshot stores its provider timestamp and fetch timestamp.
- Snapshot construction truncates hourly records to 24 and daily records to 7
  while preserving input order.

### Presentation

- `WeatherUnitSelection` is Automatic, Metric, or Imperial.
- A pure unit resolver converts temperatures only for presentation:
  Automatic uses the supplied locale, Metric uses Celsius, and Imperial uses
  Fahrenheit.
- Conversion never mutates the lossless source `Measurement` values.
- `WeatherWidgetPresentation` carries widget identity, explicit location,
  per-widget unit selection, and optional snapshot. Two widgets remain distinct
  even when every other value matches.

### Refresh helper

- A pure helper answers whether a snapshot is due for refresh.
- The caller supplies `now` and `refreshInterval`; the helper has no hidden
  clock and no default cadence.
- Injected intervals must be finite and greater than zero.
- Missing snapshots are due immediately.
- Snapshots without usable weather data are due immediately and cannot become
  available or stale.
- Future fetch timestamps are not due.
- A consumed `now`, fetch timestamp, or computed age must be finite. Invalid
  temporal input produces an explicit typed invalid-time result.
- A second pure helper classifies a failed refresh as stale or unavailable.
  The caller supplies `now` and the 6-hour stale interval; the implementation
  does not embed that duration as a default.
- Timer creation, visibility observation, wake/network observation, request
  execution, and caching are outside this module.

## Test seams

Tests use only the public core interface and cover:

1. snapshot horizon truncation and order preservation;
2. explicit missing provider values;
3. lossless source measurements and deterministic unit conversion;
4. Automatic/Metric/Imperial per-widget behavior;
5. repeated widgets retaining independent identity;
6. explicit-location identity;
7. refresh decisions with an injected clock value and interval;
8. stale/unavailable transitions with an injected stale interval.

## Exclusions

- No WeatherKit import, request, adapter, account, capability, or entitlement.
- No Core Location import, permission request, or coordinate discovery.
- No background timer, cache, disk persistence, or provider fake in production.
- No SwiftUI dashboard/widget registry, layout, settings, or tab changes.
- No new dependency.

## Acceptance

- Targeted XCTest begins red because the specified public interface is absent.
- The minimal implementation makes the targeted tests green.
- The app builds and changed Swift files pass repository lint.
- Native WeatherKit, permissions, refresh lifecycle, and user interface remain
  explicitly unverified and unimplemented.
