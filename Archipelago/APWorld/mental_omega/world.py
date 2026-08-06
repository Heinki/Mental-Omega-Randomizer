"""Manifest-driven Mental Omega Archipelago world."""

from collections import Counter

from BaseClasses import Item, ItemClassification, Location, Region, Tutorial
from worlds.AutoWorld import WebWorld, World

from .data import (
    CATALOGUE_CHECKSUM,
    GAME_NAME,
    ITEM_DATA,
    ITEM_NAME_GROUPS,
    ITEM_TABLE,
    LOCATION_TABLE,
    MISSION_DATA,
    VICTORY_EVENT,
    location_entries,
)
from .manifest import parse_manifest, validate_launcher_settings
from .options import MentalOmegaOptions


class MentalOmegaItem(Item):
    game = GAME_NAME


class MentalOmegaLocation(Location):
    game = GAME_NAME


class MentalOmegaWebWorld(WebWorld):
    theme = "partyTime"
    tutorials = [
        Tutorial(
            "Mental Omega Multiworld Setup Guide",
            "Connect the embedded Mental Omega Randomizer client.",
            "English",
            "setup_en.md",
            "setup/en",
            ["Mental Omega Randomizer contributors"],
        )
    ]


class MentalOmegaWorld(World):
    """Full catalogue; each seed's shape comes from one signed manifest."""

    game = GAME_NAME
    web = MentalOmegaWebWorld()
    options_dataclass = MentalOmegaOptions
    options: MentalOmegaOptions

    item_name_to_id = {
        name: data["id"] for name, data in ITEM_DATA.items()
    }
    location_name_to_id = dict(LOCATION_TABLE)
    item_name_groups = ITEM_NAME_GROUPS
    location_name_groups = {
        "Objectives": {
            name for name in LOCATION_TABLE if " - Objective " in name
        },
        "Mission Completion": {
            name for name in LOCATION_TABLE if " - Mission Complete - " in name
        },
    }

    def generate_early(self) -> None:
        self.run_manifest = parse_manifest(self.options.run_manifest.value)
        validate_launcher_settings(
            self.options.launcher_settings.value,
            self.run_manifest,
        )

    def create_item(self, name: str) -> MentalOmegaItem:
        item_id, classification = ITEM_TABLE[name]
        return MentalOmegaItem(name, classification, item_id, self.player)

    def _active_location_entries(self):
        for code in self.run_manifest["mission_order"]:
            for check_id, count in self.run_manifest["locations"][code].items():
                yield from location_entries(code, check_id, count)

    def create_regions(self) -> None:
        menu = Region("Menu", self.player, self.multiworld)
        victory = MentalOmegaLocation(
            self.player,
            VICTORY_EVENT,
            None,
            menu,
        )
        victory.place_locked_item(
            MentalOmegaItem(
                VICTORY_EVENT,
                ItemClassification.progression,
                None,
                self.player,
            )
        )
        menu.locations.append(victory)
        regions = [menu]
        by_location = {}
        for code in self.run_manifest["mission_order"]:
            mission = MISSION_DATA[code]
            region = Region(mission["title"], self.player, self.multiworld)
            active = {}
            for check_id, count in self.run_manifest["locations"][code].items():
                active.update(dict(location_entries(code, check_id, count)))
            region.add_locations(active, MentalOmegaLocation)
            by_location.update({location.name: location for location in region.locations})
            menu.connect(region)
            regions.append(region)

        for placement in self.run_manifest["local_placements"]:
            name, _location_id = location_entries(
                placement["mission"],
                placement["check"],
                placement["slot"],
            )[-1]
            by_location[name].place_locked_item(
                self.create_item(placement["item"])
            )
        self.multiworld.regions += regions

    def create_items(self) -> None:
        remaining = Counter(self.run_manifest["item_pool"])
        for placement in self.run_manifest["local_placements"]:
            remaining[placement["item"]] -= 1
        self.multiworld.itempool += [
            self.create_item(name)
            for name, count in remaining.items()
            for _ in range(count)
        ]
        for name, count in self.run_manifest["starting_items"].items():
            for _ in range(count):
                self.multiworld.push_precollected(self.create_item(name))

    def set_rules(self) -> None:
        # Runtime completion is reported by the embedded client from the
        # Randomizer's native goal logic.  This private event only tells AP's
        # generation audit that item placement never gates mission unlocking.
        self.multiworld.completion_condition[self.player] = (
            lambda state: state.has(VICTORY_EVENT, self.player)
        )

    def get_filler_item_name(self) -> str:
        return "Soviet Conscript Access"

    def fill_slot_data(self) -> dict:
        locations = {}
        for code in self.run_manifest["mission_order"]:
            locations[code] = {
                check_id: [
                    location_id
                    for _name, location_id in location_entries(
                        code, check_id, count
                    )
                ]
                for check_id, count in self.run_manifest["locations"][code].items()
            }
        used_items = set(self.run_manifest["item_pool"]) | set(
            self.run_manifest["starting_items"]
        )
        return {
            "slot_data_version": 3,
            "randomizer_version": self.run_manifest["randomizer_version"],
            "randomizer_seed": self.run_manifest["randomizer_seed"],
            "catalogue_checksum": CATALOGUE_CHECKSUM,
            "manifest_checksum": self.run_manifest["manifest_checksum"],
            "campaign_filter": self.run_manifest["campaign_filter"],
            "progression_mode": self.run_manifest["progression_mode"],
            "mission_goal": self.run_manifest["mission_goal"],
            "mission_order": self.run_manifest["mission_order"],
            "goal": self.run_manifest["goal"],
            "run_manifest": self.run_manifest,
            "items": {
                str(ITEM_DATA[name]["id"]): name
                for name in sorted(used_items)
            },
            "locations": locations,
        }
