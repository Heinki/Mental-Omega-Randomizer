"""Mission classification and deterministic Shop Mode offer generation."""

import random

from randomizer.missions.catalogue import (
    FINALE_MISSION_CODES,
    FINALE_STAGE_SCORE,
    LOW_LEVEL_STAGE_MAX,
    OPERATION_MISSION_CODES,
    mission_reward_class,
    mission_stage_score,
)

from .config import SHOP_CONFIG
from .model import MissionEconomyClass, MissionOffer, ShopModeConfig


_CLASS_ORDER = tuple(MissionEconomyClass)


def classify_mission(mission):
    """Adapt existing mission metadata into one Shop economy class."""
    mission = mission if isinstance(mission, dict) else {'code': mission}
    code = str(mission.get('code') or '').upper()
    explicit = str(mission.get('reward_class') or '').lower()
    if explicit:
        try:
            return MissionEconomyClass(explicit)
        except ValueError as exc:
            raise ValueError(
                f'Invalid mission reward_class for {code or "<unknown>"}: '
                f'{explicit!r}'
            ) from exc
    configured = mission_reward_class(code)
    if configured:
        return MissionEconomyClass(configured)
    if mission.get('operation') or code in OPERATION_MISSION_CODES:
        return MissionEconomyClass.OPERATION
    if code in FINALE_MISSION_CODES:
        return MissionEconomyClass.FINALE
    score = mission_stage_score(mission)
    if score >= FINALE_STAGE_SCORE:
        return MissionEconomyClass.FINALE
    if score <= LOW_LEVEL_STAGE_MAX:
        return MissionEconomyClass.ACT_1
    return MissionEconomyClass.ACT_2


def _stage_weights(stage, run_length, config):
    progress_percent = min(100, max(1, stage) * 100 // max(1, run_length))
    for profile in config.stage_class_weights:
        if progress_percent <= profile.through_percent:
            return profile.weights
    return config.stage_class_weights[-1].weights


def mission_classes_for_stage(
    stage, run_length=None, config: ShopModeConfig = SHOP_CONFIG
):
    """Return mission classes explicitly enabled for one run stage."""
    run_length = config.run_length if run_length is None else int(run_length)
    weights = _stage_weights(int(stage), run_length, config)
    return frozenset(
        class_id for class_id in _CLASS_ORDER
        if int(weights.get(class_id, 0)) > 0
    )


def _weighted_class_choice(rng, classes, weights):
    weighted = [(class_id, max(0, int(weights.get(class_id, 0)))) for class_id in classes]
    total = sum(weight for _class_id, weight in weighted)
    if total <= 0:
        return rng.choice(list(classes))
    roll = rng.randrange(total)
    for class_id, weight in weighted:
        if roll < weight:
            return class_id
        roll -= weight
    return weighted[-1][0]


def _unique_missions(missions, completed_codes):
    completed = {str(code).upper() for code in completed_codes or ()}
    unique = {}
    for mission in missions or ():
        if not isinstance(mission, dict):
            continue
        code = str(mission.get('code') or '').upper()
        if not code or code in completed or code in unique:
            continue
        normalized = dict(mission)
        normalized['code'] = code
        unique[code] = normalized
    return list(unique.values())


def generate_mission_offers(
    missions,
    *,
    run_seed,
    stage,
    run_length=None,
    completed_codes=(),
    reroll_count=0,
    previous_offer_codes=(),
    offer_count=None,
    config: ShopModeConfig = SHOP_CONFIG,
):
    """Return an isolated, repeatable offer without touching other RNG streams."""
    run_length = config.run_length if run_length is None else int(run_length)
    stage = int(stage)
    reroll_count = int(reroll_count)
    offer_count = (
        config.mission_offer_count if offer_count is None else int(offer_count)
    )
    if run_length < 1 or not 1 <= stage <= run_length:
        raise ValueError(
            f'Invalid Shop Mode stage {stage} for run length {run_length}'
        )
    if reroll_count < 0 or offer_count < 1:
        raise ValueError('Shop Mode reroll count must be non-negative and offer count positive')

    candidates = _unique_missions(missions, completed_codes)
    if not candidates:
        return ()
    rng = random.Random(
        f'{run_seed}:shop_mission_offers:{stage}:{reroll_count}'
    )
    by_class = {class_id: [] for class_id in _CLASS_ORDER}
    for mission in candidates:
        by_class[classify_mission(mission)].append(mission)
    for class_missions in by_class.values():
        class_missions.sort(key=lambda item: item['code'])

    weights = _stage_weights(stage, run_length, config)
    eligible_classes = [
        class_id for class_id in _CLASS_ORDER
        if weights.get(class_id, 0) > 0 and by_class[class_id]
    ]
    eligible_candidates = [
        mission for class_id in eligible_classes
        for mission in by_class[class_id]
    ]
    if not eligible_candidates:
        return ()
    selected = []
    selected_codes = set()
    # Early fixed-unit/hero missions provide one approachable option without
    # allowing Act 2, operations, or finales into the protected opening.
    if stage * 100 <= 20 * run_length:
        hero_candidates = [
            mission for mission in by_class[MissionEconomyClass.ACT_1]
            if (
                mission.get('true_no_build')
                or mission.get('build_classification') == 'true_no_build'
            )
        ]
        if hero_candidates:
            hero = rng.choice(hero_candidates)
            selected.append(MissionOffer(
                hero['code'], MissionEconomyClass.ACT_1
            ))
            selected_codes.add(hero['code'])

    while len(selected) < min(offer_count, len(eligible_candidates)):
        available_classes = [
            class_id for class_id in eligible_classes
            if any(item['code'] not in selected_codes for item in by_class[class_id])
        ]
        if not available_classes:
            break
        class_id = _weighted_class_choice(rng, available_classes, weights)
        class_candidates = [
            item for item in by_class[class_id]
            if item['code'] not in selected_codes
        ]
        mission = rng.choice(class_candidates)
        selected.append(MissionOffer(mission['code'], class_id))
        selected_codes.add(mission['code'])

    previous = {str(code).upper() for code in previous_offer_codes or ()}
    selected_set = {offer.mission_code for offer in selected}
    alternatives = [
        mission for mission in eligible_candidates
        if mission['code'] not in previous and mission['code'] not in selected_set
    ]
    if previous and selected_set == previous and alternatives:
        replacement = rng.choice(sorted(alternatives, key=lambda item: item['code']))
        selected[-1] = MissionOffer(
            replacement['code'], classify_mission(replacement)
        )

    difficulty = {
        class_id: config.mission_rewards[class_id].difficulty
        for class_id in _CLASS_ORDER
    }
    selected.sort(key=lambda offer: (difficulty[offer.economy_class], offer.mission_code))
    return tuple(selected)
