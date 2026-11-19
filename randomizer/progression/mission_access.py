"""Frozen Grid access contract shared by world generation and launcher."""

from collections import Counter
from copy import deepcopy
from hashlib import sha256
import random

from randomizer.progression.grid import required_goals, starting_nodes, normalize_required_count, neighbors

GRID_CONTRACT_VERSION = 2
KEY_NAMESPACE = 0x601000000000
CURRENCY_ITEM = 'Mission Key Supply'
CURRENCY_ECONOMY = 'single_keys_v2'
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


def currency_purchase_order(codes, starts, protected):
    order = [code for code in codes if code not in starts and code != protected]
    if protected is not None:
        order.append(protected)
    return order


def currency_thresholds(access):
    """AP counts acquired keys. A fixed purchase order makes spending monotone."""
    spent = 0
    for code in access.get('purchase_order', ()):
        spent += access['prices'][code]
        yield code, spent


def _currency_check_shortfalls(access, locations):
    available = sum(sum(locations[code].values()) for code in access['starting_missions'])
    previous = access['starting_missions'][0]
    for code, threshold in currency_thresholds(access):
        if available < threshold:
            yield previous, threshold - available
            available = threshold
        previous = code
        available += sum(locations[code].values())


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
        additions[CURRENCY_ITEM] = supply
    pool = Counter(manifest['item_pool'])
    # Opening reward locks can consume all starting locations. Let normal AP
    # fill place the new progression items, including in another player's world.
    if mode != 'Standard':
        manifest['local_placements'] = []
    access = {
        'version': GRID_CONTRACT_VERSION,
        'mode': mode,
        'starting_missions': starts,
        'prices': prices if mode == 'Key Currency' else {},
        'starting_keys': 0,
        'supply': supply,
        'currency_item': CURRENCY_ITEM if supply else None,
        'currency_item_value': int(bool(supply)),
        'mission_keys': keys,
        'item_ids': {name: table[name] for name in additions},
        'protected_mission': protected if mode == 'Key Currency' else None,
        'minimum_completed_missions': minimum if mode == 'Key Currency' and protected else 0,
        'economy': CURRENCY_ECONOMY if mode == 'Key Currency' else None,
    }
    locations = manifest['locations']
    added_checks = 0
    if mode == 'Key Currency':
        access['purchase_order'] = currency_purchase_order(codes, starts, protected)
        # Add real victory slots when the selected draw count cannot fund the
        # next purchase in a solo room. Each shortfall is at most one price.
        for code, count in _currency_check_shortfalls(access, locations):
            checks = locations[code]
            checks['victory'] = checks.get('victory', 0) + count
            added_checks += count
    if mode != 'Standard' and not any(locations.get(code) for code in starts):
        raise ValueError('Key modes require a starting mission with real AP reward checks.')
    count = sum(additions.values()) - added_checks
    if count > sum(pool.values()):
        raise ValueError('Not enough real AP reward checks for the selected mission keys; increase rewards per objective.')
    # Prefer replacing duplicate draws. Keep unique unlocks when slots permit.
    for keep in (1, 0):
        for name in sorted(pool, key=lambda name: (-pool[name], name)):
            removed = min(count, max(0, pool[name] - keep))
            pool[name] -= removed
            count -= removed
            if not count:
                break
    pool += additions
    manifest['item_pool'] = dict(sorted(pool.items()))
    access['real_reward_locations'] = sum(sum(checks.values()) for checks in locations.values())
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
        legacy = access.get('economy') == 'whole_board_supply_v1'
        if (access.get('supply') != supply
                or access.get('currency_item_value') != (supply if legacy else int(bool(supply)))
                or access.get('starting_keys') != 0
                or access.get('economy') not in ('whole_board_supply_v1', CURRENCY_ECONOMY)
                or access.get('currency_item') != (CURRENCY_ITEM if supply else None)
                or access.get('protected_mission') != protected or type(minimum) is not int
                or not 0 <= minimum < len(codes) or (protected is None and minimum != 0)):
            raise ValueError('Unsafe or inconsistent frozen Grid key economy.')
        if not legacy and (
            access.get('purchase_order') != currency_purchase_order(codes, starts, protected)
            or any(_currency_check_shortfalls(access, manifest['locations']))
        ):
            raise ValueError('Grid key order has insufficient reachable reward checks.')
        expected_items = {CURRENCY_ITEM: 1 if legacy else supply} if supply else {}
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
    received_ids = Counter(int(item['item']) for item in ap_state.get('checkpoint', {}).get('received_items', ()))
    received_names = {name for name, item_id in access['item_ids'].items() if item_id in received_ids}
    received = min(access['supply'], access['currency_item_value'] *
                   received_ids[access['item_ids'].get(CURRENCY_ITEM)])
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
    next_code = next((mission for mission in access.get('purchase_order', ())
                      if mission not in projection['unlocked']), None)
    if next_code is not None and code != next_code:
        return f'Purchase {next_code} next to advance the Grid.'
    if code == access['protected_mission']:
        missing = access['minimum_completed_missions'] - len(projection['completed'] - {code})
        if missing > 0:
            return f'Complete {missing} more missions before purchasing this protected objective.'
    missing = access['prices'][code] - projection['available']
    return f'Missing {missing} Mission Keys.' if missing > 0 else ''
