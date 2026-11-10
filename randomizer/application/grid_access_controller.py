"""Grid objective feedback and AP-only durable mission purchases."""

from copy import deepcopy
from tkinter import messagebox

from randomizer.progression.grid import COMPLETED, LOCKED, UNLOCKED, required_goals
from randomizer.progression.mission_access import access_projection, purchase_blocker


class GridAccessController:
    def grid_access_contract(self):
        if not self.state or not self.archipelago_run_active():
            return None
        return self.state.get('grid_access')

    def grid_mission_names_hidden(self):
        """Key modes always reveal mission identities, regardless of preferences."""
        access = self.grid_access_contract()
        return (self.hide_locked_grid_missions_var.get()
                and (not access or access['mode'] == 'Standard'))

    def grid_key_projection(self):
        access = self.grid_access_contract()
        if access is None:
            return None
        return access_projection(access, self.state.get('archipelago', {}),
                                 self.state.get('completed_missions', []))

    def grid_key_states(self):
        access = self.grid_access_contract()
        if not access or access['mode'] == 'Standard':
            return None
        projection = self.grid_key_projection()
        states = {}
        for code, node in self.state['grid']['nodes'].items():
            node['state'] = (COMPLETED if code in projection['completed'] else
                             UNLOCKED if code in projection['unlocked'] else LOCKED)
            states[code] = node['state']
        return states

    def grid_status_text(self, compact=False):
        if not self.state or self.active_progression_mode() != 'Grid Mode':
            return ''
        grid = self.state.get('grid', {})
        if not grid.get('nodes'):
            return ''
        goals = required_goals(grid)
        completed = set(self.state.get('completed_missions', ()))
        lookup = self.mission_lookup()
        remaining = [lookup.get(code, {}).get('title', code) for code in goals if code not in completed]
        remaining_label = ', '.join(remaining[:4] if compact else remaining) or 'None'
        if compact and len(remaining) > 4:
            remaining_label += f' (+{len(remaining)-4} more; full list in Details)'
        lines = [f'Required Victory Missions: {sum(code in completed for code in goals)} / {len(goals)} completed',
                 'Remaining: ' + remaining_label]
        access = self.grid_access_contract()
        if access and access['mode'] == 'Key Currency':
            projection = self.grid_key_projection()
            lines.append(f'Mission Keys received: {projection["received"]} | Starting: {access["starting_keys"]} | '
                         f'Spent: {projection["spent"]} | Available: {projection["available"]}')
            if access['protected_mission']:
                prior = len(projection['completed'] - {access['protected_mission']})
                lines.append(f'Completed missions before protected objective: {prior} / {access["minimum_completed_missions"]}')
        elif access and access['mode'] == 'Mission-Specific Keys':
            lines.append('Mission-Specific Keys: receive the matching mission item to unlock access.')
        return '\n'.join(lines)

    def grid_mission_requirements_text(self, code):
        if not self.state or self.active_progression_mode() != 'Grid Mode':
            return ''
        grid = self.state.get('grid', {})
        if code not in grid.get('nodes', {}):
            return ''
        node = grid['nodes'][code]
        required = code in required_goals(grid)
        lines = [f'Required Victory Mission: {"Yes" if required else "No"}',
                 f'Status: {node.get("state", LOCKED).title()}']
        access = self.grid_access_contract()
        if access and access['mode'] != 'Standard':
            projection = self.grid_key_projection()
            if access['mode'] == 'Key Currency':
                cost = access['prices'][code]
                lines.extend((f'Unlock cost: {cost} Mission Keys',
                              f'Available: {projection["available"]}',
                              'Purchased: ' + ('Yes' if code in self.state['archipelago'].get('mission_purchases', {}) else 'No')))
                if code in access['starting_missions']:
                    lines.append('Starting mission: free access')
                if code == access['protected_mission']:
                    prior = len(projection['completed'] - {code})
                    lines.append(f'Complete at least {access["minimum_completed_missions"]} missions: {prior}/{access["minimum_completed_missions"]}')
                if code not in projection['unlocked']:
                    blocker = purchase_blocker(access, projection, code)
                    lines.append(blocker or 'Select this mission, then Buy Mission Access.')
            elif code in access['mission_keys']:
                name = access['mission_keys'][code]
                lines.extend((f'Required item: {name}',
                              'Key received: ' + ('Yes' if name in projection['received_names'] else 'No')))
            else:
                lines.append('Starting mission: no key required')
        elif node.get('state') == LOCKED:
            lines.append('Complete an orthogonally neighboring mission to unlock access.')
        return '\n'.join(lines)

    def refresh_grid_access_controls(self):
        access = self.grid_access_contract()
        projection = (self.grid_key_projection()
                      if access and access['mode'] != 'Standard' else None)
        launch_allowed = (projection is None or self.selected_mission_code()
                          in projection['unlocked'] | projection['completed'])
        for name in ('launch_selected_button', 'primary_launch_button', 'compact_launch_button'):
            launch_button = getattr(self, name, None)
            if launch_button is not None:
                launch_button.configure(state='normal' if launch_allowed else 'disabled')
        label = getattr(self, 'grid_objectives_label', None)
        if label is not None:
            label.configure(text=self.grid_status_text(compact=True))
        button = getattr(self, 'grid_purchase_button', None)
        if button is None:
            return
        access = self.grid_access_contract()
        if not access or access['mode'] != 'Key Currency':
            button.grid_remove()
            return
        button.grid()
        code = self.selected_mission_code()
        projection = self.grid_key_projection()
        valid = bool(code in access['prices'] and code not in projection['unlocked'])
        blocker = purchase_blocker(access, projection, code) if valid else ''
        button.configure(text=(f'Buy Mission Access ({access["prices"][code]} keys)' if valid else 'Mission Access Unlocked'),
                         state='normal' if valid and not blocker and not getattr(self, 'coop_guest_connected', lambda: False)() else 'disabled')

    def buy_selected_grid_mission(self):
        """Tk serializes requests; one atomic save commits both charge and access."""
        access = self.grid_access_contract()
        if not access or access['mode'] != 'Key Currency' or getattr(self, 'coop_guest_connected', lambda: False)():
            return
        code = self.selected_mission_code()
        projection = self.grid_key_projection()
        if code in projection['unlocked']:
            return  # Repeated clicks never charge again.
        blocker = purchase_blocker(access, projection, code)
        if blocker:
            messagebox.showwarning('Mission Locked', blocker)
            return
        ap_state = self.state['archipelago']
        before = deepcopy(ap_state.get('mission_purchases', {}))
        ap_state['mission_purchases'] = {**before, code: access['prices'][code]}
        try:
            self.save_state(durable=True)
        except Exception as exc:
            ap_state['mission_purchases'] = before
            messagebox.showerror('Mission Purchase Failed', str(exc))
            return
        self.sync_grid_progression()
        self.refresh_grid_tiles()
        self.refresh_progress_view(refresh_unlocks=False)

    def apply_grid_key_receipts(self, receipts):
        """Store server receipts before acknowledgment; never turn keys into rewards."""
        access = self.grid_access_contract()
        if not access:
            return receipts
        ids = set(access['item_ids'].values())
        keys = tuple(receipt for receipt in receipts if int(self._archipelago_receipt_value(receipt, 'item', 0)) in ids)
        if not keys:
            return receipts
        session = getattr(self, '_archipelago_session', None)
        if session is None or not getattr(self, '_archipelago_session_validated', False):
            return ()
        ap_state = self.state['archipelago']
        before = ap_state.get('checkpoint')
        ap_state['checkpoint'] = session.checkpoint()
        try:
            self.save_state(durable=True)
        except Exception as exc:
            ap_state['checkpoint'] = before
            self.append_archipelago_history(f'Mission key receipt save failed: {exc}')
            return ()
        try:
            session.acknowledge_received([int(self._archipelago_receipt_value(receipt, 'index', -1)) for receipt in keys])
            ap_state['checkpoint'] = session.checkpoint()
            self.save_state(durable=True)
        except Exception as exc:
            self.append_archipelago_history(f'Mission key acknowledgment will recover on reconnect: {exc}')
        self.append_archipelago_history(f'Received {len(keys)} mission key item(s). Grid access updated.')
        self._request_archipelago_server_view_refresh('mission_keys')
        return tuple(receipt for receipt in receipts if int(self._archipelago_receipt_value(receipt, 'item', 0)) not in ids)
