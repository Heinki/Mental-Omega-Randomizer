# Developer Guide

Start here when changing code. Player settings belong in
[README_RANDOMIZER.md](README_RANDOMIZER.md); exact engine findings belong in
[TECHNICAL_FINDINGS.md](TECHNICAL_FINDINGS.md).

## Find the right file

### Seed and progression

- `randomizer/missions/catalogue.py`: installed mission parsing, filtering, deterministic
  mission ordering.
- `randomizer/progression/grid.py`: pure Grid topology and unlock state.
- `randomizer/rewards/planning.py`: pure deterministic reward-slot planning.
- `randomizer/rewards/rules.py`: reward-to-TechnoType access and role-buff scope.
- `randomizer/rewards/definitions.py`: catalogue construction and immutable
  reward data.
- `randomizer/rewards/display.py`: canonicalization, stacking, and display.
- `randomizer/rewards/catalogue.py`: stable public reward facade.

### Static configuration

- `randomizer/config/static.py`: paths, packaged override recovery, JSON loading,
  caching.
- `randomizer/config/schema.py`: required sections and focused per-file
  validation.
- `randomizer/config/player.py`: active player YAML and legacy-path migration.
- `randomizer/ui/config.py`, `randomizer/config/tuning.py`, and
  `randomizer/missions/overrides.py`: small typed adapters used by runtime code.
- `configs/`: editable policy/data. Read `configs/README.md` before adding data.

`ui.json` uses `eva_voice_tags` as one source of truth. Mapping order controls
menu order. Launcher adds `Mission default` and `Random`; no second choices list
must be synchronized. Built-in tags use Ares action indexes 0–2; custom tags
use 3 onward in mapping order.

Optional `eva_appearance_profiles` entries use the same choice label (or engine
tag) to bind a sidebar MIX index, Yuri filename mode, and mission-text color to
that voice. Built-in tags retain installed Mental Omega appearance fallbacks
when an older external `ui.json` has no profiles.

### Generated maps

- `randomizer/maps/pipeline.py`: ordered launch pipeline only.
- `randomizer/maps/houses.py`: house/country discovery and faction families.
- `randomizer/maps/ownership.py`: placed/TaskForce/AITrigger ownership and helper
  safety.
- `randomizer/maps/settings.py`: color and EVA map overrides.
- `randomizer/maps/hooks.py`: bounded Action editing and marker structures.
- `randomizer/maps/progress_hooks.py`: check-to-action pairing and marker
  injection.
- `randomizer/maps/rules.py`: stable public facade for generated-map rules.
- `randomizer/maps/base.py`, `assistance.py`, `buff_values.py`,
  `clone_references.py`, `helper_ai.py`, `player_clones.py`,
  `clone_builder.py`, `weapon_buffs.py`, `country_buffs.py`, and `powers.py`:
  focused generated-rule stages.
- `randomizer/missions/access.py`: Standard/Chaos production access translation.
- `randomizer/missions/tier_one.py`: starter selection and launch rules.
- `randomizer/missions/safety.py`: stable public mission-safety facade.
- `randomizer/maps/ini.py`: order-preserving INI mechanics. Never replace with
  `ConfigParser`.

### Launcher and files

- `launcher_gui.py`: entry point and packaged self-check.
- `randomizer/application/app.py`: Tk composition and initialization only.
- `randomizer/application/*_controller.py`, `window.py`,
  `advanced_settings.py`, `unlock_data.py`, and `unlock_view.py`: focused UI
  orchestration controllers. Keep pure behavior outside these classes.
- `randomizer/ui/builder.py`: stable widget-construction facade.
- `randomizer/ui/layout.py`, `settings.py`, and `overlay.py`: focused widget
  builders.
- `randomizer/ui/theme.py`, `grid.py`, and `tooltips.py`: presentation behavior.
- `randomizer/launch/options.py`: spawn/option INI reading and writing.
- `randomizer/core/storage.py`: atomic JSON/text persistence.
- `randomizer/progression/state.py`: pure normalization for persisted mission checks,
  failure stacks, and assistance units.
- `randomizer/core/paths.py`: source/frozen path resolution.

## Runtime flow

1. `launcher_gui.py` validates startup and imports `LauncherApp`.
2. `randomizer/missions/catalogue.py` builds eligible mission order.
3. `randomizer/rewards/planning.py` assigns every stored reward using the named seed
   RNG stream.
4. Application controllers persist complete seed/check state.
5. Launch calls `randomizer/maps/pipeline.py`.
6. Pipeline reads fresh extracted source, discovers ownership, applies
   access/clones/buffs/powers, injects progress markers, writes one loose map.
7. Debug-log watcher unlocks stored checks exactly once.

No pure module imports `randomizer/application/`. Tk variables stay on UI thread.
Workers receive frozen plain Python data.

## Change rules

- Preserve RNG call count/order. New deterministic features need a named stream.
- Preserve serialized reward/check IDs and aliases.
- Keep native campaign TechnoTypes for AI/scripts. Player effects target owned
  clones.
- Mission exceptions go in `configs/missions.json` when data can express them.
- Keep map Actions at most 511 UTF-8 bytes, Ares IDs at most 24 characters,
  veteran lists at most 480 UTF-8 bytes.
- Keep map order, repeated sections, numeric list entries, and CRLF behavior.
- Avoid generic `utils.py`. Put helpers in narrow domain modules.
- Prefer pure functions with explicit inputs. Filesystem/Tk wrappers should be
  thin.
- Delete only after whole-repository reference checks plus relevant build/runtime
  audit.
- Keep modules below 1,000 lines. Split at domain/stage boundaries; never by
  arbitrary line count.
- Preserve facade imports when splitting a public subsystem so callers do not
  depend on implementation layout.

## Validation

Routine:

```powershell
python -m compileall -q .
python launcher_gui.py --self-check
git diff --check
```

Ownership, clone, AI, power, Action, or mission-map changes require all 97
extracted maps. Determinism refactors require exact old/new plan parity, not
distribution-only checks.
