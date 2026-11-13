## Context

See proposal.md for the known and unknown facts. Commands 5 and 6 are rejected in code today. Command 7 (read) works and a full read-only backup exists (`retro87_macro_backup.py`). On the owner's keyboard all ten blocks read `ff`, so there is nothing to lose yet, but also nothing to compare against.

Evidence levels: the write sequence, the metadata field order and the event fields are vendor code only. The read path and the Super Button identification are hardware-verified. Erase extent, alignment, timer and repeat semantics are unknown.

## Goals / Non-Goals

**Goals:**

- Prove what a macro write changes before any user-facing write exists.
- Make a failed or wrong macro write recoverable from a backup.
- Reuse the existing staging, review, apply and backup model.

**Non-Goals:**

- Guessing byte offsets or semantics. Each one is decoded or measured.
- Recording macros from live typing.
- Writing outside the ten known blocks.

## Decisions

1. **Three gates, in order.** (a) Static decoding closes every unknown that static analysis can close. (b) The owner runs a bounded hardware experiment that measures the erase extent. (c) Only then is the user-facing feature built. Alternative: build the codec and the UI now behind a flag. Rejected: the invariants in GUI_IMPLEMENTATION.md require backup coverage before any write, and coverage cannot be judged without the erase extent.
2. **Erase-extent experiment.** The blocks are all `ff`, so an erase cannot be seen until data exists. The experiment therefore writes one small test macro, with the vendor's exact sequence, into two neighbouring blocks, takes a full backup, then sends the sequence again to the first block only, and compares all ten blocks with the backup. The owner approves each write. The plan is fixed in advance and written down; the run is recorded in research/README.md. Alternative: send command 5 alone. Kept as a second step, because the per-key LED experience shows that a prepare command alone can erase (research/storage-wear.md, Prepare-only erase test).
3. **A dedicated experiment script, not the product path.** The experiment uses a small script that can only touch the two chosen blocks and refuses everything else. The product code keeps rejecting commands 5 and 6 until gate (c). This keeps unfinished write code out of the CLI and the GUI.
4. **Whole-block backup before every macro write.** Before writing a block the tools read every block that the measured erase extent covers, twice, and save it in the `retro87-macro-backup` format. If the erase extent turns out to be larger than one block, the tools rewrite the other affected blocks from the backup in the same operation, or refuse if they cannot.
5. **Compile, then compare, then write.** The local macro document is compiled to block bytes. If the bytes equal what is stored, nothing is written. This is the identical-write skip that research/storage-wear.md asks for.
6. **Assignment is a separate, staged profile edit.** The key record (type 4) is written after the macro block has been verified by readback, so a key never points at a half-written block. Removing a macro resets the key record first.
7. **Snapshots stay separate.** Profile snapshots keep omitting macros. Macro backups keep their own format. The restore command works from a macro backup file.
8. **Local macro files keep their format.** The versioned `retro87-macro` JSON is the source. Fields the hardware cannot express are reported by the compiler, not silently dropped.

## Risks / Trade-offs

- Command 5 may erase more than one block, or shared data → the experiment runs while all blocks are empty, with a full backup of profile, LEDs and blocks, and the profile and LED regions are compared afterwards.
- A wrong metadata layout may confuse the firmware → the first test macro is short and is not assigned to any key until its readback matches; the factory reset combination is the last resort and is named in the experiment plan.
- Flash wear → macro writes happen only on Apply, are skipped when identical, and are never issued in a loop. The experiment plan has a fixed, small number of writes.
- The dongle answers reads from its own copy → the experiment and the first feature checks are done over the USB cable, and playback is checked by pressing the key.
- Static decoding may not settle timer and repeat semantics → those are then measured on hardware with a test macro whose timing can be seen, and the result is recorded before the compiler supports them.

## Migration Plan

Nothing to migrate. Existing macro files and backups keep working. Rollback is restoring the macro backup and the profile backup taken before the write.

## Open Questions

- Should the desktop app show macros that are stored on the keyboard but have no local file? This can wait until decoding of stored blocks works.
