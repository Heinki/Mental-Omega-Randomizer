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

    $versions = (& python -c (
        "import json; from randomizer.core.version import release_versions; " +
        "print(json.dumps(release_versions()))"
    )).Trim() | ConvertFrom-Json
    $launcherVersion = $versions.app_version

    if (-not (Test-Path -LiteralPath $launcherPath -PathType Leaf)) {
        throw "Launcher output is missing: $launcherPath"
    }
    if (-not (Test-Path -LiteralPath $apworldPath -PathType Leaf)) {
        throw "APWorld output is missing: $apworldPath"
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
        apworld_version = $versions.apworld_version
    })
}
finally {
    Pop-Location
}
