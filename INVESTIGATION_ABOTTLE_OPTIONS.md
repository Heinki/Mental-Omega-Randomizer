# Options Creator and Bottleneck regressions (1.41)

## Options Creator

The release workflow builds from a source checkout without the game's
`INI/BattleClient.ini`. `parse_missions` returned an empty list; the APWorld
builder then regenerated both catalogue and generation input with zero
missions. `MissionGoal.range_end = len(MISSION_DATA)` became zero, producing
the broken slider and rejecting YAML values such as 97.

`Archipelago/generation_missions.json` now retains the full 97-mission input.
Installed-game catalogue regeneration refreshes it; clean release builds use
it for both the catalogue projection and generation data. Both Windows
builders and the APWorld include this resource. Packaging rejects empty
catalogues and checks the explicit option bound against the mission count.

## Bottleneck (`ABOTTLE`)

The supplied map was reproduced in a temporary Mental Omega 3.3.6 install with
all generated modifiers intact. It crashed during the opening at
`C0000005 / 0071B173`. Disassembly and the engine class headers place the
exception in `TemporalClass::Fire`, dereferencing its cleared target.

Demolition Charges set `Explodes=yes` without providing a death weapon for
types lacking one. The engine falls back to the current primary weapon.
Native Chrono Legionnaires (`CLEG` and `AICLEG`) therefore tried to fire their
temporal primary while dying. The same fallback was unsafe for other control
and spawn weapons.

The modifier now supplies the installed InfantryDeathWeapon, UnitDeathWeapon,
or AircraftDeathWeapon when the effective type has no explicit death weapon.
This includes native types and registered player/payload clones. Authored
death weapons remain intact, including Bottleneck's `NCHF` EMP discharge.
Melee Fighters and One Shot, One Kill retain their configured effects.

The corrected supplied map passed the previously crashing opening and
continued through live combat and power use without that exception. This is
an opening/combat reproduction check, not a complete campaign playthrough.

## Validation

- Death-weapon, reported-upgrade, and launch unit suites: 21 passed; one
  Windows-only check skipped under Linux. The Windows build ran its launch
  checks successfully.
- Existing mission generation regressions plus the new Bottleneck case passed.
- A clean checkout without a game installation built a full APWorld with 97
  missions, 4,158 items, and 35,876 locations. Its bytes matched the installed
  build. All 13 real Archipelago integration checks passed against that archive,
  including 97-mission generation, all progression modes, fill, and handshake.
- All 97 maps passed the safe death-weapon fallback checks.
- The full 97-map Chaos/Shop and Standard/Mission List audit passed, including
  focused transport, mutation, AI, power, and reported-unit regressions.
- Full launcher and Shop domain self-checks passed. The obsolete enemy-scaling
  assertion now checks the preserved total limit (999) independently of the
  five-item per-kind cap; gameplay scaling is unchanged.

Engine reference: [YRpp TemporalClass](https://github.com/Phobos-developers/YRpp/blob/master/TemporalClass.h).
