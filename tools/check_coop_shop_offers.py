"""Check that co-op maps form a usable, deterministic Shop mission pool."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from randomizer.coop.catalogue import discover_coop_missions
from randomizer.core.paths import GAME_ROOT
from randomizer.shop.missions import generate_mission_offers


def main():
    missions = discover_coop_missions(GAME_ROOT)
    codes = {mission['code'] for mission in missions}
    assert len(missions) == len(codes) == 36
    assert all(mission['reward_class'] == 'act_1' for mission in missions)
    for stage in (1, 2, 3, 10):
        offers = generate_mission_offers(
            missions, run_seed='COOP-SHOP-CHECK', stage=stage,
            completed_codes=(),
        )
        assert len(offers) == 3, (stage, offers)
        assert len({offer.mission_code for offer in offers}) == 3
        assert {offer.mission_code for offer in offers} <= codes
        assert offers == generate_mission_offers(
            list(reversed(missions)), run_seed='COOP-SHOP-CHECK',
            stage=stage, completed_codes=(),
        )
    for side in ('Allies', 'Soviets', 'Epsilon'):
        pool = [mission for mission in missions if mission['side'] == side]
        assert len(pool) == 12
        offers = generate_mission_offers(
            pool, run_seed='COOP-SHOP-CHECK', stage=1,
        )
        assert len(offers) == 3
        assert all(offer.mission_code in {mission['code'] for mission in pool}
                   for offer in offers)
    print('Co-op Shop offers: 36 maps, stages 1–10, faction pools, stable ordering')


if __name__ == '__main__':
    main()
