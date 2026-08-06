"""Mental Omega APWorld options."""

from dataclasses import dataclass

from Options import FreeText, OptionDict, PerGameCommonOptions


class LauncherSettings(OptionDict):
    """Readable launcher options mirrored by the signed run manifest."""

    display_name = "Launcher Settings"
    default = {}


class RunManifest(FreeText):
    """Launcher-exported deterministic run manifest as JSON."""

    display_name = "Run Manifest"
    default = ""


@dataclass
class MentalOmegaOptions(PerGameCommonOptions):
    launcher_settings: LauncherSettings
    run_manifest: RunManifest
