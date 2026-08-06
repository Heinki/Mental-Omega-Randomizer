"""Manual Starting Unlocks catalogue, selection, and navigation."""

from ._dependencies import (
    ARSENAL_MODE,
    BUFF_TARGETS,
    CAMPAIGN_FILTERS,
    REWARD_POOL,
    STARTING_UNLOCK_CATEGORY_LABELS,
    canonical_reward,
    cameo_extraction_pending,
    custom_sidebar_preview,
    ensure_superweapon_cameos,
    ensure_unit_cameos,
    log_event,
    normalize_starting_unlock_reward_names,
    reward_display_name,
    tk,
    tech_ids_for_rewards,
    traceback,
)


class StartingUnlocksController:

    @staticmethod
    def reward_is_permanent_starting_unlock(reward):
        return bool(
            reward.get('kind') not in {'buff', 'message', 'retired'}
            and not reward.get('retired_reward')
            and (
                reward.get('kind') == 'superweapon'
                or tech_ids_for_rewards([reward])
            )
        )

    def permanent_starting_unlock_names(self):
        cached = self.__dict__.get('_permanent_starting_unlock_names')
        if cached is None:
            cached = frozenset(
                reward.get('name')
                for reward in map(canonical_reward, REWARD_POOL)
                if self.reward_is_permanent_starting_unlock(reward)
            )
            self._permanent_starting_unlock_names = cached
        return cached

    def filter_permanent_starting_unlock_names(self, names):
        allowed = self.permanent_starting_unlock_names()
        filtered = []
        for name in normalize_starting_unlock_reward_names(names):
            canonical_name = canonical_reward({'name': name}).get('name', name)
            if canonical_name in allowed:
                filtered.append(canonical_name)
        return normalize_starting_unlock_reward_names(filtered)

    def canonical_starting_unlock_names(self):
        return self.filter_permanent_starting_unlock_names(sorted({
            canonical_reward({'name': name}).get('name', name)
            for name in getattr(self, 'manual_starting_reward_names', set())
        }, key=str.casefold))

    def active_starting_unlock_names(self):
        return self.filter_permanent_starting_unlock_names(
            self.active_reward_settings().get('starting_unlock_rewards')
        )

    @staticmethod
    def starting_unlock_category(reward):
        if reward.get('kind') == 'superweapon':
            return {
                'aid': 'Support powers',
                'offensive': 'Superweapons',
            }.get(reward.get('power_category'), 'Other unlocks')
        tech_ids = tech_ids_for_rewards([reward])
        if tech_ids:
            categories = {
                BUFF_TARGETS.get(unit_id, {}).get('category')
                for unit_id in tech_ids
            }
            if categories.intersection({'defenses', 'special_buildings'}):
                return 'Buildings'
            return 'Units'
        return 'Other unlocks'

    def starting_unlock_entries(self):
        cached = self.__dict__.get('_starting_unlock_entries')
        if cached is not None:
            return cached
        entries = []
        seen = set()
        for source in REWARD_POOL:
            reward = canonical_reward(source)
            name = reward.get('name')
            if (
                not name
                or name in seen
                or not self.reward_is_permanent_starting_unlock(reward)
                or reward.get('kind') in {'message', 'retired'}
                or reward.get('retired_reward')
            ):
                continue
            seen.add(name)
            factions = tuple(reward.get('factions') or ('Other',))
            entries.append({
                'name': name,
                'label': reward_display_name(reward),
                'category': self.starting_unlock_category(reward),
                'factions': factions,
                'faction': ' / '.join(factions),
                'reward': reward,
            })
        category_rank = {
            label: index
            for index, label in enumerate(STARTING_UNLOCK_CATEGORY_LABELS)
        }
        faction_rank = {
            'Allies': 0, 'Soviets': 1, 'Epsilon': 2,
            'Foehn': 3, 'Neutral': 4, 'Other': 5,
        }
        entries.sort(key=lambda entry: (
            category_rank.get(entry['category'], 99),
            min(faction_rank.get(item, 5) for item in entry['factions']),
            entry['label'].casefold(),
        ))
        self._starting_unlock_entries = tuple(entries)
        return self._starting_unlock_entries

    def starting_unlock_visible_for_campaign(self, entry):
        if self.reward_mode_var.get() == ARSENAL_MODE:
            selected_factions = {
                faction for faction, variable in self.arsenal_faction_vars.items()
                if variable.get()
            }
            return bool(
                set(entry['factions']).intersection(
                    selected_factions | {'Neutral'}
                )
            )
        selected = self.campaign_var.get()
        factions = set(entry['factions'])
        if selected == CAMPAIGN_FILTERS[0]:
            return True
        if selected == 'Foehn':
            return bool(factions.intersection({
                'Allies', 'Soviets', 'Foehn', 'Neutral',
            }))
        return bool(factions.intersection({selected, 'Neutral'}))

    def visible_starting_unlock_entries(self):
        category = (
            self.starting_unlock_category_var.get()
            if hasattr(self, 'starting_unlock_category_var')
            else 'All categories'
        )
        search = (
            self.starting_unlock_search_var.get().strip().casefold()
            if hasattr(self, 'starting_unlock_search_var')
            else ''
        )
        return [
            entry
            for entry in self.starting_unlock_entries()
            if self.starting_unlock_visible_for_campaign(entry)
            and (category == 'All categories' or entry['category'] == category)
            and (
                not search
                or search in entry['label'].casefold()
                or search in entry['faction'].casefold()
                or search in entry['category'].casefold()
            )
        ]

    @staticmethod
    def starting_unlock_cameo_source(entry):
        """Return one stable image source shared by equivalent reward rows."""
        reward = entry['reward']
        power_id = str(reward.get('superweapon') or '').upper()
        if power_id:
            asset_name = reward.get('superweapon_sidebar_image')
            if asset_name:
                return 'asset', str(asset_name)
            return 'power', str(
                reward.get('cameo_superweapon') or power_id
            ).upper()
        unit_id = str(reward.get('unit') or '').upper()
        if unit_id:
            return 'unit', unit_id
        tech_ids = sorted(tech_ids_for_rewards([reward]))
        if tech_ids:
            return 'unit', tech_ids[0]
        return 'placeholder', entry['category']

    def resolve_starting_unlock_cameo_paths(self, entries):
        """Batch-resolve unique unit and power artwork; never load per row."""
        sources = {
            self.starting_unlock_cameo_source(entry) for entry in entries
        }
        unit_ids = {value for kind, value in sources if kind == 'unit'}
        power_ids = {value for kind, value in sources if kind == 'power'}
        unit_paths = self.__dict__.setdefault(
            'starting_unlock_unit_cameo_paths', {}
        )
        power_paths = self.__dict__.setdefault(
            'starting_unlock_power_cameo_paths', {}
        )
        try:
            missing_units = unit_ids - set(unit_paths)
            if missing_units:
                unit_paths.update(ensure_unit_cameos(missing_units))
            missing_powers = power_ids - set(power_paths)
            if missing_powers:
                power_paths.update(ensure_superweapon_cameos(missing_powers))
        except Exception:
            log_event(
                'starting_unlock_cameos_failed',
                traceback=traceback.format_exc(),
            )
        if (
            (unit_ids - set(unit_paths) or power_ids - set(power_paths))
            and cameo_extraction_pending()
            and not self.__dict__.get('starting_unlock_cameo_retry_after_id')
        ):
            self.starting_unlock_cameo_retry_after_id = self.after(
                1000, self.retry_starting_unlock_cameos
            )

    def retry_starting_unlock_cameos(self):
        self.starting_unlock_cameo_retry_after_id = None
        if self.winfo_exists():
            self.refresh_starting_unlocks_view()

    def starting_unlock_placeholder_photo(self, category):
        cache = self.__dict__.setdefault('starting_unlock_photo_cache', {})
        key = ('placeholder', category)
        if key in cache:
            return cache[key]
        colors = {
            'Units': '#315b82',
            'Buildings': '#6b5730',
            'Superweapons': '#7a3535',
            'Support powers': '#376653',
            'Other unlocks': '#555555',
        }
        photo = tk.PhotoImage(master=self, width=60, height=48)
        photo.put(colors.get(category, '#555555'), to=(0, 0, 60, 48))
        photo.put('#aaaaaa', to=(0, 0, 60, 2))
        photo.put('#aaaaaa', to=(0, 46, 60, 48))
        photo.put('#aaaaaa', to=(0, 0, 2, 48))
        photo.put('#aaaaaa', to=(58, 0, 60, 48))
        question = ('01110', '10001', '00010', '00100', '00100', '00000', '00100')
        for row, pixels in enumerate(question):
            for column, pixel in enumerate(pixels):
                if pixel == '1':
                    x, y = 20 + column * 4, 9 + row * 4
                    photo.put('#ffffff', to=(x, y, x + 4, y + 4))
        cache[key] = photo
        return photo

    def starting_unlock_photo(self, entry):
        kind, value = self.starting_unlock_cameo_source(entry)
        if kind == 'placeholder':
            return self.starting_unlock_placeholder_photo(value)
        cache = self.__dict__.setdefault('starting_unlock_photo_cache', {})
        key = (kind, value)
        if key in cache:
            return cache[key]
        path = None
        if kind == 'unit':
            path = self.starting_unlock_unit_cameo_paths.get(value)
        elif kind == 'power':
            path = self.starting_unlock_power_cameo_paths.get(value)
        elif kind == 'asset':
            try:
                path = custom_sidebar_preview(value)
            except Exception:
                path = None
        if path:
            try:
                photo = tk.PhotoImage(master=self, file=str(path))
                if photo.width() > 60 or photo.height() > 48:
                    factor = max(
                        1,
                        (photo.width() * 3 + 59) // 60,
                        (photo.height() * 3 + 47) // 48,
                    )
                    photo = photo.zoom(3, 3).subsample(factor, factor)
                cache[key] = photo
                return photo
            except (OSError, tk.TclError):
                pass
        return self.starting_unlock_placeholder_photo(entry['category'])

    def refresh_starting_unlocks_view(self):
        tree = getattr(self, 'starting_unlocks_tree', None)
        if tree is None:
            return
        selected_names = set(self.canonical_starting_unlock_names())
        entries = self.visible_starting_unlock_entries()
        self.resolve_starting_unlock_cameo_paths(entries)
        tree.delete(*tree.get_children())
        self.starting_unlock_tree_names = {}
        for index, entry in enumerate(entries):
            item_id = f'starting-{index}'
            is_selected = entry['name'] in selected_names
            tree.insert(
                '', 'end', iid=item_id,
                image=self.starting_unlock_photo(entry),
                values=(
                    entry['label'],
                    entry['category'],
                    entry['faction'],
                ),
                tags=('starting_selected',) if is_selected else (),
            )
            self.starting_unlock_tree_names[item_id] = entry['name']
        visible_selected = sum(
            1 for entry in entries if entry['name'] in selected_names
        )
        self.starting_unlock_status_label.configure(
            text=(
                f'{len(selected_names)} total selected; '
                f'{visible_selected}/{len(entries)} visible selected. '
                'Double-click or press Space to toggle.'
            )
        )

    def toggle_starting_unlock_tree_selection(self, event=None):
        if self.gameplay_settings_locked():
            return 'break'
        tree = getattr(self, 'starting_unlocks_tree', None)
        if tree is None:
            return 'break'
        item_ids = list(tree.selection())
        if event is not None and getattr(event, 'num', None) == 1:
            clicked = tree.identify_row(event.y)
            if clicked:
                item_ids = [clicked]
        names = {
            self.starting_unlock_tree_names[item_id]
            for item_id in item_ids
            if item_id in self.starting_unlock_tree_names
        }
        if not names:
            return 'break'
        selected = set(self.canonical_starting_unlock_names())
        if names.issubset(selected):
            selected.difference_update(names)
        else:
            selected.update(names)
        self.manual_starting_reward_names = selected
        self.save_current_launcher_config()
        self.refresh_starting_unlocks_view()
        return 'break'

    def set_visible_starting_unlocks(self, include):
        if self.gameplay_settings_locked():
            return
        names = {entry['name'] for entry in self.visible_starting_unlock_entries()}
        selected = set(self.canonical_starting_unlock_names())
        if include:
            selected.update(names)
        else:
            selected.difference_update(names)
        self.manual_starting_reward_names = selected
        self.save_current_launcher_config()
        self.refresh_starting_unlocks_view()

    def show_starting_unlocks_settings(self):
        if self.gameplay_settings_locked():
            return
        self.workspace_tabs.select(self.advanced_tab)
        self.advanced_notebook.select(self.starting_unlocks_tab)
        self.refresh_starting_unlocks_view()
        self.after_idle(self.starting_unlock_search_entry.focus_set)
