"""Pure Shop Mode rules and state models."""

from .config import SHOP_CONFIG, ShopModeConfig
from .active import active_shop_rewards
from .archipelago import (
    ap_automatic_reward_ids,
    ap_unit_entitlement_ids,
    archipelago_shop_identity,
    shop_reward_ids_from_ap_ledger,
)
from .economy import (
    discounted_shop_price,
    mission_reward,
    permanent_buff_price,
    permanent_unit_price,
    permanent_upgrade_price,
    run_buff_price,
    run_unit_price,
    starting_run_coins,
)
from .missions import classify_mission, generate_mission_offers
from .modifiers import hidden_offer_codes, modifier_effects
from .model import (
    MissionEconomyClass,
    MissionOffer,
    PurchaseResult,
    RunStatus,
    ShopProfile,
    ShopRun,
)
from .state import normalize_shop_profile, normalize_shop_run
from .summary import reward_breakdown_lines, run_summary_lines
from .persistence import ShopPersistenceError, ShopRepository
from .service import ShopProgressionService
from .transitions import (
    ShopTransitionError,
    apply_mission_failure,
    apply_mission_difficulty_assist,
    apply_mission_victory,
    commit_selected_mission,
    reroll_missions,
    select_mission,
    start_new_run,
    victory_key,
)


__all__ = (
    'SHOP_CONFIG',
    'MissionEconomyClass',
    'MissionOffer',
    'PurchaseResult',
    'RunStatus',
    'ShopModeConfig',
    'ShopPersistenceError',
    'ShopProfile',
    'ShopProgressionService',
    'ShopRepository',
    'ShopRun',
    'ShopTransitionError',
    'apply_mission_failure',
    'apply_mission_difficulty_assist',
    'apply_mission_victory',
    'active_shop_rewards',
    'ap_automatic_reward_ids',
    'ap_unit_entitlement_ids',
    'archipelago_shop_identity',
    'classify_mission',
    'commit_selected_mission',
    'discounted_shop_price',
    'generate_mission_offers',
    'hidden_offer_codes',
    'mission_reward',
    'modifier_effects',
    'normalize_shop_profile',
    'normalize_shop_run',
    'permanent_unit_price',
    'permanent_buff_price',
    'permanent_upgrade_price',
    'reroll_missions',
    'run_buff_price',
    'run_summary_lines',
    'run_unit_price',
    'starting_run_coins',
    'reward_breakdown_lines',
    'select_mission',
    'start_new_run',
    'shop_reward_ids_from_ap_ledger',
    'victory_key',
)
