# Hovracoon, Opus Custom Tank and Noise Severe investigation

Investigated against the installed Mental Omega 3.3.6 rules/art and campaign
maps, and Randomizer source reporting version 1.40. No MIX archives, installed
game balance, user saves or the existing TODO edits were changed.

## Hovracoon (`COON`)

The roster, access reward, owned template, hover locomotor, amphibious movement,
weapons and `InhibitorRange=6` are present. Raccoon (`RACC`) uses the same
superweapon inhibition mechanism. These are support weapons with `Damage=1`
and `ROF=1`; adding ordinary damage or fire-rate upgrades is unnecessary.

The defect is an identity mismatch. `NukeSpecial` and other installed/map
superweapons enumerate native IDs such as `COON` in `SW.Inhibitors`, while
production creates `MORPCOON` (or another current runtime clone). The existing
native-power reference resolver extended `SW.Designators` only.

The shared resolver now extends both lists with production and reference clone
IDs, retaining their native entries. It uses effective current map values so
map overrides, empty lists and previously applied power changes remain
authoritative. No unit-specific inhibitor exception was added. Raccoon,
Inhibitor and other listed cloned types receive the same correction.

There is a separate authored limitation: **Thread of Dread (`STHREAD`)**, a
four-silo mission matching the description, explicitly sets:

```ini
[NukeSpecial]
SW.Inhibitors=FAINHI,FAINHIB,RACC,FAJAMM,CACORE
```

Native `COON` is absent too. That behavior also exists in the native map data.
The randomizer preserves that restriction; the list alone does not establish
whether the omission was intentional or an oversight by the map author.

Changed paths:

- `randomizer/maps/base.py`: existing `resolved_native_designator_clone_rules`.
- `randomizer/maps/pipeline.py`: supplies the current generated map to that
  resolver after power and clone changes.

## Opus Custom Tank (`STNK`)

The report about missing damage/range/fire-rate rewards was correct. STNK has
`Gunner=yes`, `WeaponCount=56`, numbered `WeaponN`/`EliteWeaponN` mounts and no
normal Primary/Secondary mount. Its eight Opus weapons were absent from the
generated weapon snapshot, so normal catalogue eligibility saw no weapons.
Clone generation already understands numbered mounts; it needed metadata,
not a special STNK weapon-buff branch.

The stock snapshot now includes STNK's eight direct/damage weapon IDs, their
real Damage/ROF/Range baselines, and weapon users. A reusable maintenance tool
completes missing weapon-only gunner entries without changing the existing
standard-mount or curated weapon scope. A decoded before/after comparison
confirmed STNK and its eight Opus weapons are the only snapshot changes.
Existing catalogue, Shop, stacking and private-weapon cloning now provide all
three upgrades, including all 56 rookie and 56 elite mounts. Native AI weapons
remain unchanged.

The passenger feature uses one normal stackable unit-buff reward and data-driven
`initial_passenger_types` metadata:

| Earned stacks | Tier | Initial passenger |
|---|---|---|
| 0 | 1 (default) | `INIT` |
| 1 | 2 | `BRUTE` |
| 2 | 3 | `YURI` |

The stack limit is two: the default tier does not consume an upgrade. Each
application replaces `InitialPayload.Types`, writes `InitialPayload.Nums=1`
and retains `Passengers=1`. The payload passes through the existing isolated
payload clone/registration mechanism, so generated INI normally names
`MORPINIT`, `MORPBRUTE` or `MORPYURI`. No list concatenation or new seat occurs.
Manual entry/unloading and all three passenger-survivor chances are disabled
as requested. Preserved older editable Opus templates receive the same sealed
payload policy in memory.

Changed paths:

- `tools/complete_weapon_registry.py` and
  `randomizer/rewards/weapon_stats_data.py`: stock numbered gunner metadata.
- `configs/RandomizerVehicles.ini`, `randomizer/rewards/template_policy.py`,
  `randomizer/rewards/roster.py`: default payload and preserved-template policy.
- `configs/rewards/unit_data.json`, `randomizer/config/schema.py`,
  `randomizer/rewards/definitions.py`: validated tier metadata and eligibility.
- `configs/rewards/catalogue.json`, `randomizer/rewards/display.py`,
  `randomizer/maps/buff_values.py`, `randomizer/maps/player_clones.py`,
  `randomizer/maps/clone_builder.py`, `randomizer/maps/buff_validation.py`:
  ordinary reward, stack limit, display, replacement and payload registration.
- `configs/default_player_config.json`, `randomizer/config/player.py`: enable
  the new buff option once in older player settings, preserving prior toggles.
- `Archipelago/APWorld/mental_omega/catalogue.json`: regenerate the matching
  export. Existing item/location IDs remain stable. Generation also reconciles
  the previously stale control-capacity entries already implemented in HEAD.

## Noise Severe (`SNOISE`)

Noise Severe is a campaign mission, not a temporary Chaos effect. There is no
Noise Severe duration, active-effect flag or purchase/reroll cleanup handler.
Shop supplies a different earned loadout to the same generated-map pipeline.

The prior documented repair lists four reviewed player/transfer TaskForces in
`scripted_player_buff_taskforces`: `01000054`, `01000055`, `01000068` and
`01000090`. They must form the opening Rhino, Tesla Cruiser, infantry and
paradrop force before/after the FriendlyTank handoff. Native production gates
can stop Action-created teams from assembling.

Two defects were reproduced in generated maps:

1. The clone builder recognized the reviewed TaskForces, but the later
   reference writer still required their owners to be in the optional
   helper-buff house set. With helper buffs off, FriendlyTank's Rhino/Tesla
   TaskForces stayed native. The writer now honors the existing explicit
   TaskForce policy independently of helper buffs. Clone ownership includes
   only the reviewed runtime countries for those payload types; reference-only
   payloads remain locked and free of incompatible native production gates.
2. With helper buffs on, a build-only Drakuv clone could replace the placed
   `RAVA` while its scripted TaskForce and exact loss event still used native
   `RAVA`. The placement guard now keeps exact story identities native when
   their clone is build-only and therefore has no matching event/team rewrite.
   Ordinary selectable starting infantry still use their existing clones.

BadTank's separate `01000045` TaskForce stays native. The fixes do not enable
all helper buffs, rewrite enemy teams or add mission-specific timer logic.

Changed paths:

- `randomizer/maps/clone_references.py`: honors reviewed TaskForce IDs.
- `randomizer/maps/player_clones.py`: passes that existing policy to rewriting.
- `randomizer/maps/clone_builder.py`: reviewed runtime ownership and exact
  story-placement guard. Runtime-country ordering is deterministic.

## Regression coverage and validation

`randomizer/rewards/test_bugreport_upgrades.py` now covers native/current clone
lists, empty and narrowed inhibitor overrides, the normal Opus weapon catalogue,
all weapon baselines, support-weapon exclusions and replacement passenger tiers.

`tools/check_reported_regressions.py` generates installed campaign maps for:

- Chaos with Mission List and Shop Mode, helper buffs on/off, no purchases and
  a real Shop cloak purchase followed by a mission reroll.
- All four opening TaskForces, their counts/runtime ownership, unchanged
  BadTank payload and team scripts, uncloaked delivered Rhino references, and
  consistent Drakuv placement/loss-event identities.
- Both progression modes and every passenger tier, one registered payload,
  all 112 Opus weapon mounts, hover movement/range and native/clone inhibitors.
- Thread of Dread's authored Hovracoon exclusion.

The existing full campaign audit invokes these focused checks too. Player-facing
and maintainer documentation is updated in `README_RANDOMIZER.md` and
`configs/README.md`.

Completed validation:

- Python compilation and `git diff --check` passed.
- Launcher `--self-check` passed.
- Upgrade and launch unit suites: 17 tests, 16 passed and one Windows-only test
  skipped under Linux. The Windows build separately runs its launch suite and
  exercises the packaged executable's `--launch-self-check` under Wine.
- All 97 campaign maps passed the Chaos/Shop and Standard/Mission List audits,
  including the existing mission-specific, Shop modifier/boon and AI checks.
  The added Noise/Opus/Hovracoon generation matrix passed in that full audit.
- The weapon completion tool is idempotent; decoded snapshot differences are
  limited to STNK and its eight weapons. Player-option migration is idempotent
  and preserves previously disabled buff types.
- Windows launcher and matching APWorld built successfully to
  `/tmp/MentalOmegaRandomizer-reported-fixes.exe` and
  `/tmp/mental-omega-build/mental_omega.apworld`. The installed launcher was
  not replaced. Existing exported item/location IDs remain stable.
- The built APWorld passed generation, YAML, fill/handshake, catalogue/legacy
  compatibility and purchase/stage checks. The complete integration suite has
  one pre-existing failing Shop UI fixture in five subcases:
  `AttributeError: 'Controller' object has no attribute 'shop_coop_mode_check'`.
  All five errors were reproduced using an unchanged HEAD checkout.
- The tooltip suite has two pre-existing failures: the Rejuvenator healing
  baseline bracket assertion and the expected multiline Shop effect display.
  Both were reproduced on an unchanged HEAD checkout. They were not changed
  as part of these unit/mission fixes.

No live engine playthrough was performed. These checks prove generated rules,
ownership, payload cardinality, weapon changes and mission identity alignment;
they do not prove that Noise Severe reaches victory or that a nuke is blocked
in a running game. Live play of SNOISE and an inhibitor-enabled nuke mission
remains the final gameplay verification.
