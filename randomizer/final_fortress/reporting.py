"""Build the run receipt screen from credited events, not current prices."""

from randomizer.rewards.catalogue import BUFF_TARGETS
from .challenges import label


def reward_report(run):
    if run is None:
        return 'Finish a run to see its rewards.', []
    plan, claimed = run['plan'], set(run['claimed_events'])
    rows = []
    for entry in sorted(plan['milestones'], key=lambda item: item['seconds']):
        event = 'milestone:' + entry['id']
        rows.append((f'Survived {entry["seconds"] / 60:g} minutes',
                     plan['gem_rewards'][event] if event in claimed else 0,
                     'Earned' if event in claimed else 'Not reached'))
    victory = 'victory' in claimed
    rows.append(('Survival completed', run['config']['settings']['completion_gems'] if victory else 0,
                 'Earned' if victory else 'Not completed'))
    for entry in plan.get('challenges', []):
        effect = label(entry) if 'enemy_effect_id' in entry else entry.get('display_name', entry['id'])
        rows.append((f'Challenge: {effect} ×{entry.get("stacks", 1)}',
                     entry['victory_gems'] if victory else 0, 'Victory bonus' if victory else 'Requires victory'))
    for camp in plan['map']['camps']:
        event = 'camp:' + camp['id']
        pickup = plan.get('plan_version', 1) >= 25
        clear_event = 'camp_clear:' + camp['id'] if 18 <= plan.get('plan_version', 1) < 25 else event
        reward = camp.get('crate_reward')
        detail = ('Crate not collected' if pickup else
                  'Cleared; reward crate not collected' if clear_event in claimed else
                  'Not cleared' if plan.get('plan_version', 1) >= 18 else 'Not claimed')
        if event in claimed:
            detail = reward['display_name'] if reward else 'Claimed'
            if reward and reward['units']:
                detail += ': ' + ', '.join(
                    f'{unit["count"]} {BUFF_TARGETS.get(unit["type"], {}).get("label" if unit["count"] == 1 else "plural", unit["type"])}'
                    for unit in reward['units'])
            for slot, name in enumerate(plan.get('coop_players', [])):
                if f'camp_pick:{slot}:{camp["id"]}' in claimed:
                    detail = name + ': ' + detail
                    break
        rows.append((camp['display_name'], plan['gem_rewards'][clear_event] if clear_event in claimed else 0, detail))
    tiers = [event for event in claimed if event.startswith('kills:')]
    counts = run.get('kill_counts', {})
    verified_counts = any(value is not None for value in counts.values())
    actors = {entry['actor']: entry for entry in plan.get('coalition_scores', [])}
    players = plan.get('coop_players', ['Player'])
    missing_scores = ('Available after victory or defeat' if run['status'] == 'active' else
                      'Run ended without final scores' if run['status'] == 'abandoned' else
                      'Final scores missing from native log')
    for index, actor in enumerate(('FFPLAYER', 'FFALLY1', 'FFALLY2')):
        entry = actors.get(actor)
        name = (entry['name'] if entry and entry['name'] is not None else
                players[index] if index < len(players) else f'Helper AI {index}')
        count = counts.get(actor)
        detail = ('0 combat kills (not in this run)' if plan.get('coalition_scores') and actor not in actors else
                  f'{count} combat kills' if count is not None else
                  missing_scores)
        rows.append((f'{name} kills', '', detail))
    rows.append(('Kill reward',
                 sum(plan['gem_rewards'][event] for event in tiers),
                 f'{max(int(event.split(":")[1]) for event in tiers)}-kill threshold reached'
                 if tiers else 'No verified final scores; kill bonus unavailable' if not verified_counts else
                 'No kill-reward threshold reached'))
    total = sum(plan['gem_rewards'].get(event, 0) for event in claimed)
    outcome = {'active': 'Run in progress', 'victory': 'Victory', 'defeat': 'Defeat',
               'abandoned': 'Run ended without a verified outcome'}[run['status']]
    return f'{outcome} — {plan["map"]["display_name"]} — {total} Defensive Points earned', rows
