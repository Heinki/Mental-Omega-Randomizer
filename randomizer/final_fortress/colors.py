"""Apply a visual color choice without changing player, faction or team slots."""


def remap_colors(sections, plan):
    selected = plan.get('player_color', 0)
    if selected == 0:
        return
    for section, values in sections.items():
        keys = tuple(values) if section == 'HouseColors' else ('Color',)
        for key in keys:
            if key not in values:
                continue
            color = int(values[key])
            if color in (0, selected):
                values[key] = str(selected if color == 0 else 0)

    players = plan.get('coop_players', [])
    if players:
        colors = {row['Name']: int(row['Color']) for name, row in sections.items()
                  if name == 'Settings' or name.startswith('Other')}
        waypoints = [plan['map']['player_waypoint'], *plan.get('allied_waypoints', [])]
        order = sorted(range(len(players)), key=lambda slot: colors[players[slot]])
        for house, slot in enumerate(order, 1):
            sections['SpawnLocations'][f'Multi{house}'] = str(waypoints[slot])
