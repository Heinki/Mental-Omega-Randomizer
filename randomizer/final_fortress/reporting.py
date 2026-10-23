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
        clear_event = 'camp_clear:' + camp['id'] if plan.get('plan_version', 1) >= 18 else event
        reward = camp.get('crate_reward')
        detail = ('Cleared; reward crate not collected' if clear_event in claimed else
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
    rows.append(('Enemy kill score', sum(plan['gem_rewards'][event] for event in tiers),
                 f'{max(int(event.split(":")[1]) for event in tiers)}-kill threshold reached'
                 if tiers else 'No kill-reward threshold reached'))
    total = sum(plan['gem_rewards'].get(event, 0) for event in claimed)
    outcome = {'active': 'Run in progress', 'victory': 'Victory', 'defeat': 'Defeat',
               'abandoned': 'Run ended without a verified outcome'}[run['status']]
    return f'{outcome} — {plan["map"]["display_name"]} — {total} Defensive Points earned', rows
