"""Deterministic one-mission boons and high-risk challenge effects."""

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256

from randomizer.config.static import load_static_config
from randomizer.missions.overrides import MISSIONS_WITH_ENEMY_SCALING_DISABLED

from .active import active_shop_reward_ids
from .catalogue import canonical_reward_for_id
from .text import gem_text
from .model import MissionEconomyClass
from .modifiers import modifier_effects


@dataclass(frozen=True)
class ShopMissionModifier:
    id: str
    title: str
    description: str
    bonus_run_coins: int
    bonus_meta_coins: int
    player_reward_ids: tuple[str, ...] = ()
    enemy_reward_id: str = ''
    buffs_allied_helpers: bool = False
    exclusive_reward_ids: tuple[str, ...] = ()

    @property
    def challenge(self):
        return bool(self.enemy_reward_id)

    @property
    def reward_text(self):
        return (
            f'+{self.bonus_run_coins} Ore / '
            f'+{gem_text(self.bonus_meta_coins)}'
        )


_MISSION_EFFECT_CONFIG = load_static_config('shop_mode.json')['mission_effects']
MISSION_MODIFIERS = tuple(
    ShopMissionModifier(
        id=effect_id,
        title=str(definition['title']),
        description=str(definition['description']),
        bonus_run_coins=int(definition['bonus_run_coins']),
        bonus_meta_coins=int(definition['bonus_meta_coins']),
        player_reward_ids=tuple(definition.get('player_reward_ids', ())),
        enemy_reward_id=str(definition.get('enemy_reward_id', '')),
        buffs_allied_helpers=bool(
            definition.get('buffs_allied_helpers', False)
        ),
        exclusive_reward_ids=tuple(
            definition.get('exclusive_reward_ids', ())
        ),
    )
    for effect_id, definition in _MISSION_EFFECT_CONFIG.items()
)
CHALLENGE_MODIFIERS = tuple(
    modifier for modifier in MISSION_MODIFIERS if modifier.challenge
)
PLAYER_BOON_MODIFIERS = tuple(
    modifier for modifier in MISSION_MODIFIERS if not modifier.challenge
)


def _eligible_player_boons(owned_reward_ids=()):
    owned = {str(reward_id) for reward_id in owned_reward_ids}
    eligible = tuple(
        modifier for modifier in PLAYER_BOON_MODIFIERS
        if not owned.intersection(modifier.exclusive_reward_ids)
    )
    return eligible or tuple(
        modifier for modifier in PLAYER_BOON_MODIFIERS
        if not modifier.exclusive_reward_ids
    )


def mission_modifier_for_offer(run_seed, stage, offer, *, owned_reward_ids=()):
    """Return stable modifier using player-first early-run difficulty pacing."""
    if offer is None or offer.economy_class not in {
        MissionEconomyClass.ACT_1,
        MissionEconomyClass.ACT_2,
    }:
        return None
    stream = (
        f'shop_mission_modifier\0{run_seed}\0{int(stage)}\0'
        f'{offer.mission_code}'
    ).encode('utf-8')
    digest = sha256(stream).digest()
    stage = int(stage)
    if stage <= 2:
        appearance_percent = 60
        challenge_percent = 5
    elif stage <= 5:
        appearance_percent = 50
        challenge_percent = 20
    else:
        appearance_percent = 65
        challenge_percent = 70
    if int.from_bytes(digest[:2], 'big') % 100 >= appearance_percent:
        return None
    pool = CHALLENGE_MODIFIERS
    if int.from_bytes(digest[2:4], 'big') % 100 >= challenge_percent:
        pool = _eligible_player_boons(owned_reward_ids)
    return pool[
        int.from_bytes(digest[4:6], 'big') % len(pool)
    ]


def _raw_run_offer_modifier(
    run, offer, offer_index, *, challenge_slots, owned_reward_ids
):
    if modifier_effects(run.modifiers)['force_enemy_challenge']:
        stream = (
            f'shop_hardcore_challenge\0{run.seed}\0{run.stage}\0'
            f'{offer_index}\0{offer.mission_code}'
        ).encode('utf-8')
        digest = sha256(stream).digest()
        return CHALLENGE_MODIFIERS[
            int.from_bytes(digest[:2], 'big') % len(CHALLENGE_MODIFIERS)
        ]
    if 0 <= offer_index < max(0, int(challenge_slots)):
        stream = (
            f'shop_permanent_challenge\0{run.seed}\0{run.stage}\0'
            f'{offer_index}\0{offer.mission_code}'
        ).encode('utf-8')
        digest = sha256(stream).digest()
        pool = CHALLENGE_MODIFIERS
        if int(run.stage) <= 5:
            pool = _eligible_player_boons(owned_reward_ids)
        return pool[
            int.from_bytes(digest[:2], 'big') % len(pool)
        ]
    return mission_modifier_for_offer(
        run.seed,
        run.stage,
        offer,
        owned_reward_ids=owned_reward_ids,
    )


def _unused_modifier(raw_modifier, used_ids, owned_reward_ids):
    if raw_modifier is None or raw_modifier.id not in used_ids:
        return raw_modifier
    pool = (
        CHALLENGE_MODIFIERS
        if raw_modifier.challenge else _eligible_player_boons(owned_reward_ids)
    )
    start = pool.index(raw_modifier)
    return next(
        (
            pool[(start + offset) % len(pool)]
            for offset in range(1, len(pool))
            if pool[(start + offset) % len(pool)].id not in used_ids
        ),
        raw_modifier,
    )


def mission_modifier_for_run_offer(run, offer, *, challenge_slots=0):
    """Resolve stable offer modifiers without duplicate visible choices."""
    if run is None or offer is None:
        return None
    try:
        offer_index = run.mission_offers.index(offer)
    except ValueError:
        return mission_modifier_for_offer(
            run.seed,
            run.stage,
            offer,
            owned_reward_ids=active_shop_reward_ids(run),
        )
    owned_reward_ids = active_shop_reward_ids(run)
    used_ids = set()
    resolved = None
    for index, current_offer in enumerate(
        run.mission_offers[:offer_index + 1]
    ):
        raw_modifier = _raw_run_offer_modifier(
            run,
            current_offer,
            index,
            challenge_slots=challenge_slots,
            owned_reward_ids=owned_reward_ids,
        )
        resolved = _unused_modifier(raw_modifier, used_ids, owned_reward_ids)
        if resolved is not None:
            used_ids.add(resolved.id)
    return resolved


def active_mission_modifier(run, *, challenge_slots=0):
    if run is None or not run.selected_mission_code:
        return None
    offer = next((
        item for item in run.mission_offers
        if item.mission_code == run.selected_mission_code
    ), None)
    return mission_modifier_for_run_offer(
        run, offer, challenge_slots=challenge_slots
    )


def mission_blocks_shop_enemy_buffs(mission):
    """Protect missions where player-force buffs cannot be applied safely."""
    mission = mission if isinstance(mission, dict) else {}
    return bool(
        mission.get('no_build')
        or mission.get('true_no_build')
        or mission.get('build_classification') in {
            'true_no_build', 'no_build_production',
        }
    )


def shop_enemy_buff_block_reason(mission, mission_code=''):
    """Return the launch safety exception shown alongside Shop buff previews."""
    if str(mission_code) in MISSIONS_WITH_ENEMY_SCALING_DISABLED:
        return 'scripted-opening protection'
    if mission_blocks_shop_enemy_buffs(mission):
        return 'no-build protection'
    return ''


def shop_enemy_scaling_entries(
    run, offer, mission, *, challenge_slots=0
):
    """Build capped, deterministic Shop enemy buffs for one mission offer."""
    if run is None or offer is None:
        return []
    if shop_enemy_buff_block_reason(mission, offer.mission_code):
        return []

    candidates = []
    effects = modifier_effects(run.modifiers)
    for _index in range(max(0, effects['enemy_armor_stacks'])):
        candidates.append((
            'AI T1 Unit Armor', 'Shop run modifier',
            'Superweapon Arms Race',
        ))

    mission_modifier = mission_modifier_for_run_offer(
        run, offer, challenge_slots=challenge_slots
    )
    if mission_modifier is not None and mission_modifier.enemy_reward_id:
        candidates.append((
            mission_modifier.enemy_reward_id,
            'Shop mission challenge',
            mission_modifier.title,
        ))

    first_scaling_stage = 5
    maximum_progress_buffs = 9
    scaling_stage = int(run.stage) - first_scaling_stage
    scaling_span = max(1, int(run.run_length) - first_scaling_stage)
    progress_buffs = (
        0
        if scaling_stage < 0
        else 1 + scaling_stage * (maximum_progress_buffs - 1) // scaling_span
    )
    reward_ids = [
        'AI Infantry Armor',
        'AI Vehicle Armor',
        'AI Aircraft Armor',
        'AI Defense Armor',
        'AI Infantry Production',
        'AI Vehicle Production',
        'AI Aircraft Production',
        'AI Defense Production',
        'AI T1 Unit Health',
        'AI T1 Unit Armor',
        'AI T1 Unit Firepower',
        'AI T1 Unit Fire Rate',
        'AI T1 Unit Mobility',
    ]
    if int(run.stage) >= 8:
        reward_ids.extend((
            'AI T2 Unit Health',
            'AI T2 Unit Armor',
            'AI T2 Unit Firepower',
            'AI T2 Unit Fire Rate',
        ))
    if int(run.stage) >= int(run.run_length):
        reward_ids.extend((
            'AI T3 Unit Health',
            'AI T3 Unit Armor',
            'AI T3 Unit Firepower',
            'AI T3 Unit Fire Rate',
        ))
    reward_ids = tuple(reward_ids)
    stream = (
        f'shop_enemy_scaling\0{run.seed}\0{int(run.stage)}\0'
        f'{offer.mission_code}'
    ).encode('utf-8')
    first = sha256(stream).digest()[0] % len(reward_ids)
    for index in range(progress_buffs):
        candidates.append((
            reward_ids[(first + index) % len(reward_ids)],
            'Shop stage scaling',
            f'Stage {run.stage}/{run.run_length}',
        ))

    if effects['force_enemy_challenge']:
        # Keep Hardcore's extra buff separate from its forced mission challenge
        # and the normal stage scaling. Each mission gets a stable draw.
        used_effect_ids = {
            canonical_reward_for_id(reward_id).get('enemy_effect_id')
            for reward_id, _, _ in candidates
        }
        stream = (
            f'shop_hardcore_extra_buff\0{run.seed}\0{int(run.stage)}\0'
            f'{offer.mission_code}'
        ).encode('utf-8')
        start = (
            int.from_bytes(sha256(stream).digest()[:2], 'big')
            % len(reward_ids)
        )
        for offset in range(len(reward_ids)):
            reward_id = reward_ids[(start + offset) % len(reward_ids)]
            effect_id = canonical_reward_for_id(reward_id).get(
                'enemy_effect_id'
            )
            if effect_id not in used_effect_ids:
                candidates.append((reward_id, 'Shop Hardcore', 'Hardcore'))
                break

    entries = []
    counts = Counter()
    for reward_id, source, earned_from in candidates:
        reward = canonical_reward_for_id(reward_id)
        effect_id = str(reward.get('enemy_effect_id') or '')
        maximum = max(0, int(reward.get('enemy_maximum', 0)))
        if not effect_id or counts[effect_id] >= maximum:
            continue
        counts[effect_id] += 1
        entries.append({
            'reward': reward,
            'source': source,
            'earned_from': earned_from,
        })
    return entries
