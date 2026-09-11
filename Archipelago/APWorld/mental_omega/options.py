"""Mental Omega APWorld options."""

from dataclasses import dataclass

from Options import FreeText, OptionDict, PerGameCommonOptions, Visibility


class LauncherSettings(OptionDict):
    """Reusable settings. Archipelago generates a fresh run from these options."""

    display_name = "Launcher Settings"
    default = {}


class RunManifest(FreeText):
    """Legacy launcher-exported deterministic run manifest as JSON."""

    visibility = Visibility.none
    display_name = "Run Manifest"
    default = ""


class GeneratedWorld(OptionDict):
    """Legacy world template; new player files need only launcher_settings."""

    visibility = Visibility.none
    display_name = "Generated World"
    default = {}


@dataclass
class MentalOmegaOptions(PerGameCommonOptions):
    launcher_settings: LauncherSettings
    generated_world: GeneratedWorld
    run_manifest: RunManifest
