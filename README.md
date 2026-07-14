# Mental Omega Randomizer Launcher

A standalone Windows campaign randomizer for Mental Omega. It generates deterministic mission and reward plans, launches campaign maps directly, tracks objective and victory checks, locks unearned technology, and applies earned access and buffs through generated mission copies.

Archipelago is planned but is not connected yet. The standalone configuration deliberately uses stable option-style keys so those settings can later map to an Archipelago world.

## Quick Start

1. Make a **new, separate, fresh installation of Mental Omega**. Do not use the copy in which you normally install map packs, funmaps, rules edits, or other modifiers.
2. Start that clean installation normally once and verify that an original campaign mission launches.
3. Put `MentalOmegaRandomizer.exe` in that installation's root folder beside `MentalOmegaClient.exe`, `Syringe.exe`, and `gamemd.exe`.
4. Run `MentalOmegaRandomizer.exe`.
5. Choose the seed settings and press **Generate New Seed**.
6. Select an open mission and press **Launch Selected Mission**.
7. Complete objectives and win. The launcher records detected checks and applies earned rewards to future mission launches.

### Supported game content

The Randomizer has been developed and tested against the **original Mental Omega campaign maps only**. Custom maps, funmaps, map packs, modified rules, and installations containing other gameplay modifiers are not currently supported. Those additions can redefine houses, units, weapons, triggers, and mission scripts in ways the Randomizer has not audited; combining them may produce incorrect rewards or progress, buff the wrong force, fail to launch, or affect the original content.

Using a dedicated clean installation is the same isolation normally recommended for map packs and other game modifiers. It protects the player's usual installation and gives bug reports a known baseline. The launcher does **not** modify Mental Omega's MIX archives: it reads the installed archives, creates a generated loose copy of the selected campaign map, and stores its own configuration, saves, logs, and caches in `RandomizerLauncherData`.

**Mission List** progression opens the first three missions and adds one more after each victory. **Grid Mode** places the required missions on a compact faction-colored board: completing a node opens its orthogonal neighbors, and the bottom-right exit finishes the run after every required node is cleared. Mixed-campaign seeds weight the short seven-mission Foehn campaign proportionally instead of allowing it to dominate the randomized order. The hidden **Debug: Mark Complete** control appears only when the launcher log is expanded and is intended for development recovery.

## Documentation

Each document has one purpose so the same behavior is not maintained in several places.

| Document | Audience | Authoritative content |
|---|---|---|
| [README_RANDOMIZER.md](README_RANDOMIZER.md) | Players and future Archipelago option authors | Complete settings tables, reward display, game modes, seed lifecycle, and user-facing limitations |
| [TECHNICAL_FINDINGS.md](TECHNICAL_FINDINGS.md) | Developers | Launch architecture, generated-map pipeline, objective/victory hook implementation, reward planning, tech locking, and buff safety |
| `config/mental_omega_randomizer.yaml` | Launcher/runtime | Saved standalone option values; it is data, not a second source of documentation |

## Developer Start

From the Mental Omega folder:

```powershell
python RandomizerLauncher\launcher_gui.py
```

Build the packaged launcher with:

```powershell
powershell -ExecutionPolicy Bypass -File RandomizerLauncher\build_exe.ps1
```

The build requires PyInstaller and produces one self-contained `MentalOmegaRandomizer.exe`. Players do not need Python, the source directory, or a separate runtime folder. The launcher creates `RandomizerLauncherData` for configuration, saves, logs, and cached map/cameo data after it is run; this is writable player data, not part of the distributed application.

Run a packaged installation check without opening the UI:

```powershell
.\MentalOmegaRandomizer.exe --self-check
```

The report is written to `RandomizerLauncherData\self_check.json`.

## Source Layout

| File | Responsibility |
|---|---|
| `launcher_gui.py` | Packaged/source entry point and self-check |
| `randomizer_app.py` | Tk interface, seed flow, game launch, and log watcher |
| `grid_progression.py` | Grid construction, corner trimming, node state, neighbor unlocks, and exit rules |
| `randomizer_map.py` | Generated-map patching, marker helpers, tech rules, and map-local buffs |
| `randomizer_mission_safety.py` | Mixed-faction and Chaos production access |
| `randomizer_rewards.py` | Reward catalogue, equivalence groups, stacking, and display helpers |
| `randomizer_cameos.py` | Installed MIX cameo extraction and PCX-to-PNG decoding |
| `randomizer_config.py` | YAML-compatible configuration defaults and persistence |
| `randomizer_paths.py` | Source and packaged runtime paths |

Packaged writable data lives under `RandomizerLauncherData`; source-mode data lives under `RandomizerLauncher`.

## Current Status

The standalone flow supports seed generation, campaign filtering, Standard and experimental Chaos rewards, direct spawned mission launch, objective/victory marker detection on many maps, tech locking/unlocking, positive buffs, allied-helper buffs, optional building-free offensive/secondary superweapons and aid powers, and installed in-game unit and superpower cameos.

The principal remaining limitations are mission-specific objective matching, a few allied-house safety cases, validation of game speed on more maps, and engine limits around isolating direct unit/weapon buffs when enemies use the same global type. See [Technical Findings: Known Limits](TECHNICAL_FINDINGS.md#known-limits) for the maintained list.
