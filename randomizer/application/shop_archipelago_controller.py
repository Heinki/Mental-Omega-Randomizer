"""Shop Mode bridge for Archipelago stage and purchase locations."""

from ._dependencies import (
    CAMPAIGN_FILTERS,
    filter_missions_by_build_settings,
    normalize_faction,
)

from randomizer.shop.archipelago import (
    ARCHIPELAGO_RECEIVED_UNIT_LOADOUT_MANUAL,
    archipelago_shop_identity,
    shop_reward_ids_from_ap_ledger,
)
from randomizer.shop.archipelago_purchases import (
    archipelago_purchase_placement_text,
    archipelago_purchase_records,
)
from randomizer.shop.model import RunStatus
from randomizer.shop.text import gem_text


class ShopArchipelagoController:
    def shop_archipelago_game_active(self):
        return bool(
            self.archipelago_shop_slot_settings() is not None
            and self._active_archipelago_state() is not None
            and getattr(self, '_archipelago_session_validated', False)
        )

    def sync_shop_ap_panel(self):
        panels = getattr(self, 'shop_panels', None)
        panel = getattr(self, 'shop_ap_panel', None)
        if panels is None or panel is None:
            return
        panel_id = str(panel)
        tabs = set(panels.tabs())
        if self.shop_archipelago_game_active():
            if panel_id not in tabs:
                panels.insert(
                    panels.index(self.shop_summary_panel),
                    panel,
                    text='AP Purchases',
                )
        elif panel_id in tabs:
            panels.forget(panel)

    def _shop_campaign_missions(self, campaign):
        if campaign == CAMPAIGN_FILTERS[0]:
            return list(self.missions)
        return [
            mission for mission in self.missions
            if normalize_faction(mission.get('side', '')) == campaign
        ]

    def filtered_missions_for_seed(self):
        variable = self.__dict__.get('progression_mode_var')
        if variable is None or variable.get() != 'Shop Mode':
            return super().filtered_missions_for_seed()
        return filter_missions_by_build_settings(
            self._shop_campaign_missions(CAMPAIGN_FILTERS[0]),
            include_true_no_build=self.include_no_build_missions_var.get(),
            include_no_build_production=(
                self.include_no_build_production_missions_var.get()
            ),
        )

    def archipelago_shop_context(self):
        """Return last validated AP identity and Shop-compatible rewards."""
        ap_state = self._active_archipelago_state()
        if ap_state is not None:
            records = self._archipelago_reward_records()
        else:
            cached_state = getattr(self, '_archipelago_cached_state', None)
            ap_state = (
                cached_state.get('archipelago')
                if isinstance(cached_state, dict)
                else None
            )
            records = (
                ap_state.get('received_rewards', ())
                if isinstance(ap_state, dict)
                else ()
            )
        identity = archipelago_shop_identity(ap_state)
        if not identity:
            return '', ()
        return identity, shop_reward_ids_from_ap_ledger(records)

    def archipelago_received_unit_loadout_mode(self):
        """Read signed AP restart policy from active or cached slot state."""
        states = [self._active_archipelago_state()]
        cached_state = getattr(self, '_archipelago_cached_state', None)
        if isinstance(cached_state, dict):
            states.append(cached_state.get('archipelago'))
        for ap_state in states:
            if not isinstance(ap_state, dict):
                continue
            for source in (
                ap_state.get('slot_data'),
                ap_state.get('run_manifest'),
                ap_state,
            ):
                if not isinstance(source, dict):
                    continue
                shop = source.get('shop')
                if not isinstance(shop, dict):
                    continue
                mode = str(shop.get('received_unit_loadout') or 'manual')
                if mode in {'all', 'manual', 'random'}:
                    return mode
        return ARCHIPELAGO_RECEIVED_UNIT_LOADOUT_MANUAL

    def archipelago_shop_slot_settings(self):
        if self.archipelago_progression_mode() != 'Shop Mode':
            return None
        slot_data = getattr(self, '_archipelago_slot_data', {})
        shop = slot_data.get('shop') if isinstance(slot_data, dict) else None
        return shop if isinstance(shop, dict) else None

    def _validate_archipelago_shop_runtime_settings(self):
        shop = self.archipelago_shop_slot_settings()
        if shop is None:
            return
        expected = {
            'run_length': self.shop_config.run_length,
            'purchase_location_count': (
                self.shop_config.archipelago_purchase_locations
            ),
            'purchase_meta_coin_cost': (
                self.shop_config.archipelago_purchase_meta_coin_cost
            ),
            'mission_victories_are_locations': (
                self.shop_config.archipelago_mission_victories_are_locations
            ),
            'starting_extra_unit_limit': (
                self.shop_config.max_selected_permanent_units
            ),
        }
        mismatches = [
            key for key, value in expected.items() if shop.get(key) != value
        ]
        if mismatches:
            raise ValueError(
                'This AP Shop seed uses incompatible local Shop settings: '
                + ', '.join(mismatches)
            )

    def _synchronize_archipelago_progression_ui(self, manifest):
        result = super()._synchronize_archipelago_progression_ui(manifest)
        self._validate_archipelago_shop_runtime_settings()
        self.sync_shop_workspace()
        return result

    def _cache_archipelago_location_mappings(self, slot_data):
        super()._cache_archipelago_location_mappings(slot_data)
        shop = slot_data.get('shop') if isinstance(slot_data, dict) else None
        if not isinstance(shop, dict):
            return
        groups = dict(self._archipelago_location_groups)
        allowed = set(self._archipelago_allowed_locations)
        for index, location in enumerate(shop['purchase_locations'], start=1):
            location = int(location)
            groups[('__SHOP__', f'purchase_{index}')] = (location,)
            allowed.add(location)
        for entry in shop['stage_victories']:
            stage = int(entry['stage'])
            logic_location = int(entry['logic_location'])
            allowed.add(logic_location)
            if entry['location'] is not None:
                location = int(entry['location'])
                groups[('__SHOP__', f'stage_{stage}_reward')] = (location,)
                allowed.add(location)
        self._archipelago_location_groups = groups
        self._archipelago_allowed_locations = frozenset(allowed)

    def _shop_run_mission_pool(self, run=None):
        run = self.shop_run if run is None else run
        if run is not None and run.eligible_mission_codes:
            codes = run.eligible_mission_codes
        else:
            shop = self.archipelago_shop_slot_settings()
            codes = shop.get('mission_pool', ()) if shop is not None else ()
        if codes:
            return [
                self._mission_by_code[code]
                for code in codes
                if code in self._mission_by_code
            ]
        campaign = (
            run.campaign_filter
            if run is not None
            else CAMPAIGN_FILTERS[0]
        )
        return filter_missions_by_build_settings(
            self._shop_campaign_missions(campaign),
            include_true_no_build=self.include_no_build_missions_var.get(),
            include_no_build_production=(
                self.include_no_build_production_missions_var.get()
            ),
        )

    @staticmethod
    def _shop_location_group(check_id, locations, event_stem):
        return {
            'code': '__SHOP__',
            'check_id': str(check_id),
            'label': 'Shop Mode check',
            'event_stem': event_stem,
            'locations': tuple(int(value) for value in locations if value),
        }

    def _archipelago_shop_stage_group(self, stage):
        shop = self.archipelago_shop_slot_settings()
        if shop is None or not 1 <= int(stage) <= len(shop['stage_victories']):
            return None
        entry = shop['stage_victories'][int(stage) - 1]
        return self._shop_location_group(
            f'stage_{stage}',
            (entry.get('location'), entry['logic_location']),
            'shop_stage',
        )

    def report_archipelago_shop_stage_victory(self, stage):
        group = self._archipelago_shop_stage_group(stage)
        return self._report_archipelago_location_groups((group,)) if group else ()

    def record_archipelago_shop_victory(self, completed_stage, transition):
        self.report_archipelago_shop_stage_victory(completed_stage)
        if transition.run.status is RunStatus.COMPLETED:
            self.report_archipelago_goal_if_complete()

    def _archipelago_shop_purchase_group(self, location_id):
        shop = self.archipelago_shop_slot_settings()
        if shop is None or int(location_id) not in shop['purchase_locations']:
            return None
        return self._shop_location_group(
            f'purchase_{int(location_id)}',
            (int(location_id),),
            'shop_purchase',
        )

    def buy_selected_archipelago_purchase(self, *_args):
        selected = self.shop_ap_purchase_tree.selection()
        location_id = self._shop_ap_purchase_rows.get(
            selected[0], 0
        ) if selected else 0
        shop = self.archipelago_shop_slot_settings()
        identity, _reward_ids = self.archipelago_shop_context()
        if not location_id or shop is None:
            return
        validation = self.shop_service.purchase_archipelago_location(
            identity,
            location_id,
            cost=shop['purchase_meta_coin_cost'],
            connected=bool(
                self._active_archipelago_state() is not None
                and getattr(self, '_archipelago_session_validated', False)
            ),
            available_location_ids=shop['purchase_locations'],
            checked_location_ids=getattr(
                self, '_archipelago_server_checked_locations', ()
            ),
        )
        if validation.allowed:
            group = self._archipelago_shop_purchase_group(location_id)
            self._report_archipelago_location_groups((group,))
            purchase_index = shop['purchase_locations'].index(location_id) + 1
            self._set_shop_message(
                f'Spent {gem_text(validation.cost)} on generated AP '
                f'purchase {purchase_index}. The server determines its item.'
            )
        else:
            self._set_shop_message(
                'AP purchase failed: '
                + validation.result.value.replace('_', ' '),
                error=True,
            )
        self.refresh_shop_mode()

    def refresh_archipelago_purchase_button(self, _event=None):
        """Enable AP purchase only for the currently selected offer."""
        button = getattr(self, 'shop_ap_purchase_button', None)
        tree = getattr(self, 'shop_ap_purchase_tree', None)
        if button is None or tree is None:
            return
        selected = tree.selection()
        location_id = self._shop_ap_purchase_rows.get(
            selected[0], 0
        ) if selected else 0
        shop = self.archipelago_shop_slot_settings()
        identity, _reward_ids = self.archipelago_shop_context()
        records = archipelago_purchase_records(self.shop_profile, identity)
        checked = set(getattr(
            self, '_archipelago_server_checked_locations', ()
        ))
        can_buy = bool(
            location_id
            and shop is not None
            and identity
            and self.shop_archipelago_game_active()
            and location_id in set(shop['purchase_locations'])
            and location_id not in checked
            and str(location_id) not in records
            and self.shop_profile.meta_coins >= shop['purchase_meta_coin_cost']
        )
        button.configure(state='normal' if can_buy else 'disabled')

    def _refresh_archipelago_shop_purchases(self):
        self.sync_shop_ap_panel()
        tree = getattr(self, 'shop_ap_purchase_tree', None)
        if tree is None:
            return
        previous_selection = tree.selection()
        previous_location = (
            self._shop_ap_purchase_rows.get(previous_selection[0], 0)
            if previous_selection else 0
        )
        tree.delete(*tree.get_children())
        self._shop_ap_purchase_rows = {}
        shop = self.archipelago_shop_slot_settings()
        identity, _reward_ids = self.archipelago_shop_context()
        if (
            shop is None
            or not identity
            or not self.shop_archipelago_game_active()
        ):
            self.shop_ap_purchase_status_var.set(
                'Connect to a generated Shop Mode Archipelago slot.'
            )
            self.shop_ap_purchase_button.configure(state='disabled')
            return
        records = archipelago_purchase_records(self.shop_profile, identity)
        checked = set(getattr(
            self, '_archipelago_server_checked_locations', ()
        ))
        cost = shop['purchase_meta_coin_cost']
        archipelago_cameo = self._shop_archipelago_cameo()
        for index, location_id in enumerate(shop['purchase_locations'], start=1):
            record = records.get(str(location_id), {})
            if location_id in checked or record.get('status') == 'checked':
                status = 'Claimed'
            elif record.get('status') == 'pending':
                status = 'Pending server acknowledgement'
            else:
                status = 'Available'
            item = self._archipelago_location_info.get(location_id, {})
            item_name, recipient = archipelago_purchase_placement_text(item)
            iid = f'ap-purchase-{index}'
            options = {
                'iid': iid,
                'values': (index, item_name, recipient, status, cost),
            }
            if archipelago_cameo is not None:
                options['image'] = archipelago_cameo
            tree.insert('', 'end', **options)
            self._shop_ap_purchase_rows[iid] = location_id
            if location_id == previous_location:
                tree.selection_set(iid)
        self.shop_ap_purchase_status_var.set(
            'Each purchase sends its generated Archipelago item to the '
            'shown player/world. Placement remains server-assigned.'
        )
        self.refresh_archipelago_purchase_button()

    def is_run_complete(self):
        if self.archipelago_progression_mode() == 'Shop Mode':
            run = self.shop_repository.load_run()
            return run is not None and run.status is RunStatus.COMPLETED
        return super().is_run_complete()

    def reconcile_archipelago_checks(self):
        if self.archipelago_shop_slot_settings() is None:
            return super().reconcile_archipelago_checks()
        identity, _reward_ids = self.archipelago_shop_context()
        checked = getattr(self, '_archipelago_server_checked_locations', ())
        self.shop_service.reconcile_archipelago_purchases(identity, checked)
        groups = []
        run = self.shop_repository.load_run()
        if run is not None and run.ap_identity == identity:
            for key in run.rewarded_victories:
                parts = key.split(':')
                if len(parts) >= 4 and parts[0] == run.run_id:
                    group = self._archipelago_shop_stage_group(int(parts[1]))
                    if group:
                        groups.append(group)
        for location_id in self.shop_service.pending_archipelago_purchase_ids(
            identity
        ):
            group = self._archipelago_shop_purchase_group(location_id)
            if group:
                groups.append(group)
        added = self._report_archipelago_location_groups(groups)
        self.report_archipelago_goal_if_complete()
        return tuple(added)

    def _refresh_archipelago_server_views(self, reasons=()):
        result = super()._refresh_archipelago_server_views(reasons=reasons)
        identity, _reward_ids = self.archipelago_shop_context()
        if identity:
            self.shop_service.reconcile_archipelago_purchases(
                identity,
                getattr(self, '_archipelago_server_checked_locations', ()),
            )
        if self.shop_archipelago_game_active() or self.shop_mode_selected():
            self.refresh_shop_mode()
        return result
