# Mental Omega Randomizer Technical Reference

This document is the authoritative implementation reference. Player-facing option semantics are intentionally kept in [README_RANDOMIZER.md](README_RANDOMIZER.md#settings-reference) so they are not duplicated here.

## Runtime Architecture

| Component | Responsibility |
|---|---|
| `launcher_gui.py` | Entry point and packaged `--self-check` |
| `randomizer_app.py` | UI, deterministic seed construction, launch orchestration, progress state, and debug-log polling |
| `grid_progression.py` | Pure grid topology, corner trimming, explicit node states, unlock queries, and completion rules |
| `randomizer_missions.py` | Pure BattleClient parsing, faction normalization, mission staging, campaign caps, and deterministic ordering |
| `randomizer_ini.py` | Order-preserving INI/map parsing and one-pass bulk section merging |
| `randomizer_map.py` | Generated-map rules, trigger marker structures, country buffs, and guarded direct buffs |
| `randomizer_mission_safety.py` | Mission production discovery and Standard/Chaos access fallbacks |
| `randomizer_rewards.py` | Installed roster metadata, reward catalogue, role equivalence, stack limits, and display names |
| `randomizer_cameos.py` | On-demand MIX extraction and PCX decoding |

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
| `config/mental_omega_randomizer.yaml` | Next-seed defaults, launch settings, and reserved Archipelago fields | Updated from current UI choices |
| `randomizer_state.json` | Active seed, frozen reward settings, mission order, optional grid/node state, checks, assigned rewards, completed checks/missions, and earned rewards | Updated only by seed generation or progress events |

This split is important for a future Archipelago client: option values generate a slot/seed once, while received locations/items update progress. The current `archipelago.*` keys are placeholders and have no network behavior.

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

The Tk grid renderer keys its persistent tile-widget cache by a topology signature of dimensions, mission codes, and coordinates. A topology change rebuilds the board; ordinary selection reconfigures only the old/new tile containers, while reward and victory changes update cached tile labels and colors in place. Available nodes hide the banner widget rather than displaying a redundant label, and the body receives symmetric padding so the selection border remains visible along the top. Each tile uses nested border containers: the goal can retain its outer gold border while the inner container displays the normal light-blue selection border. This avoids window destruction, geometry churn, and visible selection flicker.

The Settings notebook page owns a canvas viewport and an inner controls frame. Canvas/content configure events synchronize the inner width and scroll region; mouse-wheel scrolling is accepted only while Settings is selected and the pointer is inside that viewport. Dark mode switches ttk/Tk palettes immediately and persists outside seed state. The canonical ttk `TLabelframe` style colors group interiors; a custom state-aware indicator replaces Clam's X with a white tick on an enabled gray box while disabled checks remain visibly distinct. Reward privacy is also immediate: Mission Details renders each assigned reward as `?????`, while Unlocks continues to reveal earned items.

The installed campaign counts are 30 Allied, 30 Soviet, 30 Epsilon, and 7 Foehn missions. The reviewed build split is 51 base-build, 27 true-no-build, and 19 production-no-build missions. By faction, true-no-build counts are Allied 7, Soviet 5, Epsilon 12, Foehn 3; production-no-build counts are Allied 5, Soviet 6, Epsilon 7, Foehn 1. Randomized mixed-campaign construction caps Foehn proportionally against the currently eligible pool, while single-campaign Foehn seeds retain every eligible mission. This cap is applied during both the protected opening and unrestricted remainder; Classic instead preserves the literal filtered catalogue prefix and records its actual faction counts. Mission List protects its first five entries. Grid Mode computes its protected cells from topology: one-start grids protect `(0,0)` and its existing orthogonal neighbors; two-start grids protect `(1,0)`, `(0,1)`, and every existing orthogonal neighbor of either start, normally six cells. Low-level missions are assigned to those cells before unrestricted missions fill the remainder. Foehn 02/03/04/06 and Foehn Op are excluded from protected openings while alternatives exist; only Foehn 01/05 receive early eligibility. A narrow Foehn-only pool falls back to late maps when the protected opening is larger than those two missions.

Access rewards are unique by reward name. Mission List seed planning walks reward slots linearly, prioritizes access, attempts a buff every fifth slot, and prefers a global buff every tenth slot while its stack cap permits. Grid Mode instead reserves slot zero of every topology-protected opening mission for a unit-access item when available, then shuffles all remaining `(mission, slot)` pairs across the entire board before running the same access/buff draw. This gives the easy start neighborhood a small guaranteed roster while preventing row-major mission storage from consuming all unique access in the top rows. A 100-seed audit of 97-cell one-start and two-start grids found unit access in every row, including the bottom, while Mission List remained front-loaded. Unit buffs normally require prior planned access; buff-only seeds relax that requirement. Buff selection spreads upgrades across the least-buffed eligible units before stacking them further. Veterancy, cloaking, sensors, and self-healing cannot repeat beyond their useful limit. Unique-unit `BuildLimit +1` is repeatable and adds one live slot per stack. Infantry speed stacks stop when the unit reaches its safe ceiling. The 222 single-type access rewards normalize their names from `BUFF_TARGETS`, correcting old/generic labels such as `Battlecruiser Access` to the installed `Trident Battleship Access`; legacy names alias to the normalized reward.

The mission-table reward fraction counts reward items, not check objects. Mission Details and mission hover text read stored check reward arrays and display each `reward_display_name`, so a 10-item check shows all ten assignments. The immediate privacy preference replaces assigned names in both views with `?????`; Unlocks still reveals earned rewards. Buff display names use `buff_effect_lines` instead of internal catalogue codenames: `Attack Sub Logistics` is presented as `Typhoon Attack Sub: Cost 20% cheaper`. Compact per-reward listings omit redundant stack suffixes; Unlocks combines duplicate rewards and shows their real cumulative stack count. Stored internal names remain stable for seed compatibility.

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

All Campaigns applies exact per-faction access. When the player captures foreign production, the mission rule adapts ownership only for earned TechnoType IDs belonging to that physical production family. A discovered foreign Construction Yard or player/scripted MCV prepares every matching production category so later barracks, factories, airfields, and shipyards still expose only earned IDs. It never substitutes role peers and has no unconditional basic-unit safety roster. Every generated map prepares exactly one complete installed-identity Engineer clone. Standard prefers the authoritative player faction when that production family is usable, otherwise the first usable family; Chaos selects the first usable family. If no production is statically visible, the player faction is prepared behind the generic `BARRACKS` prerequisite so scripted bases work without exposing a premature cameo. Engineer originals retain their effective installed/map country exclusions and add player countries to `ForbiddenHouses`—never `BuildLimit=0`—so player duplicates disappear without broadening or blocking intended AI/script production. Amphibious transports remain explicit progression essentials; optional Tier 1 starters are injected independently and do not relax exact access.

A selected single-faction campaign translates earned curated roles to foreign production families that the mission gives the player. The generated rule includes the physical factory prerequisite, native ownership, and active player countries. No combat role is granted without an earned equivalent; the single faction-appropriate Engineer remains available.

Map-local unknown buildings declaring `Factory=InfantryType` are special barracks. Every exact unlocked infantry ID receives that building as an independent prerequisite alternative, regardless of faction; the normal faction barracks remains another alternative. This covers Fallen Ashes `CAMINE`. A map that places `MWF`/`NAFIST`, including through a listed TaskForce, receives Stalin's Fist support: Standard adds `NAFIST` only to exact unlocked vehicle IDs matching the current Soviet or Epsilon player family. These special rules include explicit Tier 1 starters but never unearned access.

Foehn Standard draws bundled Allied/Soviet access peers. Standard All Campaigns draws Allied, Soviet, and Epsilon rewards. Full Foehn reward definitions are reserved for Chaos.

The optional Tier 1 starter roster models five explicit roles: ground infantry, anti-air infantry, ground vehicle, anti-air vehicle, and basic aircraft. Standard follows the established equivalent-access rule: the physical production family discovered in player placements, House base plans, or scripted/player MCV use selects the corresponding Allied, Soviet, or Epsilon starter. A detected MCV/Construction Yard also unlocks that family's AircraftType factory behind the matching Construction Yard; no base means no injected airfield. Campaign side and current player-house country do not select the unit family. All Campaigns supports all three production families; Foehn-only Standard supports its Allied/Soviet operating families. Starter access items are excluded from reward planning, while their role markers seed equivalent buff eligibility before any check is completed.

A 97-map starter audit matched every injected Standard starter section exactly to discovered physical production categories. Focused regressions verify that `ESHIP` maps an Epsilon player to Allied starters through its captured Allied base, `AGHOST` maps an Allied campaign mission to Epsilon starters through Epsilon production, and Foehn-only `FREMNANT` excludes both Epsilon and native Foehn starters.

### Chaos access

Chaos always enables controlled-tech locking and draws all four factions. Each exact earned unit receives player-country ownership and Ares alternative prerequisite lists for every matching production family. Detected special barracks are added for all earned infantry and `NAFIST` for all earned vehicles. The map's provided barracks/factory/airfield/shipyard/conyard can therefore produce the earned unit without granting foreign production structures or any additional unit access when another factory is captured.

Chaos Tier 1 starters use a separate deterministic stream, `<seed>:starting-tier-one`, so mission order and normal reward RNG calls remain unchanged. Faction order is shuffled once across the four guaranteed ground roles, producing exactly one Allied, Soviet, Epsilon, and Foehn unit. A fifth seeded role selects Stormchild, Foxtrot, or Dybbuk-Attacker. When any player MCV/Construction Yard is detected, the chosen AircraftType's native airfield is unlocked from that base family. The 97-map audit covered 43 base-capable maps, seven airfield-only maps, and 40 maps with no production; all expected airfield/aircraft rules matched and no map without base construction received an airfield.

Phobos `CameoPriority` bands keep production cameos in contiguous faction groups with the current player faction first.

## Buff Safety Model

### Failed-mission assistance

When enabled for a seed, every mission has an independent retry stack counter in `randomizer_state.json`. Closing the spawned game without a detected victory counts as a failed attempt. A subsequent `MapClass::Init_Clear` event while the same game process remains active counts as an in-game restart/reload; the initial scenario load is ignored. Assistance earned from an in-game restart is available on the next launcher-driven mission launch because the already-running game has already loaded its map.

Each stack uses the normal house/category multipliers for player vehicles/naval units and aircraft: production time x`0.85`, cost x`0.80`, speed x`1.10`, incoming armor damage x`0.90`, and fire delay x`0.90`, with the existing safety caps. Infantry production/cost/armor remain category effects, but infantry speed is a guarded direct TechnoType value capped at Speed `10`. Accessible unit types also receive guarded health and weapon-damage x`1.15` plus `0.5` cells of weapon range per stack. Values compound with earned buffs. Mission Details and the compact Retry Assistance block in Unlocks show the selected mission's current stack count and cumulative effects in player-facing language such as "higher", "faster", "cheaper", and "damage taken lower" rather than raw signed multipliers.

For randomized-access seeds, that roster is the union of earned access, always-available faction essentials, mission access rules, player-owned placed units, and units in player-owned scripted TaskForces. This lets the first mission receive help before any rewards have been earned. When access randomization is disabled, the normal roster of every player-controlled/current mission faction is included as well. All-Campaign earned cross-faction access remains eligible. Completing a mission deletes its counter and cached roster; counters belonging to other missions remain untouched.

The assistance is written only into the generated copy of the selected mission map. Campaign trigger owners are country IDs, so player and helper houses remain on their original countries. Country/category multipliers are applied only when every active house in that country family belongs to the assisted coalition; otherwise that country-level part is skipped and logged. With `buff_allied_helpers`, reviewed helper houses receive the same safe country assistance. Health uses global TechnoType fields and damage/range use global WeaponType fields, so those bonuses pass through clone isolation or the map-usage guard. No global INI or MIX archive is changed.

Campaign maps can define reusable TeamTypes with `House=Neutral` and assign their real runtime owner in `[AITriggerTypes]`. Unit-usage safety resolves that AI-trigger owner before classifying a global TechnoType or WeaponType as player or non-player. A placeholder Neutral owner is discarded only when an AI-trigger override exists and the same TeamType is not also created directly by a map action. Enemy-owned, helper-owned, and genuinely Neutral teams remain unsafe for raw player buffs.

### House and country effects

House-supported rewards use map-local country data for production time, construction time, vehicle/aircraft category speed, category cost, category armor, army ROF, and veteran lists. Player-controlled houses always participate. Infantry speed deliberately bypasses `SpeedInfantryMult` so a per-unit hard ceiling can be enforced. `buff_allied_helpers` also targets reviewed helper countries when their country family is not shared with a denied house; clone IDs replace exact originals in affected helper veteran lists.

Veterancy uses `VeteranInfantry`, `VeteranUnits`, `VeteranAircraft`, and `VeteranBuildings`. Trainable defenses such as the Allied Grand Cannon must use `VeteranBuildings`; `VeteranDefenses` is not an engine key. Empty cinematic/neutral placeholder houses that inherit a player country do not block that country's rewards when they own no placed or scripted TechnoTypes, are allied to the assisted coalition, and have no scripted hostile transition.

If an allied helper uses a country inherited by unsafe enemy houses, the country-level reward is skipped for that helper. Parent-country relationships are included in safety analysis. The house is not moved to a synthetic country because doing that disconnects triggers owned by its original country.

Unit-access ownership is narrowed at map launch to the current player countries plus safely isolated configured helper countries. Factory eligibility can follow `ParentCountry`, so clone/access `Owner` includes the complete parent chain while `RequiredHouses` retains only the concrete allowed countries. This fixes custom player countries in `EBLOOD` (`PC-Player` -> `PsiCorps`), `SAWAKE` (`PlayerEscort` -> `USSR`), and `SRAVEN` (`Player` -> `USSR`) without granting their clones to hostile houses that share the parent. A helper country is omitted from country-scoped buffs when a denied active house shares or inherits it. The house itself is never reassigned because that breaks country-owned mission triggers. Unsafe country/category and direct unit/weapon effects remain skipped.

### Direct unit and weapon effects

Health, sight, ammo, healing, cloak, sensors, weapon damage, weapon reload, and weapon range are TechnoType/WeaponType fields and therefore global within the map. The launcher applies them only when placed units and TaskForce usage show no unsafe enemy using the same unit. The bundled 3.3.6 weapon registry covers the complete playable roster and traces shared weapons through campaign-only/AI-only users, spawned aircraft and missiles, and projectile airburst/shrapnel payloads.

Damage changes target the real damaging stage instead of blindly changing launcher control weapons whose `Damage=1` is not the impact damage. Carrier and anti-sub payload weapons are followed to their spawned aircraft; V3, Dreadnought, and Akula missiles use their actual `[General]` normal/elite damage fields. Integer damage always increases by at least one. Weapons already at the engine minimum `ROF=1` are excluded from direct reload changes instead of displaying an upgrade that cannot reduce the value.

Capability eligibility is also derived from the installed 3.3.6 TechnoTypes. New pools omit self-healing for already-self-healing types, cloak for types with normal/staged/stop/attach-effect cloak, and sensors for types with `Sensors=yes` or `SensorArray=yes`. Utility-only targets (spies/infiltrators, engineers, scanner-only types, and explicit `NotAWeapon` types) cannot receive damage, reload, or range rewards. Functional nondamaging support weapons remain eligible when their reload/range fields are real gameplay controls. Mobile `Trainable=no` types cannot receive Veteran Training; legacy Engineer, Spy, Suppressor, and equivalent invalid veteran rewards canonicalize to the same unit's Armor Plating reward. Drakuv and Harbinger are removed entirely from production access/buff pools because they are aid payloads. Infantry already at or above the safe ground ceiling do not receive no-op Mobility rewards. Exactly 16 installed trainable hero/unique types with `BuildLimit=1` receive the repeatable Command Capacity reward.

Ares self-healing supports every TechnoType, including BuildingTypes, but its default amount is only one hitpoint per normal repair interval. Defense Repair Systems now writes `SelfHealing.Amount` equal to 1% of installed maximum strength, making the effect observable while retaining the normal repair interval. Mobile-unit healing remains native. The former army-wide fire-rate reward wrote `ROF` onto CountryType sections, but installed Mental Omega uses that multiplier only on difficulty sections and live testing showed no unit effect. New seeds omit it. Legacy Rapid Fire rewards canonicalize to the same target's working cloned-weapon `reload` reward. Retry assistance now applies firing speed through those guarded cloned WeaponTypes instead of a country field.

The former `guard_range` / Targeting Package reward was removed. `GuardRange` increases autonomous acquisition distance rather than weapon range and can pull units out of position into unsafe engagements. New seeds cannot generate it, and existing stored Targeting Package rewards canonicalize to the same unit's Recon Package vision reward.

Unsafe raw type changes are never written onto an enemy/helper-shared original. Mandatory narrow player clones isolate supported direct TechnoType and WeaponType effects, including buildable defenses. Unsupported indirect/spawned paths remain skipped and logged.

An experimental Phobos/Ares runtime-House AttachEffect pulse was tested and removed. Live testing showed that its owner filter did not reliably isolate the player and could buff enemy objects. Action `34` also exposed each hidden pulse as a continuously recharging default Mental Omega cameo despite `SW.ShowCameo=false`. The launcher therefore creates no `MORBuff*` superweapons, weapons, or warheads.

The all-campaign validation matrix processes all 97 installed missions, the normal roster for every player-controlled faction, optional allied helpers, scripted transfers, placed units, and AI-trigger TaskForces. It produced 9,239 verified higher damage fields plus 91 verified spawned-missile damage paths, with no partial modifier sets, unchanged numeric upgrades, or enemy leaks. At the unit/mission level, 3,744 of 4,607 damage-capable combinations applied and 863 were safely rejected because an enemy on that mission shared every relevant global type. Those enemy-shared combinations remain intentional safe skips.

The first map-local combat-clone experiment registered many copied units, full copied weapons, and split TaskForces. It produced fatal incomplete weapon construction and severe live-game slowdown, so that broad full-copy path remains removed. Country copies also remain removed because they detach campaign triggers from reassigned houses.

Narrow player TechnoType cloning is mandatory launch behavior, not a setting and not seed-frozen. Legacy `generation.experimental_player_unit_clones` values are ignored and removed from newly saved settings. Clones are created only for currently relevant direct buffs or player/helper production. The first live run proved Ares `$Inherits` unsafe here: `[MORWSCARHALFTRACKGUNX]` contained only buff overrides, so WeaponType construction failed because inherited `Projectile=InvisibleWork` was unavailable. Narrow clones contain complete installed values, with `$Inherits` removed. Buildable player clones deliberately take identity/art/name data from the installed unit or defense and copy only mission production gates; this prevents map role substitutions such as `MORALES/YUNRU -> CYBO` and `SHK -> SHOCK` from creating duplicate cameos. A clone whose original omits `Image=` receives `Image=<original ID>` because the engine would otherwise seek art under the new `MORP...` ID.

Defense cloak, health, sight, sensors, healing, and weapon damage/range/reload fields cannot be house-scoped; modifying the original gives every enemy copy the buff. Every buildable buffed defense therefore receives a registered standalone `BuildingType` clone and cloned weapons. Player and opted-in helper placements use it. Exact numbered helper House base plans use the same clone. Clone eligibility is gated by concrete `Owner`/`RequiredHouses` country IDs, so hostile `ParentCountry` descendants do not justify skipping helper plans; that former country-buff safety test left the Europeans/Pacific bases in `AWITHER` unbuffed. Enemy placements, plans, TechnoTypes, and WeaponTypes remain original; native helper fallback ownership stays separate. Country `VeteranBuildings` entries follow the clone. The helper-off path rewrites none of the helper references. The current 42-map pressure pass verified 106 configured helpers, 804 friendly base-plan and 887 friendly placement rewrites while preserving 2,309 enemy plans and 6,321 enemy placements.

TechnoType IDs embedded in Events/Actions must follow the cloned mission object. Trigger ownership alone is insufficient: `EMIGDAL` creates the player's `LIBRA` from a `PsiCorps` TaskForce but its mission-failure event is owned by `UnitedStates`. Leaving that event on `LIBRA` while the team creates `MORPLIBRA` makes the mission fail immediately. The same invariant applies to locked, reference-only map aliases: `SNOISE` watches `RAVA`, `RAVA2`, and `RAVA3`, so its three placed/TaskForce Drakuv identities and Event 61 references must all become their matching `MORP...` IDs. TaskForce replacement therefore covers every friendly clone, not only sidebar-buildable sources; enemy consumers remain native and shared TaskForces are split by their resolved runtime houses. If every resolved map consumer of a cloned source type belongs to the player/opted-in helpers, all exact Event/Action references follow the clone regardless of story-trigger owner. Shared types still change only in player/helper-owned trigger lists. Event 61 is an exact TechnoType destroyed/nonexistent test; when such a shared type has friendly and denied consumers but its event belongs to an outside story house, the launcher keeps that map's type native and lets the normal usage guard skip its unsafe direct buff. This protects ambiguous Volkov, Yunru, Siegfried, Rahn, convoy, and similar scripts rather than guessing and firing an instant loss/objective event. A 13-map integration audit kept all 15 ambiguous map/type cases native. A separate 97-map reference audit checked 1,003 exact references: 262 globally friendly and 325 friendly-owner references were rewritten, while 416 shared/enemy references stayed original; all rewritten action lines remained within 511 bytes. The follow-up hero-objective audit covered all 97 maps: 85 maps contained 707 Event 61 lists with 863 exact references. It checked all 84 cloned loss references, 14 matching friendly placements, and 85 matching friendly TaskForce slots with zero identity mismatches or over-limit action/event lines.

The first successful isolation tests kept enemy Conscripts and Soviet 12 Flak Troopers unbuffed. `FBEYOND` exposed two BuildLimit traps: `-1` made a clone one-build-only, while `0` prevented an Autocreate team from assembling. Those lock/one-build values are removed, but installed positive live-unit caps are preserved exactly (`1` for Centurion, Libra, Volkov, and the other unique units; `2` for Orcinus). The optional `generation.unlimited_hero_units` setting removes the cap only from the isolated player/selected-helper clone of the 16 trainable capped hero/unique identities. The mutually exclusive Command Capacity reward adds one to that clone per earned stack. Script-only positive caps and capped defenses never enter either feature; all enemy/native originals keep their authored caps. Additive helper pools exclude every positively capped type so an extra team cannot stall on its count. A buildable clone takes its cap from the installed identity, not a campaign section that reuses the same ID for a different hero: `SHAND [SUPR]` is capped Reznov, while the earned Suppressor clone remains normally unlimited. Native mission aliases and helper fallbacks retain their map-authored caps. A 97-map pressure audit generated 1,544 four-stack clones with cap `5` while native caps stayed `1`; eight ambiguous shared hero-event cases stayed native through the established mission-safety guard. Later `FBEYOND`, `AWITHER`, and `SHAND` testing exposed the deeper fault: campaign AI can request native country-roster IDs outside map TaskForces. Hiding those originals or rewriting only known TaskForces leaves the factory waiting forever while structure production continues. Native helper source IDs now regain their installed/map TechLevel, prerequisites, and explicit concrete helper ownership. They are hidden from the human through positive ownership, while the player's buffed copy remains the sole player cameo.

`FBEYOND` uses seven friendly AI houses. `FoehnNavy House` is the separate naval helper. The unselected base is controlled by the difficulty-specific `China2/3/4 House` or `Pacific2/3/4 House`; these six houses must be allies, not denied enemies. `Chinese House` and `Pacific House` remain the hostile main houses. `UnitedStates` controls orchestration triggers. `SellMCV House` is also friendly scripting infrastructure and inherits `Guild1`; listing it as an enemy made the country-safety guard skip all player `Guild1` multipliers, including `ROF` and veteran production. It is now in the ally allowlist.

The failed helper experiment substituted complete rosters and leaked foreign units into Standard player sidebars. The corrected design is surgical. Existing helper TeamType timing, ScriptTypes, triggers, and composition counts stay intact, but compatible placement/TaskForce unit slots use buffed clones. Native source IDs simultaneously regain native TechLevel, prerequisites, and explicit helper ownership for dynamic country-roster requests outside TaskForces. Mission production discovery considers only player-controlled factories or proven full-force transfers, never enemy/helper factories. Standard All-Campaign launch access is narrowed to the authoritative `[Basic] Player` faction before rules, clones, helper pools, or action-106 unlocks are generated. Secondary `PlayerControl=yes` scripting houses do not broaden the current mission's base reward faction. Proven foreign player production can still add only exact earned IDs through mission access rules. This prevents `SHAND` from turning its map-local `[SUPR]` hero alias into an installed Suppressor clone and prevents helper template pooling from adding Brute/Libra prerequisites to Soviet production. A catalogue contradiction that labeled Epsilon `SQD` as Soviet was also corrected.

Three base-build missions use object-level ownership changes that are not full-house Action 36 transfers. Production discovery therefore has a separate, narrow mission policy: `EBREED` reads PsiCorps2's captured `YACNST`, `EBLOOD` reads PC-Base's `YABRCK`/`YAWEAP` in addition to the already detected PC-AI transfer, and `SRAVEN` reads the Guild3 structures tagged `01000314` that Objective 2 changes to the Player house (`NACNST`, `NAHAND`, `NAWEAP`, and `NAAIR`). These source houses never enter helper/buff allowlists, so initially hostile or scripted owners remain unbuffed. Generated access remains required by the authoritative concrete player country, while `Owner` also carries its production parent. The 97-map regression checked 12,223 buildable clones and 23,272 Standard/Chaos access rules with zero missing concrete or parent ownership gates.

Chaos is unit-specific for production/cost/speed/armor. Cost, speed, and armor already had direct clone values, but production was previously omitted after category-country generation was suppressed in unit-specific mode. Clones now receive cumulative `BuildTimeMultiplier` with the same `0.85` stack and `0.35` floor. Standard still prefers safe country/category multipliers except for infantry speed, which always uses an isolated direct clone. An installed 3.3.6 audit found Chitzkoi and Libra are the fastest ground InfantryTypes at Speed `10`; speed rewards and retry assistance can raise slower ground infantry only to that value. Faster airborne InfantryTypes keep their native Speed and are never increased by Mobility rewards. The 97-map pressure audit generated 5,423 isolated infantry-speed clones; nine ambiguous shared-event cases stayed native. If the player's custom country shares a parent with denied houses and no buffed helper shares the clone, native-faction isolated clones receive direct production/cost/speed/armor fallback values instead. This preserves earned effects without changing enemy originals or expanding fallback cloning through role-equivalent foreign factions.

Player production and additive helper teams share one standalone earned clone rather than registering a second helper TechnoType. Its owners include only the player and selected helper countries, and helper production receives alternative prerequisites copied from the native slot. Source `FactoryOwners` and negative prerequisite restrictions are removed because they can leave a foreign helper team unfilled. Standard additive substitutions match the source TaskForce slot's faction; Chaos alone permits cross-faction substitutions. Native helper TaskForces use their restored originals. Native fallback ownership is tracked separately from buffed-clone ownership: when `buff_allied_helpers` is off, helper TaskForces, clone owners, and helper Veteran lists remain native/unbuffed while the queue fallback stays operational. No `MORAI...` IDs appear.

Parallel unlock variants remain bounded to eight teams per helper country and eight earned types per production class. A map-authored Autocreate TeamType without an AITrigger receives only a parallel TeamType/TaskForce and reuses action 13; native AITrigger conditions are copied when present. Added TaskForces discard every untouched template member, because one hidden campaign-only member can stall the whole team. Custom helper countries follow `ParentCountry` chains during discovery, but clone isolation uses concrete country IDs without a conflicting parent `ForbiddenHouses`. The final maximum-pressure audit of all 42 configured-helper maps started from 543 source TaskForces and produced 786 compatible native/parallel helper TaskForces. It verified 1,026 helper clone references and 273 native source targets: every compatible helper consumer used a repeatable, correctly owned level-1 clone, every native fallback remained unlimited, every produced clone retained veterancy, and no duplicate player identity or veteran overflow existed.

Country veteran lists require exact TechnoType IDs. `VeteranUnits=ABRM` does not affect `MORPABRM`; exact originals are replaced for countries that actually produce the clone. `Trainable=no` originals and clones are never added. On a shared player country such as `SHAND`'s USSR, earned veteran targets force standalone player clones even when veterancy is their only buff. Appending every clone once made `VeteranUnits` reach 755 characters and parse as `[country]VeteranUnits=J`. All lists are capped at 480 UTF-8 bytes. Helper-country generation first prioritizes clones referenced by native and parallel helper TaskForces, then other clones, then native fallback IDs. This fixed late-list omissions such as Foehn `China2/3/4` Aegis/Carrier and `FPOINT` Guild1 Dragonfly/Hailstorm/Blizzard/Armadillo. Allied 23, Soviet 24, Epsilon 24, Foehn 4, and the final 42-map pressure audit produced zero missing clone veterancy or over-limit values. A later 97-map Standard plus 97-map Chaos regression pass verified exact primary faction selection, no enemy clone references, all 20 mobile positive-cap definitions, no capped additive helper assignments, no duplicate player originals, and no invalid or over-limit generated veteran values.

## Building-Free Powers

Earned offensive, secondary, and aid powers use action `34` (`Add repeating Superweapon`) from player-owned map-start triggers. Aid entries are limited to player-facing faction delivery/reinforcement definitions; internal automatic spawn handlers and neutral tech-building powers are not rewards.

Large inventories are split into action lists of at most `16` grants and the
lists are staggered one second apart. This also keeps every generated action
line below the engine's `512`-byte parser cutoff. Emitting all `35` earned Chaos
powers in one line reproduced the malformed-action `C0000005` crash at
`007C9B92`.

The launcher extracts the complete installed `RULESMO.INI` registry and creates a new map-local `MOR...` copy for every earned power. Only the copy receives the building-free profile. Original superweapon sections remain byte-for-byte/effectively unchanged, so mission triggers can keep using their native power definitions for different scripted purposes. Existing map-local custom types are counted before randomizer types. Numeric keys such as `20000=` are list labels, not runtime indices; action `34` uses the calculated append position after the 135 installed and all native map-local types. Granting the earlier `5000=KnightfallALT` label as runtime index `5000` caused a null lookup and `C0000005` at `006CB569`.

Ares limits type IDs to 24 characters. Prefixing the complete source name produced invalid 26-character IDs `MORAmericanParaDropSpecial` and `MORPsychicDominatorSpecial`; this was a length failure, not an index collision. Clone IDs now omit the redundant `Special` suffix (for example `MORAmericanParaDrop`) and use a deterministic short hash fallback if a preferred ID is too long or already exists in installed rules/the current map. A cross-campaign audit compared all 45 active generated IDs (43 granted powers, ChronoWarp helper, and Kingsnake portal) across all 97 maps: no collisions, duplicates, or IDs over 24 characters. The longest generated ID is 19 characters. Per-map numeric list labels are also allocated around native keys before writing.

All 35 player-facing aid definitions have an entry in `AID_POWER_MAP_CONFIGS`. The copy sets `IsPowered=false` where needed and clears declared faction/building/designator gates. Paladin Aid disables inherited automatic targeting and does not inject the unusable external `SP_RANGE` designator. Knightfall preserves installed `RechargeTime=6.5` and resets inherited `SW.RangeMaximum=20` because a granted copy has no source building from which to measure range. M.A.D. Mine, Naval Mine, Drakuv, Ruiner, and Kingsnakes also clear inhibitors and source-range limits and permit targeting into shroud; their native land/water restriction remains. Kingsnakes delivers a complete map-local `MORF_KSNAK` copy with `PoweredBy=` instead of changing the global `F_KSNAK`. Drakuv `RAVA` and Harbinger `HARB` are `Trainable=no` aid payloads: they are excluded from access/buff pools and random tech locks, while old stored access/buff rewards retire without injection. `CANMIN`, `RAVA`, `HARB`, `RUINER`, and all original mission objects remain unchanged.

Offensive and secondary copies also set `IsPowered=false`. Chronoshift uses a copied `MORChronoWarp` dependent instead of the mission's `ChronoWarpSpecial`. Its installed targeting still moves only team vehicles/units; selecting infantry, enemies, or an empty source area legitimately produces no movement. Ten campaigns override shared lightning globals, and Soviet 16 `SFIRE.MAP` specifically sets `LightningDamage=1`, `LightningHitDelay=40000`, and `LightningScatterDelay=40000` for its scripted Ion Storm. The copied Lightning Storm therefore receives explicit installed 3.3.6 availability, recharge, damage, range, timing, cloud, bolt, explosion, and sound values without rewriting the mission's original storm. A 97-map registry/effective-merge audit verified 43 active reward copies plus the ChronoWarp helper on every map; runtime reward-clone indices ranged from `135` to `198`, with all native map entries preserved in front.

`MORV3TestSpecial` proves a power can be wholly new rather than copied. Its preserved config uses `UnitDelivery`, the Airborne icon, zero cost, a 0.5-minute recharge, and delivers 20 player-owned `V3` types on land. The config is currently disabled and omitted from new reward pools; legacy test rewards canonicalize to a retired non-injected entry.

`ZephyrBeaconSpecial` delivers neutral `ZTARGET`; it is a targeting beacon for already-owned `HOWI` Zephyr Artillery, not a standalone bombardment. A guaranteed minimum barrage would require a custom weapon/projectile/warhead helper or a materially different delivery power, not a safe one-key override.

Installed 3.3.6 offensive and secondary indices are:

| Faction | Offensive power (index) | Secondary power (index) |
|---|---|---|
| Allies | Lightning Storm (`2`) | Chronoshift (`3`; the engine handles its ChronoWarp follow-up) |
| Soviets | Tactical Nuke (`0`) | Invulnerability (`1`) |
| Epsilon | Psychic Dominator (`7`) | Rage (`28`) |
| Foehn | Great Tempest (`48`) | Blasticade (`47`) |

Installed aid/reinforcement indices are:

| Faction | Power indices |
|---|---|
| Allies | Airborne `6`; Bloodhounds `26`; Zephyrobot `34`; Lightning Rod `51`; Ultra Miner `61`; Kingsnakes `126`; Paladin Aid `128` |
| Soviets | Repair Drone `13`; Tank Drop `16`; Instant Shelter `29`; Motor Ambush `32`; Naval Mine `60`; Terror Drop `62`; Flame Tower `68`; Drakuv Prison Vehicle `70`; Repair Drones `124`; Disruptor `125` |
| Epsilon | Risen Monolith `15`; Scout Raven `18`; Vision `21`; Magnetic Beam `30`; Libra Clones `33`; Bloatick Trap `36`; Quick Fort `86`; Ruiner `93`; Hijackers `108` |
| Foehn | Spinblade `39`; Megaarena `52`; Knightfall `72`; Harbinger `75`; Sweeper Drop `76`; Signal Jammer `77`; Decoy Team `118`; Decoy Squadron `119`; M.A.D. Mine `133` |

Action `129` is not used because it changes the charge of a building-backed instance. A constructed matching building may consolidate with the granted instance; independent duplicate cameos are not guaranteed.

Blasticade is intentionally not replaced by Golden Wind. It is the documented Foehn support superweapon and still needs owned Blast Trench objects to produce a barrier; the access pool already contains a separate Blast Trench reward.

`EliteReservesSpecial` (`100`) is not eligible. Its `UnitDelivery` creates the invisible `F_ERESB` production-state marker through a Soviet advanced lab instead of delivering a normal targetable reinforcement. The 2026-07-14 crash reports consistently ended while action `34` processed Elite Reserves: it was last in the Soviet and Chaos grant lists and second-to-last in the Foehn list, while successful Allied/Epsilon lists did not contain it. Legacy stored rewards are canonicalized to a retired, non-injected entry.

## Cameo Pipeline

The Unlocks view resolves unit `Image` and `CameoPCX` values from installed `rulesmo.ini` and `artmo.ini` files inside Mental Omega MIX archives. Superpower rewards use the `SidebarPCX` value from their installed superweapon section, covering offensive, secondary, and aid/reinforcement powers without a manually maintained filename table. Only requested PCX members are extracted. A standard-library decoder converts indexed PCX data to cached PNG files, so Pillow and replacement artwork are unnecessary.

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
| Building-free Elite Reserves | Action `34` crashes while creating its lab-bound internal production-state marker |

## Known Limits

- Runtime discovery, trigger matching, ownership analysis, and reward injection have been audited only against the original Mental Omega campaign maps. Custom maps, funmaps, map packs, rules edits, and other gameplay modifiers are unsupported and must be reproduced on a separate fresh installation before they are treated as Randomizer defects.
- Objective checks are paired to recognized action lists by order; mission-specific mappings are still needed where briefing and action counts differ.
- `SROAD` and `EGODSEND` have no recognized standard objective-complete action in the installed audit.
- Temporary allies that are scripted to become enemies cannot safely receive static helper buffs; they are deliberately excluded even during their friendly phase.
- Mandatory standalone player clones have static 97-map generation coverage plus successful live isolation, sidebar, and helper-production tests. Loading cost, save/load behavior, and wider campaign trigger compatibility still need continued validation.
- Direct unit/weapon buffs are skipped when a denied enemy shares the affected global type.
- Matching power buildings may share the granted power instead of creating an independent copy.
- Blasticade has no effect until the player owns Blast Trenches; earning the power does not create them.
- Game-speed behavior needs validation across more campaign maps.
- Archipelago transport, slot data, item IDs, and location IDs are not implemented yet.
