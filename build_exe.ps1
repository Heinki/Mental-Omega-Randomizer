param(
    [string]$Output = "..\MentalOmegaRandomizer.exe"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$outputPath = if ([IO.Path]::IsPathRooted($Output)) {
    [IO.Path]::GetFullPath($Output)
} else {
    [IO.Path]::GetFullPath((Join-Path $scriptDir $Output))
}
$outputDir = Split-Path -Parent $outputPath
$runtimePath = [IO.Path]::GetFullPath((Join-Path $outputDir "RandomizerLauncherRuntime"))
$distDir = Join-Path $scriptDir "dist"
$workDir = Join-Path $scriptDir "build"
$iconPath = Join-Path $scriptDir "mo-logo-puzzle-icon.ico"
$staticConfigPath = Join-Path $scriptDir "configs"
$assetPath = Join-Path $scriptDir "assets"
$tkRuntimeHook = Join-Path $scriptDir "tools\pyinstaller_tk_runtime.py"
$versionInfoPath = Join-Path ([IO.Path]::GetTempPath()) "MentalOmegaRandomizer-$PID-version.txt"
$configManifestDir = Join-Path ([IO.Path]::GetTempPath()) "MentalOmegaRandomizer-$PID-config"
$configManifestPath = Join-Path $configManifestDir "bundle_manifest.json"
$tclBundleData = Join-Path $configManifestDir "_tcl_data"

New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

$requiredPythonVersion = '3.14.6'
$pythonVersion = (& python -c "import platform; print(platform.python_version())" 2>$null).Trim()
if ($LASTEXITCODE -ne 0 -or $pythonVersion -ne $requiredPythonVersion) {
    throw (
        "Python $requiredPythonVersion is required for reproducible launcher builds; " +
        "found $pythonVersion."
    )
}
if (-not (python -m PyInstaller --version 2>$null)) {
    throw "PyInstaller is required. Install build dependencies with: python -m pip install -r requirements-build.txt"
}
$websocketsVersion = (& python -c "import websockets; print(websockets.__version__)" 2>$null).Trim()
if ($LASTEXITCODE -ne 0 -or $websocketsVersion -ne '17.0') {
    throw "websockets 17.0 is required. Install build dependencies with: python -m pip install -r requirements-build.txt"
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

# PyInstaller's Tcl/Tk probe can reject otherwise working Python 3.14 installs.
# Bundle the verified runtime explicitly so windowed builds remain reproducible.
$pythonRoot = (& python -c "import sys; print(sys.base_prefix)").Trim()
$tkinterBinary = Join-Path $pythonRoot "DLLs\_tkinter.pyd"
$tkinterPackage = Join-Path $pythonRoot "Lib\tkinter"
$tclBinary = Join-Path $pythonRoot "DLLs\tcl86t.dll"
$tkBinary = Join-Path $pythonRoot "DLLs\tk86t.dll"
$tclData = Join-Path $pythonRoot "tcl\tcl8.6"
$tkData = Join-Path $pythonRoot "tcl\tk8.6"
foreach ($tkRuntimePath in @(
    $tkinterBinary, $tkinterPackage, $tclBinary, $tkBinary, $tclData, $tkData,
    $tkRuntimeHook
)) {
    if (-not (Test-Path -LiteralPath $tkRuntimePath)) {
        throw "Required Tcl/Tk runtime path is missing: $tkRuntimePath"
    }
}

python -m compileall -q -f `
    (Join-Path $scriptDir "launcher_gui.py") `
    (Join-Path $scriptDir "randomizer")
if ($LASTEXITCODE -ne 0) {
    throw "Source bytecode refresh failed; EXE was not built."
}

python -c "from randomizer.config.static import REQUIRED_STATIC_CONFIGS, validate_static_configs; validate_static_configs(REQUIRED_STATIC_CONFIGS); print('Static config preflight passed.')"
if ($LASTEXITCODE -ne 0) {
    throw "Static config preflight failed; EXE was not built."
}

$appVersion = (& python -c "from randomizer.core.version import APP_VERSION; print(APP_VERSION)").Trim()
if ($LASTEXITCODE -ne 0 -or $appVersion -notmatch '^\d+\.\d+(\.\d+)?$') {
    throw "Invalid APP_VERSION in randomizer/core/version.py: $appVersion"
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

$manifestFiles = [ordered]@{}
$staticConfigPrefix = [IO.Path]::GetFullPath($staticConfigPath).TrimEnd('\') + '\'
Get-ChildItem -LiteralPath $staticConfigPath -Recurse -File |
    Where-Object {
        ($_.Extension -eq '.json' -or $_.Name -like 'Randomizer*.ini') -and
        $_.FullName -notlike "$staticConfigPath\player\*"
    } |
    Sort-Object FullName |
    ForEach-Object {
        $fullConfigPath = [IO.Path]::GetFullPath($_.FullName)
        if (-not $fullConfigPath.StartsWith(
            $staticConfigPrefix,
            [StringComparison]::OrdinalIgnoreCase
        )) {
            throw "Refusing config outside source root: $fullConfigPath"
        }
        $relativePath = $fullConfigPath.Substring(
            $staticConfigPrefix.Length
        ).Replace('\', '/')
        $manifestFiles[$relativePath] = (
            Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
        ).Hash.ToLowerInvariant()
    }
$configManifest = [ordered]@{
    format = 1
    files = $manifestFiles
} | ConvertTo-Json -Depth 4
New-Item -ItemType Directory -Path $configManifestDir -Force | Out-Null
[IO.File]::WriteAllText(
    $configManifestPath,
    $configManifest,
    [Text.UTF8Encoding]::new($false)
)

# Tcl 8.6.15 can source init.tcl before defining ::tcl_library in this pinned
# embedded runtime. Bundle a tiny wrapper and keep the unmodified stock script
# beside it. The installed Python runtime is never edited.
Copy-Item -LiteralPath $tclData -Destination $tclBundleData -Recurse
$bundledInit = Join-Path $tclBundleData 'init.tcl'
$bundledOriginalInit = Join-Path $tclBundleData '_mor_original_init.tcl'
Move-Item -LiteralPath $bundledInit -Destination $bundledOriginalInit
$tclBootstrap = @'
# Mental Omega Randomizer bundled Tcl bootstrap
set ::tcl_library [file dirname [info script]]
source [file join $::tcl_library _mor_original_init.tcl]
'@
[IO.File]::WriteAllText(
    $bundledInit,
    $tclBootstrap,
    [Text.UTF8Encoding]::new($false)
)

# Archipelago uses compressed ws/wss connections. Keep SSL, HTTP, and email
# available for the bundled websockets handshake implementation.
try {
    python -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --runtime-tmpdir . `
        --noupx `
        --optimize 1 `
        --windowed `
        --icon $iconPath `
        --version-file $versionInfoPath `
        --add-data "$iconPath;." `
        --add-data "$staticConfigPath\*.json;configs" `
        --add-data "$staticConfigPath\*.ini;configs" `
        --add-data "$staticConfigPath\README.md;configs" `
        --add-data "$staticConfigPath\rewards;configs\rewards" `
        --add-data "$configManifestPath;configs" `
        --add-data "$assetPath;assets" `
        --add-binary "$tkinterBinary;." `
        --add-data "$tkinterPackage;tkinter" `
        --add-binary "$tclBinary;." `
        --add-binary "$tkBinary;." `
        --add-data "$tclBundleData;_tcl_data" `
        --add-data "$tkData;_tk_data" `
        --runtime-hook $tkRuntimeHook `
        --exclude-module logging.handlers `
        --exclude-module ftplib `
        --exclude-module smtplib `
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
    Remove-Item -LiteralPath $configManifestPath -Force -ErrorAction SilentlyContinue
    $resolvedManifestDir = [IO.Path]::GetFullPath($configManifestDir)
    $resolvedTempRoot = [IO.Path]::GetFullPath(
        [IO.Path]::GetTempPath()
    ).TrimEnd('\') + '\'
    if (
        -not $resolvedManifestDir.StartsWith(
            $resolvedTempRoot,
            [StringComparison]::OrdinalIgnoreCase
        ) -or
        [IO.Path]::GetFileName($resolvedManifestDir) -ne (
            "MentalOmegaRandomizer-$PID-config"
        )
    ) {
        throw "Refusing to remove unexpected build staging path: $resolvedManifestDir"
    }
    Remove-Item -LiteralPath $resolvedManifestDir -Recurse -Force `
        -ErrorAction SilentlyContinue
}

$builtExe = Join-Path $distDir "MentalOmegaRandomizer.exe"
$archiveListing = @(
    & python -m PyInstaller.utils.cliutils.archive_viewer -l $builtExe 2>&1
)
if ($LASTEXITCODE -ne 0) {
    throw "Unable to inspect built PyInstaller archive: $builtExe"
}
$archiveText = $archiveListing -join "`n"
$requiredArchiveEntries = @(
    "'_tkinter.pyd'",
    "'tcl86t.dll'",
    "'tk86t.dll'",
    "'_tcl_data\\init.tcl'",
    "'_tk_data\\tk.tcl'"
)
$missingArchiveEntries = @(
    $requiredArchiveEntries | Where-Object { -not $archiveText.Contains($_) }
)
if ($missingArchiveEntries.Count -gt 0) {
    throw (
        "Built launcher is missing required Tcl/Tk archive entries: " +
        ($missingArchiveEntries -join ', ')
    )
}
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
Write-Host (
    "Built single-file launcher v$appVersion with Python $pythonVersion " +
    "and verified Tcl/Tk runtime: $outputPath"
)
