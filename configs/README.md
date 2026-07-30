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
- `missions.json`: mission build classifications, optional-operation membership, helper/enemy house policy,
  production/power house exceptions, native identity exclusions, map-specific
  access rules, native-variant buff forwarding, and campaign starter families.
- `map_rules.json`: controlled technology locks, TechnoType registry mapping,
  and parser/engine safety limits used by generated maps.
- `factions.json`: Engineers, MCV/Construction Yard mapping, production
  buildings, amphibious transports, Chaos production, and tech
  ordering, plus default unlock owners and special-factory identities.
- `tier_one.json`: subfaction-specific starter units, fixed faction Tier 1
  defensive structures, abstract saved markers, aircraft factories, and
  installed GenericPrerequisite aliases.
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
  damage, duration, and delivered-payload buff capabilities and stack tuning.
  Supported effects have no Randomizer-imposed stack ceiling.
- `rewards/catalogue.json`: unit access items, faction access rules, buff type
  definitions, superweapon templates/rewards, support and aid-power definitions
  and mappings, access aliases, and retired reward compatibility entries.
- `rewards/tuning.json`: stack multipliers, per-category movement-speed
  ceilings, retry-assistance behavior, clone prefixes/production-field policy,
  reward count limits, and global-buff planning cadence. Display text,
  effective stack limits, and generated map values use the same data.
- `RandomizerInfantry.ini`, `RandomizerHeroes.ini`,
  `RandomizerVehicles.ini`, `RandomizerShips.ini`,
  `RandomizerAircraft.ini`, and
  `RandomizerDefensesAndSpecialBuildings.ini`: split static `MORP*` player
  roster. Infantry definitions come from mapper-reviewed `InfantryList.txt`;
  remaining definitions are Mental Omega 3.3.6 identity snapshots. Ships still
  register under engine `VehicleTypes`. Hero file contains capped reward heroes
  plus mapper infantry extras. Mission generation buffs these owned types while
  native IDs remain reserved for campaign AI and scripts.

## Mission-specific overrides

Add reviewed map exceptions to `missions.json`; do not add mission-code
branches to the Python pipeline. Available sections cover player/helper houses,
native clone exclusions, required access rules, base-section values, native
unlock preservation, arbitrary map-section values, superweapon payload clones,
and native variant buff rules.
An expansion map can use the same sections once its mission code is present in
the catalogue/classification data.

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
prefixes and production-field lists are advanced engine policy: keep IDs within
the Ares 24-character limit and retain `Projectile`/`Warhead` requirements
unless a modified engine has been tested.

Aid reward identity and display data live in `catalogue.json` under
`aid_power_rewards` (`name`, `description`, `faction`, `superweapon`, `index`).
Map injection behavior for each matching `superweapon` remains under
`aid_power_map_configs`.

Power buff applicability lives separately in `rewards/power_buffs.json`.
Grouped lists make every supported power/effect pairing reviewable without
mixing superweapon mechanics into unit/building buff policy. Runtime folds
earned stacks only into the already isolated `MOR...` power clone; native
mission SuperWeaponTypes and effect helpers remain unchanged.

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

`rewards/buff_exceptions.json` section `excluded_buff_type_ids` maps each buff type
to TechnoType IDs that must not receive it. Use `all` for complete exclusions.
These entries affect newly planned rewards; retired items in old saves stay in
state for compatibility but are omitted from the Unlocks list.

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
defaults when an older external `ui.json` does not yet contain profiles.

Every document requires `schema_version: 1` and a `sections` object. Startup
validates required sections and important value types. Invalid JSON or missing
required data stops startup with the exact file and section in the error.

Keep a backup before gameplay changes. These files define compatibility facts;
invalid mission houses, production IDs, or role groups can break campaign maps
even when JSON validation succeeds.
