"""Mental Omega APWorld options."""

from dataclasses import dataclass

from Options import (
    Choice,
    DefaultOnToggle,
    FreeText,
    OptionCounter,
    OptionDict,
    OptionGroup,
    OptionSet,
    PerGameCommonOptions,
    Range,
    Toggle,
    Visibility,
)

from .data import MISSION_DATA


CAMPAIGNS = (
    "All Campaigns", "Allies", "Soviets", "Epsilon", "Foehn",
)
PROGRESSION_MODES = ("Classic", "Mission List", "Grid Mode", "Shop Mode")
REWARD_MODES = ("Standard", "Chaos", "Randomizer Arsenal")
DIFFICULTIES = ("Casual", "Normal", "Mental")
GAME_SPEEDS = (
    "0 - Slowest", "1 - Slower", "2 - Slow", "3 - Medium",
    "4 - Fast", "5 - Faster", "6 - Fastest",
)
PLAYER_COLORS = (
    "Default", "Gold", "Red", "DarkBlue", "Green", "Orange", "Sky", "Purple",
    "Pink", "Teal", "Aqua", "Lime", "Magenta", "Crimson", "Brown2",
    "DarkGreen", "DarkRed", "LightBlue", "NeonGreen", "Olive", "Purple2",
    "Purple3", "Russet", "Yellow",
)
EVA_VOICES = ("Mission default", "Allied", "Soviet", "Epsilon", "Foehn", "Random")


class LauncherSettings(OptionDict):
    """Legacy launcher-exported settings. New YAMLs use the options below."""

    visibility = Visibility.none
    display_name = "Launcher Settings"
    default = {}


class RunManifest(FreeText):
    """Legacy launcher-exported deterministic run manifest as JSON."""

    visibility = Visibility.none
    display_name = "Run Manifest"
    default = ""


class GeneratedWorld(OptionDict):
    """Legacy world template retained for old player files."""

    visibility = Visibility.none
    display_name = "Generated World"
    default = {}


class Campaign(Choice):
    """Mission campaign pool. All Campaigns includes every installed campaign."""

    display_name = "Campaign"
    option_all_campaigns = 0
    option_allies = 1
    option_soviets = 2
    option_epsilon = 3
    option_foehn = 4
    default = 0


class MissionGoal(Range):
    """Number of missions in the generated run."""

    display_name = "Missions to Finish"
    range_start = 1
    range_end = len(MISSION_DATA)
    default = 15


class ProgressionMode(Choice):
    """Classic order, shuffled list, mission grid, or ten-stage Shop Mode."""

    display_name = "Progression Mode"
    option_classic = 0
    option_mission_list = 1
    option_grid_mode = 2
    option_shop_mode = 3
    default = 1


class GridTwoStartPositions(Toggle):
    """Start Grid Mode with two available neighboring missions."""

    display_name = "Grid: Two Starting Missions"


class UnlockAllGridRewards(Toggle):
    """Release unfinished Grid rewards after completing the final Grid mission."""

    display_name = "Grid: Release Rewards After Goal"


class RewardsPerObjective(Range):
    """Number of item draws assigned to each objective or mission victory."""

    display_name = "Rewards Per Objective"
    range_start = 1
    range_end = 30
    default = 4


class RewardsOnVictoryOnly(Toggle):
    """Assign configured player rewards only to Mission Victory checks."""

    display_name = "Rewards Only When Mission Is Finished"


class UseActRewardMultipliers(DefaultOnToggle):
    """Give later-act and finale missions additional victory rewards."""

    display_name = "Use Act-Based Reward Multipliers"


class Difficulty(Choice):
    """Difficulty written to every launched mission."""

    display_name = "Difficulty"
    option_casual = 0
    option_normal = 1
    option_mental = 2
    default = 1


class GameSpeed(Choice):
    """Game speed written to every launched mission."""

    display_name = "Game Speed"
    option_0_slowest = 0
    option_1_slower = 1
    option_2_slow = 2
    option_3_medium = 3
    option_4_fast = 4
    option_5_faster = 5
    option_6_fastest = 6
    default = 3


class PlayerColor(Choice):
    """Player color used by launched missions."""

    display_name = "Player Color"
    option_default = 0
    option_gold = 1
    option_red = 2
    option_darkblue = 3
    option_green = 4
    option_orange = 5
    option_sky = 6
    option_purple = 7
    option_pink = 8
    option_teal = 9
    option_aqua = 10
    option_lime = 11
    option_magenta = 12
    option_crimson = 13
    option_brown2 = 14
    option_darkgreen = 15
    option_darkred = 16
    option_lightblue = 17
    option_neongreen = 18
    option_olive = 19
    option_purple2 = 20
    option_purple3 = 21
    option_russet = 22
    option_yellow = 23
    default = 0


class Rainbowizer(Toggle):
    """Randomize the player color deterministically for each mission."""

    display_name = "Rainbowizer"


class EvaVoice(Choice):
    """Announcer voice and matching sidebar appearance used by launched missions."""

    display_name = "EVA Voice"
    option_mission_default = 0
    option_allied = 1
    option_soviet = 2
    option_epsilon = 3
    option_foehn = 4
    option_random_voice = 5
    default = 0


class RewardMode(Choice):
    """Standard, all-faction Chaos, or per-mission Randomizer Arsenal rewards."""

    display_name = "Reward Mode"
    option_standard = 0
    option_chaos = 1
    option_randomizer_arsenal = 2
    default = 0


class IncludeNoBuildMissions(DefaultOnToggle):
    """Include true no-build missions played with fixed or scripted forces."""

    display_name = "Include True No-Build Missions"


class IncludeNoBuildProductionMissions(DefaultOnToggle):
    """Include no-build missions that still provide limited production."""

    display_name = "Include No-Build Production Missions"


class IncludeOperationMissions(DefaultOnToggle):
    """Include optional operation missions in the mission pool."""

    display_name = "Include Operation Missions"


class PrioritizeNoBuildMissions(Toggle):
    """Prefer enabled no-build missions in protected opening positions."""

    display_name = "Prioritize No-Build Openings"


class ExcludedMissions(OptionSet):
    """Mission codes removed from the generated mission pool."""

    display_name = "Excluded Missions"
    valid_keys = frozenset(MISSION_DATA)
    default = frozenset()


class RandomizeUnitAccess(DefaultOnToggle):
    """Lock unearned combat technology and add unit access rewards."""

    display_name = "Randomize Unit Access"


class LimitUnitAndPowerAccess(Toggle):
    """Cap unique unit/building and power identities placed in the run."""

    display_name = "Limit Unit and Power Access"


class UnitAccessLimit(Range):
    """Maximum unique unit and building access identities when limits are enabled."""

    display_name = "Unit Access Limit"
    range_start = 1
    range_end = 999
    default = 1


class PowerAccessLimit(Range):
    """Maximum unique superweapon and aid-power identities when limits are enabled."""

    display_name = "Power Access Limit"
    range_start = 1
    range_end = 999
    default = 1


class StartWithTierOneUnits(Toggle):
    """Start with a safe basic Tier 1 combat roster."""

    display_name = "Start With Tier 1 Units"


class StartWithTierOneDefenses(Toggle):
    """Start with basic anti-ground and anti-air defenses."""

    display_name = "Start With Tier 1 Defenses"


class StartingRewardCount(Range):
    """Number of ordinary rewards granted before the first mission."""

    display_name = "Starting Reward Count"
    range_start = 0
    range_end = 9999
    default = 0


class StartingRewardTypes(OptionSet):
    """Unlock families allowed for randomly rolled starting rewards."""

    display_name = "Starting Reward Types"
    valid_keys = frozenset({
        "access", "superweapon", "secondary_superweapon", "aid_power",
    })
    default = frozenset()


class IncludeDefensiveBuildings(DefaultOnToggle):
    """Include defensive structures in access and buff rewards."""

    display_name = "Include Defensive Buildings"


class IncludeSpecialBuildings(DefaultOnToggle):
    """Include special economy building access rewards."""

    display_name = "Include Special Buildings"


class IncludeSpecialRewards(DefaultOnToggle):
    """Include campaign and map-only units, buildings, and powers."""

    display_name = "Include Special Rewards"


class UnlimitedHeroUnits(Toggle):
    """Remove positive simultaneous-unit limits from player hero clones."""

    display_name = "Unlimited Hero Units"


class ShareChaosRoleBuffs(Toggle):
    """Share buffs with curated same-tier equivalents in Chaos or all-campaign play."""

    display_name = "Share Equivalent Unit Buffs"


class BuffAlliedHelpers(Toggle):
    """Apply compatible player buffs to reviewed allied AI helpers."""

    display_name = "Buff Allied Helpers"


class FailureAssistance(Toggle):
    """Strengthen the player on each retry of a failed mission."""

    display_name = "Failure Assistance"


class IncludeBuffRewards(DefaultOnToggle):
    """Include repeatable unit and building buff rewards."""

    display_name = "Include Buff Rewards"


class IncludeSuperweaponRewards(DefaultOnToggle):
    """Include offensive superweapon unlock rewards."""

    display_name = "Include Offensive Superweapons"


class IncludeSecondarySuperweaponRewards(DefaultOnToggle):
    """Include secondary superweapon unlock rewards."""

    display_name = "Include Secondary Superweapons"


class IncludeAidPowerRewards(DefaultOnToggle):
    """Include support and aid power unlock rewards."""

    display_name = "Include Aid Powers"


class IncludePowerBuffRewards(DefaultOnToggle):
    """Include repeatable buffs for unlocked superweapons and aid powers."""

    display_name = "Include Power Buffs"


class EnabledBuffTypes(OptionSet):
    """Unit and building buff families allowed in the reward pool."""

    display_name = "Enabled Unit Buff Types"
    valid_keys = frozenset({
        "production", "cost", "speed", "armor", "health", "damage", "reload",
        "range", "sight", "ammo", "storage", "passenger_capacity", "open_topped",
        "build_limit", "building_limit", "cloak", "sensors", "self_healing",
        "income", "veteran",
    })
    default = frozenset({
        "production", "cost", "speed", "armor", "health", "damage", "reload",
        "range", "sight", "ammo", "storage", "passenger_capacity", "open_topped",
        "self_healing", "cloak", "sensors", "veteran", "build_limit",
        "building_limit", "income",
    })


class EnabledPowerBuffTypes(OptionSet):
    """Superweapon and aid-power buff families allowed in the reward pool."""

    display_name = "Enabled Power Buff Types"
    valid_keys = frozenset({
        "recharge", "cost", "area", "damage", "health", "duration", "effect",
        "targeting", "vision", "payload",
    })
    default = frozenset({
        "recharge", "cost", "area", "damage", "health", "duration", "effect",
        "targeting", "vision", "payload",
    })


class MainRewardWeights(OptionCounter):
    """Relative reward-category weights. Zero disables a category."""

    display_name = "Main Reward Weights"
    valid_keys = frozenset({
        "unit_unlocks", "power_unlocks", "special_unlocks", "production",
        "unit_buffs", "power_buffs",
    })
    min = 0
    max = 100
    default = {key: 100 for key in valid_keys}


class UnitBuffWeights(OptionCounter):
    """Relative weights for unit and building buff families."""

    display_name = "Unit Buff Weights"
    valid_keys = frozenset({
        "speed", "health", "damage", "range", "reload", "armor", "cost",
        "production", "self_healing", "sight", "ammo", "storage",
        "passenger_capacity", "open_topped", "cloak", "sensors", "veteran",
        "build_limit", "building_limit", "income", "other",
    })
    min = 0
    max = 100
    default = {key: 100 for key in valid_keys}


class PowerBuffWeights(OptionCounter):
    """Relative weights for superweapon and aid-power buff families."""

    display_name = "Power Buff Weights"
    valid_keys = frozenset({
        "recharge", "cost", "area", "damage", "duration", "vision", "payload",
        "other",
    })
    min = 0
    max = 100
    default = {key: 100 for key in valid_keys}


class ArsenalFactions(OptionSet):
    """Faction families available to Randomizer Arsenal rosters."""

    display_name = "Arsenal Factions"
    valid_keys = frozenset({"Allies", "Soviets", "Epsilon", "Foehn"})
    default = valid_keys


class ArsenalRosterSizes(OptionCounter):
    """Roster size per tier and production category."""

    display_name = "Arsenal Roster Sizes"
    valid_keys = frozenset(
        f"tier_{tier}_{category}"
        for tier in (1, 2, 3)
        for category in ("infantry", "vehicles", "aircraft", "naval")
    )
    min = 0
    max = 20
    default = {
        "tier_1_infantry": 3, "tier_1_vehicles": 2,
        "tier_1_aircraft": 0, "tier_1_naval": 0,
        "tier_2_infantry": 3, "tier_2_vehicles": 3,
        "tier_2_aircraft": 1, "tier_2_naval": 1,
        "tier_3_infantry": 2, "tier_3_vehicles": 2,
        "tier_3_aircraft": 1, "tier_3_naval": 1,
    }


class ArsenalPowerCounts(OptionCounter):
    """Offensive, secondary, and aid powers in each Arsenal roster."""

    display_name = "Arsenal Power Counts"
    valid_keys = frozenset({"offensive", "secondary", "aid"})
    min = 0
    max = 20
    default = {"offensive": 1, "secondary": 0, "aid": 1}


class EnemyMaximumTotalBuffs(Range):
    """Maximum hostile-AI bonus stacks placed as Archipelago Trap items."""

    display_name = "Maximum Total Enemy Buffs"
    range_start = 0
    range_end = 250
    default = 0


@dataclass
class MentalOmegaOptions(PerGameCommonOptions):
    launcher_settings: LauncherSettings
    generated_world: GeneratedWorld
    run_manifest: RunManifest
    campaign: Campaign
    mission_goal: MissionGoal
    progression_mode: ProgressionMode
    grid_two_start_positions: GridTwoStartPositions
    unlock_all_grid_rewards: UnlockAllGridRewards
    rewards_per_objective: RewardsPerObjective
    rewards_on_victory_only: RewardsOnVictoryOnly
    use_act_reward_multipliers: UseActRewardMultipliers
    difficulty: Difficulty
    game_speed: GameSpeed
    player_color: PlayerColor
    rainbowizer: Rainbowizer
    eva_voice: EvaVoice
    reward_mode: RewardMode
    include_no_build_missions: IncludeNoBuildMissions
    include_no_build_production_missions: IncludeNoBuildProductionMissions
    include_operation_missions: IncludeOperationMissions
    prioritize_no_build_missions: PrioritizeNoBuildMissions
    excluded_missions: ExcludedMissions
    randomize_unit_access: RandomizeUnitAccess
    limit_unit_and_power_access: LimitUnitAndPowerAccess
    unit_access_limit: UnitAccessLimit
    power_access_limit: PowerAccessLimit
    start_with_tier_one_units: StartWithTierOneUnits
    start_with_tier_one_defenses: StartWithTierOneDefenses
    starting_reward_count: StartingRewardCount
    starting_reward_types: StartingRewardTypes
    include_defensive_buildings: IncludeDefensiveBuildings
    include_special_buildings: IncludeSpecialBuildings
    include_special_rewards: IncludeSpecialRewards
    unlimited_hero_units: UnlimitedHeroUnits
    share_chaos_role_buffs: ShareChaosRoleBuffs
    buff_allied_helpers: BuffAlliedHelpers
    failure_assistance: FailureAssistance
    include_buff_rewards: IncludeBuffRewards
    include_superweapon_rewards: IncludeSuperweaponRewards
    include_secondary_superweapon_rewards: IncludeSecondarySuperweaponRewards
    include_aid_power_rewards: IncludeAidPowerRewards
    include_power_buff_rewards: IncludePowerBuffRewards
    enabled_buff_types: EnabledBuffTypes
    enabled_power_buff_types: EnabledPowerBuffTypes
    main_reward_weights: MainRewardWeights
    unit_buff_weights: UnitBuffWeights
    power_buff_weights: PowerBuffWeights
    arsenal_factions: ArsenalFactions
    arsenal_roster_sizes: ArsenalRosterSizes
    arsenal_power_counts: ArsenalPowerCounts
    enemy_maximum_total_buffs: EnemyMaximumTotalBuffs


MENTAL_OMEGA_OPTION_GROUPS = [
    OptionGroup("Randomizer Run", [
        Campaign, MissionGoal, ProgressionMode, GridTwoStartPositions,
        UnlockAllGridRewards, Difficulty, GameSpeed, PlayerColor, Rainbowizer,
        EvaVoice,
    ]),
    OptionGroup("Mission Pool", [
        IncludeNoBuildMissions, IncludeNoBuildProductionMissions,
        IncludeOperationMissions, PrioritizeNoBuildMissions, ExcludedMissions,
    ]),
    OptionGroup("Reward Pool", [
        RewardsPerObjective, RewardsOnVictoryOnly, UseActRewardMultipliers,
        RewardMode, RandomizeUnitAccess, LimitUnitAndPowerAccess,
        UnitAccessLimit, PowerAccessLimit, StartWithTierOneUnits,
        StartWithTierOneDefenses,
        StartingRewardCount, StartingRewardTypes, IncludeDefensiveBuildings,
        IncludeSpecialBuildings, IncludeSpecialRewards, UnlimitedHeroUnits,
        ShareChaosRoleBuffs, BuffAlliedHelpers, FailureAssistance,
        IncludeBuffRewards, IncludeSuperweaponRewards,
        IncludeSecondarySuperweaponRewards, IncludeAidPowerRewards,
        IncludePowerBuffRewards,
    ]),
    OptionGroup("Buffs and Weights", [
        EnabledBuffTypes, EnabledPowerBuffTypes, MainRewardWeights,
        UnitBuffWeights, PowerBuffWeights,
    ], start_collapsed=True),
    OptionGroup("Randomizer Arsenal", [
        ArsenalFactions, ArsenalRosterSizes, ArsenalPowerCounts,
    ], start_collapsed=True),
    OptionGroup("Enemy Rewards", [EnemyMaximumTotalBuffs], start_collapsed=True),
]


def _arsenal_rosters(flat):
    return {
        f"tier_{tier}": {
            category: int(flat.get(f"tier_{tier}_{category}", 0))
            for category in ("infantry", "vehicles", "aircraft", "naval")
        }
        for tier in (1, 2, 3)
    }


def launcher_settings_from_options(options):
    """Translate option-creator fields into the launcher's nested settings."""
    generation = {
        "reward_mode": REWARD_MODES[options.reward_mode.value],
        "arsenal": {
            "factions": sorted(options.arsenal_factions.value),
            "roster_sizes": _arsenal_rosters(options.arsenal_roster_sizes.value),
            "power_counts": dict(options.arsenal_power_counts.value),
        },
        "include_no_build_missions": bool(options.include_no_build_missions.value),
        "include_no_build_production_missions": bool(
            options.include_no_build_production_missions.value
        ),
        "include_operation_missions": bool(options.include_operation_missions.value),
        "prioritize_no_build_missions": bool(options.prioritize_no_build_missions.value),
        "excluded_mission_codes": sorted(options.excluded_missions.value),
        "randomize_unit_access": bool(options.randomize_unit_access.value),
        "access_limits": {
            "enabled": bool(options.limit_unit_and_power_access.value),
            "units": options.unit_access_limit.value,
            "powers": options.power_access_limit.value,
        },
        "start_with_tier_one_units": bool(options.start_with_tier_one_units.value),
        "start_with_tier_one_defenses": bool(options.start_with_tier_one_defenses.value),
        "starting_reward_count": options.starting_reward_count.value,
        "starting_reward_types": sorted(options.starting_reward_types.value),
        "include_defensive_buildings": bool(options.include_defensive_buildings.value),
        "include_special_buildings": bool(options.include_special_buildings.value),
        "include_special_rewards": bool(options.include_special_rewards.value),
        "unlimited_hero_units": bool(options.unlimited_hero_units.value),
        "share_chaos_role_buffs": bool(options.share_chaos_role_buffs.value),
        "buff_allied_helpers": bool(options.buff_allied_helpers.value),
        "failure_assistance": bool(options.failure_assistance.value),
        "include_buff_rewards": bool(options.include_buff_rewards.value),
        "include_superweapon_rewards": bool(options.include_superweapon_rewards.value),
        "include_secondary_superweapon_rewards": bool(
            options.include_secondary_superweapon_rewards.value
        ),
        "include_aid_power_rewards": bool(options.include_aid_power_rewards.value),
        "include_power_buff_rewards": bool(options.include_power_buff_rewards.value),
        "enabled_buff_types": sorted(options.enabled_buff_types.value),
        "enabled_power_buff_types": sorted(options.enabled_power_buff_types.value),
        "reward_weights": {
            "main": dict(options.main_reward_weights.value),
            "unit_buffs": dict(options.unit_buff_weights.value),
            "power_buffs": dict(options.power_buff_weights.value),
        },
        "enemy_scaling": {
            "maximum_total_buffs": options.enemy_maximum_total_buffs.value,
        },
    }
    return {
        "campaign_filter": CAMPAIGNS[options.campaign.value],
        "mission_goal": options.mission_goal.value,
        "progression_mode": PROGRESSION_MODES[options.progression_mode.value],
        "grid_two_start_positions": bool(options.grid_two_start_positions.value),
        "unlock_all_rewards_after_final_grid_mission": bool(
            options.unlock_all_grid_rewards.value
        ),
        "rewards_per_objective": options.rewards_per_objective.value,
        "rewards_on_victory_only": bool(options.rewards_on_victory_only.value),
        "use_act_based_reward_multipliers": bool(
            options.use_act_reward_multipliers.value
        ),
        "difficulty": DIFFICULTIES[options.difficulty.value],
        "game_speed": GAME_SPEEDS[options.game_speed.value],
        "player_color": PLAYER_COLORS[options.player_color.value],
        "rainbowizer": bool(options.rainbowizer.value),
        "eva_voice": EVA_VOICES[options.eva_voice.value],
        "generation": generation,
    }
