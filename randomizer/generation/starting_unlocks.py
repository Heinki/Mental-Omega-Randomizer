"""Generation methods shared with launcher; no GUI dependency."""

from randomizer.rewards.catalogue import REWARD_POOL, canonical_reward
from randomizer.rewards.starting import normalize_starting_unlock_reward_names
from randomizer.rewards.rules import tech_ids_for_rewards




class StartingUnlocks:
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

    def active_starting_unlock_names(self):
        return self.filter_permanent_starting_unlock_names(
            self.active_reward_settings().get('starting_unlock_rewards')
        )

