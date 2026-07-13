# Mental Omega Randomizer Launcher

Standalone Windows launcher for a Mental Omega campaign randomizer.

This project is currently a non-Archipelago base. It can generate a seed, launch missions directly from the Mental Omega folder, track objective/victory rewards, lock unearned tech, and apply earned unlocks and buffs through generated mission map copies.

## Normal User Quick Start

1. Download the latest release zip from this repository.
2. Extract `MentalOmegaRandomizer.exe` and `RandomizerLauncherRuntime` into your Mental Omega game folder, next to `MentalOmegaClient.exe`, `Syringe.exe`, and `gamemd.exe`.
3. Start `MentalOmegaRandomizer.exe`.
4. Choose campaign, difficulty, game speed, mission goal, rewards per objective, and reward settings.
   `Standard` uses campaign-aware rewards and role translation; Foehn seeds bundle matching Allied/Soviet access and buffs together. `Chaos (Experimental)` forces randomized unit access and allows every earned unit from the matching barracks, factory, air command, shipyard, or Construction Yard of any faction the mission lets the player operate. It does not grant the other factions' production structures. In-game production cameos are kept in contiguous faction blocks with the current player faction first. Its optional same-tier sharing setting applies a unit buff to every curated cross-faction equivalent (for example GI, Conscript, Initiate, and Knightframe).
   Hover over a setting for an explanation. Buff subsettings are disabled when buff rewards are off, and defensive-building access/buffs can be included or excluded independently.
5. Press `Generate New Seed`.
6. Select an open mission and press `Launch Mission`.
7. Finish objectives and win the mission. The launcher detects rewards automatically and, by default, closes the spawned game after detecting victory.

For debugging, expand `Show Launcher Log` to reveal the `Debug: Mark Complete` override. It is intentionally hidden during normal play and every use is written to persistent diagnostics.

The launcher starts missions with speed control enabled. If you change speed in the launcher, it writes the selected speed before launch and the in-game speed slider should remain available.

## Developer Start

Run from the Mental Omega game folder:

```powershell
python RandomizerLauncher\launcher_gui.py
```

Or build and run the standalone one-file executable:

```powershell
powershell -ExecutionPolicy Bypass -File RandomizerLauncher\build_exe.ps1
.\MentalOmegaRandomizer.exe
```

Keep the generated `RandomizerLauncherRuntime` folder next to the EXE. The on-directory package avoids the slow temporary extraction performed by a one-file executable.

The build requires PyInstaller (`python -m pip install pyinstaller`). The resulting EXE bundles Python and Tkinter; players do not need Python or the source folder.

For an installation/resource check without opening the UI, run `MentalOmegaRandomizer.exe --self-check`. Results are written to `RandomizerLauncherData\self_check.json`.

## Important Files

- `launcher_gui.py` starts the active launcher.
- `randomizer_app.py` contains the Tk UI and game launch flow.
- `randomizer_map.py` handles generated map patching, hooks, tech locks, and map-local buffs.
- `randomizer_cameos.py` extracts and decodes installed in-game cameo art for the unlock UI.
- `randomizer_rewards.py` contains the reward catalogue and display helpers.
- `randomizer_config.py` reads/writes the YAML-style setup file.
- `README_RANDOMIZER.md` is the longer user guide.
- `TECHNICAL_FINDINGS.md` explains the implementation details and discoveries.

When running the packaged EXE, writable state, configuration, diagnostics, generated maps, backups, and extracted cameo images are stored under `RandomizerLauncherData`. Cameos are extracted on demand from the installed Mental Omega MIX archives, so no image bundle is required.

## Current Status

Working:

- seed generation
- campaign filter
- mission goal length
- rewards per objective/victory check
- direct spawned mission launch
- launcher-selected game speed with in-game speed control enabled
- objective/victory marker hooks for many maps
- automatic spawned-game close after a detected victory
- sortable mission columns and green completed-mission rows
- global tech locking and earned tech unlocks
- positive buff rewards
- optional building-free faction superweapon rewards
- guarded map-local unit/weapon buffs
- optional allied-helper buffing
- real in-game unit cameos grouped by faction in the Current Unlocks view

Known limits:

- game-speed behavior still needs validation across more campaign maps
- objective-to-trigger mapping still needs mission-specific refinement
- matching superweapon buildings may share the granted power instead of creating a second independent cameo
- perfect player-only buff isolation may eventually need cloned player-only units or a runtime hook

## Archipelago

Archipelago is planned for later. The current YAML/config structure is intentionally shaped to make a future Archipelago world easier, but this launcher does not connect to Archipelago yet.
