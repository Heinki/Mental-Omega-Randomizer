"""Host-controlled Shop mission stage without sharing either player's economy."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import re

from randomizer.shop.config import SHOP_CONFIG
from randomizer.shop.missions import classify_mission
from randomizer.shop.model import MissionEconomyClass, MissionOffer, RunStatus
from randomizer.shop.state import normalize_shop_run
from randomizer.coop.shop_loadout import validate_shop_modifiers


STAGE_SCHEMA = 2
_CODE = re.compile(r'COOP_[A-Z0-9_]+\Z')


def stage_snapshot(run) -> dict:
    """Export only mission-control fields from one active Shop run."""
    if run is None or run.status is not RunStatus.ACTIVE:
        raise ValueError('Host needs an active Shop run.')
    if not run.mission_offers:
        raise ValueError('Host Shop stage has no mission offers.')
    validate_shop_modifiers(run.modifiers)
    return {
        'schema': STAGE_SCHEMA,
        'seed': run.seed,
        'stage': run.stage,
        'run_length': run.run_length,
        'completed_missions': list(run.completed_missions),
        'offers': [offer.to_dict() for offer in run.mission_offers],
        'selected_mission_code': run.selected_mission_code or '',
        'mission_committed': run.mission_committed,
        'rerolls_used': run.rerolls_used,
        'assisted_mission_code': run.assisted_mission_code or '',
        'difficulty_assists_used': run.difficulty_assists_used,
        'eligible_mission_codes': sorted(run.eligible_mission_codes),
        'endless': run.endless,
        'allow_repeats': run.allow_repeats,
        'mission_modifiers': sorted(set(run.modifiers) & {
            'no_safety_net', 'narrow_intelligence', 'hardcore', 'faction_roulette',
        }),
    }


def stage_digest(snapshot: dict) -> str:
    return hashlib.sha256(json.dumps(
        snapshot, sort_keys=True, separators=(',', ':'),
    ).encode('utf-8')).hexdigest()


def recovery_result_message(run):
    """Rebuild the host's last durable Shop result after a lobby reconnect."""
    if run is None or not run.coop_last_result:
        return None
    result = run.coop_last_result
    stage = result['stage']
    code = result['code']
    if result['outcome'] == 'victory':
        if (code not in run.completed_missions
                or not (run.stage > stage or run.status is RunStatus.COMPLETED)):
            raise ValueError('Stored co-op Shop victory differs from host run.')
        return {'type': 'shop_victory', 'seed': run.seed,
                'stage': stage, 'code': code}
    if result['revived']:
        if (run.status is not RunStatus.ACTIVE or run.stage != stage
                or run.emergency_revivals_used < 1):
            raise ValueError('Stored co-op Shop revival differs from host run.')
    elif (run.status is not RunStatus.FAILED or run.failed_stage != stage
          or run.failed_mission_code != code):
        raise ValueError('Stored co-op Shop failure differs from host run.')
    return {'type': 'shop_failure', 'seed': run.seed,
            'stage': stage, 'code': code,
            'revived': result['revived'], 'recovery': True}


def apply_stage_snapshot(run, snapshot: dict, missions: dict):
    """Apply host mission decisions; preserve guest purchases, buffs, and Ore."""
    if run is None or run.status is not RunStatus.ACTIVE:
        raise ValueError('Guest needs an active Shop run.')
    if not isinstance(snapshot, dict):
        raise ValueError('Invalid host Shop stage snapshot.')
    if type(snapshot.get('schema')) is not int or snapshot['schema'] != STAGE_SCHEMA:
        raise ValueError('Incompatible Shop stage snapshot. Update both launchers.')
    local = stage_snapshot(run)
    if set(snapshot) != set(local):
        raise ValueError('Invalid host Shop stage snapshot.')
    if (type(snapshot['endless']) is not bool or type(snapshot['allow_repeats']) is not bool
            or any(snapshot[key] != local[key] for key in (
                'eligible_mission_codes', 'endless', 'allow_repeats', 'mission_modifiers'))):
        raise ValueError('Shop players need matching mission pools, repeat rules, and mission-control modifiers.')
    if (not isinstance(snapshot['seed'], str)
            or type(snapshot['stage']) is not int
            or type(snapshot['run_length']) is not int
            or not isinstance(snapshot['completed_missions'], list)
            or snapshot['seed'] != run.seed or snapshot['stage'] != run.stage
            or snapshot['run_length'] != run.run_length
            or snapshot['completed_missions'] != list(run.completed_missions)):
        raise ValueError('Shop players need the same seed, stage, and completed missions.')
    raw_offers = snapshot['offers']
    if (not isinstance(raw_offers, list)
            or not 1 <= len(raw_offers) <= SHOP_CONFIG.mission_offer_count):
        raise ValueError('Invalid host Shop mission offers.')
    offers = []
    for entry in raw_offers:
        if not isinstance(entry, dict) or set(entry) != {'mission_code', 'class'}:
            raise ValueError('Invalid host Shop mission offer.')
        code = entry['mission_code']
        if (not isinstance(code, str) or not _CODE.fullmatch(code) or code not in missions
                or run.eligible_mission_codes and code not in run.eligible_mission_codes):
            raise ValueError('Host offered a mission outside guest co-op catalogue.')
        try:
            economy_class = MissionEconomyClass(entry['class'])
        except (TypeError, ValueError) as exc:
            raise ValueError('Invalid host Shop mission class.') from exc
        if classify_mission(missions[code]) is not economy_class:
            raise ValueError('Host Shop mission class differs from guest catalogue.')
        offers.append(MissionOffer(code, economy_class))
    codes = [offer.mission_code for offer in offers]
    if len(codes) != len(set(codes)):
        raise ValueError('Host Shop mission offers repeat a map.')
    selected = snapshot['selected_mission_code']
    assisted = snapshot['assisted_mission_code']
    committed = snapshot['mission_committed']
    rerolls = snapshot['rerolls_used']
    assists = snapshot['difficulty_assists_used']
    if (not isinstance(selected, str) or selected and selected not in codes
            or not isinstance(assisted, str) or assisted and assisted not in codes
            or not isinstance(committed, bool) or committed and not selected
            or not isinstance(rerolls, int) or isinstance(rerolls, bool)
            or not run.rerolls_used <= rerolls <= 10000
            or not isinstance(assists, int) or isinstance(assists, bool)
            or not run.difficulty_assists_used <= assists <= 10000):
        raise ValueError('Invalid host Shop mission decision.')
    if run.mission_committed and (
        not committed or selected != run.selected_mission_code
        or tuple(offers) != run.mission_offers
        or rerolls != run.rerolls_used
        or assisted != (run.assisted_mission_code or '')
        or assists != run.difficulty_assists_used
    ):
        raise ValueError('Host cannot change a committed Shop mission.')
    updated = replace(
        run, mission_offers=tuple(offers), selected_mission_code=selected or None,
        mission_committed=committed, rerolls_used=rerolls,
        assisted_mission_code=assisted or None,
        difficulty_assists_used=assists,
    )
    return normalize_shop_run(updated.to_dict())
