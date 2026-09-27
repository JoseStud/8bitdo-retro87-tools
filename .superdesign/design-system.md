# Retro 87 Panther Linux desktop

## Product and reference
Unofficial, native Linux PySide6/QML configuration utility for the 8BitDo Retro
87 Mecha BREAK: Panther, through its wireless dongle. Reuse the existing Python
backend. This is a desktop utility, NOT a landing page or web dashboard.

Primary visual source: official Ultimate Software V2 keyboard screenshot at
https://app.8bitdo.com/images/support/new-software/mapping.jpg.
That screenshot shows the Fami edition, not Panther. Preserve its application
shell and spatial arrangement; do not claim Panther pixel-perfect fidelity.
The official V1.35 managed assembly confirms Keys, Macros, Volume, Lighting,
profile navigation and keyboard/extension-button diagrams.

## Visual rules
- Flat near-black #171717 application background; dark-gray #303030 controls.
- Off-white #e8e8e8 text, muted #a5a5a5 labels, cyan #72d7ed active icons and
  thin active-tab underline. Amber #dba836 is reserved for device cautions.
- Segoe UI where available, Noto Sans/system sans fallback on Linux; compact
  12–14 px control text, 16 px section names. No decorative fonts.
- Thin gray borders, square or subtly rounded controls (2–4 px), no gradients,
  large cards, decorative glow, marketing headings, or spacious dashboard grid.
- Small title bar with application title and window controls. Show independent
  identity: 'Retro 87 Tools · Unofficial'. Do not invent an 8BitDo logo.
- Top-left back arrow labelled Profiles. Centered icon tabs: Keys, Macros,
  Volume, Lighting. Current profile below tabs. Left narrow control panel;
  right large accurate TKL keyboard diagram and extension-button area below.
- Keyboard diagram must be selectable keycap geometry, not a pasted screenshot
  or generated raster. Panther appearance is provisional; use dark neutral
  keycaps, subdued gray legends and cyan selected-key outlines.
- A compact bottom bar is a deliberate safety addition: connection, experimental
  status, pending-edit count, Discard and Apply. No RGB animation unless requested.

## Workflows
Keys: select a physical key, inspect current assignment, choose category/target,
stage assignment. Categories from official binary: Default, Function,
Alphanumeric, Navigation, Modifiers, Symbol, Mouse Function, Multimedia, None.
Macros: list and sequence editor, delays, repeat controls, focused recording.
Lighting: Preset/Custom, effect selector, brightness/speed/color and per-key
selection where supported. Volume: device sound control. Profiles: create,
import/export, backup and restore. Pages beyond Keys are future flow designs.

## Safety and truthful status
Opening the GUI and navigating must never change the device. Changes are staged;
Apply explicitly backs up and writes. Hardware tests require separate approval.
Do not present fake connected status, battery percentage or firmware values.
Design an offline preview state using the existing snapshot: uninitialized
profile, no pending edits. A selected key is not a staged assignment. Apply is
disabled until edits are staged. Unsupported decoded controls carry explanatory
status. Profile creation is explicit, never automatic. Unknown/default device
bytes must not appear as 255% brightness. No claim of verified hardware parity.
Full keyboard parity remains the target; firmware flashing and Windows Dynamic
Lighting integration are out of scope. Final hardware write validation is gated.

## Accessibility and sizing
Target 1200×800 with a minimum 1000×700, usable at 125–200% desktop scale.
Visible keyboard focus, accessible labels, no color-only status. Do not add a
mobile layout. Use original physical TKL grouping and correct key proportions.
