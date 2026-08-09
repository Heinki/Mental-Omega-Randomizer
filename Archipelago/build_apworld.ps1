param(
    [string]$OutputDirectory = $PSScriptRoot
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$moduleName = "mental_omega"
$sourceDirectory = Join-Path $PSScriptRoot "APWorld\$moduleName"
$manifestPath = Join-Path $sourceDirectory "archipelago.json"

if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "APWorld manifest not found: $manifestPath"
}

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$outputPath = Join-Path $OutputDirectory "$moduleName.apworld"

# Archipelago's source-only Build APWorlds component normally injects these
# container compatibility fields. The frozen 0.6.7 release does not expose
# that component, so reproduce its APWorldContainer v7 manifest here.
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$manifest | Add-Member -NotePropertyName "compatible_version" -NotePropertyValue 7 -Force
$manifest | Add-Member -NotePropertyName "version" -NotePropertyValue 7 -Force
$manifest | Add-Member -NotePropertyName "maximum_ap_version" -NotePropertyValue "0.6.7" -Force
$manifestJson = $manifest | ConvertTo-Json -Depth 20 -Compress

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$fixedTimestamp = [DateTimeOffset]::new(
    2000, 1, 1, 0, 0, 0, [TimeSpan]::Zero
)

function Add-ArchiveFile {
    param(
        [System.IO.Compression.ZipArchive]$Archive,
        [string]$SourcePath,
        [string]$EntryName
    )
    $entry = $Archive.CreateEntry(
        $EntryName,
        [System.IO.Compression.CompressionLevel]::Optimal
    )
    $entry.LastWriteTime = $fixedTimestamp
    $inputStream = [System.IO.File]::OpenRead($SourcePath)
    $outputStream = $entry.Open()
    try {
        $inputStream.CopyTo($outputStream)
    }
    finally {
        $outputStream.Dispose()
        $inputStream.Dispose()
    }
}

if (Test-Path -LiteralPath $outputPath) {
    Remove-Item -LiteralPath $outputPath -Force
}

$archive = [System.IO.Compression.ZipFile]::Open(
    $outputPath,
    [System.IO.Compression.ZipArchiveMode]::Create
)

try {
    $sourcePrefix = $sourceDirectory.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    $files = Get-ChildItem -LiteralPath $sourceDirectory -File -Recurse |
        Where-Object {
            $_.Name -ne "archipelago.json" -and
            $_.Extension -ne ".pyc" -and
            $_.FullName -notmatch "[\\/]__pycache__[\\/]"
        } |
        Sort-Object {
            $_.FullName.Substring($sourcePrefix.Length).Replace('\', '/')
        }

    foreach ($file in $files) {
        $relativePath = $file.FullName.Substring($sourcePrefix.Length).Replace('\', '/')
        $entryName = "$moduleName/$relativePath"
        Add-ArchiveFile $archive $file.FullName $entryName
    }

    $manifestEntry = $archive.CreateEntry(
        "$moduleName/archipelago.json",
        [System.IO.Compression.CompressionLevel]::Optimal
    )
    $manifestEntry.LastWriteTime = $fixedTimestamp
    $stream = $manifestEntry.Open()
    $writer = [System.IO.StreamWriter]::new(
        $stream,
        [System.Text.UTF8Encoding]::new($false)
    )
    try {
        $writer.Write($manifestJson)
    }
    finally {
        $writer.Dispose()
        $stream.Dispose()
    }
}
finally {
    $archive.Dispose()
}

Write-Output $outputPath
