param(
    [string]$Output = "..\MentalOmegaRandomizer.exe"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = Join-Path $scriptDir "MentalOmegaRandomizerLauncher.cs"
$outputPath = Join-Path $scriptDir $Output

$candidates = @(
    "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
    "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe"
)

$csc = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $csc) {
    throw "Could not find csc.exe. Install .NET Framework Developer Pack or Visual Studio Build Tools."
}

& $csc /nologo /target:winexe /out:$outputPath /reference:System.Windows.Forms.dll $source
Write-Host "Built $outputPath"
