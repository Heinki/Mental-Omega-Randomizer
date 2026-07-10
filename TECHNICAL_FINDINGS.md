# Technical Findings

This document explains how the standalone Mental Omega randomizer currently works and what we learned while getting it stable.

## Launch Model

The launcher does not modify the in-game UI. It prepares launch files and starts the game through:

```text
Syringe.exe gamemd.exe -SPAWN -CD -SPEEDCONTROL -LOG
```

The selected mission is written to `spawn.ini` as `Scenario=<map>.MAP`. The launcher writes game speed and difficulty into `spawn.ini` and the regular option INIs where possible:

- `GameSpeed`
- `Difficulty`
- `CampDifficulty`
- `DifficultyModeHuman`

`RA2MD.INI` can become extremely large on some installs. When it is above the safety limit, the launcher patches the small speed/difficulty values in place instead of rewriting the whole file.

`-SPEEDCONTROL` is required for the in-game speed slider to appear during spawned missions. The launcher keeps the flag enabled and writes the selected engine speed value (`0` slowest through `6` fastest) to `spawn.ini` and the option INIs. A previous reversed mapping made `0 - Slowest` write the high end of the range, which could normalize to a fast live speed in spawned campaign launches.

## State And Config

The launcher keeps two kinds of data:

- `config/mental_omega_randomizer.yaml` stores setup defaults, seed options, campaign filter, speed, difficulty, and future Archipelago-shaped options.
- `randomizer_state.json` stores current seed progress, mission order, completed missions, completed objective/victory checks, and earned rewards.

Archipelago is not active yet. The YAML structure is intentionally shaped so a future Archipelago world can map options into it without replacing the standalone launcher.

## Mission Discovery

Missions are read from `INI/BattleClient.ini`. The launcher records:

- mission code
- scenario map
- displayed title
- campaign/faction
- briefing objective lines

The seed can include all campaigns or a single campaign. Reward pools are selected from the campaign side so a Soviet-only seed does not hand out Allied tech unless the selected mission set explicitly needs mixed rewards.

Some missions, especially special cases, do not expose clean objective text. Those fall back to generated objective placeholders until map trigger analysis supplies better checks.

## Generated Maps

Campaign maps live in MIX archives. The launcher extracts a loose generated copy for the selected scenario, patches that copy, launches it, and removes the generated root map afterward.

Generated maps are used for:

- objective/victory marker hooks
- tech locks
- earned tech unlocks
- map-local country/house buffs
- guarded unit and weapon buffs

The launcher avoids patching original MIX archives in place.

## Objective And Victory Hooks

The game does not reliably write a simple "objective completed" state file. The practical solution is active map patching:

1. Find objective-complete and likely victory trigger actions.
2. Add randomizer marker team actions to those triggers.
3. Watch `debug/debug.log` for marker launches.
4. Grant the matching reward check once.

The launcher stores completed check IDs in state, so restarting a mission should not grant the same objective twice.

Victory is treated as its own reward check. If a victory marker fires, the launcher can mark the mission complete and grant any missed objective rewards for that mission.

## Tech Locking

The randomizer first locks all randomizer-controlled combat tech in the generated map, then reopens only earned units.

This prevents campaign maps from handing out units early through normal mission tech. Refineries and basic base operation tech are intentionally not treated as randomizer combat rewards.

Script-critical units such as Tanya, spies, and special heroes avoid the hard `TechLevel=11` lock because missions can break if those units are required for scripted events. They still receive safer build restrictions so they do not normally leak into the sidebar.

Earned access rewards are forced to `TechLevel=1` in generated maps. That means a late-game unit can be available in an early mission if the player has already earned it and the mission provides the necessary production structure/prerequisites.

At launch time the launcher scans the extracted mission map for placed conyards, barracks, factories, air commands, and shipyards, then adds only the matching off-faction basic units for that extra production. Normal Allied/Soviet/Epsilon campaign missions do not receive their own faction's basic units for free. Foehn missions are the exception: their maps can unlock Allied, Soviet, and Foehn basics when that production is actually present, because the campaign integrates those factions. `ESHIP` / Epsilon 04, for example, starts as Epsilon but gets basic Allied infantry, Rocketeers, Humvees, IFVs, and early naval access because the map contains Allied production.

The Epsilon `MIND` reward target is labeled as Mastermind. Yuri Adept / PsiCorps Trooper mission units use the separate `YURI` section in maps such as `EHUMAN`, so Mastermind buffs do not affect those scripted infantry.

## Reward Generation

Rewards are positive only. Access unlocks have higher priority than buffs so the player is less likely to get stuck without required units.

Access rewards are unique per seed. A unit is unlocked once for the whole seed. Later rewards for that unit become repeatable buffs.

Current reward categories include:

- unit access
- production speed
- cost reduction
- movement speed
- attack speed/ROF
- building construction speed
- veteran start
- armor/health
- vision
- targeting range
- guarded weapon tuning
- self-healing
- cloaking
- sensors

Veteran start is capped at one effective stack per unit because the available house flag starts units as veteran, not elite.

## House And Country Buffs

Mental Omega/RA2 has house and country fields that can apply broad multipliers:

- `CostInfantryMult`
- `CostUnitsMult`
- `SpeedInfantryMult`
- `SpeedUnitsMult`
- `BuildTimeInfantryMult`
- `BuildTimeUnitsMult`
- `BuildTimeBuildingsMult`
- `ArmorInfantryMult`
- `ArmorUnitsMult`
- `ROF`
- `VeteranInfantry`
- `VeteranUnits`
- `VeteranAircraft`

These are powerful because they can affect only a country/house, but they are dangerous if the player shares that country with enemies. The launcher checks map houses before applying them. If the player's country is shared with unsafe enemy houses, the buff is skipped instead of making enemies stronger.

When `Buff allied helpers` is enabled, the launcher attempts to apply safe global helper buffs to allied AI houses too. This is map-dependent because missions can contain several allied, neutral, scripted, or enemy houses using overlapping countries.

## Guarded Unit And Weapon Buffs

Some desired upgrades cannot be expressed as house flags, especially true per-unit damage/range style changes. The launcher can apply guarded map-local unit/weapon changes when it can prove that unsafe enemy houses do not use that same unit in the selected map.

If unsafe houses use the unit, the launcher logs a skip such as:

```text
Skipped guarded unit/weapon buffs because unsafe houses use those units: GI (...)
```

This protects the player from accidentally powering up enemies.

Starting units can be harder than newly built units because some buffs are applied through ownership, production, or map rules at load time. If a starting unit misses a buff while newly built copies receive it, that unit type likely needs a cloned player-only variant or a deeper runtime hook.

## Known Limits

- The UI does not yet show unit cameo images.
- Game-speed behavior still needs validation across more campaign maps.
- Some maps do not expose hookable objective/victory triggers cleanly.
- Some allied-helper detection cases need more map data before buffs can safely include every friendly house.
- Player-only copied unit variants remain the likely long-term answer for perfectly isolated per-unit buffs.
