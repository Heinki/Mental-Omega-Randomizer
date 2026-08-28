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
  absent. `generation.reward_weights` stores bounded `0`–`100` main,
  unit-buff, and power-buff selection weights; absent legacy keys use `100`.
  `generation.starting_reward_count` and `starting_reward_types` control the
  separately seeded pre-mission unlock grant; allowed families are access,
  offensive powers, secondary powers, and aid powers. Buff-family IDs from
  legacy or portable settings are discarded; legacy configs default to zero.
  `generation.starting_unlock_rewards` stores portable canonical reward names
  manually selected in Advanced -> Starting Unlocks; only permanent content
  access/power rewards survive normalization, and legacy configs default empty.
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
- `tier_one.json`: subfaction-specific starter equivalents, fixed faction
  Tier 1 defensive structures, Standard role
  markers, aircraft factories, and installed GenericPrerequisite aliases.
- `shop_mode.json`: Shop Mode run length, mission offers and class rewards,
  stage difficulty weights, Ore/Gem unit prices, permanent upgrade
  definitions, reward exclusions, and launcher-only mission effects.
- `ui.json`: difficulties, game speeds, campaign/reward/progression choices,
  EVA announcer tags, reward-count messages, faction colors, and
  light/dark palettes.
- `rewards/unit_data.json`: unit and defense rosters, base stats, reviewed
  transport passenger/open-top baselines and behavior exclusions, weapon stats,
  cross-faction role-equivalence groups, linked land/water buff identities,
  buff targets, labels, hero limits, and
  special weapon damage fields.
- `rewards/unit_policy.json`: installed capabilities, reward exclusions,
  trainability/naval classification, always-available essentials, trainable
  defenses, alternative production facilities, linked land/water access
  identities, and unit-specific display wording.
- `rewards/special_buildings.json`: editable faction economy/special-building
  access rewards, including labels, native Construction Yards, tech levels,
  build limits, sidebar build category/priority, and whether repeatable +1
  capacity rewards are generated. Chaos translates these to every faction
  Construction Yard.
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
  native IDs remain reserved for campaign AI and scripts.

## Shop Mode balance

`shop_mode.json` is the only static source for Shop Mode economy and run-size
policy. `settings` defines positive `run_length` and `mission_offer_count`, the
non-negative `max_selected_permanent_units` and `starting_run_coins`, the
positive `maximum_starting_ore` and `minimum_shop_price`, and the version-1
`per_run` reroll policy.
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

`mission_rewards` must contain exactly `act_1`, `act_2`, `operation`, and
`finale`. Each class has a display label, unique positive difficulty rank, and
non-negative Ore (`run_coins`) and Gem (`meta_coins`) rewards.
`stage_class_weights` uses ascending `through_percent` boundaries ending at
`100`; each profile supplies non-negative integer weights for all four mission
classes. Gem rewards must increase strictly with difficulty. Offer
generation samples only its named Shop RNG stream. A zero class weight is a
hard stage exclusion: stages 1–2 offer only Act 1, operations begin at stage 5,
and finales begin at stage 9. Protected opening offers include a fixed-unit or
hero mission when the eligible campaign pool provides one.
`unit_inventory_size` controls the deterministic run-shop unit stock. Unit
stock remains stable during a stage and rotates after each mission victory;
eligible buffs remain available for every currently owned unit. Access entries
whose target is already active are removed before display and receive stable
replacement offers, covering starters, permanent/AP access, and run purchases.
`power_inventory_size` controls the power stock shown beside unit/building
offers in the same Run Shop list and uses the same owned-access exclusion.
`discount_specialization` retains its stable save ID but applies its configured
`ore_per_level` discount to all run-shop access and buff entries. Old saved
category fields remain readable and are ignored.

`mission_effects` defines deterministic one-mission player boons and hostile
challenges. Each entry contains display text, non-negative Ore/Gem bonuses,
and exactly one of `player_reward_ids` or `enemy_reward_id`.
`exclusive_reward_ids` suppresses a player boon when its access reward is
already active. Prefer access plus payload/recharge rewards for temporary
support boons: an unowned power becomes available, while an already-owned
power still receives a useful mission-only upgrade. The three visible mission
cards resolve duplicate effects to other entries of the same boon/challenge
kind without consuming gameplay RNG.

`unit_target_prices` is the complete Shop price table for units, aircraft,
naval units, defenses, and special buildings. Every Shop target ID must appear
exactly once. Each entry has `run_access`, `run_buff`, `permanent_access`, and
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

`power_target_prices` is the complete target-specific table for aid powers and
superweapons. Every Shop power target must appear exactly once with positive
`run_access` and `run_buff` prices. `null` remains reserved for a future target
that lacks that offer kind. Powers have no permanent Shop offers.
Discounted prices use integer percentages, round down, then clamp to
`minimum_shop_price`.

`permanent_upgrades` maps stable IDs to `display_name`, positive `max_level`,
one positive price per level, and integer `effects`. Optional boolean
`purchasable` defaults to `true`; `false` retains a retired upgrade ID for old
profile normalization while hiding it and rejecting new purchases. Version 1 requires
the full stable account-upgrade catalogue, including `coupon_book`,
`stock_lock`, `veteran_academy`, `gem_dividend`, and `premium_supplier`.
`modifiers` maps stable IDs to display text and additive or
percentage economy effects. Percentage modifiers multiply exactly; flat
modifiers add. Unknown saved modifier or upgrade IDs fail with a
clear state error instead of silently changing balance.

Modifier effects support economy, stock size, mission-choice count, starter
composition/veterancy, player clone damage/durability/cost/production,
aid-power recharge, mission starting Credits, and feature-disable flags.
Percentages multiply in persisted modifier order; flat effects add. Each
distinct active ID contributes one visible difficulty point. `blind_choice`
uses the hidden-offer count only for presentation and never consumes gameplay
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
and remain available to the player. Optional
`scripted_player_buff_taskforce_access_requirements` entries limit a rewrite to
launches that already own every listed source TechnoType.

`original_mcv_access` maps mission codes to native MCV TechnoType IDs. The
bundled default exposes `AMCV` and `SMCV` only in Foehn 06 (`FREMNANT`). These
remain original mission identities; no `MORP*` MCV clone is created. Replace
that mission's list to change the available MCVs, or set it to `[]` to disable
the exception. Missions absent from the mapping receive no original MCV access.

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
