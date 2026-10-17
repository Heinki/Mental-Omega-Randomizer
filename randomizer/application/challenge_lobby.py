"""Local player choices, peer display, and host-owned challenge settings."""

import tkinter as tk
from tkinter import ttk

from randomizer.challenges.catalogue import (
    COUNTRY_LABELS, allowed_colors, allowed_countries, map_config,
)
from randomizer.config.player import save_config
from randomizer.core.paths import GAME_ROOT
from randomizer.maps.ini import all_section_value_maps_preserve
from randomizer.ui.config import GAME_SPEEDS


class ChallengeLobbyController:
    def ensure_challenge_player_options(self):
        if hasattr(self, '_coop_house_label'):
            return
        sections = all_section_value_maps_preserve(
            (GAME_ROOT / 'Resources' / 'GameOptions.ini').read_text(encoding='latin-1').splitlines()
        )
        colors = next(values for key, values in sections.items() if key.lower() == 'mpcolors')
        self._coop_color_values = {
            label: int(value.split(',')[-1].strip())
            for label, value in colors.items() if not label.startswith(';')
        }
        country = self.config.get('coop_challenge_country', self.challenge_country_var.get())
        self._coop_house_label = tk.StringVar(
            master=self, value=COUNTRY_LABELS.get(country, COUNTRY_LABELS['UnitedStates']),
        )
        default_color = 'Red' if getattr(self, '_coop_role', None) and self._coop_role.get() == 'Join' else 'Teal'
        color = self.config.get('coop_challenge_color', default_color)
        self._coop_color_label = tk.StringVar(
            master=self, value=color if color in self._coop_color_values else default_color,
        )
        self._coop_player_summary = tk.StringVar(master=self, value='Connect to share player choices.')

    def own_challenge_player_options(self):
        self.ensure_challenge_player_options()
        country = next((key for key, label in COUNTRY_LABELS.items()
                        if label == self._coop_house_label.get()), None)
        color = self._coop_color_values.get(self._coop_color_label.get())
        if country is None or type(color) is not int:
            raise ValueError('Choose your challenge house and color in Co-op Connection.')
        return {'country': country, 'color': color}

    def validate_challenge_player_options(self, options):
        self.ensure_challenge_player_options()
        if (not isinstance(options, dict) or options.get('country') not in COUNTRY_LABELS
                or type(options.get('color')) is not int
                or options['color'] not in self._coop_color_values.values()):
            raise ValueError('Peer sent an invalid challenge house or color.')
        return {'country': options['country'], 'color': options['color']}

    def build_challenge_player_controls(self, parent, row):
        self.ensure_challenge_player_options()
        frame = ttk.LabelFrame(parent, text='Your challenge player', padding=8)
        frame.grid(row=row, column=0, columnspan=2, sticky='ew', pady=6)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text='House / country').grid(row=0, column=0, sticky='w', padx=(0, 8))
        self._coop_house_combo = ttk.Combobox(
            frame, textvariable=self._coop_house_label, values=tuple(COUNTRY_LABELS.values()),
            state='readonly', width=22,
        )
        self._coop_house_combo.grid(row=0, column=1, sticky='ew')
        ttk.Label(frame, text='Color').grid(row=1, column=0, sticky='w', padx=(0, 8), pady=4)
        self._coop_color_combo = ttk.Combobox(
            frame, textvariable=self._coop_color_label, values=tuple(self._coop_color_values),
            state='readonly', width=22,
        )
        self._coop_color_combo.grid(row=1, column=1, sticky='ew', pady=4)
        for combo in (self._coop_house_combo, self._coop_color_combo):
            combo.bind('<<ComboboxSelected>>', self.on_challenge_player_options_changed)
        ttk.Label(frame, textvariable=self._coop_player_summary, wraplength=420,
                  justify='left').grid(row=2, column=0, columnspan=2, sticky='w')
        self._coop_player_frame = frame
        self.refresh_challenge_player_controls()

    def challenge_player_choices_locked(self):
        process = getattr(self, 'active_game_process', None)
        return bool(getattr(self, '_coop_busy', False)
                    or (process is not None and process.poll() is None))

    def on_challenge_player_options_changed(self, _event=None):
        if self.challenge_player_choices_locked():
            return
        options = self.own_challenge_player_options()
        self.config['coop_challenge_country'] = options['country']
        self.config['coop_challenge_color'] = self._coop_color_label.get()
        save_config(self.config)
        self.publish_challenge_player_options()
        self.refresh_challenge_player_controls()

    def on_challenge_host_difficulty_changed(self, _event=None):
        if self.selected_mission_category() == 'challenge' and not self.coop_guest_connected():
            self.config['difficulty'] = self.difficulty_var.get()
            save_config(self.config)
            self.publish_challenge_player_options()

    def publish_challenge_player_options(self):
        lobby = getattr(self, '_coop_lobby', None)
        if not (lobby and lobby.connected and self.selected_mission_category() == 'challenge'):
            return
        message = {'type': 'player_options', **self.own_challenge_player_options()}
        if lobby.role == 'host':
            message['game_speed'] = self.get_selected_game_speed_value()
            message['difficulty'] = self.difficulty_var.get()
        try:
            lobby.send(message)
        except OSError as exc:
            self._record_coop_log('Player choice sync failed: ' + str(exc), error=True)

    def challenge_pair_options(self, mission):
        own = self.own_challenge_player_options()
        peer = getattr(self, '_coop_peer_options', None)
        if peer is None:
            raise ValueError('Wait for your brother to connect and choose his house and color.')
        peer = self.validate_challenge_player_options(peer)
        lobby = getattr(self, '_coop_lobby', None)
        if lobby is None or lobby.role not in {'host', 'guest'}:
            raise ValueError('Connect both launchers before starting a two-player challenge.')
        host, guest = (own, peer) if lobby.role == 'host' else (peer, own)
        conflicts = self.challenge_player_conflicts(mission, {'Host': host, 'Guest': guest})
        if conflicts:
            raise ValueError(' '.join(conflicts))
        return {'host': dict(host), 'guest': dict(guest)}

    def challenge_player_conflicts(self, mission, players):
        """Explain incompatible saved selections without changing either player."""
        _, _, metadata, _, _ = map_config(GAME_ROOT, mission['coop_name'])
        countries, colors = allowed_countries(metadata), allowed_colors(metadata)
        color_name = lambda value: next((label for label, code in self._coop_color_values.items()
                                         if code == value), str(value))
        conflicts = []
        invalid_houses = [
            f'{role}: {COUNTRY_LABELS[options["country"]]}'
            for role, options in players.items() if options['country'] not in countries
        ]
        if invalid_houses:
            conflicts.append('Unavailable house choices (' + '; '.join(invalid_houses)
                             + '). This challenge restricts these houses or uses them as enemies.')
            conflicts.append('Allowed houses: ' + ', '.join(COUNTRY_LABELS[country]
                                                           for country in countries) + '.')
        invalid_colors = [
            f'{role}: {color_name(options["color"])}'
            for role, options in players.items() if options['color'] not in colors
        ]
        if invalid_colors:
            conflicts.append('Reserved color choices (' + '; '.join(invalid_colors) + ').')
            conflicts.append('Allowed colors: ' + ', '.join(color_name(color)
                                                           for color in colors) + '.')
        if len({options['color'] for options in players.values()}) != len(players):
            conflicts.append('Both players chose the same color. One player must choose a different color.')
        return conflicts

    def receive_challenge_player_options(self, lobby, message):
        self._coop_peer_options = self.validate_challenge_player_options(message)
        if lobby.role == 'guest':
            speed = message.get('game_speed')
            if type(speed) is not int or speed not in range(7):
                raise ValueError('Host sent an invalid challenge game speed.')
            self.game_speed_var.set(next(label for label, value in GAME_SPEEDS if value == speed))
            difficulty = message.get('difficulty')
            if difficulty not in {'Casual', 'Normal', 'Mental'}:
                raise ValueError('Host sent an invalid challenge difficulty.')
            self.difficulty_var.set(difficulty)
        self.refresh_challenge_player_controls()

    def refresh_challenge_player_controls(self):
        frame = getattr(self, '_coop_player_frame', None)
        if frame is None or not frame.winfo_exists():
            return
        if self.selected_mission_category() != 'challenge':
            frame.grid_remove()
            return
        frame.grid()
        state = 'disabled' if self.challenge_player_choices_locked() else 'readonly'
        mission = self.selected_mission()
        # A new map may make a stored choice unavailable. Keep that choice
        # visible and explain the conflict rather than silently replacing it.
        self._coop_house_combo.configure(state=state, values=tuple(
            COUNTRY_LABELS.values()
        ))
        self._coop_color_combo.configure(state=state, values=tuple(
            self._coop_color_values
        ))
        own = self.own_challenge_player_options()
        peer = getattr(self, '_coop_peer_options', None)
        color_name = lambda value: next((label for label, code in self._coop_color_values.items()
                                         if code == value), str(value))
        text = f'You: {COUNTRY_LABELS[own["country"]]}, {color_name(own["color"])}.'
        if peer:
            text += f'  Peer: {COUNTRY_LABELS[peer["country"]]}, {color_name(peer["color"])}.'
        else:
            text += '  Waiting for peer choices.'
        text += f'\nHost game speed: {self.game_speed_var.get()}.'
        if mission:
            try:
                if peer:
                    self.challenge_pair_options(mission)
                else:
                    conflicts = self.challenge_player_conflicts(mission, {'You': own})
                    if conflicts:
                        text += '\n' + ' '.join(conflicts)
            except ValueError as exc:
                text += '\n' + str(exc)
        self._coop_player_summary.set(text)
