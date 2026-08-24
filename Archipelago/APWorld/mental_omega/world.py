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
    LOCAL_VICTORY_DATA,
    LOCAL_VICTORY_ITEM_TABLE,
    LOCATION_TABLE,
    MISSION_DATA,
    SHOP_PURCHASE_LOCATION_TABLE,
    SHOP_STAGE_LOCATION_TABLE,
    SHOP_STAGE_LOGIC_DATA,
    SHOP_STAGE_LOGIC_ITEM_TABLE,
    VICTORY_EVENT,
    location_entries,
)
from .manifest import (
    parse_manifest,
    progression_for_manifest,
    validate_launcher_settings,
)
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
    item_name_to_id.update(LOCAL_VICTORY_ITEM_TABLE)
    item_name_to_id.update(SHOP_STAGE_LOGIC_ITEM_TABLE)
    location_name_to_id = dict(LOCATION_TABLE)
    item_name_groups = ITEM_NAME_GROUPS
    location_name_groups = {
        "Objectives": {
            name for name in LOCATION_TABLE if " - Objective " in name
        },
        "Mission Completion": {
            name for name in LOCATION_TABLE if " - Mission Complete - " in name
        },
        "Shop Purchases": set(SHOP_PURCHASE_LOCATION_TABLE),
        "Shop Victories": set(SHOP_STAGE_LOCATION_TABLE),
    }

    def generate_early(self) -> None:
        generated_world = self.options.generated_world.value
        self.run_manifest = parse_manifest(
            generated_world
            if generated_world
            else self.options.run_manifest.value
        )
        self.progression = progression_for_manifest(self.run_manifest)
        validate_launcher_settings(
            self.options.launcher_settings.value,
            self.run_manifest,
        )

    def create_item(self, name: str) -> MentalOmegaItem:
        if name in LOCAL_VICTORY_ITEM_TABLE or name in SHOP_STAGE_LOGIC_ITEM_TABLE:
            item_id = (
                LOCAL_VICTORY_ITEM_TABLE.get(name)
                or SHOP_STAGE_LOGIC_ITEM_TABLE[name]
            )
            return MentalOmegaItem(
                name,
                ItemClassification.progression,
                item_id,
                self.player,
            )
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
        regions = [menu]
        if self.run_manifest["progression_mode"] == "Shop Mode":
            self._create_shop_regions(menu, victory, regions)
            self.multiworld.regions += regions
            return
        by_location = {}
        by_code = {}
        for code in self.run_manifest["mission_order"]:
            mission = MISSION_DATA[code]
            region = Region(mission["title"], self.player, self.multiworld)
            active = {}
            for check_id, count in self.run_manifest["locations"][code].items():
                active.update(dict(location_entries(code, check_id, count)))
            region.add_locations(active, MentalOmegaLocation)
            by_location.update({location.name: location for location in region.locations})
            local_victory = MentalOmegaLocation(
                self.player,
                LOCAL_VICTORY_DATA[code]["location_name"],
                LOCAL_VICTORY_DATA[code]["location_id"],
                region,
            )
            local_victory.place_locked_item(
                self.create_item(LOCAL_VICTORY_DATA[code]["item_name"])
            )
            region.locations.append(local_victory)
            by_code[code] = region
            regions.append(region)

        progression = self.progression
        local_victory_names = {
            code: LOCAL_VICTORY_DATA[code]["item_name"]
            for code in self.run_manifest["mission_order"]
        }
        if progression["type"] == "victory_count":
            all_victories = tuple(local_victory_names.values())
            for code, region in by_code.items():
                required = progression["mission_requirements"][code]
                rule = None if required == 0 else (
                    lambda state, needed=required, names=all_victories:
                    sum(state.has(name, self.player) for name in names) >= needed
                )
                if rule is None:
                    menu.connect(region)
                else:
                    menu.connect(region, rule=rule)
        else:
            starts = set(progression["starting_missions"])
            for code, region in by_code.items():
                required = tuple(
                    local_victory_names[neighbor]
                    for neighbor in progression["mission_requirements"][code]
                )
                rule = None if code in starts else (
                    lambda state, names=required:
                    any(state.has(name, self.player) for name in names)
                )
                if rule is None:
                    menu.connect(region)
                else:
                    menu.connect(region, rule=rule)

        goal = self.run_manifest["goal"]
        goal_codes = (
            self.run_manifest["mission_order"]
            if goal["type"] == "all_missions"
            else [goal["mission_code"]]
        )
        goal_items = tuple(local_victory_names[code] for code in goal_codes)
        victory.access_rule = lambda state, names=goal_items: all(
            state.has(name, self.player) for name in names
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

    def _create_shop_regions(self, menu, victory, regions):
        shop = self.run_manifest["shop"]
        purchase_names = list(SHOP_PURCHASE_LOCATION_TABLE)[
            :shop["purchase_location_count"]
        ]
        menu.add_locations(
            {
                name: SHOP_PURCHASE_LOCATION_TABLE[name]
                for name in purchase_names
            },
            MentalOmegaLocation,
        )
        previous_marker = None
        for stage in range(1, shop["run_length"] + 1):
            region = Region(
                f"Shop Run Stage {stage}", self.player, self.multiworld
            )
            if previous_marker is None:
                menu.connect(region)
            else:
                menu.connect(
                    region,
                    rule=lambda state, name=previous_marker: state.has(
                        name, self.player
                    ),
                )
            if shop["mission_victories_are_locations"]:
                name = f"Shop Run Mission {stage} Victory"
                region.add_locations(
                    {name: SHOP_STAGE_LOCATION_TABLE[name]},
                    MentalOmegaLocation,
                )
            logic = SHOP_STAGE_LOGIC_DATA[stage]
            logic_location = MentalOmegaLocation(
                self.player,
                logic["location_name"],
                logic["location_id"],
                region,
            )
            logic_location.place_locked_item(
                self.create_item(logic["item_name"])
            )
            region.locations.append(logic_location)
            previous_marker = logic["item_name"]
            regions.append(region)
        victory.access_rule = (
            lambda state, name=previous_marker: state.has(name, self.player)
        )
        victory.place_locked_item(MentalOmegaItem(
            VICTORY_EVENT,
            ItemClassification.progression,
            None,
            self.player,
        ))
        menu.locations.append(victory)

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
        # Randomizer's native goal logic. This private event mirrors that goal
        # for generation without controlling launcher mission availability.
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
        shop = self.run_manifest.get("shop")
        shop_slot_data = None
        if shop is not None:
            shop_slot_data = {
                **shop,
                "purchase_locations": list(
                    SHOP_PURCHASE_LOCATION_TABLE.values()
                )[:shop["purchase_location_count"]],
                "stage_victories": [
                    {
                        "stage": stage,
                        "location": (
                            SHOP_STAGE_LOCATION_TABLE[
                                f"Shop Run Mission {stage} Victory"
                            ]
                            if shop["mission_victories_are_locations"]
                            else None
                        ),
                        "logic_item": SHOP_STAGE_LOGIC_DATA[stage]["item_id"],
                        "logic_location": SHOP_STAGE_LOGIC_DATA[stage][
                            "location_id"
                        ],
                    }
                    for stage in range(1, shop["run_length"] + 1)
                ],
            }
        return {
            "slot_data_version": 6 if shop is not None else 5,
            "randomizer_version": self.run_manifest["randomizer_version"],
            "randomizer_seed": self.run_manifest["randomizer_seed"],
            "catalogue_checksum": CATALOGUE_CHECKSUM,
            "manifest_checksum": self.run_manifest["manifest_checksum"],
            "campaign_filter": self.run_manifest["campaign_filter"],
            "progression_mode": self.run_manifest["progression_mode"],
            "mission_goal": self.run_manifest["mission_goal"],
            "mission_order": self.run_manifest["mission_order"],
            "goal": self.run_manifest["goal"],
            "shop": shop_slot_data,
            "run_manifest": self.run_manifest,
            "items": {
                **{
                    str(ITEM_DATA[name]["id"]): name
                    for name in sorted(used_items)
                },
                **({
                    str(LOCAL_VICTORY_DATA[code]["item_id"]):
                    LOCAL_VICTORY_DATA[code]["item_name"]
                    for code in self.run_manifest["mission_order"]
                } if shop is None else {}),
            },
            "locations": locations,
            "local_victories": ({
                code: {
                    "item": LOCAL_VICTORY_DATA[code]["item_id"],
                    "location": LOCAL_VICTORY_DATA[code]["location_id"],
                }
                for code in self.run_manifest["mission_order"]
            } if shop is None else {}),
        }
