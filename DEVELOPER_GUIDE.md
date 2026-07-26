# Developer Guide

Start here when changing code. Player settings belong in
[README_RANDOMIZER.md](README_RANDOMIZER.md); exact engine findings belong in
[TECHNICAL_FINDINGS.md](TECHNICAL_FINDINGS.md).

## Find the right file

### Seed and progression

- `randomizer_missions.py`: installed mission parsing, filtering, deterministic
  mission ordering.
- `grid_progression.py`: pure Grid topology and unlock state.
- `randomizer_seed_rewards.py`: pure deterministic reward-slot planning.
- `randomizer_reward_rules.py`: reward-to-TechnoType access and role-buff scope.
- `randomizer_rewards.py`: reward catalogue derivation, canonicalization,
  stacking, display.

### Static configuration

- `randomizer_static_config.py`: paths, packaged override recovery, JSON loading,
  caching.
- `randomizer_config_schema.py`: required sections and focused per-file
  validation.
- `randomizer_ui.py`, `randomizer_tuning.py`,
  `randomizer_mission_overrides.py`: small typed adapters used by runtime code.
- `configs/`: editable policy/data. Read `configs/README.md` before adding data.

`ui.json` uses `eva_voice_tags` as one source of truth. Mapping order controls
menu order. Launcher adds `Mission default` and `Random`; no second choices list
must be synchronized. Built-in tags use Ares action indexes 0–2; custom tags
use 3 onward in mapping order.

### Generated maps

- `randomizer_map_pipeline.py`: ordered launch pipeline only.
- `randomizer_map_houses.py`: house/country discovery and faction families.
- `randomizer_map_ownership.py`: placed/TaskForce/AITrigger ownership and helper
  safety.
- `randomizer_map_settings.py`: color and EVA map overrides.
- `randomizer_map_hooks.py`: bounded Action editing and marker structures.
- `randomizer_map_progress_hooks.py`: check-to-action pairing and marker
  injection.
- `randomizer_map.py`: remaining reward rules, player clones, direct buffs,
  helper production, building-free power construction.
- `randomizer_mission_safety.py`: Standard/Chaos production access translation.
- `randomizer_ini.py`: order-preserving INI mechanics. Never replace with
  `ConfigParser`.

### Launcher and files

- `launcher_gui.py`: entry point and packaged self-check.
- `randomizer_app.py`: Tk state and orchestration. Keep new pure behavior out of
  this class; add a focused module and call it.
- `randomizer_ui_builder.py`: widget construction.
- `randomizer_ui_theme.py`: Tk palette/style application.
- `randomizer_ui_grid.py`: Grid Mode widget rendering.
- `randomizer_ui_tooltips.py`: shared widget/tree tooltip lifecycle.
- `randomizer_launch_options.py`: spawn/option INI reading and writing.
- `randomizer_storage.py`: atomic JSON/text persistence.
- `randomizer_state.py`: pure normalization for persisted mission checks,
  failure stacks, and assistance units.
- `randomizer_paths.py`: source/frozen path resolution.

## Runtime flow

1. `launcher_gui.py` validates startup and imports `LauncherApp`.
2. `randomizer_missions.py` builds eligible mission order.
3. `randomizer_seed_rewards.py` assigns every stored reward using the named seed
   RNG stream.
4. `randomizer_app.py` persists complete seed/check state.
5. Launch calls `randomizer_map_pipeline.py`.
6. Pipeline reads fresh extracted source, discovers ownership, applies
   access/clones/buffs/powers, injects progress markers, writes one loose map.
7. Debug-log watcher unlocks stored checks exactly once.

No pure module imports `randomizer_app.py`. Tk variables stay on UI thread.
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
