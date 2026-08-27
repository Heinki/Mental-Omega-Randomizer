"""Pure player-facing Shop reward and run summaries."""

from .config import SHOP_CONFIG
from .economy import mission_reward
from .model import RunStatus
from .text import gem_text


def reward_breakdown_lines(
    mission_class,
    *,
    victory_coin_bonus_level=0,
    modifiers=(),
    mission_modifier=None,
    challenge_hunter_level=0,
    config=SHOP_CONFIG,
):
    definition = config.mission_rewards[mission_class]
    reward = mission_reward(
        mission_class,
        victory_coin_bonus_level=victory_coin_bonus_level,
        modifiers=modifiers,
        mission_modifier=mission_modifier,
        challenge_hunter_level=challenge_hunter_level,
        config=config,
    )
    lines = [
        f'{definition.display_name} base: +{definition.run_coins} Ore, '
        f'+{gem_text(definition.meta_coins)}',
    ]
    if reward.base_run_coins != definition.run_coins:
        lines.append(
            f'Modified mission Ore: +{reward.base_run_coins}'
        )
    modified_meta = (
        reward.meta_coins
        - reward.mission_bonus_meta_coins
        - reward.challenge_hunter_meta_coins
    )
    if modified_meta != definition.meta_coins:
        lines.append(f'Modified Gems: +{gem_text(modified_meta)}')
    if reward.victory_bonus_run_coins:
        lines.append(
            'Permanent Victory Bonus: '
            f'+{reward.victory_bonus_run_coins} Ore'
        )
    if mission_modifier is not None:
        lines.append(
            f'{mission_modifier.title}: '
            f'+{reward.mission_bonus_run_coins} Ore, '
            f'+{gem_text(reward.mission_bonus_meta_coins)}'
        )
    if reward.challenge_hunter_run_coins or reward.challenge_hunter_meta_coins:
        lines.append(
            'Challenge Hunter: '
            f'+{reward.challenge_hunter_run_coins} Ore, '
            f'+{gem_text(reward.challenge_hunter_meta_coins)}'
        )
    lines.append(
        f'Total: +{reward.run_coins} Ore, '
        f'+{gem_text(reward.meta_coins)}'
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
        f'Persistent Gems: {profile.meta_coins}',
        f'Run purchases: {sum(item.quantity for item in run.run_purchases)}',
        f'Buff stacks purchased: {sum(item.stacks for item in run.run_buffs)}',
        f'Free starting draft buffs: '
        f'{sum(item.stacks for item in run.starting_draft_buffs)}',
        f'Free Buff Tokens used: {run.free_buff_tokens_used}',
        f'Emergency Revivals used: {run.emergency_revivals_used}',
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
        if profile.salvaged_run_coins:
            lines.append(
                f'Recovery Salvage banked: {profile.salvaged_run_coins} Ore '
                'for the next run.'
            )
    if run.completed_missions:
        lines.append('Completed missions:')
        lines.extend(
            f'  {index}. {mission_titles.get(code, code)}'
            for index, code in enumerate(run.completed_missions, start=1)
        )
    return tuple(lines)
