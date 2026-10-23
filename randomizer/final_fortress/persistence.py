"""One atomic document for balance, purchases, preferences, and run receipts."""

from contextlib import contextmanager
from copy import deepcopy
import os
from pathlib import Path
import uuid

from randomizer.core.paths import APP_DIR
from randomizer.core.storage import atomic_write_json, atomic_write_text, read_json_object
from randomizer.challenges.catalogue import SIDE_COUNTRIES

from .config import DIFFICULTY_IDS, validate_config, validate_wave_multiplier
from .planning import build_run_plan
from .state import new_state, normalize_state


class FinalFortressPersistenceError(RuntimeError):
    """A failed save must not become a successful UI purchase or reward."""


class FinalFortressRepository:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else APP_DIR / 'final_fortress_state.json'

    @contextmanager
    def _locked(self):
        """OS lock releases on process exit, including after a crash."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            handle = self.path.with_suffix('.lock').open('a+b')
        except OSError as exc:
            raise FinalFortressPersistenceError(str(exc)) from exc
        acquired = False
        try:
            if os.name == 'nt':
                import msvcrt
                if handle.seek(0, os.SEEK_END) == 0:
                    handle.write(b'\0')
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
            yield
        except (OSError, ValueError) as exc:
            raise FinalFortressPersistenceError(
                f'Cannot update Final Fortress progression at {self.path}: {exc}'
            ) from exc
        finally:
            if acquired and os.name == 'nt':
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            handle.close()

    def _read(self):
        if not self.path.exists():
            return new_state()
        try:
            return normalize_state(read_json_object(self.path))
        except (ValueError, TypeError, KeyError) as exc:
            raise FinalFortressPersistenceError(
                f'Cannot read Final Fortress progression at {self.path}: {exc}'
            ) from exc

    def load(self):
        with self._locked():
            return self._read()

    def initialize_all_unlocks(self, config):
        """Keep testing unlocks current without resetting selections or run receipts."""
        from .profiles import PROFILE_PATHS, STANDARD_PROFILE, all_unlocks_state, require_local_testing
        require_local_testing()
        validate_config(config)
        if self.path.resolve() == PROFILE_PATHS[STANDARD_PROFILE].resolve():
            raise ValueError('Use a separate profile for testing unlocks.')

        def change(state):
            if self.path.exists():
                from .perks import ranks
                changed = False
                for perk in config['perks']:
                    key, maximum = perk['id'], len(ranks(perk))
                    if key not in state['owned_perks']:
                        state['owned_perks'].append(key)
                        state['selected_perks'].append(key)
                        changed = True
                    if state['perk_ranks'].get(key, 0) < maximum:
                        state['perk_ranks'][key] = maximum
                        changed = True
                return None if changed else False
            state.update(all_unlocks_state(config))
        return self._update(change)[0]

    def _update(self, change):
        with self._locked():
            state = self._read()
            result = change(state)
            normalized = normalize_state(state)
            if result is not False:
                atomic_write_json(self.path, normalized)
            return normalized, result

    def set_map(self, config, map_id):
        from .maps import select_map
        select_map(config, map_id)
        def change(state):
            state['preferences']['map_id'] = map_id
        return self._update(change)[0]

    def set_difficulty(self, difficulty):
        if difficulty not in DIFFICULTY_IDS:
            raise ValueError('Unknown Final Fortress difficulty.')

        def change(state):
            state['preferences']['difficulty'] = difficulty
        return self._update(change)[0]

    def set_workspace_selected(self, selected):
        if type(selected) is not bool:
            raise ValueError('Game mode selection must be boolean.')

        def change(state):
            state['preferences']['workspace_selected'] = selected
        return self._update(change)[0]

    def set_mental_ai_boost(self, enabled):
        if type(enabled) is not bool:
            raise ValueError('Mental AI Boost must be boolean.')

        def change(state):
            state['preferences']['mental_ai_boost'] = enabled
        return self._update(change)[0]

    def purchase_perk(self, config, perk_id):
        validate_config(config)
        perk = next((entry for entry in config['perks'] if entry['id'] == perk_id), None)
        if perk is None:
            raise ValueError('Unknown Final Fortress perk.')

        def change(state):
            from .perks import next_price, owned_rank
            rank = owned_rank(state, perk_id)
            price = next_price(perk, rank)
            if price is None:
                raise ValueError('This permanent perk is already at maximum rank.')
            if state['gems'] < price:
                raise ValueError(f'Need {price} Defensive Points for rank {rank + 1}; you have {state["gems"]}. Earn Defensive Points by surviving or collecting camp crates.')
            state['gems'] -= price
            state['perk_ranks'][perk_id] = rank + 1
            if perk_id not in state['owned_perks']:
                state['owned_perks'].append(perk_id)
            if perk_id not in state['selected_perks']:
                state['selected_perks'].append(perk_id)
        return self._update(change)[0]

    def set_wave_multiplier(self, wave_multiplier):
        validate_wave_multiplier(wave_multiplier)

        def change(state):
            state['preferences']['wave_multiplier'] = wave_multiplier
        return self._update(change)[0]

    def select_challenge(self, config, challenge_id, selected, stacks=1):
        return self.select_challenges(config, {challenge_id: (selected, stacks)})

    def select_challenges(self, config, choices):
        """Validate and save a whole selection in one atomic profile update."""
        validate_config(config)
        catalogue = {entry['id']: entry for entry in config.get('challenges', [])}
        if not isinstance(choices, dict) or not choices or set(choices) - catalogue.keys():
            raise ValueError('Invalid Final Fortress challenge selection.')
        from .challenges import maximum
        for challenge_id, choice in choices.items():
            if not isinstance(choice, (tuple, list)) or len(choice) != 2 or type(choice[0]) is not bool:
                raise ValueError('Invalid Final Fortress challenge selection.')
            entry = catalogue[challenge_id]
            cap = maximum(entry) if 'enemy_effect_id' in entry else 1
            stacks = choice[1]
            if type(stacks) is not int or not 1 <= stacks <= cap:
                raise ValueError('Choose a stack count within the Grid buff limit.')

        def change(state):
            chosen = state['preferences']['selected_challenges']
            for challenge_id, (selected, stacks) in choices.items():
                if selected and challenge_id not in chosen:
                    chosen.append(challenge_id)
                elif not selected and challenge_id in chosen:
                    chosen.remove(challenge_id)
                state['preferences']['challenge_stacks'][challenge_id] = stacks
        return self._update(change)[0]

    def set_player_country(self, country):
        if country not in SIDE_COUNTRIES:
            raise ValueError('Choose a playable Mental Omega country.')

        def change(state):
            state['preferences']['player_country'] = country
        return self._update(change)[0]

    def select_perk(self, perk_id, selected):
        if type(selected) is not bool:
            raise ValueError('Perk selection must be boolean.')

        def change(state):
            if perk_id not in state['owned_perks']:
                raise ValueError('Purchase this permanent perk first.')
            if selected and perk_id not in state['selected_perks']:
                state['selected_perks'].append(perk_id)
            elif not selected and perk_id in state['selected_perks']:
                state['selected_perks'].remove(perk_id)
        return self._update(change)[0]

    def begin_run(self, config, *, difficulty, seed, player_country, wave_multiplier=None,
                  mental_ai_boost=None, coop_players=()):
        """Commit the exact run snapshot before starting its game process."""
        snapshot = deepcopy(config)

        def change(state):
            if state['run'] is not None and state['run']['status'] == 'active':
                raise ValueError('Finish or abandon the active Final Fortress run first.')
            multiplier = (state['preferences']['wave_multiplier']
                          if wave_multiplier is None else wave_multiplier)
            plan = build_run_plan(
                snapshot, difficulty=difficulty, seed=seed, player_country=player_country,
                selected_perks=[key for key in state['selected_perks']
                                if key in {entry['id'] for entry in snapshot['perks']}],
                perk_ranks=state['perk_ranks'], wave_multiplier=multiplier,
                selected_challenges=[key for key in state['preferences']['selected_challenges']
                                     if key in {entry['id'] for entry in snapshot.get('challenges', [])}],
                challenge_stacks=state['preferences']['challenge_stacks'],
                mental_ai_boost=(state['preferences']['mental_ai_boost']
                                 if mental_ai_boost is None else mental_ai_boost),
                coop_players=coop_players,
            )
            state['run'] = {
                'id': uuid.uuid4().hex, 'status': 'active',
                'config': snapshot, 'plan': plan, 'claimed_events': [],
            }
            if coop_players:
                state['run']['coop_player'] = 0
                state['coop_run_ids'].append(state['run']['id'])
            return state['run']['id']
        return self._update(change)

    def join_coop_run(self, run, player_name):
        """Import only the frozen run; keep this player's wallet and purchases."""
        from randomizer.coop.direct import _name
        from .state import new_state
        _name(player_name)
        snapshot = deepcopy(run)
        players = snapshot.get('plan', {}).get('coop_players', [])
        if player_name not in players or players.index(player_name) == 0:
            raise ValueError('This player is not a guest in the Fortress roster.')
        if snapshot.get('status') != 'active' or snapshot.get('claimed_events') != []:
            raise ValueError('Only a fresh Fortress co-op run can be joined.')
        snapshot['coop_player'] = players.index(player_name)
        # Validate host input independently before touching local progression.
        candidate = new_state()
        candidate['run'] = snapshot
        candidate['coop_run_ids'].append(snapshot['id'])
        normalize_state(candidate)

        def change(state):
            if snapshot['id'] in state['coop_run_ids']:
                raise ValueError('This Fortress co-op run was already joined; rewards cannot be replayed.')
            if state['run'] is not None and state['run']['status'] == 'active':
                raise ValueError('Finish or recover the previous Fortress run before joining.')
            state['coop_run_ids'].append(snapshot['id'])
            state['run'] = snapshot
        return self._update(change)[0]

    def record_event(self, run_id, event_id):
        """Apply only a verified engine event, once, against its committed run.

        No wall-clock rewards or manual completion button call this method.
        The dedicated watcher binds fresh map markers to this exact run ID.
        """
        return self.record_events(run_id, [event_id])

    def recover_finished_run(self, log_path):
        """Repair a missed result only from this frozen run's native markers.

        Read the complete real log outside the save lock. Recheck the run under
        lock, preserve all prior receipts, and credit only missing verified
        events. A copied map restart or a conflicting terminal result is not
        eligible. Call on a worker when no game is running.
        """
        from .results import FinalFortressResultWatch
        snapshot = self.load()['run']
        if snapshot is None:
            return self.load(), False
        from .coop import result_identity
        name, transfers, slot = result_identity(snapshot)
        watch = FinalFortressResultWatch.read_completed_log(
            log_path, snapshot['id'], snapshot['plan'], player_name=name,
            initial_transfers=transfers, coop_slot=slot)
        if not watch.started or watch.result not in ('victory', 'defeat'):
            return self.load(), False
        events = list(dict.fromkeys([*watch.events, watch.result]))

        def change(state):
            run = state['run']
            if run is None or run['id'] != snapshot['id'] or run['plan'] != snapshot['plan']:
                raise ValueError('Final Fortress run changed during result recovery.')
            if run['status'] not in ('active', 'abandoned', watch.result):
                raise ValueError('Verified result conflicts with an existing final result.')
            missing = [event for event in events if event not in run['claimed_events']]
            counts_changed = watch.kill_counts is not None and run.get('kill_counts') != watch.kill_counts
            if not missing and not counts_changed and run['status'] == watch.result:
                return False
            backup = self.path.with_name(self.path.stem + '.before_recovery.' + run['id'] + '.json')
            if self.path.exists() and not backup.exists():
                atomic_write_text(backup, self.path.read_text(encoding='utf-8'), encoding='utf-8')
            verified = list(dict.fromkeys([*run['claimed_events'], *events]))
            nonterminal = [event for event in verified if event not in ('victory', 'defeat', 'abandoned')]
            run['claimed_events'] = [event for event in nonterminal if not event.startswith('kills:')]
            run['claimed_events'].append(watch.result)
            run['claimed_events'].extend(event for event in nonterminal if event.startswith('kills:'))
            state['gems'] += sum(run['plan']['gem_rewards'].get(event, 0) for event in missing)
            run['status'] = watch.result
            if watch.kill_counts is not None:
                run['kill_counts'] = deepcopy(watch.kill_counts)
            return True
        return self._update(change)

    def record_events(self, run_id, event_ids, *, kill_counts=None):
        """Save a verified poll's receipts together, with one atomic write."""
        events = list(dict.fromkeys(event_ids))

        def change(state):
            run = state['run']
            if run is None or run['id'] != run_id:
                raise ValueError('Final Fortress event belongs to another run.')
            rewards = run['plan']['gem_rewards']
            changed = False
            for event_id in events:
                if event_id in run['claimed_events']:
                    continue
                performance = (event_id.startswith('kills:')
                               and run['status'] in {'victory', 'defeat'})
                if run['status'] != 'active' and not performance:
                    raise ValueError('Final Fortress run has already ended.')
                if event_id not in rewards and event_id not in {'defeat', 'abandoned'}:
                    raise ValueError('Unknown Final Fortress event.')
                state['gems'] += rewards.get(event_id, 0)
                run['claimed_events'].append(event_id)
                if event_id in {'victory', 'defeat', 'abandoned'}:
                    run['status'] = event_id
                changed = True
            if kill_counts is not None and run.get('kill_counts') != kill_counts:
                if run['status'] not in {'victory', 'defeat'}:
                    raise ValueError('Kill counters require a verified final result.')
                run['kill_counts'] = deepcopy(kill_counts)
                changed = True
            return changed
        return self._update(change)
