"""Review economy effects in generated native Fortress maps and rule preloads."""

from math import isclose

from randomizer.final_fortress.player_perks import coalition, _eligible
from randomizer.maps.ini import parse_action_groups
from randomizer.rewards.catalogue import BUFF_TARGETS


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit_economy(rows, effective, plan, rules, preloads):
    if plan.get('plan_version', 1) < 34:
        return
    effects = plan['effects']
    for actor, country, _ in coalition(plan):
        if actor not in effective:
            continue
        for suffix in ('Buildings', 'Defenses', 'Infantry', 'Units', 'Aircraft'):
            field = 'Cost' + suffix + 'Mult'
            discount = effects['construction_discount_percent' if suffix in ('Buildings', 'Defenses')
                               else 'unit_discount_percent']
            expected = float(rules[country].get(field, '1')) * (1 - discount / 100)
            require(isclose(float(effective[actor].get(field, '1')), expected),
                    f'Wrong Fortress purchase discount: {actor}.{field}')
            require(effective[country].get(field) == rules[country].get(field),
                    f'Discount leaked onto native country: {country}.{field}')

    limit = effects['special_building_limit_stacks']
    if limit:
        buildings = set(rules['BuildingTypes'].values())
        for kind, metadata in BUFF_TARGETS.items():
            base = rules.get(kind, {})
            # Check the declared capacity contract independently of the runtime
            # reward-pair filter, including defenses and linked mobile forms.
            if (not metadata.get('building_limit')
                    or int(base.get('BuildLimit', '0')) <= 0
                    or not any(_eligible(base, country) for _, country, _ in coalition(plan))):
                continue
            alias = rows.get('FFPlayerTypes', {}).get(kind)
            require(alias in preloads['rules'], f'Special building has no private limit: {kind}')
            require(int(effective[alias]['BuildLimit']) == int(base['BuildLimit']) + limit,
                    f'Wrong special-building capacity: {kind}')
            require(effective[alias].get('TechLevel') == base.get('TechLevel'),
                    f'Capacity perk changed building technology: {kind}')
            require(effective[alias].get('Prerequisite') == base.get('Prerequisite'),
                    f'Capacity perk changed building prerequisites: {kind}')
            require(effective[kind].get('BuildLimit') == base.get('BuildLimit'),
                    f'Capacity perk leaked onto native type: {kind}')
            allowed = {actor for actor, country, _ in coalition(plan) if _eligible(base, country)}
            require(set(effective[alias]['RequiredHouses'].split(',')) == allowed,
                    f'Capacity perk changed faction access: {kind}')
            for field in ('DeploysInto', 'UndeploysInto'):
                target = base.get(field)
                if not BUFF_TARGETS.get(target, {}).get('building_limit'):
                    continue
                target_alias = rows.get('FFPlayerTypes', {}).get(target)
                require(target_alias in preloads['rules'] and effective[alias].get(field) == target_alias,
                        f'Capacity transformation returns to native type: {kind}.{field}')
                require(int(effective[target_alias]['BuildLimit']) == int(rules[target]['BuildLimit']) + limit,
                        f'Linked form lost special-building capacity: {target}')
        for kind in buildings:
            alias = rows.get('FFPlayerTypes', {}).get(kind)
            if (not alias or BUFF_TARGETS.get(kind, {}).get('building_limit')
                    or int(effective[alias].get('TechLevel', '-1')) < 0):
                continue
            require(int(effective[alias].get('BuildLimit', '0')) == int(rules[kind].get('BuildLimit', '0')),
                    f'Capacity perk changed an unsupported building limit: {kind}')

    personal = plan['fundraising_ranks']
    expected = {actor: personal[slot] if slot < len(personal) else personal[0]
                for slot, (actor, _, _) in enumerate(coalition(plan))}
    expected = {actor: rank for actor, rank in expected.items() if rank}
    metadata = rows.get('FFFundraising', {})
    require(set(metadata) == set(expected), 'Fundraising recipients differ from personal ranks')
    timers = {key for key, value in rows['Triggers'].items()
              if value.split(',')[2].startswith('Fortress Fundraising ')}
    require(len(timers) == len(expected), 'Fundraising must have exactly one timer per active house')
    finished = next(key for key, value in rows['VariableNames'].items()
                    if value == 'Final Fortress finished,0')
    registered = list(dict.fromkeys(effective['SuperWeaponTypes'].values()))
    powers = set()
    for actor, value in metadata.items():
        power, rank, timer = value.split(',')
        require(int(rank) == expected[actor] and power not in powers,
                'Fundraising shares a power between houses or uses the wrong rank')
        powers.add(power)
        require(timer in timers and rows['Triggers'][timer].split(',')[0] == actor,
                'Fundraising timer belongs to another house')
        require(rows['Events'][timer] == f'2,13,0,300,37,0,{finished}',
                'Fundraising interval or run-end gate changed')
        tags = [value.split(',')[0] for value in rows['Tags'].values() if value.split(',')[2] == timer]
        require(tags == ['2'], 'Fundraising timer is not repeating')
        _, actions = parse_action_groups(rows['Actions'][timer])
        require(len(actions) == 1 and actions[0][0] == '33'
                and registered[int(actions[0][2])] == power,
                'Fundraising must grant one one-shot deposit per interval')
        row = effective[power]
        require(power in preloads['rules'] and row['SW.RequiredHouses'] == actor,
                'Fundraising power is missing or not isolated')
        require(0 < int(row['Money.Amount']) == expected[actor] * 1000 <= 4000,
                'Fundraising payout exceeds the purchased rank or cap')
        require(row['SW.AutoFire'] == 'yes' and row['SW.InitialReady'] == 'yes'
                and row['SW.ManualFire'] == 'no' and row['SW.ShowCameo'] == 'no'
                and row['SW.AITargeting'] == 'Base' and row['IsPowered'] == 'no'
                and row.get('SW.AlwaysGranted', 'no') == 'no',
                'Fundraising requires interaction, power, targets or has a second timer')
        require(row['Type'] == 'GenericWarhead' and row['SW.Damage'] == '0'
                and effective[row['SW.Warhead']]['AnimList'] == 'none',
                'Fundraising has physical effects')
        require(not any(effective[kind].get(field) == power
                        for kind in effective['BuildingTypes'].values()
                        for field in ('SuperWeapon', 'SuperWeapon2')),
                'Fundraising added an unnecessary building provider')
