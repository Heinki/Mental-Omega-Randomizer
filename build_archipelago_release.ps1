param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot "release")
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$outputPath = [IO.Path]::GetFullPath($OutputDirectory)
$launcherPath = Join-Path $outputPath "MentalOmegaRandomizer.exe"
$apworldPath = Join-Path $outputPath "mental_omega.apworld"
$setupPath = Join-Path $outputPath "MentalOmegaRandomizer-Archipelago-Setup.md"
$manifestPath = Join-Path $outputPath "release_manifest.json"
$checksumsPath = Join-Path $outputPath "SHA256SUMS.txt"

New-Item -ItemType Directory -Path $outputPath -Force | Out-Null

& (Join-Path $PSScriptRoot "build_all.ps1") `
    -LauncherOutput $launcherPath `
    -APWorldOutputDirectory $outputPath | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Combined launcher/APWorld build failed with exit code $LASTEXITCODE."
}

Copy-Item -LiteralPath (
    Join-Path $PSScriptRoot "Archipelago\SETUP.md"
) -Destination $setupPath -Force

$launcherVersion = (& python -c (
    "from randomizer.core.version import APP_VERSION; print(APP_VERSION)"
)).Trim()
$worldSourceManifest = Get-Content -LiteralPath (
    Join-Path $PSScriptRoot "Archipelago\APWorld\mental_omega\archipelago.json"
) -Raw | ConvertFrom-Json

$payloadFiles = @(
    "MentalOmegaRandomizer.exe",
    "mental_omega.apworld",
    "MentalOmegaRandomizer-Archipelago-Setup.md"
)
$payloadHashes = [ordered]@{}
foreach ($name in $payloadFiles) {
    $payloadHashes[$name] = (
        Get-FileHash -LiteralPath (Join-Path $outputPath $name) -Algorithm SHA256
    ).Hash.ToLowerInvariant()
}

$releaseManifest = [ordered]@{
    format = 1
    launcher_version = $launcherVersion
    archipelago_version = "0.6.7"
    apworld_game = $worldSourceManifest.game
    apworld_version = $worldSourceManifest.world_version
    files = $payloadHashes
} | ConvertTo-Json -Depth 5
[IO.File]::WriteAllText(
    $manifestPath,
    $releaseManifest + "`n",
    [Text.UTF8Encoding]::new($false)
)

$checksumFiles = @($payloadFiles + "release_manifest.json")
$checksumLines = foreach ($name in $checksumFiles) {
    $hash = (
        Get-FileHash -LiteralPath (Join-Path $outputPath $name) -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    "$hash *$name"
}
[IO.File]::WriteAllLines(
    $checksumsPath,
    $checksumLines,
    [Text.Encoding]::ASCII
)

Write-Output ([pscustomobject]@{
    output = $outputPath
    launcher = $launcherPath
    apworld = $apworldPath
    setup = $setupPath
    manifest = $manifestPath
    checksums = $checksumsPath
})
