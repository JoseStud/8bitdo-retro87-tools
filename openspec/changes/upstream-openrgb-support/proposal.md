## Why

The keyboard works in OpenRGB only through a local patch (`openrgb/retro87-openrgb.patch`) and an unofficial fork. Every user must build or download a patched OpenRGB, and the patch can stop applying whenever upstream changes. A merge request to OpenRGB would end that. Notes for it exist in research/openrgb-merge-request.md, but nothing has been submitted.

## What Changes

- Prepare and submit a merge request to upstream OpenRGB (https://gitlab.com/CalcProgrammer1/OpenRGB), by a human, after a human rework and review of the code.
- Until it is merged, keep the local patch applying to upstream `master` and keep the two patch copies (this repository and the fork) identical.
- Close the testing gaps the draft lists before submitting.
- After a merge, shrink or remove the local patch and point the installer and documents at upstream OpenRGB.

What the record says today:

- The patch adds an 8BitDo Retro 87 controller (dongle and cable), Direct mode over the cable through HID LampArray, and a libusb path for LampArray interfaces without an interrupt-IN endpoint, including a fix for an uninitialised report-ID table. (OPENRGB.md, Changes in the OpenRGB patch)
- It was made against OpenRGB `d008deb` and also applied to `c1784ca` (upstream `master` on 2026-09-28). (OPENRGB.md, Option 3)
- `update-openrgb.sh` rebuilds daily from upstream `master` plus the patch and keeps the old binary if the patch fails to apply. The fork's workflow does the same and opens an issue on failure. (OPENRGB.md, Option 1 and Option 2)
- OpenRGB's CONTRIBUTING.md does not permit AI-generated submissions as a general rule and forbids AI authorship credits. The patch was written with an AI assistant, so it must not be submitted as-is. (OPENRGB.md, Upstream status)
- Tested on Linux over the cable only. Not yet tested: every effect mode through OpenRGB on hardware, the dongle path with this build, Windows and macOS. That leaving Direct writes nothing was not measured on hardware. (research/openrgb-merge-request.md, Testing so far; OPENRGB.md, Tests)
- Known limits: Direct and the merged device use the Linux libusb path only; with two wired Retro 87 keyboards the device takes the first LampArray found. (OPENRGB.md, Limitations)

What is unknown or needs the owner:

- Whether the owner wants to submit at all, given upstream's AI policy, and who the human submitter is.
- What upstream's CONTRIBUTING.md says today. The record is from 2026-09-28.
- Whether upstream wants one merge request or two (the generic LampArray transport, and the 8BitDo controller).
- Whether upstream accepts the flash-wear protection (coalesced saves on a background thread) in its current form.
- Whether the patch still applies to today's upstream `master`.
- How the patch behaves on Windows and macOS. Nobody has built it there.

## Capabilities

### New Capabilities
- `openrgb-support`: how the keyboard's OpenRGB support is delivered, kept current, and moved upstream.

### Modified Capabilities

None.

## Impact

- `openrgb/retro87-openrgb.patch`: reworked by a human; later reduced or removed.
- `research/openrgb-merge-request.md`: becomes the final merge request text, written by the submitter.
- `OPENRGB.md`, `README.md`: setup options and upstream status.
- `update-openrgb.sh`, `install-kde.sh`, `kde/retro87-openrgb-update.*`: simplified once upstream has the support.
- The fork `JoseStud/OpenRGB-8BitDo-Retro87`: its patch copy and release workflow.
- An external project and its maintainers. A merge request is public.
- Non-goals: AUR packaging; Windows or macOS Direct mode; new lighting features; firmware updates.
