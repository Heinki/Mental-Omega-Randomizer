# Mental Omega Randomizer Launcher

Standalone Windows launcher for a Mental Omega campaign randomizer.

This project is currently a non-Archipelago base. It can generate a seed, launch missions directly from the Mental Omega folder, track objective/victory rewards, lock unearned tech, and apply earned unlocks and buffs through generated mission map copies.

## Normal User Quick Start

1. Download the latest release zip from this repository.
2. Extract `MentalOmegaRandomizer.exe` into your Mental Omega game folder, next to `MentalOmegaClient.exe`, `Syringe.exe`, and `gamemd.exe`.
3. Start `MentalOmegaRandomizer.exe`.
4. Choose campaign, difficulty, game speed, mission goal, rewards per objective, and reward settings.
5. Press `Generate New Seed`.
6. Select an open mission and press `Launch Mission`.
7. Finish objectives and win the mission. The launcher should detect most rewards automatically and, by default, close the spawned game after detecting victory. Use `Mark Complete` only if the victory reward was missed.

The launcher starts missions with speed control enabled. If you change speed in the launcher, it writes the selected speed before launch and the in-game speed slider should remain available.

## Developer Start

Run from the Mental Omega game folder:

```powershell
python RandomizerLauncher\launcher_gui.py
```

Or build and run the small Windows bootstrap:

```powershell
powershell -ExecutionPolicy Bypass -File RandomizerLauncher\build_exe.ps1
.\MentalOmegaRandomizer.exe
```

The developer bootstrap does not bundle Python. A local Python install with Tkinter is required when running from source.

## Important Files

- `launcher_gui.py` starts the active launcher.
- `randomizer_app.py` contains the Tk UI and game launch flow.
- `randomizer_map.py` handles generated map patching, hooks, tech locks, and map-local buffs.
- `randomizer_cameos.py` extracts and decodes installed in-game cameo art for the unlock UI.
- `randomizer_rewards.py` contains the reward catalogue and display helpers.
- `randomizer_config.py` reads/writes the YAML-style setup file.
- `audit_reward_catalog.py` is a developer validation script for checking reward/unit references.
- `README_RANDOMIZER.md` is the longer user guide.
- `TECHNICAL_FINDINGS.md` explains the implementation details and discoveries.
- `TRIGGER_INVESTIGATION.md` tracks the objective/victory hook investigation.

Runtime files such as generated maps, backups, Python cache, and `randomizer_state.json` are ignored by Git.

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
- real in-game unit cameos in the Current Unlocks view

Known limits:

- game-speed behavior still needs validation across more campaign maps
- objective-to-trigger mapping still needs mission-specific refinement
- matching superweapon buildings may share the granted power instead of creating a second independent cameo
- perfect player-only buff isolation may eventually need cloned player-only units or a runtime hook

## Archipelago

Archipelago is planned for later. The current YAML/config structure is intentionally shaped to make a future Archipelago world easier, but this launcher does not connect to Archipelago yet.
