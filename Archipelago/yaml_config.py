"""Small dependency-free reader/writer for Mental Omega player YAML files."""

from __future__ import annotations

import json
from randomizer.config.player import parse_simple_yaml_text
from randomizer.core.version import ARCHIPELAGO_VERSION

GAME_NAME = "Mental Omega"


def _quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def serialize_player_yaml(settings, slot_name):
    """Export reusable gameplay settings, never generated run data."""
    from Archipelago.run_manifest import gameplay_config_snapshot

    if not isinstance(settings, dict):
        raise ValueError("Launcher settings must be a mapping.")
    if "frozen_settings" in settings:
        settings = settings["frozen_settings"].get("launcher", {})
    launcher_settings = gameplay_config_snapshot(settings)
    launcher_settings.pop("seed", None)
    if not launcher_settings:
        raise ValueError("Player YAML needs readable launcher settings.")
    settings_lines = json.dumps(
        launcher_settings, ensure_ascii=False, sort_keys=True, indent=2,
    ).splitlines()
    output = (
        f"name: {_quote(str(slot_name).strip() or 'Commander')}\n"
        f"game: {GAME_NAME}\n"
        f"description: {GAME_NAME} Randomizer player settings\n"
        "requires:\n"
        f"  version: {ARCHIPELAGO_VERSION}\n\n"
        f"{GAME_NAME}:\n"
        "  # Reuse this file for every new Archipelago seed.\n"
        "  # Archipelago generates missions, Grid, starters and rewards.\n"
        "  launcher_settings: " + settings_lines[0] + "\n"
    )
    output += "\n".join("    " + line for line in settings_lines[1:])
    return output + "\n"


def _scalar(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return json.loads(value)
    return value


def parse_player_yaml(text):
    """Read only the fields this launcher owns, rejecting ambiguous files."""
    lines = str(text).lstrip("\ufeff").splitlines()
    top = {}
    manifest_parts = []
    launcher_setting_lines = []
    in_game = capture_manifest = capture_launcher_settings = False
    for raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent == 0:
            capture_manifest = capture_launcher_settings = False
            in_game = stripped == f"{GAME_NAME}:"
            if ":" in stripped and not stripped.endswith(":"):
                key, value = stripped.split(":", 1)
                top[key.strip()] = _scalar(value)
            continue
        if in_game and indent == 2:
            capture_manifest = capture_launcher_settings = False
            if stripped.startswith("launcher_settings:"):
                capture_launcher_settings = True
                inline = stripped.split(":", 1)[1].strip()
                if inline:
                    launcher_setting_lines.append(inline)
                continue
            if stripped.startswith(("generated_world:", "run_manifest:")):
                capture_manifest = True
                inline = stripped.split(":", 1)[1].strip()
                if inline and inline not in {">", ">-", "|", "|-"}:
                    manifest_parts.append(_scalar(inline))
                continue
        if capture_launcher_settings and indent >= 4:
            launcher_setting_lines.append(raw[4:])
            continue
        if capture_manifest and indent >= 4:
            manifest_parts.append(raw[4:].strip())
    if top.get("game") != GAME_NAME:
        raise ValueError(f"Player YAML game must be {GAME_NAME}.")
    slot_name = str(top.get("name") or "").strip()
    if not slot_name:
        raise ValueError("Player YAML has no slot name.")
    manifest = None
    if manifest_parts:
        try:
            manifest = json.loads(" ".join(manifest_parts))
        except json.JSONDecodeError as exc:
            raise ValueError("Player YAML legacy manifest is not valid JSON.") from exc
        if not isinstance(manifest, dict):
            raise ValueError("Player YAML legacy manifest must be an object.")
    settings_text = "\n".join(launcher_setting_lines).strip()
    launcher_settings = (
        json.loads(settings_text) if settings_text.startswith("{")
        else parse_simple_yaml_text(settings_text)
    ) if settings_text else {}
    if not launcher_settings and manifest is not None:
        frozen = manifest.get("frozen_settings")
        launcher_settings = frozen.get("launcher") if isinstance(frozen, dict) else None
    if not isinstance(launcher_settings, dict) or not launcher_settings:
        raise ValueError("Player YAML has no readable or manifest-frozen launcher_settings.")
    return {
        "name": slot_name,
        "game": GAME_NAME,
        "launcher_settings": launcher_settings,
        "run_manifest": manifest,
    }
