# Static Randomizer Configuration

These JSON files contain editable gameplay and presentation data previously
embedded in Python modules. Restart the launcher after changing a file.

## Files

- `default_player_config.json`: fallback player, generation, launch, and future
  Archipelago settings used when active YAML keys are absent.
- `missions.json`: mission build classifications, helper/enemy house policy,
  production/power house exceptions, native identity exclusions, map-specific
  access rules, native-variant buff forwarding, and campaign starter families.
- `map_rules.json`: controlled technology locks, TechnoType registry mapping,
  and parser/engine safety limits used by generated maps.
- `factions.json`: Engineers, MCV/Construction Yard mapping, production
  buildings, Tier 1 roles, amphibious transports, Chaos production, and tech
  ordering, plus default unlock owners and special-factory identities.
- `ui.json`: difficulties, game speeds, campaign/reward/progression choices,
  reward-count messages, faction colors, and light/dark palettes.
- `rewards/unit_data.json`: unit and defense rosters, base stats, weapon stats,
  cross-faction role-equivalence groups, buff targets, labels, hero limits, and
  special weapon damage fields.
- `rewards/unit_policy.json`: installed capabilities, reward exclusions,
  trainability/naval classification, always-available essentials, trainable
  defenses, and unit-specific display wording.
- `rewards/catalogue.json`: unit access items, faction access rules, buff type
  definitions, superweapon templates/rewards, support and aid-power mappings,
  access aliases, and retired reward compatibility entries.
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
