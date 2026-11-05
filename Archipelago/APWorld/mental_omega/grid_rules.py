"""Monotone AP rules for the frozen client purchase economy."""

def connect_key_regions(world, menu, regions, local_victory_names):
    access = world.run_manifest.get('grid_access') or {}
    mode = access.get('mode', 'Standard')
    if mode == 'Standard':
        return False
    starts = set(access['starting_missions'])
    for code, region in regions.items():
        if code in starts:
            menu.connect(region)
            continue
        if mode == 'Mission-Specific Keys':
            name = access['mission_keys'][code]
            menu.connect(region, rule=lambda state, name=name: state.has(name, world.player))
        else:
            # One progression supply item covers every price simultaneously.
            # The client enforces actual spending in a separate durable ledger.
            name = access['currency_item']
            needed = access['minimum_completed_missions'] if code == access['protected_mission'] else 0
            prior = tuple(item for mission, item in local_victory_names.items() if mission != code)
            menu.connect(region, rule=lambda state, name=name, needed=needed, prior=prior:
                         state.has(name, world.player) and
                         sum(state.has(item, world.player) for item in prior) >= needed)
    return True
