"""Fortress power unlocks using the established isolated Grid/Shop buff planner."""

from copy import deepcopy

from randomizer.maps.base import cloned_superweapon_plan
from randomizer.maps.buff_values import _register_map_type
from randomizer.maps.ini import IniLines, merge_ini_section_values, section_value_map
from randomizer.maps.power_buffs import apply_power_buffs_to_unlock_rewards
from randomizer.rewards.catalogue import REWARD_POOL
from randomizer.rewards.power_buff_definitions import (
    POWER_BUFF_TYPES, power_buff_effect_text, power_buff_stack_limit, power_buff_type_ids,
)


def upgrade_description(stacks):
    """Describe compatible upgrades without suggesting that they unlock powers."""
    effects = [power_buff_effect_text({'power_buff_type': entry['id']}, stacks)
               for entry in POWER_BUFF_TYPES if entry['id'] != 'effect']
    return ('Unlocked perk powers only; compatible effects: ' + '; '.join(effects)
            + '; stronger status effects where supported. Each power uses only its reviewed '
              'capabilities and their caps. Does not unlock any power.')


def power_rewards(plan, rules):
    """Fold purchased ranks into actual unlocks, never into native enemy powers."""
    catalogue = {entry['superweapon']: entry for entry in REWARD_POOL
                 if entry.get('kind') == 'superweapon'}
    unlocks, buffs = [], []
    stacks = plan['effects'].get('power_upgrade_stacks', 0)
    for original in plan['effects']['support_powers']:
        if original not in rules['SuperWeaponTypes'].values():
            raise ValueError(f'Unknown Fortress power: {original}.')
        reward = deepcopy(catalogue.get(original, {
            'name': rules[original].get('Name', original), 'kind': 'superweapon',
            'superweapon': original,
        }))
        reward['_runtime_canonical'] = True
        values = reward.setdefault('superweapon_rules', {})
        values.update(Name='Fortress ' + rules[original].get('Name', original),
                      IsPowered='no', DisableableFromShell='no', ShowTimer='no',
                      **{key: '' for key in ('SW.AuxBuildings', 'SW.NegBuildings',
                                            'SW.RequiredHouses', 'SW.ForbiddenHouses', 'SW.Designators')})
        if original == 'AmericanParaDropSpecial' and plan['effects']['starting_units']:
            army = plan['effects']['starting_units'][:2]
            values['ParaDrop.Types'] = ','.join(unit['type'] for unit in army)
            values['ParaDrop.Num'] = '6,4' if len(army) > 1 else '10'
        unlocks.append(reward)
        for capability in power_buff_type_ids(original):
            buff = {'kind': 'buff', 'power_buff_type': capability,
                    'superweapon': original, '_runtime_canonical': True}
            buffs.extend([buff] * min(stacks, power_buff_stack_limit(buff) or stacks))
    return apply_power_buffs_to_unlock_rewards([*unlocks, *buffs], rules)


def apply_powers(writer, plan, rules, country_aliases):
    """Grant private powers, with an owned launch source for every power."""
    from .engine import _place, _transfer_tag
    from .player_perks import coalition, human_actor

    powers = plan['effects']['support_powers']
    if (not powers and not (plan.get('allied_countries') and plan['effects']['starting_credits'])
            and not plan.get('coop_players')):
        return
    # Native payload templates inherit the coalition's already isolated unit
    # buffs before the shared power planner applies its own compatible effects.
    templates = deepcopy(rules)
    for original, alias in country_aliases.items():
        templates[original] = deepcopy(writer.sections[alias])
    rewards = power_rewards(plan, templates)
    points = section_value_map(writer.lines, 'Waypoints')
    occupied = {plan['map']['player_waypoint'], *plan['map']['enemy_waypoints'],
                *plan.get('allied_waypoints', [])}
    spare = next(number for number in range(8) if number not in occupied)
    cell = int(points[str(spare)])
    for actor_index, (actor, _, waypoint) in enumerate(coalition(plan)):
        reveal = bool(plan.get('coop_players') and plan['effects'].get('reveal_map'))
        if actor == 'FFPLAYER' and not powers and not reveal:
            continue
        current = IniLines(list(writer.lines))
        merge_ini_section_values(current, writer.sections)
        sections, actions, clones, startup, static, missing = cloned_superweapon_plan(
            current, rewards, tuple(rules['SuperWeaponTypes'].values()), templates,
            superweapon_required_houses=(actor,), force_required_houses=True,
            allow_player=human_actor(plan, actor), allow_ai=not human_actor(plan, actor))
        if missing or startup or static:
            raise ValueError('Unsupported Fortress power dependencies: '
                             + ', '.join([*missing, *startup, *static]))
        for section, values in sections.items():
            row = {key: str(value) for key, value in values.items() if value is not None}
            # Keep normal production restrictions while routing delivered units
            # to the coalition's private stat copies when one exists.
            for field in ('Deliver.Types', 'ParaDrop.Types', 'DropPod.Types'):
                if field in row:
                    row[field] = ','.join(country_aliases.get(kind.strip(), kind.strip())
                                          for kind in row[field].split(','))
            writer.sections.setdefault(section, {}).update(row)
        tag = _transfer_tag(writer, waypoint, 'Support power ownership ' + actor)
        # Ares GenericWarhead needs a real owned launch building for house
        # filtering. A dedicated primary SW slot supplies it for every unlock.
        for index, power in enumerate(clones or [None]):
            provider = writer.key()
            row = deepcopy(rules['CABHUT'])
            row.update(Image='CABHUT', Name='Final Fortress support powers', InvisibleInGame='yes',
                       IsPassable='yes', Immune='yes', LegalTarget='no', Selectable='no', Capturable='no',
                       Insignificant='no', DontScore='no', KeepAlive='no', RadarInvisible='yes',
                       Unsellable='yes', CanBeOccupied='no', BridgeRepairHut='no', TechLevel='-1',
                       BuildLimit='0', ProduceCashStartup=str(plan['effects']['starting_credits']
                           if actor != 'FFPLAYER' and index == 0 else 0),
                       ProduceCashAmount='0', ProduceCashDelay='0')
            if power:
                row['SuperWeapon'] = power
            if reveal:
                row['SpySat'] = 'yes'
            writer.sections[provider] = row
            _register_map_type(writer.sections, writer.lines, rules, 'BuildingTypes', provider)
            _place(writer, 'Structures', f'Neutral,{provider},256,{cell % 1000 + index},'
                   f'{cell // 1000 + actor_index + 1},64,{tag},1,0,1,0,0,None,None,None,0,0')
        if actions:
            writer.trigger('Fortress perk powers ' + actor, [(13, 0, 2)], actions, owner=actor)


def apply_drakuv_power(writer, plan, rules, aliases):
    """Bind the Field Bureau to its coalition's reviewed, early-loaded payload.

    This remains a building-provided power with its installed price, recharge,
    power and targeting gates. It is not an additional action-granted perk.
    """
    from .player_perks import coalition
    prison, payload = aliases.get('NAPRIS'), aliases.get('RAVA')
    if not prison or not payload:
        return
    power = writer.key()
    row = deepcopy(rules['DrakuvSpecial'])
    row.update({'Deliver.Types': payload,
                'SW.RequiredHouses': ','.join(actor for actor, _, _ in coalition(plan)),
                'SW.Designators': ','.join(dict.fromkeys([
                    *row.get('SW.Designators', '').split(','), prison]))})
    writer.sections[power] = row
    _register_map_type(writer.sections, writer.lines, rules, 'SuperWeaponTypes', power)
    writer.put(prison, 'SuperWeapon2', power)
    writer.put('FFDrakuvPower', 'Power', power)
    writer.put('FFDrakuvPower', 'Provider', prison)
    writer.put('FFDrakuvPower', 'Payload', payload)
