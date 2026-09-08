"""Regression checks for the protected opening and uniform Shop mission pool."""

from collections import Counter

from .missions import generate_mission_offers, mission_classes_for_stage
from .model import MissionEconomyClass


def validate_shop_mission_selection():
    # Unequal class sizes distinguish uniform mission draws from class draws.
    missions = [
        {'code': f'SC_RANDOM_{class_id.value}_{index}', 'reward_class': class_id.value}
        for class_id in MissionEconomyClass
        for index in range(24 if class_id is MissionEconomyClass.ACT_1 else 3)
    ]
    missions[0]['true_no_build'] = True
    all_codes = {mission['code'].upper() for mission in missions}
    opening_valid = all(
        len(offers := generate_mission_offers(
            missions, run_seed='SHOP-OPENING', stage=stage, run_length=length
        )) == 3
        and all(offer.economy_class is MissionEconomyClass.ACT_1 for offer in offers)
        and missions[0]['code'].upper() in {offer.mission_code for offer in offers}
        for length in (3, 10, 20)
        for stage in (1, 2)
    )
    unrestricted_valid = all(
        mission_classes_for_stage(stage, length) == set(MissionEconomyClass)
        and {offer.mission_code for offer in generate_mission_offers(
            missions, run_seed='SHOP-ALL-CLASSES', stage=stage,
            run_length=length, offer_count=len(missions),
        )} == all_codes
        for length in (3, 10, 20)
        for stage in range(3, length + 1)
    )
    counts = Counter()
    for seed in range(2048):
        counts.update(offer.mission_code for offer in generate_mission_offers(
            missions, run_seed=f'SHOP-UNIFORM-{seed}', stage=3
        ))
    expected = 2048 * 3 / len(missions)
    uniform_valid = set(counts) == all_codes and all(
        abs(count - expected) < expected * 0.3 for count in counts.values()
    )
    # Use a smaller mixed pool so all-finale draws occur regularly.
    mixed_pool = missions[20:]
    all_finale_valid = any(
        all(offer.economy_class is MissionEconomyClass.FINALE for offer in
            generate_mission_offers(mixed_pool, run_seed=seed, stage=3))
        for seed in range(2048)
    )
    offers = generate_mission_offers(missions, run_seed='SHOP-REPEATABLE', stage=3)
    repeatable_valid = offers == generate_mission_offers(
        list(reversed(missions)) + missions,
        run_seed='SHOP-REPEATABLE', stage=3,
    )
    kept_codes = tuple(offer.mission_code for offer in offers[1:])
    rerolled = generate_mission_offers(
        missions, run_seed='SHOP-REPEATABLE', stage=3, reroll_count=1,
        completed_codes=kept_codes, previous_offer_codes=(offers[0].mission_code,),
        offer_count=1,
    )
    reroll_valid = len(rerolled) == 1 and rerolled[0].mission_code not in {
        offer.mission_code for offer in offers
    }
    exhausted_valid = generate_mission_offers(
        missions, run_seed='SHOP-EXHAUSTED', stage=3, completed_codes=all_codes,
    ) == ()
    return {
        'mission_two_stage_opening_valid': opening_valid,
        'mission_unrestricted_pool_valid': unrestricted_valid,
        'mission_uniform_selection_valid': uniform_valid,
        'mission_all_finale_offers_valid': all_finale_valid,
        'mission_selection_repeatable_valid': repeatable_valid,
        'mission_unrestricted_reroll_valid': reroll_valid,
        'mission_exhausted_pool_valid': exhausted_valid,
    }
