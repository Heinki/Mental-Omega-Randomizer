"""Keep Nanofiber mutations on isolated, buffed player identities."""

from randomizer.rewards.definitions import LINKED_BUFF_VARIANTS
from .base import _collision_safe_type_id, _value_case_insensitive
from .buff_values import _register_map_type
from .ini import all_section_value_maps_preserve


def nanofiber_clone_rules(lines, installed_sections, clone_handled):
    """Append a player-only mutation chain to the native Nanofiber chain.

    Native animations index General.AnimToInfantry, rather than a conversion
    field on the infantry. Preserve those slots for campaign/AI mutations.
    Private armor aliases keep native warheads from consuming player copies;
    the appended chain accepts only those aliases and spawns linked clones.
    Art deployment reads the animation metadata emitted alongside these rules.
    """
    current = all_section_value_maps_preserve(lines)
    installed = {str(k).lower(): v for k, v in installed_sections.items()}
    mapped = {str(k).lower(): v for k, v in current.items()}

    def values(section):
        result = dict(installed.get(section.lower(), {}))
        for key, value in mapped.get(section.lower(), {}).items():
            for old in list(result):
                if str(old).lower() == str(key).lower():
                    result.pop(old)
            result[key] = value
        return result

    active = []
    for source, variants in LINKED_BUFF_VARIANTS.items():
        for target, definition in variants.items():
            stage = definition.get('nanofiber_stage')
            source_clone = (clone_handled.get(source) or {}).get('clone_id')
            target_clone = (clone_handled.get(target) or {}).get('clone_id')
            if stage and source_clone and target_clone:
                reference_clone = clone_handled[source].get('reference_clone_id')
                source_clones = tuple(dict.fromkeys(
                    clone for clone in (source_clone, reference_clone) if clone
                ))
                active.append((int(stage), source_clones, target_clone))
    if not active:
        return {}
    active.sort()
    rules = {}
    reserved = {str(key).lower() for key in set(installed_sections) | set(current)}
    reserved.update(str(key).lower() for key in values('ArmorTypes'))
    mutation_types = [item.strip() for item in str(_value_case_insensitive(
        values('General'), 'AnimToInfantry', ''
    )).split(',') if item.strip()]
    if not mutation_types or not values('Nanofiber7P'):
        raise ValueError('Installed Nanofiber mutation definitions are missing')

    stages = []
    for stage, source_clones, target_clone in active:
        source_clone = source_clones[0]
        ids = {}
        for kind, registry in (
            ('W', 'WeaponTypes'), ('P', 'Projectiles'),
            ('WH', 'Warheads'), ('A', 'Animations'),
        ):
            type_id = _collision_safe_type_id(
                f'MORNano{stage}{kind}', f'nanofiber:{stage}:{kind}', reserved
            )
            ids[kind] = type_id
            _register_map_type(rules, lines, installed_sections, registry, type_id)
        armor = _collision_safe_type_id(
            f'MORNanoArmor{stage}', f'nanofiber-armor:{stage}',
            reserved,
        )
        source_values = values(source_clone)
        original_armor = _value_case_insensitive(source_values, 'Armor')
        if not original_armor:
            raise ValueError(f'Nanofiber source {source_clone} has no armor')
        rules.setdefault('ArmorTypes', {})[armor] = original_armor
        for clone in source_clones:
            rules.setdefault(clone, {})['Armor'] = armor
        native_wh = f'Nanofiber{stage}WH'
        rules.setdefault(native_wh, {})[f'Versus.{armor}'] = '0%'
        warhead = values(native_wh)
        # Include inherited/custom armor overrides but disable their effects.
        for key in list(warhead):
            if str(key).lower().startswith('versus.'):
                warhead[key] = '0%'
        warhead.update({
            'Verses': ','.join(['0%'] * 11),
            f'Versus.{armor}': '100%',
            'InfDeathAnim': ids['A'],
        })
        rules[ids['WH']] = warhead
        weapon = values(f'Nanofiber{stage}Weapon')
        # Health/armor/shop stacks must not prevent the lethal mutation hit.
        strength = max(int(_value_case_insensitive(
            values(clone), 'Strength', 1
        )) for clone in source_clones)
        weapon.update({
            'Warhead': ids['WH'], 'Projectile': ids['P'],
            'Damage': str(min(1_000_000_000, max(2000, strength * 16))),
        })
        rules[ids['W']] = weapon
        if target_clone not in mutation_types:
            mutation_types.append(target_clone)
        rules[ids['A']] = {
            'Image': f'NANODEATH{stage}',
            'MakeInfantry': str(mutation_types.index(target_clone)),
        }
        rules.setdefault('MORNanofiberAnimations', {})[ids['A']] = (
            f'NANODEATH{stage}'
        )
        stages.append(ids)

    rules['General'] = {'AnimToInfantry': ','.join(mutation_types)}
    for index, ids in enumerate(stages):
        projectile = values('Nanofiber7P')
        if index + 1 < len(stages):
            projectile.update({
                'Airburst': 'yes', 'AirburstWeapon': stages[index + 1]['W'],
                'Cluster': '1', 'AirburstSpread': '0.25',
            })
        rules[ids['P']] = projectile
    rules['Nanofiber7P'] = {
        'Airburst': 'yes', 'AirburstWeapon': stages[0]['W'],
        'Cluster': '1', 'AirburstSpread': '0.25',
    }
    return rules


def nanofiber_art_aliases(map_sections, art_sections):
    """Materialize private mutation animations in the temporary art overlay."""
    aliases = {}
    for animation, source in map_sections.get('MORNANOFIBERANIMATIONS', {}).items():
        animation = str(animation).upper()
        source = str(source).upper()
        original = art_sections.get(source)
        if not original:
            raise ValueError(f'Installed Nanofiber animation {source} is missing')
        metadata = map_sections[animation]
        aliases[animation] = {
            **{key: value for key, value in original.items()
               if str(key).lower() not in {'image', 'makeinfantry'}},
            'Image': source,
            'MakeInfantry': metadata['makeinfantry'],
        }
    return aliases
