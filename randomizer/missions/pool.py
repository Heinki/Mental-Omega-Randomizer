"""Shared campaign/co-op pool selection with optional native challenges."""

from collections.abc import MutableSet

from randomizer.missions.catalogue import normalize_faction


class MissionExclusions(MutableSet):
    """A writable view of base-map and shared challenge exclusions."""

    def __init__(self, base, challenges):
        self.base, self.challenges = base, challenges

    def __contains__(self, code):
        return code in self.base or code in self.challenges

    def __iter__(self):
        return iter(self.base | self.challenges)

    def __len__(self):
        return len(self.base | self.challenges)

    @classmethod
    def _from_iterable(cls, values):
        return set(values)

    def add(self, code):
        (self.challenges if code.upper().startswith('C_') else self.base).add(code)

    def discard(self, code):
        self.base.discard(code)
        self.challenges.discard(code)

    def update(self, values):
        for code in values:
            self.add(code)

    def difference_update(self, values):
        for code in values:
            self.discard(code)


def is_challenge(mission):
    return bool(mission and (mission.get('mission_category') == 'challenge'
                             or mission.get('challenge_name')))


def select_mission_pool(missions, *, category, campaign='All Campaigns',
                        include_challenges=False, excluded_codes=(),
                        excluded_challenge_codes=()):
    """Challenges supplement the base pool and ignore its campaign faction.

    Keep the legacy challenge-only category readable for existing saved runs.
    Per-map house and color choices are validated at launch, not at generation.
    """
    excluded = {str(code).upper() for code in excluded_codes}
    challenge_excluded = {str(code).upper() for code in excluded_challenge_codes}
    result = []
    for mission in missions:
        if mission['code'].upper() in excluded:
            continue
        if is_challenge(mission):
            if ((category == 'challenge' or include_challenges)
                    and mission['code'].upper() not in challenge_excluded):
                result.append(mission)
        elif category != 'challenge':
            cooperative = bool(mission.get('coop_name'))
            if cooperative != (category == 'coop'):
                continue
            if campaign == 'All Campaigns' or normalize_faction(mission.get('side', '')) == campaign:
                result.append(mission)
    return result
