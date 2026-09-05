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
- `randomizer/shop/`: pure Shop Mode models, economy, mission offers,
  purchases, lifecycle transitions, and persisted-state normalization.
- `randomizer/shop/persistence.py`: atomic permanent profile/current-run files
  plus write-ahead recovery for transitions that update both documents.
- `randomizer/shop/service.py` and `active.py`: immediate purchase/lifecycle
  persistence and persisted run-loadout resolution.
- `randomizer/shop/modifiers.py` and `summary.py`: deterministic modifier
  aggregation/Blind Choice selection plus pure reward and run-summary text.
- `randomizer/shop/archipelago.py`: stable AP room/team/slot identity plus the
  idempotent received-item projection used by Shop loadouts. AP inventory stays
  authoritative in the existing received-item ledger, never in Shop profile
  permanent purchases. New signed AP Shop seeds use its isolated deterministic
  run-number stream to roll received unit access into unused loadout slots;
  received buffs and powers remain automatic.
- `randomizer/shop/archipelago_purchases.py`: durable per-slot generated-check
  debits. A pending transaction is saved before location reporting and becomes
  checked only from authoritative server location state.

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
- `randomizer/ui/layout.py`, `settings.py`, `shop.py`, and `overlay.py`: focused
  widget builders.
- `randomizer/application/shop_controller.py`: standalone Shop workspace
  orchestration; mission launching remains in the normal launch controller.
- `randomizer/application/shop_archipelago_controller.py`: AP ledger, Shop
  stage/check reconciliation, goal reporting, and generated purchase UI bridge;
  pure transaction and entitlement rules remain in `randomizer/shop/`.
- `randomizer/application/shop_polish_controller.py`: mission reward
  breakdowns, run-result summaries, catalogue sorting/state/tooltips, and
  unit/power Shop presentation.
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
4. Application controllers persist complete seed/check state. Shop Mode uses
   its separate atomic profile/run repository and commits a mission before
   launch preparation.
5. Launch calls `randomizer/maps/pipeline.py`; Shop launch context supplies its
   persisted starters, selected permanent rewards, purchases, and buff stacks
   through the same access/clone/buff pipeline.
6. Pipeline reads fresh extracted source, discovers ownership, applies
   access/clones/buffs/powers, injects progress markers, writes one loose map.
7. Debug-log watcher unlocks stored checks exactly once. In Shop Mode, victory
   atomically grants both currencies and creates next-stage offers; detected
   failure ends the run. AP Shop victories additionally report their locked
   stage marker and optional shuffled reward location, while generated Mental
   Coin purchases persist a pending debit before reporting their location.

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
python -m unittest randomizer.launch.self_check -v
python launcher_gui.py --self-check
git diff --check
```

Packaging:

Both Windows build drivers run the mission launch regression suite before
packaging and run `MentalOmegaRandomizer.exe --launch-self-check` on the built
artifact before copying it to the output location. The focused check needs no
game assets and verifies both the Windows command string and the Linux Wine argv
boundary. On Windows Python, the suite also inspects a real child's raw command
line. Full gameplay still requires an installed copy of Mental Omega.

Syringe requires quotes around the host executable even when its filename has
no spaces: `Syringe.exe "gamemd.exe" -SPAWN -CD -SPEEDCONTROL -LOG`.
Do not replace the Windows command string with an argv list: Python's automatic
quoting removes the mandatory quotes. Linux passes a real argv list to Wine.

```powershell
# Build the game-root EXE and tracked Archipelago/mental_omega.apworld.
.\build_all.ps1

# Focused builds remain available.
.\build_exe.ps1
.\Archipelago\build_apworld.ps1

# Full publishable bundle with manifest, setup guide, and checksums.
.\build_archipelago_release.ps1
```

Equivalent Linux maintainer commands (the EXE remains a Windows executable):

```bash
./build_all_linux.sh
./build_exe_wine.sh
python3 Archipelago/build_apworld.py
```

Changes affecting the catalogue or APWorld require matching launcher and
APWorld builds through `build_all.ps1` or `build_all_linux.sh`.

Ownership, clone, AI, power, Action, or mission-map changes require all 97
extracted maps. Determinism refactors require exact old/new plan parity, not
distribution-only checks.
