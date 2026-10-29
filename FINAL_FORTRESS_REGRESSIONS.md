# Final Fortress 1.46: Iron Guard, Nuclear Converter and aircraft queues

## Findings and fixes

All three reports have corresponding faults in the Fortress map adapter.
Verification here concerns emitted game data; native gameplay has not been run.

- **Iron Guard:** Fortress copies buildings for Structure Capacity and other
  perks, and also creates private enemy buildings. `IronGuardSpecial` still
  listed only native `NAIRDM` in `EMPulse.Cannons`, excluding those copies from
  the automatic self-targeted field. The adapter now extends explicit cannon
  lists with the actual friendly and enemy identities while retaining native
  entries and power settings. This also covers Nuclear Path's copied reactors.
- **Nuclear Converter:** More power! copies `NANRCT`, but the converter's
  `PowersUpBuilding` still targeted native `NANRCT`. The dependent-upgrade pass
  previously ran only for infrastructure health. It now copies and retargets
  eligible upgrades whenever their host is copied. Power Turbines use the same
  fix. Native prerequisites, ownership restrictions and upgrade slots remain
  intact.
- **Aircraft queues:** The earlier fix in commit `2c9dfe9` registered copied
  planes in `[General] PadAircraft` for the campaign pipeline. Fortress used
  a separate generator that omitted this registration. It now reuses that
  adapter for friendly and enemy aircraft, so copied planes participate in
  native airfield capacity checks.

The cannon and aircraft list changes are included in both generated scenarios
and the rules preload, before the engine creates houses and production queues.
Map-specific lists and previous additions are preserved. These changes do not
alter frozen perk ranks or player profiles.

## Validation

The installed-map audit now inspects aircraft capacity lists, cannon lists,
upgrade attachments and their preload values for every emitted configuration.
It includes dedicated first-rank and maximum-rank More power! profiles, so the
converter check no longer depends on also buying infrastructure health.

Validation completed on 2026-10-29:

- Before the patch, all 12 baseline country variants of the installed Miners in
  the Sun map contained copied aircraft missing from `PadAircraft` and copied
  Iron Guards missing from `IronGuardSpecial.EMPulse.Cannons`.
- After the patch, 72 solo configurations passed: all 12 countries with baseline,
  first-rank generators, maximum-rank generators, Structure Capacity,
  infrastructure health and maximum perks/Challenges.
- Another 36 two-human co-op configurations passed: all 12 countries with
  first-rank generators, Structure Capacity and the secondary-power/tier profile.
  The last profile covers copied player aircraft alongside enemy aircraft.
- In the first-rank Soviet generator map, the reactor produces 2500 power and
  the converter's `PowersUpBuilding` matches its private reactor ID. The same
  reactor appears in `NuclearPathSpecial.EMPulse.Cannons`. In the Structure
  Capacity map, the private Iron Guard keeps build limit 5 and appears beside
  native and enemy guards in the cannon list.
- Python compilation and `git diff --check` passed. The Windows 1.46 launcher
  built successfully; its packaged installation/configuration report passed.
  The installed launcher and checksum metadata were updated. No release was
  published.

Audit commands:

```sh
.venv/bin/python tools/audit_final_fortress_maps.py \
  --output /tmp/fortress-regressions-after \
  --profiles baseline generators-first generators building-limits infrastructure maximum \
  --difficulties easy
.venv/bin/python tools/audit_final_fortress_maps.py \
  --output /tmp/fortress-regressions-coop \
  --profiles generators-first building-limits secondary --humans 2 --difficulties easy
```

The audit writes generated maps, spawn files and a manifest without changing
installed source maps or player profiles. Artifacts and the before-patch
findings are under `/tmp/fortress-regressions-*`.

The previous installed launcher and checksum metadata are preserved under
`backups/fortress-regressions-20261029-144822/`. Both
`../MentalOmegaRandomizer.exe` and `../MentalOmegaRandomizer-FortressFix.exe`
contain the repaired build, with SHA256
`e8c86b839c9cc6316436ac59db3f57102f06130671237b3727df37f33d5b664d`.

## Gameplay confirmation

Restart the launcher and launch a Fortress run to generate the repaired map and
preload. A saved native game retains its old type definitions.

1. Buy Structure Capacity, build an Iron Curtain and an Iron Guard, and provide
   sufficient power. Confirm the guard's automatic field protects nearby units.
2. Buy only More power!, build a Nuclear Reactor, attach a Nuclear Converter,
   and confirm its abilities can fire. Repeat with infrastructure health.
3. Fill an airfield's pads using a mixture of aircraft types. Confirm further
   orders respect capacity; freeing a pad should allow another aircraft.
