"""Readable access to Mental Omega's weapon relationships.

Why this registry exists
------------------------
Mental Omega does not store every unit's damage directly on the unit. A normal
tank points to one or more WeaponType sections, while carriers and missile
launchers can point to spawned aircraft, spawned missiles, or projectile
payloads that contain the real impact damage.

The randomizer needs four facts before it can safely apply a weapon buff:

``ROSTER_WEAPON_REFS``
    WeaponTypes mounted directly on each playable unit. Reload and range
    upgrades use these weapons.

``ROSTER_DAMAGE_WEAPON_REFS``
    WeaponTypes that deal the real damage for that unit. This includes direct
    guns plus spawned aircraft and projectile payloads. Damage upgrades use
    these weapons.

``WEAPON_BASE_STATS``
    Original ``(Damage, ROF, Range)`` values from Mental Omega 3.3.6. ``None``
    means that the weapon intentionally does not define that field.

``WEAPON_USER_IDS``
    Every TechnoType that can reach a weapon, including AI-only types and the
    parent of spawned payloads. Before changing a global WeaponType, the map
    injector checks these users and refuses the change if an enemy uses it.

Example: ``CARRIER`` directly uses ``HORNETLAUNCHER``, but its real damage is
dealt by ``HORNETBOMB`` and related Hornet payload weapons. ``WEAPON_USER_IDS``
links those payloads back to both ``HORNET`` and ``CARRIER`` so an enemy carrier
cannot accidentally inherit a player damage bonus.

The large generated values live in ``randomizer/rewards/weapon_stats_data.py`` to keep
this API readable. That internal file is a packed snapshot extracted from the
installed RULESMO.INI; it is data, not executable modifier logic.
"""

from randomizer.rewards.weapon_stats_data import (
    ROSTER_DAMAGE_WEAPON_REFS,
    ROSTER_WEAPON_REFS,
    WEAPON_BASE_STATS,
    WEAPON_USER_IDS,
)

__all__ = (
    'ROSTER_DAMAGE_WEAPON_REFS',
    'ROSTER_WEAPON_REFS',
    'WEAPON_BASE_STATS',
    'WEAPON_USER_IDS',
)
