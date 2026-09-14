# Paired Bluetooth control and battery feasibility

**Issue:** [#74](https://github.com/jdylanmc/notch/issues/74)

**Research date:** 2026-09-13

**Repository baseline:** `585b9415a5146bc206427f1c74cc9d53c39b8eb9`

**Decision context:** [MVP product direction](https://github.com/jdylanmc/notch/issues/68#issuecomment-5649878256), [developer-ready foundation](https://github.com/jdylanmc/notch/issues/54#issuecomment-5649837337)

## Verdict

No single public macOS API establishes the requested generic paired-device
inventory, meaningful profile status, connect/disconnect behavior and battery
coverage.

A public-API implementation is feasible only as a **capability-composed,
category-limited feature**:

- `IOBluetoothDevice` can enumerate system-paired classic devices and exposes
  baseband `isConnected`, `openConnection` and `closeConnection`;
- Core Bluetooth can manage app-local Generic Attribute Profile (GATT)
  peripheral connections, retrieve known peripherals by persistent identifier,
  and retrieve system-connected peripherals only when matching supplied service
  UUIDs, but neither retrieval establishes that a peripheral is already paired;
- battery is available only when an eligible device exposes an accessible
  documented public profile, such as the Bluetooth Battery Service, or the
  coarse Hands-Free Profile battery indicator; and
- generic AirPods/headset, keyboard, mouse and multi-component battery reporting
  is **not established by these public APIs**.

Private frameworks, I/O Registry scraping and vendor-specific reverse
engineering would be separate product/security/distribution decisions. They
are not recommended for the MVP and were not executed here.

## Evidence scope and confidence

| Evidence | Provenance | Source confidence | Runtime confidence |
| --- | --- | --- | --- |
| Core Bluetooth symbols and availability | Public macOS 26.5 SDK headers, inspected 2026-09-13; headers modified 2026-04-18 | High for declared API | None; no manager was created and no device was accessed |
| `IOBluetooth` symbols and availability | Public macOS 26.5 SDK headers, inspected 2026-09-13; headers modified 2026-04-18 | High for declared API | None |
| Bluetooth Battery Service | Bluetooth SIG adopted-service page, accessed 2026-09-13; page states Battery Service 1.1 errata requirements | High for devices that implement the service | None for any user device or category |
| Sandbox/privacy requirements | Apple entitlement and Info.plist documentation, accessed 2026-09-13 | High | None for Notch Pocket |
| Existing repository behavior | Static source at the stated baseline | High | None |
| AirPods and generic accessory battery | No generic public symbol found in the inspected Core Bluetooth or `IOBluetoothDevice` surfaces | Moderate-to-high negative evidence for these surfaces | Unknown; no device was enumerated |

The project deploys to macOS 14
(`notchPocket.xcodeproj/project.pbxproj:1499,1567`). The inspected current SDK
is macOS 26.5 on a macOS 26.6.2 host. Core API used by the candidate exists
well before macOS 14, but current-header presence does not prove unchanged
device/profile behavior on macOS 14. Runtime qualification must cover macOS 14
and the current supported host.

## Framework boundaries

### Core Bluetooth

Core Bluetooth is a GATT/peripheral API, not a generic macOS paired-device
control panel.

Exact public symbols:

- `CBPeer.identifier`: "unique, persistent identifier associated with the
  peer";
- `CBCentralManager.retrievePeripherals(withIdentifiers:)`: retrieves
  peripherals for identifiers already known to the app/system;
- `CBCentralManager.retrieveConnectedPeripherals(withServices:)`: returns
  system-connected peripherals implementing any supplied service UUID, and
  Apple states they still need an app-local `connect` before use;
- `CBCentralManager.connect(_:options:)`: starts an app connection and has no
  built-in timeout;
- `CBCentralManager.cancelPeripheralConnection(_:)`: cancels the app's active
  or pending connection and is non-blocking;
- `CBPeripheral.state`: disconnected, connecting, connected or disconnecting;
- `discoverServices`, `discoverCharacteristics`,
  `readValue(for:)` and `setNotifyValue` support GATT battery retrieval when
  the peripheral exposes the required service/characteristic; and
- `CBManager.state` and `CBManager.authorization` distinguish unknown,
  resetting, unsupported, unauthorized, powered-off and powered-on states,
  plus not-determined/restricted/denied/allowed authorization.

Primary Apple references:
[retrieve known peripherals](https://developer.apple.com/documentation/corebluetooth/cbcentralmanager/retrieveperipherals(withidentifiers:)),
[retrieve system-connected peripherals](https://developer.apple.com/documentation/corebluetooth/cbcentralmanager/retrieveconnectedperipherals(withservices:)),
[`connect`](https://developer.apple.com/documentation/corebluetooth/cbcentralmanager/connect(_:options:)),
[`cancelPeripheralConnection`](https://developer.apple.com/documentation/corebluetooth/cbcentralmanager/cancelperipheralconnection(_:)),
[`CBPeripheral`](https://developer.apple.com/documentation/corebluetooth/cbperipheral),
and [`CBManager.authorization`](https://developer.apple.com/documentation/corebluetooth/cbmanager/authorization-swift.property).

Static citations:

- `CoreBluetooth.framework/Headers/CBPeer.h:14-25`
- `CoreBluetooth.framework/Headers/CBCentralManager.h:130-225`
- `CoreBluetooth.framework/Headers/CBPeripheral.h:23-33,81-85,122-214`
- `CoreBluetooth.framework/Headers/CBManager.h:18-86`

Core Bluetooth cannot enumerate every paired classic device. Its "connected"
state is an app/GATT connection state, not proof that a macOS audio, keyboard,
mouse or other classic profile is active. Cancelling the app connection is not
documented as disconnecting the device from macOS or other clients.

Neither `retrievePeripherals(withIdentifiers:)` nor
`retrieveConnectedPeripherals(withServices:)` declares paired status.
A peripheral known by identifier can be unpaired, and another app can establish
the system connection returned by the service-filtered retrieval. Apple also
documents, in an iOS peripheral example, that reading or subscribing to an
encryption-required characteristic can initiate pairing. That example proves a
Core Bluetooth security behavior exists; it is not macOS runtime proof.

For the confirmed already-paired-only MVP, Core Bluetooth connect, service
discovery, characteristic read and subscription must remain deferred unless an
approved public mechanism first establishes paired eligibility without
initiating pairing. Avoiding scans is not such a mechanism. Do not infer
eligibility from identifiers, names, system-connected state or Core Audio.
No qualifying public Core Bluetooth paired-eligibility mechanism was
established by this research.

Primary Apple references:
[retrieving known peripherals](https://developer.apple.com/documentation/corebluetooth/cbcentralmanager/retrieveperipherals(withidentifiers:)),
[retrieving system-connected peripherals](https://developer.apple.com/documentation/corebluetooth/cbcentralmanager/retrieveconnectedperipherals(withservices:)),
and [encryption-required access can initiate pairing (iOS example)](https://developer.apple.com/library/archive/documentation/NetworkingInternetWeb/Conceptual/CoreBluetooth_concepts/BestPracticesForSettingUpYourIOSDeviceAsAPeripheral/BestPracticesForSettingUpYourIOSDeviceAsAPeripheral.html).

### IOBluetooth

The public Objective-C `IOBluetooth` framework exposes classic Bluetooth
baseband operations:

- `IOBluetoothDevice.pairedDevices()` returns all paired devices on the system;
  the header warns that the list is not per-user;
- `isPaired` and `isConnected` expose pair and baseband-link state;
- `openConnection` opens a baseband connection; synchronous and callback forms
  exist;
- `closeConnection` synchronously closes the baseband connection; and
- `nameOrAddress` and `addressString` identify devices, although presenting or
  persisting hardware addresses needs privacy review.

Static citation:
`IOBluetooth.framework/Headers/objc/IOBluetoothDevice.h:559-632,871-891`.

These are public symbols and are present in the current SDK, but their state is
baseband-level. The header does not promise that `openConnection` activates a
desired audio/input profile or that `closeConnection` has the same UX and
multi-client behavior as System Settings. The paired list's system-wide,
not-per-user scope is a privacy and UX constraint.

Primary Apple reference:
[`IOBluetoothDevice`](https://developer.apple.com/documentation/iobluetooth/iobluetoothdevice).

### Existing Core Audio integration

Notch Pocket already enumerates audio output devices, labels Bluetooth
transports and changes the default output:

- `notchPocket/managers/AudioRouteManager.swift:21-48`
- `notchPocket/managers/AudioRouteManager.swift:76-103`
- `notchPocket/managers/AudioRouteManager.swift:122-159`
- `notchPocket/helpers/AudioOutputRouteResolver.swift:90-156`

This is useful corroborating state for audio output selection. It is not paired
Bluetooth inventory, pairing status, battery information or a Bluetooth
connect/disconnect API. An audio device disappearing from Core Audio also
cannot by itself distinguish powered off, out of range, disconnected, denied
permission or unsupported profile.

## Capability matrix

| Device/category | Inventory | Status | Connect/disconnect | Battery | MVP assessment |
| --- | --- | --- | --- | --- | --- |
| Classic paired device (`IOBluetooth`) | `pairedDevices()` | Paired and baseband `isConnected` | Public `openConnection` / `closeConnection` | No generic percentage on `IOBluetoothDevice` | Candidate only after category/profile runtime proof; never describe baseband state as guaranteed functional profile state |
| GATT peripheral previously known by ID | `retrievePeripherals(withIdentifiers:)`; paired eligibility unknown | Existing app-local `CBPeripheral.state` only | Deferred: connecting can reach an unpaired peripheral | Accessible Battery Service only after an approved paired-eligibility gate | Not eligible for the paired-only MVP from identifier retrieval alone |
| GATT peripheral connected elsewhere | `retrieveConnectedPeripherals(withServices:)`; paired eligibility unknown | System-connected match, possibly established by another app | Deferred: app-local connect does not prove prior pairing | Service-specific only after an approved paired-eligibility gate | Not eligible for the paired-only MVP from system-connected retrieval alone |
| BLE device not known and not currently connected | Requires scanning | Discovery state only | Deferred for paired-only scope | Service-specific only after an approved paired-eligibility gate | Outside confirmed MVP inventory approach; discovery does not establish pairing |
| Bluetooth audio output | Existing Core Audio output inventory | Current/default output, not full Bluetooth state | Can select default output; not Bluetooth connect/disconnect | No public Core Audio battery property established | Keep separate from Bluetooth operations; may enrich display after runtime correlation |
| Hands-Free Profile device | `IOBluetooth`/profile-specific setup | Hands-Free Profile service-level connection | `IOBluetoothHandsFree.connect` / `disconnect` | `IOBluetoothHandsFreeIndicatorBattChg` and delegate `handsFree(_:batteryCharge:)`, coarse 0-5 | Public but profile-specific; does not establish generic headset or AirPods percentage |
| Keyboard/mouse/input device | Classic paired list may include it | Baseband state only | Public baseband calls exist | No generic public battery surface established here | High disruption risk; exclude from first control slice |
| AirPods and multi-component earbuds/case | May appear in classic/audio surfaces | Surface-specific and incomplete | No public AirPods-specific control API identified | No public generic buds/case battery API identified | Report unavailable. Do not infer support from private examples or one model |

## Battery boundaries

### Documented public coverage

The Bluetooth SIG Battery Service exposes battery information for a battery
within a device. A Core Bluetooth client can discover the service and
characteristic, read the value and subscribe when the characteristic supports
notifications. The commonly assigned UUIDs are Battery Service `0x180F` and
Battery Level `0x2A19`. Support depends on discovering an accessible service
and characteristic after connection; it does not require the peripheral to
advertise that service UUID. Apple states that connected service discovery can
find more services than fit in the peripheral's advertising packets.

Primary sources:
[Bluetooth SIG Battery Service](https://www.bluetooth.com/specifications/specs/battery-service/)
and [Apple's connected service-discovery guidance](https://developer.apple.com/library/archive/documentation/NetworkingInternetWeb/Conceptual/CoreBluetooth_concepts/PerformingCommonCentralRoleTasks/PerformingCommonCentralRoleTasks.html#//apple_ref/doc/uid/TP40013257-CH3-SW5).

For this paired-only MVP, technical service accessibility is not sufficient.
The app must establish approved public paired eligibility before connecting,
discovering services, reading or subscribing. Without that gate, the GATT
battery path remains deferred even if the peripheral is known or currently
connected to the system.

`IOBluetoothHandsFree` also declares a Hands-Free Profile battery indicator,
`IOBluetoothHandsFreeIndicatorBattChg`, and
`handsFree(_:batteryCharge:)`, with a value of 0-5. That is a coarse
profile-specific indicator, not a generic 0-100 accessory battery contract.

Static citations:

- `IOBluetooth.framework/Headers/objc/IOBluetoothHandsFree.h:65-77`
- `IOBluetooth.framework/Headers/objc/IOBluetoothHandsFreeDevice.h:257-265`

### Unsupported or unknown coverage

- `IOBluetoothDevice` has no generic accessory battery percentage property.
- A Human Interface Device service record contains battery-related metadata,
  but the inspected API does not establish a current percentage retrieval
  contract.
- Core Bluetooth Battery Service support cannot be assumed for classic audio
  devices, AirPods, keyboards, mice or any category as a whole.
- One battery value cannot be expanded into left bud, right bud and case
  values. Multi-component state must remain unavailable unless a public,
  documented source reports each component.
- Missing battery can mean unsupported service, not connected to the required
  profile, authorization denied, powered off, out of range, stale data or a
  read error. The UI must not convert any of those to `0%`.

The app's current battery model is the Mac's own power-source model through
`IOPSCopyPowerSourcesInfo`, not accessory battery support:

- `notchPocket/models/BatteryStatusViewModel.swift:4-15,60-66`
- `notchPocket/managers/BatteryActivityManager.swift:204-292`

## Sandbox, privacy and availability

For a sandboxed app, Apple documents the Boolean
`com.apple.security.device.bluetooth` entitlement. Apple also documents
`NSBluetoothAlwaysUsageDescription` as the purpose string for Bluetooth access.
Core Bluetooth exposes authorization through `CBManager.authorization`.

Primary sources:

- [Bluetooth sandbox entitlement](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.device.bluetooth)
- [`NSBluetoothAlwaysUsageDescription`](https://developer.apple.com/documentation/bundleresources/information-property-list/nsbluetoothalwaysusagedescription)
- [Core Bluetooth](https://developer.apple.com/documentation/corebluetooth)

Notch Pocket's current entitlements do not contain
`com.apple.security.device.bluetooth`, and its generated Info.plist settings do
not contain `NSBluetoothAlwaysUsageDescription`
(`notchPocket/notchPocket.entitlements:5-32`;
`notchPocket.xcodeproj/project.pbxproj:1461-1501,1530-1569`).

Adding those declarations and provoking a privacy decision require separate
approval. Static evidence does not prove whether every `IOBluetooth` read or
baseband operation is governed identically to Core Bluetooth on macOS 14 and
26; that must be included in the runtime matrix rather than hidden behind a
fallback.

## Recommended architecture

Do not combine framework objects into one success-shaped "Bluetooth device."
Use one domain record with explicit source capabilities:

- stable internal ID plus source-specific identifiers;
- display name with unknown state;
- category and transport as evidence-backed/unknown;
- pairing state, baseband state, app GATT state and audio-route state as
  separate fields;
- supported operations as a set, not inferred from category;
- battery as `percentage`, `coarseLevel`, `multipleComponents`,
  `unsupported`, `unavailable`, `stale` or `error`; and
- last observation time and source.

Deduplication across `IOBluetooth`, Core Bluetooth and Core Audio is not
documented. Names are not identity. Hardware addresses should not be exposed
to the UI or telemetry. Cross-framework joins must be conservative and may
leave separate records until runtime evidence proves a stable public join.

## Recommended bounded implementation/TDD slice

No source, entitlement or dependency changes are authorized by this research.
For a future approved slice:

1. Define `BluetoothDeviceSnapshot`, `BluetoothCapability`,
   `BluetoothConnectionState`, `BluetoothBatteryState` and source-specific
   gateway protocols.
2. Add a pure capability resolver and reducer with fixtures for classic,
   known-and-paired GATT, known-but-unpaired GATT, system-connected with unknown
   pairing, Hands-Free Profile, audio-only, unsupported, denied, powered-off,
   stale and error cases.
3. Test that unavailable battery never becomes zero, app-local disconnect
   never becomes system-disconnected, and baseband connected never becomes
   profile-ready without corroboration. Test that known identifiers and
   system-connected retrieval never grant paired eligibility.
4. Add an `IOBluetooth` adapter for paired inventory and baseband state only.
   Keep connect/disconnect behind category and human-confirmation policy.
5. Defer a production Core Bluetooth Battery Service adapter until an approved
   public mechanism establishes already-paired eligibility before any connect,
   service discovery, read or subscription. Known identifiers,
   service-filtered system-connected retrieval and absence of scanning are not
   sufficient guards.
6. Correlate existing Core Audio output state only as optional evidence, never
   as identity or Bluetooth success.

The first shippable claim should be narrower than the desired product:
"shows public paired classic inventory and exact available states; controls
only explicitly qualified categories; reports battery only from documented
profiles with established paired eligibility." Broader category support
requires product acceptance and device qualification; this wording must not be
treated as already approved.

## Separately human-approved runtime checks

Use only human-selected, nonessential devices:

1. validate denied, restricted, powered-off and authorized states without
   programmatically changing privacy or controller power;
2. compare `pairedDevices`, baseband state and System Settings for one
   nonessential classic device;
3. test asynchronous and synchronous connection outcomes, timeout policy,
   already-connected behavior and error mapping;
4. prove whether baseband connect/disconnect changes the intended profile for
   each supported category;
5. only after the paired-eligibility mechanism and scope are approved, use one
   nonessential already-paired GATT peripheral with an accessible Battery
   Service to verify connected service discovery, read, notification, stale
   and disconnect behavior; separately include a known-but-unpaired
   counterexample and prove that Notch Pocket performs no connect, read,
   subscription or pairing attempt;
6. for a Hands-Free Profile test device, verify whether the 0-5 battery
   indicator is present and how it maps without inventing precision;
7. verify Core Audio correlation for an audio device without claiming it as
   Bluetooth identity; and
8. repeat the supported matrix on macOS 14 and the current host.

Do not use a keyboard, mouse or current headphones for initial control tests.
Do not pair, scan, toggle Bluetooth globally or read private I/O Registry data.
Every operation and privacy prompt needs separate human approval.

## Product questions and approvals still required

1. Choose the first supported device categories. **Recommendation:** begin
   with public classic inventory/status, but enable controls only for a
   qualified non-input category after runtime proof; exclude keyboards and
   mice from the first control release.
2. Decide whether profile-specific/coarse battery is useful. Recommendation:
   show source-qualified coarse Hands-Free Profile state and Battery Service
   percentages only; otherwise show unavailable.
3. Decide whether generic AirPods/buds/case battery is mandatory for MVP.
   Recommendation: do not accept private APIs; treat that coverage as
   unsupported unless Apple exposes a public documented source.
4. Resolve the GATT paired-eligibility gate. Recommendation: if no public
   mechanism can prove already-paired status before Core Bluetooth access,
   defer GATT battery from the paired-only MVP rather than broadening scope or
   risking a pairing prompt. Any broader eligibility rule requires an explicit
   user scope decision.
5. Approve future Bluetooth entitlement/purpose-string changes and the
   nonessential-device runtime matrix. This research grants neither.
6. Accept that "connect/disconnect" may need category-specific semantics rather
   than one universal control. Recommendation: require a verified operation
   capability per device record and hide the control otherwise.

## Conclusion

#74 has a public-API candidate only for an explicit support matrix. Classic
paired inventory and baseband operations are documented. GATT battery is
technically available when an accessible service exists, but it remains
deferred from the paired-only MVP until an approved public paired-eligibility
gate exists; Hands-Free Profile battery remains profile-specific. Universal
paired-device control and generic AirPods/accessory battery are not supported
by the evidence. The issue and parent feature are not delivered.
