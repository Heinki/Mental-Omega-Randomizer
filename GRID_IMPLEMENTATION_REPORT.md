# Mental Omega: Grid implementation report

Implemented across standalone Grid Mode and the matching Archipelago world.
Launcher version: **1.48**. The updated Windows executable and matching
`mental_omega.apworld` are installed in the game root. A matching APWorld is also in
`Archipelago/mental_omega.apworld` in this repository.

## Behavior and defaults

- Required Victory Missions defaults to `1`, preserving the bottom-right goal.
  Larger counts select exact distinct mission identities with a separate seeded
  RNG stream; `All` requires every generated mission. Counts normalize against
  the actual filtered/irregular board. Selected mission codes persist in saves
  and the frozen manifest. Only completing the full selected set wins or runs
  the configured release-all action.
- AP Mission Unlock Mode defaults to `Standard`. `Key Currency` enables
  nonadjacent, permanently charged purchases. `Mission-Specific Keys` opens
  only the matching stable mission code. Standalone never uses AP keys.
- AP Currency Minimum Completed Missions Before Final Unlock defaults to
  `Auto`, floor(3*N/8), capped at N-1. Only the physical bottom-right mission is
  protected. Explicit invalid thresholds reject generation. Other required
  missions remain independent.
- Grid markers, footers, Details, tooltips, and purchase controls display exact
  objective progress, key receipt/spending/balance, prices, missing keys,
  completion gates, and completed required objectives.
- Existing IDs are unchanged. A source audit of the actual before/after
  catalogues found zero changed published item/location/local-victory IDs.
  New key IDs use a reserved, game-specific 48-bit namespace derived from
  mission codes. New Grid rooms require slot-data version 8 / Grid contract 2;
  incompatible older clients reject them. Legacy rooms retain their old format.
- AP received-item history stays immutable. Mission purchases use a separate
  per-run mapping, retained only for matching manifest/seed/team/slot identity.
  Purchase and key receipt saves use atomic replacement and fsync. Repeated
  purchases and deliveries do not duplicate spending or key value.

## AP generation and economy

The APWorld freezes actual mission IDs, exact goals, starts, prices, supply,
real reward capacity, item IDs, and protection rules. Key items replace an
identical number of normal reward slots; real check IDs/counts stay intact.
Mission-specific keys use ordinary AP progression fill and exact region rules.
Local-only victory markers provide goal/gate evidence in AP logic; server
checks, released rewards, and received marker items never create local wins.

Currency deliberately uses one shuffled **Mission Key Supply** progression
item worth the full remaining board cost. The client still charges each mission
separately. Remaining balance equals the sum of unbought prices, so arbitrary
optional purchases cannot permanently strand required goals. AP can model the
supply as a nonconsumable logical permit without pretending cumulative received
coins model incompatible spending. Free starting missions expose real checks;
opening reward locks are removed in key modes so normal AP fill can place keys
without a self-lock. Generation validates topology, capacity, supply, prices,
and completion gates. The tradeoff is one large delivery rather than staged
currency receipts. See [Grid progression](GRID_PROGRESSION.md) for the proof,
field mapping, and manual gameplay checklist.

The existing local-only mission victory marker architecture is retained.
Shop Mode and other independent modes were not changed.

## Build and validation results

- Relevant Python source compilation passed.
- Existing production APWorld builder completed successfully from this checkout.
- Existing Windows builder completed successfully: Python 3.14.6,
  PyInstaller 6.21.0, websockets 17.0. Required Tcl/Tk archive entries passed the
  builder's normal inspection.
- Existing production release-manifest validator verified the installed
  executable/APWorld/setup pair and SHA-256 checksums.
- `git diff --check` passed.
- No tests or test infrastructure were added or run. No AP room generation,
  game launch, or gameplay victory was used as validation. AP item-placement
  behavior was inspected and reasoned about, not executed.

## Installation, regeneration, and remaining manual checks

Previous executable/APWorld/setup/manifest/checksum files are backed up at:

`/home/Games/C&C Mental Omega - Randomizer/RandomizerLauncherData/backups/grid-victories-before-install-20261105-171214`

Install the game-root `mental_omega.apworld` into Archipelago's `custom_worlds`, restart
Archipelago, and generate a new room to enable the new Grid options. Existing
rooms cannot acquire new settings through a local launcher change. Keep the
launcher save when moving computers: AP checks cannot reconstruct local
purchases or prove gameplay victories.

The owner still needs to verify real standalone `1`/`K`/`All` victories, AP
Standard/Key Currency/Mission-Specific Keys rooms, cross-world delivery,
nonadjacent purchases, duplicate clicks, restart/reconnect, protected gates,
release/collect without local wins, and switching to another room/slot. No
manual gameplay verification is claimed.

## Changed files

- `Archipelago/APWorld/mental_omega/data.py`
- `Archipelago/APWorld/mental_omega/docs/grid_progression.md`
- `Archipelago/APWorld/mental_omega/docs/setup_en.md`
- `Archipelago/APWorld/mental_omega/grid_rules.py`
- `Archipelago/APWorld/mental_omega/manifest.py`
- `Archipelago/APWorld/mental_omega/options.py`
- `Archipelago/APWorld/mental_omega/world.py`
- `Archipelago/README.md`
- `Archipelago/SETUP.md`
- `Archipelago/client/handshake.py`
- `Archipelago/mental_omega.apworld`
- `Archipelago/run_manifest.py`
- `GRID_PROGRESSION.md`
- `README.md`
- `configs/default_player_config.json`
- `randomizer/application/app.py`
- `randomizer/application/archipelago_controller.py`
- `randomizer/application/archipelago_yaml_controller.py`
- `randomizer/application/grid_access_controller.py`
- `randomizer/application/progression_controller.py`
- `randomizer/application/reward_controller.py`
- `randomizer/application/seed_controller.py`
- `randomizer/application/state_controller.py`
- `randomizer/application/unlock_view.py`
- `randomizer/core/storage.py`
- `randomizer/core/version.py`
- `randomizer/generation/seed_controller.py`
- `randomizer/generation/service.py`
- `randomizer/progression/grid.py`
- `randomizer/progression/mission_access.py`
- `randomizer/ui/grid.py`
- `randomizer/ui/layout.py`
- `GRID_IMPLEMENTATION_REPORT.md` (this report)

## Archipelago settings usability update

- Moved AP-only Mission Unlock Mode into Grid Mission Access on the Archipelago
  page, directly before Player YAML Export. Each mode has a short description
  and the standard hover tooltip. The selector remains read-only while connected.
- Removed the editable Auto/completion-threshold field and its UI state. The
  launcher omits that override from exported YAML; the APWorld computes the
  balanced requirement from the generated board. Existing rooms retain their
  frozen rules. Legacy/expert explicit YAML overrides remain supported, but the
  technical option is hidden from Options Creator.
- Added tooltips to the shared Required Victory Missions field. It remains in
  Settings because it applies to standalone Grid Mode too. Moved the adjacent
  skirmish control below it in DTA and Reloaded to prevent overlapping rows.
- Rebuilt and installed the matching launchers and APWorlds in all three games.
  Source compilation, builds, release checksum validation, and diff checks
  passed. No tests or gameplay verification were run.

The settings update backed up the preceding release at:

`/home/Games/C&C Mental Omega - Randomizer/RandomizerLauncherData/backups/ap-settings-before-install-20261105-180716`
