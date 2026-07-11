param(
    [string]$Output = "..\MentalOmegaRandomizer.exe"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$outputPath = [IO.Path]::GetFullPath((Join-Path $scriptDir $Output))
$distDir = Join-Path $scriptDir "dist"
$workDir = Join-Path $scriptDir "build"

if (-not (python -m PyInstaller --version 2>$null)) {
    throw "PyInstaller is required. Install it with: python -m pip install pyinstaller"
}

python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name MentalOmegaRandomizer `
    --distpath $distDir `
    --workpath $workDir `
    --specpath $workDir `
    (Join-Path $scriptDir "launcher_gui.py")

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE."
}

Copy-Item -Force (Join-Path $distDir "MentalOmegaRandomizer.exe") $outputPath
Write-Host "Built $outputPath"
