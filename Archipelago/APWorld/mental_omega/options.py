"""Mental Omega APWorld options."""

from dataclasses import dataclass

from Options import FreeText, OptionDict, PerGameCommonOptions


class LauncherSettings(OptionDict):
    """Readable launcher options mirrored by the signed run manifest."""

    display_name = "Launcher Settings"
    default = {}


class RunManifest(FreeText):
    """Legacy launcher-exported deterministic run manifest as JSON."""

    display_name = "Run Manifest"
    default = ""


class GeneratedWorld(OptionDict):
    """Launcher-generated world input required by this APWorld."""

    display_name = "Generated World"
    default = {}


@dataclass
class MentalOmegaOptions(PerGameCommonOptions):
    launcher_settings: LauncherSettings
    generated_world: GeneratedWorld
    run_manifest: RunManifest
