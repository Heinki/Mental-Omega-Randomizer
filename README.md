<p align="center">
  <img src="mo-logo-puzzle.png" alt="Mental Omega Randomizer Launcher logo" width="500">
</p>

# Mental Omega Randomizer Launcher

[![Security checks](https://github.com/Heinki/Mental-Omega-Randomizer/actions/workflows/security.yml/badge.svg)](https://github.com/Heinki/Mental-Omega-Randomizer/actions/workflows/security.yml)

A standalone Windows campaign randomizer for Mental Omega. It generates deterministic mission and reward plans, launches campaign maps directly, tracks objective and victory checks, locks unearned technology, and applies earned access and buffs through generated mission copies.

Archipelago is planned but is not connected yet. The standalone configuration deliberately uses stable option-style keys so those settings can later map to an Archipelago world.

## Disclaimer

I am *not* part of the Development of Mental Omega nor did I contribute in any way, all I did was access the game and the mapfiles to create the randomizer. Credits go to the Mental Omega Developers and their work!

## Quick Start

1. Make a **new, separate, fresh installation of Mental Omega**. Do not use the copy in which you normally install map packs, funmaps, rules edits, or other modifiers.
2. Start that clean installation normally once and verify that an original campaign mission launches.
3. Put `MentalOmegaRandomizer.exe` in that installation's root folder beside `MentalOmegaClient.exe`, `Syringe.exe`, and `gamemd.exe`.
4. Run `MentalOmegaRandomizer.exe`.
5. Choose the seed settings and press **Generate New Seed**.
6. Select an open mission and press **Launch Selected Mission**.
7. Complete objectives and win. The launcher records detected checks and applies earned rewards to future mission launches.

## Release Safety and Verification

No badge or antivirus scan can prove that any program is harmless. Releases use checks that make the build public and verifiable:

- GitHub Actions builds tagged Windows releases from repository source on a clean hosted runner.
- CodeQL scans Python source, and dependency review rejects newly introduced vulnerable build dependencies.
- Every release includes `SHA256SUMS.txt` and GitHub-signed build provenance.
- The Windows package build must succeed before a release is published.

Download only from this repository's [GitHub Releases](https://github.com/Heinki/Mental-Omega-Randomizer/releases). Verify its checksum in PowerShell:

```powershell
$expected = (Get-Content .\SHA256SUMS.txt).Split()[0]
$actual = (Get-FileHash .\MentalOmegaRandomizer.exe -Algorithm SHA256).Hash.ToLowerInvariant()
$actual -eq $expected
```

Expected result is `True`. With [GitHub CLI](https://cli.github.com/) installed, verify that GitHub built the exact EXE from this repository:

```powershell
gh attestation verify .\MentalOmegaRandomizer.exe --repo Heinki/Mental-Omega-Randomizer
```

Build provenance proves where the file came from; it is not an antivirus verdict. Microsoft SmartScreen may still warn about a new or unsigned EXE because file and publisher reputation are separate from malware detection. Do not disable antivirus. If Defender incorrectly detects a release, submit that exact release to [Microsoft Security Intelligence](https://www.microsoft.com/wdsi/filesubmission) as a software developer and include the resulting submission ID in the issue report. Authenticode code signing remains the next step for showing a verified publisher name.

### Supported game content

The Randomizer has been developed and tested against the **original Mental Omega campaign maps only**. Custom maps, funmaps, map packs, modified rules, and installations containing other gameplay modifiers are not currently supported. Those additions can redefine houses, units, weapons, triggers, and mission scripts in ways the Randomizer has not audited; combining them may produce incorrect rewards or progress, buff the wrong force, fail to launch, or affect the original content.

Using a dedicated clean installation is the same isolation normally recommended for map packs and other game modifiers. It protects the player's usual installation and gives bug reports a known baseline. The launcher does **not** modify Mental Omega's MIX archives: it reads the installed archives, creates a generated loose copy of the selected campaign map, and stores its own configuration, saves, logs, and caches in `RandomizerLauncherData`.

**Mission List** progression opens the first three missions and adds one more after each victory. **Grid Mode** places the required missions on a compact faction-colored board: completing a node opens its orthogonal neighbors, and the bottom-right exit finishes the run after every required node is cleared. Mixed-campaign seeds weight the short seven-mission Foehn campaign proportionally instead of allowing it to dominate the randomized order. The hidden **Debug: Mark Complete** control appears only when the launcher log is expanded and is intended for development recovery.

## Early Development Stage

The current code is still a hot mess, since this is the first version I am releasing before doing more cleanup. It was also written with the help of ChatGPT so there might be even more code parts that need further cleanup.
Features may be incomplete, behave incorrectly, or cause crashes. 
The Randomizer was mostly tested with the Allied Faction, a bit of Soviets and barely with Epsilon and Foehn
For the Foehn faction the player will get Soviet/Allied tech instead as the Foehn Campaign does not have their own faction units.
In Chaos Mode you can get Foehn unit however.
Please report reproducible problems through the repository's [issue tracker](https://github.com/Heinki/Mental-Omega-Randomizer/issues).


## AI-Assisted Development

This project was developed with assistance from OpenAI's ChatGPT, including Codex coding assistance. AI tools have been used to analyze Mental Omega's INI formats, catalogue unit, weapon, projectile, and image tags for the UI, and support implementation, refactoring, debugging, and documentation. Generated suggestions are reviewed, adapted, and validated against project requirements before inclusion. Final design decisions, releases, and project behavior remain the responsibility of the project maintainer.

## Documentation

Each document has one purpose so the same behavior is not maintained in several places.

| Document | Audience | Authoritative content |
|---|---|---|
| [README_RANDOMIZER.md](README_RANDOMIZER.md) | Players and future Archipelago option authors | Complete settings tables, reward display, game modes, seed lifecycle, and user-facing limitations |
| [TECHNICAL_FINDINGS.md](TECHNICAL_FINDINGS.md) | Developers | Launch architecture, generated-map pipeline, objective/victory hook implementation, reward planning, tech locking, and buff safety |
| [configs/README.md](configs/README.md) | Maintainers and advanced users | Editable static mission, faction, reward, unit, and UI JSON configuration |
| `config/mental_omega_randomizer.yaml` | Launcher/runtime | Saved standalone option values; it is data, not a second source of documentation |

## Developer Workflow

Run the launcher from source, starting in the Mental Omega folder:

```powershell
python RandomizerLauncher\launcher_gui.py
```

Before packaging, compile every source module to catch syntax and import-time parsing errors:

```powershell
Set-Location RandomizerLauncher
python -m compileall -q .
python launcher_gui.py --self-check
```

Build the packaged launcher from the Mental Omega folder with:

```powershell
powershell -ExecutionPolicy Bypass -File RandomizerLauncher\build_exe.ps1
```

GitHub Actions installs pinned build dependencies from `requirements-build.txt` automatically. Only install them yourself when choosing an optional local build:

```powershell
python -m pip install -r RandomizerLauncher\requirements-build.txt
```

The build uses PyInstaller without UPX packing, embeds the release number as Windows version metadata, and embeds `mo-logo-puzzle-icon.ico`, an exact unscaled 32 x 32 crop from `mo-logo-puzzle.png`, as both the Windows executable icon and the running Tk window icon. Build dependencies are installed temporarily on the GitHub runner; maintainers need them locally only when choosing to build locally. Players do not need Python, build packages, the source directory, or a separate runtime folder. The launcher creates `RandomizerLauncherData` for configuration, saves, logs, and cached map/cameo data after it is run; this is writable player data, not part of the distributed application.

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
| `randomizer_missions.py` | Pure campaign parsing, faction normalization, stage scoring, and deterministic mission ordering |
| `randomizer_ini.py` | Order-preserving INI/map parsing and one-pass section merging |
| `randomizer_map.py` | Generated-map patching, marker helpers, tech rules, and map-local buffs |
| `randomizer_mission_safety.py` | Mixed-faction and Chaos production access |
| `randomizer_rewards.py` | Reward catalogue, equivalence groups, stacking, and display helpers |
| `randomizer_cameos.py` | Installed MIX cameo extraction and PCX-to-PNG decoding |
| `randomizer_config.py` | YAML-compatible configuration defaults and persistence |
| `randomizer_diagnostics.py` | Bounded structured launcher logging for support and debugging |
| `randomizer_paths.py` | Source and packaged runtime paths |
| `randomizer_weapon_stats.py` | Readable accessors for the installed weapon registry snapshot |
| `randomizer_weapon_stats_data.py` | Generated packed Mental Omega 3.3.6 weapon data |
| `build_exe.ps1` | PyInstaller build and packaged self-check workflow |

Packaged writable data lives under `RandomizerLauncherData`; source-mode data lives under `RandomizerLauncher`.

## Troubleshooting and Bug Reports

Run `MentalOmegaRandomizer.exe --self-check` first. The result is saved to `RandomizerLauncherData\self_check.json`, and structured launcher diagnostics are kept in `RandomizerLauncherData\logs\launcher.log`. Objective and victory marker activity comes from the game's `debug\debug.log`.

When reporting a reproducible problem, include those files together with the mission code, seed, reward mode, and whether the issue also occurs on a fresh unmodified Mental Omega installation. Do not post `randomizer_state.json` publicly without reviewing it first; it contains the active run's seed and progress.

## Current Status

The standalone flow supports seed generation, campaign filtering, Standard and experimental Chaos rewards, direct spawned mission launch, objective/victory marker detection on many maps, tech locking/unlocking, positive buffs, allied-helper buffs, optional building-free offensive/secondary superweapons and aid powers, and installed in-game unit and superpower cameos.

The principal remaining limitations are mission-specific objective matching, a few allied-house safety cases, validation of game speed on more maps, and engine limits around isolating direct unit/weapon buffs when enemies use the same global type. See [Technical Findings: Known Limits](TECHNICAL_FINDINGS.md#known-limits) for the maintained list.


## Contact

In the official Mental Omega Discord is a channel for the Randomizer mo_randomizer you can contact me there or via Discord where my Name is Heinki
Mental Omega Discord Invite link : https://discord.com/invite/KpJzhWY
