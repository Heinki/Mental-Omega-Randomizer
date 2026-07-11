# Mental Omega Randomizer Launcher

Standalone Windows launcher for a non-Archipelago Mental Omega randomizer.

The launcher starts campaign missions from outside the normal client, generates a seed, tracks mission/objective rewards, locks unearned tech, and applies earned unlocks/buffs through generated map copies.

## Quick Start

For normal players:

1. Download the latest release zip.
2. Put `MentalOmegaRandomizer.exe` in the Mental Omega game folder, next to `MentalOmegaClient.exe`, `Syringe.exe`, and `gamemd.exe`.
3. Run `MentalOmegaRandomizer.exe`.
4. Generate a seed, select an open mission, and launch it from the randomizer.
5. Complete objectives and win the mission. Objective/victory rewards are detected automatically; by default the launcher closes the spawned game after detecting victory.

The manual completion override is available only while `Show Launcher Log` is expanded. Use `Debug: Mark Complete` for development checks; the action is recorded in the persistent launcher log.

The launcher starts missions with speed control enabled and writes the selected game speed before launch. The in-game speed slider should remain available during the mission.

For development, run:

```powershell
python RandomizerLauncher\launcher_gui.py
```

Use the launcher from the Mental Omega game folder.

## Build the EXE Bootstrap

`MentalOmegaRandomizer.exe` is a standalone one-file build. Players only need the EXE in the Mental Omega game folder; Python and the source folder are not required.

From the game folder, run:

```powershell
powershell -ExecutionPolicy Bypass -File RandomizerLauncher\build_exe.ps1
```

That packages the Python launcher and Tkinter into `MentalOmegaRandomizer.exe` in the game folder. Install PyInstaller first with `python -m pip install pyinstaller`.

## Project Layout

- `randomizer_app.py` is the active Tk launcher and game-launch orchestration.
- `randomizer_map.py` contains generated-map patching, tech locks, objective marker helpers, and map-local buff injection.
- `randomizer_cameos.py` extracts installed cameo PCX assets from MIX archives and decodes them for Tkinter.
- `randomizer_paths.py` contains shared launcher/game filesystem paths.
- `randomizer_rewards.py` contains the reward catalogue, reward normalization, and reward display helpers.
- `randomizer_config.py` contains the small YAML-compatible config loader/writer.
- `launcher_gui.py` is only a compatibility entry point that starts `randomizer_app.py`.
- `config\mental_omega_randomizer.yaml` is the standalone setup file. It uses Archipelago-style option names where practical, but does not connect to Archipelago yet.
- `randomizer_state.json` is runtime progress for the current seed and should be treated separately from setup YAML.
- `extracted_maps\`, `generated_maps\`, `backups\`, and `__pycache__\` are runtime artifacts and are ignored by the launcher-local `.gitignore`.

For detailed implementation notes, see `TECHNICAL_FINDINGS.md`.

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
- Loads setup defaults from `RandomizerLauncher\config\mental_omega_randomizer.yaml` in source mode, or `RandomizerLauncherData\config\mental_omega_randomizer.yaml` beside the packaged EXE.
- Has a `Generate New Seed` button for explicitly starting over while still auto-loading the saved seed after a crash/restart.
- Clears the old launcher log when a new seed is generated, so the visible log belongs to the current seed attempt.
- Shows only currently open missions and completed missions after a seed is generated. Open missions are sorted above completed missions.
- Highlights completed missions with a green row and check mark. Clicking any mission-table heading sorts by that column; clicking it again reverses the order.
- Lets you set campaign difficulty and game speed from the launcher before launching a mission. The launcher writes `GameSpeed`, `Difficulty`, `CampDifficulty`, and `DifficultyModeHuman` into the launch files it can safely edit.
- Opens the first 3 missions in the seed, then unlocks 1 more mission whenever you mark a mission complete.
- Tracks reward checks per mission based on the objectives listed in `INI\BattleClient.ini` mission briefings, plus a `Mission Victory` reward for winning the map. Each check can grant a bundle of rewards depending on the `Rewards per objective` setting. Missions with incomplete briefing data fall back to placeholder objective checks until map trigger analysis improves them.
- Shows per-mission reward progress like `3/15` in the mission list. The count is total rewards earned for that mission, not just total objective checks. Hovering an incomplete mission shows only missing rewards and their current hints.
- Access unlocks are placed only once per seed. After a unit is part of the seed's unlocked tech pool, later checks can give repeatable buffs for that unit instead of unlocking the same unit again.
- Adds an `Unlocks` tab that groups earned access rewards and buffs by unit and displays the unit's real in-game cameo. Cameo PCX files are extracted from the installed MIX archives, decoded without an external Python image package, and cached under `RandomizerLauncherData\cameo_cache` in packaged mode.
- Attempts an in-mission objective hook by extracting a generated loose copy of the selected campaign map, adding harmless randomizer marker team actions to objective/victory triggers, and watching `debug\debug.log` for those marker launches.
- Generated randomizer maps leave the mission's `[Basic]` ending fields untouched. The victory marker is inserted immediately before the map's existing terminal win action, and the launcher always closes the spawned game process after a short delay when that marker is detected. This avoids the unsafe `EndOfGame` override that can end a mission immediately.
- Injects already-earned tech unlocks directly into the generated mission map before launch. This avoids loose global `rulesmo.ini` files while still allowing the loaded scenario to see the current randomizer tech tree.
- Locks every randomizer-controlled combat unit in every generated mission map first, then re-opens only units that have actually been earned. The lock list is seeded from `INI\Map Code\No Bases.ini`, so common infantry and vehicles such as GIs, Guardian GIs, Attack Dogs, Field Medics, Rocketeers, Humvees, IFVs, ships, and late-game tech are controlled instead of leaking through map tech.
- All unearned controlled units and defenses receive `BuildLimit=0`; regular units also retain the TechLevel sentinel. Earned access removes both restrictions on the next mission launch. Script-critical units rely on the safer build limit so campaign-created teams and preplaced units remain usable.
- Applies unit unlock rewards immediately during the current mission when possible by adding the engine's `Set Tech Level for TechType` trigger action to the same objective/victory trigger that grants the launcher reward. If a check grants several tech unlock rewards, each unlock gets its own trigger action.
- Access metadata is prepared when the map launches while the unit remains unearned and TechLevel-locked. Consequently, an objective that grants a high-tier item such as Chrono Legionnaire Access can immediately expose it from an ordinary Allied Barracks in a low-tech mission; its original tech-lab prerequisite is not retained.
- If the victory hook fires, the launcher treats the mission as fully complete and grants any objective rewards whose marker was missed by the log watcher. This prevents a won mission from staying in a partial `Done 10/20` state.
- Earned tech unlocks are forced to `TechLevel=1` in every generated mission map, even if that unit is normally late-campaign tech. If the mission gives you the needed factory/prerequisites, an early mission can become much easier because high-level units such as Battle Tortoises or Barracudas are already unlocked.
- Adds repeatable unit buff rewards with lower priority than access unlocks. Current buff reward types include production speed, cost reduction, movement speed, unit fire rate, army-wide fire rate, veteran starts, faction-wide production, armor/health, vision, attack range, auto-engagement range, guarded weapon tuning, self-healing, cloaking, and sensors. The faction-production reward is deliberately placed every tenth reward until its three-stack cap; each stack speeds infantry, vehicle, aircraft, building, and defense queues for the player and enabled safe allied helpers. Veteran-start rewards are capped at 1 stack per unit because the available house flag only starts units as veterans, not elites.
- `All Campaigns` uses the combined four-faction reward pool, keeps every unit buff independent, and retains a basic mixed-production safety net. Selecting one campaign keeps rewards strictly on that faction and translates earned access into equivalent units for off-faction barracks, factories, air commands, and shipyards found in mixed missions. Equivalent infantry, vehicles/tanks, aircraft, naval units, transports, support units, capital ships, and defenses inherit compatible buffs; genuinely unique units remain independent. Only matching Engineers are granted without an earned combat-role equivalent.
- Mixed-faction maps apply buffs to every player-controlled house automatically, so an Allied player house and a Soviet player-controlled ally receive their corresponding role and country effects. `Buff allied helpers` additionally includes AI-controlled allied houses.
- Standard mode never generates Foehn units, defenses, or Foehn superpowers. Standard Foehn campaign seeds use Allied and Soviet rewards, matching the production used throughout that campaign. Standard All Campaigns uses Allied, Soviet, and Epsilon rewards. The complete Foehn reward catalogue is exclusive to Chaos.
- `Chaos (Experimental)` draws independent access and buff rewards from all four factions regardless of the selected mission campaign. It makes every faction's barracks, War Factory, air command, and shipyard constructible from the player Construction Yard, adapts earned unit ownership to all player-controlled countries, and routes foreign infantry, vehicles, ships, and defenses through the current player faction's normal production sidebar. Aircraft retain a valid aircraft factory when the player faction has no dedicated one. Buffs stay attached only to their named unit. Cost and speed are injected directly on that unit; armor becomes unit-specific effective durability. Unsupported unit-specific production-speed rewards are omitted, while the explicitly global Faction Production and Army-wide Fire Rate rewards remain global.
- Optionally adds one unique building-free superweapon reward per faction: Lightning Storm, Tactical Nuke, Psychic Dominator, and Great Tempest. Earned powers are restored by a player-owned map-start trigger in future missions using the engine's repeating-superweapon action. This does not require the normal superweapon building. Whether constructing the matching building creates a second independent cameo or shares the granted instance still needs runtime validation, so the setting is marked experimental.
- Buff targets cover the complete installed 3.3.6 playable roster: 52 Allied, 52 Soviet, 47 Epsilon, and 46 Foehn unit sections, including subfaction units, heroes, aircraft, naval units, miners, transports, and MCVs. Buff-only seeds do not lock unit access and can draw positive rewards for every one of these units. Seed generation spreads buffs across units with the fewest rewards first, so a sufficiently large reward plan covers the full roster before heavily stacking a small subset.
- Normal access randomization covers every non-essential roster unit: 49 Allied, 49 Soviet, 44 Epsilon, and 43 Foehn unit sections. MCVs, miners, and all four Engineer sections never become access rewards and are explicitly excluded from randomizer locks. Earned units are opened to every subfaction of their side and use their earliest matching production facility, so a high-tech or subfaction unit can be used when a later-launched mission provides that basic facility.
- Defense access and buffs cover 11 Allied, 11 Soviet, 9 Epsilon, and 12 Foehn defenses. This includes basic anti-ground/anti-air towers and advanced or subfaction defenses. Defense rewards use the Construction Yard as their access prerequisite; defense buffs omit movement-speed upgrades and safely support construction time, cost, armor, health, vision, guarded weapon tuning, repair, cloak, sensors, attack range, and auto-engagement range where applicable. Veteran rewards are generated only for the 20 combat defenses that Mental Omega explicitly marks `Trainable=yes`, and use Ares' `VeteranBuildings` country flag.
- Player-country buff injection is applied directly to the generated mission map when the player country is not shared by AI houses. Temporary `rulesmo.ini` buffs remain disabled by default because loose rules files can break direct mission launch.
- Country safety follows `ParentCountry` inheritance as well as exact country names. When an allied helper's country is also an enemy ancestor, the helper is moved to a private map-local `MORALLY*` country clone before receiving house-scoped buffs, leaving the enemy on the unmodified parent.
- Tracks positive-only rewards in the launcher state. Reward pools are now selected by the mission side, so Allied missions draw Allied rewards, Soviet missions draw Soviet rewards, and so on.
- Backs up the original `spawn.ini` under the launcher's writable data directory before writing it.
- Deletes generated `rulesmo.ini` files before returning to the normal MO client. The experimental direct-launch `rulesmo.ini` buff path can be enabled with `generation.transient_rulesmo_buffs: true`, but it may trigger launcher/client errors on some installs.

## Current Limitation

Archipelago support is intentionally not active yet. The YAML file is only preparation for a future AP world/options layer. The current randomizer should continue to work fully offline.

The in-mission hook is implemented, and generated maps receive marker actions for objective and victory triggers. All 97 campaign maps extracted from the installed 3.3.6 data expose a recognized victory action and pass the generated pre-win marker insertion audit.

Tech unlock rewards can apply inside the same running mission because the map trigger can change a TechType's tech level at objective completion.

Most house-supported buff rewards now apply as generated-map country flags when the launcher can isolate the player's country from AI houses. This covers flags such as `CostInfantryMult`, `SpeedUnitsMult`, `BuildTimeInfantryMult`, `BuildTimeBuildingsMult`, `ROF`, and `VeteranInfantry`. If a map shares the player's country with enemy AI houses, the launcher skips unsafe global buffs rather than powering up the enemy.

Guarded per-unit/per-weapon buffs are also generated for units whose use can be isolated safely. These cover values that do not exist as house-level flags, such as damage/range-style weapon tuning, health, sight, sensors, cloaking, and self-healing. When unsafe enemy houses use the same unit, the launcher skips those guarded buffs for that map.

Difficulty and game speed are written to the known launch files. The launcher also uses `-SPEEDCONTROL`, which is required for the in-game speed slider to appear during spawned missions. Game-speed behavior still needs validation across more campaign maps.

Crate-style firepower/armor/veterancy effects may be a fallback path for in-mission buffs if the engine lets triggers or spawned crates apply them to the player's units only. This is a backup idea, not the preferred implementation, because direct INI-based rewards are easier to display, persist, and balance once they can be made player-only.

The next hook investigation is objective matching. In the installed campaign set, 58 of 97 maps have a different number of briefing objectives and hookable objective-complete actions, and `SROAD`/`EGODSEND` expose no standard objective-complete action. Those missions remain playable because manual objective/mission completion is available, but reliable mission-specific trigger mapping is the largest remaining automation gap.
