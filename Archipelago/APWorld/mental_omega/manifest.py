"""Strict launcher-generated run-manifest contract."""

from collections import Counter
from hashlib import sha256
import json

from .data import CATALOGUE_CHECKSUM, ITEM_DATA, LOCATION_SLOTS, MISSION_DATA


MANIFEST_SCHEMA_VERSION = 1
RANDOMIZER_VERSION = "1.25"


class ManifestError(ValueError):
    pass


def canonical_json(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def manifest_checksum(value):
    unsigned = dict(value)
    unsigned.pop("manifest_checksum", None)
    return sha256(canonical_json(unsigned).encode("utf-8")).hexdigest()


def _positive_counts(value, label, known_names):
    if not isinstance(value, dict):
        raise ManifestError(f"{label} must be an object of name/count pairs.")
    result = {}
    for name, count in value.items():
        if name not in known_names:
            raise ManifestError(f"{label} contains unknown item {name!r}.")
        if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
            raise ManifestError(f"{label} count for {name!r} must be positive.")
        result[name] = count
    return result


def parse_manifest(raw_value):
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise ManifestError("run_manifest is required; export it from the launcher.")
    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"run_manifest is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ManifestError("run_manifest must contain one JSON object.")
    if value.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ManifestError("Unsupported run-manifest schema version.")
    if value.get("randomizer_version") != RANDOMIZER_VERSION:
        raise ManifestError(
            f"Manifest requires Randomizer {value.get('randomizer_version')!r}; "
            f"APWorld requires {RANDOMIZER_VERSION}."
        )
    if value.get("catalogue_checksum") != CATALOGUE_CHECKSUM:
        raise ManifestError("Manifest reward/mission catalogue checksum is stale.")
    if value.get("manifest_checksum") != manifest_checksum(value):
        raise ManifestError("Manifest checksum is missing or invalid.")

    seed = value.get("randomizer_seed")
    if not isinstance(seed, str) or not seed.strip():
        raise ManifestError("Manifest randomizer_seed is required.")
    mission_order = value.get("mission_order")
    if (
        not isinstance(mission_order, list)
        or not mission_order
        or len(set(mission_order)) != len(mission_order)
        or any(code not in MISSION_DATA for code in mission_order)
    ):
        raise ManifestError("Manifest mission_order is invalid.")

    raw_locations = value.get("locations")
    if not isinstance(raw_locations, dict) or set(raw_locations) != set(mission_order):
        raise ManifestError("Manifest locations must cover exactly mission_order.")
    locations = {}
    total_locations = 0
    for code in mission_order:
        raw_checks = raw_locations.get(code)
        if not isinstance(raw_checks, dict):
            raise ManifestError(f"Manifest reward checks for {code} are invalid.")
        checks = {}
        for check_id, count in raw_checks.items():
            available = LOCATION_SLOTS.get(code, {}).get(check_id)
            if not available:
                raise ManifestError(f"Manifest contains unknown check {code}/{check_id}.")
            if (
                not isinstance(count, int)
                or isinstance(count, bool)
                or count <= 0
                or count > len(available)
            ):
                raise ManifestError(f"Manifest slot count for {code}/{check_id} is invalid.")
            checks[check_id] = count
            total_locations += count
        locations[code] = checks

    if total_locations <= 0:
        raise ManifestError("Manifest has no active reward locations.")

    item_pool = _positive_counts(value.get("item_pool"), "item_pool", ITEM_DATA)
    if sum(item_pool.values()) != total_locations:
        raise ManifestError(
            "Manifest item_pool count must equal configured location count."
        )
    starting_items = _positive_counts(
        value.get("starting_items", {}),
        "starting_items",
        ITEM_DATA,
    )

    raw_placements = value.get("local_placements", [])
    if not isinstance(raw_placements, list):
        raise ManifestError("local_placements must be a list.")
    placements = []
    placed_locations = set()
    placed_items = Counter()
    for entry in raw_placements:
        if not isinstance(entry, dict):
            raise ManifestError("local_placements entries must be objects.")
        code = entry.get("mission")
        check_id = entry.get("check")
        slot = entry.get("slot")
        item = entry.get("item")
        if code not in locations or check_id not in locations[code]:
            raise ManifestError("local_placements contains an inactive check.")
        if (
            not isinstance(slot, int)
            or isinstance(slot, bool)
            or slot < 1
            or slot > locations[code][check_id]
        ):
            raise ManifestError("local_placements contains an invalid slot.")
        if item not in ITEM_DATA:
            raise ManifestError("local_placements contains an unknown item.")
        key = (code, check_id, slot)
        if key in placed_locations:
            raise ManifestError("local_placements repeats a location.")
        placed_locations.add(key)
        placed_items[item] += 1
        placements.append({
            "mission": code,
            "check": check_id,
            "slot": slot,
            "item": item,
        })
    if any(placed_items[name] > item_pool.get(name, 0) for name in placed_items):
        raise ManifestError("local_placements uses more items than item_pool.")

    goal = value.get("goal")
    if not isinstance(goal, dict) or goal.get("type") not in {
        "mission", "all_missions", "grid",
    }:
        raise ManifestError("Manifest goal is invalid.")
    goal_code = goal.get("mission_code")
    if goal["type"] in {"mission", "grid"} and goal_code not in mission_order:
        raise ManifestError("Manifest goal mission is not in mission_order.")

    state_snapshot = value.get("state_snapshot")
    if not isinstance(state_snapshot, dict):
        raise ManifestError("Manifest has no server state snapshot.")
    if (
        state_snapshot.get("seed") != seed
        or state_snapshot.get("mission_order") != mission_order
        or state_snapshot.get("progression_mode") != value.get("progression_mode")
        or state_snapshot.get("campaign_filter") != value.get("campaign_filter")
    ):
        raise ManifestError("Manifest server state identity is inconsistent.")
    state_checks = state_snapshot.get("mission_checks")
    if not isinstance(state_checks, dict):
        raise ManifestError("Manifest server state has no mission checks.")
    for code, checks in locations.items():
        snapshot_checks = state_checks.get(code)
        if not isinstance(snapshot_checks, list):
            raise ManifestError(
                f"Manifest server state checks for {code} are invalid."
            )
        snapshot_ids = {
            str(check.get("id"))
            for check in snapshot_checks
            if isinstance(check, dict) and check.get("id")
        }
        if not set(checks).issubset(snapshot_ids):
            raise ManifestError(
                f"Manifest server state misses active checks for {code}."
            )

    result = dict(value)
    result["mission_order"] = list(mission_order)
    result["locations"] = locations
    result["item_pool"] = item_pool
    result["starting_items"] = starting_items
    result["local_placements"] = placements
    return result


def validate_launcher_settings(settings, manifest):
    """Reject hand edits until the launcher regenerates the signed run."""
    frozen = manifest.get("frozen_settings")
    expected = frozen.get("launcher") if isinstance(frozen, dict) else None
    if not settings:
        return expected
    if not isinstance(settings, dict):
        raise ManifestError("launcher_settings must be a mapping.")
    if settings != expected:
        raise ManifestError(
            "launcher_settings were edited after run generation. Load this "
            "YAML in Mental Omega Randomizer, generate a new seed, then "
            "generate/save the YAML again."
        )
    return settings
