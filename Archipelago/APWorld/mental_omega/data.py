"""Generated catalogue loader for the Mental Omega APWorld."""

from collections import defaultdict
from importlib.resources import files
import json

from BaseClasses import ItemClassification


GAME_NAME = "Mental Omega"
VICTORY_EVENT = "Mental Omega Victory"

_CLASSIFICATIONS = {
    "progression": ItemClassification.progression,
    "useful": ItemClassification.useful,
    "filler": ItemClassification.filler,
    "trap": ItemClassification.trap,
}

_SNAPSHOT = json.loads(
    files(__package__).joinpath("catalogue.json").read_text(encoding="utf-8")
)
CATALOGUE_CHECKSUM = _SNAPSHOT["catalogue_checksum"]
MAXIMUM_REWARDS_PER_CHECK = int(_SNAPSHOT["maximum_rewards_per_check"])

ITEM_DATA = {
    entry["name"]: {
        "id": int(entry["id"]),
        "classification": _CLASSIFICATIONS[entry["classification"]],
        "classification_name": entry["classification"],
        "category": entry["category"],
        "repeatable": bool(entry["repeatable"]),
    }
    for entry in _SNAPSHOT["items"]
}
ITEM_TABLE = {
    name: (data["id"], data["classification"])
    for name, data in ITEM_DATA.items()
}

MISSION_DATA = {
    entry["code"]: entry for entry in _SNAPSHOT["missions"]
}
LOCATION_TABLE = {
    entry["name"]: int(entry["id"])
    for entry in _SNAPSHOT["locations"]
}
LOCATION_SLOTS = defaultdict(lambda: defaultdict(list))
for _entry in _SNAPSHOT["locations"]:
    LOCATION_SLOTS[_entry["mission"]][_entry["check"]].append(
        (_entry["name"], int(_entry["id"]))
    )
LOCATION_SLOTS = {
    code: {check_id: tuple(values) for check_id, values in checks.items()}
    for code, checks in LOCATION_SLOTS.items()
}

ITEM_NAME_GROUPS = defaultdict(set)
for _name, _data in ITEM_DATA.items():
    ITEM_NAME_GROUPS[_data["category"]].add(_name)
ITEM_NAME_GROUPS = dict(ITEM_NAME_GROUPS)

# Tables above retain the shared strings/integers they need. Drop the decoded
# 17,640-entry source list so generation does not keep every location object
# twice.
del _SNAPSHOT, _entry, _name, _data


def location_entries(code, check_id, count):
    return LOCATION_SLOTS[code][check_id][:count]
