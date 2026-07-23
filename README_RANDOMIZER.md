# Mental Omega Randomizer User Guide

This is the authoritative player-facing guide for seed settings and reward behavior. Installation, building, and source layout are maintained in [README.md](README.md); implementation details are maintained in [TECHNICAL_FINDINGS.md](TECHNICAL_FINDINGS.md).

The launcher is currently standalone and offline. The option keys below are intentionally stable so they can later become Archipelago world options without redefining their meaning.

> **Installation requirement:** use the executable in a new, separate, unmodified Mental Omega installation. Only the original Mental Omega campaign maps have been tested. Custom maps, funmaps, map packs, modified rules, and other gameplay modifiers are unsupported; see [Quick Start and supported game content](README.md#quick-start).

## Seed Lifecycle

- **Generate New Seed** replaces the active run, creates a new seed identifier, mission order, objective/victory checks, and complete reward plan.
- Seed-generation settings are copied into `randomizer_state.json`. Changing gameplay settings afterward affects the next seed. Dark mode, reward-name privacy, and locked-grid mission privacy apply immediately.
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
| Include optional Special Operation missions | `generation.include_operation_missions` | `false`/`true`; default `true` | Includes the 19 Allied, Soviet, Epsilon, and Foehn missions labelled `Op`. Turning it off removes them from both the next generated seed and the Advanced Pool mission cards. | Seed generation |
| Prioritize included no-build missions in opening | `generation.prioritize_no_build_missions` | `false`/`true`; default `false` | Fills protected Mission List or Grid opening positions with the lowest-stage eligible missions from whichever no-build categories are enabled. Ignored by Classic ordering. | Seed generation |
| Advanced Pool: Missions | `generation.excluded_mission_codes` | List of mission codes; default empty | Clicking a faction-art mission card greys it out and excludes that mission from future generated seeds. Campaign and no-build filters still apply. Existing runs keep their generated mission order. | Seed generation |
| Advanced Pool: Superpowers | `generation.excluded_superweapon_ids` | List of SuperWeaponType IDs; default empty | Clicking a power cameo greys it out and removes that power from future generated reward plans. Advanced Pool shows only the selected campaign faction, except All Campaigns shows everything. | Seed generation |
| Progression | `progression_mode` | `Classic`, `Mission List`, `Grid Mode`; default `Mission List` | Selects original campaign order, a randomized linear mission list, or the orthogonal-neighbor grid described below. | Seed generation |
| Start with two available missions | `grid_two_start_positions` | `false`/`true`; default `false` | Starts Grid Mode from the cells directly right of and below top-left instead of top-left itself. Requires at least four missions. | Seed generation |
| Difficulty | `difficulty` | `Casual`, `Normal`, `Mental`; default `Normal` | Writes the selected campaign/human difficulty to launch configuration. It does not change rewards. | Every launch |
| Game speed | `game_speed` | `0 - Slowest` through `6 - Fastest`; default `3 - Medium` | Writes the engine speed and launches with `-SPEEDCONTROL`, keeping the in-game speed control available. It does not change rewards. | Every launch |
| Rewards per objective | `rewards_per_objective` | `1`–`30`; default `1` | Assigns exactly this many reward items to every briefing-objective check and to the separate Mission Victory check. Total mission rewards are `number of checks × this value`. The launcher adds playful messages at 10, 20, and the maximum of 30. | Seed generation |
| Buff allied helpers | `generation.buff_allied_helpers` | `false`/`true`; default `false` | Gives reviewed allied AI helper houses the player's safe country buffs and compatible direct-buff/unit/defense clones. Existing timing, scripts, and triggers remain intact; compatible helper TaskForce slots, placements, and exact defense base plans use the same buffed `MORP...` clones as the player. Native IDs simultaneously retain factory access as invisible-to-player fallbacks for dynamic AI requests, preventing dead queues. Bounded parallel Autocreate teams add same-faction unlocked unit clones and never retain capped or unbuildable members. When this option is off, helpers keep only native unbuffed ownership, plans, TaskForces, and veterancy. | Seed generation |
| Strengthen failed missions on retry | `generation.failure_assistance` | `false`/`true`; default `false` | An unsuccessful mission exit, reload, or detected restart adds one assistance stack to that mission only. Its next launch receives cumulative production, cost, movement-speed, health, damage, armor, fire-rate, and attack-range help. Buffed infantry speed is capped at `8`. With randomized access, eligibility is resolved from earned units, always-available essentials, and units supplied by the mission; otherwise the normal player-faction roster is included. The grid tile, Mission Details, and a compact Unlocks block show its stacks; victory deletes them. House-level assistance uses guarded country effects. Global unit/weapon fields are skipped whenever a denied enemy uses the affected type. | Seed generation |
| Dark mode | `dark_mode` | `false`/`true`; default `false` | Switches launcher colors immediately and persists independently from the active seed. | Immediate |
| Hide reward names in Mission Details | `hide_reward_details` | `false`/`true`; default `false` | Replaces pending reward names with `?????` in Mission Details and mission-row hover text. Completed or released rewards reveal their names; earned rewards also remain visible in Unlocks. | Immediate |
| Hide locked Grid Mode mission names | `hide_locked_grid_missions` | `false`/`true`; default `false` | Shows every grid node but replaces locked mission identities, faction colors, status, and goal styling with a neutral `?` tile. Completing a visible mission reveals its newly unlocked orthogonal neighbors. The Unlocks catalogue also suppresses green playable-reward hints and their mission names. | Immediate |
| Reward mode | `generation.reward_mode` | `Standard`, `Chaos (Experimental)`; default `Standard` | Selects campaign-aware rewards or the all-faction Chaos production/access model described below. Chaos always enables access randomization. | Seed generation |

### Reward Pool settings

| UI setting | Standalone/AP option key | Default | What it changes |
|---|---|---:|---|
| Randomize unit access and lock unearned tech | `generation.randomize_unit_access` | `true` | Adds unit access rewards and removes unearned combat technology from player production. Economy essentials, MCVs, miners, Engineers, and each faction's amphibious transport remain available. Chaos forces this on. |
| Advanced Pool: Units / Buildings | `generation.excluded_unit_access_ids` | List of TechnoType IDs; default empty | Clicking an in-game cameo greys it out and removes that unit, defense, or special building's access reward **and its unit-specific buff rewards** from future generated seeds. Always-available essentials such as miners, Engineers, MCVs, and amphibious transports remain available. The visible cards follow the selected campaign faction. Existing runs keep their generated reward plan. |
| Advanced Pool: Unit Buffs | `generation.excluded_unit_buff_types` | Object mapping TechnoType IDs to excluded buff IDs; default empty | Select an included unit in the Unit Buffs subtab, then enable only the buff families that may be assigned to it in future seeds. Global buff-type switches still take precedence. Existing runs keep their generated reward plan. |
| Start with basic Tier 1 combat units | `generation.start_with_tier_one_units` | `false` | Grants ground and anti-air infantry, ground and anti-air vehicles, plus a basic aircraft from seed start. Advanced Pool exclusions override these starters, so an excluded Tier 1 unit is not silently granted by this option. Standard translates the remaining roles to each physical Allied, Soviet, or Epsilon production family and the player house's subfaction. A player-controlled/scripted MCV or Construction Yard also unlocks that family's airfield. Foehn Standard uses Allied/Soviet operating technology; native Foehn starters remain Chaos-only. Chaos keeps eligible faction roles and adds an eligible seeded aircraft whenever base construction exists. Starter access rewards are removed from that seed's reward pool, but their buff rewards remain eligible immediately. Summary displays every concrete starter variant with its cameo instead of abstract role-marker names. |
| Include defensive building rewards | `generation.include_defensive_buildings` | `true` | Includes faction defenses in both access rewards and defense-targeted buffs. It does not randomize power plants, refineries, production structures, walls, or gates. |
| Include special economy building rewards | `generation.include_special_buildings` | `true` | Includes Ore Purifier, Industrial Plant, Cloning Vats, and Reprocessor access. When the limit buff is enabled, each can also receive repeatable +1 structure-capacity rewards. |
| Unlimited unique / hero units | `generation.unlimited_hero_units` | `false` | Removes positive simultaneous-unit caps from isolated player clones of the 16 trainable capped heroes/unique units. Their enemy originals retain normal caps. Opted-in allied helpers share the player clones. Script-only units and capped defenses are unchanged. Enabling this turns off and disables **Unique / hero unit limit +1**. |
| Include buff rewards | `generation.include_buff_rewards` | `true` | Adds positive repeatable upgrades. Turning it off disables the buff-type selections. At least one reward-pool option must remain enabled. |
| Share buffs with same-tier equivalent units (Chaos only) | `generation.share_chaos_role_buffs` | `false` | Makes a unit buff affect its curated cross-faction peers, such as GI, Conscript, Initiate, and Knightframe. It does not grant access by itself. Shared groups appear together in Unlocks. |
| Include offensive superweapon rewards | `generation.include_superweapon_rewards` | `true` | Adds Lightning Storm, Tactical Nuke, Psychic Dominator, and Great Tempest. |
| Include secondary superweapon rewards | `generation.include_secondary_superweapon_rewards` | `true` | Adds Chronoshift, Invulnerability, and Rage independently from the offensive-superweapon option. Blasticade is excluded because it has no effect without owned Blast Trenches. |
| Include support/aid power rewards | `generation.include_aid_power_rewards` | `true` | Adds player-facing faction strikes, buffs, scouting, unit drops, deployable support structures, minefields, and grid spawners as map-local building-free copies. |
| Enabled Buff Types | `generation.enabled_buff_types` | All listed types | Limits which buff families seed generation may assign. This option is ignored when **Include buff rewards** is off. |

### Buff type options

| Option ID | UI label | Effect per stack | Implementation scope |
|---|---|---|---|
| `production` | Production / construction speed | 15% faster production or construction | House/category scoped. Per-unit production rewards are omitted in Chaos where unsupported. |
| `cost` | Cost reduction | 20% cheaper | House/category scoped in Standard; unit-specific in Chaos. |
| `speed` | Movement speed | 10% faster until its cap | Infantry uses isolated direct clones and cannot be raised above Speed `8`; infantry already at or above that ceiling is omitted from the Mobility reward pool. Faster native infantry retains its authored speed but receives no acceleration. Vehicles, naval units, and aircraft retain their existing house/category or unit-specific behavior. |
| `armor` | Armor | About 11% stronger effective durability per stack; configurable ceiling is 186% | House/category scoped in Standard; unit-specific effective durability in Chaos. |
| `health` | Health | 15% more health | Direct unit type; applied only when enemy use of that global type is not detected. |
| `sight` | Vision | +1 sight | Direct unit type with the same safety guard. |
| `damage` | Damage | 15% more real impact/payload damage; configurable ceiling is 200% | Direct or spawned-payload weapon data with unit, spawner, and shared-weapon safety guards. |
| `reload` | Unit fire rate | 10% shorter weapon reload | Direct weapon type with unit and shared-weapon safety guards. |
| `range` | Attack range | +0.5 weapon range | Direct weapon type with unit and shared-weapon safety guards. |
| `ammo` | Ammo | +1 ammo capacity | Direct unit type with the same safety guard. |
| `self_healing` | Self-healing | Enables self-healing | Direct unit type; one effective stack. Defenses heal 1% of maximum strength per normal repair tick instead of Ares's nearly invisible 1 HP default. |
| `cloak` | Cloaking | Enables cloaking | Direct unit type; one effective stack. |
| `sensors` | Sensors | Enables sensors with a unit-derived radius | Direct unit type; one effective stack. |
| `veteran` | Veteran start | Newly produced affected units start veteran | House scoped; one effective stack because the engine flag does not start units elite. Installed `Trainable=no` units such as Engineers and Spies are excluded. Generated country lists are bounded below the engine's single-value parser limit. |
| `build_limit` | Unique / hero unit limit +1 | Raises the normal simultaneous cap by one | Repeatable. Each earned stack adds one to that unit's isolated player/helper clone: four Tanya stacks permit five simultaneous Tanyas. Available only for the 16 trainable installed hero/unique units with a positive cap. Enemy caps stay native. Disabled when **Unlimited unique / hero units** is enabled. |
| `building_limit` | Special building limit +1 | Raises a special economy building's simultaneous cap by one | Repeatable and independent from hero capacity. Available for Ore Purifier, Industrial Plant, Cloning Vats, and Reprocessor when special-building rewards are enabled. **Unlimited unique / hero units** does not disable it. |

Direct unit, defense, and weapon definitions are global to the map. The launcher creates narrow standalone `MORP...` TechnoType and `MORW...` WeaponType copies when needed to isolate earned buffs from enemies. Buildable defense buffs always use a complete installed-identity clone: player and enabled-helper placements, exact helper base-plan entries, veterancy lists, and relevant trigger event/action type references use the clone, while enemy placements, plans, original defenses, and original weapons remain unchanged. Clone `Owner` includes each allowed country's parent chain so transferred factories recognize custom campaign countries; concrete `RequiredHouses` remains the isolation gate, preventing hostile descendants of the same parent from receiving the clone. This is distinct from unsafe global country-section buffs. With helper buffs disabled, helpers retain only originals. Mobile helper TaskForces use compatible buffed clones while native originals remain buildable dynamic-AI fallbacks. Mission-critical events/actions follow a clone whenever every actual map consumer of its source type is friendly, even if the trigger itself is owned by an unrelated story house. Every friendly scripted TaskForce follows the same clone, including locked map-only hero aliases, so escort and hero-loss checks cannot watch a different identity from the one the mission creates. Shared enemy types are retargeted only in player/helper-owned trigger lists. If a shared type has an outside-owned destruction event that cannot be assigned safely, that mission keeps the original type and skips its unsafe direct buff instead of risking an instant hero-loss/objective trigger. Helper veteran lists prioritize every clone actually produced before fallback IDs so the engine's 480-byte value limit cannot silently remove veterancy. Positive ownership prevents enemy buff leakage and duplicate player cameos. Installed positive mobile-unit limits remain capped normally unless the seed enables the isolated unlimited setting or earns repeatable `+1` cap stacks; enemy originals retain native limits in both cases. Launcher locks `0` and one-build-only `-1` are never treated as live caps. Effects that cannot be isolated safely remain skipped and logged. Saved Standard rewards are canonicalized and faction-filtered again at launch, so corrected catalogue entries cannot keep leaking foreign technology from an older seed.

Campaign factories obtained through object-level capture scripts are also recognized. `EBREED` uses PsiCorps2's captured Construction Yard, `EBLOOD` includes the PC-Base factories, and `SRAVEN` changes the tagged Guild3 base to the player. These houses are production-discovery sources only; they are not treated as allied helpers and receive no player buffs. Chaos production rewards now use per-clone `BuildTimeMultiplier`. When a Standard player country shares its parent with enemies and country multipliers must be skipped, isolated native-faction clones retain earned production, cost, speed, and armor effects without changing enemy originals.

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

Grid Mode assigns each generated mission to a visible node. Its dimensions are calculated from **Missions to finish**; there are no separate width/height settings. The launcher prefers a reasonably balanced exact factorization, so 18 missions form a complete `6 × 3` board. Totals without a suitable factorization use the densest balanced rectangle and trim only unavoidable corner cells. Large boards have horizontal and vertical scrollbars; the mouse wheel scrolls vertically and Shift+wheel scrolls horizontally while the pointer is over the board.

Grid openings are protected by position rather than mission-list order. With one start, the top-left mission and both missions it can unlock are low-level. With two starts, both initially available missions and every immediate neighbor around them are low-level (up to six protected nodes). Optional no-build priority fills these protected cells from the enabled true-no-build and production-no-build categories first. All other grid cells are filled from the unrestricted remaining pool, allowing nearby later choices to include Act 2 and finale missions.

Grid rewards are spatial rather than linear. Each protected opening mission receives one unit-access reward when the selected pool can provide one. Every other reward slot is shuffled across the complete board before the normal access/buff draw runs, so unit access can appear in any row or corner instead of being consumed by the top row. Mission List keeps its stronger linear early-access bias.

Allied tile bodies are blue, Soviet red, Epsilon purple, and Foehn teal. The mission title already contains its faction and number, so tiles omit the redundant faction/code footer. Locked tiles are entirely grey. With **Hide locked Grid Mode mission names** active, every locked node remains visible but contains only `?`; faction, title, status, goal styling, selection, and predicted neighbor names remain hidden until the node unlocks. Available missions have no status banner; their faction color is the availability signal. Launching one or earning an objective reward adds an amber **In Progress** banner, while victory adds a green **Mission Completed** banner. State banners use plain text without decorative symbols. The selected tile receives a flat light-blue highlight on every edge. The bottom-right goal keeps a separate outer gold border and gains the light-blue inner selection border when selected, so both meanings remain visible. Selection and progress updates modify existing tiles in place without rebuilding the board. Only available, in-progress, or completed nodes can be launched. Selecting a node shows its coordinates, current state, and, when privacy is disabled, the currently locked neighbors that its completion would open.

The **Settings** tab is a vertically scrollable panel containing seed generation, mission/run choices, reward-pool controls, buff types, assistance, appearance, and privacy. Moving the seed form out of the permanent side header gives the mission board more vertical space. The narrower **Details** side panel keeps **Launch Selected Mission**, the recovery-only **Mark Mission Complete** button, Mission Details, and Unlocks visible together. **Hide Details** expands the mission board across the window and shows duplicate Launch/Mark buttons beneath it, so missions remain playable with the side panel hidden. Recovery guidance remains in the Mark button tooltip. The Settings scrollbar and mouse-wheel handling keep every option reachable at minimum window size.

Completing a node opens only existing orthogonal neighbors. Missing cells and diagonals are ignored. Automatically selected partial rectangles clip top-right/bottom-left corner cells while preserving a connected orthogonal route, top-left start, and bottom-right exit.

The endgoal may become reachable before the rest of the grid has been cleared. Completing it immediately records Randomizer victory, reports **Finished**, writes a structured victory event to the launcher log, releases every reward assigned to a still-pending grid check, and opens every unfinished node. Those missions stay available for optional cleanup without granting duplicate rewards when their checks are later completed. Released checks are shown as **Reward Released**, while mission completion remains separate.

The installed pool contains 30 Allied, 30 Soviet, 30 Epsilon, and 7 Foehn missions. In **All Campaigns**, Foehn receives a proportional per-seed cap—for example, at most 2 Foehn missions in an 18-mission seed. A Foehn-only seed can use all 7 missions, and the **Missions to finish** control is limited to the selected campaign's available count. Foehn 02/03/04/06 and Foehn Op are excluded from protected openings while another eligible map exists; Foehn-only goals larger than the two early-safe maps necessarily use late Foehn maps as fallback.

## Reward Modes

### Standard

Standard keeps the reward pool appropriate to the selected campaign. Single-faction campaigns translate earned roles when a mission gives the player a foreign barracks, factory, air command, or shipyard. For example, an earned basic-infantry role can provide the corresponding unit for a captured production family.

**All Campaigns** keeps earned rewards across the seed, but each Standard mission starts from the faction of its authoritative `[Basic] Player` house. Merely earning an Epsilon unit therefore cannot add it to a Soviet mission's ordinary barracks. Proven player-controlled or transferred foreign production can expose only that physical faction's exact unit IDs already unlocked by the player. Capturing an Allied Barracks with only Snipers and Suppressors unlocked therefore adds only Snipers and Suppressors, never free GIs or Guardian GIs. Every map prepares exactly one installed-identity Engineer clone: Standard prefers the player faction when usable and otherwise the first usable production family; Chaos uses the first usable production family. Its generic barracks prerequisite keeps the cameo hidden until a barracks exists, including bases reached through a starting MCV or later script. The originals retain installed/map country restrictions and add player countries to `ForbiddenHouses`, preserving preplaced/scripted units and intended AI production without duplicate sidebar cameos. Amphibious transports remain progression exceptions: Standard exposes only the authoritative player faction's transport, while Chaos exposes all four. Their buffs share only through the optional equivalent-role setting. Optional Tier 1 starters add only their explicitly selected starter roles.

Special map-provided barracks, such as the converted mine in **Epsilon Op: Fallen Ashes**, can train every exact infantry unit already unlocked by the player, regardless of faction. A deployed **Stalin's Fist** can produce only unlocked vehicles matching the mission's current Soviet or Epsilon player faction. These special factories preserve each unit's normal production building as an alternative.

With **Start with basic Tier 1 combat units**, Standard immediately grants five roles: basic ground infantry, anti-air infantry, a basic ground vehicle, an anti-air vehicle, and a basic aircraft. Their faction follows physical production; their vehicle and aircraft variant follows the player house's subfaction. United States therefore receives Bulldog/Stryker/Stormchild, Europeans Cavalier/Archon/Harrier, Pacific Kappa/Tsurugi/Black Eagle, Russia Rhino/Tigr/Foxtrot, China Qilin/Halftrack/Foxtrot, Latin Jaguar/Halftrack/Foxtrot, PsiCorps Lasher/Gatling Tank/Dybbuk-Attacker, Scorpion Cell Mantis/Gatling Tank/Dybbuk-Attacker, and Epsilon HQ Opus/Gatling Tank/Dybbuk-Attacker. Installed IDs are `MTNK` for Cavalier, `STORM` for Stormchild, and `FOX` for Foxtrot. A discovered player MCV/Construction Yard prepares the corresponding airfield; missions without player base construction receive none. **All Campaigns** supports all Allied, Soviet, and Epsilon production families. Foehn Standard still uses Allied/Soviet operating technology.

Foehn Standard uses Allied/Soviet bundled access and compatible shared buffs because Foehn missions commonly operate those technologies. Standard **All Campaigns** uses Allied, Soviet, and Epsilon rewards; the complete Foehn reward catalogue is reserved for Chaos.

### Chaos (Experimental)

Chaos draws access and buffs independently from all four factions. Cross-faction unit cameos are therefore intentional in Chaos, not a Standard-style leak. An earned unit can be produced from any matching production building that the current mission gives the player: barracks for infantry, factories for vehicles, air commands for aircraft, shipyards for naval units, and Construction Yards for defenses. Special map barracks accept all earned infantry, and Stalin's Fist accepts all earned vehicles in Chaos. Capturing another production building never grants another unit; it only provides another factory for already-earned access. A starter aircraft uses compatible player production; when an MCV/Construction Yard must supply an airfield, the launcher unlocks the player's native airfield rather than the aircraft faction's foreign structure.

With **Start with basic Tier 1 combat units**, Chaos shuffles all four factions across four guaranteed ground roles: ground infantry, anti-air infantry, ground vehicle, and anti-air vehicle. Lancer is Foehn's ground infantry and Knightframe its anti-air infantry. Ground vehicles, anti-air vehicles, and aircraft choose a deterministic valid subfaction variant. It then adds one seeded basic Allied, Soviet, or Epsilon aircraft. Every seed therefore starts with both ground and anti-air answers, exactly one ground starter from every faction, and one real AircraftType. Any player MCV/Construction Yard unlocks the player's native airfield for that aircraft.

The sidebar groups earned production cameos into faction bands with the current player faction first. Same-tier buff sharing is optional and off by default.

## Power Reward Catalogue

All earned power rewards are restored by a player-owned map-start grant in future launched missions. Each reward uses a new map-local `MOR...` power copied from the complete installed definition. The original power and any mission scripts using it remain untouched. The copy does not require its normal source building or original subfaction.

| Category | Allies | Soviets | Epsilon | Foehn |
|---|---|---|---|---|
| Offensive superweapon | Lightning Storm | Tactical Nuke | Psychic Dominator | Great Tempest |
| Secondary superweapon | Chronoshift | Invulnerability (Iron Curtain) | Rage | None |
| Aid/reinforcement | Airborne; Bloodhounds; Zephyrobot; Lightning Rod; Ultra Miner; Kingsnakes; Paladin Aid | Repair Drone; Tank Drop; Instant Shelter; Motor Ambush; Naval Mine; Terror Drop; Flame Tower; Drakuv Prison Vehicle; Repair Drones; Elite Reserves; Disruptor | Risen Monolith; Scout Raven; Vision; Magnetic Beam; Libra Clones; Bloatick Trap; Quick Fort; Ruiner; Hijackers | Spinblade; Megaarena; Knightfall; Harbinger; Sweeper Drop; Signal Jammer; Decoy Team; Decoy Squadron; M.A.D. Mine |

The copied aid powers keep installed costs, recharge times, delivered units, and effects unless their profile explicitly corrects a broken dependency. Knightfall keeps its installed `6.5` recharge. The five mine/grid spawners are the timing exception: installed `0.01` is an internal one-shot construction helper, not a usable repeating-power cooldown. Minefields use the reviewed `2.5`-minute player-power timing and Confusion/Stasis grids use `1` minute. Paladin Aid and Knightfall receive their tested targeting and delivery corrections. Drakuv and Harbinger are available only through their aid powers; their `Trainable=no` payload types never appear as production rewards or random tech locks. M.A.D. Mine, Naval Mine, Drakuv, Ruiner, and Kingsnakes remove building/designator, inhibitor, source-range, and shroud gates from their copies while preserving land/water restrictions. Kingsnakes also uses a copied portal object with its separate `PoweredBy` dependency removed. Wallbuster stays the installed `EMPulse` power with its exact `8.5` recharge, cost, 320-damage weapon, projectile, and warhead. Its private weapon, warhead, and projectile are registered in their engine type lists. Four invisible, unbuildable map-start cannon copies use the original turreted `EMPulseCannon=yes` firing path; the Chinese Atomheart never enters the construction tab, and copied targeting ranges cover the whole map. Zephyrobot remains an artillery beacon: it needs Zephyr Artillery units already owned by the player and does not create shells by itself. Tactical Nuke stays completely installed/global in every mission except Fatal Impact; there its randomizer copy alone points to a registered private copy of the installed 600-damage `NukePayload`, bypassing the map's 5000-damage objective payload.

Offensive and secondary rewards are also made independent from base power. Lightning Storm carries explicit normal storm values so campaign-specific weather scripts cannot silently reduce its damage or strike rate. Tactical Nuke remains the installed `MultiMissile` power with `NukeCarrier` in every normal mission. Fatal Impact alone redirects the reward copy to a registered private copy of the installed `NukePayload`: Damage `600`, `NUKE`, normal CellSpread. The mission's native Damage `5000`/`MIDASDeathWH` payload remains untouched and cannot affect the player reward. Chronoshift explicitly invokes its ChronoWarp follow-up; like the installed power, it moves team vehicles/units, not enemy units or infantry. Unthinkable keeps native `LIBRA` because its map-local Driller accepts only that exact passenger/operator ID; her earned buffs are applied directly. Bleed Red keeps its map-local `MORALES` Boris identity and every Boris House transport/Rhino escort native, preserving Boris art and controllable scripted reinforcements.

`V3 Test Drop` is preserved as a disabled custom-power and artwork template. When enabled, it delivers twenty player-owned V3 Launchers and uses `sidebar_image` from editable `assets/yuri_shocked.png`. The same source PNG drives both the launcher Unlocks cameo and the generated 60×48 indexed `SidebarPCX=moryv3.pcx`; Mental Omega itself consumes only the converted loose PCX.

Blasticade is excluded: it only activates existing owned Blast Trenches, so a building-free reward does nothing by itself. Golden Wind is also excluded because it only overpowers existing Spinblades. Harbinger and EM Pulse no longer require or grant separate Harbinger Tower/EMP Control Station construction access. M.A.D. Mine deploys exactly one mine, matching installed `Deliver.Types=FAMMIN`; EMP, Cryomine, and Genomine field powers deploy four mines, while Confusion and Stasis Grid powers deploy nine grid cells.

The support/aid pool contains 73 active powers:

| Faction | Included support/aid powers |
|---|---|
| Allies | Airborne, Bloodhounds, Zephyrobot, Lightning Rod, Ultra Miner, Kingsnakes, Paladin Aid, Force Shield, Target Painter, Sonar Pulse, Mercury Strike, Satellite Scan, Black Widow Alpha, Black Widow, Chronoboost, Cryoshot, Cryospear, Glacial Screen, Cryomine Field, Chronolift |
| Soviets | Repair Drone, Tank Drop, Instant Shelter, Motor Ambush, Naval Mine, Terror Drop, Flame Tower, Drakuv, Repair Drones, Elite Reserves, Disruptor, Spy Plane, Smoke Bombs, EM Pulse, Irradiation Gamma, Overcharge, Wallbuster, Irradiation Beta, Rad Attack, Pack Attack, EMP Minefield |
| Epsilon | Risen Monolith, Scout Raven, Vision, Magnetic Beam, Libra Clones, Bloatick Trap, Quick Fort, Ruiner, Hijackers, Shadow Ring, Kinetic Barrier, Geneburst, Toxic Strike, Regen Drugs, Wonder Drugs, Genomine Field |
| Foehn | Spinblade, Megaarena, Knightfall, Harbinger, Sweeper Drop, Signal Jammer, Decoy Team, Decoy Squadron, M.A.D. Mine, Nanofiber Sync, Boid Blitz, Recon Sortie, Devourer, Chaos Touch, Confusion Grid, Stasis Grid |

Source-object-only powers stay excluded because their cloned cameo would be inert without the original object: Blasticade, Golden Wind, Hunter-Seeker, Nanocharge, Gear Change, Psychic Flash, Blackout Missile, Nuclear Path, and Backwarp.

Elite Reserves is the building-bound exception. Its clone is attached to Allied, Soviet, Epsilon, and Foehn Barracks variants and restricted to the player countries. It is never granted through action `34`, avoiding the proven crash while creating its internal `F_ERESB` academy marker. Selling or losing the granting Barracks removes that instance; rebuilding a Barracks restores access.

Standard uses campaign-appropriate power factions; Foehn Standard additionally includes native Foehn powers alongside its Allied/Soviet operating technologies. Chaos draws all four factions' power rewards, so any player faction can earn and use them.

## Seeing Exact Rewards

The reward count is a summary, not a mystery bundle:

- Hover an incomplete mission row to see every remaining check and every assigned reward name.
- Select a mission and open **Mission Details** to see each objective/victory check, its completion state, its count, and the full reward-name list.
- Enable **Hide reward names in Mission Details** to replace assigned names in Mission Details and mission-row hover text with `?????`. Earned items remain visible in Unlocks.
- Open **Unlocks** for faction tabs containing every unit, defense, aircraft, and configured superpower cameo. Normal icons are unlocked, green icons have a reward in a presently playable mission, gray icons are assigned but still locked, and black icons are unavailable in the current seed. Hovering an icon shows its access state, mission/check source when public, accumulated buff effects, and any immediately obtainable effect. Green-icon hover outlines matching playable Grid nodes; in Mission List/Classic it renders matching mission rows green, bold, and underlined. Search controls exist only inside **Summary**, which retains the searchable earned-reward listing and concrete Tier 1 starter names/cameos. Locked-grid privacy removes green/source/node hints. Standard keeps native Foehn unit icons unavailable because those rewards are Chaos-only. Custom powers use their configured launcher artwork.
- The mission table `Rewards` fraction counts reward items, not checks. With 30 rewards per check, completing one check advances it by 30.

Reward assignments are generated and stored when the seed is created. Access rewards are unique within a seed; once access is planned for a unit, later eligible slots can provide repeatable buffs. Some buff types have stack caps.

Victory is its own reward check. When the victory marker is detected, the launcher also grants any objective checks that were missed by the log watcher, so a won mission cannot remain partially rewarded.

## Mission Launch and Progress

The launcher reads campaign metadata from `INI\BattleClient.ini`, prepares a loose generated copy of the selected map, and starts:

```text
Syringe.exe gamemd.exe -SPAWN -CD -SPEEDCONTROL -LOG
```

The generated map contains the current tech locks/unlocks, safe rewards, and objective/victory marker actions. The launcher watches `debug\debug.log`, records each marker once, and removes the temporary root map when the spawned process exits. After detected victory it waits briefly, closes the spawned game process tree, and prevents continuation into the normal campaign flow.

Reviewed mission compatibility rules remain local to their source map. Machinehead always exposes Foxtrots through its captured Soviet airfields and keeps its drop-pod `LIBRA`, follow-up teams, and Event 61 loss check on the same native identity. Juggernaut preserves its scripted Hammer Defense and Iron Guard actions, then exposes every earned defensive structure through the mission SMCV rather than reducing access to those two native defenses. Mermaid, Hammer to Fall, Power Hunger, and Kill the Messenger keep their objective hero/transport types native so exact loss, operator, and passenger checks continue to work. Power Hunger keeps map-local `DRIL` as its authored Burillo, keeps all scripted `INIT` Desolators native under the authored USSR/Latin/Special coalition, applies Morales buffs from his mission base, and exposes the native Burillo behind the Soviet War Factory as recovery access. Kill the Messenger changes only its scripted SMCV to Speed `16`, immediate acceleration, and faster turning so it reaches the deploy cell before pursuing tanks. Reality Check keeps `LIBRA` and all eight conversion phases native, raises their mission bases to five times authored strength (`6000` or `7500`), then adds every earned direct unit/weapon buff. Native conversion and Event 61 loss references therefore stay synchronized.

For action codes, trigger selection, marker construction, ordering guarantees, cleanup, and known mismatches, see [Objective and Victory Hooks](TECHNICAL_FINDINGS.md#objective-and-victory-hooks).

## Saved Data

| Data | Source mode | Packaged mode |
|---|---|---|
| Static gameplay/UI configuration | `RandomizerLauncher\configs` | `RandomizerLauncherData\configs` |
| Config defaults | `RandomizerLauncher\config\mental_omega_randomizer.yaml` | `RandomizerLauncherData\config\mental_omega_randomizer.yaml` |
| Active seed/progress | `RandomizerLauncher\randomizer_state.json` | `RandomizerLauncherData\randomizer_state.json` |
| Launcher diagnostics | `RandomizerLauncher\logs\launcher.log` | `RandomizerLauncherData\logs\launcher.log` |
| Self-check report | `RandomizerLauncher\self_check.json` | `RandomizerLauncherData\self_check.json` |
| Generated/extracted maps and cameos | Under `RandomizerLauncher` | Under `RandomizerLauncherData` |

Configuration describes the next seed plus immediate UI preferences. State describes the active seed and must be preserved to continue that run.

Static JSON configuration contains mission classifications and overrides, house policy, faction production, unit/defense data, reward definitions, clone/buff tuning, powers, and UI choices. Packaged defaults are copied only when missing; existing edits remain untouched. Restart the launcher after editing. See [configs/README.md](configs/README.md).

## Troubleshooting

If the launcher does not start or cannot find required game files, run the self-check from the Mental Omega folder:

```powershell
.\MentalOmegaRandomizer.exe --self-check
```

Review `RandomizerLauncherData\self_check.json` and `RandomizerLauncherData\logs\launcher.log`. For missing objective or victory detection, also preserve `debug\debug.log` before launching another mission. A useful report includes the mission code, seed, reward mode, what was expected, and whether the problem reproduces in a separate fresh installation without map packs or rules modifications.

## Player-Facing Limitations

- Objective text and map trigger actions do not always have a one-to-one relationship. Victory tracking is broader than objective tracking.
- Unsupported direct unit/weapon paths are skipped when safe clone or ownership isolation is unavailable. Buildable defense TechnoType/WeaponType buffs use player/helper clones instead of modifying enemy-shared originals.
- Randomizer power grants contain only map-local `MOR...` clones. Native mission-owned or building-provided originals remain available to their normal houses because removing them can break campaign scripts; a matching player building may share or separately expose its native power.
- Game-speed behavior still needs validation across more campaign maps.
- Archipelago connection fields are placeholders only.
