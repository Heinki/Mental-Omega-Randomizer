"""Mission-safe enemy-house scaling and AI power reward preparation."""

from randomizer.rewards.enemy_scaling import enemy_effect_values

from ._shared import (
    all_section_value_maps,
    build_unit_usage_index,
    canonical_house_name,
    map_house_records,
    player_controlled_houses,
    scripted_enemy_house_pairs,
    section_value_map_preserve,
    unique_in_order,
    unsafe_country_houses,
)
from .houses import country_family, is_buffable_helper_house
from .ownership import player_transfer_houses
from .base import format_multiplier, parse_float


def discover_hostile_ai_houses(lines):
    """Find active military AI Houses outside every player coalition."""
    sections = all_section_value_maps(lines)
    records = map_house_records(lines, sections=sections)
    players = player_controlled_houses(lines, records=records)
    coalition = {house.lower() for house in players}

    # Treat alliance links as undirected and transitively close them. Campaign
    # maps often list an alliance on only one side, or through a helper House.
    changed = True
    while changed:
        changed = False
        for house, record in records.items():
            house_lower = house.lower()
            allies = {
                canonical.lower()
                for ally in record.get('allies', ())
                if (canonical := canonical_house_name(records, ally))
            }
            linked = bool(allies.intersection(coalition)) or any(
                house_lower in {
                    canonical.lower()
                    for ally in records.get(member, {}).get('allies', ())
                    if (canonical := canonical_house_name(records, ally))
                }
                for member in records
                if member.lower() in coalition
            )
            if linked and house_lower not in coalition:
                coalition.add(house_lower)
                changed = True

    transfers = {
        house.lower()
        for house in player_transfer_houses(lines, records=records)
    }
    usage_index = build_unit_usage_index(lines)
    used_houses = set()
    for owners in usage_index.values():
        for owner in owners:
            canonical = canonical_house_name(records, owner)
            if canonical:
                used_houses.add(canonical.lower())

    hostile = []
    skipped = {}
    for house, record in records.items():
        house_lower = house.lower()
        reason = ''
        if record.get('player') or house_lower in coalition:
            reason = 'player-controlled or allied coalition'
        elif house_lower in transfers:
            reason = 'scripted to transfer to player coalition'
        elif not is_buffable_helper_house(record) or not country_family(record):
            reason = 'neutral, civilian, special, or noncombat House'
        elif house_lower not in used_houses:
            reason = 'no placed or scripted military consumer'
        if reason:
            skipped[house] = reason
        else:
            hostile.append(house)
    return unique_in_order(hostile), skipped


def active_hostile_enemy_houses(lines, configured_enemy_houses):
    """Reject human-controlled or currently allied phase houses."""
    records = map_house_records(lines)
    players = set(player_controlled_houses(lines, records=records))
    player_lower = {house.lower() for house in players}
    active = []
    skipped = []
    for house in configured_enemy_houses or ():
        record = records.get(house)
        if not record or record.get('player'):
            skipped.append(house)
            continue
        allies = {
            canonical.lower()
            for ally in record.get('allies', ())
            if (canonical := canonical_house_name(records, ally))
        }
        player_allies = any(
            house.lower() in {
                canonical.lower()
                for ally in records.get(player, {}).get('allies', ())
                if (canonical := canonical_house_name(records, ally))
            }
            for player in players
        )
        if allies.intersection(player_lower) or player_allies:
            skipped.append(house)
            continue
        active.append(house)
    return unique_in_order(active), unique_in_order(skipped)


def _effect_counts(rewards):
    raw_counts = {}
    maximums = {}
    definitions = {}
    for reward in rewards or ():
        if not reward.get('enemy_reward'):
            continue
        effect_id = str(reward.get('enemy_effect_id') or '')
        if not effect_id:
            continue
        maximum = max(1, int(reward.get('enemy_maximum', 1)))
        raw_counts[effect_id] = raw_counts.get(effect_id, 0) + 1
        if maximum >= maximums.get(effect_id, 0):
            maximums[effect_id] = maximum
            definitions[effect_id] = reward
    counts = {
        effect_id: min(count, maximums[effect_id])
        for effect_id, count in raw_counts.items()
    }
    return counts, definitions


def enemy_country_buff_rules(lines, enemy_houses, rewards):
    """Apply country multipliers only when no non-target house inherits them."""
    counts, definitions = _effect_counts(rewards)
    stat_effects = [
        (definitions[effect_id], count)
        for effect_id, count in counts.items()
        if definitions[effect_id].get('enemy_effect')
        in {'armor', 'production'}
    ]
    if not enemy_houses or not stat_effects:
        return {}, [], [], []
    sections = all_section_value_maps(lines)
    records = map_house_records(lines, sections=sections)
    usage_index = build_unit_usage_index(lines)
    scripted_enemies = scripted_enemy_house_pairs(lines, records=records)
    countries = unique_in_order(
        records.get(house, {}).get('country')
        or house.replace(' House', '')
        for house in enemy_houses
    )
    rules = {}
    applied = []
    skipped = []
    applications = []
    section_counts = {}
    for line in lines:
        stripped = str(line).strip()
        if stripped.startswith('[') and stripped.endswith(']'):
            section = stripped[1:-1].strip().lower()
            section_counts[section] = section_counts.get(section, 0) + 1
    for country in countries:
        if section_counts.get(country.lower(), 0) > 1:
            skipped.append((country, ['duplicate CountryType sections']))
            continue
        unsafe = unsafe_country_houses(
            lines,
            country,
            enemy_houses,
            records=records,
            sections=sections,
            usage_index=usage_index,
            scripted_enemies=scripted_enemies,
        )
        if unsafe:
            skipped.append((country, unsafe))
            continue
        base_values = section_value_map_preserve(lines, country)
        values = {}
        for reward, count in stat_effects:
            effect = reward['enemy_effect']
            suffix = reward['enemy_country_suffix']
            prefix = {
                'armor': 'Armor',
                'production': 'BuildTime',
            }[effect]
            key = f'{prefix}{suffix}Mult'
            existing_key = next(
                (name for name in base_values if name.lower() == key.lower()),
                key,
            )
            base = parse_float(base_values.get(existing_key), 1.0)
            effect_values = enemy_effect_values(reward, count, base)
            values[key] = format_multiplier(
                effect_values['final_engine_value']
            )
            applications.append({
                'effect_id': reward['enemy_effect_id'],
                'effect': effect,
                'category': reward.get('enemy_category', 'forces'),
                'country': country,
                'engine_field': existing_key,
                **effect_values,
            })
        if values:
            rules[country] = values
            applied.append(country)
    return rules, applied, skipped, applications


def enemy_power_launch_rewards(rewards):
    """Convert earned enemy power entries into AI-only clone inputs."""
    launch = []
    seen = set()
    for reward in rewards or ():
        if (
            not reward.get('enemy_reward')
            or reward.get('enemy_effect') != 'power'
            or not reward.get('superweapon')
        ):
            continue
        power_id = str(reward['superweapon']).upper()
        if power_id in seen:
            continue
        seen.add(power_id)
        converted = dict(reward)
        converted['kind'] = 'superweapon'
        converted['superweapon_clone'] = reward['enemy_superweapon_clone']
        values = dict(reward.get('superweapon_rules') or {})
        values.update({
            'SW.AllowAI': 'yes',
            'SW.AllowPlayer': 'no',
            'SW.AITargeting': reward['enemy_ai_targeting'],
            'SW.AITargeting.Constraints': reward.get(
                'enemy_ai_targeting_constraints', 'none'
            ),
            'SW.ShowCameo': 'no',
            'SW.ManualFire': 'no',
            'SW.UseAITargeting': 'no',
        })
        converted['superweapon_rules'] = values
        converted['_runtime_canonical'] = True
        launch.append(converted)
    return launch
