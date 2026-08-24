"""Pure player-facing Shop reward and run summaries."""

from .config import SHOP_CONFIG
from .economy import mission_reward
from .model import RunStatus


def reward_breakdown_lines(
    mission_class,
    *,
    victory_coin_bonus_level=0,
    modifiers=(),
    config=SHOP_CONFIG,
):
    definition = config.mission_rewards[mission_class]
    reward = mission_reward(
        mission_class,
        victory_coin_bonus_level=victory_coin_bonus_level,
        modifiers=modifiers,
        config=config,
    )
    lines = [
        f'{definition.display_name} base: +{definition.run_coins} Ore, '
        f'+{definition.meta_coins} Mental Coins',
    ]
    if reward.base_run_coins != definition.run_coins:
        lines.append(
            f'Modified mission Ore: +{reward.base_run_coins}'
        )
    if reward.meta_coins != definition.meta_coins:
        lines.append(f'Modified Mental Coins: +{reward.meta_coins}')
    if reward.victory_bonus_run_coins:
        lines.append(
            'Permanent Victory Bonus: '
            f'+{reward.victory_bonus_run_coins} Ore'
        )
    lines.append(
        f'Total: +{reward.run_coins} Ore, '
        f'+{reward.meta_coins} Mental Coins'
    )
    return tuple(lines)


def run_summary_lines(profile, run, mission_titles=None, config=SHOP_CONFIG):
    if run is None:
        return ('No Shop run exists.',)
    mission_titles = mission_titles or {}
    status_heading = {
        RunStatus.ACTIVE: 'RUN ACTIVE',
        RunStatus.FAILED: 'RUN OVER',
        RunStatus.COMPLETED: 'RUN VICTORY',
    }[run.status]
    lines = [
        status_heading,
        f'Seed: {run.seed}',
        f'Missions won: {len(run.completed_missions)} / {run.run_length}',
        f'Ore remaining: {run.run_coins}',
        f'Persistent Mental Coins: {profile.meta_coins}',
        f'Run purchases: {sum(item.quantity for item in run.run_purchases)}',
        f'Buff stacks purchased: {sum(item.stacks for item in run.run_buffs)}',
        'Modifiers: ' + (
            ', '.join(
                config.modifiers[item].display_name for item in run.modifiers
            )
            if run.modifiers else 'None'
        ),
    ]
    if run.status is RunStatus.FAILED:
        if run.failed_mission_code == 'GAVE_UP':
            lines.append(f'Run given up at stage {run.failed_stage}.')
        else:
            title = mission_titles.get(
                run.failed_mission_code, run.failed_mission_code
            )
            lines.append(f'Failed at stage {run.failed_stage}: {title}')
    if run.completed_missions:
        lines.append('Completed missions:')
        lines.extend(
            f'  {index}. {mission_titles.get(code, code)}'
            for index, code in enumerate(run.completed_missions, start=1)
        )
    return tuple(lines)
