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

Archipelago is not active yet. The YAML structure is intentionally shaped so a future Archipelago world can map options into it without replacing the standalone launcher. All player-facing generation settings are round-tripped through the YAML and copied into seed state so an active run retains its generated behavior.

## Mission Discovery

Missions are read from `INI/BattleClient.ini`. The launcher records:

- mission code
- scenario map
- displayed title
- campaign/faction
- briefing objective lines

The seed can include all campaigns or a single campaign. `All Campaigns` draws from the combined Allied, Soviet, Epsilon, and Foehn reward pool regardless of the current mission side. A selected faction remains strictly faction-only; mixed-mission playability is handled by mission-local safety fallbacks rather than cross-faction rewards.

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

Victory markers are inserted before the existing `Winner is`/`Announce Win` action. Appending after those actions is unreliable because the engine may end the scenario before a later marker action runs. The launcher prefers a true `Winner is` action when a map also contains an earlier `Announce Win` action. It does not change `[Basic] EndOfGame`, because forcing that field caused immediate mission completion in earlier experiments.

After the watcher sees the victory marker, it closes the spawned Syringe/gamemd process tree after a short delay. This prevents the player from continuing into the normal campaign flow. The behavior is enabled by default and can be disabled in the launcher.

## Tech Locking

The randomizer first locks all randomizer-controlled combat tech in the generated map, then reopens only earned units.

This prevents campaign maps from handing out units early through normal mission tech. Refineries and basic base operation tech are intentionally not treated as randomizer combat rewards.

Every unearned controlled TechnoType receives `BuildLimit=0` in addition to the normal TechLevel sentinel. This blocks player production even in campaign contexts that expose high TechLevels, while scripted and preplaced mission units can still exist. Script-critical units avoid a hard TechLevel override and rely on the safer build limit.

Earned access rewards are forced to `TechLevel=1` in generated maps. That means a late-game unit can be available in an early mission if the player has already earned it and the mission provides the necessary production structure/prerequisites.

At launch time the launcher scans the extracted mission map for placed conyards, barracks, factories, air commands, and shipyards, plus numbered production nodes in House-section base plans. The latter is necessary for missions such as Epsilon 07, whose captured Soviet/Chinese base is not listed under `[Structures]`. In a selected-faction campaign it translates earned access roles into equivalents supported by off-faction production: an earned Initiate role can enable a GI or Conscript, an earned Lasher role can enable the corresponding Allied/Soviet/Foehn tank, and the same rule applies to air and naval roles. Production family is derived from the physical building type rather than its pre-handover owner. Each translated rule supplies TechLevel, the real factory prerequisite, native owners, and all active player countries. Always-available matching Engineers remain available, but no combat unit is granted without an earned equivalent. Foehn missions can translate earned roles into both Allied and Soviet technology when those factories are present. `All Campaigns` keeps the unconditional basic safety net because its reward pool already spans all factions.

Single-faction campaigns use explicit cross-faction role groups for mixed-mission buffs. The mapping covers comparable infantry, scouts, specialists, tanks, APCs, artillery, support vehicles, transports, aircraft, naval units, capital ships, and defenses. Once a role peer has earned or fallback access, compatible buffs propagate using each target's own installed stats and weapons. Unique units without a credible counterpart remain independent. `All Campaigns` disables all role sharing because its combined reward pool can provide independent access and buffs across the complete roster.

Maps with multiple player-controlled houses apply country-level buffs to every player house, including mixed-faction combinations such as a primary Allied house and a secondary Soviet house. Unit/weapon safety checks likewise treat all player-controlled houses as allowed users. The `Buff allied helpers` option extends the same treatment to AI-controlled allied houses; it is not required for additional human/player-controlled houses.

Standard mode excludes every Foehn unit, defense, buff target, and Foehn superpower. The Foehn campaign draws Allied and Soviet rewards because those are its normal production factions. Curated Allied/Soviet role peers are emitted as one access reward, and compatible unit buffs share across the same pair. The Unlocks view stores the bundled unit IDs and renders their cameos, access names, and accumulated effects in one shared row. Standard All Campaigns draws Allied, Soviet, and Epsilon rewards. The full Foehn catalogue is exclusive to Chaos.

`Chaos (Experimental)` is orthogonal to mission campaign selection and always enables randomized access/tech locking. Its reward pool spans every faction and keeps role sharing off by default. Players can optionally share unit buffs across the explicit `UNIT_ROLE_EQUIVALENCE_GROUPS`; reward eligibility then accepts an unlocked peer, and map injection expands every earned unit buff across that peer group. At map generation each earned access item receives all player-controlled countries and resets its single campaign prerequisite override. Ares `Prerequisite.List0` plus independent `Prerequisite.List#` alternatives then accept the matching production building from any faction: all four barracks for infantry, factories for vehicles, air commands for aircraft, shipyards for naval units, and Construction Yards for defenses. No foreign production structure is granted. Every playable faction TechnoType receives a map-local faction-band `CameoPriority`; the player's native faction receives the highest band and equal priorities preserve vanilla sorting within each block. Unit cost and speed buffs become direct TechnoType values, armor becomes unit-specific effective durability through Strength, and unsupported per-unit production-speed rewards are removed from the Chaos pool. Explicitly global production and army-wide ROF rewards keep their advertised global behavior.

House-scoped bonuses are routed to the player and enabled allied helpers. Country/house cloning handles production, cost, speed, armor, army-wide fire rate, and veterancy. Unit/weapon rules cannot be house-scoped by the engine, so the launcher applies them only when no enemy uses the affected global type. Registering inherited player-only combat types and splitting TaskForces was tested, but caused fatal incomplete weapon construction and severe in-game slowdown even after complete weapon sections were copied. That runtime-heavy path was removed. Action 36 (`All change House`) triggers whose target is the player are included in the allowed set; debug triggers are excluded.

The Epsilon `MIND` reward target is labeled as Mastermind. Yuri Adept / PsiCorps Trooper mission units use the separate `YURI` section in maps such as `EHUMAN`, so Mastermind buffs do not affect those scripted infantry.

## Reward Generation

Rewards are positive only. Access unlocks have higher priority than buffs so the player is less likely to get stuck without required units.

The buff catalogue is audited against the full installed 3.3.6 faction roster rather than inferred from access rewards. Coverage is currently 52 Allied, 52 Soviet, 47 Epsilon, and 46 Foehn unit sections. Public names do not always match rules IDs (for example Cavalier=`MTNK`, Mirage=`MGTK`, Zephyr=`HOWI`, Catastrophe=`APOC`, SODAR=`MSA`), so the explicit roster mapping is intentional.

`BFRT` and `FORTRESS` are distinct Allied units despite the similar historical naming: `BFRT` is the ground Battle Tortoise, while `FORTRESS` is the Barracuda aircraft. Old saved rewards named `Battle Fortress Access` are canonicalized to `Barracuda Access` and use the Allied airfield prerequisite.

Normal access coverage excludes only economy/base essentials: the four MCVs, four miners, and four Engineer sections. These have no access rewards and are removed from `controlled_tech_ids`, so access randomization cannot lock them. Every remaining roster section is an access item, with faction-wide ownership and a basic production `PrerequisiteOverride`. Defense access/buff coverage is 11 Allied, 11 Soviet, 9 Epsilon, and 12 Foehn structures; power plants, refineries, Construction Yards, production structures, walls, and gates remain outside access randomization.

Access rewards are unique per seed. A unit is unlocked once for the whole seed. Later rewards for that unit become repeatable buffs.

Every access item's faction ownership and basic production `PrerequisiteOverride` are prepared at map load. Unearned access retains its production limit; an earned reward removes that limit and applies TechLevel 1 on the next mission launch. Applying access between missions prevents campaign-native TechLevel actions from bypassing randomizer state.

Current reward categories include:

- unit access
- building-free faction superweapons
- production speed
- cost reduction
- movement speed
- per-unit weapon fire rate
- army-wide fire rate
- building construction speed
- veteran start
- armor/health
- vision
- attack range
- automatic engagement range (`GuardRange`)
- guarded weapon tuning
- self-healing
- cloaking
- sensors

Veteran start is capped at one effective stack per unit because the available house flag starts units as veteran, not elite.

The superweapon family uses trigger action `34` (`Add repeating Superweapon`) rather than action `129`, which only changes the charge of a building-backed power. The installed 3.3.6 indices are Lightning Storm `2`, Tactical Nuke `0`, Psychic Dominator `7`, and Great Tempest `48`. Earned powers are granted from a one-second player-owned map trigger at the start of each future mission. Attaching the action directly to objective triggers would be unsafe because most objective triggers are owned by a different house.

This proves building-free access, but not two independent copies of the same power. A matching constructed building may consolidate with the directly granted house instance. Guaranteed duplicate cameos would require cloned superweapon types and mission-local type registration.

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
- `VeteranBuildings` (the Ares key used for trainable defenses; `VeteranDefenses` is not valid)

These are powerful because they can affect only a country/house, but they are dangerous if the player shares that country with enemies. The launcher checks map houses before applying them. If the player's country is shared with unsafe enemy houses, the buff is skipped instead of making enemies stronger.

The faction-production reward applies all five build-time country multipliers (`Infantry`, `Units`, `Aircraft`, `Buildings`, and `Defenses`). Seed generation reserves every tenth reward for this global upgrade until its three-stack cap, so the much larger complete unit roster cannot crowd it out.

When `Buff allied helpers` is enabled, the launcher attempts to apply safe global helper buffs to allied AI houses too. The safety check follows `ParentCountry` inheritance: an enemy on `UnitedStates2`, for example, is treated as a consumer of `UnitedStates` defaults. If an allied helper needs that shared parent, the launcher assigns the helper a private map-local `MORALLY*` country clone and buffs the clone instead of the parent.

## Guarded Unit And Weapon Buffs

Some desired upgrades cannot be expressed as house flags, especially true per-unit damage/range style changes. The launcher can apply guarded map-local unit/weapon changes when it can prove that unsafe enemy houses do not use that same unit in the selected map. The safety check also follows Mental Omega weapon sharing, so an enemy using a different unit with the same weapon prevents that shared weapon section from being changed.

If unsafe houses use the unit, the launcher logs a skip such as:

```text
Skipped guarded unit/weapon buffs because unsafe houses use those units: GI (...)
```

This protects the player from accidentally powering up enemies.

Starting and TaskForce-created units participate in the same global-type safety audit as newly produced copies.

## Cameo Images

The Current Unlocks view reads each unit's `Image` and `CameoPCX` mapping from the installed `rulesmo.ini` and `artmo.ini` inside the Mental Omega MIX archives. The launcher extracts only needed PCX files, decodes the indexed PCX data to PNG with the Python standard library, and caches the results locally. No Pillow installation or generated replacement artwork is required.

Unlock entries are ordered Allies, Soviets, Epsilon, then Foehn. Shared Chaos role groups use that same faction order within a single side-by-side cameo row. The defensive-building option filters both access and buff rewards and also narrows the set of TechnoTypes whose native map unlock actions are suppressed.

## Known Limits

- Game-speed behavior still needs validation across more campaign maps.
- Victory actions are recognized in all 97 extracted campaign maps. Objective matching remains incomplete: 58 maps have different briefing-objective and hook-action counts, while `SROAD` and `EGODSEND` expose no standard objective-complete action.
- Some allied-helper detection cases need more map data before buffs can safely include every friendly house.
- Perfectly isolated per-unit buffs need an engine-supported house effect or runtime hook; map-local combat-type registration proved too expensive for campaign play.
