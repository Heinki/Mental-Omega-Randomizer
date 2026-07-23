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
$staticConfigPath = Join-Path $scriptDir "configs"
$assetPath = Join-Path $scriptDir "assets"
$versionInfoPath = Join-Path ([IO.Path]::GetTempPath()) "MentalOmegaRandomizer-$PID-version.txt"

New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

if (-not (python -m PyInstaller --version 2>$null)) {
    throw "PyInstaller is required. Install build dependencies with: python -m pip install -r requirements-build.txt"
}
if (-not (Test-Path -LiteralPath $iconPath -PathType Leaf)) {
    throw "Launcher icon is missing: $iconPath"
}
if (-not (Test-Path -LiteralPath $staticConfigPath -PathType Container)) {
    throw "Static config directory is missing: $staticConfigPath"
}
if (-not (Test-Path -LiteralPath $assetPath -PathType Container)) {
    throw "Launcher asset directory is missing: $assetPath"
}

python -c "from randomizer_static_config import REQUIRED_STATIC_CONFIGS, validate_static_configs; validate_static_configs(REQUIRED_STATIC_CONFIGS); print('Static config preflight passed.')"
if ($LASTEXITCODE -ne 0) {
    throw "Static config preflight failed; EXE was not built."
}

$appVersion = (& python -c "from randomizer_version import APP_VERSION; print(APP_VERSION)").Trim()
if ($LASTEXITCODE -ne 0 -or $appVersion -notmatch '^\d+\.\d+(\.\d+)?$') {
    throw "Invalid APP_VERSION in randomizer_version.py: $appVersion"
}
$versionParts = @($appVersion.Split('.') | ForEach-Object { [int]$_ })
while ($versionParts.Count -lt 4) {
    $versionParts += 0
}
$versionTuple = $versionParts -join ', '
$versionInfo = @"
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($versionTuple),
    prodvers=($versionTuple),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [
          StringStruct(u'CompanyName', u'Mental Omega Randomizer contributors'),
          StringStruct(u'FileDescription', u'Mental Omega Randomizer Launcher'),
          StringStruct(u'FileVersion', u'$appVersion'),
          StringStruct(u'InternalName', u'MentalOmegaRandomizer'),
          StringStruct(u'OriginalFilename', u'MentalOmegaRandomizer.exe'),
          StringStruct(u'ProductName', u'Mental Omega Randomizer Launcher'),
          StringStruct(u'ProductVersion', u'$appVersion')
        ]
      )
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"@
[IO.File]::WriteAllText($versionInfoPath, $versionInfo, [Text.UTF8Encoding]::new($false))

# The standalone launcher has no network client. Remove the network-related
# exclusions below when Archipelago connectivity is implemented.
try {
    python -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --noupx `
        --optimize 1 `
        --windowed `
        --icon $iconPath `
        --version-file $versionInfoPath `
        --add-data "$iconPath;." `
        --add-data "$staticConfigPath;configs" `
        --add-data "$assetPath;assets" `
        --exclude-module logging.handlers `
        --exclude-module ssl `
        --exclude-module _ssl `
        --exclude-module http `
        --exclude-module urllib.request `
        --exclude-module urllib.error `
        --exclude-module ftplib `
        --exclude-module smtplib `
        --exclude-module email `
        --name MentalOmegaRandomizer `
        --distpath $distDir `
        --workpath $workDir `
        --specpath $workDir `
        (Join-Path $scriptDir "launcher_gui.py")

    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed with exit code $LASTEXITCODE."
    }
} finally {
    Remove-Item -LiteralPath $versionInfoPath -Force -ErrorAction SilentlyContinue
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
Write-Host "Built single-file launcher v$appVersion $outputPath"
