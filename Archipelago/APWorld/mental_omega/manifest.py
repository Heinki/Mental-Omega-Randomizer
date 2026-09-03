"""Strict launcher-generated run-manifest contract."""

from collections import Counter
from collections.abc import Mapping
from hashlib import sha256
import json

from .data import (
    CATALOGUE_CHECKSUM,
    ITEM_DATA,
    LOCATION_SLOTS,
    MAXIMUM_SHOP_PURCHASE_LOCATIONS,
    MAXIMUM_SHOP_RUN_LENGTH,
    MISSION_DATA,
)


MANIFEST_SCHEMA_VERSION = 1
RANDOMIZER_VERSION = "1.34"


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


def _grid_positions(grid, mission_order):
    if not isinstance(grid, dict):
        raise ManifestError("Grid Mode manifest has no grid topology.")
    nodes = grid.get("nodes")
    if not isinstance(nodes, dict) or set(nodes) != set(mission_order):
        raise ManifestError("Grid topology must cover exactly mission_order.")
    positions = {}
    for code, node in nodes.items():
        if not isinstance(node, dict):
            raise ManifestError(f"Grid node {code!r} is invalid.")
        x, y = node.get("x"), node.get("y")
        if (
            not isinstance(x, int)
            or isinstance(x, bool)
            or not isinstance(y, int)
            or isinstance(y, bool)
            or x < 0
            or y < 0
            or (x, y) in positions
        ):
            raise ManifestError(f"Grid node {code!r} has an invalid position.")
        positions[(x, y)] = code
    return positions


def _validate_progression(value, mode, mission_order, grid):
    if not isinstance(value, dict):
        raise ManifestError("Manifest has no local progression logic.")
    progression_type = value.get("type")
    starts = value.get("starting_missions")
    requirements = value.get("mission_requirements")
    if (
        not isinstance(starts, list)
        or not starts
        or len(set(starts)) != len(starts)
        or any(code not in mission_order for code in starts)
    ):
        raise ManifestError("Manifest starting missions are invalid.")
    if not isinstance(requirements, dict) or set(requirements) != set(mission_order):
        raise ManifestError(
            "Manifest progression requirements must cover exactly mission_order."
        )

    if mode == "Shop Mode":
        if (
            progression_type != "shop_stages"
            or starts != mission_order
            or any(requirements[code] != [] for code in mission_order)
        ):
            raise ManifestError(
                "Shop Mode progression must expose its complete mission pool."
            )
        return value

    if mode == "Grid Mode":
        if progression_type != "grid_neighbors":
            raise ManifestError("Grid Mode requires grid-neighbor progression.")
        positions = _grid_positions(grid, mission_order)
        expected_starts = (
            [positions.get((1, 0)), positions.get((0, 1))]
            if grid.get("two_start_positions")
            else [positions.get((0, 0))]
        )
        expected_starts = [code for code in expected_starts if code]
        if starts != expected_starts:
            raise ManifestError("Grid starting missions do not match topology.")
        for code, required_neighbors in requirements.items():
            if (
                not isinstance(required_neighbors, list)
                or len(set(required_neighbors)) != len(required_neighbors)
                or any(
                    neighbor not in mission_order or neighbor == code
                    for neighbor in required_neighbors
                )
            ):
                raise ManifestError(
                    f"Grid progression requirements for {code!r} are invalid."
                )
            node = grid["nodes"][code]
            expected = [
                positions[position]
                for position in (
                    (node["x"], node["y"] - 1),
                    (node["x"] - 1, node["y"]),
                    (node["x"] + 1, node["y"]),
                    (node["x"], node["y"] + 1),
                )
                if position in positions
            ]
            if required_neighbors != expected:
                raise ManifestError(
                    f"Grid progression requirements for {code!r} do not match topology."
                )
            if code not in starts and not required_neighbors:
                raise ManifestError(f"Grid mission {code!r} cannot be unlocked.")
        reachable = set(starts)
        changed = True
        while changed:
            changed = False
            for code, required_neighbors in requirements.items():
                if code not in reachable and any(
                    neighbor in reachable for neighbor in required_neighbors
                ):
                    reachable.add(code)
                    changed = True
        if reachable != set(mission_order):
            raise ManifestError("Grid progression topology is disconnected.")
        return value

    if progression_type != "victory_count":
        raise ManifestError("Mission List/Classic requires victory-count progression.")
    if starts != mission_order[:len(starts)]:
        raise ManifestError("Starting missions must be a mission_order prefix.")
    for index, code in enumerate(mission_order):
        required = requirements.get(code)
        expected = max(0, index - len(starts) + 1)
        if (
            not isinstance(required, int)
            or isinstance(required, bool)
            or required != expected
        ):
            raise ManifestError(
                f"Victory requirement for {code!r} does not match mission order."
            )
    return value


def progression_for_manifest(value):
    """Return signed progression, deriving only for legacy schema-1 YAMLs."""
    mission_order = value["mission_order"]
    mode = value.get("progression_mode")
    if value.get("progression") is not None:
        return _validate_progression(
            value["progression"], mode, mission_order, value.get("grid")
        )
    if mode == "Shop Mode":
        shop_progression = {
            "type": "shop_stages",
            "starting_missions": list(mission_order),
            "mission_requirements": {
                code: [] for code in mission_order
            },
        }
        return _validate_progression(
            shop_progression, mode, mission_order, value.get("grid")
        )
    if mode == "Grid Mode":
        grid = value.get("grid")
        positions = _grid_positions(grid, mission_order)
        starts = (
            [positions.get((1, 0)), positions.get((0, 1))]
            if grid.get("two_start_positions")
            else [positions.get((0, 0))]
        )
        starts = [code for code in starts if code]
        requirements = {}
        for code in mission_order:
            node = grid["nodes"][code]
            requirements[code] = [
                positions[position]
                for position in (
                    (node["x"], node["y"] - 1),
                    (node["x"] - 1, node["y"]),
                    (node["x"] + 1, node["y"]),
                    (node["x"], node["y"] + 1),
                )
                if position in positions
            ]
        legacy = {
            "type": "grid_neighbors",
            "starting_missions": starts,
            "mission_requirements": requirements,
        }
        return _validate_progression(legacy, mode, mission_order, grid)
    frozen = value.get("frozen_settings")
    frozen = frozen if isinstance(frozen, dict) else {}
    default_count = 1 if mode == "Classic" else 3
    try:
        starting_count = int(
            frozen.get("starting_unlocked_missions", default_count)
        )
    except (TypeError, ValueError):
        starting_count = default_count
    starting_count = max(1, min(len(mission_order), starting_count))
    legacy = {
        "type": "victory_count",
        "starting_missions": mission_order[:starting_count],
        "mission_requirements": {
            code: max(0, index - starting_count + 1)
            for index, code in enumerate(mission_order)
        },
    }
    return _validate_progression(
        legacy, mode, mission_order, value.get("grid")
    )


def _validate_shop_settings(value, mode, mission_order):
    if mode != "Shop Mode":
        if value is not None:
            raise ManifestError("Non-Shop manifest cannot contain Shop settings.")
        return None
    required_keys = {
        "run_length",
        "mission_pool",
        "mission_victories_are_locations",
        "purchase_location_count",
        "purchase_meta_coin_cost",
        "starting_extra_unit_limit",
    }
    optional_keys = {"received_unit_loadout"}
    if (
        not isinstance(value, dict)
        or not required_keys.issubset(value)
        or not set(value).issubset(required_keys | optional_keys)
    ):
        raise ManifestError("Shop Mode manifest settings are invalid.")
    run_length = value.get("run_length")
    purchase_count = value.get("purchase_location_count")
    purchase_cost = value.get("purchase_meta_coin_cost")
    extra_limit = value.get("starting_extra_unit_limit")
    received_unit_loadout = value.get("received_unit_loadout", "manual")
    if (
        not isinstance(run_length, int)
        or isinstance(run_length, bool)
        or not 5 <= run_length <= MAXIMUM_SHOP_RUN_LENGTH
        or len(mission_order) < run_length
        or value.get("mission_pool") != mission_order
        or not isinstance(
            value.get("mission_victories_are_locations"), bool
        )
        or not isinstance(purchase_count, int)
        or isinstance(purchase_count, bool)
        or not 0 <= purchase_count <= MAXIMUM_SHOP_PURCHASE_LOCATIONS
        or not isinstance(purchase_cost, int)
        or isinstance(purchase_cost, bool)
        or purchase_cost < 1
        or not isinstance(extra_limit, int)
        or isinstance(extra_limit, bool)
        or not 0 <= extra_limit <= 10
        or received_unit_loadout not in {"all", "manual", "random"}
    ):
        raise ManifestError("Shop Mode manifest settings are out of range.")
    result = dict(value)
    result["received_unit_loadout"] = received_unit_loadout
    return result


def parse_manifest(raw_value):
    if isinstance(raw_value, Mapping):
        value = dict(raw_value)
    else:
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise ManifestError(
                "generated_world is required; export Player YAML from the launcher."
            )
        try:
            value = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise ManifestError(
                f"generated_world is not valid JSON: {exc}"
            ) from exc
    if not isinstance(value, dict):
        raise ManifestError("generated_world must contain one mapping.")
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

    if value.get("progression_mode") not in {
        "Classic", "Mission List", "Grid Mode", "Shop Mode"
    }:
        raise ManifestError("Manifest progression_mode is invalid.")
    progression = (
        _validate_progression(
            value["progression"],
            value["progression_mode"],
            mission_order,
            value.get("grid"),
        )
        if value.get("progression") is not None
        else None
    )

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

    shop = _validate_shop_settings(
        value.get("shop"), value.get("progression_mode"), mission_order
    )
    if shop is not None:
        total_locations += shop["purchase_location_count"]
        if shop["mission_victories_are_locations"]:
            total_locations += shop["run_length"]
    if total_locations <= 0 and shop is None:
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
    if shop is not None and raw_placements:
        raise ManifestError("Shop Mode cannot contain mission local placements.")
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
        "mission", "all_missions", "grid", "shop_run",
    }:
        raise ManifestError("Manifest goal is invalid.")
    goal_code = goal.get("mission_code")
    if goal["type"] in {"mission", "grid"} and goal_code not in mission_order:
        raise ManifestError("Manifest goal mission is not in mission_order.")
    if goal["type"] == "shop_run" and (
        shop is None or goal.get("run_length") != shop["run_length"]
    ):
        raise ManifestError("Manifest Shop goal does not match Shop settings.")
    if shop is not None and goal["type"] != "shop_run":
        raise ManifestError("Shop Mode requires a shop_run goal.")

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
    if progression is not None:
        result["progression"] = progression
    result["locations"] = locations
    result["shop"] = shop
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
