# Getting Started

This guide takes a new RigManifest workspace from a CHIRP radio image to a compiled,
bank-aware image ready to inspect and upload with CHIRP.

## 1. Install RigManifest

Download the appropriate package from the
[latest GitHub Release](https://github.com/jongentsch/rigmanifest/releases/latest).

- **Windows installer:** normal desktop installation; data lives in the per-user
  application-data directory.
- **Windows portable ZIP:** extract the entire archive and run `RigManifest.exe`.
  Application data stays in the adjacent `data` folder, so move or back up the whole
  extracted folder.
- **Linux AppImage:** mark it executable with `chmod +x RigManifest_*.AppImage` and
  run it. Its workspace stays in `data` beside the AppImage.
- **Debian package:** install the `.deb` normally. Data lives in the per-user
  application-data directory.
- **macOS DMG:** choose the Apple Silicon (`aarch64`) or Intel (`x64`) download,
  open the DMG, and drag RigManifest into Applications. The build is ad-hoc signed
  and not Apple-notarized, so approve its first launch in **System Settings > Privacy
  & Security**. Data lives in the per-user application-data directory.

Dark mode is the first-run default. Theme and global font scaling are available in
**Settings**.

## 2. Create a source image in CHIRP

1. Connect the radio and download it in CHIRP.
2. Confirm that CHIRP shows the expected memories, banks, and settings.
3. Save the downloaded radio as a CHIRP `.img` file.
4. Keep an untouched backup of this source image.

An image is required because it identifies the exact CHIRP driver and radio variant.
It also carries radio-specific settings and bank information that a CSV cannot.

## 3. Add the radio

Open **My radios** and choose **Add radio from IMG**.

![My radios page](images/radios.png)

RigManifest asks CHIRP to load the image and then:

- records the detected model and capabilities;
- imports non-empty memories as reusable frequency definitions;
- imports populated banks as frequency sets;
- creates a profile that groups those bank sets;
- preserves unbanked memories as direct profile selections; and
- copies the unchanged source image into the workspace's managed `radios` directory.

The SQLite database tracks image versions and relative paths. The image bytes are not
stored as database blobs.

## 4. Organize the frequency library

Open **Frequency library** to edit user-owned sets and definitions or reuse built-in
read-only presets.

![Frequency library](images/frequency-library.png)

A definition stores RF intent independently of a radio. Give it a useful name and
review receive frequency, transmit behavior, signaling, mode, and tuning step. CHIRP
provides the standard CTCSS values shown by the editor.

The saved advisory plan can flag unusual offsets or frequency placement. Its findings
are guidance only and never prevent you from saving a definition.

## 5. Build profiles

Open **Profiles** and create a reusable operating loadout such as Home, Dayton,
Canada Trip, Vacation Home, or Emergency.

![Profiles and prospective banks](images/profiles.png)

A profile may include many sets and individual definitions. The right-hand preview
groups set-based selections as prospective banks, but it is not yet a compiled radio
plan. Final memory numbering and bank behavior depend on the radio selected later.

## 6. Compile and export

Open **Compile & export** and choose:

- one image-backed radio;
- zero or more profiles;
- any additional frequency sets; and
- any additional individual definitions.

Compile the selection and inspect the memory table, capacity summary, and diagnostics.

![Compiled memory plan](images/compile-plan.png)

Warnings remain advisory. A definition is omitted only when the target radio or CHIRP
driver cannot safely represent it, such as an out-of-range transmit frequency or an
unsupported signaling mode. RigManifest reports the reason.

Choose **Export CHIRP IMG** to create a new image. RigManifest loads a managed copy of
the source through CHIRP, applies memories and bank mappings through the detected
driver, and asks CHIRP to save a new image. It never overwrites the source image.

## 7. Verify and upload

Open the exported image in CHIRP before writing it to the radio. Review at least:

- memory frequencies and transmit behavior;
- labels;
- CTCSS/DCS access and receive squelch;
- banks and memberships; and
- radio-specific settings that should have remained unchanged.

Use CHIRP's normal upload workflow when the image looks correct.

## Backups and updates

Use **Back up data** from the Frequency Library page before major catalog changes.
Backups include the SQLite workspace and managed radio-image directory.

Installed Windows, macOS, and Linux AppImage builds can install signature-verified
updates after approval and create a workspace backup first. Windows portable and
Debian builds notify you about new releases but require manual replacement.

Next: read the [User Guide](user-guide.md) for page details or
[Core Concepts](concepts.md) for the data model.
