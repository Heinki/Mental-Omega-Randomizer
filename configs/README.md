# Static Randomizer Configuration

These JSON files contain editable gameplay and presentation data previously
embedded in Python modules. Restart the launcher after changing a file.

`player/mental_omega_randomizer.yaml` is different: it is ignored local runtime
state containing next-seed and launcher choices. Source runs create it here so
all configuration is grouped under `configs/`. Packaged runs create the same
relative path under `RandomizerLauncherData/configs/player/`. Do not commit a
personal player YAML.

The six `Randomizer*.ini` files do not replace these documents. INI files are
complete player-owned TechnoType templates. JSON files define randomizer
policy, reward identity/display, mission exceptions, cross-faction roles,
stacking, compatibility aliases, and building-free power conversion. The main
intentional overlap is `rewards/unit_data.json`: roster/base-stat snapshots
could eventually be derived from static INI templates, but current reward
construction and old-save compatibility still consume its labels, categories,
role groups, linked identities, and special damage metadata. Remove or migrate
that overlap only with full reward-plan and 97-map parity coverage.

## Files

- `default_player_config.json`: fallback player, generation, launch, privacy,
  reward-weight, and future Archipelago settings used when active YAML keys are
  absent. `restrict_final_mission_rewards` defaults to `true` for new seeds
  and restricts every Grid-goal/final Mission List check to buffs, including
  multiplier bonuses. Existing saves without the field keep their plans.
  `generation.reward_weights` stores bounded `0`–`100` main,
  unit-buff, and power-buff selection weights; absent legacy keys use `100`.
  `generation.starting_reward_count` and `starting_reward_types` control the
  separately seeded pre-mission unlock grant; allowed families are access,
  offensive powers, secondary powers, and aid powers. Buff-family IDs from
  legacy or portable settings are discarded; legacy configs default to zero.
  `generation.starting_unlock_rewards` stores portable canonical reward names
  manually selected in Advanced -> Starting Unlocks; only permanent content
  access/power rewards survive normalization, and legacy configs default empty.
  `generation.access_limits` optionally caps unique unit/building and power
  unlock identities across Starting Rewards and mission rewards. Its `units`
  and `powers` values are positive integers; `enabled` defaults to `false`, so
  absent legacy settings retain unrestricted planning. Shop Mode and Randomizer
  Arsenal ignore these caps.
- `missions.json`: mission build classifications, configurable mission reward
  classes/multipliers and per-mission overrides, optional-operation membership, helper/enemy house policy,
  production/power house exceptions, native identity exclusions, map-specific
  access rules, original mission-only MCV access, native-variant buff
  forwarding, and campaign starter families.
- `map_rules.json`: controlled technology locks, TechnoType registry mapping,
  and parser/engine safety limits used by generated maps.
- `factions.json`: Engineers, MCV/Construction Yard mapping, production
  buildings, amphibious transports, Chaos production, and tech
  ordering, plus default unlock owners and special-factory identities.
- `tier_one.json`: subfaction-specific land/air starter equivalents, faction
  naval-attack and anti-air ship equivalents, fixed faction Tier 1 defensive
  structures, Standard role markers, aircraft factories, and installed
  GenericPrerequisite aliases. `ground_roles` and `naval_roles` identify the
  separately faction-shuffled Chaos/Shop role groups; every naval-role entry
  must use production category `naval`.
- `shop_mode.json`: Shop Mode run length, mission choices and class rewards,
  stage difficulty weights, Ore/Gem unit prices, permanent upgrade
  definitions, reward exclusions, and launcher-only mission effects.
- `final_fortress.json`: independent Final Fortress map, survival timing,
  native AI difficulty, shared faction wave stages with alternative mixed
  compositions, milestone/camp Defensive Points identities, and permanent perks.
  Two/three-human co-op uses the existing friendly waypoints and host loadout.
  Humans consume friendly seats before the allied-helper perk: at most one AI
  with two humans, none with three. Plan 22 freezes names and per-human setup
  score corrections; state schema 9 stores local co-op participation receipts
  without copying the host's permanent perk ownership to guests.
  The saved x1–x10 wave multiplier changes additional spawn counts independently of AI
  difficulty selection. Difficulty also supplies first-wave base counts of
  3 / 6 / 9 per active side. The configured unit budget applies after multiplication;
  `wave_pressure` defines growth by the starting amount, one/two/three spawn
  sides at minutes 5/10/15, and a separate living-wave unit limit. Both shared
  limits are provisionally 480. New runs split that budget into eight reusable
  20-unit slots per enemy. Small mixed deliveries reuse empty slots without
  waiting for an entire earlier wave; each next interval begins after the
  preceding delivery finishes. Normal AI production is excluded. Help contains the
  wave forecast. All twelve native country pools include three time stages
  with four mixed compositions each, including infantry-led columns.
  `wave_air_support` is an optional ordered list of `from_seconds`, `percent`
  and `units_by_country` stages. Each country has one to four weighted native
  flying-vehicle choices (`type` and relative `count`). Shipped stages replace
  15% of the existing wave budget from minute 15 and 25% from minute 30, adding
  heavy aircraft to the later choices. Ground identities, infantry and selected
  Powerhouses retain at least one member. Air and ground use separate attack
  teams sharing the existing unit slots; no extra population ceiling is added.
  The frozen run retains the stage table and resolved air types/counts.
  Miners in the Sun is the single source;
  human waypoint 3 faces enemy waypoints 0, 1, and 5. The protected Einstein
  Lab (`CALAB`, 3 × 4 foundation) starts at (91, 57).
  Milestone rewards are incremental: 25 Defensive Points at minute 25 and another 25 at
  minute 45; `completion_gems: 50` brings the victory total to 100 at one hour.
  `survival_seconds: 3600` admits eleven five-minute waves, through minute 55.
  `performance` defines kills per reward tier, Defensive Points per tier, and a tier cap.
  Native setup transfers are excluded from the local kill score.
  Each camp defines `position`, `enemy_index` (0–2), installed `guards`, and
  `gems`. Optional `guard_positions` supplies reviewed clear, level cells for
  expanded formations. `camp_balance` defines `guards_by_difficulty` (shipped
  Casual/Normal/Mental 5/8/12), `max_guards_per_camp` (30),
  `max_total_guards` (180), `special_chance_percent` (35) and reviewed
  `special_units_by_country`. New plans multiply the difficulty baseline by the
  selected wave multiplier before applying both ceilings, then select varied
  mixed formations from native faction wave rosters. Camp roster factions are
  independent of the enemy base rolls: Allies, Soviets, Epsilon and Foehn each
  appear before any family repeats across the six camps. Each camp draws one
  seeded subfaction roster while retaining its configured enemy AI owner.
  A special roll replaces one ordinary guard with a faction hero or heavy.
  Optional `camp_balance.starter_camps` names nearby `camp_ids`, lower
  `guards_by_difficulty`, separate `max_guards_by_difficulty` and basic
  `units_by_country`. The shipped north-east starter camp uses 2/3/4 infantry
  on Casual/Normal/Mental before multiplication, capped at 4/6/8. It never
  receives advanced wave formations or special guards; its normal rewards are
  retained. Runtime validation restricts starter guards to installed TechLevel-1
  infantry. The other five camps keep their existing formation/count rules.
  Balance settings and resolved formations are frozen with the plan.
  Guards use private copies owned by that enemy AI, with normal speed
  and passive acquisition disabled until an attack wakes their team. The
  native crate appears after all guard identities disappear and Defensive Points are earned
  immediately on clearance. Only player entry at the camp center claims the
  separate frozen cash/unit reward. AI can remove the physical native crate
  without consuming that player claim. Earlier frozen plans keep pickup-based
  Defensive Points rewards and their original guard compositions.
  `challenges` references the Grid enemy stat/production, Powerhouse and
  reinforcement-power catalogue through
  `enemy_effect_id`; `victory_gems_per_stack` prices each enabled stack.
  Shared Grid definitions supply labels, eligibility, formulas and stack caps.
  Fortress also provides the aggregate `faction_superweapons` effect, granting
  each enemy its own native-recharge offensive power. The five new effects
  each have one toggle/stack. Reinforcement powers support optional integer
  `shots` (1–12, shipped 3) and `recharge_multiplier` (1–10, shipped 2).
  They are not initially charged. Their native-delivered units are outside
  scripted-wave admission, so finite shots bound lifetime extra populations.
  Powerhouses use Grid's rotating family heavy pools inside the frozen wave
  and living-unit budgets, replacing ordinary members when the cap is full.
  Their wave teams are veteran; this mode does not add Shop-stage companions.
  `crate_rewards` defines weighted credit/unit outcomes; each unit outcome
  has `units_by_country` for all twelve playable countries. Reward choices
  are frozen per camp in the run plan, and only player claims receive them.
  `perks` specifies permanent purchases and up to six increasing-price `ranks`
  (eight for `periodic_reinforcements`).
  Each rank has `gem_cost` and its complete cumulative `effects`; rank one
  must match the entry's base `gem_cost` and `effects`. Effects are not added
  again for earlier ranks. Purchases enable the perk automatically; disabling
  it preserves ownership. Removed perk IDs remain owned in saved state.
  Supported effects include starting credits, units/defenses and veterancy;
  `production_percent` (up to 50), `defense_percent` (up to 60), veteran defenses,
  separate `tier_buffs` for tiers `1`, `2`, `3` (up to 30 each), `reveal_map`,
  and `allied_helpers` (up to two). The shipped production perk has five ranks
  capped at 25%. Country-specific `starting_units_by_country`,
  `buildings_by_country`, `defenses_by_country`, `power_buildings_by_country`, `harvesters_by_country`,
  `fallback_units_by_country`, and `support_powers_by_country` cover all twelve
  native countries. These values name installed types, not generated private
  IDs. A combined starting army cannot exceed 15 units. Fallback infantry are
  granted only when no other starting army is selected. Army `veterancy`
  supports 1 (Veteran) and 2 (Elite, the native maximum); the shipped perk has
  both ranks. `support_powers_by_country` supports up to five cumulative native
  powers, with one additional unlock per shipped rank. The first two ranks
  retain their earlier faction-family powers; later ranks use country-specific
  selections. Native recharge times, use costs and localized names are retained.
  `superweapons_by_country` has two shipped cumulative ranks: the country's
  secondary power first, then that power plus its offensive superweapon.
  `starting_credits` has six shipped ranks at +2,000 per rank, up to +12,000.
  Production speed covers infantry, vehicle/naval, aircraft, building and
  defense queues. `power_upgrade_stacks` (0–6) applies that many compatible
  Grid/Shop power-buff stacks to every enabled perk power and superweapon;
  capability caps still apply and no power is granted without its unlock.
  Shared reviewed definitions in `rewards/power_buffs.json` determine which
  powers support vision, area, payload, duration, damage and other effects.
  Each unlocked power receives its own owned invisible launch provider in
  new runs. Great Tempest upgrades and private Foehn Nanofiber mutations also
  stage animation art and early registry entries before the Fortress country
  preload is merged.
  `special_units_by_country` grants cumulative reviewed production access for
  all twelve countries. Each rank must append exactly one distinct special type
  to its previous rank's list. The shipped three-rank family sequences use
  private reviewed Shop/Grid models, ordinary faction-factory prerequisites,
  and the original credit costs/unique limits, leaving native enemies unchanged.
  `reinforcements` contains `first_seconds`, `interval_seconds`,
  `max_active_units`, and `units_by_country`, plus optional `veterancy` (0 Rookie,
  1 Veteran, 2 Elite). The shipped eight ranks arrive every
  300 simulation seconds from minute 5 and retain ten basic infantry while
  improving the 10/14/18/21/24/25-unit roster through rank six. Ranks seven/eight
  retain that roster and grant Veteran/Elite units, respectively, without
  changing timing or the cap. Each arrival may contain at most
  six distinct installed ground infantry/vehicle types and 30 units per house.
  Units with untracked passengers, aircraft spawns or building deployments are
  rejected by the native adapter. Helpers receive the same arrival, and a whole
  coalition arrival must fit within the shared 150-unit reinforcement cap.
  Plan-17 runs use at most fifteen reusable groups shared across all houses
  (ten units each with the shipped 150-unit cap). A group is released after all
  its private identities disappear, including captured/converted units. Partial
  groups retain their full reservation. Each house has independent timers and
  resumes its next small delivery when shared capacity returns; the player sees
  a capacity-wait message. No fixed per-house quota is imposed. Spawn waypoints
  10–12 use the center of their existing protected 5x3 aprons.
  Ordinary production, starting grants and enemies are outside this cap. The
  adapter supports at most eleven friendly arrivals before the survival deadline;
  reducing intervals or increasing duration must respect that native flag budget.
  `healing_stacks` (0–6, shipped three ranks) enables rookie self-healing and
  uses the shared maximum-HP healing calculation. Existing stronger native
  amounts and native intervals remain. `recon_stacks` (0–6, shipped three)
  adds sight and supported cloak sensors without shrinking native sensor range.
  `unique_limit_stacks` (0–6, shipped three) raises eligible positive live-unit
  limits without granting access or removing production gates. `income_stacks`
  (0–4) adds five credits per stack to eligible special-building payout amounts,
  retaining their delay and prerequisites. No buildings or free income sources
  are granted. All four use private player/helper types, reviewed eligibility
  and linked-form propagation. Native captured income buildings remain native.
  `map.allied_waypoints` reserves up to two distinct unused native starts;
  `map.perk_layouts` covers the human and each configured helper with five
  building positions, sixteen defense positions, twelve power-plant positions,
  and a 5-by-3 army staging area. Old snapshots with four defense positions
  remain readable. Defense ranks give four copies of each cumulative unlocked
  type, up to sixteen. `power_buildings_by_country` supplies enough native
  plants for defenses and the five optional starting buildings. It supports
  up to twelve plants per country; edit their quantities with the power budget
  in mind. Perk details show cumulative per-rank grants for the selected faction.
  Audit foundations and terrain before changing these positions. Helpers use
  the player's faction and the same selected perks. Preplaced refineries have
  one separately configured harvester to avoid duplicate native free units.
  Shipped positions now stay within projected playable `LocalSize`, with actual
  terrain-height/foundation audits. Runtime placement checks conservatively
  allow for elevation and reject off-map added objects before writing files.
  `map.enemy_defenses` provides `layouts` for the three enemy waypoints (12–32
  positions each, shipped 24) and `types_by_country` with three distinct faction
  turret types. Each successive position cycles basic/anti-air/advanced types.
  New plans require this setup. Enemy buildings are private immune copies;
  their country starts with an immune construction yard and their build lists,
  upgrade links, MCV deployment, refinery free units and docking stay connected.
  Fixed perimeter turrets are power-independent and unbuildable. Ordinary troops
  remain damageable. Player/helper buildings retain their separate rules.
  `map.enemy_wave_positions` supplies three reviewed 5x3 arrival aprons, keyed
  by enemy start waypoint. Top-left cells are (93,147), (79,168), (142,166).
  Invisible passable foundations prevent later construction; separate waypoints
  16–18 spawn units beside construction yards. New enemy wave pools support a
  shared living ceiling of 3–480; at most eight groups of up to twenty are
  reserved per enemy, rounding down where the configured ceiling requires it.
  New protected enemy buildings/MCVs are not legal attack targets; private helper
  scripts replace building-only assault objectives with legal hostile targets.
  The saved `preferences.mental_ai_boost` checkbox defaults false and freezes as
  `plan.mental_ai_boost` for new runs. It loads the installed Mental AI game-option
  INI before cloning factories, so enemy and helper AI receive the native option.
  Plan 17 also creates a separate display-only `Next enemy wave` recharge timer,
  using `wave_interval_seconds`. It resets after each complete enemy delivery,
  waits at zero during a capacity delay, and is removed after the final wave
  or objective completion. Its hidden provider at (113,71) uses the reserved
  utility row and cannot be built or fired by the player. Its ownership transfer
  is included in the setup score correction; removal is silent.
  Both map rules and early rules preload include the changes; `spawn.ini` also
  records `MentalAI=Yes/No`. No extra Challenge Defensive Points are awarded for this setting.
  Six camps now cover the map; guard and claim cells require clear playable
  terrain. Preplaced guards sleep until the existing attacked-team behavior wakes
  them. Preplaced starting-army experience encodes ranks as 100/200, while native
  TeamType veterancy keeps its existing one-based enumeration.
  Saved state schema 9 stores purchased ranks up to six (eight only for
  `periodic_reinforcements`) and migrates the former
  one-rank offensive-superweapon purchase to rank two. Run plan 21 freezes their effects,
  power-upgrade stacks, starting power plants and helper starts with the original balance snapshot, preserving existing
  Defensive Points receipts when current configuration changes, including special access and
  the complete friendly reinforcement schedule, utility stacks and Powerhouse
  wave identities, four-faction camp rosters, staged air attacks and the revised
  safe layouts/enemy fortifications. Earlier plan versions remain
  readable with their original effects. The former six-unit
  Reinforcements purchase migrates to army rank two.
  The separate **Testing (all unlocks)** profile is available only in a source
  checkout with an existing ignored `final_fortress_testing_state.json` save;
  selecting it also adds newly configured unlocks at maximum rank without
  resetting Defensive Points, results, frozen runs or previously disabled selections.
  Its unlock updates and gameplay receipts never change the Standard save.
  Compiled EXEs expose Standard only and reject all-unlocks initialization.
  See [FINAL_FORTRESS.md](../FINAL_FORTRESS.md) for the configuration contract
  and gameplay validation limits.
- `ui.json`: difficulties, game speeds, campaign/reward/progression choices,
  EVA announcer tags, reward-count messages, faction colors, and
  light/dark palettes.
- `rewards/unit_data.json`: unit and defense rosters, base stats, reviewed
  transport passenger/open-top baselines and behavior exclusions, weapon stats,
  cross-faction role-equivalence groups, linked deployment/mutation buff identities,
  buff targets, labels, hero limits, and
  special weapon damage fields.
- `rewards/unit_policy.json`: installed capabilities, reward exclusions,
  trainability/naval classification, always-available essentials, trainable
  defenses, alternative production facilities, linked land/water access
  identities, and unit-specific display wording.
- `rewards/special_buildings.json`: editable faction economy/special-building
  access rewards, including labels, native Construction Yards, tech levels,
  build limits, sidebar build category/priority, and whether repeatable +1
  capacity rewards are generated. Chaos translates these buildings to every
  faction Construction Yard. Superpowers remain separate rewards.
- `rewards/buff_exceptions.json`: reviewed per-buff TechnoType exclusions.
- `rewards/power_buffs.json`: reviewed power-specific recharge, cost, area,
  damage, duration, delivered-payload, and reconnaissance-plane vision buff
  capabilities and stack tuning.
  Supported effects have no Randomizer-imposed stack ceiling.
  - `rewards/enemy_scaling.json`: reviewed hostile-AI CountryType armor,
    T1/T2/T3 unit and weapon bonuses, production-speed rewards, and support
    powers; per-stack tuning, positive engine clamps, allowed effect IDs, and
    hard per-effect caps. The base Randomizer assigns them beside normal
    reward slots without replacing player rewards. Archipelago exports the
    selected inventory as extra Trap items with matching extra locations.
    Player settings can narrow but never exceed the enabled bonuses' real
    combined capacity.
- `rewards/catalogue.json`: unit access items, faction access rules, buff type
  definitions, superweapon templates/rewards, support and aid-power definitions
  and mappings, access aliases, and retired reward compatibility entries.
- `rewards/tuning.json`: stack multipliers, per-category movement-speed
  ceilings, retry-assistance behavior, clone prefixes/production-field policy,
  reward count limits, and global-buff planning cadence. Display text,
  effective stack limits, and generated map values use the same data. Unit
  damage uses x1.15 per stack and caps at x6 total (+500%) on stack 13.
- `RandomizerInfantry.ini`, `RandomizerHeroes.ini`,
  `RandomizerVehicles.ini`, `RandomizerShips.ini`,
  `RandomizerAircraft.ini`, and
  `RandomizerDefensesAndSpecialBuildings.ini`: split static `MORP*` player
  roster. Infantry definitions come from mapper-reviewed `InfantryList.txt`;
  remaining definitions are Mental Omega 3.3.6 identity snapshots. Ships still
  register under engine `VehicleTypes`. Hero file contains capped reward heroes
  plus mapper infantry extras. Mission generation buffs these owned types while
  native IDs remain reserved for campaign AI and scripts. These files are a
  stock-rules snapshot, not the final clone body: map generation replays the
  shared template policy in `randomizer/rewards/template_policy.py` over the
  installed rules registry, so a submodded `rulesmo.ini` reaches every player
  clone. A reward whose source section is absent from installed rules (Super
  Thor, boss Brutes, campaign-only heroes) keeps its committed definition.

## Shop Mode balance

`shop_mode.json` is the only static source for Shop Mode economy and run-size
policy. `settings` defines positive `run_length` and `mission_offer_count`, the
non-negative `max_selected_permanent_units` and `starting_run_coins`, the
positive `maximum_starting_ore` and `minimum_shop_price`, and the version-1
`per_run` reroll policy.
`run_modifier_victory_run_coins` and `run_modifier_victory_meta_coins` set the
extra Ore and Gems paid per distinct enabled modifier on each victory.
`archipelago_purchase_locations` is the generated purchase-check count from
0 through 25, `archipelago_purchase_meta_coin_cost` is their positive shared
Gem price, and `archipelago_mission_victories_are_locations` controls
whether the ten stage victories also enter the shuffled AP item pool. These
values are signed into Shop player YAML and validated again at connection.
New Shop YAML signs `received_unit_loadout: all`: every received AP unit is
active on every Shop run without consuming permanent extra-unit slots. Legacy
`manual` and `random` rooms remain compatible and receive the same all-unit
behavior. This policy never changes Shop currency or mission-credit values.
`excluded_reward_ids` removes canonical rewards from Shop stock without
retiring them from normal Randomizer progression or old save receipts.

Legacy code and saved-state identifiers retain `MissionOffer`,
`mission_offers`, and `mission_offer_count` for compatibility. Player-facing
text calls every map presented at a stage a **mission choice**.

`mission_rewards` must contain exactly `act_1`, `act_2`, `operation`, and
`finale`. Each class has a display label, unique positive difficulty rank, and
non-negative Ore (`run_coins`) and Gem (`meta_coins`) rewards.
Gem rewards must increase strictly with difficulty. Mission-choice generation
samples only its named Shop RNG stream. Stages 1–2 offer only Act 1 and include a
fixed-unit or hero mission when the eligible pool provides one. From stage 3,
every remaining eligible mission has equal selection probability, regardless
of class or run length. All three mission choices can be finales. Completed
missions and duplicate choices are excluded; mission-pool inclusion settings
still apply.
The former `stage_class_weights` section is no longer used; older configuration
files containing it remain loadable.
`stage_difficulty_weights` independently controls actual in-game Casual,
Normal, and Mental difficulty for each visible mission choice. Profiles use the
same ascending percentage boundaries. Each choice's difficulty is derived from
run seed, stage, and mission code without consuming mission-selection RNG.
Stages 1–3 are Casual-heavy, stages 4–5 are Normal-heavy, stages 6–7 introduce
Mental, and stages 8–10 give Normal and Mental equal weight. Difficulty Assist
reduces only the chosen mission by one step.
`unit_inventory_size` controls deterministic Current Run Shop unit stock. Unit
stock remains stable during a stage and rotates after each mission victory;
eligible buffs remain available for every currently owned unit. Access entries
whose target is already active are removed before display and receive stable
replacement stock entries, covering starters, permanent/AP access, and run
purchases.
`power_inventory_size` controls the power stock shown beside unit/building
stock in the same Current Run Shop list and uses the same owned-access exclusion.
`discount_specialization` retains its stable save ID but applies its configured
`ore_per_level` discount to all Current Run Shop access and buff entries. Old
saved category fields remain readable and are ignored.

`mission_effects` defines deterministic one-mission player boons and hostile
challenges. Each entry contains display text, non-negative Ore/Gem bonuses,
and exactly one of `player_reward_ids` or `enemy_reward_id`.
`exclusive_reward_ids` suppresses a player boon when its access reward is
already active. Prefer access plus payload/recharge rewards for temporary
support boons: an unowned power becomes available, while an already-owned
power still receives a useful mission-only upgrade. The three visible mission
cards resolve duplicate effects to other entries of the same boon/challenge
kind without consuming gameplay RNG.

`unit_target_prices` is the Shop price table for units, aircraft, naval units,
defenses, and special buildings. Every active Shop target ID must appear
exactly once. Dormant rows are allowed so preserved customized reward
catalogues remain compatible when a launcher update adds a target. Each entry
has `run_access`, `run_buff`, `permanent_access`, and
`permanent_buff`. Prices are positive integers; use `null` only when that
target has no corresponding access or buff offer. Run and permanent fields for
the same offer kind must either both be priced or both be `null`. This table is
deliberately target-specific: TechLevel still supplies the displayed tier but
never determines a unit or targeted-buff price.

```json
"E1": {
  "run_access": 2,
  "run_buff": 2,
  "permanent_access": 8,
  "permanent_buff": 5
}
```

`power_target_prices` is the target-specific table for aid powers and
superweapons. Every active Shop power target must appear exactly once with
positive `run_access`, `run_buff`, `permanent_access`, and `permanent_buff`
prices.
The run and permanent fields for each offer kind must have matching
availability. `null` remains reserved for a target that lacks that offer kind.
Permanent powers activate automatically in future Shop runs without consuming
unit loadout slots; their permanent buffs apply whenever the power is active.
Discounted prices use integer percentages, round down, then clamp to
`minimum_shop_price`.

`permanent_upgrades` maps stable IDs to `display_name`, positive `max_level`,
one positive price per level, and integer `effects`. Optional boolean
`purchasable` defaults to `true`; `false` retains a retired upgrade ID for old
profile normalization while hiding it and rejecting new purchases. Version 1 requires
the full stable account-upgrade catalogue, including `coupon_book`,
`stock_lock`, `veteran_academy`, `gem_dividend`, and `premium_supplier`.

Gem Dividend pays on every mission victory from the Ore balance held before
the victory reward or Liquid Assets liquidation. The defaults grant 1 Gem per
5 Ore, capped at 2 Gems per upgrade level; the held Ore is not spent. The
mission preview and victory total include this bonus.

`modifiers` maps stable IDs to display text and additive or
percentage economy effects. Percentage modifiers multiply exactly; flat
modifiers add. Unknown saved modifier or upgrade IDs fail with a
clear state error instead of silently changing balance.

Modifier effects support economy, stock size, mission-choice count, starter
composition/veterancy, player clone damage/durability/cost/production,
aid-power recharge, mission starting Credits, and feature-disable flags.
Percentages multiply in persisted modifier order; flat effects add. Each
distinct active ID contributes one visible difficulty point and earns the
configured victory currency bonus. `blind_choice` uses the hidden-offer count
only for presentation and never consumes gameplay
RNG. Combat changes are applied to isolated player clones; overlapping
production modifiers multiply instead of overwriting each other.

Example mission reward:

```json
"operation": {
  "display_name": "Operation",
  "difficulty": 3,
  "run_coins": 7,
  "meta_coins": 3
}
```

## Mission-specific overrides

Add reviewed map exceptions to `missions.json`; do not add mission-code
branches to the Python pipeline. Available sections cover player/helper houses,
native clone exclusions, required access rules, base-section values, native
unlock preservation, arbitrary map-section values, superweapon payload clones,
and native variant buff rules, plus reviewed Time Freeze immunity targets.
An expansion map can use the same sections once its mission code is present in
the catalogue/classification data.

`player_production_houses` lists houses whose factories later become usable by
the player without changing their initial factory-owner identity. Native
production isolation adds each listed house's country to
`FactoryOwners.Forbidden`, preventing an original unit cameo beside its
isolated player clone while preserving authored TaskForces. Zero Signal lists
`Pacific House` so its captured Barracks cannot expose locked native Allied
infantry.

`scripted_player_buff_taskforces` lists reviewed player or transferred-player
TaskForce IDs whose unit references follow the launch's isolated player clones.
Use it when authored Action-created teams must receive player buffs or when
native production-isolation fields would stop Ares from assembling the team.
Noise Severe lists its Rhino, Tesla Cruiser, Tigr/Shock/Flak, and paradrop
TaskForces; their scripted waves therefore form before the FriendlyTank handoff
and remain available to the player. This explicit policy applies even when
helper buffs are disabled. Clone ownership includes the reviewed team's runtime
country without enabling buffs for unrelated helper teams. Optional
`scripted_player_buff_taskforce_access_requirements` entries limit a rewrite to
launches that already own every listed source TechnoType.

`original_mcv_access` maps mission codes to native MCV TechnoType IDs. The
bundled default exposes `AMCV` and `SMCV` only in Foehn 06 (`FREMNANT`). These
remain original mission identities; production uses the native MCVs. Their
authored TechLevel and Action 106 unlock timing remain intact, and generic
player production gates exclude these IDs. Any linked Construction Yard buff
counterpart stays locked and receives no MCV unlock action. Replace
that mission's list to change the available MCVs, or set it to `[]` to disable
the exception. Missions absent from the mapping receive no original MCV access.

`enemy_scaling_disabled_missions` suppresses all acquired AI stat and power
rewards for missions whose scripted opening cannot survive them. Withershins
and Parasomnia use this exception. Authored enemies and mission difficulty
remain unchanged, and acquired AI rewards still apply to other missions.

`rewards/enemy_scaling.json` includes the single-stack `powerhouse` reward
(`AI Enemy Powerhouses`). It appears under **AI reinforcement waves** in the
reward-pool controls and participates in normal Shop stage scaling and the
standalone/Archipelago enemy reward pool. Enemy-buff settings control its
eligibility and cap.
Saved runs drop the retired run-modifier ID.
Land reinforcement teams gain two native faction heavies; air and
naval teams gain one existing combat member. Expanded teams spawn at least
veteran. Epsilon heavy additions exclude Masterminds so fixed-unit openings
on base-building missions cannot lose their only hero or Engineer to random
mind control. Private TaskForces preserve shared player/allied waves, and native
spawnability checks include the added enemy members. Transport, engineer, MCV,
unique-unit, unknown-terrain and protected story teams are skipped. No-build
and scripted-opening protections remain active. Co-op uses registered enemy
slots and produces identical host/guest map bytes. Hero companions unlock at
Shop stage 4, faction superunits at stage 8; Mental advances both unlocks by
four stages. All four factions have their own pools. Allied, Soviet and
Epsilon special selections independently substitute Foehn heroes or
superunits with a seeded one-in-three chance for each category. Foehn copies
use the existing hostile country and its matching factories; no Foehn enemy
house or Foehn factory is required. Companion teams use
private, armed portable actors and Hunt orders, with at most two hero team
definitions and one superunit team definition per enemy house; authored
repeating waves can summon them again. Matching enemy factories and active
native AI production teams also receive low-priority private production
teams, capped at one living copy per selected type per house (BuildLimit=1,
Max=1). Production is skipped for countries shared with non-hostile actors.
Factory actors retain the hidden player-production gate; wave-only actors
have TechLevel=-1. Co-op manifests record non-default difficulty alongside
the existing Shop stage.

`time_freeze_immune_techno_ids` maps mission codes to exact scripted
TechnoTypes. Generation gives each target a mission-private armor alias that
inherits its normal armor, then gives only that alias `0%` verses on the
mission's private Time Freeze warhead. Other units sharing the original armor
remain affected. Use only for mission-critical objects whose EMP/AttachEffect
state can trigger AI selling, invalidate an objective chain, or permit
script-breaking stunlock abuse. Power Hunger protects `MORALES` and `NAHAMM`;
Bleed Red protects its scripted map-local `MORALES` Boris identity.

`native_production_gate_exclusions` is narrower engine-safety policy for
script-created native units. Power Hunger excludes `SAPC` because its player
MCV delivery team needs the authored Zubr identity. Its map-authored
`TechLevel=-1` still blocks native player production, while the isolated
buildable transport clone remains available.

Mermaid likewise excludes its map-local `TANY`. The authored Tanya changes
weapons after collecting her equipment, and its placed unit, attached trigger,
and scripted control flow must never inherit the hidden player production gate.

Bleed Red excludes its map-local `MORALES` identity because Ares also evaluates
the randomizer's hidden production gate while assembling the authored Boris
TeamType. The extracted type, TaskForce, and exact-type Events must stay native;
historical attempts to move or replace that identity caused instant defeat and
runtime fatal errors.

Power Hunger also patches four authored `Actions` values. Objective 2
completion now creates both Latin AI and player MCV delivery teams. The Latin
team reuses the proven native `SAPC+SMCV` TaskForce and unloads before running
an explicit deploy action, its authored base-ready sequence, and guard. Live
play proved `TransportsReturnOnUnload=yes` leaves the empty transporter in the
MCV's deployment cells. Unload mode `8,2` separates that SAPC from the MCV
team. Local-47 action `01001542` then creates Latin-only
`MORSREDLatinSAPCReturn`, which recruits exactly one free SAPC with the
authored SAPC-only TaskForce/script, moves it to waypoint 400, and deletes it.
No whole-team delete touches the MCV. Authored script `01001529` originally
moved a land MCV to waypoint 3. The transported version repeats that move after
unload so the separated MCV receives it, waits six seconds for the SAPC to
clear, then deploys. The delivery uses the same prebuilt,
non-Autocreate mode as working Latin SAPC reinforcements. Objective 2 also sets
authored local `47`, guaranteeing the unchanged Latin ConYard and AI activation
chain even if the engine rejects the visual transport at water waypoint `EY`.
Later native actions retain every non-MCV effect but omit duplicate MCV
creation. This replaces the authored 7.5-minute plus 3-minute Latin MCV delay;
the player MCV originally waited for that AI MCV to deploy into `NACNST`.

`objective_clone_event_refs` retargets exact reviewed objective Events to the
player clone allocated for that launch without rewriting enemy placements or
scripted TaskForces. Machinehead uses this for Foxtrot Events `01000926` and
`01000942`; both count the isolated build-only clone, including compact veteran
IDs, while enemy Foxtrots stay native. Its GHTNK transports carry the Driller
reinforcements. Changing or disabling their return triggers also crashed and is
not part of the fix. Original/generated comparison found every native type in
that reinforcement wave had received randomizer production-isolation fields:
`GHTNK`, `CNTR`, its initial `COVE` payload, `EMPR`, `CTNK`, and `ARMA`.
`native_runtime_identity_preserve_ids` restores reviewed runtime sections after
clone planning. EHEAD uses it for that complete set; return triggers, scripts,
TaskForces, and runtime identities therefore retain the original map values,
except the two final return-script deletes. After identity preservation removed
the earlier invalid-vtable crash, the next live dump failed inside gamemd at
`004F9AB1`: a returned GHTNK had already had its Owner cleared by action 37 but
was still referenced by the engine's object scan. Scripts `01000557` and
`01000558` retain their authored move-to-edge action and replace only final
`37,0` with guard `5,2`; triggers and team creation remain authored.
Singularity attaches an
Entered-by-PsiCorps tag to the authored Driller, so Malver boarding completes
the evacuation condition even though transported passengers remain live game
objects.

`transport_factory_exceptions` adds reviewed physical factory alternatives to
an always-available amphibious transport without removing its normal naval
yard path. Keys are mission codes, then transport TechnoType IDs; each value is
a non-empty list of extra factory IDs. Golden Gate adds `GAWEAP` for `SAPC`, so
its Zubr can be rebuilt from the captured Allied War Factory or Soviet Naval
Yard in every reward mode.

`special_infantry_factory_exclusions` lists map-local `Factory=InfantryType`
buildings that serve only authored mission production. Excluded factories are
never appended to randomizer Engineer, Standard infantry, or Chaos infantry
prerequisite alternatives.

`map_section_rules` can patch any INI section in any configured mission. A
literal replaces a value, `null` removes its key, and `add`/`remove` edits a
comma-separated ID list without copying the map's complete original value:

```json
"map_section_rules": {
  "SFATAL": {
    "YTUNNEL": {
      "Passengers.Allowed": {
        "add": ["MORPSVOLKOV"],
        "remove": []
      }
    }
  }
}
```

`rewards/tuning.json` changes newly generated maps and reward plans. Clone ID
prefixes, the `ui_description` shown on every Randomizer-owned unit, and
production-field lists are advanced engine policy: keep IDs within the Ares
24-character limit and retain `Projectile`/`Warhead` requirements unless a
modified engine has been tested. Older files without `ui_description` retain
the compatible `NOSTR:* Granted by Randomizer` default.

Aid reward identity and display data live in `catalogue.json` under
`aid_power_rewards` (`name`, `description`, `faction`, `superweapon`, `index`).
Map injection behavior for each matching `superweapon` remains under
`aid_power_map_configs`.

Power buff applicability lives separately in `rewards/power_buffs.json`.
Grouped lists make every supported power/effect pairing reviewable without
mixing superweapon mechanics into unit/building buff policy. Runtime folds
earned stacks only into an actually earned power unlock and its isolated
`MOR...` clone; a buff alone emits no grant or clone. The Unlock dashboard also
tracks earned buffs separately from earned access, keeps the power locked, and
labels those effects stored until the real unlock is received. Native mission
SuperWeaponTypes and effect helpers remain unchanged.
`payload.drop_pod_type_weight_additions` adds configured type weights for each
DropPod payload stack. Moon Reinforcements adds both `SHOCK` and `CYBO` per
stack while increasing its minimum and maximum pod count.
`vision.power_fields` privately clones the configured SpyPlane aircraft and
increments only its `Sight`; Spy Plane is deliberately excluded from payload
count because additional planes do not improve that power.

`health.techno_fields`, `effect.multiplier_fields`, and
`targeting.vehicle_armor_fields` describe isolated delivered-structure health,
AttachEffect multiplier, and all-vehicle upgrades. All-vehicle targeting derives
armor overrides from selectable installed `VehicleTypes`; explicitly
unselectable or non-scoring spawners, dummy objects, timed beams, and add-ons
remain excluded. Script-only map armor aliases continue inheriting their
authored immunity. An optional
`clone_key` selects an existing private clone whose lookup key differs from its
installed `source` section. `payload.internal_unit_delivery_fields` increases a
nested delivery SuperWeaponType instead of duplicating its outer structure.
`duration.draining_techno_fields` gives timed self-damaging structures a private
armor alias, allowing health and lifetime stacks to remain independent.

`techno_clones` may provide private weapons, projectiles, warheads, delivered
academy markers, or hidden EMPulse cannon buildings. A BuildingType with
`startup_count` is created for each power-grant country; runtime replaces its
inherited ownership with that country and splits map-start action lists by both
the configured action-count ceiling and the engine's byte limit.
`provides_superweapon=true` binds the generated SuperWeaponType clone to that
hidden BuildingType through its vanilla primary `SuperWeapon` slot. This
supplies a real player-owned launch source for engine paths such as
GenericWarhead EMP/AttachEffect filtering without adding a weapon.
`static_startup=true` places that provider directly in `[Structures]` under
each exact mission House instead of creating it through action 125. Use this
when engine filtering must resolve the provider from the owning House before
map-start grant triggers run.

Custom power artwork uses `sidebar_image` with a plain PNG filename from
`assets/`; its matching `values.SidebarPCX` supplies the loose PCX filename
referenced by the generated map. The launcher converts the PNG to the game's
required 60×48 indexed PCX format on launch and uses the same PNG for its
Unlocks preview. Packaged defaults become visible under
`RandomizerLauncherData/assets` so replacement artwork remains editable.
For a custom power, copy `my_power.png` into that `assets` directory and set:

```json
"sidebar_image": "my_power.png",
"values": {
  "SidebarPCX": "mormypwr.pcx"
}
```

Use a plain PNG filename and a unique PCX filename beginning with `mor`; no
manual image conversion or `cameo_superweapon` fallback is needed.

Map-only unit cameos use `rewards/unit_data.json:unit_sidebar_images`. Keep the
existing `image` + namespaced `pcx` pair for bundled PNG artwork. Use a single
`source_pcx` filename for game/Bonus MIX artwork. Installed game-root MIX files
always win; `assets/expandmo21 Bonus.mix` is fallback only. Required PCXs are
extracted into launcher staging, activated beside the game only for the spawned
mission, and removed afterward by hash-verified cleanup.
When a TechnoType uses a different `Image=`, add `art_id` to the PNG mapping so
the same cameo is merged into that complete installed art section.

`rewards/buff_exceptions.json` section `excluded_buff_type_ids` maps each buff type
to TechnoType IDs that must not receive it. Use `all` for complete exclusions.
These entries affect newly planned rewards; retired items in old saves stay in
state for compatibility but are omitted from the Unlocks list. Weapon buffs
must change a direct weapon on the isolated player clone. Keep damage rewards
for shared spawned aircraft, missiles, or payload weapons excluded unless the
complete payload chain gains a private, validated clone path.

`rewards/unit_data.json` section `spawned_missile_range_support` maps a reviewed
launcher TechnoType to its spawned missile AircraftType and installed base
`GuardRange`. When that launcher's weapon range is upgraded, map generation
adds the same range increase to the missile pursuit envelope. Keep this list
narrow: extending missile pursuit is safe only when the native launcher's
unchanged weapon range remains within its original envelope. Akula is the only
reviewed entry.

## Load locations

Source runs load static files from this directory directly. A packaged EXE
bundles these defaults plus a hash manifest and exposes them under
`RandomizerLauncherData/configs` beside the game. First launch after upgrading
from a pre-manifest build backs up differing legacy files as
`*.pre-bundle-sync-backup`, then installs one complete current set. Later
updates replace only files still matching the preceding bundled hash; locally
edited files remain authoritative. Player YAML lives in the separate
`configs/player/` child, is always launcher-managed, and is excluded from
packaged build inputs.

EVA voice labels and engine tags have one source under `ui.json`:
`eva_voice_tags`. Object order controls menu order. Add, remove, or rename one
mapping there; launcher derives its choices automatically, with fixed
`Mission default` and `Random` options around configured entries. Engine tags
`Allied`, `Russian`, and `Yuri` use Ares EVA indexes 0–2. Other configured tags
use indexes 3 onward in this same object order, which must match their order in
the installed `EVATypes` list.

`eva_appearance_profiles` optionally binds the matching faction sidebar and
mission-text color to an EVA choice. Profile keys normally match the visible
choice label from `eva_voice_tags`; an engine tag also works as a fallback.
`Mission default` applies neither voice nor appearance overrides. Built-in
Allied, Soviet, Epsilon, and Foehn voices retain their installed appearance
defaults when an older external `ui.json` does not yet contain profiles. All
four Mental Omega sidebar sets use Yuri's Revenge filenames, so their
`sidebar_yuri_file_names` value must be `true`; runtime enforces this for the
built-in EVA tags to protect preserved older editable configurations.

Every document requires `schema_version: 1` and a `sections` object. Startup
validates required sections and important value types. Invalid JSON or missing
required data stops startup with the exact file and section in the error.

Keep a backup before gameplay changes. These files define compatibility facts;
invalid mission houses, production IDs, or role groups can break campaign maps
even when JSON validation succeeds.
