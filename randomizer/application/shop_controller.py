"""Standalone Shop Mode UI coordination."""

from dataclasses import replace
from hashlib import sha256
import uuid
import tkinter as tk
from tkinter import messagebox

from ._dependencies import (
    BUFF_TYPES,
    DIFFICULTIES,
    GAME_EXE,
    GAME_LAUNCHER_EXE,
    POWER_BUFF_TYPES,
    STANDARD_STARTER_FAMILIES_BY_CAMPAIGN,
    cameo_extraction_pending,
    custom_sidebar_preview,
    ensure_superweapon_cameos,
    ensure_unit_cameos,
)

from randomizer.missions.tier_one import (
    expanded_tier_one_defense_ids,
    expanded_tier_one_unit_ids,
)
from randomizer.rewards.definitions import unit_display_label
from randomizer.rewards.display import buff_effect_lines, reward_display_name
from randomizer.shop.active import active_shop_rewards
from randomizer.shop.archipelago import (
    ARCHIPELAGO_RECEIVED_UNIT_LOADOUT_RANDOM,
    ap_automatic_reward_ids,
    ap_unit_entitlement_ids,
    random_ap_unit_entitlement_ids,
)
from randomizer.shop.catalogue import (
    canonical_reward_for_id,
    catalogue_entry,
    shop_catalogue,
    shop_entry_available,
)
from randomizer.shop.config import SHOP_CONFIG
from randomizer.shop.economy import (
    permanent_buff_price,
    permanent_unit_price,
    permanent_upgrade_price,
)
from randomizer.shop.missions import (
    generate_mission_offers,
    mission_classes_for_stage,
)
from randomizer.shop.mission_modifiers import active_mission_modifier
from randomizer.shop.meta import validate_starting_loadout
from randomizer.shop.model import BuffPurchase, RunStatus, ShopRewardType
from randomizer.shop.persistence import ShopRepository
from randomizer.shop.service import ShopProgressionService
from randomizer.shop.transitions import ShopTransitionError
from .shop_polish_controller import ShopPolishController


SHOP_FACTION_POOLS = (
    'All Factions',
    'Allies Only',
    'Soviets Only',
    'Epsilon Only',
    'Foehn Only',
)
SHOP_FACTION_CAMPAIGNS = {
    'All Factions': 'All Campaigns',
    'Allies Only': 'Allies',
    'Soviets Only': 'Soviets',
    'Epsilon Only': 'Epsilon',
    'Foehn Only': 'Foehn',
}
SHOP_CAMPAIGN_FACTIONS = {
    campaign: label for label, campaign in SHOP_FACTION_CAMPAIGNS.items()
}
SHOP_REWARD_MODE = 'Standard'
SHOP_DISCOUNT_SPECIALIZATIONS = ('Units', 'Buffs', 'Powers')
class ShopController(ShopPolishController):
    def initialize_shop_controller(self):
        self.shop_config = SHOP_CONFIG
        self.shop_repository = ShopRepository()
        self.shop_service = ShopProgressionService(self.shop_repository)
        self.shop_profile, self.shop_run = self.shop_repository.load()
        self.shop_stage_var = tk.StringVar(value='Run — / 10')
        self.shop_status_var = tk.StringVar(value='Status: No Run')
        self.shop_run_coins_var = tk.StringVar(value='Ore: 0')
        self.shop_meta_coins_var = tk.StringVar(value='Mental Coins: 0')
        self.shop_rerolls_var = tk.StringVar(value='Rerolls: 0 / 0')
        self.shop_message_var = tk.StringVar(value='')
        self.shop_ap_purchase_status_var = tk.StringVar(value='')
        saved_faction_pool = self.config.get('shop_faction_pool')
        if saved_faction_pool not in SHOP_FACTION_POOLS:
            saved_faction_pool = SHOP_CAMPAIGN_FACTIONS.get(
                self.campaign_var.get(), SHOP_FACTION_POOLS[0]
            )
        self.shop_faction_pool_options = SHOP_FACTION_POOLS
        self.shop_faction_pool_var = tk.StringVar(value=saved_faction_pool)
        self.shop_buff_draft_options = (
            ('Any Buff', ''),
            *((item['setting_label'], item['id']) for item in BUFF_TYPES),
        )
        draft_labels = {label for label, _value in self.shop_buff_draft_options}
        saved_draft = str(self.config.get('shop_starting_buff_draft') or '')
        if saved_draft not in draft_labels:
            saved_draft = 'Any Buff'
        self.shop_starting_buff_draft_var = tk.StringVar(value=saved_draft)
        saved_specialization = str(
            self.config.get('shop_discount_specialization') or 'Units'
        )
        if saved_specialization not in SHOP_DISCOUNT_SPECIALIZATIONS:
            saved_specialization = 'Units'
        self.shop_discount_specialization_options = SHOP_DISCOUNT_SPECIALIZATIONS
        self.shop_discount_specialization_var = tk.StringVar(
            value=saved_specialization
        )
        self.shop_loadout_help_var = tk.StringVar(value='')
        self.shop_permanent_setup_help_var = tk.StringVar(value='')
        self.shop_category_var = tk.StringVar(value='Units')
        self.shop_buff_target_var = tk.StringVar(value='')
        self.shop_permanent_buff_target_var = tk.StringVar(value='')
        self.shop_search_var = tk.StringVar(value='')
        self.shop_loadout_search_var = tk.StringVar(value='')
        self.shop_setup_search_var = tk.StringVar(value='')
        self.shop_permanent_search_var = tk.StringVar(value='')
        self.shop_sort_var = tk.StringVar(value='Name')
        self.shop_show_locked_var = tk.BooleanVar(value=True)
        self.shop_summary_var = tk.StringVar(value='No Shop run exists.')
        self.shop_modifier_vars = {
            modifier_id: tk.BooleanVar(value=False)
            for modifier_id in self.shop_config.modifiers
        }
        catalogue = shop_catalogue()
        self._shop_entry_by_reward_id = {
            entry.reward_id: entry for entry in catalogue
        }
        self._shop_unit_entries = tuple(
            entry for entry in catalogue
            if entry.reward_type is ShopRewardType.UNIT_ACCESS
        )
        self._shop_buff_entries = tuple(
            entry for entry in catalogue
            if entry.reward_type is ShopRewardType.UNIT_BUFF
        )
        self._shop_power_entries = tuple(
            entry for entry in catalogue
            if entry.reward_type is ShopRewardType.POWER_ACCESS
        )
        self._shop_power_buff_entries = tuple(
            entry for entry in catalogue
            if entry.reward_type is ShopRewardType.POWER_BUFF
        )
        self._shop_catalogue_rows = {}
        self._shop_catalogue_buyable = {}
        self._shop_catalogue_upgrade_targets = {}
        self._shop_permanent_rows = {}
        self._shop_permanent_buyable = {}
        self._shop_upgrade_rows = {}
        self._shop_upgrade_buyable = {}
        self._shop_permanent_buff_rows = {}
        self._shop_permanent_buff_buyable = {}
        self._shop_permanent_buff_target_ids = {}
        self._shop_loadout_rows = {}
        self._shop_pending_loadout_selection = set()
        self._shop_current_loadout_targets = {}
        self._shop_loadout_details = {}
        self._shop_catalogue_upgrade_buttons = {}
        self._shop_loadout_upgrade_buttons = {}
        self._shop_buff_target_ids = {}
        self._shop_ap_purchase_rows = {}
        self._shop_cameo_images = {}
        self._shop_cameo_retry_after_id = None
        self._shop_cameo_retry_count = 0
        self._shop_launch_run = None
        self._shop_launch_mission_pool = ()

    def shop_mode_selected(self):
        return self.progression_mode_var.get() == 'Shop Mode'

    def shop_campaign_filter(self):
        return SHOP_FACTION_CAMPAIGNS.get(
            self.shop_faction_pool_var.get(), 'All Campaigns'
        )

    def shop_run_faction_filter(self, run=None):
        if run is None:
            return self.shop_campaign_filter()
        return str(
            run.reward_settings.get('shop_faction_filter')
            or run.campaign_filter
            or 'All Campaigns'
        )

    def on_shop_faction_pool_changed(self, _event=None):
        self.save_current_launcher_config()
        self.refresh_shop_mode()

    def save_current_launcher_config(self):
        self.config['shop_faction_pool'] = self.shop_faction_pool_var.get()
        self.config['shop_starting_buff_draft'] = (
            self.shop_starting_buff_draft_var.get()
        )
        self.config['shop_discount_specialization'] = (
            self.shop_discount_specialization_var.get()
        )
        return super().save_current_launcher_config()

    def apply_portable_settings(self, config):
        result = super().apply_portable_settings(config)
        saved = self.config.get('shop_faction_pool')
        self.shop_faction_pool_var.set(
            saved if saved in SHOP_FACTION_POOLS else SHOP_FACTION_POOLS[0]
        )
        draft = str(self.config.get('shop_starting_buff_draft') or 'Any Buff')
        if draft not in {item[0] for item in self.shop_buff_draft_options}:
            draft = 'Any Buff'
        self.shop_starting_buff_draft_var.set(draft)
        specialization = str(
            self.config.get('shop_discount_specialization') or 'Units'
        )
        if specialization not in SHOP_DISCOUNT_SPECIALIZATIONS:
            specialization = 'Units'
        self.shop_discount_specialization_var.set(specialization)
        return result

    def sync_shop_workspace(self):
        if not all(hasattr(self, name) for name in (
            'shop_tab', 'mission_view_frame', 'workspace_tabs'
        )):
            return
        selected_tab = self.workspace_tabs.select()
        tabs = set(self.workspace_tabs.tabs())
        shop_tab = str(self.shop_tab)
        mission_tab = str(self.mission_view_frame)
        advanced_tab = (
            str(self.advanced_tab) if hasattr(self, 'advanced_tab') else ''
        )
        if hasattr(self, 'seed_action_button'):
            self.seed_action_button.configure(
                text=(
                    'Start Shop Mode'
                    if self.shop_mode_selected()
                    else 'Generate Seed'
                )
            )
        if self.shop_mode_selected():
            replace_selected_tab = selected_tab == mission_tab
            if hasattr(self, 'settings_tab'):
                self.workspace_tabs.tab(self.settings_tab, text='Shop Setup')
            if mission_tab in tabs:
                self.workspace_tabs.forget(self.mission_view_frame)
            tabs = set(self.workspace_tabs.tabs())
            if shop_tab not in tabs:
                self.workspace_tabs.insert(0, self.shop_tab, text='Shop Mode')
            else:
                self.workspace_tabs.tab(self.shop_tab, text='Shop Mode')
            tabs = set(self.workspace_tabs.tabs())
            if advanced_tab and advanced_tab in tabs:
                was_advanced = selected_tab == advanced_tab
                self.workspace_tabs.forget(self.advanced_tab)
                if was_advanced and hasattr(self, 'settings_tab'):
                    self.workspace_tabs.select(self.settings_tab)
            if replace_selected_tab:
                needs_setup = bool(
                    self.shop_run is None
                    or self.shop_run.status is not RunStatus.ACTIVE
                )
                self.workspace_tabs.select(
                    self.settings_tab if needs_setup else self.shop_tab
                )
            self.sync_shop_settings_view()
            self.refresh_shop_mode()
            return

        replace_selected_tab = selected_tab == shop_tab
        if hasattr(self, 'settings_tab'):
            self.workspace_tabs.tab(self.settings_tab, text='Settings')
        if shop_tab in tabs:
            self.workspace_tabs.forget(self.shop_tab)
        tabs = set(self.workspace_tabs.tabs())
        progression_label = (
            'Grid Mode'
            if self.active_progression_mode() == 'Grid Mode'
            else 'Mission List'
        )
        if mission_tab not in tabs:
            self.workspace_tabs.insert(
                0, self.mission_view_frame, text=progression_label
            )
        else:
            self.workspace_tabs.tab(
                self.mission_view_frame, text=progression_label
            )
        tabs = set(self.workspace_tabs.tabs())
        if advanced_tab and advanced_tab not in tabs:
            if hasattr(self, 'archipelago_tab') and str(
                self.archipelago_tab
            ) in tabs:
                index = self.workspace_tabs.index(self.archipelago_tab)
                self.workspace_tabs.insert(
                    index, self.advanced_tab, text='Advanced'
                )
            else:
                self.workspace_tabs.add(self.advanced_tab, text='Advanced')
        if replace_selected_tab:
            self.workspace_tabs.select(self.mission_view_frame)
        self.sync_shop_settings_view()

    def sync_shop_settings_view(self, *, reset_scroll=False):
        if not all(hasattr(self, name) for name in (
            'settings_canvas', 'shop_settings_frame'
        )):
            return
        self.__dict__.pop('_settings_layout_signature', None)
        self.layout_settings_sections(self.settings_canvas.winfo_width())
        self.refresh_shop_settings_controls()
        if reset_scroll:
            self.settings_canvas.yview_moveto(0)

    def refresh_shop_settings_controls(self):
        if not hasattr(self, 'shop_setup_start_button'):
            return
        locked = self.gameplay_settings_locked()
        active = bool(
            self.shop_run is not None
            and self.shop_run.status is RunStatus.ACTIVE
        )
        self.shop_progression_mode_combo.configure(
            state='disabled' if locked else 'readonly'
        )
        self.shop_seed_entry.configure(
            state='disabled' if locked or active else 'normal'
        )
        self.shop_setup_start_button.configure(
            state='disabled' if locked or active else 'normal',
            text='Run Active' if active else 'Start Shop Mode',
        )
        self.shop_faction_pool_combo.configure(
            state='disabled' if locked or active else 'readonly'
        )
        setup_combos = (
            (
                self.shop_starting_buff_draft_combo,
                'starting_buff_draft',
            ),
            (
                self.shop_discount_specialization_combo,
                'discount_specialization',
            ),
        )
        for combo, upgrade_id in setup_combos:
            combo.configure(
                state=(
                    'disabled'
                    if locked or active
                    or self.shop_profile.upgrade_level(upgrade_id) <= 0
                    else 'readonly'
                )
            )
        for combo in (
            self.shop_game_speed_combo,
            self.shop_difficulty_combo,
        ):
            combo.configure(state='disabled' if locked else 'readonly')

    def on_progression_mode_changed(self, event=None):
        self.sync_shop_workspace()
        self.sync_shop_settings_view(reset_scroll=True)
        result = super().on_progression_mode_changed(event)
        if (
            self.shop_mode_selected()
            or self.config.get('progression_mode') == 'Shop Mode'
        ):
            self.save_current_launcher_config()
        return result

    def on_new_seed(self):
        if self.shop_mode_selected():
            self.start_shop_run()
            return
        return super().on_new_seed()

    def shop_launch_active(self):
        return getattr(self, '_shop_launch_run', None) is not None

    def randomizer_launch_active(self):
        if self.shop_launch_active():
            return True
        return super().randomizer_launch_active()

    def active_launch_seed(self):
        if self.shop_launch_active():
            return self._shop_launch_run.seed
        return super().active_launch_seed()

    def active_launch_campaign_filter(self):
        if self.shop_launch_active():
            return self._shop_launch_run.campaign_filter
        return super().active_launch_campaign_filter()

    def launch_state_document(self):
        if self.shop_launch_active():
            run = self._shop_launch_run
            return {
                'seed': run.seed,
                'campaign_filter': run.campaign_filter,
                'progression_mode': 'Shop Mode',
                'completed_missions': list(run.completed_missions),
            }
        return super().launch_state_document()

    def active_reward_mode(self):
        run = self._shop_context_run()
        if run is not None:
            return run.reward_mode
        if self._shop_mode_context_selected():
            return SHOP_REWARD_MODE
        return super().active_reward_mode()

    def active_progression_mode(self):
        if self._shop_mode_context_selected():
            return 'Shop Mode'
        return super().active_progression_mode()

    def active_reward_settings(self):
        run = self._shop_context_run()
        if run is not None:
            settings = dict(run.reward_settings)
            settings['start_with_tier_one_units'] = True
            settings['start_with_tier_one_defenses'] = True
            settings['failure_assistance'] = False
            mission_modifier = self._active_shop_mission_modifier(run)
            if mission_modifier is not None and mission_modifier.buffs_allied_helpers:
                settings['buff_allied_helpers'] = True
            return settings
        return super().active_reward_settings()

    def active_launch_rewards(self):
        if self.shop_launch_active():
            rewards = list(active_shop_rewards(self._shop_launch_run))
            starting_credit_level = self.shop_profile.upgrade_level(
                'mission_starting_credits'
            )
            rewards.extend(
                canonical_reward_for_id('Starting Credits +1,000')
                for _index in range(starting_credit_level)
            )
            mission_modifier = self._active_shop_mission_modifier(
                self._shop_launch_run
            )
            if mission_modifier is not None:
                for reward_id in mission_modifier.player_reward_ids:
                    reward = dict(canonical_reward_for_id(reward_id))
                    if reward.get('kind') == 'superweapon':
                        reward['superweapon_ignore_foreign_tech_gate'] = True
                    rewards.append(reward)
            return rewards
        return super().active_launch_rewards()

    def active_enemy_scaling_entries(self):
        if self.shop_launch_active():
            mission_modifier = self._active_shop_mission_modifier(
                self._shop_launch_run
            )
            if mission_modifier is None or not mission_modifier.enemy_reward_id:
                return []
            return [{
                'reward': canonical_reward_for_id(
                    mission_modifier.enemy_reward_id
                ),
                'source': 'Shop mission challenge',
                'earned_from': mission_modifier.title,
            }]
        return super().active_enemy_scaling_entries()

    def launch_rewards_for_mission(self, code):
        if self.shop_launch_active():
            return self.active_launch_rewards()
        return super().launch_rewards_for_mission(code)

    def active_starting_rewards_for_report(self):
        run = self._shop_context_run()
        if run is not None:
            return [
                canonical_reward_for_id(reward_id)
                for reward_id in run.selected_permanent_units
            ]
        return super().active_starting_rewards_for_report()

    def active_progression_rewards_for_report(self):
        run = self._shop_context_run()
        if run is not None:
            reward_ids = [
                *ap_automatic_reward_ids(run.ap_entitlements_snapshot),
                *(
                    item.reward_id
                    for item in run.permanent_buffs_snapshot
                    for _index in range(item.stacks)
                ),
                *(item.reward_id for item in run.run_purchases),
                *(item.reward_id for item in run.run_buffs),
                *(
                    item.reward_id
                    for item in run.starting_draft_buffs
                    for _index in range(item.stacks)
                ),
            ]
            return [canonical_reward_for_id(item) for item in reward_ids]
        return super().active_progression_rewards_for_report()

    def active_starting_tier_one_unit_ids(self):
        run = self._shop_context_run()
        if run is not None:
            return list(run.starting_unit_ids)
        if self._shop_mode_context_selected():
            return []
        return super().active_starting_tier_one_unit_ids()

    def active_starting_tier_one_defense_ids(self):
        run = self._shop_context_run()
        if run is not None:
            return list(run.starting_defense_ids)
        if self._shop_mode_context_selected():
            return []
        return super().active_starting_tier_one_defense_ids()

    def randomize_unit_access_enabled(self):
        if self._shop_mode_context_selected():
            return True
        return super().randomize_unit_access_enabled()

    def active_standard_starter_families(self):
        run = self._shop_context_run()
        if run is not None:
            return tuple(STANDARD_STARTER_FAMILIES_BY_CAMPAIGN.get(
                run.campaign_filter,
                ('allies', 'soviets', 'epsilon'),
            ))
        return super().active_standard_starter_families()

    def share_chaos_role_buffs_enabled(self):
        run = self._shop_context_run()
        if run is not None:
            return bool(
                (
                    run.reward_mode == 'Chaos'
                    or run.campaign_filter == 'All Campaigns'
                )
                and run.reward_settings.get('share_chaos_role_buffs', False)
            )
        return super().share_chaos_role_buffs_enabled()

    def foehn_standard_bundles_enabled(self):
        run = self._shop_context_run()
        if run is not None:
            return bool(
                run.campaign_filter == 'Foehn'
                and run.reward_mode == 'Standard'
            )
        return super().foehn_standard_bundles_enabled()

    def failure_assistance_enabled(self):
        if self._shop_mode_context_selected():
            return False
        return super().failure_assistance_enabled()

    def mission_failure_stack(self, code):
        if self._shop_mode_context_selected():
            return 0
        return super().mission_failure_stack(code)

    def cache_mission_assistance_units(self, code, unit_ids):
        if self._shop_mode_context_selected():
            return
        return super().cache_mission_assistance_units(code, unit_ids)

    def enemy_scaling_dashboard_rows(self):
        if self._shop_mode_context_selected():
            return []
        return super().enemy_scaling_dashboard_rows()

    def record_enemy_reward_applications(self, code, applications):
        if self.shop_launch_active():
            return
        return super().record_enemy_reward_applications(code, applications)

    def _shop_reroll_capacity(self):
        level = self.shop_profile.upgrade_level('mission_reroll')
        per_level = self.shop_config.permanent_upgrades[
            'mission_reroll'
        ].effects['rerolls_per_level']
        return level * int(per_level)

    def _shop_difficulty_assist_capacity(self):
        level = self.shop_profile.upgrade_level('mission_difficulty_assist')
        per_level = self.shop_config.permanent_upgrades[
            'mission_difficulty_assist'
        ].effects['assists_per_level']
        return level * int(per_level)

    def _shop_challenge_slots(self):
        definition = self.shop_config.permanent_upgrades[
            'permanent_challenge_slots'
        ]
        return self.shop_profile.upgrade_level(
            'permanent_challenge_slots'
        ) * int(definition.effects['slots_per_level'])

    def _active_shop_mission_modifier(self, run):
        return active_mission_modifier(
            run, challenge_slots=self._shop_challenge_slots()
        )

    def shop_eased_difficulty_labels(self):
        labels = [name for name, _value in DIFFICULTIES]
        current = self.difficulty_var.get()
        try:
            index = labels.index(current)
        except ValueError:
            index = 1
        return current, labels[max(0, index - 1)]

    def get_selected_difficulty_value(self):
        value = super().get_selected_difficulty_value()
        run = self.__dict__.get('_shop_launch_run')
        if (
            run is not None
            and run.selected_mission_code
            and run.assisted_mission_code == run.selected_mission_code
        ):
            return max(0, value - 1)
        return value

    def _shop_mission(self, code):
        return self._mission_by_code.get(str(code).upper(), {})

    def _shop_entry_available(self, entry, run=None):
        if run is None:
            reward_mode = SHOP_REWARD_MODE
            campaign_filter = self.shop_campaign_filter()
        else:
            reward_mode = run.reward_mode
            campaign_filter = self.shop_run_faction_filter(run)
        return shop_entry_available(
            entry,
            campaign_filter=campaign_filter,
            reward_mode=reward_mode,
            strict_faction=True,
        )

    def _set_shop_message(self, message, *, error=False):
        self.shop_message_var.set(str(message))
        if hasattr(self, 'append_log'):
            self.append_log(str(message), error=error)

    def refresh_shop_mode(self, *_args):
        if not hasattr(self, 'shop_stage_var'):
            return
        self.shop_profile, self.shop_run = self.shop_repository.load()
        self.shop_run = self._repair_shop_mission_offers(self.shop_run)
        ap_identity, ap_reward_ids = self.archipelago_shop_context()
        if self.shop_run is not None and self.shop_run.status is RunStatus.ACTIVE:
            self.shop_run = self.shop_service.sync_archipelago_entitlements(
                ap_identity, ap_reward_ids, current_run=self.shop_run
            )
        run = self.shop_run
        if run is None:
            self.shop_stage_var.set(f'Run — / {self.shop_config.run_length}')
            self.shop_status_var.set('Status: No Run')
            self.shop_run_coins_var.set('Ore: 0')
        else:
            self.shop_stage_var.set(f'Run {run.stage} / {run.run_length}')
            self.shop_status_var.set(f'Status: {run.status.value.title()}')
            self.shop_run_coins_var.set(f'Ore: {run.run_coins}')
        if hasattr(self, 'shop_status_label'):
            status_style = (
                'Shop.Status.TLabel'
                if run is None or run.status is RunStatus.ACTIVE
                else 'Error.TLabel'
                if run.status is RunStatus.FAILED
                else 'Shop.Mental.TLabel'
            )
            self.shop_status_label.configure(style=status_style)
        self.shop_meta_coins_var.set(
            f'Mental Coins: {self.shop_profile.meta_coins}'
        )
        capacity = self._shop_reroll_capacity()
        used = run.rerolls_used if run is not None else 0
        self.shop_rerolls_var.set(f'Rerolls: {used} / {capacity}')
        self._refresh_shop_missions()
        self.refresh_shop_catalogue()
        self._refresh_shop_loadout()
        self._refresh_shop_setup()
        self._refresh_permanent_shop()
        self._refresh_shop_history()
        self._refresh_archipelago_shop_purchases()
        self.refresh_shop_settings_controls()
        self.refresh_progress_view()

    def _shop_unit_id_for_item(self, item_id):
        entry = catalogue_entry(canonical_reward_for_id(item_id))
        if entry is not None and entry.reward_type in {
            ShopRewardType.UNIT_ACCESS,
            ShopRewardType.UNIT_BUFF,
        }:
            return entry.target_id
        raw = str(item_id or '').upper()
        return raw if raw and ' ' not in raw else ''

    def _shop_power_cameo_for_item(self, item_id):
        reward = canonical_reward_for_id(item_id)
        entry = catalogue_entry(reward)
        if entry is None or entry.reward_type not in {
            ShopRewardType.POWER_ACCESS,
            ShopRewardType.POWER_BUFF,
        }:
            return '', '', ''
        power_id = str(
            reward.get('cameo_superweapon')
            or reward.get('superweapon')
            or entry.target_id
            or ''
        ).upper()
        sidebar_override = str(
            (reward.get('superweapon_rules') or {}).get('SidebarPCX') or ''
        )
        return (
            power_id,
            str(reward.get('superweapon_sidebar_image') or ''),
            sidebar_override,
        )

    def _schedule_shop_cameo_retry(self):
        if (
            self._shop_cameo_retry_after_id is not None
            or self._shop_cameo_retry_count >= 20
            or not cameo_extraction_pending()
        ):
            return
        self._shop_cameo_retry_count += 1

        def retry():
            self._shop_cameo_retry_after_id = None
            if hasattr(self, 'shop_stage_var'):
                self.refresh_shop_mode()

        self._shop_cameo_retry_after_id = self.after(1000, retry)

    def _prepare_shop_unit_cameos(self, item_ids):
        item_ids = tuple(str(item_id) for item_id in item_ids)
        unit_by_item = {
            item_id: self._shop_unit_id_for_item(item_id)
            for item_id in item_ids
        }
        power_by_item = {
            item_id: self._shop_power_cameo_for_item(item_id)
            for item_id in item_ids
        }
        unit_ids = {
            unit_id for unit_id in unit_by_item.values() if unit_id
        }
        missing = [
            unit_id for unit_id in unit_ids
            if not self._shop_cameo_images.get(f'unit:{unit_id}')
        ]
        if missing:
            try:
                paths = ensure_unit_cameos(missing)
            except Exception:
                paths = {}
            for unit_id in missing:
                path = paths.get(unit_id)
                if not path:
                    self._shop_cameo_images[f'unit:{unit_id}'] = None
                    continue
                try:
                    self._shop_cameo_images[f'unit:{unit_id}'] = tk.PhotoImage(
                        master=self, file=str(path)
                    )
                except tk.TclError:
                    self._shop_cameo_images[f'unit:{unit_id}'] = None
        power_ids = {
            power_id
            for power_id, _asset_name, _sidebar_override
            in power_by_item.values()
            if power_id
        }
        power_sidebar_overrides = {
            power_id: sidebar_override
            for power_id, _asset_name, sidebar_override
            in power_by_item.values()
            if power_id and sidebar_override
        }
        power_paths = {}
        missing_power_ids = [
            power_id for power_id in power_ids
            if not self._shop_cameo_images.get(f'power:{power_id}')
        ]
        if missing_power_ids:
            try:
                power_paths = ensure_superweapon_cameos(
                    missing_power_ids, power_sidebar_overrides
                )
            except Exception:
                power_paths = {}
            for power_id in missing_power_ids:
                path = power_paths.get(power_id)
                if not path:
                    self._shop_cameo_images[f'power:{power_id}'] = None
                    continue
                try:
                    self._shop_cameo_images[f'power:{power_id}'] = tk.PhotoImage(
                        master=self, file=str(path)
                    )
                except tk.TclError:
                    self._shop_cameo_images[f'power:{power_id}'] = None
        for item_id, (
            power_id, asset_name, _sidebar_override
        ) in power_by_item.items():
            if not power_id or not asset_name:
                continue
            cache_key = f'power:{power_id}'
            if self._shop_cameo_images.get(cache_key):
                continue
            try:
                path = custom_sidebar_preview(asset_name)
                self._shop_cameo_images[cache_key] = tk.PhotoImage(
                    master=self, file=str(path)
                )
            except Exception:
                self._shop_cameo_images[cache_key] = None
        if any(
            not self._shop_cameo_images.get(f'power:{power_id}')
            for power_id in power_ids
        ):
            self._schedule_shop_cameo_retry()
        else:
            self._shop_cameo_retry_count = 0
        return {
            item_id: (
                self._shop_cameo_images.get(
                    f'power:{power_by_item[item_id][0]}'
                )
                if power_by_item[item_id][0]
                else self._shop_cameo_images.get(
                    f'unit:{unit_by_item[item_id]}'
                )
            )
            for item_id in item_ids
        }

    def give_up_shop_run(self):
        run = self.shop_run
        if (
            run is None
            or run.status is not RunStatus.ACTIVE
            or self.shop_launch_active()
        ):
            return
        if not messagebox.askyesno(
            'Give Up Shop Run?',
            'End this run now?\n\n'
            'Run Ore and run purchases will be abandoned. '
            'Mental Coins and permanent unlocks are kept.',
            parent=self,
        ):
            return
        try:
            self.shop_service.give_up_run()
        except ShopTransitionError as exc:
            self._set_shop_message(exc, error=True)
        else:
            self._set_shop_message(
                f'Gave up Shop run at stage {run.stage}. You can start a new run.'
            )
        self.refresh_shop_mode()
        if self.shop_run is not None and self.shop_run.status is not RunStatus.ACTIVE:
            self.workspace_tabs.select(self.settings_tab)
            self.sync_shop_settings_view(reset_scroll=True)

    def _repair_shop_mission_offers(self, run):
        if (
            run is None
            or run.status is not RunStatus.ACTIVE
            or run.mission_committed
            or not self.missions
        ):
            return run
        allowed = mission_classes_for_stage(run.stage, run.run_length)
        offers_valid = bool(
            len(run.mission_offers) == self.shop_config.mission_offer_count
            and all(
                offer.economy_class in allowed
                for offer in run.mission_offers
            )
        )
        if offers_valid:
            return run
        offers = generate_mission_offers(
            self._shop_run_mission_pool(run),
            run_seed=run.seed,
            stage=run.stage,
            run_length=run.run_length,
            completed_codes=run.completed_missions,
            reroll_count=run.rerolls_used,
        )
        if len(offers) != self.shop_config.mission_offer_count:
            return run
        repaired = replace(
            run,
            mission_offers=offers,
            selected_mission_code='',
        )
        self.shop_repository.save_run(repaired)
        self._set_shop_message(
            f'Updated stage {run.stage} offers for gradual Shop difficulty.'
        )
        return repaired

    def reroll_shop_mission(self, index):
        if self.shop_launch_active():
            self._set_shop_message('Wait for current mission process to close.')
            return
        run = self.shop_run
        if run is None:
            self.shop_loadout_upgrade_button.configure(state='disabled')
            return
        try:
            mission_pool = self._shop_run_mission_pool(run)
            index = int(index)
            replaced = run.mission_offers[index]
            kept_codes = tuple(
                offer.mission_code
                for offer_index, offer in enumerate(run.mission_offers)
                if offer_index != index
            )
            replacement = generate_mission_offers(
                mission_pool,
                run_seed=run.seed,
                stage=run.stage,
                run_length=run.run_length,
                completed_codes=run.completed_missions + kept_codes,
                reroll_count=run.rerolls_used + 1,
                previous_offer_codes=(replaced.mission_code,),
                offer_count=1,
            )
            if len(replacement) != 1:
                raise ShopTransitionError('No replacement mission is available')
            offers = list(run.mission_offers)
            offers[index] = replacement[0]
            self.shop_service.reroll(
                offers, replaced_mission_code=replaced.mission_code
            )
        except (IndexError, ShopTransitionError, ValueError) as exc:
            self._set_shop_message(exc, error=True)
        else:
            self._set_shop_message(
                f'Rerolled only {replaced.mission_code}; other choices kept.'
            )
        self.refresh_shop_mode()

    def reroll_shop_missions(self):
        self._set_shop_message('Use Reroll This Mission under chosen card.')

    def ease_shop_mission(self, index):
        run = self.shop_run
        if run is None:
            return
        try:
            code = run.mission_offers[int(index)].mission_code
            self.shop_service.ease_mission(code)
        except (IndexError, ShopTransitionError, ValueError) as exc:
            self._set_shop_message(exc, error=True)
        else:
            normal, eased = self.shop_eased_difficulty_labels()
            self._set_shop_message(
                f'{code} eased from {normal} to {eased}; reward unchanged.'
            )
        self.refresh_shop_mode()

    def on_launch_selected(self):
        if self.shop_mode_selected():
            self.launch_selected_shop_mission()
            return
        return super().on_launch_selected()

    def launch_shop_mission(self, index):
        """Select and launch one offer directly from its mission card."""
        if self.shop_launch_active():
            self._set_shop_message('Another mission is already running.')
            return
        self.shop_profile, run = self.shop_repository.load()
        self.shop_run = run
        try:
            if run is None or run.status is not RunStatus.ACTIVE:
                raise ShopTransitionError('No active Shop run can be launched')
            code = self.shop_mission_cards[int(index)]['code']
            if not code:
                raise ShopTransitionError('No mission exists in this slot')
            if run.mission_committed:
                if run.selected_mission_code != code:
                    raise ShopTransitionError(
                        f'Shop stage is committed to {run.selected_mission_code}'
                    )
            else:
                self.shop_service.select_mission(code)
        except (IndexError, ShopTransitionError, ValueError) as exc:
            self._set_shop_message(exc, error=True)
            self.refresh_shop_mode()
            return
        self.launch_selected_shop_mission()

    def launch_selected_shop_mission(self):
        self.shop_profile, run = self.shop_repository.load()
        self.shop_run = run
        try:
            process = getattr(self, 'active_game_process', None)
            if process is not None and process.poll() is None:
                raise ShopTransitionError('Another mission is already running')
            missing = [
                path for path in (GAME_LAUNCHER_EXE, GAME_EXE)
                if not path.exists()
            ]
            if missing:
                raise ShopTransitionError(
                    'Missing launch executable(s): '
                    + ', '.join(str(path) for path in missing)
                )
            if run is None or run.status is not RunStatus.ACTIVE:
                raise ShopTransitionError('No active Shop run can be launched')
            code = str(run.selected_mission_code or '').upper()
            offered = {offer.mission_code for offer in run.mission_offers}
            if not code or code not in offered:
                raise ShopTransitionError(
                    'Select one current Shop mission before launching'
                )
            if code in set(run.completed_missions):
                raise ShopTransitionError(
                    f'Shop mission {code} is already completed'
                )
            if run.mission_committed and run.selected_mission_code != code:
                raise ShopTransitionError(
                    f'Shop stage is committed to {run.selected_mission_code}'
                )
            mission = self._shop_mission(code)
            if not mission or not mission.get('scenario'):
                raise ShopTransitionError(
                    f'Shop mission data is missing for {code}'
                )
            committed = self.shop_service.commit_mission(code)
        except ShopTransitionError as exc:
            self._set_shop_message(exc, error=True)
            messagebox.showwarning('Cannot Launch Shop Mission', str(exc), parent=self)
            self.refresh_shop_mode()
            return

        self._shop_launch_run = committed
        self._shop_launch_mission_pool = tuple(
            self._shop_run_mission_pool(committed)
        )
        self.shop_run = committed
        self.save_current_launcher_config()
        self._set_shop_message(
            f'Launching committed Shop mission {code}. '
            'Other offers and purchases are now locked.'
            + (
                f' Mission effect: {modifier.title} — '
                f'{modifier.description}'
                if (
                    modifier := self._active_shop_mission_modifier(committed)
                ) is not None
                else ''
            )
        )
        self.refresh_shop_mode()
        self.launch_mission_async(
            mission,
            launch_note=(
                f'Shop Mode stage {committed.stage}/{committed.run_length}; '
                f'{committed.run_coins} Ore before mission.'
            ),
        )

    def mission_checks(self, code):
        if not self.shop_launch_active():
            return super().mission_checks(code)
        code = str(code or '').upper()
        run = self.shop_repository.load_run() or self._shop_launch_run
        if code != str(run.selected_mission_code or '').upper():
            return []
        return [{
            'id': 'victory',
            'name': 'Mission Victory',
            'description': 'Win the committed Shop mission.',
            'rewards': [],
            'unlocked': code in set(run.completed_missions),
        }]

    def is_mission_complete(self, code):
        if not self.shop_launch_active():
            return super().is_mission_complete(code)
        run = self.shop_repository.load_run() or self._shop_launch_run
        return str(code or '').upper() in set(run.completed_missions)

    def unlock_mission_check(self, code, check_id, source):
        if not self.shop_launch_active():
            return super().unlock_mission_check(code, check_id, source)
        code = str(code or '').upper()
        if check_id != 'victory':
            return False
        run = self.shop_repository.load_run()
        if (
            run is None
            or run.run_id != self._shop_launch_run.run_id
            or run.status is not RunStatus.ACTIVE
            or not run.mission_committed
            or run.selected_mission_code != code
        ):
            return False
        try:
            next_offers = ()
            if run.stage < run.run_length:
                next_offers = generate_mission_offers(
                    self._shop_launch_mission_pool,
                    run_seed=run.seed,
                    stage=run.stage + 1,
                    run_length=run.run_length,
                    completed_codes=run.completed_missions + (code,),
                )
            transition = self.shop_service.record_victory(
                code, next_offers=next_offers
            )
        except (ShopTransitionError, ValueError) as exc:
            self._set_shop_message(exc, error=True)
            return False
        if not transition.changed:
            return False
        self._shop_launch_run = transition.run
        self.shop_profile = transition.profile
        self.shop_run = transition.run
        self.show_shop_victory_result(source, code, run, transition)
        self.record_archipelago_shop_victory(run.stage, transition)
        self.refresh_shop_mode()
        return True

    def record_failed_mission_attempt(self, code, source):
        if not self.shop_launch_active():
            return super().record_failed_mission_attempt(code, source)
        code = str(code or '').upper()
        run = self.shop_repository.load_run()
        if (
            run is None
            or run.run_id != self._shop_launch_run.run_id
            or run.status is not RunStatus.ACTIVE
            or not run.mission_committed
            or run.selected_mission_code != code
            or code in set(run.completed_missions)
        ):
            return False
        try:
            revival_definition = self.shop_config.permanent_upgrades[
                'emergency_revival'
            ]
            revival_capacity = (
                self.shop_profile.upgrade_level('emergency_revival')
                * int(revival_definition.effects['revivals_per_run'])
            )
            revival_offers = ()
            if run.emergency_revivals_used < revival_capacity:
                revival_offers = generate_mission_offers(
                    self._shop_launch_mission_pool,
                    run_seed=run.seed,
                    stage=run.stage,
                    run_length=run.run_length,
                    completed_codes=run.completed_missions + (code,),
                    reroll_count=(
                        run.rerolls_used + run.emergency_revivals_used + 101
                    ),
                    previous_offer_codes=(
                        offer.mission_code for offer in run.mission_offers
                    ),
                )
            transition = self.shop_service.record_failure(
                code, revival_offers=revival_offers
            )
        except ShopTransitionError as exc:
            self._set_shop_message(exc, error=True)
            return False
        if not transition.changed:
            return False
        self._shop_launch_run = transition.run
        self.shop_run = transition.run
        self.show_shop_failure_result(source, code, transition)
        self.refresh_shop_mode()
        return True

    def finish_progression_launch_context(self):
        if not self.shop_launch_active():
            return
        self._shop_launch_run = None
        self._shop_launch_mission_pool = ()
        if hasattr(self, 'shop_stage_var'):
            self.refresh_shop_mode()

    def on_debug_mark_complete(self):
        if not self.shop_mode_selected():
            return super().on_debug_mark_complete()
        self.shop_profile, run = self.shop_repository.load()
        if run is None or run.status is not RunStatus.ACTIVE:
            messagebox.showwarning('Shop Mode', 'No active Shop run.', parent=self)
            return
        code = str(run.selected_mission_code or '').upper()
        if not code:
            messagebox.showwarning(
                'Shop Mode', 'Select a Shop mission first.', parent=self
            )
            return
        try:
            run = self.shop_service.commit_mission(code)
            self._shop_launch_run = run
            self._shop_launch_mission_pool = tuple(
                self._shop_run_mission_pool(run)
            )
            self.unlock_mission_check(code, 'victory', 'Debug override')
        finally:
            self.finish_progression_launch_context()

    def _selected_loadout_reward_ids(self):
        self.capture_shop_setup_selection()
        return tuple(sorted(self._shop_pending_loadout_selection))

    def capture_shop_setup_selection(self, _event=None):
        if not hasattr(self, 'shop_loadout_select_tree'):
            return
        visible = set(self._shop_loadout_rows.values())
        selected = {
            self._shop_loadout_rows[item]
            for item in self.shop_loadout_select_tree.selection()
            if item in self._shop_loadout_rows
        }
        self._shop_pending_loadout_selection.difference_update(visible)
        self._shop_pending_loadout_selection.update(selected)

    def shop_reward_settings_for_new_run(self):
        """Remove hidden normal-mode tuning from Shop Mode run behavior."""
        settings = dict(self.current_reward_settings())
        settings.update({
            'randomize_unit_access': True,
            'start_with_tier_one_units': True,
            'start_with_tier_one_defenses': True,
            'starting_reward_count': 0,
            'starting_unlock_rewards': [],
            'include_defensive_buildings': True,
            'include_special_buildings': True,
            'include_special_rewards': True,
            'unlimited_hero_units': False,
            'share_chaos_role_buffs': False,
            'buff_allied_helpers': False,
            'failure_assistance': False,
            'include_buff_rewards': True,
            'include_superweapon_rewards': True,
            'include_secondary_superweapon_rewards': True,
            'include_aid_power_rewards': True,
            'include_power_buff_rewards': True,
            'enabled_reward_types': [
                'access', 'buff', 'superweapon',
                'secondary_superweapon', 'aid_power', 'power_buff',
            ],
            'enabled_buff_types': [
                definition['id'] for definition in BUFF_TYPES
            ],
            'enabled_power_buff_types': [
                definition['id'] for definition in POWER_BUFF_TYPES
            ],
            'excluded_unit_access_ids': [],
            'excluded_superweapon_ids': [],
            'excluded_unit_buff_types': {},
            'excluded_power_buff_types': {},
        })
        enemy_scaling = dict(settings.get('enemy_scaling') or {})
        enemy_scaling['maximum_total_buffs'] = 0
        settings['enemy_scaling'] = enemy_scaling
        return settings

    def _starting_buff_draft(self, seed, active_target_ids):
        level = self.shop_profile.upgrade_level('starting_buff_draft')
        per_level = int(self.shop_config.permanent_upgrades[
            'starting_buff_draft'
        ].effects['buffs_per_level'])
        count = level * per_level
        if count <= 0:
            return ()
        selected_label = self.shop_starting_buff_draft_var.get()
        selected_type = dict(self.shop_buff_draft_options).get(
            selected_label, ''
        )
        preferred = []
        fallback = []
        for entry in self._shop_buff_entries:
            if (
                entry.tier != 'tier_1'
                or entry.target_id not in active_target_ids
                or not self._shop_entry_available(entry)
            ):
                continue
            reward = canonical_reward_for_id(entry.reward_id)
            if selected_type and reward.get('buff_type') == selected_type:
                preferred.append(entry)
            else:
                fallback.append(entry)
        sort_key = lambda entry: (
            sha256(
                f'{seed}\0starting_buff_draft\0{entry.reward_id}'.encode(
                    'utf-8'
                )
            ).digest(),
            entry.reward_id,
        )
        preferred.sort(key=sort_key)
        fallback.sort(key=sort_key)
        candidates = preferred + fallback
        return tuple(
            BuffPurchase(entry.reward_id, 1) for entry in candidates[:count]
        )

    def start_shop_run(self):
        if not self.missions:
            messagebox.showwarning(
                'Shop Mode', 'Mission data is still loading.', parent=self
            )
            return
        if self.shop_run is not None and self.shop_run.status is RunStatus.ACTIVE:
            messagebox.showwarning(
                'Shop Mode',
                'The current Shop run must finish or fail before a new run.',
                parent=self,
            )
            return
        seed = self.seed_var.get().strip() or uuid.uuid4().hex[:16].upper()
        salvaged_ore = self.shop_profile.salvaged_run_coins
        self.seed_var.set(seed)
        settings = self.shop_reward_settings_for_new_run()
        faction_filter = self.shop_campaign_filter()
        settings['shop_faction_filter'] = faction_filter
        settings['shop_discount_specialization'] = (
            self.shop_discount_specialization_var.get()
        )
        previous_context = self.__dict__.get('_seed_generation_context')
        self._seed_generation_context = {
            'campaign_filter': faction_filter,
            'reward_mode': SHOP_REWARD_MODE,
        }
        try:
            starting_units = self.starting_tier_one_unit_ids_for_seed(
                seed, settings
            )
            starting_defenses = self.starting_tier_one_defense_ids_for_seed(
                settings, seed=seed
            )
        finally:
            self._seed_generation_context = previous_context
        starter_tech_ids = set(expanded_tier_one_unit_ids(starting_units))
        starter_tech_ids.update(
            expanded_tier_one_defense_ids(starting_defenses)
        )
        ap_identity, ap_reward_ids = self.archipelago_shop_context()
        maximum_extra_units = (
            self.shop_config.max_selected_permanent_units
            + self.shop_profile.upgrade_level('expanded_loadout')
            * int(self.shop_config.permanent_upgrades[
                'expanded_loadout'
            ].effects['slots_per_level'])
        )
        selected = self._selected_loadout_reward_ids()
        if (
            ap_identity
            and self.archipelago_received_unit_loadout_mode()
            == ARCHIPELAGO_RECEIVED_UNIT_LOADOUT_RANDOM
        ):
            permanent_entitlements = set(
                self.shop_profile.permanent_unit_unlocks
            )
            selected = tuple(
                reward_id for reward_id in selected
                if reward_id in permanent_entitlements
            )
            local_loadout = validate_starting_loadout(
                starter_tech_ids=starter_tech_ids,
                selected_reward_ids=selected,
                entitled_reward_ids=permanent_entitlements,
                maximum_extra_units=maximum_extra_units,
            )
            active_tech_ids = set(local_loadout.active_tech_ids)
            eligible_ap_units = tuple(
                reward_id
                for reward_id in ap_unit_entitlement_ids(ap_reward_ids)
                for entry in [self._shop_entry_by_reward_id.get(reward_id)]
                if (
                    entry is not None
                    and entry.target_id not in active_tech_ids
                    and self._shop_entry_available(entry)
                )
            )
            selected += random_ap_unit_entitlement_ids(
                eligible_ap_units,
                run_seed=seed,
                run_number=self.shop_profile.lifetime_runs_started + 1,
                maximum_count=(
                    max(
                        0,
                        maximum_extra_units - local_loadout.extra_slots_used,
                    )
                    if local_loadout.allowed else 0
                ),
                ap_identity=ap_identity,
                excluded_reward_ids=selected,
            )
        permanent_buff_targets = set(starter_tech_ids)
        permanent_buff_targets.update(
            entry.target_id
            for reward_id in selected
            for entry in [self._shop_entry_by_reward_id.get(reward_id)]
            if entry is not None and entry.target_id
        )
        starting_draft_buffs = self._starting_buff_draft(
            seed, permanent_buff_targets
        )
        permanent_buffs = tuple(
            item for item in self.shop_profile.permanent_buffs
            if (
                (entry := self._shop_entry_by_reward_id.get(item.reward_id))
                is not None
                and entry.target_id in permanent_buff_targets
            )
        )
        modifiers = tuple(
            modifier_id for modifier_id, variable in self.shop_modifier_vars.items()
            if variable.get()
        )
        try:
            mission_pool = self._shop_run_mission_pool()
            if len(mission_pool) < self.shop_config.run_length:
                raise ShopTransitionError(
                    f'Shop Mode needs at least {self.shop_config.run_length} '
                    'eligible missions under current filters'
                )
            offers = generate_mission_offers(
                mission_pool,
                run_seed=seed,
                stage=1,
            )
            if len(offers) != self.shop_config.mission_offer_count:
                raise ShopTransitionError(
                    'Shop Mode needs at least '
                    f'{self.shop_config.mission_offer_count} eligible Act 1 '
                    'missions for its protected opening'
                )
            self.shop_service.start_run(
                run_id=uuid.uuid4().hex,
                seed=seed,
                mission_offers=offers,
                campaign_filter='All Campaigns',
                reward_mode=SHOP_REWARD_MODE,
                reward_settings=settings,
                eligible_mission_codes=(
                    mission.get('code') for mission in mission_pool
                ),
                starter_tech_ids=starter_tech_ids,
                starting_unit_ids=starting_units,
                starting_defense_ids=starting_defenses,
                selected_reward_ids=selected,
                permanent_entitlement_ids=(
                    self.shop_profile.permanent_unit_unlocks
                ),
                permanent_buffs=permanent_buffs,
                starting_draft_buffs=starting_draft_buffs,
                maximum_extra_units=maximum_extra_units,
                ap_entitlement_ids=ap_reward_ids,
                ap_identity=ap_identity,
                modifiers=modifiers,
            )
            self.save_current_launcher_config()
        except (ShopTransitionError, ValueError) as exc:
            self._set_shop_message(exc, error=True)
            messagebox.showerror('Shop Run Failed', str(exc), parent=self)
        else:
            self._set_shop_message(
                f'Started Shop run with seed {seed}. '
                f'Starting draft: {len(starting_draft_buffs)} buff(s).'
                + (
                    f' Recovery Salvage added {salvaged_ore} Ore.'
                    if salvaged_ore else ''
                )
            )
            self.shop_panels.select(0)
            self.sync_shop_workspace()
            self.workspace_tabs.select(self.shop_tab)
        self.refresh_shop_mode()

    def buy_selected_shop_reward(self, _event=None):
        if self.shop_launch_active():
            self._set_shop_message('Wait for current mission process to close.')
            return
        selected = self.shop_catalogue_tree.selection()
        if not selected:
            return
        reward_id = self._shop_catalogue_rows.get(selected[0])
        if not reward_id:
            return
        try:
            validation = self.shop_service.purchase_run_reward(reward_id)
        except ShopTransitionError as exc:
            self._set_shop_message(exc, error=True)
        else:
            if validation.allowed:
                self._shop_focus_reward_id = reward_id
                self._set_shop_message(
                    f'Purchased {reward_id} with a Free Buff Token.'
                    if validation.cost == 0 else
                    f'Purchased {reward_id} for {validation.cost} Ore.'
                )
            else:
                self._set_shop_message(
                    f'Purchase failed: {validation.result.value.replace("_", " ")}.',
                    error=True,
                )
        self.refresh_shop_mode()

    def _refresh_shop_loadout(self):
        tree = self.shop_loadout_tree
        self._clear_shop_tree_buttons('_shop_loadout_upgrade_buttons')
        tree.delete(*tree.get_children())
        self._shop_current_loadout_targets = {}
        self._shop_loadout_details = {}
        run = self.shop_run
        if run is None:
            self._rebuild_shop_loadout_upgrade_buttons()
            self.shop_loadout_upgrade_button.configure(state='disabled')
            return
        records = {}

        def add_access(source, item, *, raw_unit=False):
            entry = self._shop_entry_by_reward_id.get(item)
            if entry is not None and entry.reward_type not in {
                ShopRewardType.UNIT_ACCESS,
                ShopRewardType.POWER_ACCESS,
            }:
                return
            is_power = bool(
                entry is not None
                and entry.reward_type is ShopRewardType.POWER_ACCESS
            )
            target_id = (
                entry.target_id if entry is not None
                else str(item).upper() if raw_unit else ''
            )
            if not target_id:
                return
            key = (is_power, target_id)
            record = records.setdefault(key, {
                'sources': [],
                'item': item,
                'target_id': target_id,
                'is_power': is_power,
                'buffs': [],
            })
            if source not in record['sources']:
                record['sources'].append(source)

        for unit_id in run.starting_unit_ids:
            add_access('Tier 1 Starter', unit_id, raw_unit=True)
        for unit_id in run.starting_defense_ids:
            add_access('Tier 1 Defense', unit_id, raw_unit=True)
        ap_units = set(ap_unit_entitlement_ids(run.ap_entitlements_snapshot))
        local_units = set(self.shop_profile.permanent_unit_unlocks)
        for reward_id in run.selected_permanent_units:
            if reward_id in ap_units and reward_id not in local_units:
                source = 'AP Selected Extra'
            elif reward_id in ap_units:
                source = 'Permanent / AP Selected'
            else:
                source = 'Permanent Selected'
            add_access(source, reward_id)
        ap_rewards = tuple(ap_automatic_reward_ids(
            run.ap_entitlements_snapshot
        ))
        for reward_id in ap_rewards:
            add_access('AP Received', reward_id)
        for item in run.run_purchases:
            add_access('Purchased This Run', item.reward_id)

        buff_items = [
            ('Permanent', item.reward_id, item.stacks)
            for item in run.permanent_buffs_snapshot
        ] + [
            ('This Run', item.reward_id, item.stacks)
            for item in run.run_buffs
        ] + [
            ('Starting Draft', item.reward_id, item.stacks)
            for item in run.starting_draft_buffs
        ] + [
            ('AP Received', reward_id, 1)
            for reward_id in ap_rewards
            if (
                (entry := self._shop_entry_by_reward_id.get(reward_id))
                is not None
                and entry.reward_type in {
                    ShopRewardType.UNIT_BUFF,
                    ShopRewardType.POWER_BUFF,
                }
            )
        ]
        for source, reward_id, stacks in buff_items:
            entry = self._shop_entry_by_reward_id.get(reward_id)
            if entry is None:
                continue
            is_power = entry.reward_type is ShopRewardType.POWER_BUFF
            key = (is_power, entry.target_id)
            record = records.get(key)
            if record is None:
                record = records.setdefault(key, {
                    'sources': ['Buff entitlement'],
                    'item': entry.target_id,
                    'target_id': entry.target_id,
                    'is_power': is_power,
                    'buffs': [],
                })
            record['buffs'].append((source, reward_id, int(stacks)))

        rows = sorted(
            records.values(),
            key=lambda item: (
                item['is_power'],
                str(item['item']).casefold(),
            ),
        )
        term = self.shop_loadout_search_var.get().strip().casefold()
        visible = []
        for record in rows:
            buff_lines = []
            for source, reward_id, stacks in record['buffs']:
                effects = buff_effect_lines(
                    canonical_reward_for_id(reward_id), count=stacks
                )
                effect = '; '.join(effects) or reward_display_name(
                    canonical_reward_for_id(reward_id)
                )
                buff_lines.append(
                    f'{source}: {effect} ×{stacks}'
                )
            record['buff_lines'] = buff_lines
            haystack = ' '.join((
                *record['sources'],
                str(record['item']),
                record['target_id'],
                *buff_lines,
            )).casefold()
            if not term or term in haystack:
                visible.append(record)
        cameo_images = self._prepare_shop_unit_cameos(
            record['item'] for record in visible if not record['is_power']
        )
        unit_buff_targets = {entry.target_id for entry in self._shop_buff_entries}
        power_buff_targets = {
            entry.target_id for entry in self._shop_power_buff_entries
        }
        for index, record in enumerate(visible):
            iid = f'current-loadout-{index}'
            target_id = record['target_id']
            is_power = record['is_power']
            has_upgrades = target_id in (
                power_buff_targets if is_power else unit_buff_targets
            )
            if has_upgrades:
                self._shop_current_loadout_targets[iid] = (
                    target_id, is_power
                )
            item = record['item']
            item_label = (
                str(item)
                if is_power or item in self._shop_entry_by_reward_id
                else f'{unit_display_label(target_id)} [{target_id}]'
            )
            total_stacks = sum(
                stacks for _source, _reward, stacks in record['buffs']
            )
            buff_summary = (
                f'{len(record["buffs"])} effects / {total_stacks} stacks'
                if record['buffs'] else 'No buffs'
            )
            options = {
                'iid': iid,
                'values': (
                    ' + '.join(record['sources']),
                    item_label,
                    buff_summary,
                    '' if has_upgrades else '—',
                ),
            }
            cameo = cameo_images.get(item)
            if cameo is not None:
                options['image'] = cameo
            tree.insert('', 'end', **options)
            details = [
                item_label,
                'Source: ' + ' + '.join(record['sources']),
                'Active for current run.',
                '',
                'Attached buffs:',
            ]
            details.extend(record['buff_lines'] or ('None',))
            self._shop_loadout_details[iid] = '\n'.join(details)
        self._rebuild_shop_loadout_upgrade_buttons()
        unit_upgrade_count = len({
            target for target, is_power
            in self._shop_current_loadout_targets.values()
            if not is_power
        })
        self.shop_loadout_upgrade_button.configure(
            state='normal' if unit_upgrade_count else 'disabled',
            text=(
                f'Browse Owned Unit Upgrades '
                f'({unit_upgrade_count})'
            ),
        )

    def _refresh_shop_setup(self):
        tree = self.shop_loadout_select_tree
        self.capture_shop_setup_selection()
        tree.delete(*tree.get_children())
        self._shop_loadout_rows = {}
        expanded_level = self.shop_profile.upgrade_level('expanded_loadout')
        maximum_loadout = (
            self.shop_config.max_selected_permanent_units
            + expanded_level * int(self.shop_config.permanent_upgrades[
                'expanded_loadout'
            ].effects['slots_per_level'])
        )
        random_ap_loadout = (
            self.archipelago_received_unit_loadout_mode()
            == ARCHIPELAGO_RECEIVED_UNIT_LOADOUT_RANDOM
        )
        if random_ap_loadout:
            self.shop_loadout_help_var.set(
                f'Choose permanent units; received AP units randomly fill '
                f'unused slots up to the {maximum_loadout}-unit limit when '
                'the run starts. Mandatory Tier 1 starters are automatic.'
            )
        else:
            self.shop_loadout_help_var.set(
                f'Choose up to {maximum_loadout} permanent or AP-entitled '
                'extra units. Mandatory Tier 1 starters are added '
                'automatically.'
            )
        draft_level = self.shop_profile.upgrade_level('starting_buff_draft')
        specialization_level = self.shop_profile.upgrade_level(
            'discount_specialization'
        )
        specialization_ore = (
            specialization_level * int(self.shop_config.permanent_upgrades[
                'discount_specialization'
            ].effects['ore_per_level'])
        )
        self.shop_permanent_setup_help_var.set(
            f'Starting Buff Draft: {draft_level} free Tier 1 buff(s) at run '
            f'start; {"choose preferred type above" if draft_level else "locked"}. '
            f'Discount Specialization: {specialization_ore} Ore off selected '
            f'category; {"choose category above" if specialization_level else "locked"}.'
        )
        local_owned = set(self.shop_profile.permanent_unit_unlocks)
        _ap_identity, ap_reward_ids = self.archipelago_shop_context()
        ap_owned = set(ap_unit_entitlement_ids(ap_reward_ids))
        active_run = bool(
            self.shop_run is not None
            and self.shop_run.status is RunStatus.ACTIVE
        )
        selectable_ap_owned = (
            ap_owned if not random_ap_loadout or active_run else set()
        )
        owned = local_owned | selectable_ap_owned
        selected = set(
            self.shop_run.selected_permanent_units
            if self.shop_run is not None else ()
        )
        if self.shop_run is None:
            selected = set(self._shop_pending_loadout_selection)
        else:
            self._shop_pending_loadout_selection = set(selected)
        entries = sorted(
            (
                entry for entry in self._shop_unit_entries
                if entry.reward_id in owned
                and self._shop_entry_available(entry)
                and (
                    not self.shop_setup_search_var.get().strip()
                    or self.shop_setup_search_var.get().strip().casefold()
                    in (entry.reward_id + ' ' + entry.target_id).casefold()
                )
            ),
            key=lambda entry: entry.reward_id.casefold(),
        )
        selection = []
        cameo_images = self._prepare_shop_unit_cameos(
            entry.reward_id for entry in entries
        )
        for index, entry in enumerate(entries):
            iid = f'loadout-{index}'
            options = {
                'iid': iid,
                'values': (
                    entry.reward_id,
                    (entry.tier or '').replace('_', ' ').title(),
                    (
                        'Permanent + AP'
                        if entry.reward_id in local_owned
                        and entry.reward_id in ap_owned
                        else 'AP Received'
                        if entry.reward_id in ap_owned
                        else 'Permanent'
                    ),
                ),
            }
            cameo = cameo_images.get(entry.reward_id)
            if cameo is not None:
                options['image'] = cameo
            tree.insert('', 'end', **options)
            self._shop_loadout_rows[iid] = entry.reward_id
            if entry.reward_id in selected:
                selection.append(iid)
        if selection:
            tree.selection_set(selection)
        modifiers_locked = bool(
            self.shop_run is not None
            and self.shop_run.status is RunStatus.ACTIVE
        )
        tree.configure(selectmode='none' if modifiers_locked else 'extended')
        if modifiers_locked:
            selected_modifiers = set(self.shop_run.modifiers)
            for modifier_id, variable in self.shop_modifier_vars.items():
                variable.set(modifier_id in selected_modifiers)
            enabled_names = [
                self.shop_config.modifiers[item].display_name
                for item in self.shop_run.modifiers
            ]
            self.shop_modifier_status_var.set(
                'Locked for the active run. Enabled now: '
                + (', '.join(enabled_names) if enabled_names else 'none')
                + '. Finish or give up the run to configure the next one.'
            )
        else:
            self.shop_modifier_status_var.set(
                'Optional run-wide tradeoffs. Check any combination before '
                'starting; both benefits and penalties apply for the whole run.'
            )
        for button in self.shop_modifier_buttons:
            button.configure(state='disabled' if modifiers_locked else 'normal')

    def _refresh_permanent_shop(self):
        active_run = bool(
            self.shop_run is not None
            and self.shop_run.status is RunStatus.ACTIVE
        )
        unit_tree = self.shop_permanent_unit_tree
        unit_tree.delete(*unit_tree.get_children())
        self._shop_permanent_rows = {}
        self._shop_permanent_buyable = {}
        term = self.shop_permanent_search_var.get().strip().casefold()
        owned = set(self.shop_profile.permanent_unit_unlocks)
        entries = sorted(
            (
                entry for entry in self._shop_unit_entries
                if not term or term in (
                    entry.reward_id + ' ' + entry.target_id
                ).casefold()
            ),
            key=lambda item: item.reward_id.casefold(),
        )
        cameo_images = self._prepare_shop_unit_cameos(
            entry.reward_id for entry in entries
        )
        for index, entry in enumerate(entries):
            iid = f'permanent-{index}'
            price = permanent_unit_price(entry.tier or 'tier_1')
            if entry.reward_id in owned:
                state = 'Owned'
                row_tag = 'owned'
                buyable = False
            elif active_run:
                state = 'Locked: run active'
                row_tag = 'unavailable'
                buyable = False
            elif self.shop_profile.meta_coins < price:
                state = f'Need {price - self.shop_profile.meta_coins} more'
                row_tag = 'unavailable'
                buyable = False
            else:
                state = 'Available'
                row_tag = 'available'
                buyable = True
            options = {
                'iid': iid,
                'tags': (row_tag,),
                'values': (
                    entry.reward_id,
                    (entry.tier or '').replace('_', ' ').title(),
                    state,
                    f'{price} Mental',
                ),
            }
            cameo = cameo_images.get(entry.reward_id)
            if cameo is not None:
                options['image'] = cameo
            unit_tree.insert('', 'end', **options)
            self._shop_permanent_rows[iid] = entry.reward_id
            self._shop_permanent_buyable[iid] = buyable
        upgrade_tree = self.shop_upgrade_tree
        upgrade_tree.delete(*upgrade_tree.get_children())
        self._shop_upgrade_rows = {}
        self._shop_upgrade_buyable = {}
        for index, (upgrade_id, definition) in enumerate(
            self.shop_config.permanent_upgrades.items()
        ):
            if term and term not in (
                upgrade_id + ' ' + definition.display_name + ' '
                + ' '.join(definition.effects)
            ).casefold():
                continue
            level = self.shop_profile.upgrade_level(upgrade_id)
            maxed = level >= definition.max_level
            price = (
                None if maxed
                else permanent_upgrade_price(upgrade_id, level + 1)
            )
            if maxed:
                state, row_tag, buyable = 'Maximum level', 'maxed', False
            elif active_run:
                state, row_tag, buyable = 'Locked: run active', 'unavailable', False
            elif self.shop_profile.meta_coins < price:
                state = f'Need {price - self.shop_profile.meta_coins} more'
                row_tag, buyable = 'unavailable', False
            else:
                state, row_tag, buyable = 'Available', 'available', True
            next_price = 'Max' if maxed else f'{price} Mental'
            iid = f'upgrade-{index}'
            upgrade_tree.insert(
                '', 'end', iid=iid,
                tags=(row_tag,),
                values=(
                    definition.display_name,
                    f'{level} / {definition.max_level}',
                    state,
                    next_price,
                ),
            )
            self._shop_upgrade_rows[iid] = upgrade_id
            self._shop_upgrade_buyable[iid] = buyable
        self._refresh_permanent_buffs(active_run)
        self.configure_shop_tree_tags()

    def _refresh_permanent_buffs(self, active_run):
        tree = self.shop_permanent_buff_tree
        tree.delete(*tree.get_children())
        self._shop_permanent_buff_rows = {}
        self._shop_permanent_buff_buyable = {}
        owned = set(self.shop_profile.permanent_unit_unlocks)
        owned_entries = sorted(
            (
                entry for entry in self._shop_unit_entries
                if entry.reward_id in owned
            ),
            key=lambda entry: entry.reward_id.casefold(),
        )
        labels = [entry.reward_id for entry in owned_entries]
        self._shop_permanent_buff_target_ids = {
            entry.reward_id: entry.target_id for entry in owned_entries
        }
        selected_label = self.shop_permanent_buff_target_var.get()
        if selected_label not in self._shop_permanent_buff_target_ids:
            selected_label = labels[0] if labels else ''
            self.shop_permanent_buff_target_var.set(selected_label)
        self.shop_permanent_buff_target_combo.configure(
            values=labels,
            state='readonly' if labels else 'disabled',
        )
        target_id = self._shop_permanent_buff_target_ids.get(
            selected_label, ''
        )
        entries = sorted(
            (
                entry for entry in self._shop_buff_entries
                if entry.target_id == target_id
                and (
                    not self.shop_permanent_search_var.get().strip()
                    or self.shop_permanent_search_var.get().strip().casefold()
                    in (
                        entry.reward_id + ' '
                        + self._shop_catalogue_display_name(entry, '', 0)
                    ).casefold()
                )
            ),
            key=lambda entry: entry.reward_id.casefold(),
        )
        stacks_by_reward = {
            item.reward_id: item.stacks
            for item in self.shop_profile.permanent_buffs
        }
        cameo_images = self._prepare_shop_unit_cameos(
            entry.reward_id for entry in entries
        )
        for index, entry in enumerate(entries):
            stacks = stacks_by_reward.get(entry.reward_id, 0)
            maximum = entry.stack_limit or 1
            maxed = stacks >= maximum
            price = permanent_buff_price(entry.tier or 'tier_1')
            effect_state = 'MAX' if maxed else f'Stacks {stacks} / {maximum}'
            if maxed:
                state, row_tag, buyable = 'Maximum stacks', 'maxed', False
            elif active_run:
                state, row_tag, buyable = 'Locked: run active', 'unavailable', False
            elif self.shop_profile.meta_coins < price:
                state = f'Need {price - self.shop_profile.meta_coins} more'
                row_tag, buyable = 'unavailable', False
            else:
                state, row_tag, buyable = 'Available', 'available', True
            iid = f'permanent-buff-{index}'
            options = {
                'iid': iid,
                'tags': (row_tag,),
                'values': (
                    self._shop_catalogue_display_name(
                        entry, effect_state, stacks
                    ),
                    f'{stacks} / {maximum}',
                    state,
                    'Max' if maxed else f'{price} Mental',
                ),
            }
            cameo = cameo_images.get(entry.reward_id)
            if cameo is not None:
                options['image'] = cameo
            tree.insert('', 'end', **options)
            self._shop_permanent_buff_rows[iid] = entry.reward_id
            self._shop_permanent_buff_buyable[iid] = buyable
        self.refresh_permanent_buff_button()

    def refresh_permanent_buff_button(self, _event=None):
        if not hasattr(self, 'shop_permanent_buff_button'):
            return
        selected = self.shop_permanent_buff_tree.selection()
        allowed = bool(
            selected
            and self._shop_permanent_buff_buyable.get(selected[0], False)
        )
        self.shop_permanent_buff_button.configure(
            state='normal' if allowed else 'disabled'
        )
        if not selected:
            self.shop_permanent_buff_info_var.set(
                'Select a permanently unlocked unit, then choose a buff.'
            )
            self.shop_permanent_buff_button.configure(
                text='Select a Permanent Buff'
            )
            return
        values = self.shop_permanent_buff_tree.item(selected[0], 'values')
        self.shop_permanent_buff_info_var.set(
            f'{values[0]} • {values[1]} • {values[2]} • Next: {values[3]}.'
        )
        self.shop_permanent_buff_button.configure(
            text=(
                f'Buy Permanent Stack — {values[3]}'
                if allowed else values[2]
            )
        )
        self.refresh_permanent_purchase_buttons()

    def buy_selected_permanent_unit(self):
        selected = self.shop_permanent_unit_tree.selection()
        if not selected:
            return
        reward_id = self._shop_permanent_rows.get(selected[0])
        if not reward_id:
            return
        try:
            outcome = self.shop_service.purchase_permanent_unit(reward_id)
        except ShopTransitionError as exc:
            self._set_shop_message(exc, error=True)
        else:
            self._report_profile_purchase(outcome, reward_id)
        self.refresh_shop_mode()

    def buy_selected_permanent_upgrade(self):
        selected = self.shop_upgrade_tree.selection()
        if not selected:
            return
        upgrade_id = self._shop_upgrade_rows.get(selected[0])
        if not upgrade_id:
            return
        try:
            outcome = self.shop_service.purchase_permanent_upgrade(upgrade_id)
        except ShopTransitionError as exc:
            self._set_shop_message(exc, error=True)
        else:
            self._report_profile_purchase(outcome, upgrade_id)
        self.refresh_shop_mode()

    def buy_selected_permanent_buff(self):
        selected = self.shop_permanent_buff_tree.selection()
        if not selected:
            return
        reward_id = self._shop_permanent_buff_rows.get(selected[0])
        if not reward_id:
            return
        try:
            outcome = self.shop_service.purchase_permanent_buff(reward_id)
        except ShopTransitionError as exc:
            self._set_shop_message(exc, error=True)
        else:
            self._report_profile_purchase(outcome, reward_id)
        self.refresh_shop_mode()

    def _report_profile_purchase(self, outcome, item_id):
        validation = outcome.validation
        if validation.allowed:
            self._set_shop_message(
                f'Purchased {item_id} for {validation.cost} Mental Coins.'
            )
        else:
            self._set_shop_message(
                f'Purchase failed: {validation.result.value.replace("_", " ")}.',
                error=True,
            )
