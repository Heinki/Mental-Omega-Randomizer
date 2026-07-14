# Mental Omega Randomizer Technical Reference

This document is the authoritative implementation reference. Player-facing option semantics are intentionally kept in [README_RANDOMIZER.md](README_RANDOMIZER.md#settings-reference) so they are not duplicated here.

## Runtime Architecture

| Component | Responsibility |
|---|---|
| `launcher_gui.py` | Entry point and packaged `--self-check` |
| `randomizer_app.py` | UI, deterministic seed construction, launch orchestration, progress state, and debug-log polling |
| `grid_progression.py` | Pure grid topology, corner trimming, explicit node states, unlock queries, and completion rules |
| `randomizer_map.py` | INI parsing/merging, generated-map rules, trigger marker structures, country buffs, and guarded direct buffs |
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

The packaged launcher uses PyInstaller one-file mode so the release contains only `MentalOmegaRandomizer.exe`. PyInstaller embeds Python, Tcl/Tk, and native extensions and expands them to its temporary `_MEI*` directory at startup. That extraction cannot be removed while retaining a self-contained PyInstaller/Tk executable, so unnecessary imports are kept out of the bundle and diagnostics use the base `logging.FileHandler` rather than `logging.handlers` and its unused mail/network stack. Persistent configuration and caches remain under `RandomizerLauncherData`; they are player data rather than application runtime files.

## Configuration and State

The launcher separates defaults from active progress:

| Data | Contents | Mutation rule |
|---|---|---|
| `config/mental_omega_randomizer.yaml` | Next-seed defaults, launch settings, and reserved Archipelago fields | Updated from current UI choices |
| `randomizer_state.json` | Active seed, frozen reward settings, mission order, optional grid/node state, checks, assigned rewards, completed checks/missions, and earned rewards | Updated only by seed generation or progress events |

This split is important for a future Archipelago client: option values generate a slot/seed once, while received locations/items update progress. The current `archipelago.*` keys are placeholders and have no network behavior.

## Mission Discovery and Seed Construction

Mission code, map filename, title, side, and briefing objective text are read from `INI/BattleClient.ini`. A mission with briefing objectives receives one check per objective plus a separate `victory` check. When no objective text exists, the launcher creates three placeholder objective checks plus victory.

Seed construction is deterministic for a seed string:

1. Filter eligible missions by campaign.
2. Build a staged shuffled mission order up to the mission goal.
3. In Grid Mode, map that order onto the corner-trimmed grid and persist each node's coordinates and initial state.
4. Allocate `objective count + 1 victory` checks per mission.
5. Allocate 1–10 reward slots to every check.
6. Build the complete reward plan with a random stream derived from `<seed>:seed-rewards`.
7. Store every check and assigned reward in state before play begins.

Grid progression is derived from completed mission codes and then written back as explicit `locked`, `unlocked`, or `completed` node state. Launch history adds the UI-only in-progress presentation before objective markers arrive. `completing_unlocks` provides the side-effect-free current unlock query used by mission details and victory logging. Grid dimensions are derived solely from the mission goal: balanced exact factors are preferred, then the densest balanced partial rectangle receives connected corner trimming. Layout version 3 migrates older manually sized boards without losing completed mission codes.

The Tk grid renderer keys its persistent tile-widget cache by a topology signature of dimensions, mission codes, and coordinates. A topology change rebuilds the board; ordinary selection reconfigures only the old/new tile containers, while reward and victory changes update cached tile labels and colors in place. Available nodes hide the banner widget rather than displaying a redundant label, and the body receives symmetric padding so the selection border remains visible along the top. Each tile uses nested border containers: the goal can retain its outer gold border while the inner container displays the normal light-blue selection border. This avoids window destruction, geometry churn, and visible selection flicker.

The Settings notebook page owns a canvas viewport and an inner controls frame. Canvas/content configure events synchronize the inner width and scroll region; mouse-wheel scrolling is accepted only while Settings is selected and the pointer is inside that viewport. The controls themselves remain ordinary ttk widgets and retain their existing callbacks and state rules.

The installed campaign counts are 30 Allied, 30 Soviet, 30 Epsilon, and 7 Foehn missions. Mixed-campaign construction caps Foehn at `ceil(mission_goal × 7 / 97)` (bounded to the installed count), while single-campaign Foehn seeds retain all seven eligible missions. This cap is applied during every staged-order selection pass, including the early starting pool and fallback fill.

Access rewards are unique by reward name. Seed planning prioritizes access, attempts a buff every fifth slot, and prefers a global buff every tenth slot while its stack cap permits. Unit buffs normally require prior planned access; buff-only seeds relax that requirement. Buff selection spreads upgrades across the least-buffed eligible units before stacking them further. Capped effects such as veterancy, cloaking, sensors, and self-healing cannot be repeated beyond their useful limit.

The mission-table reward fraction counts reward items, not check objects. The Rewards tab and mission hover text read the stored check reward arrays and display each `reward_display_name`, so a 10-item check shows all ten assignments.

## Generated Map Pipeline

Every mission launch starts from the cached extracted source, not the previous generated result. `prepare_hooked_map` performs the following operations in order:

1. Build the global controlled-tech lock set for the active seed.
2. Add mission-required Standard equivalents or Chaos all-faction production alternatives.
3. Merge already-earned access rules and remove their launcher locks.
4. Apply safe map-local country/house buffs to all player-controlled houses and optionally AI allied helpers.
5. Apply guarded direct unit/weapon buffs where no unsafe enemy uses the same global type.
6. Add a map-start trigger for already-earned building-free superweapons.
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

An action list containing terminal victory codes `1` or `67` is excluded from ordinary objective candidates. Remaining objective checks and candidate action IDs are paired in their encountered order with `zip`; extra briefing checks or extra actions cannot be matched automatically without mission-specific metadata.

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

The close callback verifies that the process and hook are still current, then uses `taskkill /PID <pid> /T /F` with a direct terminate fallback. If the game has already exited, no close is attempted.

Granting missed objective checks on victory is intentional. The objective/action mapping is incomplete on some maps, and a legitimate win must not leave the mission in a partially rewarded state.

### Watcher shutdown and failure behavior

Polling continues while the spawned process is alive. On exit the launcher records marker counts, clears the active process/hook, removes generated root maps, and removes any launcher-generated loose `rulesmo.ini` file.

If map extraction or hook preparation throws, the launcher logs the traceback, cleans generated root maps, and can still start the mission without automatic objective detection. If no victory candidate exists, the mission remains playable but automatic victory progress is unavailable; the hidden debug completion control is the recovery path.

An installed Mental Omega 3.3.6 audit recognized a victory action on all 97 extracted campaign maps. Objective matching is less complete: 58 maps had a different number of briefing objectives and hookable objective actions, while `SROAD` and `EGODSEND` exposed no standard objective-complete action. This is why victory reconciliation remains required.

## Technology Locking and Access

With access randomization enabled, every controlled unearned combat TechnoType receives `BuildLimit=0`. Regular units also receive a high TechLevel sentinel. Script-critical types use only the safer build limit so preplaced units and campaign TeamTypes can still exist.

MCVs, miners, Engineers, refineries, core production, and other base-operation essentials are outside the access pool. Earned access removes launcher locks and is forced to TechLevel 1 in future generated maps.

Before launch, the mission safety layer scans both placed structures and numbered House-section base plans for Construction Yards, barracks, factories, air commands, and shipyards. House plans matter for captured bases that are not initially present under `[Structures]`, such as Epsilon 07.

### Standard mixed-faction access

A selected single-faction campaign translates earned curated roles to foreign production families that the mission gives the player. The generated rule includes the physical factory prerequisite, native ownership, and active player countries. No combat role is granted without an earned equivalent; matching Engineers remain always available.

Foehn Standard draws bundled Allied/Soviet access peers. Standard All Campaigns draws Allied, Soviet, and Epsilon rewards. Full Foehn reward definitions are reserved for Chaos.

### Chaos access

Chaos always enables controlled-tech locking and draws all four factions. Each earned unit receives player-country ownership and Ares alternative prerequisite lists for every matching production family. The map's provided barracks/factory/airfield/shipyard/conyard can therefore produce the earned unit without granting foreign production structures.

Phobos `CameoPriority` bands keep production cameos in contiguous faction groups with the current player faction first.

## Buff Safety Model

### Failed-mission assistance

When enabled for a seed, every mission has an independent retry stack counter in `randomizer_state.json`. Closing the spawned game without a detected victory counts as a failed attempt. A subsequent `MapClass::Init_Clear` event while the same game process remains active counts as an in-game restart/reload; the initial scenario load is ignored. Assistance earned from an in-game restart is available on the next launcher-driven mission launch because the already-running game has already loaded its map.

Each stack uses the normal house/category multipliers for player infantry, vehicles/naval units, and aircraft: production time x`0.85`, cost x`0.80`, speed x`1.10`, incoming armor damage x`0.90`, and fire delay x`0.90`, with the existing safety caps. Accessible unit types also receive guarded health and weapon-damage x`1.15` plus `0.5` cells of weapon range per stack. Values compound with earned buffs. Mission Details and the compact Retry Assistance block in Unlocks show the selected mission's current stack count and cumulative effects in player-facing language such as "higher", "faster", "cheaper", and "damage taken lower" rather than raw signed multipliers.

For randomized-access seeds, that roster is the union of earned access, always-available faction essentials, mission access rules, player-owned placed units, and units in player-owned scripted TaskForces. This lets the first mission receive help before any rewards have been earned. When access randomization is disabled, the normal roster of every player-controlled/current mission faction is included as well. All-Campaign earned cross-faction access remains eligible. Completing a mission deletes its counter and cached roster; counters belonging to other missions remain untouched.

The assistance is written only into the generated copy of the selected mission map. Every assisted player-controlled house is always moved to a private map-local `MORASSIST*` country copy, even if its original country currently appears unshared. AI helper houses are included only when the seed's `buff_allied_helpers` setting is enabled; each included helper is moved with its assisted country group or into its own private copy. Enemy and unselected helper houses remain on their original countries, so they cannot inherit the country multipliers. Health uses global TechnoType fields and damage/range use global WeaponType fields, so those three bonuses pass through the established map-usage guard: if an enemy house uses the unit type or a shared weapon, that direct bonus is skipped and logged instead of buffing the enemy. No global INI or MIX archive is changed.

Campaign maps can define reusable TeamTypes with `House=Neutral` and assign their real runtime owner in `[AITriggerTypes]`. Unit-usage safety resolves that AI-trigger owner before classifying a global TechnoType or WeaponType as friendly or hostile. A placeholder Neutral owner is discarded only when an AI-trigger override exists and the same TeamType is not also created directly by a map action. Enemy-owned AI triggers and genuinely Neutral direct teams remain unsafe. Houses whose complete forces are scripted to transfer to the player are canonicalized to their map House section and participate in both direct and country-scoped buffs; this covers choice missions such as Foehn 04, where `Pacific` or `Chinese` forces can become player/support forces. Friendly mission-provided units are also added to the current map's buff-access set, so an earned unit buff applies to an allied/helper unit supplied by the mission even when the player has not earned that unit's separate access reward.

### House and country effects

House-supported rewards use map-local country data for production time, construction time, category cost, category speed, category armor, army ROF, and veteran lists. Every player-controlled house participates. With `buff_allied_helpers`, eligible allied AI houses also participate.

If an allied helper uses a country inherited by unsafe enemy houses, it can be moved to a private `MORALLY*` country copy. Parent-country relationships are included in safety analysis. This isolates the friendly effect without modifying the enemy parent.

Action `36` (`All change House`) transfers whose target is the player are included as friendly future users; debug-only transfer triggers are ignored.

### Direct unit and weapon effects

Health, sight, ammo, healing, cloak, sensors, guard range, weapon damage, weapon reload, and weapon range are TechnoType/WeaponType fields and therefore global within the map. The launcher applies them only when placed units and TaskForce usage show no unsafe enemy using the same unit. The bundled 3.3.6 weapon registry covers the complete playable roster and traces shared weapons through campaign-only/AI-only users, spawned aircraft and missiles, and projectile airburst/shrapnel payloads.

Damage changes target the real damaging stage instead of blindly changing launcher control weapons whose `Damage=1` is not the impact damage. Carrier and anti-sub payload weapons are followed to their spawned aircraft; V3, Dreadnought, and Akula missiles use their actual `[General]` normal/elite damage fields. Integer damage always increases by at least one. Weapons already at the engine minimum `ROF=1` are excluded from direct reload changes instead of displaying an upgrade that cannot reduce the value.

Unsafe direct changes are logged and skipped instead of powering up enemies. Starting, produced, and TeamType-created units all use the same global definition, so the safety decision covers all of them.

The all-campaign validation matrix processes all 97 installed missions, the normal roster for every player-controlled faction, optional allied helpers, scripted transfers, placed units, and AI-trigger TaskForces. The current matrix produced 9,239 verified higher damage fields plus 91 verified spawned-missile damage paths, with no partial modifier sets, unchanged numeric upgrades, or enemy leaks. At the unit/mission level, 3,744 of 4,607 damage-capable combinations applied and 863 were safely rejected because an enemy on that mission shared every relevant global type. The 863 figure is repeated unit x mission cases in a worst-case full-roster audit, not 863 unique weapons or rewards. Enemy-shared global types remain intentional safe skips; RA2/YR does not provide a reliable map-local country firepower field that could replace those global edits.

Map-local cloned combat types were tested as an isolation mechanism. Registering many inherited units, full weapons, and split TaskForces produced fatal incomplete weapon construction and severe live-game slowdown. That approach was removed; country copies remain limited to lightweight house-scoped effects.

## Building-Free Powers

Earned offensive, secondary, and aid powers use action `34` (`Add repeating Superweapon`) from player-owned map-start triggers. Aid entries are limited to player-facing faction delivery/reinforcement definitions; internal automatic spawn handlers and neutral tech-building powers are not rewards.

Large inventories are split into action lists of at most `16` grants and the
lists are staggered one second apart. The installed campaign maps use at most
`24` actions in any native list; emitting all `35` earned Chaos powers in one
list reproduced the cross-faction `C0000005` crash at `007C9B92`.

For earned aid instances, the generated map clears only the availability fields actually declared by that installed definition (`SW.RequiredHouses`, `SW.AuxBuildings`, `SW.NegBuildings`, or `SW.Designators`). This removes the original building/subfaction gate for Chaos without adding empty overrides to unrelated powers or changing recharge, cost, delivered types, targeting, or inhibitors.

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
| Foehn | Spinblade `39`; Megaarena `52`; Knightfall `72`; Sweeper Drop `76`; Signal Jammer `77`; Decoy Team `118`; Decoy Squadron `119`; M.A.D. Mine `133` |

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
| Player-only cloned TechnoTypes/WeaponTypes/TaskForces | Fatal weapon construction and unacceptable campaign runtime slowdown |
| Buffing a shared global type anyway | Would grant the same reward to enemy units |
| Building-free Elite Reserves | Action `34` crashes while creating its lab-bound internal production-state marker |

## Known Limits

- Objective checks are paired to recognized action lists by order; mission-specific mappings are still needed where briefing and action counts differ.
- `SROAD` and `EGODSEND` have no recognized standard objective-complete action in the installed audit.
- Some unusual alliance/house-transfer layouts need more map-specific data before allied-helper inclusion can be proven safe.
- Direct unit/weapon buffs are skipped when an enemy shares the global type.
- Matching power buildings may share the granted power instead of creating an independent copy.
- Blasticade has no effect until the player owns Blast Trenches; earning the power does not create them.
- Game-speed behavior needs validation across more campaign maps.
- Archipelago transport, slot data, item IDs, and location IDs are not implemented yet.
