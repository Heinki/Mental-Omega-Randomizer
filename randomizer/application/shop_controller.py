"""Standalone Shop Mode UI coordination."""

from collections import Counter
from dataclasses import replace
import uuid
import tkinter as tk
from tkinter import messagebox

from ._dependencies import (
    BUFF_TARGETS,
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

from randomizer.rewards.definitions import unit_display_label
from randomizer.rewards.display import buff_effect_lines, reward_display_name
from randomizer.shop.active import (
    active_shop_rewards,
    active_shop_starter_defense_ids,
    active_shop_starter_unit_ids,
    active_shop_tech_ids,
    shop_starter_defense_ids,
    shop_starter_unit_ids,
)
from randomizer.shop.archipelago import (
    ap_automatic_reward_ids,
    ap_unit_entitlement_ids,
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
    mission_difficulty,
    mission_classes_for_stage,
)
from randomizer.shop.mission_modifiers import active_mission_modifier
from randomizer.shop.modifiers import (
    modifier_difficulty,
    modifier_effects,
    modifier_mission_offer_count,
)
from randomizer.shop.model import (
    SHOP_ACCESS_REWARD_MODE,
    RunStatus,
    ShopRewardType,
)
from randomizer.shop.persistence import ShopPersistenceError, ShopRepository
from randomizer.shop.service import ShopProgressionService
from randomizer.shop.text import gem_text
from randomizer.shop.transitions import ShopTransitionError
from randomizer.ui.cameos import ARCHIPELAGO_CAMEO_PATH
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
# Shop progression grants exact purchased identities. Reuse Chaos' isolated
# access pipeline internally; Shop Mode still owns its separate economy/UI.
SHOP_REWARD_MODE = SHOP_ACCESS_REWARD_MODE
class ShopController(ShopPolishController):
    def initialize_shop_controller(self):
        self.shop_config = SHOP_CONFIG
        self.shop_repository = ShopRepository()
        self.shop_service = ShopProgressionService(self.shop_repository)
        self.shop_profile, self.shop_run = self.shop_repository.load()
        self.shop_stage_var = tk.StringVar(value='Run — / 10')
        self.shop_status_var = tk.StringVar(value='Status: No Run')
        self.shop_run_coins_var = tk.StringVar(value='Ore: 0')
        self.shop_meta_coins_var = tk.StringVar(value='Gems: 0')
        self.shop_rerolls_var = tk.StringVar(value='Rerolls: 0 / 0')
        self.shop_difficulty_var = tk.StringVar(value='Difficulty: +0')
        self.shop_message_var = tk.StringVar(value='')
        self.shop_ap_purchase_status_var = tk.StringVar(value='')
        saved_faction_pool = self.config.get('shop_faction_pool')
        if saved_faction_pool not in SHOP_FACTION_POOLS:
            saved_faction_pool = SHOP_CAMPAIGN_FACTIONS.get(
                self.campaign_var.get(), SHOP_FACTION_POOLS[0]
            )
        self.shop_faction_pool_options = SHOP_FACTION_POOLS
        self.shop_faction_pool_var = tk.StringVar(value=saved_faction_pool)
        self.shop_loadout_help_var = tk.StringVar(value='')
        self.shop_category_var = tk.StringVar(value='Offers')
        self.shop_access_view_var = tk.StringVar(value='Available')
        self.shop_buff_target_var = tk.StringVar(value='')
        self.shop_permanent_buff_target_var = tk.StringVar(value='')
        self.shop_permanent_unit_filter_var = tk.StringVar(value='All')
        self.shop_search_var = tk.StringVar(value='')
        self.shop_loadout_search_var = tk.StringVar(value='')
        self.shop_setup_search_var = tk.StringVar(value='')
        self.shop_permanent_search_var = tk.StringVar(value='')
        self.shop_sort_var = tk.StringVar(value='Name')
        self.shop_summary_var = tk.StringVar(value='No Shop run exists.')
        self.shop_modifier_vars = {
            modifier_id: tk.BooleanVar(value=False)
            for modifier_id in self.shop_config.modifiers
        }
        for variable in self.shop_modifier_vars.values():
            variable.trace_add('write', self._refresh_shop_modifier_difficulty)
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
        self._shop_loadout_selection_initialized = False
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
        return super().save_current_launcher_config()

    def apply_portable_settings(self, config):
        result = super().apply_portable_settings(config)
        saved = self.config.get('shop_faction_pool')
        self.shop_faction_pool_var.set(
            saved if saved in SHOP_FACTION_POOLS else SHOP_FACTION_POOLS[0]
        )
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
            state='disabled' if locked else 'readonly'
        )
        self.shop_game_speed_combo.configure(
            state='disabled' if locked else 'readonly'
        )

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
            # Legacy Shop runs serialized "Standard". Never let that old
            # implementation detail restore Standard's faction translation.
            return SHOP_REWARD_MODE
        if self._shop_mode_context_selected():
            return SHOP_REWARD_MODE
        return super().active_reward_mode()

    def active_progression_mode(self):
        if self._shop_mode_context_selected():
            return 'Shop Mode'
        return super().active_progression_mode()

    def _shop_modifier_clone_seed_plan(self, run):
        existing = Counter(
            (
                str(reward.get('unit') or '').upper(),
                str(reward.get('buff_type') or ''),
            )
            for reward in active_shop_rewards(run)
            if reward.get('kind') == 'buff'
        )
        armor = {}
        damage = {}
        for target_id in active_shop_tech_ids(run):
            target = BUFF_TARGETS.get(target_id, {})
            armor_reward = canonical_reward_for_id(
                f'{target.get("label", target_id)} Armor Plating I'
            )
            if armor_reward.get('buff_type') == 'armor':
                armor[target_id] = existing[(target_id, 'armor')]
            if not target.get('weapons'):
                continue
            damage_reward = canonical_reward_for_id(
                f'{target.get("label", target_id)} Firepower I'
            )
            if damage_reward.get('buff_type') == 'damage':
                damage[target_id] = existing[(target_id, 'damage')]
        return armor, damage

    def active_reward_settings(self):
        run = self._shop_context_run()
        if run is not None:
            settings = dict(run.reward_settings)
            settings['start_with_tier_one_units'] = True
            settings['start_with_tier_one_defenses'] = True
            settings['failure_assistance'] = False
            effects = modifier_effects(run.modifiers)
            for key in (
                'player_damage_percent',
                'player_armor_percent',
                'production_time_percent',
                'combat_production_time_percent',
                'player_cost_percent',
                'mission_starting_credits_flat',
            ):
                value = effects[key]
                settings[f'shop_{key}'] = (
                    float(value) if key.endswith('_percent') else int(value)
                )
            armor_seeds, damage_seeds = self._shop_modifier_clone_seed_plan(run)
            settings['shop_modifier_armor_seed_stacks'] = armor_seeds
            settings['shop_modifier_damage_seed_stacks'] = damage_seeds
            mission_modifier = self._active_shop_mission_modifier(run)
            if mission_modifier is not None and mission_modifier.buffs_allied_helpers:
                settings['buff_allied_helpers'] = True
            return settings
        return super().active_reward_settings()

    def active_launch_rewards(self):
        if self.shop_launch_active():
            run = self._shop_launch_run
            effects = modifier_effects(run.modifiers)
            rewards = [dict(item) for item in active_shop_rewards(run)]
            starting_credit_level = self.shop_profile.upgrade_level(
                'mission_starting_credits'
            )
            rewards.extend(
                canonical_reward_for_id('Starting Credits +1,000')
                for _index in range(starting_credit_level)
            )
            mission_modifier = self._active_shop_mission_modifier(
                run
            )
            if mission_modifier is not None:
                for reward_id in mission_modifier.player_reward_ids:
                    reward = dict(canonical_reward_for_id(reward_id))
                    if reward.get('kind') == 'superweapon':
                        reward['superweapon_ignore_foreign_tech_gate'] = True
                    rewards.append(reward)
            veteran_targets = set()
            if self.shop_profile.upgrade_level('veteran_academy'):
                for reward_id in run.selected_permanent_units:
                    entry = self._shop_entry_by_reward_id.get(reward_id)
                    if entry is not None and entry.target_id:
                        veteran_targets.add(entry.target_id.upper())
            if effects['starter_veteran']:
                veteran_targets.update(active_shop_starter_unit_ids(run))
            for target_id in sorted(veteran_targets):
                target = BUFF_TARGETS.get(target_id, {})
                reward_name = f'{target.get("label", target_id)} Veteran Training I'
                try:
                    reward = dict(canonical_reward_for_id(reward_name))
                except KeyError:
                    continue
                if reward.get('buff_type') == 'veteran':
                    rewards.append(reward)
            if effects['player_armor_percent'] != 1:
                armor_seeds, _damage_seeds = (
                    self._shop_modifier_clone_seed_plan(run)
                )
                for target_id in armor_seeds:
                    target = BUFF_TARGETS.get(target_id, {})
                    reward_name = f'{target.get("label", target_id)} Armor Plating I'
                    reward = dict(canonical_reward_for_id(reward_name))
                    reward['force_direct_unit_buff'] = True
                    reward['_shop_modifier_clone_seed'] = True
                    rewards.append(reward)
            if effects['player_damage_percent'] != 1:
                _armor_seeds, damage_seeds = (
                    self._shop_modifier_clone_seed_plan(run)
                )
                for target_id in damage_seeds:
                    target = BUFF_TARGETS.get(target_id, {})
                    reward_name = f'{target.get("label", target_id)} Firepower I'
                    reward = dict(canonical_reward_for_id(reward_name))
                    reward['force_direct_unit_buff'] = True
                    reward['_shop_modifier_clone_seed'] = True
                    rewards.append(reward)
            support_factor = float(effects['support_recharge_percent'])
            if support_factor != 1.0:
                for index, reward in enumerate(rewards):
                    if (
                        reward.get('kind') == 'superweapon'
                        and reward.get('power_category') == 'aid'
                    ):
                        updated = dict(reward)
                        updated['superweapon_recharge_multiplier'] = (
                            float(updated.get(
                                'superweapon_recharge_multiplier', 1.0
                            )) * support_factor
                        )
                        rewards[index] = updated
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
            return list(active_shop_starter_unit_ids(run))
        if self._shop_mode_context_selected():
            return []
        return super().active_starting_tier_one_unit_ids()

    def active_starting_tier_one_defense_ids(self):
        run = self._shop_context_run()
        if run is not None:
            return list(active_shop_starter_defense_ids(run))
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
            return False
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
        run = self.__dict__.get('shop_run')
        if run is not None and modifier_effects(
            run.modifiers
        )['disable_rerolls']:
            return 0
        level = self.shop_profile.upgrade_level('mission_reroll')
        per_level = self.shop_config.permanent_upgrades[
            'mission_reroll'
        ].effects['rerolls_per_level']
        return level * int(per_level)

    def _shop_difficulty_assist_capacity(self):
        run = self.__dict__.get('shop_run')
        if run is not None and modifier_effects(
            run.modifiers
        )['disable_assists']:
            return 0
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

    def shop_mission_difficulty_label(self, run, mission_code):
        if run is None:
            return 'Casual'
        return mission_difficulty(
            run.seed,
            run.stage,
            mission_code,
            run_length=run.run_length,
        )

    def shop_mission_difficulty_value(self, run, mission_code):
        return dict(DIFFICULTIES).get(
            self.shop_mission_difficulty_label(run, mission_code),
            0,
        )

    def shop_eased_difficulty_labels(self, run, mission_code):
        labels = [name for name, _value in DIFFICULTIES]
        current = self.shop_mission_difficulty_label(run, mission_code)
        try:
            index = labels.index(current)
        except ValueError:
            index = 0
        return current, labels[max(0, index - 1)]

    def get_selected_difficulty_value(self):
        run = self.__dict__.get('_shop_launch_run')
        if run is None or not run.selected_mission_code:
            return super().get_selected_difficulty_value()
        value = self.shop_mission_difficulty_value(
            run, run.selected_mission_code
        )
        if run.assisted_mission_code == run.selected_mission_code:
            return max(0, value - 1)
        return value

    def _shop_mission(self, code):
        return self._mission_by_code.get(str(code).upper(), {})

    def _shop_entry_available(self, entry, run=None):
        if run is None:
            reward_mode = SHOP_REWARD_MODE
            campaign_filter = self.shop_campaign_filter()
        else:
            reward_mode = SHOP_REWARD_MODE
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
                else 'Shop.Gem.TLabel'
            )
            self.shop_status_label.configure(style=status_style)
        self.shop_meta_coins_var.set(
            f'Gems: {self.shop_profile.meta_coins}'
        )
        capacity = self._shop_reroll_capacity()
        used = run.rerolls_used if run is not None else 0
        self.shop_rerolls_var.set(f'Rerolls: {used} / {capacity}')
        self._refresh_shop_missions()
        self.refresh_shop_catalogue()
        self._refresh_shop_loadout()
        self._refresh_shop_setup()
        self._refresh_permanent_shop()
        if hasattr(self, 'header_summary_var'):
            self.update_header_summary()
        self._refresh_shop_history()
        self._refresh_archipelago_shop_purchases()
        self.refresh_shop_settings_controls()
        if hasattr(self, 'shop_debug_mission_combo'):
            self.refresh_shop_debug_completion_choices()
        self.refresh_progress_view()

    def refresh_shop_debug_completion_choices(self):
        """Populate the hidden developer picker from current Shop offers."""
        if not hasattr(self, 'shop_debug_mission_combo'):
            return
        run = self.shop_repository.load_run()
        offers = (
            tuple(run.mission_offers)
            if run is not None and run.status is RunStatus.ACTIVE
            else ()
        )
        if run is not None and run.mission_committed:
            offers = tuple(
                offer for offer in offers
                if offer.mission_code == run.selected_mission_code
            )
        previous_code = self.shop_debug_mission_codes.get(
            self.shop_debug_mission_var.get(),
            '',
        )
        labels = []
        code_by_label = {}
        for offer in offers:
            code = str(offer.mission_code or '').upper()
            mission = self._shop_mission(code)
            title = str(mission.get('title') or code)
            label = f'{title} [{code}]'
            labels.append(label)
            code_by_label[label] = code
        self.shop_debug_mission_codes = code_by_label
        self.shop_debug_mission_combo.configure(
            values=labels,
            state='readonly' if labels else 'disabled',
        )
        selected_code = (
            str(run.selected_mission_code or '').upper()
            if run is not None and run.mission_committed
            else previous_code
        )
        selected_label = next(
            (
                label for label, code in code_by_label.items()
                if code == selected_code
            ),
            labels[0] if labels else '',
        )
        self.shop_debug_mission_var.set(selected_label)
        self.shop_debug_complete_button.configure(
            state='normal' if labels else 'disabled'
        )

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

    def _shop_archipelago_cameo(self):
        cache_key = 'archipelago:item'
        if cache_key not in self._shop_cameo_images:
            try:
                self._shop_cameo_images[cache_key] = tk.PhotoImage(
                    master=self,
                    file=str(ARCHIPELAGO_CAMEO_PATH),
                )
            except tk.TclError:
                self._shop_cameo_images[cache_key] = None
        return self._shop_cameo_images[cache_key]

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
            'Gems and permanent unlocks are kept.',
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

    def open_shop_permanent_upgrades(self):
        self.sync_shop_workspace()
        self.workspace_tabs.select(self.shop_tab)
        self.shop_panels.select(self.shop_permanent_panel)
        self.shop_permanent_tabs.select(self.shop_permanent_upgrades_panel)

    def open_selected_permanent_unit_buffs(self):
        selected = self.shop_permanent_unit_tree.selection()
        if not selected:
            return
        reward_id = self._shop_permanent_rows.get(selected[0], '')
        if reward_id not in self.shop_profile.permanent_unit_unlocks:
            return
        self.shop_permanent_search_var.set('')
        self.shop_permanent_buff_target_var.set(reward_id)
        active_run = bool(
            self.shop_run is not None
            and self.shop_run.status is RunStatus.ACTIVE
        )
        self._refresh_permanent_buffs(active_run)
        self.shop_permanent_tabs.select(self.shop_permanent_buffs_panel)

    def show_shop_permanent_units(self):
        self.shop_permanent_tabs.select(self.shop_permanent_units_panel)

    def reset_shop_profile(self):
        if self.shop_launch_active():
            self._set_shop_message(
                'Close the running mission before resetting the Shop profile.',
                error=True,
            )
            return
        if not messagebox.askyesno(
            'Reset Shop Profile?',
            'This permanently deletes all Shop Gems, permanent units, '
            'permanent buffs, upgrades, lifetime totals, and the current '
            'Shop run. This cannot be undone.\n\nReset everything?',
            parent=self,
        ):
            return
        try:
            self.shop_profile, self.shop_run = self.shop_service.reset_profile()
        except (OSError, ShopPersistenceError) as exc:
            self._set_shop_message(f'Profile reset failed: {exc}', error=True)
            return
        self._shop_pending_loadout_selection.clear()
        self._shop_loadout_selection_initialized = True
        self._set_shop_message('Shop profile and current run reset.')
        self.refresh_shop_mode()

    def _repair_shop_mission_offers(self, run):
        if (
            run is None
            or run.status is not RunStatus.ACTIVE
            or run.mission_committed
            or not self.missions
        ):
            return run
        allowed = mission_classes_for_stage(run.stage, run.run_length)
        offer_count = modifier_mission_offer_count(run.modifiers)
        offers_valid = bool(
            len(run.mission_offers) == offer_count
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
            offer_count=offer_count,
        )
        if len(offers) != offer_count:
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
            normal, eased = self.shop_eased_difficulty_labels(run, code)
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
                    offer_count=modifier_mission_offer_count(run.modifiers),
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
                0
                if modifier_effects(run.modifiers)['disable_revivals']
                else self.shop_profile.upgrade_level('emergency_revival')
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
                    offer_count=modifier_mission_offer_count(run.modifiers),
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
        if not run.mission_committed:
            code = self.shop_debug_mission_codes.get(
                self.shop_debug_mission_var.get(),
                '',
            )
        if not code:
            messagebox.showwarning(
                'Shop Mode',
                'Choose a current Shop mission beside the developer button.',
                parent=self,
            )
            return
        try:
            if not run.mission_committed:
                run = self.shop_service.select_mission(code)
            run = self.shop_service.commit_mission(code)
            self._shop_launch_run = run
            self._shop_launch_mission_pool = tuple(
                self._shop_run_mission_pool(run)
            )
            self.unlock_mission_check(code, 'victory', 'Debug override')
        except ShopTransitionError as exc:
            self._set_shop_message(exc, error=True)
            messagebox.showwarning(
                'Cannot Complete Shop Mission', str(exc), parent=self
            )
        finally:
            self.finish_progression_launch_context()

    def _selected_loadout_reward_ids(self):
        return tuple(sorted(self._shop_pending_loadout_selection))

    def _maximum_shop_loadout(self):
        definition = self.shop_config.permanent_upgrades['expanded_loadout']
        return (
            self.shop_config.max_selected_permanent_units
            + self.shop_profile.upgrade_level('expanded_loadout')
            * int(definition.effects['slots_per_level'])
        )

    def toggle_shop_setup_unit(self, event):
        if (
            self.shop_run is not None
            and self.shop_run.status is RunStatus.ACTIVE
        ):
            return 'break'
        iid = self.shop_loadout_select_tree.identify_row(event.y)
        reward_id = self._shop_loadout_rows.get(iid, '')
        if not reward_id:
            return 'break'
        if reward_id in self._shop_pending_loadout_selection:
            self._shop_pending_loadout_selection.remove(reward_id)
        elif len(self._shop_pending_loadout_selection) >= self._maximum_shop_loadout():
            self._set_shop_message(
                f'Starting loadout allows up to '
                f'{self._maximum_shop_loadout()} extra units.',
                error=True,
            )
            return 'break'
        else:
            self._shop_pending_loadout_selection.add(reward_id)
        self._shop_loadout_selection_initialized = True
        self._refresh_shop_setup()
        return 'break'

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
        requested_seed = self.seed_var.get().strip()
        seed = requested_seed or uuid.uuid4().hex[:16].upper()
        salvaged_ore = self.shop_profile.salvaged_run_coins
        # Only a seed typed by the player is an instruction to reuse it.
        # Automatically generated run IDs must not remain in the input field.
        if not requested_seed:
            self.seed_var.set('')
        settings = self.shop_reward_settings_for_new_run()
        modifiers = tuple(
            modifier_id for modifier_id, variable in self.shop_modifier_vars.items()
            if variable.get()
        )
        effects = modifier_effects(modifiers)
        faction_filter = self.shop_campaign_filter()
        settings['shop_faction_filter'] = faction_filter
        previous_context = self.__dict__.get('_seed_generation_context')
        self._seed_generation_context = {
            'campaign_filter': faction_filter,
            'reward_mode': SHOP_REWARD_MODE,
        }
        try:
            starting_unit_markers = self.starting_tier_one_unit_ids_for_seed(
                seed, settings
            )
            starting_defense_markers = self.starting_tier_one_defense_ids_for_seed(
                settings, seed=seed
            )
        finally:
            self._seed_generation_context = previous_context
        starting_units = shop_starter_unit_ids(
            seed=seed,
            starting_unit_ids=starting_unit_markers,
            faction_filter=faction_filter,
            excluded_unit_ids=settings.get('excluded_unit_access_ids', ()),
        )
        if effects['starter_unit_count_flat'] == -2 and len(starting_units) >= 5:
            # Remove one infantry and one vehicle while preserving aircraft
            # and naval safety roles.
            starting_units = (
                starting_units[0], starting_units[2], *starting_units[4:]
            )
        starting_defenses = shop_starter_defense_ids(
            seed=seed,
            starting_defense_ids=starting_defense_markers,
            faction_filter=faction_filter,
            excluded_unit_ids=settings.get('excluded_unit_access_ids', ()),
        )
        starter_tech_ids = set(starting_units)
        starter_tech_ids.update(starting_defenses)
        ap_identity, ap_reward_ids = self.archipelago_shop_context()
        maximum_extra_units = self._maximum_shop_loadout()
        permanent_entitlements = set(self.shop_profile.permanent_unit_unlocks)
        selected = tuple(
            reward_id for reward_id in self._selected_loadout_reward_ids()
            if reward_id in permanent_entitlements
        )
        permanent_buff_targets = set(starter_tech_ids)
        permanent_buff_targets.update(
            entry.target_id
            for reward_id in (
                *selected,
                *ap_unit_entitlement_ids(ap_reward_ids),
            )
            for entry in [self._shop_entry_by_reward_id.get(reward_id)]
            if entry is not None and entry.target_id
        )
        permanent_buffs = tuple(
            item for item in self.shop_profile.permanent_buffs
            if (
                (entry := self._shop_entry_by_reward_id.get(item.reward_id))
                is not None
                and entry.target_id in permanent_buff_targets
            )
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
                offer_count=modifier_mission_offer_count(modifiers),
            )
            expected_offer_count = modifier_mission_offer_count(modifiers)
            if len(offers) != expected_offer_count:
                raise ShopTransitionError(
                    'Shop Mode needs at least '
                    f'{expected_offer_count} eligible Act 1 '
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
                f'Started Shop run with seed {seed}.'
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

        def add_access(source, item, *, raw_unit=False, archipelago=False):
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
                'archipelago_item': False,
            })
            if source not in record['sources']:
                record['sources'].append(source)
            record['archipelago_item'] |= bool(archipelago)

        for unit_id in active_shop_starter_unit_ids(run):
            add_access('Tier 1 Starter', unit_id, raw_unit=True)
        for unit_id in active_shop_starter_defense_ids(run):
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
            add_access(source, reward_id, archipelago=reward_id in ap_units)
        ap_rewards = tuple(ap_automatic_reward_ids(
            run.ap_entitlements_snapshot
        ))
        for reward_id in ap_rewards:
            add_access('AP Received', reward_id, archipelago=True)
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
                    'archipelago_item': False,
                })
            record['buffs'].append((source, reward_id, int(stacks)))
            if source == 'AP Received':
                record['archipelago_item'] = True

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
            record['item'] for record in visible
            if not record['is_power'] and not record['archipelago_item']
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
            cameo = (
                self._shop_archipelago_cameo()
                if record['archipelago_item']
                else cameo_images.get(item)
            )
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
        tree.delete(*tree.get_children())
        self._shop_loadout_rows = {}
        maximum_loadout = self._maximum_shop_loadout()
        ap_identity, ap_reward_ids = self.archipelago_shop_context()
        local_owned = set(self.shop_profile.permanent_unit_unlocks)
        ap_owned = set(ap_unit_entitlement_ids(ap_reward_ids))
        active_run = bool(
            self.shop_run is not None
            and self.shop_run.status is RunStatus.ACTIVE
        )
        owned = local_owned | (ap_owned if active_run else set())
        if active_run:
            selected = set(self.shop_run.selected_permanent_units)
            self._shop_pending_loadout_selection = selected & local_owned
        else:
            if not self._shop_loadout_selection_initialized:
                self._shop_pending_loadout_selection = set(
                    self.shop_run.selected_permanent_units
                    if self.shop_run is not None else ()
                ) & local_owned
                self._shop_loadout_selection_initialized = True
            self._shop_pending_loadout_selection.intersection_update(local_owned)
            selected = set(self._shop_pending_loadout_selection)
        if active_run:
            selected.update(ap_owned)
        self.shop_loadout_help_var.set(
            f'Click a row to toggle it for next run. Selected '
            f'{len(self._shop_pending_loadout_selection)} / {maximum_loadout}. '
            + (
                'Received AP units are automatic and use no slots. '
                if ap_identity else ''
            )
            + 'Mandatory Tier 1 starters are automatic.'
            + (' Selection locked during active run.' if active_run else '')
        )
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
        cameo_images = self._prepare_shop_unit_cameos(
            entry.reward_id for entry in entries
            if entry.reward_id not in ap_owned
        )
        for index, entry in enumerate(entries):
            iid = f'loadout-{index}'
            options = {
                'iid': iid,
                'tags': (
                    ('selected_loadout',)
                    if entry.reward_id in selected else ()
                ),
                'values': (
                    (
                        '✓ Active'
                        if active_run and entry.reward_id in selected
                        else '✓ Selected'
                        if entry.reward_id in selected else '—'
                    ),
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
            cameo = (
                self._shop_archipelago_cameo()
                if entry.reward_id in ap_owned
                else cameo_images.get(entry.reward_id)
            )
            if cameo is not None:
                options['image'] = cameo
            tree.insert('', 'end', **options)
            self._shop_loadout_rows[iid] = entry.reward_id
        modifiers_locked = bool(
            self.shop_run is not None
            and self.shop_run.status is RunStatus.ACTIVE
        )
        tree.configure(selectmode='none')
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
        self._refresh_shop_modifier_difficulty()

    def _refresh_shop_modifier_difficulty(self, *_args):
        if not hasattr(self, 'shop_difficulty_var'):
            return
        modifiers = (
            self.shop_run.modifiers
            if self.shop_run is not None
            and self.shop_run.status is RunStatus.ACTIVE
            else tuple(
                modifier_id
                for modifier_id, variable in self.shop_modifier_vars.items()
                if variable.get()
            )
        )
        score = modifier_difficulty(modifiers)
        self.shop_difficulty_var.set(f'Difficulty: +{score}')
        if hasattr(self, 'shop_modifier_difficulty_var'):
            self.shop_modifier_difficulty_var.set(
                f'Run difficulty +{score}'
            )

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
        unit_filter = self.shop_permanent_unit_filter_var.get()
        entries = sorted(
            (
                entry for entry in self._shop_unit_entries
                if (
                    unit_filter == 'All'
                    or (
                        unit_filter == 'Owned'
                        and entry.reward_id in owned
                    )
                    or (
                        unit_filter == 'Not Owned'
                        and entry.reward_id not in owned
                    )
                )
                and (
                    not term or term in (
                        entry.reward_id + ' ' + entry.target_id
                    ).casefold()
                )
            ),
            key=lambda item: item.reward_id.casefold(),
        )
        cameo_images = self._prepare_shop_unit_cameos(
            entry.reward_id for entry in entries
        )
        for index, entry in enumerate(entries):
            iid = f'permanent-{index}'
            price = permanent_unit_price(entry.target_id)
            if entry.reward_id in owned:
                state = 'Owned'
                row_tag = 'owned'
                buyable = False
            elif active_run:
                state = 'Locked: run active'
                row_tag = 'unavailable'
                buyable = False
            elif self.shop_profile.meta_coins < price:
                state = (
                    f'Need {gem_text(price - self.shop_profile.meta_coins)} '
                    'more'
                )
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
                    gem_text(price),
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
            if not definition.purchasable:
                continue
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
                state = (
                    f'Need {gem_text(price - self.shop_profile.meta_coins)} '
                    'more'
                )
                row_tag, buyable = 'unavailable', False
            else:
                state, row_tag, buyable = 'Available', 'available', True
            next_price = 'Max' if maxed else gem_text(price)
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
        previous_selection = tree.selection()
        selected_reward_id = self.__dict__.pop(
            '_shop_permanent_buff_focus_reward_id', ''
        ) or (
            self._shop_permanent_buff_rows.get(previous_selection[0], '')
            if previous_selection else ''
        )
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
        restore_iid = ''
        for index, entry in enumerate(entries):
            stacks = stacks_by_reward.get(entry.reward_id, 0)
            maximum = entry.stack_limit or 1
            maxed = stacks >= maximum
            price = permanent_buff_price(entry.target_id)
            effect_state = 'MAX' if maxed else f'Stacks {stacks} / {maximum}'
            if maxed:
                state, row_tag, buyable = 'Maximum stacks', 'maxed', False
            elif active_run:
                state, row_tag, buyable = 'Locked: run active', 'unavailable', False
            elif self.shop_profile.meta_coins < price:
                state = (
                    f'Need {gem_text(price - self.shop_profile.meta_coins)} '
                    'more'
                )
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
                    'Max' if maxed else gem_text(price),
                ),
            }
            cameo = cameo_images.get(entry.reward_id)
            if cameo is not None:
                options['image'] = cameo
            tree.insert('', 'end', **options)
            self._shop_permanent_buff_rows[iid] = entry.reward_id
            self._shop_permanent_buff_buyable[iid] = buyable
            if entry.reward_id == selected_reward_id:
                restore_iid = iid
        if restore_iid:
            tree.selection_set(restore_iid)
            tree.see(restore_iid)
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
            if outcome.validation.allowed:
                self._shop_permanent_buff_focus_reward_id = reward_id
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
                f'Purchased {item_id} for {gem_text(validation.cost)}.'
            )
        else:
            self._set_shop_message(
                f'Purchase failed: {validation.result.value.replace("_", " ")}.',
                error=True,
            )
