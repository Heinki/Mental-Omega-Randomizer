# Mental Omega Randomizer User Guide

This is the authoritative player-facing guide for seed settings and reward behavior. Installation, building, and source layout are maintained in [README.md](README.md); implementation details are maintained in [TECHNICAL_FINDINGS.md](TECHNICAL_FINDINGS.md).

The launcher is currently standalone and offline. The option keys below are intentionally stable so they can later become Archipelago world options without redefining their meaning.

> **Installation requirement:** use the executable in a new, separate, unmodified Mental Omega installation. Only the original Mental Omega campaign maps have been tested. Custom maps, funmaps, map packs, modified rules, and other gameplay modifiers are unsupported; see [Quick Start and supported game content](README.md#quick-start).

## Seed Lifecycle

- **Generate New Seed** replaces the active run, creates a new seed identifier, mission order, objective/victory checks, and complete reward plan.
- Seed-generation settings are copied into `randomizer_state.json`. Changing the Settings tab afterward affects the next seed, not the active seed.
- Difficulty and game speed are launch settings and may be changed between missions.
- **Classic** mode preserves the installed campaign order, opens only the first mission, and opens the next mission after each victory.
- **Mission List** mode randomizes the linear mission order, opens the first three missions, and opens one additional mission after each victory.
- **Grid Mode** opens the top-left node, or the two orthogonal neighbors of top-left when **Two start positions** is enabled. A victory opens the node's up/down/left/right neighbors; diagonal nodes do not open.
- The generated mission order contains **Missions to finish** missions. Classic and Mission List finish after that many victories. Grid Mode finishes when its bottom-right endgoal is completed, then releases every remaining reward and opens every unfinished node for optional cleanup.

## Settings Reference

### Main launcher settings

| UI setting | Standalone/AP option key | Values and default | What it changes | Timing |
|---|---|---|---|---|
| Seed | `seed` | Generated `MO-XXXXXXXX` identifier; blank config default | Seeds the deterministic mission order and reward plan. The **Generate New Seed** button creates a fresh identifier. | Seed generation |
| Campaign | `campaign_filter` | `All Campaigns`, `Allies`, `Soviets`, `Epsilon`, `Foehn`; default `All Campaigns` | Restricts the mission pool. In Standard mode it also selects the campaign-appropriate reward pool. Foehn Standard uses bundled Allied/Soviet roles because those campaigns operate those production families. | Seed generation |
| Missions to finish | `mission_goal` | `1` through the number of eligible missions; default `15` | Number of mission victories required to finish the run and therefore the length of the generated mission order. | Seed generation |
| Include true no-build / fixed-unit missions | `generation.include_no_build_missions` | `false`/`true`; default `true` | Includes the 27 reviewed missions played only with fixed/scripted units, heroes, or map powers and no player production. Turning it off removes that category from the eligible mission pool. | Seed generation |
| Include no-build missions with production | `generation.include_no_build_production_missions` | `false`/`true`; default `true` | Includes the 19 reviewed missions without normal base building but with limited unit production. Turning both no-build inclusion settings off leaves the 51 base-build missions. See [all 97 classifications](MISSION_CLASSIFICATION.md). | Seed generation |
| Prioritize included no-build missions in opening | `generation.prioritize_no_build_missions` | `false`/`true`; default `false` | Fills protected Mission List or Grid opening positions with the lowest-stage eligible missions from whichever no-build categories are enabled. Ignored by Classic ordering. | Seed generation |
| Progression | `progression_mode` | `Classic`, `Mission List`, `Grid Mode`; default `Mission List` | Selects original campaign order, a randomized linear mission list, or the orthogonal-neighbor grid described below. | Seed generation |
| Start with two available missions | `grid_two_start_positions` | `false`/`true`; default `false` | Starts Grid Mode from the cells directly right of and below top-left instead of top-left itself. Requires at least four missions. | Seed generation |
| Difficulty | `difficulty` | `Casual`, `Normal`, `Mental`; default `Normal` | Writes the selected campaign/human difficulty to launch configuration. It does not change rewards. | Every launch |
| Game speed | `game_speed` | `0 - Slowest` through `6 - Fastest`; default `3 - Medium` | Writes the engine speed and launches with `-SPEEDCONTROL`, keeping the in-game speed control available. It does not change rewards. | Every launch |
| Rewards per objective | `rewards_per_objective` | `1`–`30`; default `1` | Assigns exactly this many reward items to every briefing-objective check and to the separate Mission Victory check. Total mission rewards are `number of checks × this value`. The launcher adds playful messages at 10, 20, and the maximum of 30. | Seed generation |
| Buff allied helpers | `generation.buff_allied_helpers` | `false`/`true`; default `false` | Gives earned buffs, unit access, and retry assistance to the AI helper houses explicitly listed for that mission in `randomizer_mission_houses.py`. The 42 configured missions were cross-checked against the [Mental Omega mission wiki](https://moapyr.fandom.com/wiki/Category:Missions); forces hostile during any phase remain denied even if they later break free. Player-controlled houses are always included. Every unlisted AI house is denied by default; map `Allies` fields and ownership-transfer actions are no longer trusted at launch. The setting off means no AI helper allowlist is used. Country/global rules are still skipped when the engine cannot isolate them from a denied house. | Seed generation |
| Strengthen failed missions on retry | `generation.failure_assistance` | `false`/`true`; default `false` | An unsuccessful mission exit, reload, or detected restart adds one assistance stack to that mission only. Its next launch receives cumulative production, cost, movement-speed, health, damage, armor, fire-rate, and attack-range help. With randomized access, eligibility is resolved from earned units, always-available essentials, and units supplied by the mission; otherwise the normal player-faction roster is included. The grid tile, Mission Details, and a compact Unlocks block show its stacks; victory deletes them. House-level assistance uses guarded country effects. Global unit/weapon fields are skipped whenever a denied enemy uses the affected type. | Seed generation |
| Reward mode | `generation.reward_mode` | `Standard`, `Chaos (Experimental)`; default `Standard` | Selects campaign-aware rewards or the all-faction Chaos production/access model described below. Chaos always enables access randomization. | Seed generation |

### Reward Pool settings

| UI setting | Standalone/AP option key | Default | What it changes |
|---|---|---:|---|
| Randomize unit access and lock unearned tech | `generation.randomize_unit_access` | `true` | Adds unit access rewards and removes unearned combat technology from player production. Economy essentials, MCVs, miners, Engineers, and each faction's amphibious transport remain available. Chaos forces this on. |
| Start with basic Tier 1 combat units | `generation.start_with_tier_one_units` | `false` | Grants ground and anti-air infantry plus ground and anti-air vehicles from seed start. Standard translates the four roles to each physical Allied, Soviet, or Epsilon barracks/factory family present in the mission: Allied production gets Allied starters, Soviet production Soviet starters, and Epsilon production Epsilon starters, regardless of campaign or player house. Foehn Standard uses Allied/Soviet operating technology; native Foehn starters remain Chaos-only. Starter access rewards are removed from that seed's reward pool, but their buff rewards remain eligible immediately. |
| Include defensive building rewards | `generation.include_defensive_buildings` | `true` | Includes faction defenses in both access rewards and defense-targeted buffs. It does not randomize power plants, refineries, production structures, walls, or gates. |
| Include buff rewards | `generation.include_buff_rewards` | `true` | Adds positive repeatable upgrades. Turning it off disables the buff-type selections. At least one reward-pool option must remain enabled. |
| Share buffs with same-tier equivalent units (Chaos only) | `generation.share_chaos_role_buffs` | `false` | Makes a unit buff affect its curated cross-faction peers, such as GI, Conscript, Initiate, and Knightframe. It does not grant access by itself. Shared groups appear together in Unlocks. |
| Include offensive superweapon rewards | `generation.include_superweapon_rewards` | `true` | Adds Lightning Storm, Tactical Nuke, Psychic Dominator, and Great Tempest. |
| Include secondary superweapon rewards | `generation.include_secondary_superweapon_rewards` | `true` | Adds Chronoshift, Invulnerability, Rage, and Blasticade independently from the offensive-superweapon option. |
| Include aid/reinforcement power rewards | `generation.include_aid_power_rewards` | `true` | Adds the installed faction delivery powers: unit drops, temporary reinforcements, deployable support structures/mines, and delivery-based support markers. |
| Enabled Buff Types | `generation.enabled_buff_types` | All listed types | Limits which buff families seed generation may assign. This option is ignored when **Include buff rewards** is off. |

### Buff type options

| Option ID | UI label | Effect per stack | Implementation scope |
|---|---|---|---|
| `production` | Production / construction speed | 15% faster production or construction | House/category scoped. Per-unit production rewards are omitted in Chaos where unsupported. |
| `cost` | Cost reduction | 20% cheaper | House/category scoped in Standard; unit-specific in Chaos. |
| `speed` | Movement speed | 10% faster | House/category scoped in Standard; unit-specific in Chaos. |
| `armor` | Armor | About 10% stronger effective durability | House/category scoped in Standard; unit-specific effective durability in Chaos. |
| `health` | Health | 15% more health | Direct unit type; applied only when enemy use of that global type is not detected. |
| `sight` | Vision | +1 sight | Direct unit type with the same safety guard. |
| `damage` | Damage | 15% more real impact/payload damage | Direct or spawned-payload weapon data with unit, spawner, and shared-weapon safety guards. |
| `reload` | Unit fire rate | 10% shorter weapon reload | Direct weapon type with unit and shared-weapon safety guards. |
| `rof` | Army-wide fire rate | 10% faster player/allied weapon fire | House scoped. |
| `range` | Attack range | +0.5 weapon range | Direct weapon type with unit and shared-weapon safety guards. |
| `ammo` | Ammo | +1 ammo capacity | Direct unit type with the same safety guard. |
| `self_healing` | Self-healing | Enables self-healing | Direct unit type; one effective stack. |
| `cloak` | Cloaking | Enables cloaking | Direct unit type; one effective stack. |
| `sensors` | Sensors | Enables sensors with a unit-derived radius | Direct unit type; one effective stack. |
| `veteran` | Veteran start | Newly produced affected units start veteran | House scoped; one effective stack because the engine flag does not start units elite. |

Direct unit and weapon definitions are global to the map. If an enemy uses the same type, the launcher skips that unsafe direct change instead of buffing the enemy or registering expensive cloned combat types. House-scoped rewards are written to an existing country only when that country is not shared with an enemy. Campaign houses are never reassigned to synthetic countries, because map triggers are owned by the original country IDs.

Reward labels shown in mission tiles, mission details, logs, and the Rewards tab state the actual effect, such as `Typhoon Attack Sub: Cost 20% cheaper`, instead of internal catalogue names such as `Attack Sub Logistics`. Access rewards use the installed playable roster name; for example, `HCRUIS` is shown as `Trident Battleship Access`, not the obsolete `Battlecruiser Access`.

The pool omits capability rewards a unit already possesses. Existing self-healing, cloaking (including staged/stop/attach-effect cloak), `Sensors=yes`, and `SensorArray=yes` are detected from the installed 3.3.6 definitions. Disguise kits, engineer tools, scanners, and explicit `NotAWeapon` helpers do not qualify their unit for weapon-stat rewards. Functional support weapons such as healing, repair, EMP, web, and time-warp tools remain eligible where reload or range really changes their effect. Legacy stored rewards that are now redundant or inapplicable retire without map injection.

### Non-UI configuration keys

These keys are runtime/developer controls and should not become normal Archipelago options without a design review.

| Key | Default | Purpose |
|---|---:|---|
| `generation.starting_unlocked_missions` | `3` | Mission List starting count. Grid Mode uses its own start rule. |
| `generation.enabled_reward_types` | `[access, buff, superweapon, secondary_superweapon, aid_power]` | Derived compatibility list written from the five reward-pool toggles. |
| `generation.safe_player_country_buffs` | `true` | Enables the stable map-local country safety path. |
| `generation.experimental_house_buffs` | `false` | Legacy house-buff route; it is still constrained by the same no-reassignment trigger safety rule. |
| `archipelago.*` | Disabled/blank | Reserved connection and slot fields. They currently do not connect to an Archipelago server. |

## Progression Modes

### Classic

Classic takes missions directly from the filtered installed campaign catalogue without shuffling them. Only the first mission is initially open, and each victory opens the next mission. Reward assignment remains seeded, so normal buffs, unit access, powers, and other enabled Randomizer systems still apply. With **All Campaigns**, catalogue order is preserved across the complete installed mission list; selecting one campaign preserves that campaign's own order.

### Mission List

Mission List uses randomized linear progression. The first three entries in the generated order are open, and each recorded mission victory opens the next entry. Its first five generated entries are drawn from low-level campaign missions (missions 1-6 in the installed catalogue). Optional no-build priority fills these protected positions from the enabled true-no-build and production-no-build categories first. Every later entry is fully shuffled from the remaining eligible pool, so Act 2 and finale missions can appear from position six onward.

### Grid Mode

Grid Mode assigns each generated mission to a visible node. Its dimensions are calculated from **Missions to finish**; there are no separate width/height settings. The launcher prefers a reasonably balanced exact factorization, so 18 missions form a complete `6 × 3` board. Totals without a suitable factorization use the densest balanced rectangle and trim only unavoidable corner cells.

Grid openings are protected by position rather than mission-list order. With one start, the top-left mission and both missions it can unlock are low-level. With two starts, both initially available missions and every immediate neighbor around them are low-level (up to six protected nodes). Optional no-build priority fills these protected cells from the enabled true-no-build and production-no-build categories first. All other grid cells are filled from the unrestricted remaining pool, allowing nearby later choices to include Act 2 and finale missions.

Grid rewards are spatial rather than linear. Each protected opening mission receives one unit-access reward when the selected pool can provide one. Every other reward slot is shuffled across the complete board before the normal access/buff draw runs, so unit access can appear in any row or corner instead of being consumed by the top row. Mission List keeps its stronger linear early-access bias.

Allied tile bodies are blue, Soviet red, Epsilon purple, and Foehn teal. The mission title already contains its faction and number, so tiles omit the redundant faction/code footer. Locked tiles are entirely grey. Available missions have no status banner; their faction color is the availability signal. Launching one or earning an objective reward adds an amber **In Progress** banner, while victory adds a green **Mission Completed** banner. State banners use plain text without decorative symbols. The selected tile receives a flat light-blue highlight on every edge. The bottom-right goal keeps a separate outer gold border and gains the light-blue inner selection border when selected, so both meanings remain visible. Selection and progress updates modify existing tiles in place without rebuilding the board. Only available, in-progress, or completed nodes can be launched. Selecting a node shows its coordinates, current state, and the currently locked neighbors that its completion would open.

The **Settings** tab is a vertically scrollable panel. Its scrollbar and mouse-wheel handling keep every reward-pool and buff-type option reachable when the launcher is used at its minimum window size.

Completing a node opens only existing orthogonal neighbors. Missing cells and diagonals are ignored. Automatically selected partial rectangles clip top-right/bottom-left corner cells while preserving a connected orthogonal route, top-left start, and bottom-right exit.

The endgoal may become reachable before the rest of the grid has been cleared. Completing it immediately records Randomizer victory, reports **Finished**, writes a structured victory event to the launcher log, releases every reward assigned to a still-pending grid check, and opens every unfinished node. Those missions stay available for optional cleanup without granting duplicate rewards when their checks are later completed. Released checks are shown as **Reward Released**, while mission completion remains separate.

The installed pool contains 30 Allied, 30 Soviet, 30 Epsilon, and 7 Foehn missions. In **All Campaigns**, Foehn receives a proportional per-seed cap—for example, at most 2 Foehn missions in an 18-mission seed. A Foehn-only seed can use all 7 missions, and the **Missions to finish** control is limited to the selected campaign's available count. Foehn 02/03/04/06 and Foehn Op are excluded from protected openings while another eligible map exists; Foehn-only goals larger than the two early-safe maps necessarily use late Foehn maps as fallback.

## Reward Modes

### Standard

Standard keeps the reward pool appropriate to the selected campaign. Single-faction campaigns translate earned roles when a mission gives the player a foreign barracks, factory, air command, or shipyard. For example, an earned basic-infantry role can provide the corresponding unit for a captured production family.

**All Campaigns** does not translate roles between factions. Capturing production exposes only that physical faction's exact unit IDs already unlocked by the player. Capturing an Allied Barracks with only Snipers and Suppressors unlocked therefore adds only Snipers and Suppressors, never free GIs or Guardian GIs. Mixed captured barracks share one Allied Engineer cameo; Soviet, Epsilon, and Foehn Engineer production is hidden on that map while preplaced and scripted Engineers remain intact. The four always-available amphibious transports remain progression exceptions. Optional Tier 1 starters add only their explicitly selected starter roles.

Special map-provided barracks, such as the converted mine in **Epsilon Op: Fallen Ashes**, can train every exact infantry unit already unlocked by the player, regardless of faction. A deployed **Stalin's Fist** can produce only unlocked vehicles matching the mission's current Soviet or Epsilon player faction. These special factories preserve each unit's normal production building as an alternative.

With **Start with basic Tier 1 combat units**, Standard immediately grants four roles: basic ground infantry, anti-air infantry, a basic ground vehicle, and an anti-air vehicle. Their faction follows the physical production family discovered in the map, matching the existing equivalent-access behavior. For example, Epsilon 04 gives Allied starters after its Allied Construction Yard is captured; a map with Epsilon barracks/factories gives Epsilon starters even when its campaign or current player house differs. **All Campaigns** supports all Allied, Soviet, and Epsilon production families. Foehn Standard still uses Allied/Soviet operating technology; native Foehn starters remain exclusive to Chaos.

Foehn Standard uses Allied/Soviet bundled access and compatible shared buffs because Foehn missions commonly operate those technologies. Standard **All Campaigns** uses Allied, Soviet, and Epsilon rewards; the complete Foehn reward catalogue is reserved for Chaos.

### Chaos (Experimental)

Chaos draws access and buffs independently from all four factions. An earned unit can be produced from any matching production building that the current mission gives the player: barracks for infantry, factories for vehicles, air commands for aircraft, shipyards for naval units, and Construction Yards for defenses. Special map barracks accept all earned infantry, and Stalin's Fist accepts all earned vehicles in Chaos. Capturing another production building never grants another unit; it only provides another factory for already-earned access. Chaos does **not** grant foreign production buildings.

With **Start with basic Tier 1 combat units**, Chaos shuffles all four factions across four guaranteed roles: ground infantry, anti-air infantry, ground vehicle, and anti-air vehicle. Every seed therefore starts with both ground and anti-air answers and exactly one Allied, Soviet, Epsilon, and Foehn starter.

The sidebar groups earned production cameos into faction bands with the current player faction first. Same-tier buff sharing is optional and off by default.

## Power Reward Catalogue

All earned power rewards are restored by a player-owned map-start grant in future launched missions. Each reward uses a new map-local `MOR...` power copied from the complete installed definition. The original power and any mission scripts using it remain untouched. The copy does not require its normal source building or original subfaction.

| Category | Allies | Soviets | Epsilon | Foehn |
|---|---|---|---|---|
| Offensive superweapon | Lightning Storm | Tactical Nuke | Psychic Dominator | Great Tempest |
| Secondary superweapon | Chronoshift | Invulnerability (Iron Curtain) | Rage | Blasticade |
| Aid/reinforcement | Airborne; Bloodhounds; Zephyrobot; Lightning Rod; Ultra Miner; Kingsnakes; Paladin Aid | Repair Drone; Tank Drop; Instant Shelter; Motor Ambush; Naval Mine; Terror Drop; Flame Tower; Drakuv Prison Vehicle; Repair Drones; Disruptor | Risen Monolith; Scout Raven; Vision; Magnetic Beam; Libra Clones; Bloatick Trap; Quick Fort; Ruiner; Hijackers | Spinblade; Megaarena; Knightfall; Sweeper Drop; Signal Jammer; Decoy Team; Decoy Squadron; M.A.D. Mine |

The copied aid powers keep installed costs, recharge times, delivered units, and effects unless their profile explicitly corrects a broken dependency. Paladin Aid and Knightfall receive their tested targeting and delivery corrections. M.A.D. Mine, Naval Mine, Drakuv, Ruiner, and Kingsnakes remove building/designator, inhibitor, source-range, and shroud gates from their copies while preserving land/water restrictions. Kingsnakes also uses a copied portal object with its separate `PoweredBy` dependency removed. Zephyrobot remains an artillery beacon: it needs Zephyr Artillery units already owned by the player and does not create shells by itself.

Offensive and secondary rewards are also made independent from base power. Lightning Storm carries explicit normal storm values so campaign-specific weather scripts cannot silently reduce its damage or strike rate. Chronoshift explicitly invokes its ChronoWarp follow-up; like the installed power, it moves team vehicles/units, not enemy units or infantry.

The proven `V3 Test Drop` custom-power definition is preserved as a disabled template for future powers. It is not assigned by new seeds, and legacy test rewards are retired without map injection.

Blasticade is correctly classified as Foehn's support superweapon. It activates the owning House's existing Blast Trenches, so earning Blasticade does not create trenches and the separate **Foehn Blast Trench Access** reward is still needed to construct them. Golden Wind remains an ordinary Blast Furnace/Spinblade support power and is not the secondary superweapon.

Elite Reserves is intentionally excluded. Unlike a unit drop, it delivers an internal production-state marker from a Soviet advanced lab; attempting to create that power with a building-free map action crashes the engine. Older seeds containing it display the reward as retired and do not inject it.

Standard uses campaign-appropriate power factions; Foehn Standard additionally includes native Foehn powers alongside its Allied/Soviet operating technologies. Chaos draws all four factions' power rewards, so any player faction can earn and use them.

## Seeing Exact Rewards

The reward count is a summary, not a mystery bundle:

- Hover an incomplete mission row to see every remaining check and every assigned reward name.
- Select a mission and open **Rewards** to see each objective/victory check, its completion state, its count, and the full reward-name list.
- Open **Unlocks** to see rewards already earned, grouped by faction/unit with installed cameo art and accumulated buff effects. Offensive, secondary, and aid/reinforcement powers display their installed sidebar icon beside the reward name.
- The mission table `Rewards` fraction counts reward items, not checks. With 30 rewards per check, completing one check advances it by 30.

Reward assignments are generated and stored when the seed is created. Access rewards are unique within a seed; once access is planned for a unit, later eligible slots can provide repeatable buffs. Some buff types have stack caps.

Victory is its own reward check. When the victory marker is detected, the launcher also grants any objective checks that were missed by the log watcher, so a won mission cannot remain partially rewarded.

## Mission Launch and Progress

The launcher reads campaign metadata from `INI\BattleClient.ini`, prepares a loose generated copy of the selected map, and starts:

```text
Syringe.exe gamemd.exe -SPAWN -CD -SPEEDCONTROL -LOG
```

The generated map contains the current tech locks/unlocks, safe rewards, and objective/victory marker actions. The launcher watches `debug\debug.log`, records each marker once, and removes the temporary root map when the spawned process exits. After detected victory it waits briefly, closes the spawned game process tree, and prevents continuation into the normal campaign flow.

For action codes, trigger selection, marker construction, ordering guarantees, cleanup, and known mismatches, see [Objective and Victory Hooks](TECHNICAL_FINDINGS.md#objective-and-victory-hooks).

## Saved Data

| Data | Source mode | Packaged mode |
|---|---|---|
| Config defaults | `RandomizerLauncher\config\mental_omega_randomizer.yaml` | `RandomizerLauncherData\config\mental_omega_randomizer.yaml` |
| Active seed/progress | `RandomizerLauncher\randomizer_state.json` | `RandomizerLauncherData\randomizer_state.json` |
| Launcher diagnostics | `RandomizerLauncher\logs\launcher.log` | `RandomizerLauncherData\logs\launcher.log` |
| Self-check report | `RandomizerLauncher\self_check.json` | `RandomizerLauncherData\self_check.json` |
| Generated/extracted maps and cameos | Under `RandomizerLauncher` | Under `RandomizerLauncherData` |

Configuration describes the next seed. State describes the active seed and must be preserved to continue that run.

## Troubleshooting

If the launcher does not start or cannot find required game files, run the self-check from the Mental Omega folder:

```powershell
.\MentalOmegaRandomizer.exe --self-check
```

Review `RandomizerLauncherData\self_check.json` and `RandomizerLauncherData\logs\launcher.log`. For missing objective or victory detection, also preserve `debug\debug.log` before launching another mission. A useful report includes the mission code, seed, reward mode, what was expected, and whether the problem reproduces in a separate fresh installation without map packs or rules modifications.

## Player-Facing Limitations

- Objective text and map trigger actions do not always have a one-to-one relationship. Victory tracking is broader than objective tracking.
- Direct unit/weapon buffs are skipped when a denied enemy shares the affected global type. This prevents enemy buffs but means the player does not receive that particular reward effect on that mission.
- Randomizer power grants contain only map-local `MOR...` clones. Native mission-owned or building-provided originals remain available to their normal houses because removing them can break campaign scripts; a matching player building may share or separately expose its native power.
- Game-speed behavior still needs validation across more campaign maps.
- Archipelago connection fields are placeholders only.
