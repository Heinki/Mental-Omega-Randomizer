"""Map-local engine hooks required by player-owned special buildings."""

from randomizer.core.collections import comma_items, unique_in_order
from randomizer.maps.ini import all_section_value_maps
from randomizer.rewards.catalogue import BUFF_TARGETS


REPROCESSOR_SOURCE_ID = 'FAREPR'
REPROCESSOR_BOUNTY_SECTION = 'General'
REPROCESSOR_BOUNTY_KEY = 'BountyEnablers'
REPROCESSOR_BOUNTY_CATEGORIES = frozenset({
    'infantry', 'units', 'aircraft',
})


def _section_values(sections, section):
    wanted = str(section).lower()
    return next(
        (
            {
                str(key).lower(): str(value)
                for key, value in values.items()
            }
            for name, values in (sections or {}).items()
            if str(name).lower() == wanted
        ),
        {},
    )


def _effective_section_values(map_sections, installed_sections, section):
    values = _section_values(installed_sections, section)
    values.update(_section_values(map_sections, section))
    return values


def reprocessor_bounty_rules(
    lines,
    installed_sections,
    clone_handled,
    buildable_tech_ids=(),
):
    """Bind Ares bounty activation to the actual player Reprocessor clone.

    Ares checks ``[General]BountyEnablers`` by exact BuildingType. Native
    Mental Omega lists only ``FAREPR``. Randomizer production uses an isolated
    player clone, so owning it cannot activate bounty until its runtime ID is
    appended here.
    """
    reprocessor = (clone_handled or {}).get(REPROCESSOR_SOURCE_ID, {})
    clone_id = str(reprocessor.get('clone_id') or '').strip()
    report = {
        'clone_id': clone_id,
        'trigger_enabled': False,
        'trigger_mode': 'absent',
        'registered': False,
        'enablers': (),
        'eligible_by_faction': {},
        'eligible_unit_ids': (),
        'excluded_unit_ids': (),
        'issues': (),
    }
    if not clone_id:
        return {}, report

    map_sections = all_section_value_maps(lines)
    map_general = _section_values(map_sections, REPROCESSOR_BOUNTY_SECTION)
    installed_general = _section_values(
        installed_sections, REPROCESSOR_BOUNTY_SECTION
    )
    bounty_key = REPROCESSOR_BOUNTY_KEY.lower()
    explicit_map_enablers = bounty_key in map_general
    raw_enablers = (
        map_general.get(bounty_key, '')
        if explicit_map_enablers
        else installed_general.get(bounty_key, '')
    )
    enablers = unique_in_order(comma_items(raw_enablers))

    registered_buildings = {
        str(value).upper()
        for value in _effective_section_values(
            map_sections, installed_sections, 'BuildingTypes'
        ).values()
        if str(value).strip()
    }
    registered = clone_id.upper() in registered_buildings
    rules = {}
    if explicit_map_enablers and not str(raw_enablers).strip():
        # Empty list means bounty is globally enabled. Preserve authored map
        # behavior instead of changing it into a Reprocessor-only gate.
        effective_enablers = ()
        trigger_mode = 'always'
        trigger_enabled = True
    else:
        effective_enablers = tuple(unique_in_order(enablers + [clone_id]))
        trigger_mode = 'building'
        trigger_enabled = registered and clone_id.upper() in {
            item.upper() for item in effective_enablers
        }
        rules = {
            REPROCESSOR_BOUNTY_SECTION: {
                REPROCESSOR_BOUNTY_KEY: ','.join(effective_enablers),
            }
        }

    eligible_by_faction = {}
    eligible_ids = []
    excluded_ids = []
    candidate_ids = {
        str(unit_id).upper()
        for unit_id in buildable_tech_ids
        if str(unit_id).strip()
    }
    for unit_id in sorted(candidate_ids):
        target = BUFF_TARGETS.get(unit_id, {})
        if target.get('category') not in REPROCESSOR_BOUNTY_CATEGORIES:
            continue
        actual_id = str(
            (clone_handled or {}).get(unit_id, {}).get('clone_id') or unit_id
        )
        values = _effective_section_values(
            map_sections, installed_sections, actual_id
        )
        if str(values.get('bounty', '')).strip().lower() == 'yes':
            eligible_ids.append(actual_id)
            for faction in target.get('factions', ()):
                eligible_by_faction.setdefault(str(faction), []).append(
                    actual_id
                )
        else:
            excluded_ids.append(actual_id)

    issues = []
    if not registered:
        issues.append(f'{clone_id} is absent from BuildingTypes')
    if not trigger_enabled:
        issues.append(f'{clone_id} is absent from effective BountyEnablers')
    if not eligible_ids:
        issues.append('no buildable player units have Bounty=yes')

    report.update({
        'trigger_enabled': trigger_enabled,
        'trigger_mode': trigger_mode,
        'registered': registered,
        'enablers': effective_enablers,
        'eligible_by_faction': {
            faction: tuple(unit_ids)
            for faction, unit_ids in sorted(eligible_by_faction.items())
        },
        'eligible_unit_ids': tuple(eligible_ids),
        'excluded_unit_ids': tuple(excluded_ids),
        'issues': tuple(issues),
    })
    return rules, report


def validate_reprocessor_bounty_support():
    """Self-check native parity plus four-faction player-clone eligibility."""
    from randomizer.rewards.roster import randomizer_unit_roster

    _paths, clone_ids, templates = randomizer_unit_roster()
    representatives = {
        'Allies': 'E1',
        'Soviets': 'E2',
        'Epsilon': 'INIT',
        'Foehn': 'KNIGHT',
    }

    def value(values, key, default=''):
        wanted = str(key).lower()
        return next(
            (
                str(raw_value)
                for raw_key, raw_value in values.items()
                if str(raw_key).lower() == wanted
            ),
            default,
        )

    eligible_by_faction = {}
    excluded_by_faction = {}
    for faction in representatives:
        faction_ids = sorted(
            unit_id
            for unit_id, target in BUFF_TARGETS.items()
            if faction in target.get('factions', ())
            and target.get('category') in REPROCESSOR_BOUNTY_CATEGORIES
        )
        eligible_by_faction[faction] = [
            unit_id
            for unit_id in faction_ids
            if value(templates.get(unit_id, {}), 'Bounty').lower() == 'yes'
        ]
        excluded_by_faction[faction] = [
            unit_id
            for unit_id in faction_ids
            if value(templates.get(unit_id, {}), 'Bounty').lower() != 'yes'
        ]

    reprocessor_template = templates.get(REPROCESSOR_SOURCE_ID, {})
    native_parity = {
        'powered': value(reprocessor_template, 'Powered').lower() == 'true',
        'power': value(reprocessor_template, 'Power') == '-200',
        'superweapon': (
            value(reprocessor_template, 'SuperWeapon') == 'DevourerSpecial'
        ),
        'empulse_cannon': (
            value(reprocessor_template, 'EMPulseCannon').lower() == 'yes'
        ),
        'native_prerequisite': (
            value(reprocessor_template, 'Prerequisite') == 'FACNST,FOETECH'
        ),
    }

    lines = [
        '[BuildingTypes]',
        f'0={clone_ids[REPROCESSOR_SOURCE_ID]}',
        '',
        f'[{clone_ids[REPROCESSOR_SOURCE_ID]}]',
        'Bounty=no',
    ]
    clone_handled = {
        REPROCESSOR_SOURCE_ID: {
            'clone_id': clone_ids[REPROCESSOR_SOURCE_ID],
        }
    }
    for faction, source_id in representatives.items():
        clone_id = clone_ids[source_id]
        clone_handled[source_id] = {'clone_id': clone_id}
        lines.extend([
            '',
            f'[{clone_id}]',
            f'Bounty={value(templates[source_id], "Bounty")}',
        ])
    runtime_rules, runtime_report = reprocessor_bounty_rules(
        lines,
        {
            'General': {'BountyEnablers': REPROCESSOR_SOURCE_ID},
        },
        clone_handled,
        buildable_tech_ids=representatives.values(),
    )
    runtime_enablers = comma_items(
        runtime_rules.get(REPROCESSOR_BOUNTY_SECTION, {}).get(
            REPROCESSOR_BOUNTY_KEY, ''
        )
    )
    representative_results = {
        faction: clone_ids[source_id] in runtime_report['eligible_unit_ids']
        for faction, source_id in representatives.items()
    }
    errors = []
    errors.extend(
        f'Reprocessor template lacks native {field}'
        for field, valid in native_parity.items()
        if not valid
    )
    errors.extend(
        f'{faction} representative {representatives[faction]} lacks Bounty=yes'
        for faction, valid in representative_results.items()
        if not valid
    )
    if not runtime_report['trigger_enabled']:
        errors.extend(runtime_report['issues'])
    if REPROCESSOR_SOURCE_ID not in runtime_enablers:
        errors.append('native FAREPR was removed from BountyEnablers')
    if clone_ids[REPROCESSOR_SOURCE_ID] not in runtime_enablers:
        errors.append('player Reprocessor clone was not added to BountyEnablers')
    if errors:
        raise ValueError(
            'Reprocessor bounty validation failed: ' + '; '.join(errors)
        )
    return {
        'native_parity': native_parity,
        'runtime_enablers': runtime_enablers,
        'representatives': representatives,
        'representative_results': representative_results,
        'eligible_counts': {
            faction: len(unit_ids)
            for faction, unit_ids in eligible_by_faction.items()
        },
        'excluded_unit_ids': excluded_by_faction,
    }
