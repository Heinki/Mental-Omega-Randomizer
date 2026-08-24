"""Filesystem boundary for Shop lifecycle and purchase transactions."""

from .active import (
    active_shop_power_ids,
    active_shop_reward_ids,
    active_shop_tech_ids,
)
from .archipelago_purchases import (
    commit_archipelago_purchase,
    pending_archipelago_purchase_ids,
    reconcile_archipelago_purchases,
    validate_archipelago_purchase,
)
from .catalogue import (
    canonical_reward_for_id,
    catalogue_entry,
    shop_entry_available,
)
from .config import SHOP_CONFIG
from .economy import (
    permanent_buff_price,
    permanent_unit_price,
    run_buff_price,
    run_unit_price,
)
from .meta import (
    purchase_permanent_unit as apply_permanent_unit_purchase,
    purchase_permanent_buff as apply_permanent_buff_purchase,
    purchase_permanent_upgrade as apply_permanent_upgrade_purchase,
)
from .model import RunStatus, ShopRewardType
from .persistence import ShopRepository
from .purchases import apply_validated_run_purchase, validate_run_purchase
from .transitions import (
    ShopTransitionError,
    abandon_run,
    apply_mission_failure,
    apply_mission_difficulty_assist,
    apply_mission_victory,
    commit_selected_mission,
    reroll_missions,
    merge_archipelago_entitlements,
    select_mission,
    start_new_run,
)


class ShopProgressionService:
    def __init__(self, repository=None):
        self.repository = repository or ShopRepository()

    def start_run(self, **run_options):
        profile, current_run = self.repository.load()
        if current_run is not None and current_run.status is RunStatus.ACTIVE:
            raise ShopTransitionError(
                'Cannot replace an active Shop run; fail or complete it first'
            )
        requested_run_id = str(run_options.get('run_id') or '')
        if current_run is not None and current_run.run_id == requested_run_id:
            raise ShopTransitionError(
                f'New Shop run must not reuse run_id {requested_run_id!r}'
            )
        transition = start_new_run(profile, **run_options)
        self.repository.commit(
            transition.profile,
            transition.run,
            transition.transaction_id,
        )
        return transition

    def commit_mission(self, mission_code):
        run = self.repository.load_run()
        if run is None:
            raise ShopTransitionError('No Shop run exists')
        committed = commit_selected_mission(run, mission_code)
        if committed != run:
            self.repository.save_run(committed)
        return committed

    def sync_archipelago_entitlements(
        self, ap_identity, reward_ids, *, current_run=None
    ):
        run = (
            self.repository.load_run()
            if current_run is None
            else current_run
        )
        if run is None:
            return None
        updated = merge_archipelago_entitlements(
            run, ap_identity, reward_ids
        )
        if updated != run:
            self.repository.save_run(updated)
        return updated

    def select_mission(self, mission_code):
        run = self.repository.load_run()
        if run is None:
            raise ShopTransitionError('No Shop run exists')
        selected = select_mission(run, mission_code)
        if selected != run:
            self.repository.save_run(selected)
        return selected

    def purchase_archipelago_location(
        self,
        identity,
        location_id,
        *,
        cost,
        connected,
        available_location_ids,
        checked_location_ids=(),
    ):
        profile = self.repository.load_profile()
        validation = validate_archipelago_purchase(
            profile,
            identity,
            location_id,
            cost=cost,
            connected=connected,
            available_location_ids=available_location_ids,
            checked_location_ids=checked_location_ids,
        )
        if validation.allowed:
            self.repository.save_profile(
                commit_archipelago_purchase(profile, identity, validation)
            )
        return validation

    def pending_archipelago_purchase_ids(self, identity):
        return pending_archipelago_purchase_ids(
            self.repository.load_profile(), identity
        )

    def reconcile_archipelago_purchases(self, identity, checked_location_ids):
        profile = self.repository.load_profile()
        updated = reconcile_archipelago_purchases(
            profile, identity, checked_location_ids
        )
        if updated != profile:
            self.repository.save_profile(updated)
        return updated

    def reroll(self, mission_offers, *, replaced_mission_code=None):
        profile, run = self.repository.load()
        if run is None:
            raise ShopTransitionError('No Shop run exists')
        upgrade = SHOP_CONFIG.permanent_upgrades['mission_reroll']
        maximum = (
            profile.upgrade_level('mission_reroll')
            * int(upgrade.effects['rerolls_per_level'])
        )
        updated = reroll_missions(
            run,
            mission_offers,
            maximum_rerolls=maximum,
            replaced_mission_code=replaced_mission_code,
        )
        self.repository.save_run(updated)
        return updated

    def ease_mission(self, mission_code):
        profile, run = self.repository.load()
        if run is None:
            raise ShopTransitionError('No Shop run exists')
        upgrade = SHOP_CONFIG.permanent_upgrades['mission_difficulty_assist']
        maximum = (
            profile.upgrade_level('mission_difficulty_assist')
            * int(upgrade.effects['assists_per_level'])
        )
        updated = apply_mission_difficulty_assist(
            run, mission_code, maximum_assists=maximum
        )
        self.repository.save_run(updated)
        return updated

    def purchase_run_reward(self, reward_id):
        profile, run = self.repository.load()
        if run is None:
            raise ShopTransitionError('No Shop run exists')
        reward = canonical_reward_for_id(reward_id)
        entry = catalogue_entry(reward)
        if entry is None or entry.reward_type not in {
            ShopRewardType.UNIT_ACCESS,
            ShopRewardType.UNIT_BUFF,
            ShopRewardType.POWER_ACCESS,
            ShopRewardType.POWER_BUFF,
        }:
            return validate_run_purchase(
                reward,
                price=0,
                run_coins=run.run_coins,
                shop_eligible=False,
            )
        price_function = (
            run_unit_price
            if entry.reward_type in {
                ShopRewardType.UNIT_ACCESS,
                ShopRewardType.POWER_ACCESS,
            }
            else run_buff_price
        )
        price = price_function(
            entry.tier or 'tier_1',
            shop_discount_level=profile.upgrade_level('shop_discount'),
            modifiers=run.modifiers,
        )
        owned = active_shop_reward_ids(run)
        stacks = next(
            (
                item.stacks for item in run.run_buffs
                if item.reward_id == entry.reward_id
            ),
            0,
        ) + next(
            (
                item.stacks for item in run.permanent_buffs_snapshot
                if item.reward_id == entry.reward_id
            ),
            0,
        )
        validation = validate_run_purchase(
            reward,
            price=price,
            run_coins=run.run_coins,
            run_status=run.status,
            mission_committed=run.mission_committed,
            owned_reward_ids=owned,
            active_tech_ids=active_shop_tech_ids(run),
            active_power_ids=active_shop_power_ids(run),
            current_stacks=stacks,
            shop_eligible=shop_entry_available(
                entry,
                campaign_filter=str(
                    run.reward_settings.get('shop_faction_filter')
                    or run.campaign_filter
                ),
                reward_mode=run.reward_mode,
                strict_faction=True,
            ),
        )
        if validation.allowed:
            self.repository.save_run(
                apply_validated_run_purchase(run, reward, validation)
            )
        return validation

    def purchase_permanent_unit(self, reward_id):
        profile, run = self.repository.load()
        if run is not None and run.status is RunStatus.ACTIVE:
            raise ShopTransitionError(
                'Permanent purchases are locked during an active Shop run'
            )
        reward = canonical_reward_for_id(reward_id)
        entry = catalogue_entry(reward)
        price = permanent_unit_price(
            entry.tier if entry is not None and entry.tier else 'tier_1'
        )
        outcome = apply_permanent_unit_purchase(
            profile, reward, price=price, shop_eligible=entry is not None
        )
        if outcome.validation.allowed:
            self.repository.save_profile(outcome.profile)
        return outcome

    def purchase_permanent_buff(self, reward_id):
        profile, run = self.repository.load()
        if run is not None and run.status is RunStatus.ACTIVE:
            raise ShopTransitionError(
                'Permanent purchases are locked during an active Shop run'
            )
        reward = canonical_reward_for_id(reward_id)
        entry = catalogue_entry(reward)
        price = permanent_buff_price(
            entry.tier if entry is not None and entry.tier else 'tier_1'
        )
        outcome = apply_permanent_buff_purchase(
            profile, reward, price=price, shop_eligible=entry is not None
        )
        if outcome.validation.allowed:
            self.repository.save_profile(outcome.profile)
        return outcome

    def purchase_permanent_upgrade(self, upgrade_id):
        profile, run = self.repository.load()
        if run is not None and run.status is RunStatus.ACTIVE:
            raise ShopTransitionError(
                'Permanent purchases are locked during an active Shop run'
            )
        outcome = apply_permanent_upgrade_purchase(profile, upgrade_id)
        if outcome.validation.allowed:
            self.repository.save_profile(outcome.profile)
        return outcome

    def record_victory(self, mission_code, *, next_offers=()):
        profile, run = self.repository.load()
        if run is None:
            raise ShopTransitionError('No Shop run exists')
        transition = apply_mission_victory(
            profile, run, mission_code, next_offers=next_offers
        )
        if transition.changed:
            self.repository.commit(
                transition.profile,
                transition.run,
                transition.victory_key,
            )
        return transition

    def record_failure(self, mission_code):
        run = self.repository.load_run()
        if run is None:
            raise ShopTransitionError('No Shop run exists')
        transition = apply_mission_failure(run, mission_code)
        if transition.changed:
            self.repository.save_run(transition.run)
        return transition

    def give_up_run(self):
        run = self.repository.load_run()
        if run is None:
            raise ShopTransitionError('No Shop run exists')
        transition = abandon_run(run)
        if transition.changed:
            self.repository.save_run(transition.run)
        return transition
