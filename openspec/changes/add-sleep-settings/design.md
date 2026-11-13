## Context

See proposal.md for the motivation and for the list of known and unknown facts. The design question is which values the tools may write while the valid range is unknown.

Evidence levels:

- `0x5cc` layout and its native writer: vendor code only. Two hand-made writes were accepted and read back (300 → 0, later → 65535).
- Zero being rejected or reset: inferred from one later read of 60.
- `0x26` and `0x27`: named in the profile layout only. No writer or UI control traced.

## Goals / Non-Goals

**Goals:**

- Let the owner change the LED sleep timeout without hand-made byte writes.
- Never offer a value whose effect is unknown as if it were safe or meaningful.

**Non-Goals:**

- An "always on" promise. It is offered only if a value is hardware-verified to do that.
- Changing `0x26` or `0x27` before their meaning is decoded.
- Firmware changes.

## Decisions

1. **Decode before code.** The vendor UI control and its choices are traced first with `research/inspect_vendor.py`. The result is written to research/README.md. Alternative: ship a free number field now. Rejected, because zero has already behaved unexpectedly.
2. **Allowed values come from evidence.** The tools accept a value only if it is a vendor UI choice or a value the owner has checked on hardware. Until the trace is done, the confirmed set is empty and the feature stays read-only. Alternative: accept any uint32. Rejected for the same reason.
3. **Zero is refused** unless the trace or a hardware check shows what it does.
4. **One write of four bytes at `0x5cc`**, matching the vendor writer, through the existing apply path (backup, write, readback). No new transport code.
5. **`0x26`/`0x27` are a second step.** They get a setter only if decoding shows that this model uses them. Otherwise they stay preserved bytes and the tools show their raw value.
6. **Same staging model as volume.** In the desktop app the edit is staged, reviewed and applied like the sound level. In the CLI it is a command that previews by default.

## Risks / Trade-offs

- The firmware may clamp or reset values → the tools read the value back and report a mismatch; the owner's idle check is the real proof.
- The dongle answers reads from its own copy → readback does not prove the keyboard stored the value; the idle observation does.
- The vendor UI may offer no sleep control for this model → the change then ends after the decoding tasks with a documented "not supported", and only the read-only display stays.
- Storage wear → one profile write per explicit user change. Profile-write wear is not measured (research/storage-wear.md covers the LED block), so the tools skip a write when the value is unchanged.

## Open Questions

- Does the setting apply while the profile is inactive? Answered by task 2.4. It does not change the design.
