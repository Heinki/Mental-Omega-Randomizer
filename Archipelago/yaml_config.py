"""Small dependency-free reader/writer for Mental Omega player YAML files."""

from __future__ import annotations

import json

from randomizer.config.player import (
    parse_simple_yaml_text,
    simple_yaml_mapping_lines,
)


GAME_NAME = "Mental Omega"


def _quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def serialize_player_yaml(manifest, slot_name):
    if not isinstance(manifest, dict) or not manifest.get("manifest_checksum"):
        raise ValueError("A validated run manifest is required.")
    formatted_manifest = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    frozen = manifest.get("frozen_settings")
    launcher_settings = (
        frozen.get("launcher") if isinstance(frozen, dict) else None
    )
    if not isinstance(launcher_settings, dict) or not launcher_settings:
        raise ValueError("Run manifest has no readable launcher settings.")
    output = (
        f"name: {_quote(str(slot_name).strip() or 'Commander')}\n"
        f"game: {GAME_NAME}\n"
        "description: Mental Omega Randomizer generated player file\n"
        "requires:\n"
        "  version: 0.6.7\n\n"
        f"{GAME_NAME}:\n"
    )
    output += (
        "\n"
        "  # Exact Settings-page values used to generate this AP run.\n"
        "  # Change settings in the launcher, then save a new Player YAML.\n"
        "  launcher_settings:\n"
    )
    output += "\n".join(
        simple_yaml_mapping_lines(launcher_settings, indent=4)
    )
    # Archipelago options are mappings and scalars, not embedded document
    # fragments.  Keep required generated world input as one normal mapping
    # option.  JSON flow syntax is valid YAML and remains dependency-free.
    manifest_lines = formatted_manifest.splitlines()
    output += "\n\n  generated_world: " + manifest_lines[0] + "\n"
    output += "\n".join(
        "    " + line for line in manifest_lines[1:]
    )
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
    in_game = False
    capture_manifest = False
    capture_launcher_settings = False
    for raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent == 0:
            capture_manifest = False
            capture_launcher_settings = False
            in_game = stripped == f"{GAME_NAME}:"
            if ":" in stripped and not stripped.endswith(":"):
                key, value = stripped.split(":", 1)
                top[key.strip()] = _scalar(value)
            continue
        if in_game and indent == 2:
            capture_manifest = False
            capture_launcher_settings = False
            if stripped.startswith("launcher_settings:"):
                capture_launcher_settings = True
                continue
            if stripped.startswith(("generated_world:", "run_manifest:")):
                capture_manifest = True
                inline = stripped.split(":", 1)[1].strip()
                if inline and inline not in {">", ">-", "|", "|-"}:
                    manifest_parts.append(_scalar(inline))
                continue
        if capture_launcher_settings:
            if indent < 4:
                capture_launcher_settings = False
            else:
                launcher_setting_lines.append(raw[4:])
                continue
        if capture_manifest:
            if indent < 4:
                capture_manifest = False
            else:
                manifest_parts.append(raw[4:].strip())
    if top.get("game") != GAME_NAME:
        raise ValueError("Player YAML game must be Mental Omega.")
    slot_name = str(top.get("name") or "").strip()
    if not slot_name:
        raise ValueError("Player YAML has no slot name.")
    if not manifest_parts:
        raise ValueError("Player YAML has no Mental Omega generated_world data.")
    try:
        manifest = json.loads(" ".join(manifest_parts))
    except json.JSONDecodeError as exc:
        raise ValueError("Player YAML generated_world is not valid JSON.") from exc
    if not isinstance(manifest, dict):
        raise ValueError("Player YAML generated_world must be an object.")
    launcher_settings = parse_simple_yaml_text(
        "\n".join(launcher_setting_lines)
    ) if launcher_setting_lines else {}
    if not launcher_settings:
        frozen = manifest.get("frozen_settings")
        launcher_settings = (
            frozen.get("launcher") if isinstance(frozen, dict) else None
        )
    if not launcher_settings:
        raise ValueError(
            "Player YAML has no readable or manifest-frozen launcher_settings."
        )
    return {
        "name": slot_name,
        "game": GAME_NAME,
        "launcher_settings": launcher_settings,
        "run_manifest": manifest,
    }
