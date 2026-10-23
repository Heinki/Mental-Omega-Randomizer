"""Bounded Powerhouse waves and private AI-only challenge powers."""

from collections import Counter
from copy import deepcopy

from randomizer.challenges.catalogue import SIDE_COUNTRIES, SIDE_FAMILIES
from randomizer.maps.enemy_powerhouses import POWERHOUSE_UNITS_BY_FAMILY
from randomizer.maps.enemy_scaling import enemy_power_launch_rewards
from randomizer.rewards.catalogue import REWARD_POOL
from randomizer.rewards.enemy_scaling import build_enemy_reward_pool


FAMILIES = dict(zip(SIDE_COUNTRIES, SIDE_FAMILIES))
OFFENSIVE = {'allies': 'ai_lightning_storm', 'soviets': 'ai_nuclear_missile',
             'epsilon': 'ai_psychic_dominator', 'foehn': 'ai_great_tempest'}


def add_powerhouses(plan):
    """Freeze the extra heavy identities inside the existing enemy cap budget."""
    from .pressure import size_composition
    if not any(entry.get('enemy_effect_id') == 'powerhouse' for entry in plan['challenges']):
        return
    limit = min(plan['max_wave_units'], plan['wave_pressure']['max_active_units'])
    for wave_index, wave in enumerate(plan['wave_schedule']):
        headroom = limit - sum(unit['count'] for group in wave['groups'] for unit in group['units'])
        for group in wave['groups']:
            pool = POWERHOUSE_UNITS_BY_FAMILY[FAMILIES[group['country']]]
            side = plan['map']['enemy_waypoints'].index(group['waypoint'])
            heavy = [pool[(wave_index + side + offset) % len(pool)] for offset in range(2)]
            extra = min(2, headroom)
            total = sum(unit['count'] for unit in group['units']) + extra
            if total < 3:
                raise ValueError('Powerhouse waves need room for two heavies and one ordinary unit.')
            if plan.get('wave_priorities'):
                from .wave_priority import priority
                policy = plan['wave_priorities']
                ordered = sorted(group['units'], key=lambda u: (-priority(u['type'], policy), -u['count']))
                base = ordered[:4]
                infantry = next((u for u in ordered if u['type'] in policy['infantry_units']), None)
                if infantry and not any(u['type'] in policy['infantry_units'] for u in base):
                    base[-1] = infantry
            else:
                base = sorted(group['units'], key=lambda unit: -unit['count'])[:4]
            units = size_composition(base, base_units=total - 2, seed=plan['seed'],
                                     house=side + 2, seconds=wave['seconds'])
            counts = Counter({unit['type']: unit['count'] for unit in units})
            counts.update(heavy)
            group.update(units=[{'type': kind, 'count': count} for kind, count in counts.items()],
                         powerhouse_types=heavy, veteran_level=2)
            headroom -= extra
        if 'size' in wave:
            wave['size']['total_units'] = sum(unit['count'] for group in wave['groups'] for unit in group['units'])


def rewards_for(plan, country):
    """Use reviewed Grid reward payloads without mutating native power sections."""
    pool = {entry['enemy_effect_id']: entry for entry in build_enemy_reward_pool(REWARD_POOL)}
    result = []
    for challenge in plan.get('challenges', []):
        key = challenge.get('enemy_effect_id')
        offensive = key == 'faction_superweapons'
        if offensive:
            key = OFFENSIVE[FAMILIES[country]]
        if key not in {'ai_paratroopers', 'ai_bloodhounds', 'ai_moon_reinforcements', *OFFENSIVE.values()}:
            continue
        reward = deepcopy(pool[key])
        reward['enemy_use_existing_power'] = False
        if offensive:
            reward['enemy_isolated_native_power'] = True
        converted = enemy_power_launch_rewards([reward])[0]
        converted['superweapon_recharge_multiplier'] = (1 if offensive else challenge.get('recharge_multiplier', 2))
        values = converted['superweapon_rules']
        values.update(**{'SW.InitialReady': 'no', 'SW.AutoFire': 'yes',
                         'SW.Shots': '-1' if offensive else str(challenge.get('shots', 3)),
                         'ShowTimer': 'yes' if offensive else 'no', 'DisableableFromShell': 'no'})
        if plan.get('plan_version', 1) >= 31:
            # Hidden providers are not newly discovered silos or Dominators.
            # Preserve genuine readiness/launch notifications and the power.
            # Empty CSF literal clears native text without resolving "none".
            values.update({'EVA.Detected': 'none', 'Message.Detected': 'NOSTR:'})
        if key == 'ai_paratroopers':
            # Explicit portable payload avoids native General defaults choosing
            # another faction's infantry for an isolated derivative country.
            payload = {'allies': ('E1,GGI', '6,2'), 'soviets': ('E2,FLAKT', '8,4'),
                       'epsilon': ('INIT,HARP', '6,2'), 'foehn': ('COVE,HUNTR', '6,2')}
            types, counts = payload[FAMILIES[country]]
            values.update(Type='AmerParaDrop', **{'ParaDrop.Types': types, 'ParaDrop.Num': counts})
        result.append(converted)
    return result


def apply_enemy_powers(writer, plan, rules, enemy_aliases):
    """Provide one real owned launch source for every private hostile power."""
    from randomizer.maps.base import cloned_superweapon_plan
    from randomizer.maps.buff_values import _register_map_type
    from randomizer.maps.ini import IniLines, merge_ini_section_values, section_value_map
    from .engine import _place, _transfer_tag

    if plan.get('plan_version', 1) < 12:
        return
    templates = dict(rules)
    for original, alias in enemy_aliases.items():
        templates[original] = deepcopy(writer.sections[alias])
    points = section_value_map(writer.lines, 'Waypoints')
    occupied = {plan['map']['player_waypoint'], *plan['map']['enemy_waypoints'],
                *plan.get('allied_waypoints', [])}
    # First spare start hosts friendly powers. Use the second for hostile
    # providers so helpers, camp grants and cash escrows keep their own cells.
    spare = [number for number in range(8) if number not in occupied][1]
    cell = int(points[str(spare)])
    for index, country in enumerate(plan['enemy_countries']):
        rewards = rewards_for(plan, country)
        if not rewards:
            continue
        actor = f'FFENEMY{index + 1}'
        for reward in rewards:
            reward['superweapon_clone'] = writer.key()
        current = IniLines(list(writer.lines))
        merge_ini_section_values(current, writer.sections)
        sections, actions, clones, startup, static, missing = cloned_superweapon_plan(
            current, rewards, tuple(rules['SuperWeaponTypes'].values()), templates,
            superweapon_required_houses=(actor,), force_required_houses=True,
            allow_player=False, allow_ai=True)
        if startup or static or missing or len(clones) != len(rewards):
            raise ValueError('Unsupported Fortress enemy power dependencies: ' + ', '.join(missing))
        for section, values in sections.items():
            row = {key: str(value) for key, value in values.items() if value is not None}
            for field in ('Deliver.Types', 'ParaDrop.Types', 'DropPod.Types'):
                if field in row:
                    row[field] = ','.join(enemy_aliases.get(kind.strip(), kind.strip())
                                          for kind in row[field].split(','))
            writer.sections.setdefault(section, {}).update(row)
        tag = _transfer_tag(writer, plan['map']['enemy_waypoints'][index], 'Enemy power ownership ' + actor)
        for slot, power in enumerate(clones):
            provider = writer.key()
            row = deepcopy(rules['CABHUT'])
            row.update(Image='CABHUT', Name='Final Fortress enemy power provider',
                       InvisibleInGame='yes', IsPassable='yes', Immune='yes', LegalTarget='no',
                       Selectable='no', Capturable='no', Insignificant='no', DontScore='no',
                       KeepAlive='no', RadarInvisible='yes', Unsellable='yes', CanBeOccupied='no',
                       BridgeRepairHut='no', TechLevel='-1', BuildLimit='0', SuperWeapon=power,
                       ProduceCashStartup='0', ProduceCashAmount='0', ProduceCashDelay='0')
            writer.sections[provider] = row
            _register_map_type(writer.sections, writer.lines, rules, 'BuildingTypes', provider)
            _place(writer, 'Structures', f'Neutral,{provider},256,{cell % 1000 + slot},'
                   f'{cell // 1000 + index + 1},64,{tag},1,0,1,0,0,None,None,None,0,0')
            writer.put('FFEnemyPowers', power, f'{actor},{rewards[slot]["superweapon"]}')
        writer.trigger('Fortress enemy powers ' + actor, [(13, 0, 2)], actions, owner=actor)
