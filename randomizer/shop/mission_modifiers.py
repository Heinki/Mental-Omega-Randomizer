"""Deterministic one-mission boons and high-risk challenge effects."""

from dataclasses import dataclass
from hashlib import sha256

from randomizer.config.static import load_static_config

from .active import active_shop_reward_ids
from .text import gem_text
from .model import MissionEconomyClass


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
