param(
    [string]$OutputDirectory = $PSScriptRoot
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$builder = Join-Path $PSScriptRoot "build_apworld.py"
$projectRoot = Split-Path -Parent $PSScriptRoot

Push-Location $projectRoot
try {
    & python $builder --output-directory $OutputDirectory
    if ($LASTEXITCODE -ne 0) {
        throw "APWorld build failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
