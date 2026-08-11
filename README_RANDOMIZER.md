# Mental Omega Randomizer User Guide

This is the authoritative player-facing guide for seed settings and reward behavior. Installation, building, and source layout are maintained in [README.md](README.md); implementation details are maintained in [TECHNICAL_FINDINGS.md](TECHNICAL_FINDINGS.md).

The launcher supports standalone play and Archipelago 0.6.7 multiworld play.
The same settings generate both modes. Archipelago player YAML exposes a
readable copy of the normal nested launcher settings and freezes the generated
run in a separate protected manifest.

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
| EVA voice | `eva_voice` | `Mission default`, `Allied`, `Soviet`, `Epsilon`, `Foehn`, `Random`; default `Mission default` | Selects one announcer plus its matching faction sidebar and mission-text color for the complete launched mission. `Mission default` preserves authored appearance. `Random` deterministically selects one profile from the seed and mission, so it never changes during play. | Every launch |
| Rewards per objective | `rewards_per_objective` | `1`–`30`; default `1` | Assigns exactly this many reward items to every briefing-objective check and to the separate Mission Victory check. Total mission rewards are `number of checks × this value`. The launcher adds playful messages at 10, 20, and the maximum of 30. | Seed generation |
| Rewards only when mission is finished | `rewards_on_victory_only` | `false`/`true`; default `false` | Keeps objective tracking but assigns zero player rewards to objectives. The spinner becomes **Rewards per mission**. Mission Victory grants exactly that value, then applies mission weight only when **Use Act-based reward multipliers** is enabled. Objective count no longer changes the mission total. | Seed generation |
| Use Act-based reward multipliers | `use_act_based_reward_multipliers` | `false`/`true`; default `true` | When enabled, uses existing mission classification: Act 1 x1, Act 2 x2, Finale x3, and configured Special Operation classes/overrides. Extra draws go only to Mission Victory; objective rewards stay normal. When disabled, every mission uses x1. Mission Details shows the current multiplier only while enabled. | Seed generation |
| Buff allied helpers | `generation.buff_allied_helpers` | `false`/`true`; default `false` | Gives reviewed allied AI helper houses the player's safe country buffs and compatible direct-buff/unit/defense clones. Existing timing, scripts, and triggers remain intact; compatible helper TaskForce slots, placements, and exact defense base plans use the same buffed `MORP...` clones as the player. Native IDs simultaneously retain factory access as invisible-to-player fallbacks for dynamic AI requests, preventing dead queues. Bounded parallel Autocreate teams add same-faction unlocked unit clones and never retain capped or unbuildable members. When this option is off, helpers keep only native unbuffed ownership, plans, TaskForces, and veterancy. | Seed generation |
| Strengthen failed missions on retry | `generation.failure_assistance` | `false`/`true`; default `false` | An unsuccessful mission exit, reload, or detected restart adds one assistance stack to that mission only. Its next launch receives cumulative production, cost, movement-speed, health, damage, armor, fire-rate, and attack-range help with no arbitrary stack-count cutoff; infantry Speed retains its safety ceiling of `8`. With randomized access, eligibility is resolved from earned units, always-available essentials, and units supplied by the mission; otherwise the normal player-faction roster is included. The grid tile, Mission Details, and a compact Unlocks block show its stacks; victory deletes them. House-level assistance uses guarded country effects. Global unit/weapon fields are skipped whenever a denied enemy uses the affected type. | Seed generation |
| Dark mode | `dark_mode` | `false`/`true`; default `false` | Switches launcher colors immediately and persists independently from the active seed. | Immediate |
| Hide reward names in Mission Details | `hide_reward_details` | `false`/`true`; default `false` | Replaces pending reward names with `?????` in Mission Details and mission-row hover text. Completed or released rewards reveal their names; earned rewards also remain visible in Unlocks. | Immediate |
| Hide locked Grid Mode mission names | `hide_locked_grid_missions` | `false`/`true`; default `false` | Shows every grid node but replaces locked mission identities, faction colors, status, and goal styling with a neutral `?` tile. Completing a visible mission reveals its newly unlocked orthogonal neighbors. The Unlocks catalogue also suppresses green playable-reward hints and their mission names. | Immediate |
| Reward mode | `generation.reward_mode` | `Standard`, `Chaos`, `Randomizer Arsenal`; default `Standard` | Selects campaign-aware rewards, permanent all-faction Chaos progression, or seed-fixed per-mission Arsenal rosters with buff-only rewards. Chaos and Arsenal always enable access isolation. | Seed generation |
| Arsenal factions and roster sizes | `generation.arsenal` | All four factions; configurable Tier 1/2/3 Infantry, Vehicle, Aircraft, Naval, and power counts | Randomizer Arsenal uses an independent deterministic stream for every mission. TechLevel 1-2 is Tier 1, 3-6 Tier 2, and 7+ Tier 3. Equivalent units never share one roster. Existing Advanced unit, power, and buff exclusions still apply. | Seed generation |

### Reward Pool settings

| UI setting | Standalone/AP option key | Default | What it changes |
|---|---|---:|---|
| Randomize unit access and lock unearned tech | `generation.randomize_unit_access` | `true` | Adds unit access rewards and removes unearned combat technology from player production. Economy essentials, MCVs, miners, Engineers, and each faction's amphibious transport remain available. Chaos forces this on. |
| Advanced Pool: Units / Buildings | `generation.excluded_unit_access_ids` | List of TechnoType IDs; default empty | Clicking an in-game cameo greys it out and removes that unit, defense, or special building's access reward **and its unit-specific buff rewards** from future generated seeds. Always-available essentials such as miners, Engineers, MCVs, and amphibious transports remain available. The visible cards follow the selected campaign faction. Existing runs keep their generated reward plan. |
| Advanced Pool: Unit Buffs | `generation.excluded_unit_buff_types` | Object mapping TechnoType IDs to excluded buff IDs; default empty | Select an included unit in the Unit Buffs subtab, then enable only the buff families that may be assigned to it in future seeds. Global buff-type switches still take precedence. Existing runs keep their generated reward plan. |
| Start with basic Tier 1 combat units | `generation.start_with_tier_one_units` | `false` | Grants ground and anti-air infantry, ground and anti-air vehicles, plus a basic aircraft from seed start. Advanced Pool exclusions override these starters. Standard resolves each role for physically available faction production and keeps exact factory prerequisites, so foreign technology remains dormant until capture. Chaos lets every compatible production building use each selected starter and lets any Construction Yard build its required airfield. Starter access rewards are removed from that seed's reward pool, but their buff rewards remain eligible immediately. Summary displays every concrete starter variant with its cameo. |
| Start with basic Tier 1 defensive structures | `generation.start_with_tier_one_defenses` | `false` | Grants basic ground and anti-air defenses. Standard prepares faction equivalents behind their exact physical Construction Yards, so foreign defenses remain dormant until capture. Chaos selects two defenses from distinct faction families and lets any faction Construction Yard build both. Advanced Pool exclusions override starters. When defensive-building rewards are enabled, their access rewards leave the seed pool while buffs remain eligible immediately. |
| Starting Rewards | `generation.starting_reward_count` | `0` | Rolls this many normal rewards during seed creation and grants them before the first mission. Starting rewards immediately appear as earned in Unlocks and seed every later reward draw, preventing the same unlock or TechnoType access from being granted again. Invalid or capped choices are rerolled; exhaustion produces one **Max rewards achieved.** marker. Range `0`-`9999`. |
| Starting Rewards allowed types | `generation.starting_reward_types` | All four unlock families | Chooses among unit/building unlocks, offensive superweapons, secondary powers, and support/aid powers. Buffs remain normal progression rewards. Existing Reward Pool toggles, Advanced exclusions, reward weights, access prerequisites, and power prerequisites remain authoritative. |
| Advanced → Starting Unlocks | `generation.starting_unlock_rewards` | Empty list | Selects exact permanent unit, building, superweapon, support-power, or other content unlocks already owned before the first mission. Buffs and every repeatable/stat upgrade remain progression-only and never appear in this tab. Cached cameos appear beside every entry, with a generic placeholder when art is unavailable. Portable canonical unlock names are frozen into the generated seed, appear as earned immediately, bypass ordinary pool/faction filtering for launch, and are excluded from both random Starting Rewards and all later rewards. Duplicate TechnoType access is omitted. Use **Configure Starting Unlocks...** beside Starting Rewards to open this page directly. |
| AI bonus stacks per completed objective | `generation.enemy_scaling.rewards_per_completed_objective` | `0` | Attempts to activate this many deterministic AI bonus stacks after every completed non-victory objective. Range `0`-`10`. All AI sources share per-effect caps, so later objectives grant fewer or zero after every enabled bonus is capped. |
| AI bonus stacks per completed mission | `generation.enemy_scaling.rewards_per_completed_mission` | `0` | Attempts to activate this many additional deterministic AI bonus stacks after mission victory. Range `0`-`10`; objective and mission values stack until shared caps are exhausted. |
| Include AI rewards in normal reward pool | `generation.enemy_scaling.reward_enabled` | `false` | Adds real AI-only entries to normal reward rolls. They occupy reward slots, appear as red `AI Reward:` descriptions, and target only confirmed hostile AI houses discovered from mission ownership and military use. |
| AI reward weight | `generation.reward_weights.main.enemy_buffs` | `100` | Controls normal AI-reward selection frequency. It does not change effect strength or completion-based draws. |
| Include defensive building rewards | `generation.include_defensive_buildings` | `true` | Includes faction defenses in both access rewards and defense-targeted buffs. It does not randomize power plants, refineries, production structures, walls, or gates. |
| Include special economy building rewards | `generation.include_special_buildings` | `true` | Includes Ore Purifier, Industrial Plant, Cloning Vats, and Reprocessor access. When the limit buff is enabled, each can also receive repeatable +1 structure-capacity rewards. |
| Include campaign/map-only Special rewards | `generation.include_special_rewards` | `true` | Includes every unit, marked building, and power shown as **Special**, plus its matching unit/building or power buffs. Turning it off leaves normal roster units, ordinary special economy buildings, and ordinary aid powers untouched. The usual access, buff, power-category, and special-building switches still apply; existing runs keep their saved choice. |
| Unlimited unique / hero units | `generation.unlimited_hero_units` | `false` | Removes positive simultaneous-unit caps from isolated player clones of the 16 trainable capped heroes/unique units. Their enemy originals retain normal caps. Opted-in allied helpers share the player clones. Script-only units and capped defenses are unchanged. Enabling this turns off and disables **Unique / hero unit limit +1**. |
| Include buff rewards | `generation.include_buff_rewards` | `true` | Adds positive repeatable upgrades. Turning it off disables the buff-type selections. At least one reward-pool option must remain enabled. |
| Share buffs with same-tier equivalent units (Chaos / All Campaigns) | `generation.share_chaos_role_buffs` | `false` | In Chaos or Standard All Campaigns, makes a unit buff affect its curated cross-faction peers, such as GI, Conscript, Initiate, and Knightframe. It does not grant access by itself. Shared groups appear together in Unlocks. |
| Include offensive superweapon rewards | `generation.include_superweapon_rewards` | `true` | Adds Lightning Storm, Tactical Nuke, Psychic Dominator, and Great Tempest. |
| Include secondary superweapon rewards | `generation.include_secondary_superweapon_rewards` | `true` | Adds Chronoshift, Invulnerability, and Rage independently from the offensive-superweapon option. Blasticade is excluded because it has no effect without owned Blast Trenches. |
| Include support/aid power rewards | `generation.include_aid_power_rewards` | `true` | Adds player-facing faction strikes, buffs, scouting, unit drops, deployable support structures, minefields, and grid spawners as map-local building-free copies. |
| Include superweapon / aid power buff rewards | `generation.include_power_buff_rewards` | `true` | Adds repeatable buffs only after their matching power has been planned as unlocked. Settings → **Superweapons** enables broad buff families; Advanced → **Superpower Buffs** configures valid effects per included power. Invalid effects are unavailable rather than producing no-op rewards. |
| Main reward weights | `generation.reward_weights.main` | Every value `100` | Controls relative selection of normal unit unlocks, power/aid unlocks, Special unit unlocks, faction-wide production increases, unit/building buffs, and power buffs. A `0` category is never selected. A category with no currently valid reward is removed before the roll, so its chance is reallocated. |
| Unit buff weights | `generation.reward_weights.unit_buffs` | Every value `100` | Controls relative selection of movement, health, damage, range, fire rate, armor, cost, production time, healing, vision, ammo, cloaking, sensors, veterancy, and other existing unit/building buffs. Weights change item frequency only, never effect strength or stack caps. |
| Superweapon buff weights | `generation.reward_weights.power_buffs` | Every value `100` | Controls relative selection of recharge, cost, area, damage, duration, delivered units, reconnaissance-plane vision, and future/other reviewed power buffs. A power buff remains unavailable until its matching power is unlocked. |
| Enabled Buff Types | `generation.enabled_buff_types` | All listed types | Limits which buff families seed generation may assign. This option is ignored when **Include buff rewards** is off. |
| Settings → Superweapons / Advanced → Superpower Buffs | `generation.enabled_power_buff_types`, `generation.excluded_power_buff_types` | All broad families enabled; no per-power exclusions | Settings globally enables recharge, cost, area, damage, duration, or payload reward families. Advanced selects one included power at a time for finer valid-effect exclusions. Existing generated runs keep their saved reward plan. |

Weights use separate sliders accepting integers from `0` through `100`. Invalid,
missing, or old-config
values are normalized safely; negative values become `0`, oversized values
become `100`, and malformed values use the default. Existing reward and
buff checkboxes remain the enabled/disabled source; a disabled choice stays
unavailable regardless of its slider. Main category selection
happens before the matching unit- or power-buff subtype selection, preventing a
large catalogue category from gaining extra chance merely because it contains
more individual rewards. Already-earned one-time unlocks, capped buffs,
inapplicable unit buffs, and power buffs whose power is still locked are removed
before each roll. The **Default** button restores every slider to `100` only;
other reward-pool, buff-type, and Advanced exclusions remain
unchanged. The all-default weight set uses the original reward planner exactly,
including existing seed output. Missing weight settings in older player configs
and generated runs therefore retain prior behavior.

### AI Enemy Rewards

Eight reviewed AI-only effects are available: infantry, vehicle/naval,
aircraft, and defense armor, plus infantry, vehicle/naval, aircraft, and defense
production time. They use guarded
CountryType multipliers. Human-controlled houses, player allies, countries
shared with any non-target house, and ambiguous duplicate CountryType sections
are skipped.

Objective and mission completion counts use one independent deterministic RNG
stream. Both rates may be above zero and stack. When normal and completion AI
rewards are both enabled, completion planning leaves part of each shared cap
available to normal rolls. The two sources combine without exceeding global
per-effect caps. The same seed and frozen settings reproduce the same plan.
Each effect has five stacks. Armor adds the configured 11% strength per stack
through the reciprocal received-damage multiplier; production reduces its
engine multiplier by the configured 10% per stack. Thus stacks 1–5 produce
armor values `1.11`–`1.55` and production values `0.9`–`0.5` from a `1.0`
baseline. A capped effect leaves the candidate pool, so later draws reroll among
other valid AI effects.

The **Enemy Rewards** tab shows a text card only after a generated map records
that exact bonus as applied to a real hostile AI target. Merely enabled,
seed-assigned, or earned/pending bonuses remain hidden. Cards and hover text
show the confirmed cumulative percentage, stack `1/5` through `5/5`, configured
per-stack value, hostile target, exact generated INI field, and final engine
value. The old
large applied-reward table is removed. These entries never enter player launch
rewards, Unlocks, or production.

Hostile targeting combines reviewed per-mission enemy allowlists with guarded
discovery of placed or scripted military AI Houses. Player, allied, neutral,
civilian, future player-transfer, shared-country, and ambiguous duplicate
CountryType targets are skipped with exact log reasons. Multiple safe hostile
Houses receive the effect independently.

Settings exposes only working groups: **AI stat bonuses** and **AI
production-speed bonuses**. AI unit/building cost reductions are deliberately
absent because cheaper production does not strengthen effectively unlimited-
cash campaign AI. Generic AI unit unlocks remain excluded because they can
replace story-critical identities. AI support powers and superweapons remain
excluded because no end-to-end AI launch has yet been observed in an engine
log; configured ownership, charging, and targeting alone do not count as proof.
Unsupported types are logged when AI rewards are enabled.

### Buff type options

| Option ID | UI label | Effect per stack | Implementation scope |
|---|---|---|---|
| `production` | Production / construction time | 15% shorter production or construction time, capped at 80% shorter | Written to the currently buildable owned clone in Standard and Chaos. |
| `cost` | Cost reduction | 20% cheaper, capped at 100% | House/category scoped in Standard; unit-specific in Chaos. |
| `speed` | Movement speed | 10% faster per stack | Infantry uses isolated direct clones and cannot be raised above Speed `8`; infantry already at or above that ceiling is omitted from the Mobility reward pool. Faster native infantry retains its authored speed but receives no acceleration. Vehicles, naval units, and aircraft retain their existing house/category or unit-specific behavior. |
| `armor` | Armor | About 11% stronger effective durability per stack, capped at +1000% | House/category scoped in Standard; unit-specific effective durability in Chaos. |
| `health` | Health | 15% more health, capped at +1000% | Direct unit type; applied only when enemy use of that global type is not detected. |
| `sight` | Vision | +1 sight, capped at +100 | Direct unit type with the same safety guard. |
| `damage` | Damage | 15% more real impact/payload damage per stack | Direct or spawned-payload weapon data with unit, spawner, and shared-weapon safety guards. |
| `reload` | Unit fire rate | 10% shorter weapon reload | Direct weapon type with unit and shared-weapon safety guards. |
| `range` | Attack range | +0.5 weapon range, capped at +50 | Direct weapon type with unit and shared-weapon safety guards. |
| `ammo` | Ammo | +1 ammo capacity | Direct unit type with the same safety guard. |
| `passenger_capacity` | Passenger capacity +1 | +1 passenger slot | Repeatable direct transport-clone effect. Available for 20 reviewed cargo and capture-bay units. `Gunner=yes` IFV-family units and sealed internal-payload systems are excluded. `SizeLimit` remains unchanged. |
| `open_topped` | Passenger firing | Enables passengers to fire from inside the transport | One effective direct transport-clone stack. `Gunner=yes` IFV-family units and the noncombat Stallion are excluded. Units already using `OpenTopped=yes` omit this reward while retaining native firing behavior and passenger-capacity rewards. |
| `self_healing` | Self-healing | +1% maximum health per normal repair tick per stack, capped at 50% | Direct unit type. Every useful stack raises `SelfHealing.Amount`; the first also enables self-healing. |
| `cloak` | Cloaking | Enables cloaking | Direct unit type; one effective stack. |
| `sensors` | Sensors | Enables sensors with a unit-derived radius | Direct unit type; one effective stack. |
| `veteran` | Veteran start | Newly produced affected units start veteran | House scoped; one effective stack because the engine flag does not start units elite. Installed `Trainable=no` units such as Engineers and Spies are excluded. Generated country lists are bounded below the engine's single-value parser limit. |
| `build_limit` | Unique / hero unit limit +1 | Raises the normal simultaneous cap by one | Repeatable. Each earned stack adds one to that unit's isolated player/helper clone: four Tanya stacks permit five simultaneous Tanyas. Available only for the 16 trainable installed hero/unique units with a positive cap. Enemy caps stay native. Disabled when **Unlimited unique / hero units** is enabled. |
| `building_limit` | Special building limit +1 | Raises a special economy building's simultaneous cap by one | Repeatable up to four stacks and independent from hero capacity. Available only for Ore Purifier, Industrial Plant, Cloning Vats, and Reprocessor when special-building rewards are enabled. The four-stack limit prevents unusable extra copies and no-op rewards for facilities whose effect does not continue scaling. Heroes never offer this type; legacy hero Structure Capacity rewards migrate to the matching Command Capacity reward. **Unlimited unique / hero units** does not disable it. |

Passenger firing, Sensors, Cloaking, and Veteran start stop after one effective
stack. Production, cost, armor, health, range, vision, and self-healing stop at
their listed caps.
The final useful stack receives only the remaining effect needed to hit its cap;
seed planning reallocates later reward slots to other eligible buffs. Movement
uses category safety ceilings, and special-building capacity retains its
reviewed four-stack limit. Damage, reload, ammo, passenger capacity, and hero
capacity remain repeatable without an additional Randomizer stat cap.
Existing player configs enable newly introduced Passenger capacity and
Passenger firing once; previously disabled older buff types stay disabled.
Frozen seed reward settings never migrate.

Direct unit, defense, and weapon definitions are global to the map. The launcher creates narrow standalone `MORP...` TechnoType and `MORW...` WeaponType copies when needed to isolate earned buffs from enemies. Buildable defense buffs always use a complete installed-identity clone: player and enabled-helper placements, exact helper base-plan entries, veterancy lists, and relevant trigger event/action type references use the clone, while enemy placements, plans, original defenses, and original weapons remain unchanged. Clone `Owner` includes each allowed country's parent chain so transferred factories recognize custom campaign countries; concrete `RequiredHouses` remains the isolation gate, preventing hostile descendants of the same parent from receiving the clone. This is distinct from unsafe global country-section buffs. With helper buffs disabled, helpers retain only originals. Mobile helper TaskForces use compatible buffed clones while native originals remain buildable dynamic-AI fallbacks. Mission-critical events/actions follow a clone whenever every actual map consumer of its source type is friendly, even if the trigger itself is owned by an unrelated story house. Every friendly scripted TaskForce follows the same clone, including locked map-only hero aliases, so escort and hero-loss checks cannot watch a different identity from the one the mission creates. Shared enemy types are retargeted only in player/helper-owned trigger lists. If a buildable shared type has an outside-owned destruction event that cannot be assigned safely, the launcher creates a buffed build-only player clone while leaving every native placement, team, action, and event untouched; non-buildable ambiguous types stay native and skip unsafe direct buffs. Helper veteran lists prioritize every clone actually produced before fallback IDs so the engine's 480-byte value limit cannot silently remove veterancy. Positive ownership prevents enemy buff leakage and duplicate player cameos. Installed positive mobile-unit limits remain capped normally unless the seed enables the isolated unlimited setting or earns repeatable `+1` cap stacks; enemy originals retain native limits in both cases. Launcher locks `0` and one-build-only `-1` are never treated as live caps. Effects that cannot be isolated safely remain skipped and logged. Saved Standard rewards are canonicalized and faction-filtered again at launch, so corrected catalogue entries cannot keep leaking foreign technology from an older seed.

Trainable defense clones apply earned damage, range, and reload stacks to every direct rookie, veteran, elite, and gattling-stage weapon. Promotion therefore cannot replace a buffed rookie weapon with an unbuffed native elite weapon. Chaos clones also retain their all-Construction-Yard prerequisite lists, including Shipwrecked's captured-yard path.

Campaign factories obtained through object-level capture scripts are also recognized. `EBREED` uses PsiCorps2's captured Construction Yard, `EBLOOD` includes the PC-Base factories, and `SRAVEN` changes the tagged Guild3 base to the player. These houses are production-discovery sources only; they are not treated as allied helpers and receive no player buffs. Chaos production rewards now use per-clone `BuildTimeMultiplier`. When a Standard player country shares its parent with enemies and country multipliers must be skipped, isolated native-faction clones retain earned and retry-assistance production, cost, speed, and armor effects without changing enemy originals. This fallback remains active when allied-helper buffs are enabled; safe helper countries do not make the shared player country safe.

Reward labels shown in mission tiles, mission details, logs, and the Rewards tab state the actual effect, such as `Typhoon Attack Sub: Cost 20% cheaper`, instead of internal catalogue names such as `Attack Sub Logistics`. Access rewards use the installed playable roster name; for example, `HCRUIS` is shown as `Trident Battleship Access`, not the obsolete `Battlecruiser Access`.

The pool omits capability rewards a unit already possesses. Existing self-healing, cloaking (including staged/stop/attach-effect cloak), `Sensors=yes`, `SensorArray=yes`, and reviewed `OpenTopped=yes` transports are detected from the installed 3.3.6 definitions. IFV-family exclusions are detected by `Gunner=yes`, not unit names. Disguise kits, engineer tools, scanners, and explicit `NotAWeapon` helpers do not qualify their unit for weapon-stat rewards. Functional support weapons such as healing, repair, EMP, web, and time-warp tools remain eligible where reload or range really changes their effect. Legacy stored rewards that are now redundant or inapplicable retire without map injection.

### Non-UI configuration keys

These keys are runtime/developer controls and should not become normal Archipelago options without a design review.

| Key | Default | Purpose |
|---|---:|---|
| `generation.starting_unlocked_missions` | `3` | Mission List starting count. Grid Mode uses its own start rule. |
| `generation.enabled_reward_types` | `[access, buff, superweapon, secondary_superweapon, aid_power, power_buff]` | Derived compatibility list written from the six reward-pool toggles. |
| `generation.safe_player_country_buffs` | `true` | Enables the stable map-local country safety path. |
| `generation.experimental_house_buffs` | `false` | Legacy house-buff route; it is still constrained by the same no-reassignment trigger safety rule. |
| `archipelago.*` | Disabled; server `archipelago.gg` | Server, port, slot identity, client UUID, active manifest identity, and crash-safe synchronization checkpoint. Hosted rooms use `archipelago.gg` plus the game-server port shown on the room page. Passwords are never persisted. |

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

Standard keeps the reward pool appropriate to the selected campaign. Every earned role resolves to one equivalent for each production family available in the mission. The starting family's equivalent uses its own factory immediately; a foreign equivalent stays unavailable until that faction's barracks, factory, air command, or shipyard is captured or constructed.

**All Campaigns** keeps earned roles across the seed, but mission tech follows only physical or scripted production—not the campaign side or `[Basic] Player` country. An Epsilon-controlled mission operating only Soviet buildings therefore gets Soviet equivalents and no Epsilon units. Capturable Allied production prepares Allied equivalents behind exact Allied factories, remaining hidden until those factories are owned. The same rule applies to all four factions. Every map prepares one clone per mapped production unit and exact-gated Engineer/transport mappings. Native matching units retain campaign AI/script ownership but receive a human-only `TechLevel=-1` lock plus the hidden negative prerequisite gate, so only the correct clone appears in player production. Optional Tier 1 unit and defense starters use the same physical-tech gating.

Special map-provided barracks, such as the converted mine in **Epsilon Op: Fallen Ashes**, can train every exact infantry unit already unlocked by the player, regardless of faction. A deployed **Stalin's Fist** can produce only unlocked vehicles matching the mission's current Soviet or Epsilon player faction. These special factories preserve each unit's normal production building as an alternative.

With **Start with basic Tier 1 combat units**, Standard immediately grants five roles: basic ground infantry, anti-air infantry, a basic ground vehicle, an anti-air vehicle, and a basic aircraft. Their concrete variant follows physical production and the player house's subfaction. United States therefore receives Bulldog/Stryker/Stormchild, Europeans Cavalier/Archon/Harrier, Pacific Kappa/Tsurugi/Black Eagle, Russia Rhino/Tigr/Foxtrot, China Qilin/Halftrack/Foxtrot, Latin Jaguar/Halftrack/Foxtrot, PsiCorps Lasher/Gatling Tank/Dybbuk-Attacker, Scorpion Cell Mantis/Gatling Tank/Dybbuk-Attacker, and Epsilon HQ Opus/Gatling Tank/Dybbuk-Attacker. Installed IDs are `MTNK` for Cavalier, `STORM` for Stormchild, and `FOX` for Foxtrot. Standard keeps each placed or scripted faction mapping behind its exact prerequisite; foreign units and airfields remain dormant until capture. Chaos makes each selected unit available from every compatible production building and lets any Construction Yard build the required airfield.

With **Start with basic Tier 1 defensive structures**, Standard resolves the basic defenses for physical or capturable faction families and keeps each exact Yard prerequisite. Chaos selects one ground and one anti-air defense from distinct factions; any faction Construction Yard can build both. Advanced Pool exclusions always win.

Foehn Standard can still draw the campaign's bundled Allied/Soviet rewards, but earned roles now resolve to Foehn equivalents whenever Foehn production exists. Standard **All Campaigns** uses Allied, Soviet, and Epsilon reward markers; those markers likewise resolve to Foehn equivalents behind exact Foehn factories. The complete Foehn reward catalogue remains reserved for Chaos.

### Chaos

Chaos draws access and buffs independently from all four factions. Each exact unlocked unit or building is available through every compatible Allied, Soviet, Epsilon, and Foehn production category. Any unlocked Barracks shows all unlocked infantry, any compatible War Factory shows all unlocked vehicles, and the same rule applies to airfields, shipyards, and Construction Yards. Foehn unlocks therefore work in non-Foehn campaigns. Mission-specific production may add another valid factory, but cannot narrow Chaos back to one faction. Standard remains separate: own-faction production starts active, while foreign role equivalents retain exact captured-factory prerequisites.

### Randomizer Arsenal

Randomizer Arsenal creates and stores one mixed roster for every mission when the seed is generated. Reopening the launcher or replaying a mission reads that stored roster; it never rerolls. Selected units keep their installed TechLevel and matching Barracks, War Factory, airfield, or naval-yard production type, while compatible factories accept selected units from any enabled faction. Units and powers are temporary mission content, not permanent unlocks.

Mission rewards are buffs only. Each check draws from buffs affecting that mission's selected units or powers, plus the valid global production buff. Invalid, duplicate, or capped choices reroll through the normal planner. The existing **Unlocks** faction tabs mark the selected mission's temporary units and powers as active, with mission-specific tooltips; **Summary** shows its exact roster, powers, and active earned buffs. Save Settings / Load Settings includes the complete Arsenal faction, count, unit, power, and buff configuration without copying run progress.

With **Start with basic Tier 1 combat units**, Chaos shuffles all four factions across four guaranteed ground roles: ground infantry, anti-air infantry, ground vehicle, and anti-air vehicle. Lancer is Foehn's ground infantry and Knightframe its anti-air infantry. Ground vehicles, anti-air vehicles, and aircraft choose a deterministic valid subfaction variant. It then adds one seeded basic Allied, Soviet, or Epsilon aircraft. Every seed therefore starts with both ground and anti-air answers, exactly one ground starter from every faction, and one real AircraftType. Any player MCV/Construction Yard unlocks the player's native airfield for that aircraft.

With **Start with basic Tier 1 defensive structures**, Chaos grants Pillbox, Patriot, Sentry Gun, Flak Cannon, Gatling Cannon, Sonic Emitter, and Shrike Nest. Each accepts any available Allied, Soviet, Epsilon, or Foehn Construction Yard as its prerequisite. No player Construction Yard means no starter-defense cameo.

The sidebar groups earned production cameos into faction bands with the current player faction first. Same-tier buff sharing is optional and off by default.

## Power Reward Catalogue

All earned power rewards are restored by a player-owned map-start grant in future launched missions. Each reward uses a new map-local `MOR...` power copied from the complete installed definition. The original power and any mission scripts using it remain untouched. The copy does not require its normal source building or original subfaction.

Power buffs use the Advanced **Superpower Buffs** page and remain separate in
policy from unit/building buffs. Every unlockable power can receive faster recharge.
Paid powers can receive lower activation cost. Reviewed area powers grow
their `SW.Range` or private warhead `CellSpread`; reviewed timed effects grow
their direct or private-warhead duration. Direct-damage powers receive higher
`SW.Damage`. Safe UnitDelivery and paradrop rewards gain exactly one
additional payload object per stack. Spy Plane never gains redundant extra
aircraft; its reviewed reconnaissance buff increases only its private plane's
`Sight`. Unique source structures, beacons, and
fixed-layout grid spawners intentionally omit payload buffs. Buffs are folded
into the same isolated power/helper clones, never native campaign definitions.
Recharge, activation-cost, damage, and duration buffs stop at five stacks per
power. Seed planning reallocates later reward slots after a power reaches that
limit. Effect radius and extra delivered units remain unbounded.

| Category | Allies | Soviets | Epsilon | Foehn |
|---|---|---|---|---|
| Offensive superweapon | Lightning Storm | Tactical Nuke | Psychic Dominator | Great Tempest |
| Secondary superweapon | Chronoshift | Invulnerability (Iron Curtain) | Rage | None |
| Aid/reinforcement | Airborne; Bloodhounds; Lightning Rod; Ultra Miner; Kingsnakes; Paladin Aid | Engineering Team; Repair Drone; Tank Drop; Instant Shelter; Motor Ambush; Naval Mine; Terror Drop; Flame Tower; Drakuv Prison Vehicle; Repair Drones; Elite Reserves; Disruptor | Risen Monolith; Scout Raven; Vision; Magnetic Beam; Libra Clones; Bloatick Trap; Quick Fort; Ruiner; Hijackers | Spinblade; Megaarena; Knightfall; Harbinger; Sweeper Drop; Signal Jammer; Decoy Team; Decoy Squadron; M.A.D. Mine |

The copied aid powers keep installed costs, recharge times, delivered units, and effects unless their profile explicitly corrects a broken dependency. Engineering Team has no Barracks gate and uses the invoking country's normal paradrop transport, so it works for every campaign faction without training a Barracks unit first. Knightfall keeps its installed `6.5` recharge. The five mine/grid spawners are the timing exception: installed `0.01` is an internal one-shot construction helper, not a usable repeating-power cooldown. Minefields use the reviewed `2.5`-minute player-power timing and Confusion/Stasis grids use `1` minute. Paladin Aid and Knightfall receive their tested targeting and delivery corrections. Paladin Tank Hunter is also a separate Allied **Special** unit access/buff target; Paladin Aid remains available and delivers the current buffed player clone whenever one exists, with its native pair as the no-clone fallback. Drakuv, Ruiner, and Harbinger are available only through their aid powers; their `Trainable=no` payload types never appear as production rewards, unit-buff options, Unlocks cards, or random tech locks. M.A.D. Mine, Naval Mine, Drakuv, Ruiner, and Kingsnakes remove building/designator, inhibitor, source-range, and shroud gates from their copies while preserving land/water restrictions. Kingsnakes also uses a copied portal object with its separate `PoweredBy` dependency removed. Mercury Strike matches the supplied mapper-tested building-free `MultiMissile` form while isolating its original chain from campaign overrides: `Nuke.Payload=MercuryOverdriveAlt` and `SW.Warhead=MercuryStrikeAlt` reference registered map-local copies. It has no hidden uplink or inherited EMPulse range gate and retains recharge `6`, cost `-800`, weapon speed `100`, and damage `150`. Wallbuster uses a private mapper-tested `MultiMissile` carrier, upward projectile, downward projectile, and 320-damage payload chain instead of a hidden cannon. It retains installed recharge `8.5`, cost, `wbsticon.pcx` sidebar art, `RROCKET` projectile art, and red flare animation. Every private WeaponType, Projectile, and Warhead is registered in its engine type list. Zephyrobot is retired: its installed beacon requires campaign-specific Zephyr support, while portable hidden-support attempts remained non-firing and the instrumented form caused a runtime fatal error. Old saved Zephyrobot rewards canonicalize to a harmless retired entry. Tactical Nuke stays completely installed/global in every mission except Fatal Impact; there its randomizer copy alone points to a registered private copy of the installed 600-damage `NukePayload`, bypassing the map's 5000-damage objective payload.

Offensive and secondary rewards are also made independent from base power. Lightning Storm carries explicit normal storm values so campaign-specific weather scripts cannot silently reduce its damage or strike rate. Tactical Nuke remains the installed `MultiMissile` power with `NukeCarrier` in every normal mission. Fatal Impact alone redirects the reward copy to a registered private copy of the installed `NukePayload`: Damage `600`, `NUKE`, normal CellSpread. The mission's native Damage `5000`/`MIDASDeathWH` payload remains untouched and cannot affect the player reward. Chronoshift explicitly invokes its ChronoWarp follow-up; like the installed power, it moves team vehicles/units, not enemy units or infantry. Unthinkable keeps native `LIBRA` because its map-local Driller accepts only that exact passenger/operator ID; her earned buffs are applied directly. Bleed Red keeps its authored map-local `MORALES` Boris identity and every exact-type script reference native, preserving the delivery/death chain.

`V3 Test Drop` is preserved as a disabled custom-power and artwork template. When enabled, it delivers twenty player-owned V3 Launchers and uses `sidebar_image` from editable `assets/yuri_shocked.png`. The same source PNG drives both the launcher Unlocks cameo and the generated 60×48 indexed `SidebarPCX=moryv3.pcx`. Conversion stays in `runtime_assets`; the game-root copy exists only during a spawned game and is hash-verified before cleanup.

Blasticade is excluded: it only activates existing owned Blast Trenches, so a building-free reward does nothing by itself. Golden Wind is also excluded because it only overpowers existing Spinblades. Harbinger and EM Pulse no longer require or grant separate Harbinger Tower/EMP Control Station construction access. M.A.D. Mine deploys exactly one mine, matching installed `Deliver.Types=FAMMIN`; EMP, Cryomine, and Genomine field powers deploy four mines, while Confusion and Stasis Grid powers deploy nine grid cells.

The support/aid pool contains 82 active powers:

| Faction | Included support/aid powers |
|---|---|
| Allies | Airborne, Bloodhounds, Lightning Rod, Ultra Miner, Kingsnakes, Paladin Aid, Force Shield, Target Painter, Sonar Pulse, Mercury Strike, Satellite Scan, Black Widow Alpha, Black Widow, Chronoboost, Cryoshot, Cryospear, Glacial Screen, Cryomine Field, Chronolift, Backwarp, Hunter-Seeker |
| Soviets | Engineering Team, Repair Drone, Tank Drop, Instant Shelter, Motor Ambush, Naval Mine, Terror Drop, Flame Tower, Drakuv, Repair Drones, Elite Reserves, Disruptor, Spy Plane, Smoke Bombs, EM Pulse, Irradiation Gamma, Overcharge, Wallbuster, Irradiation Beta, Rad Attack, Pack Attack, EMP Minefield, Nuclear Path, Gear Change |
| Epsilon | Risen Monolith, Scout Raven, Vision, Magnetic Beam, Libra Clones, Bloatick Trap, Quick Fort, Ruiner, Hijackers, Shadow Ring, Kinetic Barrier, Geneburst, Toxic Strike, Regen Drugs, Wonder Drugs, Genomine Field, Psychic Flash |
| Foehn | Spinblade, Megaarena, Knightfall, Harbinger, Sweeper Drop, Signal Jammer, Decoy Team, Decoy Squadron, M.A.D. Mine, Nanofiber Sync, Boid Blitz, Recon Sortie, Devourer, Chaos Touch, Confusion Grid, Stasis Grid, Blackout Missile, Nanocharge |
| Neutral | Missile Strike, Maintenance |

Neutral Missile Strike clones and registers its complete carrier/up/payload/
down/warhead chain. Maintenance uses a private warhead for area and duration
buffs plus one invisible `CASTRF`-derived exact-House provider so its
zero-damage GenericWarhead retains a real firing owner. The private warhead is
registered in the map `[Warheads]` list before `SW.Warhead` is parsed, then
reuses the installed `MAINT` animation and `MaintAnimWH` repair loop. Both
remove their visible Tech Structure dependency and remain available in every
campaign filter.

Backwarp, Nuclear Path, Blackout Missile, Gear Change, and Nanocharge use private map-local effect chains plus invisible exact-House startup providers, so their reward copies do not require the native Warpshop, Nuclear Reactor/Converter, Palace, Cyberkernel, Industrial Plant, or Nanofiber Loom. Gear Change retains its installed duration/effect and shuts down every factory carrying the shared `fact` armor, including Allied, Soviet, Epsilon, and Foehn War Factories. Psychic Flash directly targets Inferno Tower and Antares defense identities plus their current player clones; planning withholds it until either defense is unlocked. Nanocharge is targetable only while an owned Leviathan or Mastodon (including its current player clone) is on the field. Hunter-Seeker uses the same reviewed hidden-provider pattern. Blasticade and Golden Wind remain excluded because they still need preplaced Blast Trenches or Spinblades.

Elite Reserves is the building-bound exception. Its clone is attached to Allied, Soviet, Epsilon, and Foehn Barracks variants and restricted to the player countries. It is never granted through action `34`, avoiding the proven crash while creating its internal `F_ERESB` academy marker. Selling or losing the granting Barracks removes that instance; rebuilding a Barracks restores access.

Standard uses campaign-appropriate power factions; Foehn Standard additionally includes native Foehn powers alongside its Allied/Soviet operating technologies. Chaos draws all four factions' power rewards, so any player faction can earn and use them.

## Seeing Exact Rewards

The reward count is a summary, not a mystery bundle:

- Hover an incomplete mission row to see every remaining check and every assigned reward name.
- Select a mission and open **Mission Details** to see each objective/victory check, its completion state, its count, and the full reward-name list.
- Enable **Hide reward names in Mission Details** to replace assigned names in Mission Details and mission-row hover text with `?????`. Earned items remain visible in Unlocks.
- Open **Unlocks** for faction tabs containing every unit, defense, aircraft, and configured superpower cameo. In Randomizer Arsenal, normal icons are the selected mission's seed-fixed temporary roster/powers and black icons are absent from that mission; hover identifies the mission and whether earned buffs are active there. In other modes, normal icons are unlocked, green icons have a reward in a presently playable mission, gray icons are assigned but still locked, and black icons are unavailable in the current seed. Green-icon hover outlines matching playable Grid nodes; in Mission List/Classic it renders matching mission rows green, bold, and underlined. Search controls exist only inside **Summary**, which also shows the selected Arsenal mission's roster, powers, active buffs, searchable earned-reward listing, and concrete Tier 1 starter names/cameos. Locked-grid privacy removes green/source/node hints. Standard keeps native Foehn unit icons unavailable because those rewards are Chaos-only. Custom powers use their configured launcher artwork.
- The mission table `Rewards` fraction counts reward items, not checks. With 30 rewards per check, completing one check advances it by 30.

Reward assignments are generated and stored when the seed is created. Access rewards are unique within a seed; once access is planned for a unit, later eligible slots can provide repeatable buffs. Sensors, Cloaking, and Veteran start are the only one-stack buffs.

Victory is its own reward check. Normally, when the victory marker is detected, the launcher also grants any objective checks that were missed by the log watcher, so a won mission cannot remain partially rewarded. With **Rewards only when mission is finished**, objective checks carry no player rewards and Victory alone grants `Rewards per mission × mission weight`.

## Mission Launch and Progress

The launcher reads campaign metadata from `INI\BattleClient.ini`, prepares a loose generated copy of the selected map, and starts:

```text
Syringe.exe gamemd.exe -SPAWN -CD -SPEEDCONTROL -LOG
```

The generated map contains the current tech locks/unlocks, safe rewards, and objective/victory marker actions. The launcher watches `debug\debug.log`, records each marker once, and removes the temporary root map when the spawned process exits. After detected victory it waits briefly, closes the spawned game process tree, and prevents continuation into the normal campaign flow.

Reviewed mission compatibility rules remain local to their source map. Machinehead exposes both native and isolated Foxtrots through `NAAIR`; parallel count triggers accept sixteen of either identity. Singularity completes when Malver, Virus, and the Psi Trooper identities are absent after boarding the Driller, instead of waiting for every randomizer-owned PsiCorps unit to disappear. Tainted Empire retries Yunru only while no Yunru exists. Machinehead also keeps its drop-pod `LIBRA`, follow-up teams, and Event 61 loss check on the same native identity. Juggernaut preserves its scripted Hammer Defense and Iron Guard actions, then exposes every earned defensive structure through the mission SMCV rather than reducing access to those two native defenses. Mermaid, Hammer to Fall, Power Hunger, and Kill the Messenger keep their objective hero/transport types native so exact loss, operator, and passenger checks continue to work. Power Hunger keeps map-local `DRIL` as its authored Burillo, keeps all scripted `INIT` Desolators and native `SAPC` under the authored USSR/Latin/Special coalition, applies Morales buffs from his mission base, and exposes native Burillo behind Soviet War Factory as recovery access. Once Morales has entered Burillo and Objective 2 defenses are destroyed, Objective 2 completion creates both Latin AI and player `SAPC+SMCV` delivery teams. Latin transport is prebuilt, unloads, then guards in place while the original SMCV/base sequence continues. Objective 2 also sets authored base-ready local `47`, guaranteeing Latin ConYard creation and AI activation even if visual reinforcement creation fails. Later authored triggers retain their other effects but cannot create duplicate MCVs. The Remnant exposes native Allied and Soviet MCVs by default without cloning them; edit `configs/missions.json:original_mcv_access` to replace those IDs or use an empty `FREMNANT` list to disable them. Kill the Messenger changes only its scripted SMCV to Speed `16`, immediate acceleration, and faster turning so it reaches the deploy cell before pursuing tanks. Reality Check keeps `LIBRA` and all eight conversion phases native, raises their mission bases to five times authored strength (`6000` or `7500`), then adds every earned direct unit/weapon buff. Native conversion and Event 61 loss references therefore stay synchronized.

Insomnia keeps initial and respawned Tanya/Siegfried on native identities, applies earned buffs directly, and keeps their Event 61 absence checks synchronized with the living heroes.

For action codes, trigger selection, marker construction, ordering guarantees, cleanup, and known mismatches, see [Objective and Victory Hooks](TECHNICAL_FINDINGS.md#objective-and-victory-hooks).

## Saved Data

| Data | Source mode | Packaged mode |
|---|---|---|
| Static gameplay/UI configuration | `RandomizerLauncher\configs` | `RandomizerLauncherData\configs` |
| Config defaults | `RandomizerLauncher\configs\player\mental_omega_randomizer.yaml` | `RandomizerLauncherData\configs\player\mental_omega_randomizer.yaml` |
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
- Archipelago requires the matching launcher/APWorld release and an exported
  player YAML for the active run. A different seed, configuration, catalogue,
  or edited manifest is rejected before tracking begins.
- Generating or loading AP YAML stages connection data only. Standalone rewards
  and Unlocks remain active until the server slot validates. Once validated,
  AP rewards stay active while disconnected so offline checks and reconnects
  remain safe. **Generate New Seed** clears AP mode and returns to standalone.
