"""Keep native spawn colors and score identities in sync."""


def remap_color(color, plan):
    """Swap the host's default color with the chosen color for every house."""
    selected = plan.get('player_color', 0)
    return selected if color == 0 else 0 if color == selected else color


def score_scheme(color):
    """Mental Omega creates two remap schemes per rules [Colors] entry.

    Multiplayer slots skip LightGrey, the third rules color (observer/flash).
    Score records use the second scheme of each pair, starting with Teal=1.
    """
    return 2 * (color + int(color >= 2)) + 1


def remap_score_scheme(scheme, plan):
    """Resolve a frozen default-color receipt against the actual spawn palette.

    Keep historical plans unchanged so their configuration and reward receipts
    still validate, including runs launched before color-aware score parsing.
    """
    selected_scheme = score_scheme(plan.get('player_color', 0))
    return selected_scheme if scheme == 1 else 1 if scheme == selected_scheme else scheme


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
            values[key] = str(remap_color(color, plan))

    players = plan.get('coop_players', [])
    if players:
        colors = {row['Name']: int(row['Color']) for name, row in sections.items()
                  if name == 'Settings' or name.startswith('Other')}
        waypoints = [plan['map']['player_waypoint'], *plan.get('allied_waypoints', [])]
        order = sorted(range(len(players)), key=lambda slot: colors[players[slot]])
        for house, slot in enumerate(order, 1):
            sections['SpawnLocations'][f'Multi{house}'] = str(waypoints[slot])
