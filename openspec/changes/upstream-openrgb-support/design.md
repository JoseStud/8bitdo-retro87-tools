## Context

See proposal.md. The hard constraint is upstream's contribution policy as recorded in OPENRGB.md: no AI-generated submissions as a general rule, and no AI authorship credits. The patch and the draft text were written with an AI assistant. The record says "a submitter would need to rework and fully vet it".

The patch is about 2,000 lines over two controller directories: `Controllers/HIDLampArrayController` (changed) and `Controllers/8BitDoController/8BitDoRetro87Controller` (new).

## Goals / Non-Goals

**Goals:**

- A submission that follows upstream's rules honestly.
- A local patch that keeps working until upstream has the support, and gets smaller after.
- Flash-wear protection that survives the move upstream.

**Non-Goals:**

- Having an AI agent write, rework or submit the upstream code or text. The rework is human work.
- Hiding how the code was first written.
- Publishing packages.

## Decisions

1. **The owner decides first, and asks upstream.** Before any rework, the owner re-reads upstream's current CONTRIBUTING.md and decides whether to go on. If the policy is unclear for a human-reworked patch, the owner asks the maintainers before investing the time. Alternative: submit and see. Rejected: it risks breaking the project's rules in public.
2. **The human submitter owns the code.** The owner (or another human) rewrites and reviews every part until they can explain and defend it, and writes the merge request text themselves. Agents may run builds and tests on the local patch and keep this repository's documents current. They do not author upstream commits. Alternative: agent-prepared branches for the owner to push. Rejected by the recorded policy.
3. **Propose two merge requests.** First the generic LampArray change (libusb transport for interfaces without an IN endpoint, and the report-ID table fix). It helps other devices and is easier to review. Then the 8BitDo controller, which depends on it. Alternative: one merge request. Simpler to prepare, but mixes a generic change with a device driver. The owner may choose either after asking upstream.
4. **Keep the wear protection in the device.** Coalesced saves and the identical-write skip stay part of the controller in the submission, with the hardware evidence from research/storage-wear.md in the description. If upstream wants a different shape, the limits stay the same: Custom writes at most once per second, identical writes skipped, Direct never saved.
5. **Close the test gaps before submitting.** Every effect through OpenRGB on hardware, the dongle path with the patched build, and a build check on Windows and macOS (compile only is acceptable if no hardware is at hand; the gap is then stated in the merge request).
6. **Patch queue stays until merge.** The repository keeps `openrgb/retro87-openrgb.patch` as the source for local builds, as OPENRGB.md "Maintaining the fork" describes. Review changes from upstream flow back into the patch and the fork copy, which stay byte-identical.
7. **After a partial merge, the patch shrinks.** When the first merge request lands, the local patch drops those hunks. When both land, the patch, the updater and the fork's release workflow are retired in a follow-up change, and the installer uses upstream OpenRGB.

## Risks / Trade-offs

- Upstream may decline because of the code's origin → the local patch and fork keep working; the decision and its reason are recorded in OPENRGB.md.
- Upstream moves while the rework is in progress → the daily updater and the fork workflow already report when the patch stops applying; the rework branch is rebased by the submitter.
- Review may ask to drop the background writer → the wear limits are a hard requirement of this project; if upstream's version is weaker, the tray service must keep its own limits and the documents must say so.
- Windows and macOS cannot be tested on hardware by the owner → state it in the merge request; the Linux-only parts are already guarded by the libusb path.
- Custom-mode testing on hardware costs flash erases → the test plan uses a fixed, small number of Custom saves.

## Migration Plan

1. Until merge: no change for users. Local build or fork release, as today.
2. After merge: a follow-up change removes the merged hunks, updates `install-kde.sh` to prefer an upstream OpenRGB that has the device, and updates OPENRGB.md and README.md.
3. Rollback: keep the last patch and the fork release available until an upstream release with the support exists.

## Open Questions

- Which upstream release will first contain the support. This only affects when the local build can be retired.
