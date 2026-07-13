param(
    [string]$Output = "..\MentalOmegaRandomizer.exe"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$outputPath = [IO.Path]::GetFullPath((Join-Path $scriptDir $Output))
$outputDir = Split-Path -Parent $outputPath
$runtimeName = "RandomizerLauncherRuntime"
$runtimePath = Join-Path $outputDir $runtimeName
$distDir = Join-Path $scriptDir "dist"
$workDir = Join-Path $scriptDir "build"

if (-not (python -m PyInstaller --version 2>$null)) {
    throw "PyInstaller is required. Install it with: python -m pip install pyinstaller"
}

python -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --contents-directory $runtimeName `
    --windowed `
    --name MentalOmegaRandomizer `
    --distpath $distDir `
    --workpath $workDir `
    --specpath $workDir `
    (Join-Path $scriptDir "launcher_gui.py")

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE."
}

$bundleDir = Join-Path $distDir "MentalOmegaRandomizer"
Copy-Item -Force (Join-Path $bundleDir "MentalOmegaRandomizer.exe") $outputPath
if (Test-Path $runtimePath) {
    Remove-Item -LiteralPath $runtimePath -Recurse -Force
}
Copy-Item -Recurse -Force (Join-Path $bundleDir $runtimeName) $runtimePath
Write-Host "Built $outputPath with adjacent runtime folder $runtimePath"
