"""Generate the APWorld's deterministic view of launcher-owned catalogues.

This module imports no Archipelago runtime code.  The launcher remains the
authority for reward and mission semantics; the APWorld consumes the generated
snapshot instead of maintaining a second hand-written catalogue.
"""

from __future__ import annotations

from hashlib import sha256
import json

from randomizer.core.paths import BATTLE_CLIENT_INI
from randomizer.missions.catalogue import parse_missions
from randomizer.rewards.catalogue import MAX_REWARDS_PER_CHECK, REWARD_POOL
from randomizer.rewards.weights import main_reward_weight_type


SNAPSHOT_SCHEMA_VERSION = 1
ITEM_ID_BASE = 0x4D4F000
LOCATION_ID_BASE = 0x4D5F000
PROTOTYPE_ITEM_IDS = {
    "GI Access": ITEM_ID_BASE,
    "Soviet Conscript Access": ITEM_ID_BASE + 1,
}

# Published catalogue immediately before the additive Starting Credits item.
# Existing IDs and reward semantics are unchanged, and server slot data carries
# its exact used-item map, location map, and signed state snapshot. Keeping this
# one checksum compatible lets already-hosted rooms reconnect safely.
BACKWARD_COMPATIBLE_CATALOGUE_CHECKSUMS = frozenset({
    "8a59f49bc0a8746086ad2fd020832542b2dd7057d53cf719dd727cb11822121d",
})


def _canonical_json(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _item_classification(reward):
    if reward.get("enemy_reward"):
        return "trap"
    if reward.get("kind") == "buff":
        return "useful"
    return "progression"


def _check_name(check_id):
    if check_id == "victory":
        return "Mission Complete"
    return "Objective " + check_id.rsplit("_", 1)[-1]


def build_catalogue_projection():
    """Return stable AP-relevant data derived from the live Randomizer."""
    items = []
    for reward in sorted(REWARD_POOL, key=lambda entry: entry["name"]):
        items.append({
            "name": reward["name"],
            "classification": _item_classification(reward),
            "category": main_reward_weight_type(reward),
            "repeatable": reward.get("kind") == "buff",
        })

    missions = []
    for mission in parse_missions(BATTLE_CLIENT_INI):
        objectives = list(mission.get("objectives") or ())
        checks = [
            {
                "id": f"objective_{index}",
                "name": f"Objective {index}",
                "hint": hint,
                "maximum_slots": MAX_REWARDS_PER_CHECK,
            }
            for index, hint in enumerate(objectives, start=1)
        ]
        checks.append({
            "id": "victory",
            "name": "Mission Complete",
            "hint": "Win the mission.",
            "maximum_slots": 0,
        })
        multiplier = int(mission["reward_multiplier"])
        check_count = len(checks)
        checks[-1]["maximum_slots"] = MAX_REWARDS_PER_CHECK * (
            1 + check_count * (multiplier - 1)
        )
        missions.append({
            "code": mission["code"],
            "title": mission["title"],
            "side": mission["side"],
            "reward_multiplier": multiplier,
            "checks": checks,
        })

    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "maximum_rewards_per_check": MAX_REWARDS_PER_CHECK,
        "items": items,
        "missions": missions,
    }


def projection_checksum(projection):
    return sha256(_canonical_json(projection).encode("utf-8")).hexdigest()


def runtime_catalogue_checksum():
    return projection_checksum(build_catalogue_projection())


def runtime_catalogue_is_compatible(checksum):
    checksum = str(checksum or "")
    return (
        checksum == runtime_catalogue_checksum()
        or checksum in BACKWARD_COMPATIBLE_CATALOGUE_CHECKSUMS
    )


def _preserved_ids(existing, key):
    values = existing.get(key, ()) if isinstance(existing, dict) else ()
    return {
        entry["name"]: int(entry["id"])
        for entry in values
        if isinstance(entry, dict)
        and isinstance(entry.get("name"), str)
        and isinstance(entry.get("id"), int)
    }


def build_snapshot(existing=None):
    """Build a snapshot, retaining IDs already published by an old snapshot."""
    projection = build_catalogue_projection()
    old_item_ids = _preserved_ids(existing or {}, "items")
    old_location_ids = _preserved_ids(existing or {}, "locations")

    used_item_ids = set(old_item_ids.values()) | set(PROTOTYPE_ITEM_IDS.values())
    next_item_id = max(used_item_ids, default=ITEM_ID_BASE - 1) + 1
    items = []
    for entry in projection["items"]:
        name = entry["name"]
        item_id = PROTOTYPE_ITEM_IDS.get(name, old_item_ids.get(name))
        if item_id is None:
            while next_item_id in used_item_ids:
                next_item_id += 1
            item_id = next_item_id
            used_item_ids.add(item_id)
            next_item_id += 1
        items.append({**entry, "id": item_id})

    prototype_locations = {
        "Allied 01: RED DAWN RISING - Objective 1 - Reward 1": (
            LOCATION_ID_BASE
        ),
        "Allied 01: RED DAWN RISING - Mission Complete - Reward 1": (
            LOCATION_ID_BASE + 1
        ),
    }
    used_location_ids = set(old_location_ids.values()) | set(
        prototype_locations.values()
    )
    next_location_id = max(
        used_location_ids,
        default=LOCATION_ID_BASE - 1,
    ) + 1
    locations = []
    for mission in projection["missions"]:
        for check in mission["checks"]:
            for slot in range(1, check["maximum_slots"] + 1):
                name = (
                    f'{mission["title"]} - {_check_name(check["id"])} '
                    f"- Reward {slot}"
                )
                location_id = prototype_locations.get(
                    name,
                    old_location_ids.get(name),
                )
                if location_id is None:
                    while next_location_id in used_location_ids:
                        next_location_id += 1
                    location_id = next_location_id
                    used_location_ids.add(location_id)
                    next_location_id += 1
                locations.append({
                    "name": name,
                    "id": location_id,
                    "mission": mission["code"],
                    "check": check["id"],
                    "slot": slot,
                })

    return {
        **projection,
        "catalogue_checksum": projection_checksum(projection),
        "items": items,
        "locations": locations,
    }


def snapshot_is_current(snapshot):
    if not isinstance(snapshot, dict):
        return False
    rebuilt = build_snapshot(snapshot)
    return snapshot == rebuilt
