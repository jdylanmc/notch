# Local macOS regression VM experiment

Issue [#100](https://github.com/jdylanmc/notch/issues/100) explores a non-disruptive
environment for installed-app regressions under
[#75](https://github.com/jdylanmc/notch/issues/75). This is a **prototype**, not the
production regression suite, a CI gate, or comprehensive product coverage.

## What is local, and what travels with Git

`.local/vm-regression/` is ignored in its entirety. Its `AGENTS.md` is the local
operator handoff. Do not expect this directory to exist in a fresh clone.

| Local path | Contents |
| --- | --- |
| `AGENTS.md`, `vm.sh` | Machine-local operating instructions and pinned Tart launcher |
| `work/tart-home/vms/` | Prepared macOS VM and disposable test clones: virtual disk, NVRAM, configuration |
| `work/tart.app/`, `work/home/`, `work/tmp/` | Verified Tart app bundle and isolated runtime directories |
| `work/access-private/` | Dedicated SSH private key and verified guest host key; never copy into Git |
| `work/GuestRegressionProbe/`, `work/GuestProbeBuild/` | Working experimental source and compiled test runner |
| `work/overlay-*.zip`, `work/guest-input/` | Explicit test inputs and optional read-only transfer staging |
| `evidence/` | Candidate-specific receipts, logs and local-only public About screenshots |

The portable sources are in [`experiments/tart-regression/`](../../experiments/tart-regression/).
They contain no VM image, credentials, personal signing selector or
machine-specific candidate identity. The parent can build exact checkout
sources into ignored local work with the opt-in
[stable runner entrypoint](../../experiments/tart-regression/RUNNER.md);
copy prepared source/Products into guest-local scratch space before running.
Older local proof files and receipts can reference historical session paths;
those paths are not reconstruction dependencies.

## Re-create on another machine

1. **Check prerequisites.** Use a supported Apple-silicon Mac, a properly licensed
   macOS guest and Xcode installation, and enough free storage. The proof used
   Tart **2.40.1**, guest **macOS 26.6.2**, Xcode **27.0**, **4 vCPUs / 8 GiB RAM /
   80 GB virtual disk / 1440x900 display**. These are tested inputs, not a promise
   that they suit every host. Xcode's minimum guest OS is separate from Notch's
   deployment target.
2. **Install Tart locally.** Download the exact official release archive, verify
   its published SHA-256, code signature, Gatekeeper assessment and bundled
   license. Keep the complete `tart.app` bundle in `work/`; use `TART_HOME` under
   this directory rather than another user's cache. The tested archive was
   `https://github.com/openai/tart/releases/download/2.40.1/tart.tar.gz`,
   SHA-256 `363e2701154a8155cbc1bb6d845430c9b42697d2a186bc49574471ca2877db46`.
   Its FSL-1.1-ALv2 terms permit internal use; read the terms of the actual version.
3. **Create a fresh guest from Apple.** Resolve a host-supported Apple restore
   image, pin its version/URL/digest and verify the downloaded bytes before
   `tart create <name> --from-ipsw <verified-file> --disk-size 80`.
   Use `tart set <name> --cpu 4 --memory 8192 --display 1440x900 --no-display-refit`.
   Do not adopt an image with disabled security controls as an unnoticed shortcut.
   Apple guest licensing is independent of Tart's license.
4. **Complete one-time guest setup manually.** Create a test-only local account
   named `notch`, with no Apple Account, personal-data migration or host keychain.
   Enable Remote Login for that account only. Install a dedicated SSH public key
   and verify the guest's host fingerprint through the visible guest console
   before authenticating. Keep strict host-key checking enabled. Never store an
   account password in source, fixtures, command arguments or evidence.
5. **Configure this guest, not the host.** For unattended use, the owner must
   choose automatic login; display timeout and screen saver **Never**; no automatic
   system sleep; and **Require password after screen saver/display off: Never**.
   These intentionally reduce protection of the test guest's graphical session.
   Keep it free of personal data. Verify effective behavior, not just toggles.
   The owner may authorize UI testing in guest Terminal with
   `/usr/bin/automationmodetool enable-automationmode-without-authentication`.
   Authenticate there; never automate privacy approval or modify privacy databases.
6. **Install complete, licensed Xcode and the exact candidate.** Finish Xcode's
   first launch and verify `DEVELOPER_DIR=... xcodebuild -checkFirstLaunchStatus`.
   Build Notch using the repository's normal approved process, or use an explicitly
   chosen existing artifact. Record its path, version, executable SHA-256 and
   signature status; install those exact bytes into the guest. Do not silently
   rebuild, re-sign, substitute a different release, or bypass Gatekeeper.
   `ditto` ZIP archives and guest-local extraction preserved framework symlinks
   in the proof; direct `.app` copying through the shared filesystem did not.
7. **Build and run the source-only probe.** Follow
   [the experiment README](../../experiments/tart-regression/README.md). Create a
   local candidate manifest from the actual installed artifact, and supply it
   explicitly. No product module, mock, internal controller call or successful
   command dispatch substitutes for the guest UI/pixel assertion.
   Existing permission-free About may use ad-hoc builds. New panel or
   ScreenCapture-dependent cases require parent-signed stable Products prepared
   outside the guest with the already-approved certificate; never copy private
   keys. Verify the complete immutable artifact/source/designated requirement
   before a human grants guest permissions. Record the actual responsible
   `.xctrunner` and fixed ignored work path separately from candidate identity.
   Preserve existing owner-granted runners during migration. A changed source
   hash with the same requirement still needs native permission/readiness proof;
   stable signing alone does not guarantee TCC reuse or a successful headless exit.
8. **Prove reset and isolation.** Shut down the guest normally before cloning a
   baseline. Run one disposable clone at a time with
   `tart run <clone> --no-graphics --no-audio --no-clipboard --no-usb-accessories --net-host`.
   `--net-host` intentionally has no internet; Tart's default shared NAT is a
   separate choice. Verify automatic graphical login, candidate identity,
   actual PASS/FAIL/BLOCKED results, cleanup and a fresh-clone repeat.
   Never treat suspend/resume as disk rollback or host-only networking as proof
   that an optional remote-control listener binds only to loopback.

A visible guest is started by omitting `--no-graphics`. The viewer's red close
button stops the VM; it is not a hide button. CLI-managed background processes
must be supervised and checked for readiness. Preserve unrelated VMs and apps.

## What the proof established, and what it did not

- Guest-local native clicks, hovering, automatic Settings opening, screenshots
  and Vision OCR worked against the unchanged installed candidate with no host
  VM window. Wrong visible output produced FAIL; stale evidence produced BLOCKED.
  General/closed Settings state was restored after each case.
- A fresh clone reproduced the checks with identical test inputs; the original
  stopped baseline's full disk/configuration/NVRAM hashes remained unchanged.
  Host observations and owner feedback supported non-disruptive execution.
- The first overnight experiment **did not prove locked-host UI regression**:
  one three-case round behaved as expected, then 60 attempts blocked. The guest
  was confirmed locked on morning inspection. Automatic login and host Caffeine
  do **not** prevent the guest from locking after idle time. There were 27 attempts
  with the host confirmed locked and no successful UI result among them.
- After the owner changed guest idle/lock settings, the headless guest passed
  the positive and both negative controls before and after a 12-minute interval
  with no guest commands/input. The reconstructed source-only probe then passed
  with the host locked throughout a 45-second, 899-sample observation: no Tart
  window, host pointer movement or Space switch. This establishes a **bounded
  locked-host success**, not a replacement overnight reliability result.
- A separately packaged Accessibility helper did not obtain a usable grant in
  this experiment. It is **not a dependency** of the successful native notch-gear
  route. Neither helper Screen Recording permission nor remote management is
  required by that route.

The repository now includes `regression-test`, `regression-suite` and the
user-only `setup-regression-suite` skills around this initial executable suite.
Every new candidate/environment needs its own evidence. Real-notch hardware,
accounts, media devices, broader feature coverage and long-term reliability
remain separate work.
