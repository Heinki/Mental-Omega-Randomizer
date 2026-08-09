param(
    [string]$LauncherOutput = (Join-Path $PSScriptRoot "..\MentalOmegaRandomizer.exe"),
    [string]$APWorldOutputDirectory = (Join-Path $PSScriptRoot "Archipelago")
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Push-Location $PSScriptRoot
try {
    $launcherPath = [IO.Path]::GetFullPath($LauncherOutput)
    $apworldDirectory = [IO.Path]::GetFullPath($APWorldOutputDirectory)
    $apworldPath = Join-Path $apworldDirectory "mental_omega.apworld"

    & (Join-Path $PSScriptRoot "build_exe.ps1") -Output $launcherPath
    if ($LASTEXITCODE -ne 0) {
        throw "Launcher build failed with exit code $LASTEXITCODE."
    }

    & (Join-Path $PSScriptRoot "Archipelago\build_apworld.ps1") `
        -OutputDirectory $apworldDirectory | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "APWorld build failed with exit code $LASTEXITCODE."
    }

    $launcherVersion = (& python -c (
        "from randomizer.core.version import APP_VERSION; print(APP_VERSION)"
    )).Trim()
    $worldManifestPath = Join-Path $PSScriptRoot (
        "Archipelago\APWorld\mental_omega\archipelago.json"
    )
    $worldManifest = Get-Content -LiteralPath $worldManifestPath -Raw |
        ConvertFrom-Json
    $worldContractPath = Join-Path $PSScriptRoot (
        "Archipelago\APWorld\mental_omega\manifest.py"
    )
    $worldContract = Get-Content -LiteralPath $worldContractPath -Raw

    if (-not (Test-Path -LiteralPath $launcherPath -PathType Leaf)) {
        throw "Launcher output is missing: $launcherPath"
    }
    if (-not (Test-Path -LiteralPath $apworldPath -PathType Leaf)) {
        throw "APWorld output is missing: $apworldPath"
    }
    if ($worldContract -notmatch (
        'RANDOMIZER_VERSION\s*=\s*["'']' +
        [Regex]::Escape($launcherVersion) + '["'']'
    )) {
        throw "APWorld launcher compatibility does not match v$launcherVersion."
    }

    $fileVersion = (Get-Item -LiteralPath $launcherPath).VersionInfo.FileVersion
    if (-not $fileVersion.StartsWith($launcherVersion)) {
        throw (
            "Built EXE version $fileVersion does not match launcher " +
            "v$launcherVersion."
        )
    }

    Write-Output ([pscustomobject]@{
        launcher = $launcherPath
        launcher_version = $launcherVersion
        apworld = $apworldPath
        apworld_version = $worldManifest.world_version
    })
}
finally {
    Pop-Location
}
