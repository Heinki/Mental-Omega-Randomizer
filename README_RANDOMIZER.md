# Mental Omega Randomizer Launcher

Standalone Windows launcher for a non-Archipelago Mental Omega randomizer.

The launcher starts campaign missions from outside the normal client, generates a seed, tracks mission/objective rewards, locks unearned tech, and applies earned unlocks/buffs through generated map copies.

## Quick Start

Run `MentalOmegaRandomizer.exe` from the game folder, or run:

```powershell
python RandomizerLauncher\launcher_gui.py
```

Use the launcher from the Mental Omega game folder. The current EXE is a small bootstrap and still needs a local Python install.

## Build the EXE Bootstrap

The current `MentalOmegaRandomizer.exe` is a small Windows bootstrap that starts the Python launcher. It does not bundle Python yet.

From the game folder, run:

```powershell
powershell -ExecutionPolicy Bypass -File RandomizerLauncher\build_exe.ps1
```

That compiles `RandomizerLauncher\MentalOmegaRandomizerLauncher.cs` into `MentalOmegaRandomizer.exe` in the game folder.

## GitHub Setup

The Git repository lives in `RandomizerLauncher`, not in the full game folder. The full game folder contains large Mental Omega files and should not be pushed.

From the game folder:

```powershell
cd RandomizerLauncher
git status
git remote add origin https://github.com/<your-user>/<your-repo>.git
git push -u origin master
```

If Fork still only pushes locally, check `Repository Settings > Remotes` and add the same GitHub URL as `origin`. If Git reports an `index.lock` file, close Fork and any terminal Git command first; only remove `.git\index.lock` when no Git process is running.

## Project Layout

- `randomizer_app.py` is the active Tk launcher and game-launch orchestration.
- `randomizer_map.py` contains generated-map patching, tech locks, objective marker helpers, and map-local buff injection.
- `randomizer_paths.py` contains shared launcher/game filesystem paths.
- `randomizer_rewards.py` contains the reward catalogue, reward normalization, and reward display helpers.
- `randomizer_config.py` contains the small YAML-compatible config loader/writer.
- `launcher_gui.py` is only a compatibility entry point that starts `randomizer_app.py`.
- `MentalOmegaRandomizerLauncher.cs` is the small Windows exe bootstrap source. Keep it for building `MentalOmegaRandomizer.exe`; it is not a second launcher implementation.
- `config\mental_omega_randomizer.yaml` is the standalone setup file. It uses Archipelago-style option names where practical, but does not connect to Archipelago yet.
- `randomizer_state.json` is runtime progress for the current seed and should be treated separately from setup YAML.
- `extracted_maps\`, `generated_maps\`, `backups\`, and `__pycache__\` are runtime artifacts and are ignored by the launcher-local `.gitignore`.

For the detailed implementation notes, see `TECHNICAL_FINDINGS.md`. For the trigger/hook investigation history, see `TRIGGER_INVESTIGATION.md`.

## What Works Now

- Reads missions from `INI\BattleClient.ini`, including campaign and special operation missions.
- Uses the Mental Omega difficulty names: `Casual`, `Normal`, `Mental`.
- Launches missions directly through:

```text
Syringe.exe gamemd.exe -SPAWN -CD -SPEEDCONTROL -LOG
```

- Generates a seed with shuffled mission order.
- Lets you choose how many missions are required to finish the seed.
- Lets you choose how many rewards each objective or victory check grants when generating a seed. The current maximum is 5 rewards per check for an intentionally overpowered run.
- Lets you choose whether a seed uses all campaigns or only `Allies`, `Soviets`, `Epsilon`, or `Foehn` missions.
- Loads setup defaults from `RandomizerLauncher\config\mental_omega_randomizer.yaml` and writes the current seed setup back there whenever a seed is generated.
- Has a `Generate New Seed` button for explicitly starting over while still auto-loading the saved seed after a crash/restart.
- Clears the old launcher log when a new seed is generated, so the visible log belongs to the current seed attempt.
- Shows only currently open missions and completed missions after a seed is generated. Open missions are sorted above completed missions.
- Lets you set campaign difficulty and game speed from the launcher before launching a mission. The launcher writes `GameSpeed`, `Difficulty`, `CampDifficulty`, and `DifficultyModeHuman` into the launch files it can safely edit. If an option INI is suspiciously large or corrupt, it is skipped and the launch values are still written to `spawn.ini`.
- Opens the first 3 missions in the seed, then unlocks 1 more mission whenever you mark a mission complete.
- Tracks reward checks per mission based on the objectives listed in `INI\BattleClient.ini` mission briefings, plus a `Mission Victory` reward for winning the map. Each check can grant a bundle of rewards depending on the `Rewards per objective` setting. Missions with incomplete briefing data fall back to placeholder objective checks until map trigger analysis improves them.
- Shows per-mission reward progress like `3/15` in the mission list. The count is total rewards earned for that mission, not just total objective checks. Hovering an incomplete mission shows only missing rewards and their current hints.
- Access unlocks are placed only once per seed. After a unit is part of the seed's unlocked tech pool, later checks can give repeatable buffs for that unit instead of unlocking the same unit again.
- Adds a second `Current Unlocks` tab that groups earned access rewards and buffs by unit, so IFV/Humvee/GI rewards are easier to inspect.
- Attempts an in-mission objective hook by extracting a generated loose copy of the selected campaign map, adding harmless randomizer marker team actions to objective/victory triggers, and watching `debug\debug.log` for those marker launches.
- Generated randomizer maps currently leave the mission's `[Basic]` ending fields untouched. Victory rewards can still trigger through the hook, but after the score screen the player should return to the launcher manually instead of continuing the vanilla campaign chain.
- Injects already-earned tech unlocks directly into the generated mission map before launch. This avoids loose global `rulesmo.ini` files while still allowing the loaded scenario to see the current randomizer tech tree.
- Locks every randomizer-controlled combat unit in every generated mission map first, then re-opens only units that have actually been earned. The lock list is seeded from `INI\Map Code\No Bases.ini`, so common infantry and vehicles such as GIs, Guardian GIs, Attack Dogs, Field Medics, Rocketeers, Humvees, IFVs, ships, and late-game tech are controlled instead of leaking through map tech.
- Script-critical units such as `GHOST`/Tanya, `SPY`, `SUPR`, `SNIPE`, and `VOLKOV` avoid the hard `TechLevel=11` lock, but still receive the randomizer prerequisite lock plus `BuildLimit=0` so they should not leak into the player's production sidebar.
- Applies unit unlock rewards immediately during the current mission when possible by adding the engine's `Set Tech Level for TechType` trigger action to the same objective/victory trigger that grants the launcher reward. If a check grants several tech unlock rewards, each unlock gets its own trigger action.
- If the victory hook fires, the launcher treats the mission as fully complete and grants any objective rewards whose marker was missed by the log watcher. This prevents a won mission from staying in a partial `Done 10/20` state.
- Earned tech unlocks are forced to `TechLevel=1` in every generated mission map, even if that unit is normally late-campaign tech. If the mission gives you the needed factory/prerequisites, an early mission can become much easier because high-level units such as Battle Fortresses are already unlocked.
- Adds repeatable unit buff rewards with lower priority than access unlocks. Current buff reward types include production speed, cost reduction, movement speed, attack speed/ROF, veteran starts, faster building construction, armor/health, vision, targeting range, guarded weapon tuning, self-healing, cloaking, and sensors. Veteran-start rewards are capped at 1 stack per unit because the available house flag only starts units as veterans, not elites.
- Player-country buff injection is applied directly to the generated mission map when the player country is not shared by AI houses. Temporary `rulesmo.ini` buffs remain disabled by default because loose rules files can break direct mission launch.
- Tracks positive-only rewards in the launcher state. Reward pools are now selected by the mission side, so Allied missions draw Allied rewards, Soviet missions draw Soviet rewards, and so on.
- Backs up the original `spawn.ini` to `RandomizerLauncher\backups\spawn.ini.original.bak` before writing it.
- Deletes generated `rulesmo.ini` files before returning to the normal MO client. The experimental direct-launch `rulesmo.ini` buff path can be enabled with `generation.transient_rulesmo_buffs: true`, but it may trigger launcher/client errors on some installs.

## Current Limitation

Archipelago support is intentionally not active yet. The YAML file is only preparation for a future AP world/options layer. The current randomizer should continue to work fully offline.

The in-mission hook is implemented, and generated maps now receive marker actions for objective triggers and likely victory triggers. If the generated loose map is loaded and the engine logs the marker team creation, objective and victory rewards should unlock automatically. If a victory marker is missed, return to the launcher and press `Mark Complete`.

Tech unlock rewards can apply inside the same running mission because the map trigger can change a TechType's tech level at objective completion.

Most house-supported buff rewards now apply as generated-map country flags when the launcher can isolate the player's country from AI houses. This covers flags such as `CostInfantryMult`, `SpeedUnitsMult`, `BuildTimeInfantryMult`, `BuildTimeBuildingsMult`, `ROF`, and `VeteranInfantry`. If a map shares the player's country with enemy AI houses, the launcher skips unsafe global buffs rather than powering up the enemy.

Guarded per-unit/per-weapon buffs are also generated for units whose use can be isolated safely. These cover values that do not exist as house-level flags, such as damage/range-style weapon tuning, health, sight, sensors, cloaking, and self-healing. When unsafe enemy houses use the same unit, the launcher skips those guarded buffs for that map.

Difficulty and game speed are written to all known launch files, and recent debug logs show the engine reading those startup values. If the visible in-game speed slider later changes, that appears to be Mental Omega/client/map control after startup rather than the launcher failing to write the value.

Crate-style firepower/armor/veterancy effects may be a fallback path for in-mission buffs if the engine lets triggers or spawned crates apply them to the player's units only. This is a backup idea, not the preferred implementation, because direct INI-based rewards are easier to display, persist, and balance once they can be made player-only.

The next investigation step is in `TRIGGER_INVESTIGATION.md`: validating whether the generated loose campaign map is loaded and whether the marker team action appears in `debug.log` as `[LAUNCH] MOR_...`.
