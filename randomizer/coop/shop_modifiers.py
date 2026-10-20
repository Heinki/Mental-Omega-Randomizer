"""Apply personal Shop tradeoffs to RA2 production clones, never native actors."""

import hashlib

from randomizer.maps.shop_modifiers import apply_shop_clone_modifiers


def apply_personal_shop_modifiers(changes, handled, installed, native, settings,
                                 scope, register):
    if not settings:
        return
    damage = settings.get('shop_player_damage_percent', 1.0) != 1.0
    personal = {}
    seen = set()
    for source, details in handled.items():
        clone = details['clone_id']
        if clone in seen or clone not in changes:
            continue
        seen.add(clone)
        weapons = {}
        if damage:
            from randomizer.coop.reward_map import _lookup, _weapon_key
            from randomizer.rewards.catalogue import BUFF_TARGETS

            mind_control = {
                str(key).upper()
                for key in BUFF_TARGETS.get(source, {}).get('mind_control_weapons', {})
            }
            source_values = _lookup(installed, source)
            source_values.update(_lookup(native, source))
            for field, weapon in list(changes[clone].items()):
                if not _weapon_key(field) or not weapon:
                    continue
                definition = _lookup(installed, weapon)
                definition.update(_lookup(native, weapon))
                definition.update(_lookup(changes, weapon))
                # Damage is capacity for mind-control weapons, and negative
                # damage heals. Neither is a firepower tradeoff.
                original = next((value for key, value in source_values.items()
                                 if str(key).lower() == str(field).lower()), weapon)
                if str(original).upper() in mind_control:
                    continue
                amount = next((value for key, value in definition.items()
                               if str(key).lower() == 'damage'), 0)
                try:
                    if float(amount) <= 0:
                        continue
                except (TypeError, ValueError):
                    continue
                if weapon not in weapons:
                    suffix = hashlib.sha1(
                        f'{scope}|{clone}|{weapon}'.encode('ascii')
                    ).hexdigest()[:12].upper()
                    private = f'MOR{scope}SM{suffix}'
                    changes[private] = dict(definition)
                    register('WeaponTypes', private)
                    weapons[weapon] = private
                changes[clone][field] = weapons[weapon]
        personal[source] = {'clone_id': clone, 'weapon_clone_ids': weapons}
    apply_shop_clone_modifiers(changes, personal, settings)
