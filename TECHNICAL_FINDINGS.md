# Mental Omega Randomizer Technical Reference

This document is the authoritative implementation reference. Player-facing option semantics are intentionally kept in [README_RANDOMIZER.md](README_RANDOMIZER.md#settings-reference) so they are not duplicated here.

## Runtime Architecture

| Component | Responsibility |
|---|---|
| `launcher_gui.py` | Entry point and packaged `--self-check` |
| `randomizer/application/` | Tk composition plus focused state, reward, progression, launch, and Unlocks controllers |
| `randomizer/config/` | Player YAML persistence, static JSON loading, schema validation, and tuning |
| `randomizer/core/` | Paths, atomic storage, diagnostics, version, and collection primitives |
| `randomizer/launch/` | Spawn/option INI serialization and oversized-file patching |
| `randomizer/maps/` | Ordered map pipeline, INI mechanics, ownership, hooks, clone isolation, buffs, helper AI, settings, and powers |
| `randomizer/missions/` | BattleClient catalogue, house policy, production access, mission exceptions, and Tier 1 starters |
| `randomizer/progression/` | Pure Grid topology and persisted-state normalization |
| `randomizer/rewards/` | Reward definitions, canonical display, deterministic planning, owned roster, and weapon snapshot |
| `randomizer/ui/` | Widget construction, palettes, Grid rendering, tooltips, cameos, and custom presentation |

Every Python module is kept below 1,000 lines. Stable facades
(`randomizer.maps.rules`, `randomizer.missions.safety`,
`randomizer.rewards.catalogue`, and `randomizer.ui.builder`) isolate callers
from responsibility-based implementation splits.

The launcher does not patch the original campaign MIX archives. It extracts and caches source maps, writes a temporary loose root map for the selected scenario, and removes only files carrying the randomizer hook marker.

## Launch Model

Missions start through:

```text
Syringe.exe gamemd.exe -SPAWN -CD -SPEEDCONTROL -LOG
```

`spawn.ini` receives the scenario, game speed, `Difficulty`, `CampDifficulty`, and human/computer difficulty values. The launcher also updates existing normal option INIs where safe, but does not create a missing `RA2MO.ini` or `RA2MD.INI`. `RA2MD.INI` may be extremely large, so values are patched in place above the size threshold instead of rewriting the complete file. Routine INI snapshots are not retained because they were never consumed or restored; the selected launch settings are intentionally persistent.

`-LOG` produces `debug/debug.log`, which is the communication channel for objective/victory markers. `-SPEEDCONTROL` keeps the spawned-game speed control available.

The packaged launcher uses PyInstaller one-file mode so the release contains only `MentalOmegaRandomizer.exe`. PyInstaller embeds Python, Tcl/Tk, native extensions, and `mo-logo-puzzle-icon.ico`, then expands them to its temporary `_MEI*` directory at startup. The same icon is used for the executable shell icon and loaded through Tk `iconbitmap` for the running window; source runs read it directly from the repository. That extraction cannot be removed while retaining a self-contained PyInstaller/Tk executable, so unnecessary imports are kept out of the bundle and diagnostics use the base `logging.FileHandler` rather than `logging.handlers` and its unused mail/network stack. Persistent configuration and caches remain under `RandomizerLauncherData`; they are player data rather than application runtime files.

## Configuration and State

The launcher separates defaults from active progress:

| Data | Contents | Mutation rule |
|---|---|---|
| `configs/*.json` and `configs/rewards/*.json` | Editable mission overrides, faction/UI/unit data, clone policy, buff/assistance tuning, access, superweapon, and aid-power definitions | Read on process startup; never rewritten by launcher |
| `configs/player/mental_omega_randomizer.yaml` | Next-seed defaults, launch settings, and reserved Archipelago fields | Updated from current UI choices |
| `randomizer_state.json` | Active seed, frozen reward settings, mission order, optional grid/node state, checks, assigned rewards, completed checks/missions, and earned rewards | Updated only by seed generation or progress events |

This split is important for a future Archipelago client: option values generate a slot/seed once, while received locations/items update progress. The current `archipelago.*` keys are placeholders and have no network behavior.

Player YAML keeps its file format but now lives with other configuration under
`configs/player/` in source and `RandomizerLauncherData/configs/player/` when
packaged. On first load, an old `config/mental_omega_randomizer.yaml` is moved
to the new path when no new-path file exists. State paths remain unchanged.
Writes use a complete sibling temporary file followed by same-directory atomic
replacement, preventing a crash or power loss from leaving partially written
YAML or JSON.

Source runs load static data directly from `configs`. One-file builds generate and bundle a SHA-256 manifest with every static JSON and `Randomizer*.ini`, excluding player YAML. Frozen startup verifies the bundle, then synchronizes visible `RandomizerLauncherData/configs`: a pre-manifest installation gets one recoverable `*.pre-bundle-sync-backup` migration to the complete current set; later updates replace only files whose live hash still matches the prior bundled hash, preserving local edits. This prevents valid but stale external catalogues from hiding newly packaged units or powers. Restart is required after editing. Every JSON document uses a validated `schema_version` and required-section envelope. See [configs/README.md](configs/README.md).

## Mission Discovery and Seed Construction

Mission code, map filename, title, side, and briefing objective text are read from `INI/BattleClient.ini`. `MISSION_BUILD_CLASSIFICATIONS` assigns every installed catalogue code to `base_build`, `true_no_build`, or `no_build_production`; [MISSION_CLASSIFICATION.md](MISSION_CLASSIFICATION.md) is the player-readable 97-entry list. Classification uses reviewed gameplay behavior and community correction rather than initial map ownership alone; Allied 01 is explicitly a base-build mission. A mission with briefing objectives receives one check per objective plus a separate `victory` check. When no objective text exists, the launcher creates three placeholder objective checks plus victory.

Seed construction is deterministic for a seed string:

1. Filter eligible missions by campaign and independently include/exclude true-no-build and production-no-build missions. Disabling both leaves only base-build missions.
2. Classic takes the requested prefix of the filtered installed catalogue without consuming mission-order RNG. Randomized modes protect the progression opening with stage 1-6 missions, then fill every remaining slot from one unrestricted shuffle of the eligible pool. Mission List protects its first five entries; Grid Mode protects topology cells at or one move from its start nodes. Optional no-build priority fills these protected positions from the enabled no-build categories in stage order before normal low-level selection.
3. In Grid Mode, map that order onto the corner-trimmed grid and persist each node's coordinates and initial state.
4. Allocate `objective count + 1 victory` checks per mission.
5. Allocate 1–30 reward slots to every check.
6. Build the complete reward plan with a random stream derived from `<seed>:seed-rewards`.
7. Store every check and assigned reward in state before play begins.

Grid progression is derived from completed mission codes and then written back as explicit `locked`, `unlocked`, or `completed` node state. Launch history adds the UI-only in-progress presentation before objective markers arrive. `completing_unlocks` provides the side-effect-free current unlock query used by mission details and victory logging. Completing the designated endgoal marks the Grid Mode run complete, changes every unfinished node to `unlocked`, and marks every still-pending check reward as `released`. Released rewards participate in earned tech/buffs immediately without setting their mission checks or victory checks to complete; later optional completion clears the release marker without awarding a duplicate. Existing saves whose endgoal was already completed receive the same release during migration. The launcher writes both the visible victory message and a structured `randomizer_victory_achieved` event for future Archipelago status integration. Classic starts with one mission and Mission List starts with three; both open one additional ordered entry per victory and complete at their configured mission count. Grid dimensions are derived solely from the mission goal: balanced exact factors are preferred, then the densest balanced partial rectangle receives connected corner trimming. Layout version 3 migrates older manually sized boards without losing completed mission codes.

The Tk grid renderer keys its persistent tile-widget cache by a topology signature of dimensions, mission codes, and coordinates. A topology change rebuilds the board; ordinary selection reconfigures only the old/new tile containers, while reward and victory changes update cached tile labels and colors in place. Optional locked-mission privacy keeps topology visible but renders locked cached tiles as neutral `?` nodes, blocks their selection, removes goal/faction/status clues, and suppresses predicted neighbor names in Mission Details. Available nodes hide the banner widget rather than displaying a redundant label, and the body receives symmetric padding so the selection border remains visible along the top. Each tile uses nested border containers: the goal can retain its outer gold border while the inner container displays the normal light-blue selection border. This avoids window destruction, geometry churn, and visible selection flicker.

The Settings notebook page owns a canvas viewport and an inner controls frame. It now contains the Seed & Run form as well as every advanced setting; no generation controls remain above the side notebook. Canvas/content configure events synchronize the inner width and scroll region; mouse-wheel scrolling is accepted only while Settings is selected and the pointer is inside that viewport. The main mission/details split uses uniform 13:6 weights, large enough for four 80-pixel Unlocks cameos at normal size while giving the board more space. Unlocks reflows from four columns to two or three when the side viewport narrows, retaining full-size cameos without clipping. **Hide Details** expands the mission viewport across both columns and reveals a separate two-button action row below it; showing Details removes that duplicate row. Side Launch and recovery controls remain above Mission Details/Unlocks without a permanent recovery caption. Dark mode switches ttk/Tk palettes immediately and persists outside seed state. The canonical ttk `TLabelframe` style colors group interiors; a custom state-aware indicator replaces Clam's X with a white tick on an enabled gray box while disabled checks remain visibly distinct. Privacy settings are immediate: Mission Details renders pending rewards as `?????` but reveals completed/released checks, while locked-grid privacy hides undiscovered tiles and names.

The installed campaign counts are 30 Allied, 30 Soviet, 30 Epsilon, and 7 Foehn missions. The reviewed build split is 51 base-build, 27 true-no-build, and 19 production-no-build missions. By faction, true-no-build counts are Allied 7, Soviet 5, Epsilon 12, Foehn 3; production-no-build counts are Allied 5, Soviet 6, Epsilon 7, Foehn 1. Randomized mixed-campaign construction caps Foehn proportionally against the currently eligible pool, while single-campaign Foehn seeds retain every eligible mission. This cap is applied during both the protected opening and unrestricted remainder; Classic instead preserves the literal filtered catalogue prefix and records its actual faction counts. Mission List protects its first five entries. Grid Mode computes its protected cells from topology: one-start grids protect `(0,0)` and its existing orthogonal neighbors; two-start grids protect `(1,0)`, `(0,1)`, and every existing orthogonal neighbor of either start, normally six cells. Low-level missions are assigned to those cells before unrestricted missions fill the remainder. Foehn 02/03/04/06 and Foehn Op are excluded from protected openings while alternatives exist; only Foehn 01/05 receive early eligibility. A narrow Foehn-only pool falls back to late maps when the protected opening is larger than those two missions.

Access rewards are unique by reward name. Mission List seed planning walks reward slots linearly, prioritizes access, attempts a buff every fifth slot, and prefers a global buff every tenth slot while its stack cap permits. Grid Mode instead reserves slot zero of every topology-protected opening mission for a unit-access item when available, then shuffles all remaining `(mission, slot)` pairs across the entire board before running the same access/buff draw. This gives the easy start neighborhood a small guaranteed roster while preventing row-major mission storage from consuming all unique access in the top rows. A 100-seed audit of 97-cell one-start and two-start grids found unit access in every row, including the bottom, while Mission List remained front-loaded. Unit buffs normally require prior planned access; buff-only seeds relax that requirement. Buff selection spreads upgrades across the least-buffed eligible units before stacking them further. Production, cost, armor, health, range, sight, self-healing, veterancy, cloak, sensors, movement, and special-building capacity all have finite useful limits. Once one reward reaches its limit it leaves the candidate set, so the same slot is assigned to another eligible reward when possible. Unique-unit `BuildLimit +1` remains repeatable and adds one live slot per stack. The 243 single-type access rewards normalize their names from `BUFF_TARGETS`, correcting old/generic labels such as `Battlecruiser Access` to the installed `Trident Battleship Access`; legacy names alias to the normalized reward. Reward names are canonical keys, so visually identical faction copies still need distinct labels: `LUNR` is `Soviet Cosmonaut` and `LUNRE` is `Epsilon Cosmonaut`, preventing one access or buff definition from canonicalizing into the other. Harbinger Tower and EMP Control Station are intentionally absent because their powers are building-free. `generation.include_special_rewards` defaults on and filters all 19 marked Special access targets, three marked powers, and their propagated buff rewards as one seed-frozen policy. When off, marked TechnoTypes also leave the randomizer lock set; unmarked special economy buildings and ordinary aid powers remain controlled by their existing category switches.

The mission-table reward fraction counts reward items, not check objects. Mission Details and mission hover text read stored check reward arrays and display each `reward_display_name`, so a 10-item check shows all ten assignments. The immediate privacy preference replaces pending names with `?????`; completed or Grid-released checks reveal their assigned rewards, and Unlocks continues to reveal all earned rewards. Buff display names use `buff_effect_lines` instead of internal catalogue codenames: `Attack Sub Logistics` is presented as `Typhoon Attack Sub: Cost 20% cheaper`. Compact per-reward listings omit redundant stack suffixes; Unlocks combines duplicate rewards and shows their real cumulative stack count. Stored internal names remain stable for seed compatibility. Legacy items that canonicalize to `retired_reward` stay stored but are omitted from Unlocks instead of filling its Reward list with disabled entries.

Unlocks now has Allies, Soviets, Epsilon, and Foehn cameo dashboards plus the legacy searchable Summary. Its view model indexes serialized check rewards by affected TechnoType or superweapon without consuming RNG or changing state. Unlocked icons remain normal; pending rewards in any currently playable mission are green; assigned later rewards are gray; items absent from the generated seed are black. Hover text aggregates earned buff stacks and names public mission/check sources. Green-icon hover temporarily outlines matching playable Grid tiles; Mission List/Classic instead add a green bold-underlined Treeview tag to matching rows. Leaving the icon or hiding Details restores ordinary styling. Widget and mission-tree tooltips share one active-tooltip owner, hide on replacement/unmap/destruction, and cancel pending callbacks; stale hover cards cannot survive dashboard refreshes or overlap another tooltip. `hide_locked_grid_missions` deliberately converts green candidates to ordinary locked presentation and suppresses their source names and tile highlights, preventing the catalogue from bypassing hidden-node privacy. Search controls are children of Summary only; the outer Unlocks header contains only the wrapped state legend. Shared Chaos/Foehn role buffs index every affected equivalent icon. Dashboard cameos use a Tk-native 4:3 zoom/subsample scale from 60×48 to 80×64, retaining the dependency-free decoder pipeline. Summary lists Standard Tier 1 starters as abstract mission-equivalent roles, while Chaos and Shop embed their fixed concrete cameos. Legacy concrete Standard starter saves normalize back to roles. Standard always renders native Foehn unit icons unavailable and filters old serialized Foehn unit rewards at launch; Chaos retains them.

Unlocks now also has a Neutral dashboard. Standard production, cost, and armor
rewards appear there because their generated CountryType multipliers affect
whole production categories, not only the unit named by the reward. Chaos
non-global cost/armor rewards stay on faction unit cards because they use
direct clones. Veterancy also stays unit-specific because `Veteran*` contains
an exact TechnoType list. Each buff routes to one dashboard card only.

Mission Details always shows each check's stored briefing-objective hint beside
its rewards. Completion and Grid reward release change only the status label;
they do not hide the objective text. Existing saves receive current hints from
the normal objective-summary synchronization without a schema migration.

## Generated Map Pipeline

Every mission launch starts from the cached extracted source, not the previous generated result. `prepare_hooked_map` performs the following operations in order:

1. Build the global controlled-tech lock set for the active seed.
2. Add mission-required Standard equivalents or Chaos all-faction production alternatives.
3. Merge already-earned access rules and remove their launcher locks.
4. Apply safe map-local country/house buffs to player-controlled houses and, when enabled, the reviewed allied-helper allowlist. Compatible helper placements/TaskForce slots use buffed clones while native IDs stay buildable as dynamic-queue fallbacks; timing, scripts, and triggers remain intact. Bounded parallel variants add earned clones.
5. Apply guarded direct unit/weapon buffs where no unsafe enemy uses the same global type.
6. Add map-start triggers for already-earned building-free superweapons.
7. Remove native action `106` tech unlocks that would reopen still-unearned controlled technology.
8. Discover objective/victory action lists and add marker teams.
9. Run the native unlock filter again after action-list edits.
10. Write a diagnostic copy under `generated_maps` and a loose scenario map in the game root.

The root copy begins with `HOOKED_MAP_MARKER`. A pre-existing non-randomizer loose map is backed up before replacement. Cleanup scans root `*.MAP` files and removes only those carrying this marker; extracted and diagnostic copies remain cached.

## Objective and Victory Hooks

### Why a map hook is required

The engine does not expose reliable objective state in a simple external save file. The launcher therefore attaches harmless marker-team creation to existing map action lists and observes the resulting team launch name in `debug/debug.log`.

The hook is an observer. It does not replace the mission objective logic or decide when the player wins.

### Check-to-action discovery

Objective action lists are recognized by these action signatures:

| Action | Recognized parameter | Meaning used by the launcher |
|---:|---|---|
| `19` | `ObjectiveComplete` | Text/UI objective completion |
| `21` | `EVA_ObjectiveComplete` | EVA objective-complete notification |
| `11` | `Mission:ObjC` | Mission objective-complete variable |

An action list containing terminal victory codes `1` or `67` is excluded from ordinary objective candidates. Every objective check and candidate action ID is first paired in its encountered ordinal position with `zip`; completed checks are filtered only after that pairing. This preserves Objective 2 -> action 2 after a restart where Objective 1 is already complete instead of shifting Objective 2 onto action 1. Extra briefing checks or extra actions cannot be matched automatically without mission-specific metadata.

Victory candidates are ordered deliberately:

1. Action lists containing code `1` (`Winner is`).
2. Action lists containing code `67` (`Announce Win`).
3. Trigger names containing `[win]`, `/win`, `mission victory`, or `mission successful`.

The first candidate is used for the victory check. Preferring a real winner action prevents an earlier announcement from completing the randomizer mission prematurely.

### Marker construction

Every mapped incomplete check receives unique map-local IDs:

```text
TeamType:  RND00001
TaskForce: RNT00001
Script:    RNS00001
Marker:    MOR_<MISSION>_O1  or  MOR_<MISSION>_VIC
```

The TaskForce is empty. The ScriptType uses a harmless guard action. The TeamType is owned by the active player house and carries the marker in its name. The original action list receives action code `4` to create that marker team.

Objective markers are appended to their action list. Victory markers are inserted immediately before the first terminal code in the set `1`, `67`, or `69`; appending after a winner action is unreliable because the scenario may end before later actions execute. A name-only fallback with no recognized terminal code retains append behavior.

Map action lines must remain at most `511` UTF-8 bytes because the game truncates
the parser input at byte `512`. Hook TeamType IDs remain the proven eight-character
`RND00001` form; shorter IDs loaded but action `4` did not create the marker team
in live Bleed Red testing. Both append and pre-terminal insertion reject any
result above the limit. When a full objective list uses a standalone global
event (`11`, global set, or `61`, all objects of type destroyed), the launcher
adds a separate marker-only trigger and mirrors the native trigger's enable and
disable actions. Golden Gate's native `01000108` therefore remains its original
`493` bytes instead of becoming the crashing `516` bytes, while its objective
still produces an immediate marker. Unsupported full-list hooks are skipped;
victory reconciliation remains the fallback.

The launcher deliberately leaves `[Basic] EndOfGame` unchanged. Earlier attempts to force that field could end a mission immediately on load.

### Log watcher and exactly-once behavior

At process launch, the active hook stores:

- mission code and scenario;
- marker-to-check mapping;
- an empty `seen` set;
- the current end offset of `debug/debug.log`;
- the spawned process and generated root-map path.

Starting at the current log offset prevents markers from an earlier launch being replayed. Every 1500 ms the watcher reads only appended text. If the log is truncated, it resets the offset to zero. A line containing `[LAUNCH] <marker>`—or the marker text as a compatibility fallback—calls `unlock_mission_check` once. Both the in-memory `seen` set and the persisted check `unlocked` flag make duplicate log lines harmless.

Objective completion unlocks that check's stored rewards. Rewards modify launcher state immediately but their technology/buffs are injected when a later mission map is generated; the running map is not rewritten in memory.

### Victory semantics

Victory is a separate configured reward check. When its marker is seen:

1. The mission code is added to `completed_missions`.
2. The victory check is unlocked.
3. Any still-locked objective checks in that mission are unlocked and their stored rewards are granted.
4. State is saved, the mission list refreshes, and the next mission slot opens.
5. After 2500 ms, the launcher closes the spawned Syringe/gamemd process tree to prevent normal campaign continuation.

In Grid Mode, victory on the designated endgoal additionally records Randomizer victory, releases every pending reward, and unlocks every unfinished grid node. Release state is separate from check completion, preventing both false mission victories and duplicate rewards during optional cleanup.

The close callback verifies that the process and hook are still current, then uses `taskkill /PID <pid> /T /F` with a direct terminate fallback. If the game has already exited, no close is attempted.

Granting missed objective checks on victory is intentional. The objective/action mapping is incomplete on some maps, and a legitimate win must not leave the mission in a partially rewarded state.

### Watcher shutdown and failure behavior

Polling continues while the spawned process is alive. On exit the launcher records marker counts, clears the active process/hook, removes generated root maps, and removes any launcher-generated loose `rulesmo.ini` file.

If map extraction or hook preparation throws, the launcher logs the traceback, cleans generated root maps, and can still start the mission without automatic objective detection. If no victory candidate exists, the mission remains playable but automatic victory progress is unavailable; the hidden debug completion control is the recovery path.

An installed Mental Omega 3.3.6 audit recognized a victory action on all 97 extracted campaign maps. Objective matching is less complete: 58 maps had a different number of briefing objectives and hookable objective actions, while `SROAD` and `EGODSEND` exposed no standard objective-complete action. This is why victory reconciliation remains required.

## Technology Locking and Access

With access randomization enabled, every controlled unearned combat TechnoType receives `BuildLimit=0`. Regular units also receive a high TechLevel sentinel. Script-critical types use only the safer build limit so preplaced units and campaign TeamTypes can still exist.

MCVs, miners, Engineers, amphibious transports (Voyager, Zubr, Mandjet, and Watercat), refineries, core production, and other base-operation essentials are outside the access pool. Generated maps force each transport to TechLevel 1 behind its matching faction shipyard so transport-dependent missions cannot be progression-locked. Chaos accepts any faction shipyard. Earned access removes launcher locks and is forced to TechLevel 1 in future generated maps.

Before launch, the mission safety layer scans both placed structures and numbered House-section base plans for Construction Yards, barracks, factories, air commands, and shipyards. House plans matter for captured bases that are not initially present under `[Structures]`, such as Epsilon 07.

### Standard mixed-faction access

All Campaigns applies exact per-faction access. When the player captures foreign production, the mission rule adapts ownership only for earned TechnoType IDs belonging to that physical production family. A discovered foreign Construction Yard or player/scripted MCV prepares every matching production category so later barracks, factories, airfields, and shipyards still expose only earned IDs. It never substitutes role peers and has no unconditional basic-unit safety roster. Player clones retain the `Owner` countries of every concrete prerequisite factory in addition to the exact player country's production ancestry; `RequiredHouses` remains limited to the player/helper countries. This is necessary because a captured foreign factory must share an `Owner` entry with the produced type even though the current House is separately permitted. Moonlight exposed the failure clearly: `MORPGACPIL` and `MORPGAPOST` had valid `NACNST` alternative prerequisites but only `Owner=PsiCorps,MORPLAYER`, so the Soviet Yard showed its native mission roster instead of the earned clones. Every generated map prepares exactly one complete installed-identity Engineer clone. Standard prefers the authoritative player faction when that production family is usable, otherwise the first usable family; Chaos selects the first usable family. Authored player TaskForce Engineers remain native story units and are not promoted into additional buildable clones. Every native Engineer keeps its authored `ForbiddenHouses` unchanged and receives the hidden exact-player-House negative prerequisite, which suppresses factory cameos without preventing scripted Team creation. This removes Moonlight's native Soviet Engineer duplicate while its Borillo/Engineer and Engineer-drop teams remain valid. If no production is statically visible, the player faction is prepared behind the generic `BARRACKS` prerequisite so scripted bases work without exposing a premature cameo. Amphibious transports remain explicit progression essentials; optional Tier 1 starters are injected independently and do not relax exact access.

Build-only player clones preserve authored player TaskForces, so their native identities use `FactoryOwners.Forbidden` instead of the hidden negative prerequisite. That filter evaluates the factory's initial country, including when scripts later hand the building to another house. `player_production_houses` records reviewed handover sources; Red Dawn includes `Europeans House`, preventing native GI and Guardian GI cameos beside `MORPE1` and `MORPGGI` after its European barracks becomes player-usable.

A selected single-faction campaign translates earned curated roles to foreign production families that the mission gives the player. The generated rule includes the physical factory prerequisite, native ownership, and active player countries. No combat role is granted without an earned equivalent; the single faction-appropriate Engineer remains available.

Map-local unknown buildings declaring `Factory=InfantryType` are special barracks. Every exact unlocked infantry ID receives that building as an independent prerequisite alternative, regardless of faction; the normal faction barracks remains another alternative. This covers Fallen Ashes `CAMINE`. A map that places `MWF`/`NAFIST`, including through a listed TaskForce, receives Stalin's Fist support: Standard adds `NAFIST` only to exact unlocked vehicle IDs matching the current Soviet or Epsilon player family. These special rules include explicit Tier 1 starters but never unearned access.

Foehn Standard draws bundled Allied/Soviet access peers. Standard All Campaigns draws Allied, Soviet, and Epsilon rewards. Full Foehn reward definitions are reserved for Chaos.

The optional Tier 1 starter roster models five roles: ground infantry, anti-air infantry, ground tank, anti-air tank, and basic aircraft. Standard seed-selects one concrete identity for every role and every usable faction family on isolated `<seed>:starting-tier-one-standard:<family>` streams. An all-faction Standard seed therefore stores exactly 15 identities: five Allied, five Soviet, and five Epsilon. `_preferred_standard_starter_family` selects exactly one player/scripted production family for each launch map, and only that family's five selected identities receive rules. All entries retain exact Barracks/War Factory/Airfield prerequisites; a missing category stays dormant until its scripted factory appears. Capturable enemy factories never add another starter family. Legacy Standard role-marker or oversized subtype saves deterministically normalize to the same five-per-family selection at runtime. Ground tank candidates include Bulldog/Cavalier/Kappa, Rhino/Qilin/Jaguar, and Lasher/Mantis/Opus; anti-air tank candidates include Stryker/Archon/Tsurugi, Tigr/Halftrack, and Gatling Tank. Aircraft candidates include Stormchild/Harrier/Black Eagle, Foxtrot, and Dybbuk-Attacker. One candidate fills each slot; siblings are not granted. Chaos and Shop preserve separate exact five-unit total seeded rosters.

The independent Tier 1 defense starter persists abstract ground and anti-air roles in Standard and resolves them per launch map. Allied `GAPILL`/`NASAM`, Soviet `NALASR`/`NAFLAK`, and Epsilon `YAGGUN` remain behind only their native Yard; Epsilon legitimately collapses both roles to one identity. Legacy Standard saves containing concrete defenses normalize back to the shared role marker. Chaos and Shop instead retain concrete selections; Chaos gives its two defenses Ares alternatives for all four Construction Yards. Advanced Pool exclusions override starter injection and reward-pool suppression. Eligible starter defense access rewards are removed while defense buffs remain eligible immediately.

Standard starter regressions verify that `ESHIP` maps an Epsilon player to Allied starters through its captured Allied base, `AGHOST` maps an Allied campaign mission to Epsilon starters through Epsilon production, scripted-opening base missions fall back to current player family, and Foehn-only `FREMNANT` uses Allied/Soviet operating production while excluding Epsilon/native Foehn starters.

### Chaos access

Chaos always enables controlled-tech locking and draws all four factions. Each exact earned unit receives player-country ownership and Ares alternative prerequisite lists for every matching production family. Detected special barracks are added for all earned infantry and `NAFIST` for all earned vehicles. The map's provided barracks/factory/airfield/shipyard/conyard can therefore produce the earned unit without granting foreign production structures or any additional unit access when another factory is captured.

Zero Signal's capturable Pacific Barracks is an explicit player-production
source. Native `ENFO`, `GHOST`, and `JUMPJET` now exclude that factory while
locked, preventing Siege Cadre, Navy SEAL, and Rocketeer access from leaking on
capture. Its four starting Archons remain native mission objects so nearby
Siege Cadres retain the authored automatic-entry behavior; an earned Archon
still uses the separate build-only player clone.

Chaos Tier 1 starters use a separate deterministic stream, `<seed>:starting-tier-one`, so mission order and normal reward RNG calls remain unchanged. Faction order is shuffled once across the four guaranteed ground roles, producing exactly one Allied, Soviet, Epsilon, and Foehn unit; roles with subfaction variants make an additional deterministic choice. A fifth seeded role selects one Allied/Soviet/Epsilon aircraft. Shop uses the same five-role count with its own isolated streams. Both modes expose exactly five starters total, never every subtype.

Chaos Tier 1 defenses use independent deterministic stream `<seed>:starting-tier-one-defenses`. Faction order is shuffled once; ground and anti-air roles take distinct families. Exactly two saved defenses accept all four Yard families, while exclusions still win. Earned Chaos defenses and special buildings retain those same four Yard alternatives and every corresponding factory-owner country while `RequiredHouses` stays limited to the player and allowed helpers. This is required for captured or scripted foreign MCVs: the engine checks both the prerequisite BuildingType and an `Owner` overlap with its deployed Construction Yard. FKILL's Standard-only Soviet Yard repair no longer narrows Chaos defense clones to `NACNST`.

Phobos `CameoPriority` bands keep production cameos in contiguous faction groups with the current player faction first. Each unit also receives a unique rank from the committed faction roster, preventing map-local clone registration order from shuffling Infantry/Units/Defenses inside a faction. Buildable Chaos `MORP...` clones copy that priority after their installed identity is restored.

## Buff Safety Model

### Failed-mission assistance

When enabled for a seed, every mission has an independent retry stack counter in `randomizer_state.json`. Closing the spawned game without a detected victory counts as a failed attempt. A subsequent `MapClass::Init_Clear` event while the same game process remains active counts as an in-game restart/reload; the initial scenario load is ignored. Assistance earned from an in-game restart is available on the next launcher-driven mission launch because the already-running game has already loaded its map.

Each stack uses normal house/category multipliers for production time x`0.85`, cost x`0.80`, and incoming armor damage x`0.90`. RA2/YR implements CountryType `Armor*Mult` as a divisor on incoming damage, so launch output writes the reciprocal (`1/0.9` per stack), not the reward model's received-damage multiplier. Writing `0.9` makes units weaker; the former capped `0.091` output reduced effective durability to 9.1% and could cancel large direct `Strength` rewards. Direct clone armor still divides `Strength` by the reward multiplier and was already correct. Capped exponential effects clamp their final useful stack to the exact remaining value rather than retaining an overshooting raw power: production reaches multiplier `0.2` at 10 stacks (80% shorter), cost reaches `0` at 24 (100% cheaper), armor reaches engine divisor `11` at 23 (+1000% effective durability), and health reaches `11` at 18 (+1000%). Range reaches +50 at 100 stacks, sight reaches +100 at 100, and self-healing reaches 50% effective maximum Strength per tick at 50. Planning, UI aggregation, retry assistance, direct clones, country fields, and guarded legacy launch paths share these limits. This prevents old states from underflowing or overflowing capped fields; later reward slots are redistributed among remaining eligible candidates. Movement speed is always a guarded direct TechnoType value: x`1.10` until the unit reaches its reviewed ceiling (infantry `8`, VehicleTypes/naval `12`, AircraftTypes `30`). Faster authored identities retain their base speed without further acceleration. Accessible unit types also receive guarded weapon-damage x`1.15` and per-unit weapon fire delay x`0.90` without these restored stat caps. Mission Details and the compact Retry Assistance block in Unlocks show cumulative effects in player-facing language such as "higher", "faster", "cheaper", and "damage taken lower" rather than raw signed multipliers.

For randomized-access seeds, that roster is the union of earned access, always-available faction essentials, mission access rules, player-owned placed units, and units in player-owned scripted TaskForces. This lets the first mission receive help before any rewards have been earned. When access randomization is disabled, the normal roster of every player-controlled/current mission faction is included as well. All-Campaign earned cross-faction access remains eligible. Completing a mission deletes its counter and cached roster; counters belonging to other missions remain untouched.

The assistance is written only into the generated copy of the selected mission map. Campaign trigger owners are country IDs, so player and helper houses remain on their original countries. Country/category multipliers are applied only when every active house in that country family belongs to the assisted coalition; otherwise that country-level part is skipped and logged. With `buff_allied_helpers`, reviewed helper houses receive the same safe country assistance. Health uses global TechnoType fields and damage/range use global WeaponType fields, so those bonuses pass through clone isolation or the map-usage guard. No global INI or MIX archive is changed.

Campaign maps can define reusable TeamTypes with `House=Neutral` and assign their real runtime owner in `[AITriggerTypes]`. Unit-usage safety resolves that AI-trigger owner before classifying a global TechnoType or WeaponType as player or non-player. A placeholder Neutral owner is discarded only when an AI-trigger override exists and the same TeamType is not also created directly by a map action. Enemy-owned, helper-owned, and genuinely Neutral teams remain unsafe for raw player buffs.

### House and country effects

House-supported rewards use map-local country data for category cost, category armor, and veteran lists. Player-controlled houses always participate. Production and construction deliberately bypass country `BuildTime*Mult`: those values parse but did not change live campaign build timing. Every earned production reward instead writes `BuildTimeMultiplier` to the isolated owned infantry, vehicle/naval, aircraft, defense, or special-building clone in both Standard and Chaos. Global `MOR_BUILDINGS` rewards expand over the currently buildable clone set and combine with exact-unit production stacks under the normal ten-stack cap. Country production fields are suppressed to prevent double application. All movement speed likewise bypasses `SpeedInfantryMult`, `SpeedUnitsMult`, and `SpeedAircraftMult`; isolated player/helper clones enforce per-unit hard ceilings without accelerating native scripted teams. `buff_allied_helpers` also targets reviewed helper countries when their country family is not shared with a denied house; clone IDs replace exact originals in affected helper veteran lists. The removed army-wide ROF reward is canonicalized to working per-unit cloned-weapon fire-rate rewards.

Veterancy uses `VeteranInfantry`, `VeteranUnits`, `VeteranAircraft`, and `VeteranBuildings`. Trainable defenses such as the Allied Grand Cannon must use `VeteranBuildings`; `VeteranDefenses` is not an engine key. Empty cinematic/neutral placeholder houses that inherit a player country do not block that country's rewards when they own no placed or scripted TechnoTypes, are allied to the assisted coalition, and have no scripted hostile transition.

If an allied helper uses a country inherited by unsafe enemy houses, the country-level reward is skipped for that helper. Parent-country relationships are included in safety analysis. The house is not moved to a synthetic country because doing that disconnects triggers owned by its original country.

Unit-access ownership is narrowed at map launch to the current player countries plus safely isolated configured helper countries. Factory eligibility can follow `ParentCountry`, so clone/access `Owner` includes the complete parent chain while `RequiredHouses` retains only the concrete allowed countries. This fixes custom player countries in `EBLOOD` (`PC-Player` -> `PsiCorps`), `SAWAKE` (`PlayerEscort` -> `USSR`), and `SRAVEN` (`Player` -> `USSR`) without granting their clones to hostile houses that share the parent. A helper country is omitted from country-scoped buffs when a denied active house shares or inherits it. The house itself is never reassigned because that breaks country-owned mission triggers. Unsafe country/category and direct unit/weapon effects remain skipped.

### Direct unit and weapon effects

Health, sight, ammo, healing, cloak, sensors, weapon damage, weapon reload, and weapon range are TechnoType/WeaponType fields and therefore global within the map. The launcher applies them only when placed units and TaskForce usage show no unsafe enemy using the same unit. The bundled 3.3.6 weapon registry covers the complete playable roster and traces shared weapons through campaign-only/AI-only users, spawned aircraft and missiles, and projectile airburst/shrapnel payloads.

Damage changes target the real damaging stage instead of blindly changing launcher control weapons whose `Damage=1` is not the impact damage. Carrier and anti-sub payload weapons are followed to their spawned aircraft; V3, Dreadnought, and Akula missiles use their actual `[General]` normal/elite damage fields. Integer damage always increases by at least one. Weapons already at the engine minimum `ROF=1` are excluded from direct reload changes instead of displaying an upgrade that cannot reduce the value. Enemy direct-weapon scaling also rejects every `Spawner=yes` controller instead of cloning it: its ROF does not control the spawn interval, and replacing these live spawn-manager weapons is unsafe. Earthrise exposed the missing enemy-side guard when the generated map contained six such controller clones and later failed at the engine's spawn-manager exception address. Enemy weapon clones merge installed values with map-local overrides while preserving the exact INI key spelling. Vanishing Point overrides `AAGattling` with `Warhead=SP_GattAAWH`; passing that override through the lowercase analysis view emitted `warhead`, which Ares did not recognize and caused fatal construction of `MORE1YTNKAAGattling`. Akula is the sole reviewed spawned-missile range exception: every earned `CruiseLauncher` range increase adds the same amount to `[CMISL] GuardRange`, preserving the installed seven-cell pursuit margin. Native enemy Akulas keep their unchanged 23-cell launcher range, so the shared missile envelope does not extend enemy acquisition or firing range.

Capability eligibility is also derived from the installed 3.3.6 TechnoTypes. New pools omit self-healing for already-self-healing types, cloak for types with normal/staged/stop/attach-effect cloak, and sensors for types with `Sensors=yes` or `SensorArray=yes`. Utility-only targets (spies/infiltrators, engineers, scanner-only types, and explicit `NotAWeapon` types) cannot receive damage, reload, or range rewards. Functional nondamaging support weapons remain eligible when their reload/range fields are real gameplay controls. Reviewed redundant or ineffective per-type combinations are configured in `configs/rewards/buff_exceptions.json` under `excluded_buff_type_ids`; `all` excludes a type completely, while buff-type keys exclude only that effect. The separate document lets frozen upgrades install this policy without overwriting an existing editable unit policy. Mobile `Trainable=no` types cannot receive Veteran Training; legacy Engineer, Spy, Suppressor, and equivalent invalid veteran rewards canonicalize to the same unit's Armor Plating reward. Drakuv, Ruiner, and Harbinger are removed entirely from production access/buff pools because they are aid payloads. Mobile units already at or above their category ceiling do not receive no-op Mobility rewards. Each remaining Mobility reward has a finite per-unit stack limit calculated from base speed and the x`1.10` factor; planning stops at that limit and legacy excess stacks clamp at launch. Exactly 16 installed trainable hero/unique types with `BuildLimit=1` receive the repeatable Command Capacity reward. Structure Capacity uses a distinct `building_limit` eligibility marker and is generated only for the four configured special economy buildings. Legacy hero Structure Capacity rewards canonicalize to the same hero's valid Command Capacity reward.

Ares self-healing supports every TechnoType, including BuildingTypes, but its default amount is only one hitpoint per normal repair interval. Repair Systems writes `SelfHealing.Amount` equal to 1% of effective maximum strength per earned stack for mobile units and defenses, capped at 50%, while retaining the normal repair interval. The former army-wide fire-rate reward wrote `ROF` onto CountryType sections, but installed Mental Omega uses that multiplier only on difficulty sections and live testing showed no unit effect. New seeds omit it. Legacy Rapid Fire rewards canonicalize to the same target's working cloned-weapon `reload` reward. Retry assistance now applies firing speed through those guarded cloned WeaponTypes instead of a country field.

The former `guard_range` / Targeting Package reward was removed. `GuardRange` increases autonomous acquisition distance rather than weapon range and can pull units out of position into unsafe engagements. New seeds cannot generate it, and existing stored Targeting Package rewards canonicalize to the same unit's Recon Package vision reward.

Unsafe raw type changes are never written onto an enemy/helper-shared original. Mandatory narrow player clones isolate supported direct TechnoType and WeaponType effects, including buildable defenses. Unsupported indirect/spawned paths remain skipped and logged. Movement ceilings exposed a build-only clone bookkeeping regression: the clone reported every buff as handled even though mission-authored placements/TaskForces deliberately stayed native, suppressing their health, sight, capability, and weapon buffs. Build-only or otherwise native-preserved mission identities now report only speed as handled. Their authored/default Speed remains unchanged, while every other ownership-safe unit/weapon effect continues through the guarded native pass. A later Hammer to Fall regression showed blanket TaskForce preservation was too broad for direct starts: action-referenced enemy/shared GI teams may stay native while exact UnitedStates placements safely use a locked buffed reference clone. Sources with ambiguous exact Event/Action references remain excluded. All four Engineer identities are stricter: campaign-authored placements, TaskForces, Events, and Actions always stay native so vehicle boarding, `CanDrive`, and exact mission semantics use the engine-reviewed identity. The duplicate native cameo is hidden only by the exact-House negative prerequisite, never a player `ForbiddenHouses` entry. Newly trained Engineers use independent buffed `MORP*` clones that forcibly restore `Engineer=yes`, `CanDrive=yes`, `GroupAs=Engineers`, `IFVMode=1`, size/physical size 1, and normal locomotion. That pass applies only its computed unhandled `direct_types`; testing the original count set would accidentally reapply handled speed whenever any non-speed effect remained.

An experimental Phobos/Ares runtime-House AttachEffect pulse was tested and removed. Live testing showed that its owner filter did not reliably isolate the player and could buff enemy objects. Action `34` also exposed each hidden pulse as a continuously recharging default Mental Omega cameo despite `SW.ShowCameo=false`. The launcher therefore creates no `MORBuff*` superweapons, weapons, or warheads.

The all-campaign validation matrix processes all 97 installed missions, the normal roster for every player-controlled faction, optional allied helpers, scripted transfers, placed units, and AI-trigger TaskForces. It produced 9,239 verified higher damage fields plus 91 verified spawned-missile damage paths, with no partial modifier sets, unchanged numeric upgrades, or enemy leaks. At the unit/mission level, 3,744 of 4,607 damage-capable combinations applied and 863 were safely rejected because an enemy on that mission shared every relevant global type. Those enemy-shared combinations remain intentional safe skips.

The first map-local combat-clone experiment registered many copied units, full copied weapons, and split TaskForces. It produced fatal incomplete weapon construction and severe live-game slowdown, so that broad full-copy path remains removed. Country copies also remain removed because they detach campaign triggers from reassigned houses.

Owned player TechnoTypes are mandatory launch behavior, not a setting and not seed-frozen. Six `configs/Randomizer*.ini` files contain fixed `MORP<source>` definitions split into infantry, heroes, vehicles, ships, aircraft, and defenses/special buildings. Mapper-reviewed `InfantryList.txt` supplies infantry identity values; remaining definitions are a generated Mental Omega 3.3.6 snapshot. Mission generation registers only currently relevant owned types, overlays mission production gates, then applies rewards to those owned sections. Native TechnoTypes retain campaign `Owner`, `RequiredHouses`, `TechLevel`, `BuildLimit`, and positive prerequisites. Current player countries can still be appended to native `ForbiddenHouses`; every mapped original also receives `Prerequisite.Negative=MORPOriginalGate`. One hidden immune/passable gate is statically owned by each exact player House. Ares applies this negative prerequisite to ordinary, captured-factory, alternate-prerequisite, and reverse-engineered production, while native AI houses and scripted TeamTypes do not own the gate. This preserves native IDs for campaign AI, triggers, and dynamic country-roster requests while making the MORP identity the only player cameo. Map-only variants retain guarded complete-copy fallback. First live clone run proved Ares `$Inherits` unsafe: `[MORWSCARHALFTRACKGUNX]` contained only buff overrides, so WeaponType construction failed because inherited `Projectile=InvisibleWork` was unavailable. Static owned definitions and private buffed WeaponTypes therefore contain complete values with `$Inherits` removed. Any type whose source omits `Image=` receives `Image=<original ID>` because engine otherwise seeks nonexistent `MORP...` art.

The original native-cameo guard exempted every script-referenced TaskForce
type. That was too broad: enemy/helper-only Terror Drones, Halftracks, Demo
Trucks, Dogs, and Engineers leaked through transferred or captured factories
beside the isolated player clone. A story source now retains that exemption
only when its concrete placed/TaskForce usage intersects a player-controlled
runtime house. Reviewed future-player and exact-trigger exclusions remain
native. Their player production is still blocked through the exact-House
negative-prerequisite gate. This does not change starting/Tier-1 clone access
or stolen/captured production access to the earned clone.

Campaign player-unit clones additionally layer player-owned map-authored identity and combat fields onto the static owned template before earned buffs. This applies to heroes and ordinary units: maps deliberately strengthen, weaken, rearm, disable, or attach mission effects to both. Production and ownership gates remain isolated. This fixes missions whose authored hero is stronger than the installed roster baseline: Recharger defines Volkov at `1350` health and Chitz at `1650`, while the old static clone started them at `600` and `500`. Engineer clones still remove unsafe cached Chrono identity mutations, but retain safe authored mission health. Disabled `NotA*` weapon placeholders remain literal and are never cloned as real weapons. A maximum-pressure audit covered 239 player-authored modified units across 87 missions with zero clone below or inconsistent with its authored map baseline; Recharger reached `2700`/`3300` under that audit seed. Build-only unlocks do not copy hostile map-authored boss/target overrides: Thread of Dread's marked Chinese Centurion retains its native `Armor=special`, while a player-built Centurion starts from the ordinary installed `cntr` armor before rewards. Native scripted phases that cannot safely clone instead map the earned source-hero buffs onto their exact identities (`AWITHER:ATANY`, `SJUGGER:CYCOM`, `ETOTAL:ASSN`, `EMIGDAL:LIBRA2/LIBRA4`, and `FEMPIRE:YUNRU`). Focused isolation audits found no TechnoType or WeaponType combat edits on Recharger's enemy GI/Navy SEAL or Juggernaut's enemy Flak Trooper/Archer identities.

Defense cloak, health, sight, sensors, healing, and weapon damage/range/reload fields cannot be house-scoped; modifying the original gives every enemy copy the buff. Every buildable buffed defense therefore receives a registered standalone `BuildingType` clone and cloned weapons. Player and opted-in helper placements use it. Exact numbered helper House base plans use the same clone. Clone eligibility is gated by concrete `Owner`/`RequiredHouses` country IDs, so hostile `ParentCountry` descendants do not justify skipping helper plans; that former country-buff safety test left the Europeans/Pacific bases in `AWITHER` unbuffed. Enemy placements, plans, TechnoTypes, and WeaponTypes remain original; native helper fallback ownership stays separate. Country `VeteranBuildings` entries follow the clone. The helper-off path rewrites none of the helper references. The current 42-map pressure pass verified 106 configured helpers, 804 friendly base-plan and 887 friendly placement rewrites while preserving 2,309 enemy plans and 6,321 enemy placements.

TechnoType IDs embedded in Events/Actions must follow the cloned mission object. Trigger ownership alone is insufficient: `EMIGDAL` creates the player's `LIBRA` from a `PsiCorps` TaskForce but its mission-failure event is owned by `UnitedStates`. Leaving that event on `LIBRA` while the team creates `MORPLIBRA` makes the mission fail immediately. The same invariant applies to locked, reference-only map aliases: `SNOISE` watches `RAVA`, `RAVA2`, and `RAVA3`, so its three placed/TaskForce Drakuv identities and Event 61 references must all become their matching `MORP...` IDs. TaskForce replacement therefore covers every friendly clone, not only sidebar-buildable sources; enemy consumers remain native and shared TaskForces are split by their resolved runtime houses. If every resolved map consumer of a cloned source type belongs to the player/opted-in helpers, all exact Event/Action references follow the clone regardless of story-trigger owner. Shared types still change only in player/helper-owned trigger lists. Event 61 is an exact TechnoType destroyed/nonexistent test; when such a shared type has friendly and denied consumers but its event belongs to an outside story house, the launcher keeps that map's type native and lets the normal usage guard skip its unsafe direct buff. A second mission-local identity policy covers objects with non-trigger constraints: Mermaid Tanya (`TANY`), Hammer to Fall's Tanya/Stallion (`TANY`/`SHAD`), Power Hunger's Morales/Borillo/Desolators (`MORALES`/`BOREK`/map-local `DRIL`/map-local `INIT`), Kill the Messenger's Yunru (`YUNRU`), and Reality Check's `LIBRA` plus `LIBRA1`-`LIBRA8` remain native. Hammer to Fall pins Tanya to the mission-authored Strength `320` instead of the installed default `200`; earned Tanya buffs layer directly onto that native identity so its TaskForce and loss event stay aligned. Power Hunger reuses installed `DRIL`/`INIT` IDs for unrelated authored units; rewriting its Latin fallback TaskForce to `MORPINIT` separated the passengers from the native Burillo house/type chain. Both types now retain authored USSR/Latin/Special ownership and every transport TaskForce remains native. Morales direct buffs are calculated from map Strength `450` and Speed `10`, not lower installed bases. Reality Check's native-only policy also preserves its `Convert.Script=LIBRA6/7/8` sequence and Event 61 loss IDs; reward buffs are applied directly to every native phase and its map-local primary weapon. Exclusions are enforced at the final clone-candidate boundary because access, veterancy, helper, and unlimited-cap candidates can otherwise recreate a clone after direct buff counts were filtered. A 13-map integration audit kept all ambiguous map/type cases native. A separate 97-map reference audit checked 1,003 exact references: 262 globally friendly and 325 friendly-owner references were rewritten, while 416 shared/enemy references stayed original; all rewritten action lines remained within 511 bytes. The follow-up hero-objective audit covered all 97 maps: 85 maps contained 707 Event 61 lists with 863 exact references. It checked all 84 cloned loss references, 14 matching friendly placements, and 85 matching friendly TaskForce slots with zero identity mismatches or over-limit action/event lines.

Epsilon 14 (`EHUEHUE`) is a deliberate native exception: loss Event
`01000171` watches exact `NACLON`. Rewriting the event to `MORPNACLON` while
the mission still owns native Cloning Vats satisfies Event 61 immediately and
causes the opening defeat. `NACLON` therefore appears in both the mission's
native clone exclusions and native trigger-reference allowlist. Fatal Impact
(`SFATAL`) likewise keeps starting/scripted `VOLKOV` and `SVOLKOV` identities;
its native-variant rule applies all earned Volkov direct and primary-weapon
buffs from each map-authored baseline. The portable Perun template overrides
the campaign's `BuildTimeMultiplier=121` with `1`, otherwise the valid
factory/prerequisite clone appears permanently unbuildable.

Trigger ownership also cannot prove that a shared/native object should follow a player clone. Some player-owned triggers watch an initially foreign object that is captured later or manipulate a native scripted object. `EPEACE` Event `01000151` must keep `LCRF` so taking the authored Voyager advances Peacekeeper; `ESING` Event `01000647` must keep `DRIL` so the surviving authored Driller does not satisfy a false all-destroyed loss; `EBREED` Event `01000352` and Action `01000381` must keep `DISK` and `KAOS` so Memory Dealer's Disk/Bloatick control and ending chain complete. `MISSION_NATIVE_TRIGGER_REFERENCE_IDS` supplies these narrow exemptions while player-buildable/buffed clones remain available. Focused generated-map checks confirmed all four native lines remain byte-equivalent to source.

The first successful isolation tests kept enemy Conscripts and Soviet 12 Flak Troopers unbuffed. `FBEYOND` exposed two BuildLimit traps: `-1` made a clone one-build-only, while `0` prevented an Autocreate team from assembling. Those lock/one-build values are removed, but installed positive live-unit caps are preserved exactly (`1` for Centurion, Libra, Volkov, and the other unique units; `2` for Orcinus). The optional `generation.unlimited_hero_units` setting removes the cap only from the isolated player/selected-helper clone of the 16 trainable capped hero/unique identities. The mutually exclusive Command Capacity reward adds one to that clone per earned stack. Script-only positive caps and capped defenses never enter either feature; all enemy/native originals keep their authored caps. Additive helper pools exclude every positively capped type so an extra team cannot stall on its count. A buildable clone takes its cap from the installed identity, not a campaign section that reuses the same ID for a different hero: `SHAND [SUPR]` is capped Reznov, while the earned Suppressor clone remains normally unlimited. Native mission aliases and helper fallbacks retain their map-authored caps. Shared outside-owned Event 61 types now receive a build-only clone when the player can produce them; native mission placements, teams, events, and actions remain unchanged. This lets Fatal Impact expose a fully buffed normal `MORPVOLKOV` without redirecting any of its native enemy `VOLKOV` destruction checks. Non-buildable ambiguous types still remain native and forgo unsafe direct buffs. A 97-map maximum-buff regression created 14 build-only ambiguous clones with zero missing clone sections or native-reference rewrites. Later `FBEYOND`, `AWITHER`, and `SHAND` testing exposed the deeper fault: campaign AI can request native country-roster IDs outside map TaskForces. Hiding those originals or rewriting only known TaskForces leaves the factory waiting forever while structure production continues. Native helper source IDs now regain their installed/map TechLevel, prerequisites, and explicit concrete helper ownership. They are hidden from the human through positive ownership, while the player's buffed copy remains the sole player cameo.

`FBEYOND` uses seven friendly AI houses. `FoehnNavy House` is the separate naval helper. The unselected base is controlled by the difficulty-specific `China2/3/4 House` or `Pacific2/3/4 House`; these six houses must be allies, not denied enemies. `Chinese House` and `Pacific House` remain the hostile main houses. `UnitedStates` controls orchestration triggers. `SellMCV House` is also friendly scripting infrastructure and inherits `Guild1`; listing it as an enemy made the country-safety guard skip all player `Guild1` multipliers, including `ROF` and veteran production. It is now in the ally allowlist.

The failed helper experiment substituted complete rosters and leaked foreign units into Standard player sidebars. The corrected design is surgical. Existing helper TeamType timing, ScriptTypes, triggers, and composition counts stay intact, but compatible placement/TaskForce unit slots use buffed clones. Native source IDs simultaneously regain native TechLevel, prerequisites, and explicit helper ownership for dynamic country-roster requests outside TaskForces. Mission production discovery considers only player-controlled factories or proven full-force transfers, never enemy/helper factories. Standard All-Campaign launch access is narrowed to the authoritative `[Basic] Player` faction before rules, clones, helper pools, or action-106 unlocks are generated. Secondary `PlayerControl=yes` scripting houses do not broaden the current mission's base reward faction. Proven foreign player production can still add only exact earned IDs through mission access rules. This prevents `SHAND` from turning its map-local `[SUPR]` hero alias into an installed Suppressor clone and prevents helper template pooling from adding Brute/Libra prerequisites to Soviet production. A catalogue contradiction that labeled Epsilon `SQD` as Soviet was also corrected.

Three base-build missions use object-level ownership changes that are not full-house Action 36 transfers. Production discovery therefore has a separate, narrow mission policy: `EBREED` reads PsiCorps2's captured `YACNST`, `EBLOOD` reads PC-Base's `YABRCK`/`YAWEAP` in addition to the already detected PC-AI transfer, and `SRAVEN` reads the Guild3 structures tagged `01000314` that Objective 2 changes to the Player house (`NACNST`, `NAHAND`, `NAWEAP`, and `NAAIR`). These source houses never enter helper/buff allowlists, so initially hostile or scripted owners remain unbuffed. Generated access remains required by the authoritative concrete player country, while `Owner` also carries its production parent. The 97-map regression checked 12,223 buildable clones and 23,272 Standard/Chaos access rules with zero missing concrete or parent ownership gates.

Chaos is unit-specific for production/cost/speed/armor. Cost, speed, and armor already had direct clone values, but production was previously omitted after category-country generation was suppressed in unit-specific mode. Production is now clone-direct in every mode, while Standard still prefers safe country/category multipliers for cost and armor. Clones receive cumulative `BuildTimeMultiplier`, clamped to an exact 80% relative reduction at 10 stacks; the generated-launch log reports the concrete multiplier values and clone counts by category. Currently usable always-available Engineers and amphibious transports join the buildable clone set when buffed; otherwise their production reward has no owned identity on which to write the multiplier. Miners are handled separately and always register all four owned identities behind exact faction factory+refinery pairs; these must use normal `Prerequisite` AND lists. `PrerequisiteOverride` is OR across entries, and the obsolete `YAREFN` ID produced a live Phobos parse warning; Epsilon's refinery is `YARIREFN`. This avoids the old broad `ALWAYS_AVAILABLE_UNIT_IDS` path that also cloned mission-critical MCVs. Movement speed always uses an isolated direct clone. Singularity showed that Speed `10` lets Malver become stuck on campaign slopes, establishing infantry ceiling `8`. Kill the Messenger showed category-wide vehicle acceleration could let tanks block scripted SMCV deployment, establishing VehicleTypes/naval ceiling `12`; AircraftTypes use conservative ceiling `30`. Faster authored types retain their Speed but are never increased by Mobility rewards. If the player's country shares a parent with denied houses, native-faction isolated clones receive direct cost/armor fallback values for earned rewards and retry assistance. Speed and production already follow that direct path globally. The fallback remains active with buffed helpers enabled: safe helper countries do not make the shared player country safe. This preserves player effects without changing enemy originals or expanding fallback cloning through role-equivalent foreign factions.

Player production and additive helper teams share one standalone earned clone rather than registering a second helper TechnoType. Its owners include only the player and selected helper countries, and helper production receives alternative prerequisites copied from the native slot. Source `FactoryOwners` and negative prerequisite restrictions are removed because they can leave a foreign helper team unfilled. Standard additive substitutions match the source TaskForce slot's faction; Chaos alone permits cross-faction substitutions. Native helper TaskForces use their restored originals. Native fallback ownership is tracked separately from buffed-clone ownership: when `buff_allied_helpers` is off, helper TaskForces, clone owners, and helper Veteran lists remain native/unbuffed while the queue fallback stays operational. No `MORAI...` IDs appear.

Parallel unlock variants remain bounded to eight teams per helper country and eight earned types per production class. A map-authored Autocreate TeamType without an AITrigger receives only a parallel TeamType/TaskForce and reuses action 13; native AITrigger conditions are copied when present. Added TaskForces discard every untouched template member, because one hidden campaign-only member can stall the whole team. Custom helper countries follow `ParentCountry` chains during discovery, but clone isolation uses concrete country IDs without a conflicting parent `ForbiddenHouses`. The final maximum-pressure audit of all 42 configured-helper maps started from 543 source TaskForces and produced 786 compatible native/parallel helper TaskForces. It verified 1,026 helper clone references and 273 native source targets: every compatible helper consumer used a repeatable, correctly owned level-1 clone, every native fallback remained unlimited, every produced clone retained veterancy, and no duplicate player identity or veteran overflow existed.

Country veteran lists require exact TechnoType IDs. `VeteranUnits=ABRM` does not affect the player clone; exact originals are replaced for countries that actually produce it. `Trainable=no` originals and clones are never added. On a shared player country such as `SHAND`'s USSR, earned veteran targets force standalone player clones even when veterancy is their only buff. Appending every `MORP...` clone once made `VeteranUnits` reach 755 characters and parse as `[country]VeteranUnits=J`; merely bounding values to 480 bytes then silently omitted late earned rewards in maximum Chaos seeds. Earned veteran player clones therefore receive deterministic collision-checked two-character map-local IDs, while non-veteran clones retain stable `MORP...` IDs. `VOLKOV` retains `MORPVOLKOV` because Fatal Impact names it in a reviewed tunnel-passenger rule. All final lists remain capped at 480 UTF-8 bytes. A full active veteran pool produced 49 infantry, 96 vehicle/naval, 7 aircraft, and 20 building clone IDs with no omitted rewards; the largest field was 287 bytes.

Mission-created units have a second veterancy path. Reinforcement actions `7`, `80`, and `107` force the referenced TeamType's `VeteranLevel` and can override a correct country `Veteran*` entry with the authored rookie value `1`. Launch generation now raises only player/opted-in-helper reinforcement TeamTypes whose every TaskForce member has earned Veteran Training to `VeteranLevel=2`; mixed, unearned, enemy, and already-elite teams remain authored. Build-only production clones also keep the safe native source ID after the clone in country veteran lists because their mission placements and scripted TaskForces deliberately remain native. Reviewed native mission variants accept either the earned source or its isolated clone as proof of the earlier country-safety decision, then add their exact scripted IDs. A focused Juggernaut launch with only Volkov access/veterancy changed the native `CYCOM` reinforcement TeamType from rookie to veteran and retained `VOLKOV,CYCOM` in USSR's infantry list. The full 97-map launch path generated every mission with no new clone, reference, ownership, or rule failure.

Trainable defenses may switch to `ElitePrimary` or separate `EliteWeapon1..N` gattling stages after promotion. Defense clones now discover every direct installed/map weapon reference and clone applicable weapons with the same earned damage, range, and reload stacks. All 20 trainable defenses were audited: 17 weapon-buffable types produced 58 isolated rookie/veteran/elite references; Avalon, Shrike Nest, and Psychic Tower expose no weapon-stat reward types, while their unit-stat buffs and exact veterancy still apply. Chaos buildable clones must also retain `PrerequisiteOverride=none` when `Prerequisite.Lists` exists. Stripping that sentinel reactivated installed faction prerequisites, hiding cross-faction towers in Shipwrecked despite correct access rules.

## Building-Free Powers

Installed `ChronoliftSpecial` and dependent `PostliftSpecial` both use `RechargeTime=1`. Reward configuration now states both values explicitly, preventing drift without changing installed balance.

Earned offensive, secondary, and support/aid powers use action `34` (`Add repeating Superweapon`) from player-owned map-start triggers. Eligible entries include player-facing strikes, buffs, scouting, delivery/reinforcement powers, and five useful mine/grid spawners converted from automatic self-targeting to manual map targeting. Neutral tech powers, internal handlers, and source-object-only effects are not rewards.

Large inventories are split into action lists of at most `16` grants and the
lists are staggered one second apart. This also keeps every generated action
line below the engine's `512`-byte parser cutoff. Emitting `35` earned Chaos
powers in one line previously reproduced the malformed-action `C0000005` crash at
`007C9B92`.

The launcher extracts the complete installed `RULESMO.INI` registry and creates a new map-local `MOR...` copy for every earned power. Only the copy receives the building-free profile. Original superweapon sections remain byte-for-byte/effectively unchanged, so mission triggers can keep using their native power definitions for different scripted purposes. Existing map-local custom types are counted before randomizer types. Numeric keys such as `20000=` are list labels, not runtime indices; action `34` uses the calculated append position after the 135 installed and all native map-local types. Granting the earlier `5000=KnightfallALT` label as runtime index `5000` caused a null lookup and `C0000005` at `006CB569`.

Ares limits type IDs to 24 characters. Prefixing the complete source name produced invalid 26-character IDs `MORAmericanParaDropSpecial` and `MORPsychicDominatorSpecial`; this was a length failure, not an index collision. Clone IDs omit the redundant `Special` suffix and use a deterministic short hash fallback if needed. The current maximum synthetic inventory creates 79 action-granted copies, one Barracks-bound Elite Reserves copy, and two dependent ChronoWarp/Postlift copies: 82 unique registry additions, no missing definitions, and no ID over 21 characters. Per-map numeric list labels are allocated around native keys before writing.

All active player-facing support/aid definitions have an entry in `AID_POWER_MAP_CONFIGS`. Copies clear source power, faction, building, designator, inhibitor, and source-range gates where needed and permit map-wide targeting. Elite Reserves is the exception: its isolated copy remains building-bound, is attached to all eight Barracks variants, is restricted to player countries, and never receives an action `34` grant. Ordinary copies inherit their complete installed recharge/effect/delivery fields. The spawners are the reviewed exception: installed `RechargeTime=0.01` is their invisible construction helper delay, so repeatable minefields use AHAMARTIA's player-facing `2.5` timing and both grids use its `1`-minute timing. Cryomine, EMP Mine, and Genomine fields preserve their installed four-object delivery lists, while Confusion and Stasis grids preserve nine objects. Paladin Aid disables inherited automatic targeting and does not inject the unusable external `SP_RANGE` designator. Knightfall preserves installed `RechargeTime=6.5`. M.A.D. Mine intentionally preserves installed `Deliver.Types=FAMMIN`, which deploys one mine. Kingsnakes delivers a complete map-local `MORF_KSNAK` copy with `PoweredBy=` instead of changing global `F_KSNAK`. Drakuv `RAVA` and Harbinger `HARB` remain `Trainable=no` aid payloads. Harbinger Tower `FAHARB` and EMP Control Station `NAEMPS` are excluded from access/buff pools because their building-free powers clear source gates. Original mission objects remain unchanged.

Offensive and secondary copies also set `IsPowered=false`. Chronoshift uses copied `MORChronoWarp`; Chronolift uses copied `MORPostlift`. Their installed two-stage targeting stays intact. Ten campaigns override shared lightning globals, so copied Lightning Storm receives explicit installed 3.3.6 effect values without rewriting mission storm definitions. `MORNuke` globally remains installed `Type=MultiMissile`, `Action=Nuke`, `WeaponType=NukeCarrier`; changing Type/Action in a map copy is unsupported and broke the power in every mission. Fatal Impact alone registers a private `MORFNukePayload` copied from the installed `NukePayload` (Damage `600`, Warhead `NUKE`) and points only `MORNuke` at it, leaving the map's Damage `5000`/`MIDASDeathWH` objective payload untouched. Mercury Strike follows the supplied mapper-tested building-free `MultiMissile` form rather than an EMPulse cannon: `Nuke.Payload=MercuryOverdriveAlt`, `SW.Warhead=MercuryStrikeAlt`, and `Nuke.SiloLaunch=no`. The payload, projectile, laser, and both warheads are registered map-local copies of the installed originals; `PreventScatter=yes` is the only effect change. Private copies are necessary because campaigns can override the globals (`ACONV` sets `MercuryOverdrive Damage=220`) while the reward must preserve installed recharge `6`, cost `-800`, weapon speed `100`, damage `150`, and effect data. Inherited EMPulse pulse/range fields are removed and no hidden Mercury startup buildings are generated. Wallbuster also follows a mapper-tested `MultiMissile` design. `MORWBCarrier` launches `MORWBUp` through `NukeMaker`; `MORWBPayload` descends through `MORWBDown` and deals the installed 320 damage through private `MORWBWarhead`. Both WeaponTypes, both Projectiles, and the Warhead are registered. The copy retains installed recharge `8.5`, cost, `wbsticon.pcx`, `RROCKET`, and `FLARERED`. Generic clone specs support a separate `source` key so two private sections can safely derive from one installed template. Renamed TechnoType payload clones must explicitly retain source `Image`; omitting `Image=B52` from `MORB52` made Stratofortress crash when the first cloned aircraft spawned. Time Freeze cannot use its native `EMPulse` implementation as a portable reward: the mission power depends on an authored cannon/building relationship, and cloned hidden cannons consumed the charge without applying the effect. The portable copy is now `Type=GenericWarhead`, detonates private `MORTimeFreezeWH` directly with `SW.Damage=0`, and sets `AllowZeroDamage=yes` so sonar/weapon-disable/AttachEffect fields are not optimized away. `DamageAirThreshold=-1` extends the battlefield-wide freeze to airborne units. Its exact-House static provider supplies the launch building needed by Ares targeting, allowing stable `Range=1.4`, `SW.RangeMaximum=384`, and `SW.RangeMinimum=-1`. No Time Freeze weapon or startup cannon is generated. Nanofiber clears inherited `IsPlug` and `Upgrades`; otherwise its hidden `FANANO` clone remains an upgrade rather than a standalone firing building. Hidden support placement orders candidate cells inward toward map center so edge anchors do not send cannon actions farther outside playable terrain. Startup actions share the existing 16-action chunk limit.

The installed Time Freeze is self-targeted and therefore defines no manual
cursor. Its portable copy must explicitly set `Action=Custom`,
`Cursor=Glacial`, and `NoCursor=NoCanDo`; without these fields, clicking the
ready power produced a red health cursor and the engine rejected activation.

The first enemy-filter fix was insufficient. Ares 3.0's
`SW_GenericWarhead::Activate` searches the owning House's buildings for one
that provides the exact SuperWeaponType. It passes that BuildingClass as the
source to `applyEMP` and `applyAttachedEffect`. Action 34 grants portable Time
Freeze without a provider, so this search returns null. Both effect functions
then skip `CanAffectTarget`, causing owner, allies, and enemies to receive the
freeze regardless of `SW.AffectsHouse` or warhead flags. Native mission Time
Freeze differs because its authored source object supplies a non-null firer.

The fix keeps direct `Type=GenericWarhead` and adds no Time Freeze weapon or
EMPulse cannon. One hidden `MORTimeFreezeProvider`, cloned from `DUMMYDUMMY`,
is written directly into `[Structures]` for each exact player House before
map-start triggers run. It declares `SuperWeapon=MORTimeFreeze` in the vanilla
primary slot, carries exact player ownership, is
hidden/passable/EMP-immune/unselectable/non-scoring, and has no weapon. Ares can
therefore resolve it from the owning House's `Buildings` collection and pass
that House through existing EMP and AttachEffect warhead filtering. The power
still sets `SW.AffectsHouse=enemies`; private `MORTimeFreezeWH` sets
`AffectsOwner=no`, `AffectsAllies=no`, and `AffectsEnemies=yes`.
`Versus.misc=0%` independently protects neutral scenery because the installed
warhead uses `EffectsRequireVerses=yes`. ASOMNIA's additional
`Versus.libra=0%` remains mission-specific; copying it globally would exempt
enemy Libra. Runtime definitions reapply provider and filter fields for older
editable packaged catalogues. Ares 3.0 treats the firing house itself as allied
in this direct warhead path, so `AffectsAllies=no` is the operative
owner/allied exclusion; `AffectsOwner` remains an explicit compatibility
field. Both plural binding and later singular binding through action 125 were
structurally present but failed live in Red Dawn. The decisive working-mission
difference is a statically pre-owned provider in `[Structures]`, not only its
slot spelling.

Portable Time Freeze pins its private warhead contract instead of relying on
an editable catalogue's partial overrides. EMP stays disabled through
`EMP.Duration=0` and `EMP.Cap=0`; freezing uses matching 615-frame
`Sonar.Duration`, `DisableWeapons.Duration`, and `AttachEffect.Duration`
values. AttachEffect retains zero speed/firepower, animation, decloak,
zero-damage allowance, `EffectsRequireDamage=no`, and
`EffectsRequireVerses=yes`. `Sonar.Duration` is the installed engine key;
`SonarDuration` does not occur in installed Mental Omega rules. Duration buffs
scale only those three active fields and never restore EMP from the installed
615-frame baseline. Warhead references follow allocated collision-safe IDs.
Repeated unlock input cannot multiply the requested static provider count.

`MORV3TestSpecial` proves a power can be wholly new rather than copied. Its disabled template uses `UnitDelivery`, zero cost, a 0.5-minute recharge, and delivers 20 player-owned `V3` types on land when enabled. `sidebar_image=yuri_shocked.png` supplies both the launcher Unlocks preview and the configured 60×48 indexed `SidebarPCX=moryv3.pcx` loose game asset. PNG is configuration input only; Mental Omega consumes the generated PCX.

`ZephyrBeaconSpecial` delivers neutral `ZTARGET`; installed behavior is only a targeting beacon for already-owned `HOWI` Zephyr Artillery. Convergence (`ACONV`) works through map-specific `HOWI`, armor, two-stage `TargetHate` projectile, and retaliation data. Two portable attempts failed: the direct hidden-building form created the beacon but never fired, while the campaign-chain/instrumented form emitted three `Failed to parse ... LaunchSW` diagnostics under the installed engine and later crashed at `006A84B7` during ordinary runtime before any Zephyr launch was logged. A globally legal hidden `target`-armor building also expands unsafe target state. `ZephyrBeaconSpecial` is therefore disabled in `AID_POWER_MAP_CONFIGS`, removed from `aid_power_rewards`, and retired during canonicalization so old saves cannot regenerate its helper/types. No hidden provider, projectile, warhead, trace SuperWeaponType, or attacked trigger is emitted.

Installed 3.3.6 offensive and secondary indices are:

| Faction | Offensive power (index) | Secondary power (index) |
|---|---|---|
| Allies | Lightning Storm (`2`) | Chronoshift (`3`; the engine handles its ChronoWarp follow-up) |
| Soviets | Tactical Nuke (`0`) | Invulnerability (`1`) |
| Epsilon | Psychic Dominator (`7`) | Rage (`28`) |
| Foehn | Great Tempest (`48`) | None (Blasticade requires owned Blast Trenches) |

Installed delivery/reinforcement indices are:

| Faction | Power indices |
|---|---|
| Allies | Airborne `6`; Bloodhounds `26`; Lightning Rod `51`; Ultra Miner `61`; Kingsnakes `126`; Paladin Aid `128` |
| Soviets | Repair Drone `13`; Tank Drop `16`; Instant Shelter `29`; Motor Ambush `32`; Naval Mine `60`; Terror Drop `62`; Flame Tower `68`; Drakuv Prison Vehicle `70`; Elite Reserves `100` (static provider); Repair Drones `124`; Disruptor `125` |
| Epsilon | Risen Monolith `15`; Scout Raven `18`; Vision `21`; Magnetic Beam `30`; Libra Clones `33`; Bloatick Trap `36`; Quick Fort `86`; Ruiner `93`; Hijackers `108` |
| Foehn | Spinblade `39`; Megaarena `52`; Knightfall `72`; Harbinger `75`; Sweeper Drop `76`; Signal Jammer `77`; Decoy Team `118`; Decoy Squadron `119`; M.A.D. Mine `133` |

`MORV3TestSpecial` is wholly custom and therefore has no installed index; when enabled, it is appended to each generated map's runtime `SuperWeaponTypes` list before action `34` receives its calculated index.

Additional eligible standalone support indices are Allies `10,11,12,17,22,24,41,50,64,78,92,103,104,127`; Soviets `8,14,19,25,42,59,69,73,120,121,122,123`; Epsilon `31,37,38,44,84,102,105,109`; Foehn `40,46,49,55,56,57,63,74,106`.

Action `129` is not used because it changes the charge of a building-backed instance. A constructed matching building may consolidate with the granted instance; independent duplicate cameos are not guaranteed.

Blasticade is not a reward because it needs owned Blast Trench objects to produce any effect. Golden Wind is also source-object dependent and is not a replacement.

`EliteReservesSpecial` (`100`) cannot be granted through action `34`. Its `UnitDelivery` creates the invisible `F_ERESB` production-state marker; 2026-07-14 crash reports consistently ended while action `34` processed it. The active reward now registers `MOREliteReserves` on one hidden exact-House static `MOREliteProvider`, clears power/auxiliary/house gates, and never attaches to Barracks. Delivered `MORF_ERESB` removes inherited Owner, RequiredHouses, ForbiddenHouses, FactoryOwners, prerequisite, and TechLevel gates while retaining all four factions' Tier 1 Academy effects.

Map-start power grants normally target only authoritative `[Basic] Player`. Reviewed phase-based exceptions target every required human country: `ASIREN` declares Europeans as `[Basic] Player` while its gameplay triggers and second controllable force use UnitedStates, and `SAWAKE` rotates among PlayerEscort, Player, and USSR2. Each reviewed country receives the same isolated clone indices in separately bounded action lists; native mission power sections and triggers remain unchanged. This explicit allowlist avoids empowering unrelated temporary/script houses merely because a map also marks them `PlayerControl=yes`.

The July 2026 mission audit confirmed that `ABMIND`'s `IronCurtainSpecial RechargeTime=.3` is native map data and remains identical in generated output. Machinehead exposes only its isolated `MORPFOX` player build identity and retargets authored Event 81 `01000942` to count sixteen of it. A parallel native/clone trigger enabled from `01000920` caused a live C0000005 exactly when the second reinforcement/Hammer-defense transition enabled it; never extend this objective with an injected trigger. Singularity's native passengers remain live global objects after boarding, so Event 61 absence is not a transport-entry detector. The authored Driller unit 43 now carries `MORSGIN`, and enabled success trigger `01000639` uses object-attached Entered-by Event 1 for PsiCorps House index 6; Malver entering fires success without depending on unrelated PsiCorps objects. Tainted Empire's Yunru retry loop now requires `YUNRU` absence instead of a local that stays clear until lab entry. Machinehead's ScorpionCell drop-pod creates native `LIBRA`, so all follow-up teams and Event 61 loss references must also remain native. Rewriting only the loss event to `MORPLIBRA` makes the absent clone satisfy Event 61 immediately when Libra arrives and causes instant defeat. Juggernaut's Action 106 entries for `NAHAMM`/`NAIRDM` now target registered player clones, while a mission-local earned-defense pass also exposes every unlocked Allied, Soviet, Epsilon, and Foehn defense through any construction yard; the native pair is not mistaken for the complete reward inventory. Soviet 24 likewise retargets its authored Action 106 `MAMM` unlock to `MORPMAMM`. When Apocalypse is not already earned, its complete owned clone stays at `TechLevel=-1` until that action fires; native MAMM TaskForces remain unchanged. Apocalypse is also a Soviet Special reward with a complete static owned type and six independently cloned/buffed rookie/elite cannon/missile/strike weapons. If Special access is already owned, the clone is available immediately and the later action harmlessly targets the same identity. SHAND's native DOG and SENGINEER remain available only to their exact story/helper countries; the player receives only the isolated buffed copies. Kill the Messenger applies its deployment fix to native `[SMCV]` as a final map-section rule: routing it through ordinary required-access handling incorrectly moved the fields onto `MORPSMCV`, while TeamType `01000031` still created native `SMCV`. Its four reviewed Guild1-only starting TaskForces (`01000006`, `01000007`, `01000008`, `01000020`) are explicit exceptions to blanket action-referenced story-team preservation and now use isolated buffed clones. Enemy/shared TaskForces remain native. The SMCV keeps Speed `16`, `Accelerates=false`, and ROT `10`; earned speed does not alter it. Bleed Red's map-local `MORALES` is Boris, not the installed hero: his native identity is retained, only his spawn TeamType (`01000468`) is assigned to `USSR`, and all four transport/escort TeamTypes remain explicitly assigned to authored `Boris`. Native fallback-loss Event `01000528` originally checked whether House index 15 (`Boris House`) had no objects; moving Boris out of that house made the condition true immediately at his arrival. The map-only event override now checks global `MORALES` absence followed by the original elapsed-time condition, so Boris remains controllable and defeat occurs only after he actually dies. Unthinkable keeps `LIBRA`, its final `MDUMMY2` Driller, and `ASSN` Rahn native: its exact post-Libra boarding TaskForce and script chain now remain intact. Reality Check excludes `ScorpionCell House` from reward/retry buff targeting because that future player-control house begins allied to the hostile army. `LIBRA` and all eight phase identities stay native. Their authored Strength bases are multiplied by five (`6000` for 1200-strength phases, `7500` for 1500-strength phases), then all earned health, armor, sight, ammo, stealth, cost, speed, and primary-weapon buffs are layered on those mission bases. `FKILL` supplies a Soviet MCV, so Foehn Standard translates earned basic-defense roles to Soviet equivalents. `HARB` and `RAVA` remain aid-only payloads. Moon Reinforcements clears inherited target kind, shroud, and distance gates; direct action-34 ownership has no source building from which `SW.RangeMaximum=22` could be measured. Each payload stack adds one pod plus `SHOCK` and `CYBO` weights. Power action lists remain split at 16 actions. Maximum-power map generation remains below the 511-byte action-line limit.

The July 23 reward audit replaced the old ad-hoc cross-faction buff mapping with the reviewed `grouping ideas.txt`/`regrouping.txt` roles. Groups are disjoint and validated at startup. In particular, `CLAIR` now follows `SPY/SBTR/INTRUDER`, `SYNC` follows `SUPR/ARSO/REPU`, the three Allied IFV variants share their anti-air group, and `DUNE` is restored as a full Epsilon access/buff target with its installed sensor and HoverGrenade baselines. Robot Tank access now uses both `GAWEAP` and `GAYARD`; Chaos retains both production categories. Linked identity pairs `JACKAL/JACKALP`, `DIVER/DIVERP`, and `TARCHIA/TARCHIAP` expand each earned direct-buff count to both the normal Foehn and Allied prototype form, while keeping each form's own cost, speed, strength, faction, label, and weapon baselines. Editable special-building rewards live in `rewards/special_buildings.json` and cover `GAOREP`, `NAINDP`, `NACLON`, and `FAREPR`: Standard uses the native faction Construction Yard, while Chaos permits all four. Divergence exposed the old Wallbuster placement defect: its human `PsiCorps` house owns no startup object, so the retired hidden-cannon implementation used arbitrary edge anchors. The mapper-tested `MultiMissile` conversion below removes that dependency. Mission-specific `map_section_rules` provide final literal/null or CSV add/remove edits for arbitrary extracted-map sections without mission-code branches. Fatal Impact uses this hook to append the randomized `MORPSVOLKOV` identity to `YTUNNEL.Passengers.Allowed` while preserving its five native passengers.

The July 26 mapper-tested Wallbuster conversion supersedes the earlier hidden-cannon placement findings above. Wallbuster now consumes no map-start action slots or placement anchors; its private `MultiMissile` chain works directly from the action-34 power copy. Maximum-power action lists remain under both action-count and 511-byte limits.

Multi-house power grants must not replace the single concrete country used by
objective marker TeamTypes. The first implementation removed the old `house`
local but left marker generation referencing it. Any mission with pending
checks then raised `NameError`; launch fallback deliberately ran the untouched
source map, which looked like a complete loss of buffs and earned production.
Marker ownership now uses a separate authoritative player-country value while
power grants retain their reviewed multi-house list. Real-map generation tests
for `ABADAPPLE` and `SRAVEN` each produced all three objective/victory markers
and a hooked map containing the reward/access rules.

## Cameo Pipeline

The Unlocks view resolves unit `Image` and `CameoPCX` values from installed `rulesmo.ini` and `artmo.ini` files inside Mental Omega MIX archives. Superpower rewards use the `SidebarPCX` value from their installed superweapon section, covering offensive, secondary, and aid/reinforcement powers without a manually maintained filename table. Only requested PCX members are extracted. A standard-library decoder converts indexed PCX data to cached PNG files, so Pillow and replacement artwork are unnecessary. Extraction is serialized in-process and uses a per-process/per-thread request file, preventing concurrent background work or multiple launcher processes from overwriting another request. Decoder rejections log their exact format/truncation reason. Mortar Quad is the reviewed art-name exception: its copied player definition uses `Image=MOTOR`, matching installed `[MOTOR] CameoPCX=quadicon.pcx`; mapper-source `Image=MORTAR` has no installed art section.

TechnoType `CameoPCX` is art-INI-only; putting it into a generated map rules
section is ignored. Before a generated mission starts, the launcher therefore
writes a complete temporary loose `artmo.ini` from the installed cached file
and appends exact aliases for registered generated IDs. Perun's extracted
`peruico.pcx` image is bundled as `assets/perun_flagship.png`, converted to
namespaced loose `morperunicon.pcx` at launch, and assigned to exact compact
clone aliases plus `[PERUN]`; this avoids the missing installed art section
which otherwise falls through to the generic Mental Omega icon. Jackal
Prototype uses `jackaicon.pcx`. The file has a launcher marker, refuses to
replace custom loose art, and is deleted with the generated map. Normal and
prototype standalone Jackal clones use `Image=JACKAL`
because native `Image=JACKALA` depends on the original identity's mobile
turret and produced an invisible standalone clone.

Map and cameo extraction load `NLog.dll`, `CNCMaps.Shared.dll`, and `CNCMaps.FileFormats.dll` from byte arrays in dependency order. This avoids .NET error `0x80131515` when a freshly copied/downloaded Mental Omega folder retains Windows `Zone.Identifier` markers. The launcher does not unblock, rewrite, or remove alternate streams from the installed renderer DLLs or MIX archives.

## Rejected or Disabled Paths

| Approach | Reason |
|---|---|
| Forced `[Basic] EndOfGame` | Could complete a mission immediately and bypass normal map logic |
| Marker appended after terminal victory | Engine may end the scenario before executing it |
| Loose global `rulesmo.ini` for ordinary rewards | Can destabilize spawned missions or cause client installation checks to fail |
| Broad indiscriminate TechnoType/WeaponType/TaskForce cloning | Fatal weapon construction and unacceptable campaign runtime slowdown; mandatory narrow clones copy only currently required combat sections |
| Reassigning campaign houses to `MORPLAYER`, `MORALLY*`, or `MORASSIST*` countries | Trigger owners use the original country IDs; reassignment breaks mission logic and scripted ownership transfers |
| Writing a buff directly onto an enemy-shared TechnoType/WeaponType | Would grant the same raw type change to enemy units, so the effect is skipped |
| Action-34 Elite Reserves | Action `34` crashes while creating its internal production-state marker; use exact-House static provider |

## July 25 Compatibility Additions

- Six `configs/Randomizer*.ini` files are player-owned TechnoType source: infantry, heroes, vehicles, ships, aircraft, and defenses/special buildings. Ships still use engine `VehicleTypes`; hero file may contain both InfantryTypes and VehicleTypes. Startup/self-check must reject a missing file, target definition, or registry entry. Regenerate only with `tools/generate_randomizer_units.py`; runtime never rebuilds them from installed rules cache.
- The copied Iron Guard clears its installed `NAIRON` prerequisite and adds `MORPNAIRDM` beside native `NAIRDM` in `IronGuardSpecial.EMPulse.Cannons`. This keeps native mission/AI Iron Guards intact while the player copy builds and fires through any earned faction Construction Yard. Iron Guard is excluded from cloak rewards and its static clone has `Cloakable.Allowed=no`: the building is the auto-firing self-targeted EMPulse cannon, so cloaking that source can suppress the invulnerability field. A mandatory code-side reward exclusion and roster-template overlay repeat both facts because packaged upgrades intentionally preserve older editable files under `RandomizerLauncherData/configs`.
- Mercury uses a registered private copy of the mapper-tested `MercuryOverdrive` payload chain plus `MercuryStrikeAlt` warhead and needs no startup object. Devourer and Nanofiber Sync remain EMPulse source-dependent; each copied power uses four hidden direct-fire startup cannons with `Owner`/`RequiredHouses` set to the actual grant country and target range `0..9999`. Devourer uses a private zero-minimum-range weapon chain; Nanofiber uses its installed seven-stage chain. Wallbuster likewise uses its registered private `MultiMissile` chain and needs no startup object. Map-start chunks retain the 16-action ceiling and split earlier when a serialized line would exceed 511 bytes.
- Superseding earlier Barracks-bound notes, Elite Reserves remains outside action `34` but uses one hidden exact-House static provider, so no Barracks, live power, auxiliary tech, or faction gate can suppress it. It delivers private unrestricted `MORF_ERESB`. Its Academy starts from native Tier 1 infantry, vehicles, and aircraft across all four factions, then launch generation adds each actual player clone ID. Static `MORP*` names cannot be used: earned veterancy assigns compact two-character clone IDs, and the Phobos debug log explicitly rejected every unregistered static Academy entry.
- The earlier 97-map maximum-power/veterancy audit produced the reviewed hidden EMPulse cannons for Devourer and Nanofiber, the complete registered Wallbuster chain, no missing/unknown Academy IDs, and compact Elite Reserves targets on every map. The July 30 Elite audit generated all 97 maps with one static provider each, zero Elite action-34 grants, zero Academy production/house/tech/prerequisite gates, all infantry/vehicle/aircraft veterancy effects intact, and longest action 502 bytes. A focused 97-map Mercury audit verifies its mapper-tested `MultiMissile` fields, installed payload, registered alternate warhead, original recharge/cost/speed/damage, one grant action, no missing dependencies, and no startup cannon on every campaign map.
- Power buffs are separate rewards and settings from unit/building buffs. Settings `Superweapons` controls broad global families through `enabled_power_buff_types`. Advanced `Superpower Buffs` uses the same card/detail pattern as `Unit Buffs`: select one included power, then enable or disable only its globally enabled valid buff types; detailed exclusions persist in `excluded_power_buff_types`. There is no separate `Toplevel` or duplicate global row inside Advanced. `rewards/power_buffs.json` explicitly groups safe applicability for recharge, activation cost, effect area, direct damage, timed duration, and delivered payload count. Planning requires the matching power access first. Launch folds stacks into the canonical reward copy before `cloned_superweapon_plan`; a runtime-canonical marker prevents downstream compatibility canonicalization from discarding those overlays. Warhead area/duration changes use private auxiliary clones. Recharge, activation-cost, direct-damage, and timed-duration rewards stop at five stacks per power; effect-area and extra-payload rewards remain unbounded. Planning excludes capped rewards immediately and launch clamps legacy excess to the same effective count. UI labels and accumulated-effect text use this shared cap source.
- Target Painter potency scales its private `AttachEffect.ArmorMultiplier`. Overcharge scales only its private `AttachEffect.FirepowerMultiplier`; its first 25%-stronger stack raises the installed 50% bonus to 62.5%, above Rage's installed 60%. Bloatick Trap privately clones `YATUNL` and `TickTrapSpawn`; payload stacks add Bloaticks to the nested spawner, KAOS delivery resolves to the current player clone so buildable Bloatick buffs carry over, health scales `Strength`, and a private armor alias compensates `VisionKillWH` self-damage so health and lifetime stacks remain independent. Nanocharge and Megaarena all-vehicle upgrades enumerate normal installed `VehicleTypes` and write only their private warhead verses; explicitly unselectable and non-scoring helpers plus script immunity armors remain excluded, and upgraded Nanocharge clears its Leviathan/Mastodon designator gate. Devourer, Geneburst, Toxic Strike, and Mercury damage/area stacks modify their distinct private payload-weapon and terminal-warhead chains rather than assuming `SW.Damage` or `SW.Range`.
- A private warhead section is not sufficient for `SW.Warhead`. Ares resolves the reference through the `[Warheads]` registry while parsing the SuperWeaponType. Live `debug.log` exposed the failure as `Failed to parse INI file content: [MORMaintenance]SW.Warhead=MORMaintenanceWH`; the power still consumed its charge but `SW_GenericWarhead::Activate` received no warhead. Auxiliary clone specs now honor their configured type list, and power-buff-created `SW.Warhead` clones set `list=Warheads`. This also removes the same parse failure from all area/duration-buffed powers, not only Maintenance.
Insomnia keeps `TANY` and `SIEG` native across initial teams, Event 61 absence checks, and respawn TaskForces, then forwards earned buffs directly to those map identities. Cloning only the watched identity made live heroes count as absent and produced duplicate respawns.

EVA selection is launch-time appearance state, not seed progression. Side
`EVA.Tag` fields alone are not reliable for an already-created campaign player.
Launch generation therefore keeps the four Side fields as fallback and adds
Ares action `148` at time zero for the live player: Allied `0`, Russian `1`,
Yuri `2`, then configured custom tags from `3` onward. Native positive action
`148` changes are rebound to the selected voice; `-1` still silences EVA for
authored cinematics.

Standard Tier 1 starters are saved as five concrete identities per usable
faction family. Each launch map prepares only its selected family's five behind
exact prerequisites. Ordinary maps whose MCV/factories appear only after
opening scripts still use the human-house fallback without adding sibling
subtypes. True fixed-unit/no-build maps retain no starter combat units;
reviewed no-build maps with authored production receive compatible equivalents.

## Known Limits

- Runtime discovery, trigger matching, ownership analysis, and reward injection have been audited only against the original Mental Omega campaign maps. Custom maps, funmaps, map packs, rules edits, and other gameplay modifiers are unsupported and must be reproduced on a separate fresh installation before they are treated as Randomizer defects.
- Objective checks are paired to recognized action lists by order; mission-specific mappings are still needed where briefing and action counts differ.
- `SROAD` and `EGODSEND` have no recognized standard objective-complete action in the installed audit.
- Temporary allies that are scripted to become enemies cannot safely receive static helper buffs; they are deliberately excluded even during their friendly phase.
- Mandatory standalone player clones have static 97-map generation coverage plus successful live isolation, sidebar, and helper-production tests. Loading cost, save/load behavior, and wider campaign trigger compatibility still need continued validation.
- Direct unit/weapon buffs are skipped when a denied enemy shares the affected global type.
- Matching power buildings may share the granted power instead of creating an independent copy.
- Backwarp, Nuclear Path, and Blackout Missile use private EMPulse weapon/projectile/warhead chains fired by invisible exact-House startup cannons. Gear Change and Nanocharge use private Hunter-Seeker payload chains plus invisible exact-House providers. All five clear live-power, house, auxiliary-building, negative-building, inhibitor, and inherited designator gates; none requires its native tech structure. Psychic Flash clears those same availability gates and overpowers only `YARAIL`/`YAHADE` plus their current map-local player clones. Seed planning withholds Psychic Flash until either defense access reward is already earned. Nanocharge deliberately restores a designator gate for `LEVI`/`PROME` and their player clones, whose generated copies receive `DesignatorRange=384`; the power therefore cannot be used without an owned Leviathan or Mastodon on the field. Blasticade and Golden Wind remain excluded because their effects require preplaced Blast Trenches or Spinblades. Grinder is skipped because its native mobile form already deploys into the linked grinder building, and Old Mobile Gap Generator is skipped as obsolete campaign novelty.
- Game-speed behavior needs validation across more campaign maps.

## July 26 Context and Sidebar Rules

- Randomizer SuperWeaponType clones set `CameoPriority=10000`. Phobos evaluates this before vanilla cameo ordering and larger values sort first, placing granted powers above the current defense/building bands while preserving relative power order.
- `PROJECT_CONTEXT.md` is compact authoritative agent memory. Root and repository `AGENTS.md` files require Caveman ultra plus that one context read, then defer `TECHNICAL_FINDINGS.md`, JSON catalogues, INI rosters, extracted maps, and installed rules until a task needs exact detail.
- Static `Randomizer*.ini` files own complete player TechnoType identities. Validated JSON remains policy/compatibility data. `rewards/unit_data.json` has intentional roster/base-stat overlap that may be migrated later, but cannot be deleted while reward construction still consumes its target metadata, role groups, linked variants, labels, and compatibility facts.
- Archipelago transport, slot data, item IDs, and location IDs are not implemented yet.

## August 1 Mission Corrections

- Supersedes the July Machinehead native-and-clone note: `FOX` is now native
  only, excluded from direct buffs, and buildable behind `NAAIR`. Authored Event
  81 `01000942` counts that same identity. Never add a parallel trigger to
  objective action `01000920`; the attempted trigger caused a live C0000005 at
  the second reinforcement/Hammer-defense transition.
- Singularity passengers remain live global objects while inside a transport,
  so Event 61 absence cannot detect evacuation. Native Driller unit 43 carries
  an attached Entered-by-PsiCorps tag that fires authored success trigger
  `01000639` when Malver boards.

## August 2 Trigger and Power-State Corrections

- Machinehead action `01000580` contains reinforcement waypoint `FV`. Generic
  exact-reference rewriting confused it with the IFV TechnoType and wrote
  `MORPFV`. Serialized Action groups have eight fields after the count, and
  field eight is always a waypoint. Clone discovery and replacement now exclude
  that field globally while preserving genuine type parameters. A later live
  run retained `FV` but crashed at the same transition, proving waypoint repair
  was not the complete crash fix.
- Machinehead crash dump `snapshot-20260802-000754` failed at the same virtual
  call as the later `003320` snapshot. The bad object used the
  `.?AVAbstractClass@@` vtable; its `+0x78` slot held invalid target
  `A2529D39`, while a valid infantry object's corresponding slot resolved into
  `gamemd.exe`. Debug timing placed the fault immediately after `GHTNK 235` and
  `GHTNK 236` reached their west-edge waypoints. Replacing their authored
  `37,0` cleanup with guard (`5,2`) did not fix it: live snapshot
  `20260802-005323` traversed the same paths and failed through the same
  `AbstractClass` vtable, now at invalid target `404E0000`. The GHTNKs are the
  transports that deliver the visible Driller wave. Disabling return-only
  triggers `01000561` and `01000563` caused an immediate live crash and was
  reverted. Restoring `[GHTNK]` alone did not fix the live crash: snapshot
  `20260802-012939` reached the same return paths and failed at the same invalid
  virtual target. Full wave comparison then showed that every other prebuilt
  reinforcement identity was still changed. `[CNTR]`, its initial `[COVE]`
  payload, `[EMPR]`, `[CTNK]`, and `[ARMA]` each gained
  `ForbiddenHouses`, the hidden negative gate, and `TechLevel=-1` (replacing
  authored `TechLevel=11` for CNTR/COVE). TeamTypes, TaskForces, Scripts,
  Actions, and return triggers were otherwise authored. EHEAD now preserves all
  six runtime sections after clone planning while player production continues
  through separate clones. The focused audit found no other difference in the
  crashing reinforcement chain. The next fresh-seed snapshot
  `20260802-014444` proved this removed the invalid-vtable failure, but exposed
  a second cleanup fault at gamemd `004F9AB1`. Disassembly shows the engine
  calling through a valid GHTNK object and reading its Owner at offset `+0x21C`;
  Owner was null immediately after the return paths reached their deletion
  edge. That looked like a destructive action-37 use-after-delete. The earlier
  guard-only experiment could not isolate it because native wave identities
  were still changed. With all six wave identities preserved, the scripts were
  changed to final guard `5,2`; snapshot `20260802-015337` nevertheless failed
  through the earlier invalid virtual target. This disproved action 37 as the
  root cause.

  The earlier comparison covered map-authored sections only and missed an
  effective installed-rule change. TaskForce `01000387`, which creates the two
  player reinforcement teams immediately before the failing transition,
  contains two native `YENGINEER`s plus one native `DRIL`. Generated output
  kept those references but changed installed `YENGINEER` from
  `TechLevel=2`, no negative prerequisite, no cloak, and `Strength=90` to
  `TechLevel=-1`, `Prerequisite.Negative=MORPOriginalGate`, cloak enabled, and
  `Strength=103`. The exact-House gate belongs to the same PsiCorps House
  creating the TeamType. Established TeamType behavior rejects that native
  passenger while still allowing the native Driller, leaving both mixed
  reinforcement teams incomplete before their return cleanup. The later GHTNK
  transition exposes the stale team/object state; it does not create it. EHEAD
  runtime preservation now includes `DRIL` and `YENGINEER` as well as the six
  wave identities. Scripts `01000557`/`01000558` are restored to authored
  `37,0`; no cleanup guard workaround remains. Focused regeneration found that
  clone-stage preservation alone removed the gate but a later guarded/native
  buff pass still restored cloak and changed Strength to `119`. Runtime
  preservation is therefore re-applied after every clone, gate, assistance,
  direct-buff, and weapon pass. The final EHEAD map matches effective original
  rules for all eight reinforcement identities; its delivery, return, wave,
  TaskForce, TeamType, ScriptType, trigger, placement, and registry chain is
  exact. Foxtrot production/objective isolation remains intact. A 97-map real
  saved-state launch audit passed with action lines at most 511 bytes and no
  generated root maps left. Fresh live confirmation remains required.
- Machinehead native/shared Foxtrot counting was also rejected. Player
  production, native enemy placements, TaskForces, and Events `01000926` and
  `01000942` now all retain `FOX`. The 8/16 objectives keep one authored
  identity and no second trigger.
- Definitive Machinehead generated-map defect superseding the action-37 and
  partial-YENGINEER-team theories: the active EHEAD map contained six unpacked
  INI lines above the engine's 511-byte raw line limit.
  `MORKnightfallSpawn DropPod.Types` was 602 bytes;
  `MORKingsnakes Deliver.Types` 541; `MOREMPMineSpawn Deliver.Types` 629;
  `MORPaladinAid Deliver.Types` 601; `MORCryomineSpawn Deliver.Types` 629; and
  `MORGenomineSpawn Deliver.Types` 629. The engine debug log named those exact
  six fields as parse failures and showed truncated values. Original EHEAD and
  all 97 original campaign maps have zero unpacked lines over 511 bytes. Base
  Mental Omega already registers 1,156 BuildingTypes and generated EHEAD reaches
  1,179, exactly matching the recurring `> 512` warning; that warning is
  inherited, not the Machinehead-specific regression. The 609 Ares pointer
  warnings are also stable across snapshots.

  The newest exception was `C0000005` at invalid EIP `000000B9`. Its callers
  resolve to `BuildingClass::AI`, `TechnoClass::SelectAutoTarget`, and
  `TechnoClass::CanAutoTargetObject`; older crashes used unrelated invalid
  targets. This is downstream memory corruption from malformed live
  SuperWeaponTypes, exposed when reinforcement arrival changes an armed
  building's target scan, not evidence of a Team/Script loop or early delete.

  UnitDelivery and DropPod payloads now use deterministic two-character player
  clone IDs before repeated lists are serialized. Kingsnakes' fixed auxiliary
  clone is `MORFKS`; exact payload counts remain 107/48/56/49/56/56. A final
  generation invariant rejects every unpacked line above 511 bytes. Two other
  parser failures, `VeteranInfantry=LUNRE` and `VeteranUnits=JACKALP`, referenced
  sections without matching TechnoType registry entries; Country Veteran fields
  now retain only IDs in the effective matching category registry. A real
  saved-state launch-path audit generated all 97 missions with zero overlong
  unpacked lines and zero invalid Veteran references. Focused EHEAD comparison
  retained all native TaskForces, ScriptTypes, Triggers, Tags, original
  placements, Foxtrot Events, and all eight protected reinforcement identities.
  Fifteen intended player reinforcement TeamTypes change only
  `VeteranLevel=1` to `2`. Fresh live confirmation remains required.
- Power Hunger must never put `37,0` in delivery script `01001529`: that deletes
  both SAPC and SMCV. Unload mode `8,2` releases the SAPC from the delivery team.
  Local-47 action `01001542` now creates a separate Latin cleanup TeamType using
  authored SAPC-only TaskForce `01001090` and script `01001082`; it moves and
  deletes only the freed transporter. Authored `01001529` moved a land MCV to
  waypoint 3; transport conversion accidentally gave that move only to the
  loaded SAPC. The script now repeats move-to-3 after unload, waits six seconds
  for cleanup, then action `9,0` deploys the separated MCV.
- Power buff rewards never imply access. Grant preparation now returns only
  earned `kind=superweapon` rewards, folding stored buff counts into those real
  unlocks. Dashboard indexing has separate `earned` and `earned_unlocks` lists;
  a buff-only power remains locked and shows deferred effects until access is
  actually earned.

## August 2 Unit Damage Ceiling

- Supersedes earlier uncapped unit-damage notes. Unit weapon damage remains
  x1.15 per stack but caps at x6 total damage, displayed as +500%, on stack 13.
  Planning stops assigning that unit's damage reward at 13; UI aggregation and
  generated WeaponTypes clamp legacy excess stacks to the same value.

## August 2 House Buff and Time Freeze Audit

- Root cause of faction-skewed house buffs was split application. Standard UI
  and CountryType code aggregated production/cost/armor by category, but the
  direct clone fallback retained only each reward source's own stack. Because
  production is always clone-local and shared child countries force cost/armor
  clone-local, most Allied/Epsilon/Foehn clones received zero or one stack;
  safe Soviet CountryTypes appeared correct. Direct house-wide application now
  removes those source-local counts, aggregates category plus global stacks,
  clamps once, then writes every applicable owned clone. Country-safe paths
  still emit reciprocal `Armor*Mult`; shared-country paths divide clone
  Strength by the same received-damage multiplier. Unlocks combines global and
  category production when showing live category percentages. Fire-rate text
  uses inverse ROF delay, matching attacks per time.
- Portable Time Freeze keeps its exact-House static provider and dual house
  filters. Mission-critical immunity is additional, data-driven defense:
  every configured exact TechnoType receives a mission-private custom armor
  alias inheriting its normal armor, and only that alias receives `0%` verses
  on the private warhead. SRED protects Morales and Hammer Defense without
  exempting unrelated `moral` or `defense_b` objects, preventing scripted hero
  stunlock and Hammer Defense EMP/AI sell behavior. SBLEED protects only its
  scripted Morales. EBLOOD emits no combat immunity; its `PC-Player House`
  provider owns the power and owner/allied denial prevents Dance of Blood from
  freezing player objects.

## August 2 T1 Defense and Campaign AI Power Audit

- The missing-defense root had two layers. `ACCESS_CATALOG` was eagerly built
  during the rewards/maps import cycle and permanently captured an empty reward
  pool. After making it lazy, its parser still ignored ordinary `Prerequisite`
  and indexed the normalized null `Prerequisite.List0=none` sentinel. Runtime
  access discovery therefore returned no defense entries. The catalogue now
  initializes on first use, parses normal/override/numbered prerequisites, and
  rejects null sentinels. Standard's saved T1 defense marker resolves to the
  selected mission family's ground/anti-air pair; Epsilon legitimately uses
  one Gatling Cannon identity for both. Chaos uses fixed concrete defenses,
  and starter rules apply after
  mission-specific defense merges so primary/list prerequisites cannot be
  duplicated or replaced.
- Soviet 03 retained its original paradrop and back-air TeamTypes, TaskForces,
  Scripts, Triggers, Actions, timings, and targets, but E1, GGI, COMA, and
  JUMPJET first ended at launcher `TechLevel=-1`/`BuildLimit=0`. Restoring those
  fields was necessary but not sufficient. Live debug later logged repeated
  `[LAUNCH] ParaDropSpecial` without Paradrop 1/2 TeamType creation: the native
  payloads still had `MORPOriginalGate`, and Ares checks negative prerequisites
  while creating scripted/ParaDrop payloads. Every registered randomized native
  type restores effective TechLevel/BuildLimit, but the exact-player negative
  gate is now omitted for any non-player placement/TeamType consumer. Player
  clone access remains independent. GAAIRC keeps its original SuperWeapon and
  installed broad ownership; T1 preparation does not narrow it.
- Action 106 filtering was global and removed enemy/story TechLevel actions for
  randomized types; reviewed player clone retargeting could likewise rewrite
  them. The pipeline now derives non-player trigger IDs from map House records
  and preserves their authored Action groups through both rewrite and filter
  passes. Player/helper-owned access actions remain eligible for clone
  retargeting. Existing reviewed semantic mission fixes, such as SRED's duplicate
  MCV-delivery suppression, remain authoritative.
- A real 9,960-reward launch audit regenerated all 97 campaigns with zero
  failures. It checked 255 T1 defense rules, 9,030 hostile TeamTypes plus their
  TaskForces/Scripts, 14,927 payload entries and effective production fields,
  13,364 hostile triggers, 822 original SuperWeapon fields, and 1,856
  AITrigger entries. Soviet 03's Paradrop 1, Paradrop 2, Back Air Attack, and
  GAAIRC chain passed focused and full audits. Live in-engine observation of
  original timing and targets remains final confirmation.
- Later Golden Gate live proof superseded the native-FreeUnit attempt: a foreign
  refinery could not create its native miner because that miner's Owner did not
  match the current player, while captured factories exposed both native and
  MORP cameos. All four original refinery identities now point their sole
  `FreeUnit` at the matching player miner clone. Every clone has player Owner/
  RequiredHouses, TechLevel 1, and exact factory+refinery prerequisites. Native
  miner production is hidden; no refinery clone, alternate registration, or
  `FreeUnit2` exists.
- Map `ForbiddenHouses=none` is authoritative. The old union reintroduced an
  installed restriction even when campaign authors explicitly cleared it, and
  null removal then exposed the installed fallback again. Literal `none` is
  emitted when clearing an inherited restriction. Player-added forbidden
  countries are also removed from a native type whenever they collide with an
  authored non-player runtime House/country. Final 97-map generation validated
  20,949 non-player runtime consumers and all 388 refinery/miner paths with zero
  spawn gates, launcher-added ownership collisions, or missing/duplicate player
  miner clones.

The August 2026 normal-attack regression began when commit `9f81466` narrowed
the original production-gate exclusions from all non-player runtime identities
to DropPod/runtime-preserve identities. Ordinary campaign TaskForce payloads
therefore gained `MORPOriginalGate`; later build-only isolation could also add
player countries to `FactoryOwners.Forbidden`. Ares evaluates these production
filters while forming native campaign teams, so the AI loop and support powers
could remain active while ordinary attacks silently stopped. The global repair
uses the already-computed non-player TaskForce payload set: non-Engineer native
payloads retain authored effective negative-prerequisite and factory-owner
filters, with a final validator enforcing both. It does not edit mission AI.
Focused AREDDAWN and SDRAGON generation preserved their original AITrigger,
TeamType, TaskForce, ScriptType, house, Autocreate, prerequisite, and timing
data. A split full audit covered all 97 launch paths; reviewed player/helper
clone rewrites and explicit mission overrides remained allowed, while every
original hostile team/script payload and AI registry entry stayed intact.

Noise Severe creates its opening force through player-owned TeamTypes after a
FriendlyTank-versus-BadTank sequence, then hands every surviving FriendlyTank
object to the USSR player. The reported generated map left TaskForces
`01000054`, `01000055`, `01000068`, and `01000090` on native `HTNK`, `TTNK`,
`SCAR`/`SHOCK`/`FLAKT`, and `E2`/`FLAKT`/`SHOCK`, while those native sections
gained `FactoryOwners.Forbidden=USSR,MORPLAYER`. Ares evaluates that filter
while Action 80 assembles the USSR teams, so the handoff completed without the
expected player force. These four reviewed TaskForces now follow the isolated
player clones; BadTank's separate native TaskForce `01000045` remains authored.

Stormbringer's placed Siegfried is infantry record `71`, owned by Pacific House
and bound to tag `01000745` (`[OTHER]/Siegfried Dies`). The original uses native
`SIEG`; the reported bad map replaced it with `MORPSIEG`. That clone still had
the correct infantry locomotor `{4A582744-9839-11d1-B709-00A024DDAFD1}`,
`MovementZone=Infantry`, `Speed=6`, and `Teleporter=yes`, excluding a malformed
movement definition. It also detached the object from native map overrides and
the authored identity used by mission behavior. A later saved-state generation
happened to use a separate uncloaked `MORRSIEG` reference and moved normally,
but that did not make the original rewrite safe. ASTORM was missing from the
same native scripted-hero policy already used by AINSOMNIA. It now preserves
native SIEG through trigger-reference, clone-exclusion, and direct-buff policy,
then applies earned buffs through `native_variant_buff_rules`. No mission
Trigger, Tag, Event, Action, TeamType, TaskForce, or ScriptType changes.

Road Trippin's four player-controlled Guardian GIs are infantry records `16`,
`17`, `24`, and `25`. Replacing these authored startup objects with the isolated
`MORPGGI` identity left them selectable but unable to move, matching the earlier
Stormbringer placed-infantry failure even though both native and cloned movement
fields were valid. `AROADTRIP` now keeps `GGI` native for placements, TaskForces,
and exact mission references. Earned Guardian GI buffs are forwarded to that
native mission identity, so preserving campaign behavior does not discard the
player's upgrades.

## August 25 Suicide-Unit Range Safety

Suicide weapons detonate at their firing point. Extra weapon range therefore
makes the unit explode before reaching its target. Range rewards are excluded
for Bomb Buggy, Ivan Biker, Ivan Cadet, Demolition Truck, Old Demo Truck, and
Mosquito Demoboat. This exclusion is mandatory in code as well as present in
editable reward policy, so preserved packaged configs, retry assistance, old
saves, and externally supplied rewards cannot restore the harmful effect.
Published `Old Demo Truck Optics I` save/AP receipts migrate to Old Demo Truck
Reinforced Frames instead; the preceding AP catalogue checksum remains accepted
and its item-ID mapping is canonicalized during connection and ledger recovery.

## August 27 Shop Access and Mission-Opening Safety

Shop runs originally serialized and launched through Standard reward mode.
That path translates access through map factions and compatible production,
which could expose unpurchased naval identities and multiple faction airfields.
Shop now uses the Chaos isolation/access pipeline internally for both legacy
and new runs: only exact starter, permanent, AP, and purchased identities are
active. The player-facing mode and economy remain Shop Mode.

Shop mission-card bonuses now resolve in offer order without duplicate visible
effects. This does not consume gameplay RNG: the existing SHA-256 Shop stream
selects each raw effect, then duplicate boons or challenges advance through the
configured pool. Temporary power boons include their access reward plus safe
recharge and payload/damage buffs, so owning the power does not make the bonus
empty. Profile reset uses the existing write-ahead Shop transaction and permits
an explicit null run target; recovery writes the empty profile and removes only
the current Shop run file before clearing the journal.

Starting Buff Draft duplicated Free Buff Token while choosing only a buff type,
not its random unit target. New runs no longer generate draft buffs, and the
upgrade is hidden and unpurchasable. Its stable config ID and serialized run
field remain accepted so old profiles and active runs do not become invalid.

Yuri Prime's player clone is build-limited but was cloneable. A mission-owned
Cloning Vats could create the free copy while the paid copy was still queued;
the hero cap then left the infantry queue blocked. `MORPYURIPR` now uses
`Cloneable=no`, generated from the same roster override as its static template.
Its installed `BuildTimeMultiplier=1.2` is unrelated to this cap transition.

Shipwrecked places Airborne Humvees under the hostile UnitedStates House during
the Engineer/MCV opening. Tier 1 enemy firepower cloned `HumveeGun`, allowing
the opening guard to kill the objective Engineer before entry. Mission policy
now excludes only native `AHMV` from enemy tier-unit cloning in `ESHIP`; other
hostile houses and units still receive configured AI scaling.
