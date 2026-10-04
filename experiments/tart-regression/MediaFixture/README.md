# PR106 public-API media producer

Test-only source, **not product integration, Spotify support, or native evidence**.
Identity remains `com.jdylanmc.notchpocket.regression.mediafixture`, version 1.0,
build 2. Public AppKit/AVFoundation/MediaPlayer only. No product import, account,
network, notification injection, fake clock, preference writes or application
data I/O. Parent builds/signs/launches it separately; the regression never does.

## Provenance and deliberate reduction

Derived from `experiments/tart-regression/MediaFixture` at
`82b65308bfd53b95d24fd50610d5677b2ffa9024` in the read-only
`notch-complete-idle-launcher` worktree (closed PR86). Specifically:
`Sources/GeneratedAudio.swift` retains the PCM generator; the producer retains
the distinct identity, muted real AVAudioPlayer, public publication,
main-thread command delivery and explicit stop/clear pattern from
`Sources/MediaFixtureApp.swift` / `FixtureState.swift`. Repository GPL-3.0
licensing and existing `LICENSE`/`THIRD_PARTY_LICENSES` apply.

This is **not** a blind port of that unaccepted experiment. It does not bring
back launcher behavior, activation/reopen journeys, history routing, persistent
storage, play/pause remote commands, or its old unregistered scenario claims.
New next/previous commands cycle Alpha / Bravo / Charlie, restarting the same
real 30-second, mono 22,050 Hz generated WAV at volume zero. Track names are
distinct synthetic labels; a new track still requires actual engine progress.
Only successful `play()` plus `isPlaying` publishes playback. Natural completion
clears publication. Explicit Stop and normal shutdown stop/reset the engine and
clear publication; a forced kill is not cleanup evidence.

Native static-text **values**, under `mediafixture.v2.`, expose `identity`
(bundle ID and PID), `title`, `engine`, `elapsed`, `publication`, `remote-next`,
`remote-previous` and `error`. Buttons `play` and `stop` are real native controls.
Launch starts stopped; no activation or reopen starts playback. Counters are
append-only per process and are sampled relative to the actual initial values,
not reset to make a scenario pass. Sampled elapsed comes only from the engine.
Publication values/counters alone never establish consumer behavior.

## Parent-only commands after diff reconciliation

From the clearance checkout, with the existing approved Xcode:

```bash
mkdir -p .build
bash experiments/tart-regression/MediaFixture/build.sh \
  "$PWD/.build/pr106-media-fixture-001"
```

The output must be a new immediate child of `.build`. This produces an
**unsigned arm64 macOS 14+ app**, with no automatic dependency installation or
signing. Parent records source hashes and verifies/signs that exact artifact
using the existing approved selector, never impersonating Spotify or
re-signing the candidate/runner. There are no extra fixture entitlements.
No notarization, distribution, OS consent or host launch is implied.

The existing `test-oracle.sh` also compiles the actual generated-audio source
and checks its exact WAV header, duration/sample format, bounded samples and
edge fades without starting an audio engine. Python reader/fixture-pin controls
live in `scripts/tests/test_regression_interactions.py`. Neither is playback,
publication, remote-command or native consumer proof.

Parent transfers the exact signed bundle to a private guest-owned path under
`/Users/notch/`, pins its executable independently of Notch, and starts it
normally in that guest. Start stopped, with no error; leave its window visible.
Real audio engine advancement with Tart `--no-audio`, public OS Now Playing
publication, remote command delivery and native labels remain **unverified**.
No VM flags or time limits may change to manufacture a pass.

See [the scenario contract](../scenarios/pr106-retained-interactions.md) for
the mandatory synthetic-profile attestation and external restoration gate.
