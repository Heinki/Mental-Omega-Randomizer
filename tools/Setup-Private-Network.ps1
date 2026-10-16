[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$Launcher = '',
    [switch]$Elevate
)

$ErrorActionPreference = 'Stop'
$gameRoot = [IO.Path]::GetFullPath($PSScriptRoot)
if (-not $Launcher) {
    $candidate = Get-ChildItem -LiteralPath $gameRoot -Filter 'MentalOmegaRandomizer*.exe' -File |
        Where-Object { $_.VersionInfo.ProductVersion -match '^\d+\.\d+(?:\.\d+){0,2}$' } |
        Sort-Object @{ Expression = { [Version]$_.VersionInfo.ProductVersion }; Descending = $true }, LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $candidate) {
        throw 'No Mental Omega Randomizer launcher was found in this game folder.'
    }
    $Launcher = $candidate.Name
}
$launcherPath = [IO.Path]::GetFullPath((Join-Path $gameRoot $Launcher))
if (-not [IO.Path]::GetDirectoryName($launcherPath).Equals(
    $gameRoot, [StringComparison]::OrdinalIgnoreCase
)) {
    throw 'The launcher must be an EXE inside this game folder.'
}
if ([IO.Path]::GetExtension($launcherPath) -ne '.exe') {
    throw 'The launcher filename must end in .exe.'
}
$engine = Join-Path $gameRoot 'gamemd.exe'
foreach ($requiredPath in @($launcherPath, $engine)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw 'Keep this script inside the extracted Mental Omega Challenges folder.'
    }
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
$isAdministrator = $principal.IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $WhatIfPreference -and -not $isAdministrator -and $Elevate) {
    $arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $PSCommandPath +
        '" -Launcher "' + $Launcher + '"'
    $setup = Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments `
        -Verb RunAs -WindowStyle Hidden -Wait -PassThru
    if ($setup.ExitCode -ne 0) {
        throw 'Network setup did not finish. See Setup-Private-Network.log in this game folder.'
    }
    Write-Host 'Private-network firewall setup completed.'
    return
}
if (-not $WhatIfPreference -and -not $isAdministrator) {
    throw 'Open Windows PowerShell as administrator, change to this game folder, and run: powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Setup-Private-Network.ps1'
}
if (-not $WhatIfPreference) {
    Start-Transcript -Path (Join-Path $gameRoot 'Setup-Private-Network.log') -Append | Out-Null
}
$adapters = @(Get-NetAdapter -IncludeHidden | Where-Object {
    $_.InterfaceDescription -match 'ZeroTier|Tailscale' -or
    $_.Name -match '^ZeroTier|^Tailscale$'
})
if ($adapters.Count -eq 0) {
    throw 'Connect ZeroTier or Tailscale first, then run this script again. No firewall rules were changed.'
}
$aliases = @($adapters | Select-Object -ExpandProperty Name -Unique)

$hasher = [Security.Cryptography.SHA256]::Create()
try {
    $digest = $hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($gameRoot.ToLowerInvariant()))
    $folderId = ([BitConverter]::ToString($digest)).Replace('-', '').Substring(0, 12)
} finally {
    $hasher.Dispose()
}
$group = 'Mental Omega Challenges private network'
$definitions = @(
    @{ Suffix = 'lobby'; Label = 'Lobby and preparation'; Program = $launcherPath; Protocol = 'TCP'; Ports = @(19420, 19421) },
    @{ Suffix = 'game'; Label = 'Game'; Program = $engine; Protocol = 'UDP'; Ports = @(1234) }
)
foreach ($definition in $definitions) {
    $name = 'MORChallenges-' + $folderId + '-' + $definition.Suffix
    $parameters = @{
        Name = $name
        Enabled = 'True'
        Direction = 'Inbound'
        Action = 'Allow'
        Profile = @('Private', 'Public')
        InterfaceAlias = $aliases
        Program = $definition.Program
        Protocol = $definition.Protocol
        LocalPort = $definition.Ports
        RemoteAddress = 'Any'
        EdgeTraversalPolicy = 'Block'
    }
    if ($PSCmdlet.ShouldProcess($definition.Label, 'Allow game traffic on private VPN adapters')) {
        $existing = Get-NetFirewallRule -Name $name -ErrorAction SilentlyContinue
        if ($existing) {
            Set-NetFirewallRule @parameters | Out-Null
        } else {
            New-NetFirewallRule @parameters -DisplayName (
                'Mental Omega Challenges - ' + $definition.Label
            ) -Group $group | Out-Null
        }
    }
}
if ($WhatIfPreference) {
    Write-Host 'Preview complete. No firewall rules were changed.'
} else {
    Write-Host ('Game firewall setup complete, restricted to ' + $aliases.Count + ' private VPN adapter(s).')
}
Write-Host 'Host lobby/preparation: TCP 19420 and 19421. Game on both PCs: UDP 1234.'
Write-Host 'Run this again if you move the game folder or install another private VPN.'
if (-not $WhatIfPreference) { Stop-Transcript | Out-Null }
