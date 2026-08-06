"""Build the APWorld manifest from an already-generated Randomizer run."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json

from Archipelago.catalogue_contract import runtime_catalogue_checksum
from randomizer.progression.grid import grid_opening_mission_codes
from randomizer.rewards.catalogue import REWARD_BY_NAME
from randomizer.rewards.display import canonical_reward
from randomizer.rewards.planning import is_max_rewards_achieved_reward


MANIFEST_SCHEMA_VERSION = 1

GAMEPLAY_CONFIG_KEYS = (
    "seed",
    "campaign_filter",
    "mission_goal",
    "progression_mode",
    "grid_two_start_positions",
    "rewards_per_objective",
    "rewards_on_victory_only",
    "difficulty",
    "game_speed",
    "player_color",
    "rainbowizer",
    "eva_voice",
)


def _canonical_json(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _reward_names(values):
    result = []
    for value in values or ():
        reward = canonical_reward(value)
        name = reward.get("name")
        if (
            name in REWARD_BY_NAME
            and not is_max_rewards_achieved_reward(reward)
        ):
            result.append(name)
    return result


def _goal_for_state(state, mission_order):
    mode = state.get("progression_mode")
    if mode == "Mission List":
        return {"type": "all_missions"}
    if mode == "Grid Mode":
        grid = state.get("grid") if isinstance(state.get("grid"), dict) else {}
        return {
            "type": "grid",
            "mission_code": grid.get("goal") or mission_order[-1],
        }
    return {"type": "mission", "mission_code": mission_order[-1]}


def _stable_grid(value):
    """Keep topology while excluding mutable locked/completed node state."""
    if not isinstance(value, dict):
        return None
    nodes = value.get("nodes")
    stable_nodes = {}
    if isinstance(nodes, dict):
        for code, node in nodes.items():
            if not isinstance(node, dict):
                continue
            stable_nodes[str(code)] = {
                "x": int(node.get("x", 0)),
                "y": int(node.get("y", 0)),
            }
    return {
        "layout_version": int(value.get("layout_version", 0)),
        "width": int(value.get("width", 0)),
        "height": int(value.get("height", 0)),
        "two_start_positions": bool(value.get("two_start_positions", False)),
        "goal": value.get("goal"),
        "nodes": stable_nodes,
    }


def gameplay_config_snapshot(config):
    """Return only gameplay-affecting launcher settings; omit UI/network data."""
    if not isinstance(config, dict):
        return {}
    result = {
        key: deepcopy(config[key])
        for key in GAMEPLAY_CONFIG_KEYS
        if key in config
    }
    if isinstance(config.get("generation"), dict):
        result["generation"] = deepcopy(config["generation"])
    return result


def _launcher_snapshot_for_state(state, config):
    """Overlay generated-run truth onto current launch-time UI settings."""
    result = gameplay_config_snapshot(config)
    result.update({
        "seed": str(state.get("seed") or ""),
        "campaign_filter": str(state.get("campaign_filter") or ""),
        "mission_goal": int(state.get("mission_goal") or 1),
        "progression_mode": str(state.get("progression_mode") or "Classic"),
        "grid_two_start_positions": bool(
            (state.get("grid") or {}).get("two_start_positions", False)
            if isinstance(state.get("grid"), dict) else False
        ),
        "rewards_per_objective": int(state.get("rewards_per_check") or 1),
        "rewards_on_victory_only": bool(
            state.get("rewards_on_victory_only", False)
        ),
    })
    generation = result.setdefault("generation", {})
    mission_pool = state.get("mission_pool_settings")
    if isinstance(mission_pool, dict):
        generation.update(deepcopy(mission_pool))
    reward_settings = state.get("reward_settings")
    if isinstance(reward_settings, dict):
        generation.update(deepcopy(reward_settings))
    generation["reward_mode"] = state.get("reward_mode")
    generation["starting_unlocked_missions"] = state.get(
        "starting_unlocked_missions"
    )
    return result


def _first_active_location(locations, code):
    for check_id, count in locations.get(code, {}).items():
        if count:
            return check_id, 1
    return None


def _is_access_item(name):
    reward = REWARD_BY_NAME[name]
    return not reward.get("enemy_reward") and reward.get("kind") != "buff"


def _local_opening_placements(state, mission_order, locations, rewards_by_code):
    pool = Counter(
        name
        for code in mission_order
        for names in rewards_by_code.get(code, {}).values()
        for name in names
    )
    if state.get("progression_mode") == "Grid Mode":
        opening_codes = list(grid_opening_mission_codes(state.get("grid") or {}))
    else:
        opening_codes = mission_order[:1]
    placements = []
    for code in opening_codes:
        target = _first_active_location(locations, code)
        if target is None:
            continue
        local_candidates = [
            name
            for names in rewards_by_code.get(code, {}).values()
            for name in names
            if pool[name] and _is_access_item(name)
        ]
        candidates = local_candidates or [
            name for name, count in pool.items()
            if count and _is_access_item(name)
        ]
        if not candidates:
            continue
        item = candidates[0]
        pool[item] -= 1
        check_id, slot = target
        placements.append({
            "mission": code,
            "check": check_id,
            "slot": slot,
            "item": item,
        })
    return placements


def build_run_manifest(state, launcher_config=None):
    """Freeze one generated run without reimplementing its generation logic."""
    if not isinstance(state, dict):
        raise ValueError("Randomizer state must be an object.")
    mission_order = [str(code) for code in state.get("mission_order", ())]
    if not mission_order or len(set(mission_order)) != len(mission_order):
        raise ValueError("Randomizer state has no valid mission order.")
    raw_checks = state.get("mission_checks")
    if not isinstance(raw_checks, dict):
        raise ValueError("Randomizer state has no mission checks.")

    rewards_by_code = {}
    locations = {}
    item_pool = Counter()
    for code in mission_order:
        rewards_by_check = {}
        location_counts = {}
        for check in raw_checks.get(code, ()):
            if not isinstance(check, dict) or not check.get("id"):
                continue
            names = _reward_names(check.get("rewards") or (
                [check.get("reward")] if check.get("reward") else []
            ))
            if not names:
                continue
            check_id = str(check["id"])
            rewards_by_check[check_id] = names
            location_counts[check_id] = len(names)
            item_pool.update(names)
        rewards_by_code[code] = rewards_by_check
        locations[code] = location_counts
    if not item_pool:
        raise ValueError("Randomizer run has no real mission rewards.")

    progression_mode = str(state.get("progression_mode") or "Classic")
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "randomizer_version": "1.24",
        "randomizer_seed": str(state.get("seed") or ""),
        "catalogue_checksum": runtime_catalogue_checksum(),
        "campaign_filter": str(state.get("campaign_filter") or ""),
        "progression_mode": progression_mode,
        "mission_goal": int(state.get("mission_goal") or len(mission_order)),
        "mission_order": mission_order,
        "grid": _stable_grid(state.get("grid")),
        "goal": _goal_for_state(state, mission_order),
        "locations": locations,
        "item_pool": dict(sorted(item_pool.items())),
        "starting_items": dict(sorted(Counter(
            _reward_names(state.get("starting_rewards"))
        ).items())),
        "local_placements": _local_opening_placements(
            state,
            mission_order,
            locations,
            rewards_by_code,
        ),
        "frozen_settings": {
            "reward_mode": state.get("reward_mode"),
            "rewards_per_check": state.get("rewards_per_check"),
            "rewards_on_victory_only": state.get("rewards_on_victory_only"),
            "starting_unlocked_missions": state.get(
                "starting_unlocked_missions"
            ),
            "campaign_mission_limits": deepcopy(
                state.get("campaign_mission_limits")
            ),
            "mission_pool_settings": deepcopy(
                state.get("mission_pool_settings")
            ),
            "reward_settings": deepcopy(state.get("reward_settings")),
            "starting_unit_ids": deepcopy(state.get("starting_unit_ids")),
            "starting_defense_ids": deepcopy(state.get("starting_defense_ids")),
            "mission_arsenals": deepcopy(state.get("mission_arsenals")),
            "enemy_progress_plan": deepcopy(state.get("enemy_progress_plan")),
            "launcher": _launcher_snapshot_for_state(
                state, launcher_config
            ),
        },
    }
    unsigned = _canonical_json(manifest).encode("utf-8")
    manifest["manifest_checksum"] = sha256(unsigned).hexdigest()
    return manifest


def validate_run_manifest_for_state(state, manifest):
    """Validate checksum and exact immutable identity against the active run."""
    if not isinstance(manifest, dict):
        raise ValueError("Archipelago run manifest must be an object.")
    supplied_checksum = str(manifest.get("manifest_checksum") or "")
    unsigned = deepcopy(manifest)
    unsigned.pop("manifest_checksum", None)
    actual_checksum = sha256(
        _canonical_json(unsigned).encode("utf-8")
    ).hexdigest()
    if supplied_checksum != actual_checksum:
        raise ValueError("Archipelago run manifest checksum is invalid.")
    frozen = manifest.get("frozen_settings")
    launcher = frozen.get("launcher") if isinstance(frozen, dict) else None
    expected = build_run_manifest(state, launcher_config=launcher)
    if expected.get("manifest_checksum") != supplied_checksum:
        raise ValueError(
            "Archipelago YAML does not match the active Randomizer run."
        )
    return expected


def serialize_run_manifest(state, launcher_config=None):
    return _canonical_json(build_run_manifest(state, launcher_config))
