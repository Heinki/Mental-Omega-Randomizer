"""Build the APWorld manifest from an already-generated Randomizer run."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json

from Archipelago.catalogue_contract import (
    build_catalogue_projection,
    runtime_catalogue_checksum,
)
from randomizer.core.version import APP_VERSION
from randomizer.progression.grid import grid_opening_mission_codes
from randomizer.rewards.catalogue import REWARD_BY_NAME, REWARD_POOL
from randomizer.rewards.display import canonical_reward
from randomizer.rewards.enemy_scaling import plan_enemy_trap_rewards
from randomizer.rewards.planning import is_max_rewards_achieved_reward


MANIFEST_SCHEMA_VERSION = 1

GAMEPLAY_CONFIG_KEYS = (
    "seed",
    "campaign_filter",
    "mission_goal",
    "progression_mode",
    "grid_two_start_positions",
    "unlock_all_rewards_after_final_grid_mission",
    "rewards_per_objective",
    "rewards_on_victory_only",
    "use_act_based_reward_multipliers",
    "difficulty",
    "game_speed",
    "player_color",
    "rainbowizer",
    "eva_voice",
)

PLAYER_GENERATION_KEYS = {
    "reward_mode",
    "arsenal",
    "include_no_build_missions",
    "include_no_build_production_missions",
    "include_operation_missions",
    "prioritize_no_build_missions",
    "excluded_mission_codes",
    "excluded_unit_access_ids",
    "excluded_superweapon_ids",
    "excluded_unit_buff_types",
    "excluded_power_buff_types",
    "randomize_unit_access",
    "start_with_tier_one_units",
    "start_with_tier_one_defenses",
    "starting_reward_count",
    "starting_reward_types",
    "starting_unlock_rewards",
    "include_defensive_buildings",
    "include_special_buildings",
    "include_special_rewards",
    "unlimited_hero_units",
    "share_chaos_role_buffs",
    "buff_allied_helpers",
    "failure_assistance",
    "include_buff_rewards",
    "include_superweapon_rewards",
    "include_secondary_superweapon_rewards",
    "include_aid_power_rewards",
    "include_power_buff_rewards",
    "enabled_buff_types",
    "enabled_power_buff_types",
    "reward_weights",
    "enemy_scaling",
}


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
    """Return exact player-facing gameplay controls; omit UI/network/derived data."""
    if not isinstance(config, dict):
        return {}
    result = {
        key: deepcopy(config[key])
        for key in GAMEPLAY_CONFIG_KEYS
        if key in config
    }
    if isinstance(config.get("generation"), dict):
        result["generation"] = {
            key: deepcopy(value)
            for key, value in config["generation"].items()
            if key in PLAYER_GENERATION_KEYS
        }
    return result


def _launcher_snapshot_for_state(state, config):
    """Freeze values read from live launcher controls without state/default overlays."""
    result = gameplay_config_snapshot(config)
    if result:
        return result
    return {
        "seed": str(state.get("seed") or ""),
        "campaign_filter": str(state.get("campaign_filter") or ""),
        "mission_goal": int(state.get("mission_goal") or 1),
        "progression_mode": str(state.get("progression_mode") or "Classic"),
        "grid_two_start_positions": bool(
            (state.get("grid") or {}).get("two_start_positions", False)
            if isinstance(state.get("grid"), dict) else False
        ),
        "unlock_all_rewards_after_final_grid_mission": bool(
            state.get("unlock_all_rewards_after_final_grid_mission", False)
        ),
        "rewards_per_objective": int(state.get("rewards_per_check") or 1),
        "rewards_on_victory_only": bool(
            state.get("rewards_on_victory_only", False)
        ),
        "use_act_based_reward_multipliers": bool(
            state.get("use_act_based_reward_multipliers", True)
        ),
        "generation": {
            "reward_mode": state.get("reward_mode"),
            **deepcopy(state.get("mission_pool_settings") or {}),
            **deepcopy(state.get("reward_settings") or {}),
        },
    }


def _server_state_snapshot(state):
    """Freeze generated run structure while removing mutable local progress."""
    snapshot = deepcopy(state)
    snapshot.pop("archipelago", None)
    snapshot["completed_missions"] = []
    snapshot["started_missions"] = []
    snapshot["mission_failure_stacks"] = {}
    snapshot["mission_assistance_units"] = {}
    snapshot["earned_rewards"] = []
    # This is a generation-only duplicate of every planned reward. AP owns
    # delivery after room creation, so shipping it back in Connected slot data
    # wastes several megabytes and can make hosted rooms time out during auth.
    snapshot["reward_queue"] = []
    snapshot.pop("enemy_progress_plan", None)
    snapshot.pop("enemy_progress_earned", None)
    snapshot.pop("enemy_progress_requested", None)
    snapshot["enemy_reward_applications"] = {}
    for checks in snapshot.get("mission_checks", {}).values():
        if not isinstance(checks, list):
            continue
        for check in checks:
            if isinstance(check, dict):
                check.pop("unlocked", None)
                check.pop("released", None)
                # AP randomizes the item pool onto these locations, so local
                # pre-generation assignments are both stale and unnecessary.
                # Slot-data location groups retain exact reward counts; scouts
                # and ReceivedItems are authoritative for item identities.
                check.pop("rewards", None)
                check.pop("reward", None)
    grid = snapshot.get("grid")
    if isinstance(grid, dict):
        for node in grid.get("nodes", {}).values():
            if isinstance(node, dict):
                node.pop("state", None)
    return snapshot


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


def _append_enemy_trap_inventory(state, mission_order, locations, item_pool):
    """Add deterministic Trap items plus matching extra AP locations."""
    settings = state.get("reward_settings", {}).get("enemy_scaling")
    traps = plan_enemy_trap_rewards(
        state.get("seed", ""), settings, REWARD_POOL
    )
    if not traps:
        return []
    maximums = {
        (mission["code"], check["id"]): int(check["maximum_slots"])
        for mission in build_catalogue_projection()["missions"]
        if mission["code"] in mission_order
        for check in mission["checks"]
    }
    available = [
        [code, check_id, maximum]
        for code in mission_order
        for (mission_code, check_id), maximum in maximums.items()
        if mission_code == code
        if int(locations.get(code, {}).get(check_id, 0)) < maximum
    ]
    added = []
    cursor = 0
    for reward in traps:
        while available:
            slot = available[cursor % len(available)]
            code, check_id, maximum = slot
            current = int(locations.setdefault(code, {}).get(check_id, 0))
            if current >= maximum:
                available.pop(cursor % len(available))
                if available:
                    cursor %= len(available)
                continue
            locations[code][check_id] = current + 1
            name = reward["name"]
            item_pool[name] += 1
            added.append(name)
            cursor = (cursor + 1) % len(available)
            break
        if not available:
            break
    return added


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

    enemy_traps = _append_enemy_trap_inventory(
        state, mission_order, locations, item_pool
    )

    progression_mode = str(state.get("progression_mode") or "Classic")
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "randomizer_version": APP_VERSION,
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
            "use_act_based_reward_multipliers": bool(
                state.get("use_act_based_reward_multipliers", True)
            ),
            "unlock_all_rewards_after_final_grid_mission": state.get(
                "unlock_all_rewards_after_final_grid_mission"
            ),
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
            "enemy_trap_count": len(enemy_traps),
            "launcher": _launcher_snapshot_for_state(
                state, launcher_config
            ),
        },
        "state_snapshot": _server_state_snapshot(state),
    }
    unsigned = _canonical_json(manifest).encode("utf-8")
    manifest["manifest_checksum"] = sha256(unsigned).hexdigest()
    return manifest


def validate_run_manifest_checksum(manifest):
    """Validate signed manifest identity without consulting launcher state."""
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
    return manifest


def validate_run_manifest_for_state(state, manifest):
    """Validate checksum and exact immutable identity against the active run."""
    validate_run_manifest_checksum(manifest)
    supplied_checksum = str(manifest.get("manifest_checksum") or "")
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
