param(
    [string]$Output = "..\MentalOmegaRandomizer.exe"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$outputPath = [IO.Path]::GetFullPath((Join-Path $scriptDir $Output))
$outputDir = Split-Path -Parent $outputPath
$runtimePath = [IO.Path]::GetFullPath((Join-Path $outputDir "RandomizerLauncherRuntime"))
$distDir = Join-Path $scriptDir "dist"
$workDir = Join-Path $scriptDir "build"
$iconPath = Join-Path $scriptDir "mo-logo-puzzle-icon.ico"

New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

if (-not (python -m PyInstaller --version 2>$null)) {
    throw "PyInstaller is required. Install build dependencies with: python -m pip install -r requirements-build.txt"
}
if (-not (Test-Path -LiteralPath $iconPath -PathType Leaf)) {
    throw "Launcher icon is missing: $iconPath"
}

# The standalone launcher has no network client. Remove the network-related
# exclusions below when Archipelago connectivity is implemented.
python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --optimize 1 `
    --windowed `
    --icon $iconPath `
    --exclude-module logging.handlers `
    --exclude-module ssl `
    --exclude-module _ssl `
    --exclude-module http `
    --exclude-module urllib.request `
    --exclude-module urllib.error `
    --exclude-module ftplib `
    --exclude-module smtplib `
    --exclude-module email `
    --exclude-module hashlib `
    --exclude-module _hashlib `
    --name MentalOmegaRandomizer `
    --distpath $distDir `
    --workpath $workDir `
    --specpath $workDir `
    (Join-Path $scriptDir "launcher_gui.py")

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE."
}

$builtExe = Join-Path $distDir "MentalOmegaRandomizer.exe"
Copy-Item -Force $builtExe $outputPath

# Remove the support folder created by older on-directory builds. Guard the
# resolved path because this is the only recursive deletion in the build.
if (Test-Path $runtimePath) {
    $expectedParent = [IO.Path]::GetFullPath($outputDir).TrimEnd('\') + '\'
    if (
        -not $runtimePath.StartsWith($expectedParent, [StringComparison]::OrdinalIgnoreCase) -or
        [IO.Path]::GetFileName($runtimePath) -ne 'RandomizerLauncherRuntime'
    ) {
        throw "Refusing to remove unexpected runtime path: $runtimePath"
    }
    Remove-Item -LiteralPath $runtimePath -Recurse -Force
}
Write-Host "Built single-file launcher $outputPath"
