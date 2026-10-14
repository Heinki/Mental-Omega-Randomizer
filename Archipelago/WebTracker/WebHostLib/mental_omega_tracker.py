"""Mental Omega's website-only cameo tracker; no launcher or world imports."""

from functools import lru_cache
import json
from pathlib import Path

GAME = 'Mental Omega'
FACTIONS = ('Allies', 'Soviets', 'Epsilon', 'Foehn', 'Neutral', 'Global')


@lru_cache(maxsize=1)
def presentation_data():
    return json.loads(Path(__file__).with_name('mental_omega_tracker_data.json').read_text(encoding='utf-8'))


def tracker_view(slot, inventory, locations, checked, item_names, location_names, data):
    """Combine public AP inventory with exported launcher presentation data."""
    manifest = slot.get('run_manifest') or {}
    settings = manifest.get('frozen_settings') or {}
    used = set(manifest.get('item_pool', {})) | set(manifest.get('starting_items', {}))
    if not used:
        used = set((slot.get('items') or {}).values())
    received = {str(identity) for identity, count in inventory.items() if count > 0}
    wanted = {identity for identity, item in data['items'].items() if not used or item['name'] in used}
    wanted |= received & data['items'].keys()
    baseline = set(settings.get('starting_unit_ids') or ()) | set(settings.get('starting_defense_ids') or ())
    grouped = {faction: [] for faction in FACTIONS}
    for key, entity in data['entities'].items():
        identities = [str(identity) for identity in entity['items'] if str(identity) in wanted]
        starting = key.startswith('unit:') and key[5:] in baseline
        if not identities and not starting:
            continue
        rows = []
        for identity in identities:
            item = data['items'][identity]
            count = inventory.get(int(identity), 0)
            level = min(count, item['maximum'])
            rows.append({**item, 'count': count, 'level': level,
                         'effects': item['effects'][level] if count else [],
                         'next_effects': item['effects'][min(level + 1, item['maximum'])] if item['buff'] else [],
                         'identity': identity})
        rows.sort(key=lambda row: (row['buff'], row['name'].casefold()))
        access = starting or entity.get('always_available', False) or any(row['count'] and not row['buff'] for row in rows)
        has_items = any(row['count'] for row in rows)
        status = ('Tracked bonus received' if key.startswith('global:') and has_items
                  else 'Starting access' if starting or entity.get('always_available', False)
                  else 'Access received' if access
                  else 'Buffs received; access not received' if has_items
                  else 'Not received')
        combined = []
        health = next((row for row in rows if row['buff_type'] == 'health' and row['count']), None)
        armor = next((row for row in rows if row['buff_type'] == 'armor' and row['count']), None)
        if health and armor and entity.get('strength'):
            base = max(1, int(round(entity['strength'])))
            strength = int(round(base * data['health_multipliers'][health['level']]))
            effective = max(1, int(round(strength / data['armor_multipliers'][armor['level']])))
            combined = [f'Health + armor: {effective:,} effective HP [{base:,} base]']
        card = {**entity, 'key': key, 'rows': rows, 'status': status,
                'active': access or (key.startswith('global:') and has_items),
                'has_items': has_items or starting or entity.get('always_available', False),
                'count': sum(row['count'] for row in rows), 'combined': combined}
        card['search'] = ' '.join([card['label'], card['faction'], card['category'],
                                   *(row['name'] + ' ' + row['description'] for row in rows)]).casefold()
        grouped.setdefault(entity['faction'], []).append(card)

    # Keep obsolete/unknown received rewards visible when tracking older rooms.
    logic_items = {entry['item'] for entry in (slot.get('local_victories') or {}).values()}
    logic_items.update(entry['logic_item'] for entry in (slot.get('shop') or {}).get('stage_victories', []))
    unknown = [{'name': item_names.get(int(identity), f'Item {identity}'), 'count': inventory[int(identity)]}
               for identity in sorted(received - data['items'].keys(), key=int)
               if int(identity) not in logic_items]
    logic_locations = {entry['location'] for entry in (slot.get('local_victories') or {}).values()}
    logic_locations.update(entry['logic_location'] for entry in (slot.get('shop') or {}).get('stage_victories', []))
    # Use slot mappings, not assumed ID ranges, to hide local victory markers.
    mission_by_location = {int(identity): code for code, checks in (slot.get('locations') or {}).items()
                           for identities in checks.values() for identity in identities}
    mission_groups = {}
    for identity in locations:
        if identity in logic_locations:
            continue
        name = location_names.get(identity, f'Location {identity}')
        code = mission_by_location.get(identity)
        group = code or (name.split(' - ', 1)[0] if ' - ' in name else 'Shop / Other checks')
        mission_groups.setdefault(group, []).append({'name': name, 'checked': identity in checked})
    order = {code: index for index, code in enumerate(slot.get('mission_order') or ())}
    missions = [{'code': code, 'rows': rows, 'checked': sum(row['checked'] for row in rows), 'total': len(rows)}
                for code, rows in sorted(mission_groups.items(), key=lambda pair: (order.get(pair[0], len(order)), pair[0]))]
    sections = [{'faction': faction, 'cards': sorted(cards, key=lambda card: (card['category'], card['label'].casefold()))}
                for faction, cards in grouped.items() if cards]
    reward_total = sum(count for identity, count in inventory.items() if str(identity) in data['items'])
    return {'sections': sections, 'missions': missions, 'unknown_items': unknown,
            'reward_total': reward_total, 'checked_total': sum(mission['checked'] for mission in missions),
            'location_total': sum(mission['total'] for mission in missions)}


def render_mental_omega_tracker(tracker_data, team, player):
    from flask import render_template

    slot = tracker_data.get_slot_data(player)
    view = tracker_view(slot, tracker_data.get_player_inventory_counts(team, player),
                        tracker_data.get_player_locations(player),
                        tracker_data.get_player_checked_locations(team, player),
                        tracker_data.item_id_to_name[GAME], tracker_data.location_id_to_name[GAME],
                        presentation_data())
    return render_template('tracker__MentalOmega.html', **view, room=tracker_data.room,
                           team=team, player=player,
                           player_name=tracker_data.get_room_long_player_names()[team, player],
                           saving_second=tracker_data.get_room_saving_second(),
                           game_finished=tracker_data.get_player_client_status(team, player) == 30,
                           progression_mode=slot.get('progression_mode', 'Campaign'))
