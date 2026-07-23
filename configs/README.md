# Static Randomizer Configuration

These JSON files contain editable gameplay and presentation data previously
embedded in Python modules. Restart the launcher after changing a file.

## Files

- `default_player_config.json`: fallback player, generation, launch, privacy,
  and future Archipelago settings used when active YAML keys are absent.
- `missions.json`: mission build classifications, helper/enemy house policy,
  production/power house exceptions, native identity exclusions, map-specific
  access rules, native-variant buff forwarding, and campaign starter families.
- `map_rules.json`: controlled technology locks, TechnoType registry mapping,
  and parser/engine safety limits used by generated maps.
- `factions.json`: Engineers, MCV/Construction Yard mapping, production
  buildings, amphibious transports, Chaos production, and tech
  ordering, plus default unlock owners and special-factory identities.
- `tier_one.json`: subfaction-specific starter units, abstract saved role
  markers, aircraft factories, and installed GenericPrerequisite aliases.
- `ui.json`: difficulties, game speeds, campaign/reward/progression choices,
  reward-count messages, faction colors, and light/dark palettes.
- `rewards/unit_data.json`: unit and defense rosters, base stats, weapon stats,
  cross-faction role-equivalence groups, buff targets, labels, hero limits, and
  special weapon damage fields.
- `rewards/unit_policy.json`: installed capabilities, reward exclusions,
  trainability/naval classification, always-available essentials, trainable
  defenses, and unit-specific display wording.
- `rewards/buff_exceptions.json`: reviewed per-buff TechnoType exclusions.
- `rewards/catalogue.json`: unit access items, faction access rules, buff type
  definitions, superweapon templates/rewards, support and aid-power definitions
  and mappings, access aliases, and retired reward compatibility entries.
- `rewards/tuning.json`: stack multipliers and caps, retry-assistance behavior,
  clone prefixes/production-field policy, reward count limits, and global-buff
  planning cadence. Display text and generated map values use the same data.

## Mission-specific overrides

Add reviewed map exceptions to `missions.json`; do not add mission-code
branches to the Python pipeline. Available sections cover player/helper houses,
native clone exclusions, required access rules, base-section values, native
unlock preservation, superweapon payload clones, and native variant buff rules.
An expansion map can use the same sections once its mission code is present in
the catalogue/classification data.

`rewards/tuning.json` changes newly generated maps and reward plans. Clone ID
prefixes and production-field lists are advanced engine policy: keep IDs within
the Ares 24-character limit and retain `Projectile`/`Warhead` requirements
unless a modified engine has been tested.

Aid reward identity and display data live in `catalogue.json` under
`aid_power_rewards` (`name`, `description`, `faction`, `superweapon`, `index`).
Map injection behavior for each matching `superweapon` remains under
`aid_power_map_configs`.

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

Source runs load this directory directly. A packaged EXE bundles these defaults
and copies each missing file to `RandomizerLauncherData/configs` beside the game.
Existing external files are never overwritten, so local edits survive launcher
updates.

Every document requires `schema_version: 1` and a `sections` object. Startup
validates required sections and important value types. Invalid JSON or missing
required data stops startup with the exact file and section in the error.

Keep a backup before gameplay changes. These files define compatibility facts;
invalid mission houses, production IDs, or role groups can break campaign maps
even when JSON validation succeeds.
