"""Small dependency-free reader/writer for Mental Omega player YAML files."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

from randomizer.config.player import (
    parse_simple_yaml_text,
)


GAME_NAME = "Mental Omega"
RANDOM_SEED_MARKER = "random"


def _canonical_json(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def reusable_manifest_template(manifest):
    """Remove exported-run identity and duplicated settings from Player YAML."""
    template = deepcopy(manifest)
    template["randomizer_seed"] = RANDOM_SEED_MARKER
    snapshot = template.get("state_snapshot")
    if isinstance(snapshot, dict):
        snapshot["seed"] = RANDOM_SEED_MARKER
    frozen = template.get("frozen_settings")
    launcher = frozen.get("launcher") if isinstance(frozen, dict) else None
    launcher = deepcopy(launcher) if isinstance(launcher, dict) else {}
    launcher.pop("seed", None)
    # Keep only an integrity fingerprint; full settings already appear once as
    # launcher_settings. APWorld verifies and restores them for slot data.
    template["frozen_settings"] = {
        "launcher_checksum": sha256(
            _canonical_json(launcher).encode("utf-8")
        ).hexdigest(),
    }
    template.pop("manifest_checksum", None)
    template["manifest_checksum"] = sha256(
        _canonical_json(template).encode("utf-8")
    ).hexdigest()
    return template


def _quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def serialize_player_yaml(manifest, slot_name):
    if not isinstance(manifest, dict) or not manifest.get("manifest_checksum"):
        raise ValueError("A validated run manifest is required.")
    frozen = manifest.get("frozen_settings")
    launcher_settings = (
        frozen.get("launcher") if isinstance(frozen, dict) else None
    )
    if not isinstance(launcher_settings, dict) or not launcher_settings:
        raise ValueError("Run manifest has no readable launcher settings.")
    launcher_settings = deepcopy(launcher_settings)
    launcher_settings.pop("seed", None)
    template = reusable_manifest_template(manifest)
    formatted_manifest = json.dumps(
        template,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
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
        "  # Reusable Settings-page values. Archipelago chooses a fresh\n"
        "  # Randomizer seed whenever it generates a new room.\n"
        "  launcher_settings:\n"
    )
    settings_lines = json.dumps(
        launcher_settings, ensure_ascii=False, sort_keys=True, indent=2,
    ).splitlines()
    output = output.removesuffix("  launcher_settings:\n")
    output += "  launcher_settings: " + settings_lines[0] + "\n"
    output += "\n".join("    " + line for line in settings_lines[1:])
    # Seed-independent generated shape needed by this APWorld. It is a normal
    # mapping option; AP generation restores settings, assigns a fresh seed,
    # then signs the room-specific manifest sent to the launcher.
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
    settings_text = "\n".join(launcher_setting_lines).strip()
    launcher_settings = (
        json.loads(settings_text) if settings_text.startswith("{")
        else parse_simple_yaml_text(settings_text)
    ) if settings_text else {}
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
