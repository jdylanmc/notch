# Test-only OS Now Playing producer

Bounded source fixture for issue #53 / PR #86, authored against
`35656780a87613fa95e8b873c687a6275b222d73`. This is **not a product target,
dependency, import, backend or registered regression scenario**. It uses only
public AppKit, AVFoundation and MediaPlayer APIs. No notifications, models,
preferences or AppDelegate hooks are injected into Notch.

The independent worker must prove OS delivery to the exact approved Notch
candidate. Producer-local counters, metadata assignments and static checks
are **not native proof**, Spotify account proof or whole-suite signoff.
The existing thirteen-case registry is unchanged. Its no-target cases require
a separate clean guest with no fixture history; do not mix them with this
history-producing fixture or erase history to make them pass.

## Source and local checks

Run from the repository root, with native macOS, Python 3 and a compatible
installed Swift/macOS SDK (Xcode 26+, Swift 6, minimum deployment macOS 14).
The receipt records the exact compiler/SDK used. No third-party packages. An explicit `DEVELOPER_DIR`
may select the parent's approved Xcode; nothing sources `local.env`.

```bash
python3 -B experiments/tart-regression/MediaFixture/build.py check \
  --output "$PWD/.build/mediafixture-check-001"
python3 -B -m unittest discover \
  -s experiments/tart-regression/MediaFixture/Tests -p 'test_build.py'
```

This compiles the full native source to **object files only** for arm64 and
x86_64 (no app bundle or native app executable), then compiles/runs only
Foundation/Darwin state, WAV and owned-storage contracts. It never instantiates
AppKit, MediaPlayer or an audio player. The test executable may receive the
toolchain's implicit linker ad-hoc seal needed for execution; no certificate
selection, `codesign`, Keychain lookup or identity signing occurs. Six contract
groups include failed play/pause/stop, no synthetic elapsed advancement,
activation/reopen without playback, explicit remote commands, end/cleanup state,
malformed/redirected storage, exclusive producer ownership and wrong-outcome
controls. Those are synthetic assertions, not guest interactions.
Seven Python recipe controls mock the compiler; they check exact fixture-only
inputs, no app execution/signing and refusal of redirected/unsafe/reused outputs.

Every invocation requires a **new immediate child** of this worktree's `.build`.
No existing output is reused or overwritten. Outputs/failures are retained;
`build.json` identifies source hashes, compiler, SDK and the actual check mode.
The script performs no network, product build, signing, installation or app
execution. Local tests write only their own output folder.

## Parent-owned build and signing (not author-executed)

```bash
python3 -B experiments/tart-regression/MediaFixture/build.py build \
  --output "$PWD/.build/mediafixture-build-001"
```

Result: native-host-architecture **unsigned** `NotchMediaFixture.app`, empty
private sibling `MediaFixtureData/`, and `build.json`. The executable disables
linker ad-hoc signing. No Xcode project changes or product dependency resolution.
Use arm64 for an Apple Silicon Tart guest; x86_64 is object-compiled, not runtime
validated. Build output is not a runnable approved artifact until the parent
applies its separately approved signing process.

Generic parent-only signing example, using the **same already approved public
selector** as the candidate, not a hardcoded certificate or newly discovered
identity:

```bash
: "${APPROVED_SIGNING_SELECTOR:?Parent supplies the existing approved name or public SHA-1 selector}"
FIXTURE_APP="$PWD/.build/mediafixture-build-001/NotchMediaFixture.app"
codesign --sign "$APPROVED_SIGNING_SELECTOR" --options runtime --timestamp=none "$FIXTURE_APP"
codesign --verify --strict --verbose=2 "$FIXTURE_APP"
codesign --display --verbose=4 "$FIXTURE_APP"
```

This is a **local-only** signing recipe, no secure timestamp or notarization
claim. Do not enumerate/export/import keys or certificates, inspect Keychain,
source local settings, add entitlements, use `--deep`, re-sign Notch, or fall
back to another selector. The parent checks the exact bundle ID, expected team
and signer against its approved artifact, records pre/post-sign executable
hashes and signature verification, and retains the source manifest. Approval
and signer availability are external prerequisites; the author exercises none.
Do not bypass Gatekeeper, strip quarantine or automate consent.

Transfer the exact parent-approved fixture bundle with its empty
`MediaFixtureData` sibling into a **new guest-owned private folder**, for example
`$HOME/NotchMediaFixture-run-001/`, using the parent's established transfer
process. Keep directory modes private (`0700` for data). Never install it on the
host, replace a real player, use a Spotify bundle ID, or store it directly in a
shared Applications folder. Normal guest launch registers this distinct app
with LaunchServices; the worker must verify exact path/PID/bundle/signature
resolution before trusting Notch's `NSWorkspace` activation.

## Native behavior and public observations

- Identity: `com.jdylanmc.notchpocket.regression.mediafixture`. Starts **idle**,
  zero per-process commands/play attempts, no metadata and stopped publication.
  Neither launch, activation nor reopen calls playback. Quit/last-window close
  normally stops the engine, clears `nowPlayingInfo`, sets `playbackState` to
  stopped and writes `shutdown_cleared`. Forced kill/crash cannot guarantee that.
- Play invokes an actual `AVAudioPlayer` over a generated local mono 16-bit PCM
  WAV: 30 seconds, 22,050 Hz, 440 Hz, bounded amplitude with short edge fades.
  No looping, network, microphone, account, private clip, artwork or media
  library. Output volume is fixed at zero. Muted real playback is not proof of
  audible output. Only a successful `play()` plus `isPlaying` publishes playing.
- Elapsed observations come exclusively from `AVAudioPlayer.currentTime`.
  One-second samples do not increment or extrapolate a clock. Play failures,
  decoder errors, inconsistent observations or receipt failures are explicit;
  playback is stopped and publication cleared on failure. Notch/OS may
  independently extrapolate their own clock; that is not producer evidence.
- Pause pauses the engine and retains fixed metadata with rate zero and
  `.paused`. Stop resets the engine to zero and clears metadata with `.stopped`.
  Natural completion also clears metadata. Play resumes pause or starts after
  stop; remote play/pause/stop/toggle commands operate the same real engine and
  are counted separately, including attempts that fail.
  `play-starts` counts successful `play()` calls, including a repeated Play
  while already playing; it is not an acoustic output or hardware-start count.
- Launch count persists only in the fixture folder. Activation/reopen counters
  and command counters are per-process. A new process starts idle even when the
  prior process was playing. Activation counters report AppKit callbacks, **not
  the caller** or the number of `NSWorkspace` requests. Already-active apps need
  not emit another activation. The worker must first foreground another app.
  Remote counters cover commands **delivered to this producer**, not commands
  the OS drops or routes elsewhere; retain the actual candidate interaction and
  adapter observations rather than claiming global command tracing.
- UI fields are read-only native static texts with stable
  `mediafixture.v1.` identifiers. Buttons: `play`, `pause`, `stop`, `quit`;
  window: `window`; labels: `identity`, `status`, `engine`, `elapsed`,
  `publication`, `launch-count`, `activation-count`, `reopen-count`, `active`,
  `play-attempts`, `play-starts`, `ui-commands`, `remote-commands`, `natural-ends`,
  `error`. `identity` includes PID. Query static-text **values**, not captions.

Only sibling `MediaFixtureData/` is used for runtime application file I/O:
`producer.lock`, atomic `launch-count.json`, and new `launch-NNNNNN/` folders
containing `tone.wav` and `receipts.jsonl`. No preferences or user-media paths.
A nonprivate/redirected/unowned directory, concurrent producer, corrupt counter
or reused launch directory fails closed, never resets history. Receipts are
flushed JSON lines (schema 1), max 8 MiB per launch; overflow stops playback and
displays `receipt_write_failed`. Each contains PID, sequence, fixed event,
launch/activation/command counts, actual engine samples and publication intent.
They deliberately contain no personal media, caller identity, private errors
or secrets. `publicationIsConsumerProof` is always false. Read receipts only;
never edit them to induce state. Failed initial setup has a visible error and
public stderr code, not a fabricated successful launch receipt.

## Independent guest proof still required

The parent owns the signed fixture/candidate and independent worker. No guest,
host UI, player process, signing or VM command is run by this author. Use the
existing headless Tart/Aqua-session/candidate guards, native AppKit controls,
bounded waits and exact-candidate receipts, not model injection or screenshots
without assertions. This source-only slice deliberately adds no harness
selector/registry entry and makes no claim to cover the outstanding journey.

1. On a prepared isolated guest, launch fixture normally. Assert identity and
   fresh idle counters. Activate/reopen it without Play: engine elapsed remains
   zero, no metadata and no commands. Select available **Now Playing** in
   Notch's actual Settings. Its fallback to another backend is BLOCKED, not a
   fixture pass.
2. Click fixture Play. Within five seconds require two advancing real engine
   elapsed samples and `engine=playing`, no error. Require the actual candidate
   to display `Regression Tone` / `Notch Test Fixture`, the full player and its
   transport, from its real adapter stream. Bind candidate and producer
   identities/hashes separately. Metadata-only display without engine progress
   is invalid playback evidence.
3. Click Pause; require stable engine time, retained metadata/rate zero and
   Notch's immediate opened-section launcher without the slider. Snapshot
   counters after another guest app becomes foreground. Click **Notch's**
   launcher, not a fixture activation substitute. Require the fixture frontmost,
   same PID and launch count, increased activation count, and unchanged UI/
   remote command counts, play attempts/starts and paused engine time. Observe
   for at least two engine sampling intervals, not just one immediate frame.
4. Click fixture Play; require resumed real elapsed progression and Notch full
   player. Repeat with Stop, requiring cleared publication and idle launcher.
   Launcher activation must not play. Explicit fixture Play must restore the
   full player. Complete each playing segment within the 30-second duration.
5. For retained-history routing, establish actual playback first, then **Quit**
   the fixture normally. Require `shutdown_cleared`, exited PID and disappearance
   of the current producer in the actual OS/adapter observation. Keep Notch
   running. Its launcher must reopen this exact bundle from retained history:
   new PID, launch count +1, idle, zero per-process commands/play, metadata
   still cleared. Explicit Play must then restore real consumer playback.
   If OS retains a stale current source, retained-*history-only* routing is
   **unproven**, not a pass inferred from the fixture's cleanup receipt.
6. Restore the guest's original UI/source/focus and normally quit fixture.
   Generated remembered history cannot be restored by deleting preferences:
   use an isolated disposable guest baseline owned by the parent. Retain
   failures and both artifact identities in the worker's report.

**Negative controls:** omit Play (must fail advancing-engine/full-player
requirements); deliberately click Play after the paused activation baseline
(must fail unchanged command/start counts, even if subsequently paused); omit
the Notch launcher click (must fail foreground/activation requirements); quit
and relaunch (must fail the running-process same-PID control, while belonging
only in the separately asserted exit/history journey). Wrong/missing title,
slider left visible when paused, stale PID/path or absent cleanup must not pass.
Execute controls via real guest UI, not counter edits, fake adapter input or a
product fixture switch. Unit controls only establish analogous policy behavior.

**Hardware/environment unknown:** public MediaPlayer registration, remote
command delivery, LaunchServices resolution, audio-device availability and
AVAudioPlayer progress in the prepared Tart guest. In particular Tart
`--no-audio` viability is unverified. If it prevents engine progress or OS
publication, report an environment BLOCKED with exact evidence; do not fake a
clock, claim sound from metadata, silently change VM/audio configuration, or
substitute host execution. Spotify live-account behavior and other layouts/
gestures remain separate required evidence, not coverage supplied by this app.
