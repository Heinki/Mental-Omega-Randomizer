"""Monotone AP rules for the frozen client purchase economy."""

try:
    from ._vendor.randomizer.progression.mission_access import currency_thresholds
except ModuleNotFoundError:
    from randomizer.progression.mission_access import currency_thresholds


def connect_key_regions(world, menu, regions, local_victory_names):
    access = world.run_manifest.get('grid_access') or {}
    mode = access.get('mode', 'Standard')
    if mode == 'Standard':
        return False
    starts = set(access['starting_missions'])
    thresholds = dict(currency_thresholds(access))
    for code, region in regions.items():
        if code in starts:
            menu.connect(region)
            continue
        if mode == 'Mission-Specific Keys':
            name = access['mission_keys'][code]
            menu.connect(region, rule=lambda state, name=name: state.has(name, world.player))
        else:
            name = access['currency_item']
            count = thresholds.get(code, 1)  # Legacy rooms award a single bundle.
            needed = access['minimum_completed_missions'] if code == access['protected_mission'] else 0
            prior = tuple(item for mission, item in local_victory_names.items() if mission != code)
            menu.connect(region, rule=lambda state, name=name, count=count, needed=needed, prior=prior:
                         state.has(name, world.player, count) and
                         sum(state.has(item, world.player) for item in prior) >= needed)
    return True
