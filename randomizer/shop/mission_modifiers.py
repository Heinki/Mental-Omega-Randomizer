"""Deterministic one-mission boons and high-risk challenge effects."""

from dataclasses import dataclass
from hashlib import sha256

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

    @property
    def challenge(self):
        return bool(self.enemy_reward_id)

    @property
    def reward_text(self):
        return (
            f'+{self.bonus_run_coins} Ore / '
            f'+{self.bonus_meta_coins} Mental Coins'
        )


MISSION_MODIFIERS = (
    ShopMissionModifier(
        'command_surge',
        'Command Surge',
        'Player and allied-helper production time is 30% shorter.',
        1,
        1,
        ('Faction Production Drill I', 'Faction Production Drill I'),
        buffs_allied_helpers=True,
    ),
    ShopMissionModifier(
        'tempest_support',
        'Great Tempest Support',
        'Player receives a building-free repeating Great Tempest aid power.',
        1,
        1,
        ('Great Tempest Power',),
    ),
    ShopMissionModifier(
        'armored_vanguard',
        'Armored AI Vanguard',
        'Hostile AI Tier 1 units have 11% stronger armor.',
        2,
        1,
        enemy_reward_id='AI T1 Unit Armor',
    ),
    ShopMissionModifier(
        'lethal_vanguard',
        'Lethal AI Vanguard',
        'Hostile AI Tier 1 units deal 15% more damage.',
        2,
        1,
        enemy_reward_id='AI T1 Unit Firepower',
    ),
    ShopMissionModifier(
        'tempest_threat',
        'AI Great Tempest',
        'Hostile AI receives a repeating Great Tempest power.',
        3,
        2,
        enemy_reward_id='AI Foehn Great Tempest',
    ),
)
CHALLENGE_MODIFIERS = tuple(
    modifier for modifier in MISSION_MODIFIERS if modifier.challenge
)
PLAYER_BOON_MODIFIERS = tuple(
    modifier for modifier in MISSION_MODIFIERS if not modifier.challenge
)


def mission_modifier_for_offer(run_seed, stage, offer):
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
    pool = (
        CHALLENGE_MODIFIERS
        if int.from_bytes(digest[2:4], 'big') % 100 < challenge_percent
        else PLAYER_BOON_MODIFIERS
    )
    return pool[
        int.from_bytes(digest[4:6], 'big') % len(pool)
    ]


def mission_modifier_for_run_offer(run, offer, *, challenge_slots=0):
    """Resolve an offer modifier, forcing first permanent challenge slots."""
    if run is None or offer is None:
        return None
    try:
        offer_index = run.mission_offers.index(offer)
    except ValueError:
        offer_index = -1
    if 0 <= offer_index < max(0, int(challenge_slots)):
        stream = (
            f'shop_permanent_challenge\0{run.seed}\0{run.stage}\0'
            f'{offer_index}\0{offer.mission_code}'
        ).encode('utf-8')
        digest = sha256(stream).digest()
        pool = (
            PLAYER_BOON_MODIFIERS
            if int(run.stage) <= 5 else CHALLENGE_MODIFIERS
        )
        return pool[
            int.from_bytes(digest[:2], 'big') % len(pool)
        ]
    return mission_modifier_for_offer(run.seed, run.stage, offer)


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
