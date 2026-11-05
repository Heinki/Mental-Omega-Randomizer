"""Frozen Grid access contract shared by world generation and launcher.

Currency is delivered as one shuffled progression supply item, worth the sum
of all non-start prices. Once received, every optional and mandatory purchase
is affordable in aggregate. Thus AP's monotone item state never models mutually
exclusive spends, and arbitrary optional spending cannot strand progression.
"""

from collections import Counter
from copy import deepcopy
from hashlib import sha256
import random

from randomizer.progression.grid import required_goals, starting_nodes, normalize_required_count, neighbors

GRID_CONTRACT_VERSION = 2
KEY_NAMESPACE = 0x601000000000
CURRENCY_ITEM = 'Mission Key Supply'
UNLOCK_MODES = ('Standard', 'Key Currency', 'Mission-Specific Keys')


def mission_key_name(code):
    return f'{code} Mission Key'


def key_item_table(codes):
    table = {mission_key_name(code): KEY_NAMESPACE + int.from_bytes(
        sha256(code.encode('utf-8')).digest()[:4], 'big') for code in codes}
    table[CURRENCY_ITEM] = KEY_NAMESPACE + 0x100000000
    if len(set(table.values())) != len(table):
        raise ValueError('Mission key ID collision; catalogue cannot be packaged.')
    return table


def local_victory_table(missions, game_name):
    """New DTA markers use code-derived IDs independent of catalogue ordering."""
    return {code: {
        'item_name': f'{game_name} Local Victory: {code}',
        'item_id': KEY_NAMESPACE + 0x200000000 + int.from_bytes(
            sha256(code.encode('utf-8')).digest()[:4], 'big'),
        'location_name': f'{mission["title"]} [{code}] - Local Victory',
        'location_id': KEY_NAMESPACE + 0x200000000 + int.from_bytes(
            sha256(code.encode('utf-8')).digest()[:4], 'big'),
    } for code, mission in missions.items()}


def configure_grid_access(manifest, settings):
    """World-generation-only allocation against real reward-location capacity."""
    if manifest['progression_mode'] != 'Grid Mode':
        return manifest
    grid = manifest['grid']
    if 'required_goals' not in grid:
        return manifest  # Legacy exports retain their original contract.
    codes = manifest['mission_order']
    starts = starting_nodes(grid)
    mode = settings.get('mission_unlock_mode', 'Standard')
    if mode not in UNLOCK_MODES:
        raise ValueError(f'Invalid Mission Unlock Mode: {mode!r}.')
    table = key_item_table(codes)
    remaining = [code for code in codes if code not in starts]
    protected = grid['goal'] if grid['goal'] not in starts else None
    requested = settings.get('minimum_completed_missions_before_final_unlock', 'Auto') if mode == 'Key Currency' else 'Auto'
    if str(requested).strip().lower() == 'auto':
        minimum = min(len(codes) - 1, max(0, len(codes) * 3 // 8))
    elif type(requested) is int or (isinstance(requested, str) and requested.isdecimal()):
        minimum = int(requested)
        if not 0 <= minimum < len(codes):
            raise ValueError(f'Minimum Completed Missions must be 0..{len(codes)-1} or Auto.')
    else:
        raise ValueError('Minimum Completed Missions must be a nonnegative integer or Auto.')
    rng = random.Random(f'{manifest["randomizer_seed"]}:grid-key-prices:v1')
    prices = {code: (0 if code in starts else rng.randint(1, 4)) for code in codes}
    supply = sum(prices.values()) if mode == 'Key Currency' else 0
    keys = {code: mission_key_name(code) for code in remaining} if mode == 'Mission-Specific Keys' else {}
    additions = Counter(keys.values())
    if supply:
        additions[CURRENCY_ITEM] = 1
    pool = Counter(manifest['item_pool'])
    # Preserve the exact number and identity of real checks. New progression
    # items replace deterministic reward slots, never local-victory markers.
    if sum(additions.values()) > sum(pool.values()):
        raise ValueError('Not enough real AP reward checks for the selected mission keys; increase rewards per objective.')
    count = sum(additions.values())
    for name in sorted(pool):
        removed = min(count, pool[name])
        pool[name] -= removed
        count -= removed
        if not count:
            break
    pool += additions
    manifest['item_pool'] = dict(sorted(pool.items()))
    # Opening reward locks can consume all starting locations. Let normal AP
    # fill place the new progression items, including in another player's world.
    if mode != 'Standard':
        manifest['local_placements'] = []
        if not any(manifest['locations'].get(code) for code in starts):
            raise ValueError('Key modes require a starting mission with real AP reward checks.')
    access = {
        'version': GRID_CONTRACT_VERSION,
        'mode': mode,
        'starting_missions': starts,
        'prices': prices if mode == 'Key Currency' else {},
        'starting_keys': 0,
        'supply': supply,
        'currency_item': CURRENCY_ITEM if supply else None,
        'currency_item_value': supply,
        'mission_keys': keys,
        'item_ids': {name: table[name] for name in additions},
        'protected_mission': protected if mode == 'Key Currency' else None,
        'minimum_completed_missions': minimum if mode == 'Key Currency' and protected else 0,
        'economy': 'whole_board_supply_v1' if mode == 'Key Currency' else None,
        'real_reward_locations': sum(sum(checks.values()) for checks in manifest['locations'].values()),
    }
    manifest['grid_contract'] = GRID_CONTRACT_VERSION
    manifest['grid_access'] = access
    manifest['state_snapshot']['grid_access'] = deepcopy(access)
    # Client and AP both use the same signed exact objective list.
    manifest['state_snapshot']['grid'] = deepcopy(grid)
    validate_grid_contract(manifest)
    return manifest


def validate_grid_contract(manifest):
    """Reject mismatched new-format clients, snapshots, objectives and economies."""
    if manifest.get('grid_contract') is None:
        if manifest.get('grid_access') is not None or (manifest.get('grid') or {}).get('required_goals') is not None:
            raise ValueError('New Grid data requires Grid contract version 2 and slot-data version 8.')
        return
    if manifest.get('grid_contract') != GRID_CONTRACT_VERSION or manifest.get('progression_mode') != 'Grid Mode':
        raise ValueError('Unsupported Grid contract. Install matching launcher and APWorld.')
    grid = manifest['grid']
    codes = manifest['mission_order']
    if set(grid.get('nodes', {})) != set(codes):
        raise ValueError('Grid access mission identities do not match the board.')
    goals = required_goals(grid)
    if len(goals) != normalize_required_count(grid.get('required_victory_missions', 1), len(codes)):
        raise ValueError('Grid required victory count differs from its objective set.')
    if grid.get('required_victory_missions', 1) == 1 and goals != [grid.get('goal')]:
        raise ValueError('Single-goal Grid must retain its legacy bottom-right objective.')
    positions = [(node.get('x'), node.get('y')) for node in grid['nodes'].values()]
    if len(set(positions)) != len(codes) or any(type(x) is not int or type(y) is not int or x < 0 or y < 0 for x, y in positions):
        raise ValueError('Grid contains invalid or duplicate mission positions.')
    reachable = set(starting_nodes(grid))
    pending = list(reachable)
    while pending:
        for neighbor in neighbors(grid, pending.pop()):
            if neighbor not in reachable:
                reachable.add(neighbor)
                pending.append(neighbor)
    if reachable != set(codes):
        raise ValueError('Grid objectives must be reachable from a playable starting mission.')
    if manifest.get('goal', {}).get('mission_codes') != goals:
        raise ValueError('Grid victory objective sets disagree.')
    if grid.get('goal') not in codes:
        raise ValueError('Grid legacy endgame mission is invalid.')
    access = manifest.get('grid_access')
    if not isinstance(access, dict) or access.get('version') != GRID_CONTRACT_VERSION or access.get('mode') not in UNLOCK_MODES:
        raise ValueError('Invalid frozen Grid access rules.')
    snapshot = manifest.get('state_snapshot', {})
    if snapshot.get('completed_missions') or snapshot.get('started_missions'):
        raise ValueError('Generated Grid snapshots cannot contain gameplay victories.')
    if snapshot.get('grid_access') != access or snapshot.get('grid') != grid:
        raise ValueError('Grid access snapshot differs from the authoritative manifest.')
    starts = starting_nodes(grid)
    if not starts or access.get('starting_missions') != starts:
        raise ValueError('Grid access has invalid starting missions.')
    remaining = set(codes) - set(starts)
    mode = access['mode']
    expected_keys = {code: mission_key_name(code) for code in codes if code in remaining} if mode == 'Mission-Specific Keys' else {}
    if access.get('mission_keys') != expected_keys:
        raise ValueError('Mission-specific keys do not match exact mission identities.')
    prices = access.get('prices')
    if mode == 'Key Currency':
        if (not isinstance(prices, dict) or set(prices) != set(codes)
                or any(type(price) is not int or price < 0 or (code in remaining and price == 0)
                       or (code in starts and price != 0) for code, price in prices.items())):
            raise ValueError('Invalid frozen mission prices.')
        supply = sum(prices.values())
        protected = grid['goal'] if grid['goal'] not in starts else None
        minimum = access.get('minimum_completed_missions')
        if (access.get('supply') != supply or access.get('currency_item_value') != supply
                or access.get('starting_keys') != 0 or access.get('economy') != 'whole_board_supply_v1'
                or access.get('currency_item') != (CURRENCY_ITEM if supply else None)
                or access.get('protected_mission') != protected or type(minimum) is not int
                or not 0 <= minimum < len(codes) or (protected is None and minimum != 0)):
            raise ValueError('Unsafe or inconsistent frozen Grid key economy.')
        expected_items = {CURRENCY_ITEM: 1} if supply else {}
    else:
        if (prices != {} or access.get('supply') != 0 or access.get('minimum_completed_missions') != 0
                or access.get('protected_mission') is not None or access.get('currency_item') is not None
                or access.get('currency_item_value') != 0 or access.get('starting_keys') != 0):
            raise ValueError('Non-currency Grid cannot contain currency gates.')
        expected_items = dict(Counter(expected_keys.values()))
    table = key_item_table(codes)
    if access.get('item_ids') != {name: table[name] for name in expected_items}:
        raise ValueError('Frozen mission key IDs are incompatible.')
    pool = manifest.get('item_pool', {})
    known_keys = set(table)
    if {name: count for name, count in pool.items() if name in known_keys} != expected_items:
        raise ValueError('Grid key supply does not match the actual AP item pool.')
    capacity = sum(sum(checks.values()) for checks in manifest['locations'].values())
    if access.get('real_reward_locations') != capacity or sum(pool.values()) != capacity:
        raise ValueError('Grid economy capacity differs from real reward checks.')
    if mode != 'Standard' and (manifest.get('local_placements') or not any(manifest['locations'].get(code) for code in starts)):
        raise ValueError('Grid key placement has no usable opening checks.')


def access_projection(access, ap_state, completed_codes):
    """Project immutable AP receipts separately from the purchase ledger."""
    received_ids = {int(item['item']) for item in ap_state.get('checkpoint', {}).get('received_items', ())}
    received_names = {name for name, item_id in access['item_ids'].items() if item_id in received_ids}
    received = access['currency_item_value'] if CURRENCY_ITEM in received_names else 0
    purchases = ap_state.get('mission_purchases', {})
    if not isinstance(purchases, dict) or any(
            code not in access['prices'] or type(cost) is not int or cost != access['prices'][code] or cost <= 0
            for code, cost in purchases.items()):
        raise ValueError('Saved mission purchase ledger is invalid.')
    spent = sum(purchases.values())
    balance = received + access['starting_keys'] - spent
    if balance < 0:
        raise ValueError('Saved mission purchases exceed server-received keys; reconnect to synchronize items.')
    completed = set(completed_codes) & (set(access['starting_missions']) | set(access['prices']) | set(access['mission_keys']))
    unlocked = set(access['starting_missions'])
    if access['mode'] == 'Mission-Specific Keys':
        unlocked.update(code for code, name in access['mission_keys'].items() if name in received_names)
    elif access['mode'] == 'Key Currency':
        unlocked.update(purchases)
    return {'received': received, 'spent': spent, 'available': balance,
            'unlocked': unlocked, 'completed': completed, 'received_names': received_names}


def purchase_blocker(access, projection, code):
    if access['mode'] != 'Key Currency':
        return 'Mission access cannot be purchased in this unlock mode.'
    if code in projection['unlocked']:
        return ''
    if code not in access['prices']:
        return 'Mission is not part of this generated Grid.'
    if code == access['protected_mission']:
        missing = access['minimum_completed_missions'] - len(projection['completed'] - {code})
        if missing > 0:
            return f'Complete {missing} more missions before purchasing this protected objective.'
    missing = access['prices'][code] - projection['available']
    return f'Missing {missing} Mission Keys.' if missing > 0 else ''
