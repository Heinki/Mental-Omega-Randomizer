"""Describe each cumulative rank using the selected faction's real grants."""

from collections import Counter

from randomizer.rewards.catalogue import BUFF_TARGETS
from randomizer.ui.cameos import installed_rules_registry

from .perks import ranks


def rank_descriptions(perk, country):
    _, rules = installed_rules_registry()

    def name(kind, count=1):
        power_names = {'ChronoSphereSpecial': 'Chronosphere', 'IronCurtainSpecial': 'Iron Curtain',
                       'RageInductorSpecial': 'Rage Inductor', 'NukeSpecial': 'Tactical Nuke',
                       'PsychicDominatorSpecial': 'Psychic Dominator'}
        if kind in power_names:
            return power_names[kind]
        entry = BUFF_TARGETS.get(kind, {})
        label = entry.get('label' if count == 1 else 'plural')
        if label:
            return label
        label = rules.get(kind, {}).get('Name', kind)
        return label + 's' if count != 1 and not label.lower().endswith('s') else label

    def units(entries):
        amounts = Counter()
        for entry in entries:
            amounts[entry['type']] += entry['count']
        return ', '.join(f'{count} {name(kind, count)}' for kind, count in amounts.items())

    def buildings(entries):
        return units([{'type': kind, 'count': 1} for kind in entries])

    descriptions = []
    for index, rank in enumerate(ranks(perk), 1):
        effect = rank['effects']
        parts = []
        if effect.get('defense_health_percent'):
            parts.append(f'+{effect["defense_health_percent"]}% maximum health for starting, '
                         'produced and recovered-outpost defenses; stacks with defense veterancy and firepower')
        if effect.get('camp_salvage_credits'):
            parts.append(f'+{effect["camp_salvage_credits"]:,} credits per collected camp alongside its normal reward. '
                         'The collecting human receives the credits; AI collections use the host')
        if effect.get('camp_veterancy'):
            parts.append('All camp-awarded mobile units arrive '
                         + ('Veteran' if effect['camp_veterancy'] == 1 else 'Elite (highest veterancy)'))
        if effect.get('camp_reward_units_by_country'):
            table = effect['camp_reward_units_by_country']
            parts.append('Ordinary Tier 1/2 camp unit rewards become '
                         + (units(table[country]) if country else
                            f'{sum(unit["count"] for unit in next(iter(table.values())))} mixed faction units')
                         + '; credit and special-unit rolls remain. Combines with Salvage and Veteran Spoils')
        if effect.get('reinforcement_interval_reduction_seconds'):
            interval = 300 - effect['reinforcement_interval_reduction_seconds']
            parts.append(f'Periodic reinforcements every {interval // 60}:{interval % 60:02d}, '
                         'including the first delivery. Requires Periodic reinforcements; '
                         'the shared living-unit cap and capacity wait remain')
        if effect.get('outpost_rank'):
            additions = ('powered barracks and two basic defenses', 'refinery with harvester',
                         'radar and anti-air defenses', 'war factory and advanced defenses',
                         'second refinery/factory and more defenses', 'construction yard and up to 12 defenses')
            parts.append('Collected camps deploy cumulative faction outposts: '
                         + '; '.join(additions[:effect['outpost_rank']])
                         + '. All ranks include enough power. Collecting humans own their outpost; '
                         'AI collections use the host. Foundations are reserved until collection; '
                         'blocking units are moved aside and ore under buildings is cleared during native creation. '
                         'Tight terrain can reduce the outpost. Structures cannot be sold')
        if effect.get('factory_training_percent'):
            parts.append(f'Barracks and land war factories train eligible units with '
                         f'{effect["factory_training_percent"]}% progress toward Veteran. '
                         'Rank 3 starts Veteran; stronger academy bonuses remain. '
                         'Airfield aircraft, naval units and nontrainable units are excluded')
        if effect.get('mobility_stacks'):
            from randomizer.rewards.definitions import MOVEMENT_SPEED_SAFE_CEILINGS
            caps = MOVEMENT_SPEED_SAFE_CEILINGS
            parts.append(f'{effect["mobility_stacks"]} existing Mobility stacks for catalogue-eligible mobile units. '
                         f'Reviewed Speed caps: infantry {caps["infantry"]}, vehicles {caps["units"]}, '
                         f'aircraft {caps["aircraft"]}. Faster native types are not accelerated; '
                         'jumpjet movement stays aligned with Speed')
        if effect.get('lab_health_percent'):
            percent = effect['lab_health_percent']
            base = int(rules['CALAB']['Strength'])
            health = base * (100 + percent) // 100
            parts.append(f"+{percent}% maximum health for Einstein's Lab ({health:,} HP from {base:,}). "
                         'Starts at full health; emergency repair restores the upgraded maximum. '
                         'One shared objective bonus in co-op')
        if effect.get('lab_emergency_repair'):
            parts.append("Automatically restore Einstein's Lab to full health once per run when it "
                         'falls below the native red-health threshold (35% in Mental Omega). '
                         'The whole coalition shares one repair')
        if effect.get('lab_reserve_units_by_country'):
            table = effect['lab_reserve_units_by_country']
            parts.append((units(table[country]) if country else
                          f'{sum(unit["count"] for unit in next(iter(table.values())))} faction units')
                         + ' per friendly house once per run when the Lab falls below 50% health. '
                         'Arrivals use reserved base tiles; human squads remain controllable. '
                         'This is a separate one-time reserve, outside the periodic reinforcement cap')
            if effect.get('lab_reserve_shield_seconds'):
                parts.append(f'The same activation immediately protects only the Lab with Iron Curtain '
                             f'for {effect["lab_reserve_shield_seconds"]} in-game seconds while squads arrive')
            level = effect.get('lab_reserve_veterancy', 0)
            if level:
                parts.append('Reserve units arrive ' + ('Veteran' if level == 1 else 'Elite (highest veterancy)'))
        if effect.get('starting_credits'):
            parts.append(f'+{effect["starting_credits"]:,} starting credits')
        if effect.get('production_percent'):
            parts.append(f'{effect["production_percent"]}% shorter infantry, vehicle/naval, aircraft, '
                         'building and defense production time')
        if effect.get('construction_discount_percent'):
            parts.append(f'{effect["construction_discount_percent"]}% lower cost for all buildings and defenses')
        if effect.get('unit_discount_percent'):
            parts.append(f'{effect["unit_discount_percent"]}% lower infantry, vehicle/naval and aircraft costs')
        if effect.get('special_building_limit_stacks'):
            parts.append(f'+{effect["special_building_limit_stacks"]} to supported special-building and capped-defense limits; '
                         'normal technology and ownership requirements remain')
        if effect.get('transport_capacity_stacks'):
            parts.append(f'+{effect["transport_capacity_stacks"]} passenger slots on catalogue-eligible transports; '
                         'gunner vehicles, Chrono Prison and sealed weapon payloads are excluded. '
                         'Does not add initial passengers or unlock units')
        if effect.get('infrastructure_health_percent'):
            parts.append(f'+{effect["infrastructure_health_percent"]}% health for starting and future friendly '
                         'production and economy buildings: Construction Yards, barracks, factories, '
                         'airfields, shipyards, refineries, generators, grinders and special economy buildings. '
                         'Normal access requirements remain; defenses, tech/support buildings and the Lab are unchanged')
        if effect.get('open_topped'):
            from .utilities import supported_pairs
            eligible = sorted(kind for kind, buff in supported_pairs() if buff == 'open_topped')
            parts.append('Passenger firing enabled on catalogue-reviewed transports only: '
                         + ', '.join(name(kind) for kind in eligible)
                         + '. Gunner vehicles, Stallion and Chrono Prison are excluded; '
                         'existing open-topped units retain their behavior. Does not unlock units')
        if effect.get('fundraising_stacks'):
            parts.append(f'{effect["fundraising_stacks"] * 1000:,} credits deposited automatically every '
                         '300 in-game seconds, first payment at 5 minutes. Each human uses their own '
                         'enabled Fundraising rank; AI helpers share the host rank. No collection required')
        if effect.get('starting_units'):
            parts.append(units(effect['starting_units']))
        if effect.get('starting_units_by_country'):
            entries = effect['starting_units_by_country']
            parts.append(units(entries[country]) if country else
                         f'{sum(unit["count"] for unit in next(iter(entries.values())))} starting faction units')
        for field, label in (('buildings_by_country', 'starting faction buildings'),
                             ('defenses_by_country', 'starting faction defenses'),
                             ('power_buildings_by_country', 'power plants to cover starting demand')):
            if field == 'power_buildings_by_country' and 'buildings_by_country' in effect:
                continue
            if field in effect:
                if country:
                    entries = list(effect[field][country])
                    if field == 'buildings_by_country':
                        entries.extend(effect.get('power_buildings_by_country', {}).get(country, []))
                    if entries:
                        parts.append(buildings(entries))
                elif any(effect[field].values()):
                    parts.append(label)
        if effect.get('harvesters_by_country'):
            parts.append(units(effect['harvesters_by_country'][country]) if country else '1 faction harvester')
        if effect.get('veterancy'):
            level = 'Veteran' if effect['veterancy'] == 1 else 'Elite'
            text = f'All units granted by Starting army begin {level}'
            if effect['veterancy'] == 2:
                text += ' (highest veterancy)'
            fallback = effect.get('fallback_units_by_country', {})
            if fallback:
                text += '. Without Starting army: ' + (
                    units(fallback[country]) if country else '2 faction infantry') + f' instead, also {level}'
            parts.append(text)
        if effect.get('defense_veterancy'):
            parts.append('Starting and newly built defenses begin veteran')
        if effect.get('defense_percent'):
            parts.append(f'+{effect["defense_percent"]}% defense damage, fire rate and range')
        for tier, percent in effect.get('tier_buffs', {}).items():
            parts.append(f'+{percent}% Tier {tier} unit health, damage and fire rate')
        for field, label in (('support_powers_by_country', 'Support powers'),
                             ('superweapons_by_country', 'Superweapons')):
            if effect.get(field):
                powers = effect[field]
                parts.append(label + ': ' + (', '.join(name(kind) for kind in powers[country]) if country
                                            else f'{len(next(iter(powers.values())))} faction powers'))
        if effect.get('power_upgrade_stacks'):
            from .powers import upgrade_description
            parts.append(upgrade_description(effect['power_upgrade_stacks']))
        if effect.get('healing_stacks'):
            parts.append(f'Eligible units and defenses automatically heal {effect["healing_stacks"]}% '
                         'of maximum HP per native healing tick, including rookie units; '
                         'existing stronger healing is retained')
        if effect.get('recon_stacks'):
            parts.append(f'+{effect["recon_stacks"]} sight for eligible units/defenses; '
                         'supported types detect nearby cloaked units. Existing longer sensor ranges remain')
        if effect.get('unique_limit_stacks'):
            parts.append(f'+{effect["unique_limit_stacks"]} to positive live-unit limits on eligible '
                         'heroes and unlocked specials; does not unlock additional unit types')
        if effect.get('income_stacks'):
            from .utilities import supported_pairs
            from randomizer.config.tuning import stacking_amount
            targets = [kind for kind in rules if (kind, 'income') in supported_pairs()
                       and float(rules[kind].get('ProduceCashAmount', '0')) > 0]
            parts.append(f'+{stacking_amount("income", effect["income_stacks"]):g} credits per existing '
                         'payout cycle on eligible special buildings: '
                         + ', '.join(f'{name(kind)} pays '
                                     f'{float(rules[kind]["ProduceCashAmount"]) + stacking_amount("income", effect["income_stacks"]):g}'
                                     for kind in targets)
                         + ' credits per cycle. Requires constructing the building; '
                         'captured native copies retain their original payout. Ore-sale percentage is unchanged')
        if effect.get('special_units_by_country'):
            table = effect['special_units_by_country']
            counts = [len(values) for values in table.values()]
            amount = str(min(counts)) if min(counts) == max(counts) else f'{min(counts)}–{max(counts)}'
            label = 'stolen-tech units' if perk['id'] == 'stolen_tech_access' else 'special units'
            parts.append('Production access: ' + (', '.join(name(kind) for kind in table[country])
                         if country else f'{amount} faction {label}'))
        if effect.get('reinforcements'):
            reinforcement = effect['reinforcements']
            table = reinforcement['units_by_country']
            parts.append((units(table[country]) if country else
                          f'{sum(unit["count"] for unit in next(iter(table.values())))} faction units')
                         + f' at base after {reinforcement["first_seconds"] // 60} minutes, then every '
                         f'{reinforcement["interval_seconds"] // 60} minutes; '
                         f'{reinforcement["max_active_units"]} living reinforcement units shared with helpers. '
                         'Walkable arrival tiles are reserved against construction. '
                         'Small groups wait for shared capacity; each house restarts its timer after delivery. '
                         'Each human sees a Next allied reinforcements countdown; '
                         'at zero, capacity-wait messages repeat until the arrival can finish')
            if reinforcement.get('veterancy'):
                parts.append('Every reinforcement arrives '
                             + ('Elite (highest veterancy)' if reinforcement['veterancy'] == 2 else 'Veteran'))
        if effect.get('reveal_map'):
            parts.append('Reveal the entire map at the start')
        if effect.get('allied_helpers'):
            count = effect['allied_helpers']
            parts.append(f'{count} allied skirmish AI {"helper" if count == 1 else "helpers"}, sharing enabled perks')
        if effect.get('generator_power_percent'):
            parts.append(f'+{effect["generator_power_percent"]}% power from starting and future generators '
                         'for every friendly house; power consumption is unchanged')
        if effect.get('starting_defenses'):
            parts.append(buildings([entry['type'] for entry in effect['starting_defenses']]))
        descriptions.append(f'Rank {index}: ' + '; '.join(parts or [perk['description']]))
    if not country and any(key.endswith('_by_country') for rank in ranks(perk) for key in rank['effects']):
        descriptions.insert(0, 'Choose a player faction to see exact units and buildings.')
    return '\n\n'.join(descriptions)
