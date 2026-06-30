[CmdletBinding()]
param(
    [ValidateSet("All", "Design", "Build", "Review", "Browser", "Release", "Safety", "Testing")]
    [string[]]$Team = @("All"),

    [ValidateSet("Auto", "Codex", "Claude", "Cursor", "OpenCode")]
    [string[]]$Target = @("Auto"),

    [string]$Destination = (Join-Path $env:USERPROFILE ".agents\skills"),

    [string]$CodexDestination = (Join-Path $env:USERPROFILE ".codex\skills"),

    [switch]$RegisterHooks,

    [switch]$InstallClaude,

    [string]$ClaudeDestination = (Join-Path $env:USERPROFILE ".claude\skills"),

    [string]$CursorDestination = (Join-Path $env:USERPROFILE ".cursor\skills"),

    [string]$OpenCodeDestination = (Join-Path $env:USERPROFILE ".config\opencode\skills")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path $PSScriptRoot -Parent
$sourceRoot = Join-Path $repoRoot "skills"

# Core components are always installed. They contain the Admiral pipeline spine
# (entry orchestrator, cross-stage gate, memory, investigation, skill-maker), the
# runtime harness (hooks + deterministic gate engine), and the root doctrine and
# protocol files every skill resolves by relative path.
$coreItems = @(
    "admiral",
    "gatekeeper-admiral",
    "session-memory",
    "investigate",
    "skill-maker",
    "harness",
    "design-doctrine.md",
    "grill-me-doctrine.md",
    "harness-doctrine.md",
    "mcp-tools.md",
    "routing-doctrine.md",
    "save-protocol.md"
)

# Friendly team name -> source directory under skills/.
$teamDirectories = @{
    design  = "design"
    build   = "build"
    review  = "review"
    browser = "browser-automation"
    release = "release-and-deployment"
    safety  = "safety-guardrails"
    testing = "testing-and-qa"
}

$allTeamNames = @("design", "build", "review", "browser", "release", "safety", "testing")
$managedItems = $coreItems + ($allTeamNames | ForEach-Object { $teamDirectories[$_] })

# Paths from older Supreme Team layouts that are no longer shipped. Removed from
# the destination on each run so an in-place update over an old install does not
# leave stale directories behind. Not part of the source-layout assertion.
$legacyItems = @("azure", "references", "design\tech-stacks")

function Assert-PathPresent {
    param(
        [string]$Path,
        [string]$Description
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Missing $Description at '$Path'."
    }
}

function Resolve-TeamSelection {
    param([string[]]$RequestedTeams)

    $resolved = @()

    foreach ($requestedTeam in $RequestedTeams) {
        if ($requestedTeam -eq "All") {
            foreach ($teamName in $allTeamNames) {
                if ($resolved -notcontains $teamName) {
                    $resolved += $teamName
                }
            }

            continue
        }

        $normalized = $requestedTeam.ToLowerInvariant()

        if ($resolved -notcontains $normalized) {
            $resolved += $normalized
        }
    }

    return $resolved
}

function Clear-InstallDestination {
    param([string]$TargetRoot)

    New-Item -ItemType Directory -Force -Path $TargetRoot | Out-Null

    foreach ($item in ($managedItems + $legacyItems)) {
        $targetPath = Join-Path $TargetRoot $item

        if (-not (Test-Path -LiteralPath $targetPath)) {
            continue
        }

        $targetItem = Get-Item -LiteralPath $targetPath

        if ($targetItem.PSIsContainer) {
            Remove-Item -LiteralPath $targetPath -Recurse -Force
        }
        else {
            Remove-Item -LiteralPath $targetPath -Force
        }
    }
}

function Copy-SourceItem {
    param(
        [string]$ItemName,
        [string]$TargetRoot
    )

    $sourcePath = Join-Path $sourceRoot $ItemName
    $sourceItem = Get-Item -LiteralPath $sourcePath

    if ($sourceItem.PSIsContainer) {
        Copy-Item -LiteralPath $sourcePath -Destination $TargetRoot -Recurse -Force
    }
    else {
        Copy-Item -LiteralPath $sourcePath -Destination $TargetRoot -Force
    }
}

function Assert-SourceLayout {
    Assert-PathPresent -Path $sourceRoot -Description "skills source directory"

    foreach ($item in $coreItems) {
        Assert-PathPresent -Path (Join-Path $sourceRoot $item) -Description "source item '$item'"
    }

    foreach ($teamName in $allTeamNames) {
        Assert-PathPresent -Path (Join-Path $sourceRoot $teamDirectories[$teamName]) -Description "source team '$teamName'"
    }
}

function Assert-DestinationLayout {
    param(
        [string]$TargetRoot,
        [string[]]$SelectedTeams
    )

    foreach ($item in $coreItems) {
        Assert-PathPresent -Path (Join-Path $TargetRoot $item) -Description "installed item '$item'"
    }

    foreach ($teamName in $SelectedTeams) {
        Assert-PathPresent -Path (Join-Path $TargetRoot $teamDirectories[$teamName]) -Description "installed team '$teamName'"
    }
}

function Install-SupremeTeam {
    param(
        [string]$TargetRoot,
        [string[]]$SelectedTeams
    )

    Clear-InstallDestination -TargetRoot $TargetRoot

    foreach ($item in $coreItems) {
        Copy-SourceItem -ItemName $item -TargetRoot $TargetRoot
    }

    foreach ($teamName in $SelectedTeams) {
        Copy-SourceItem -ItemName $teamDirectories[$teamName] -TargetRoot $TargetRoot
    }

    Assert-DestinationLayout -TargetRoot $TargetRoot -SelectedTeams $SelectedTeams
}

function Format-TeamList {
    param([string[]]$SelectedTeams)

    return ($SelectedTeams | ForEach-Object {
        $_.Substring(0, 1).ToUpperInvariant() + $_.Substring(1)
    }) -join ", "
}

function Add-UniqueValue {
    param(
        [string[]]$Values,
        [string]$Value
    )

    if ($Values -notcontains $Value) {
        return @($Values + $Value)
    }

    return $Values
}

function Test-SupremeTeamInstallPresent {
    param([string]$TargetRoot)

    foreach ($item in ($managedItems + $legacyItems)) {
        if (Test-Path -LiteralPath (Join-Path $TargetRoot $item)) {
            return $true
        }
    }

    return $false
}

function Test-CommandAvailable {
    param([string]$Name)

    try {
        return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
    }
    catch {
        return $false
    }
}

function Test-PythonMinimumVersion {
    param(
        [string]$Command,
        [string[]]$Arguments = @()
    )

    try {
        & $Command @Arguments -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 13) else 1)" *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Find-CompatiblePythonCommand {
    $candidates = @(
        @{ Command = "py"; Arguments = @("-3.13") },
        @{ Command = "python"; Arguments = @() },
        @{ Command = "python3"; Arguments = @() }
    )

    foreach ($candidate in $candidates) {
        if (-not (Test-CommandAvailable -Name $candidate.Command)) {
            continue
        }

        if (Test-PythonMinimumVersion -Command $candidate.Command -Arguments $candidate.Arguments) {
            return [pscustomobject]$candidate
        }
    }

    return $null
}

function Write-PythonReadinessWarning {
    if ($null -eq (Find-CompatiblePythonCommand)) {
        Write-Warning "Python 3.13+ was not found. Skill files will still be copied, but hook verification and registration require Python 3.13 or newer."
    }
}

function Test-HostDetected {
    param([string]$HostName)

    switch ($HostName) {
        "codex" {
            return (Test-CommandAvailable -Name "codex") -or
                (Test-Path -LiteralPath (Join-Path $env:USERPROFILE ".codex"))
        }
        "claude" {
            return (Test-CommandAvailable -Name "claude") -or
                (Test-Path -LiteralPath (Join-Path $env:USERPROFILE ".claude"))
        }
        "cursor" {
            return (Test-CommandAvailable -Name "cursor") -or
                (Test-Path -LiteralPath (Join-Path $env:USERPROFILE ".cursor")) -or
                (Test-Path -LiteralPath (Join-Path $env:APPDATA "Cursor"))
        }
        "opencode" {
            return (Test-CommandAvailable -Name "opencode") -or
                (Test-Path -LiteralPath (Join-Path $env:USERPROFILE ".config\opencode")) -or
                (Test-Path -LiteralPath (Join-Path $env:APPDATA "opencode"))
        }
        default {
            return $false
        }
    }
}

function Resolve-HostTargets {
    param([string[]]$RequestedTargets)

    $resolved = @()
    $normalizedTargets = $RequestedTargets | ForEach-Object { $_.ToLowerInvariant() }

    if ($normalizedTargets -contains "auto") {
        foreach ($hostName in @("codex", "claude", "cursor", "opencode")) {
            if (Test-HostDetected -HostName $hostName) {
                $resolved = Add-UniqueValue -Values $resolved -Value $hostName
            }
        }
    }

    foreach ($targetName in $normalizedTargets) {
        if ($targetName -eq "auto") {
            continue
        }

        $resolved = Add-UniqueValue -Values $resolved -Value $targetName
    }

    if ($InstallClaude) {
        $resolved = Add-UniqueValue -Values $resolved -Value "claude"
    }

    return $resolved
}

function Find-PythonCommand {
    $candidate = Find-CompatiblePythonCommand
    if ($null -eq $candidate) {
        throw "Python 3.13 or newer is required to register runtime harness hooks."
    }

    return $candidate
}

function Register-HarnessHooks {
    param(
        [string[]]$HostTargets,
        [string]$HookRoot
    )

    if ($HostTargets.Count -eq 0) {
        Write-Host "Hook registration skipped: no host targets were detected. Pass -Target Codex,Claude,Cursor,OpenCode to choose explicitly."
        return
    }

    $helper = Join-Path $repoRoot "scripts\install_hooks.py"
    Assert-PathPresent -Path $helper -Description "hook registration helper"

    $python = Find-PythonCommand
    $hookArgs = @($helper, "--hook-root", $HookRoot)
    foreach ($hostName in $HostTargets) {
        $hookArgs += @("--target", $hostName)
    }

    $pythonArgs = @($python.Arguments)
    & $python.Command @pythonArgs @hookArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Hook registration failed."
    }
}

try {
    Assert-SourceLayout

    $selectedTeams = Resolve-TeamSelection -RequestedTeams $Team
    $hostTargets = @(Resolve-HostTargets -RequestedTargets $Target)
    $normalizedRequestedTargets = @($Target | ForEach-Object { $_.ToLowerInvariant() })
    $explicitCodexTarget = $normalizedRequestedTargets -contains "codex"
    $explicitCursorTarget = $normalizedRequestedTargets -contains "cursor"
    Write-PythonReadinessWarning

    Write-Host "Installing Supreme Team to $Destination"
    Install-SupremeTeam -TargetRoot $Destination -SelectedTeams $selectedTeams

    $mirrorSummaries = @()

    if (($hostTargets -contains "codex") -and ($explicitCodexTarget -or (Test-SupremeTeamInstallPresent -TargetRoot $CodexDestination))) {
        Write-Host "Mirroring Supreme Team to $CodexDestination"
        Install-SupremeTeam -TargetRoot $CodexDestination -SelectedTeams $selectedTeams
        $mirrorSummaries += "codex=$CodexDestination"
    }

    if ($hostTargets -contains "claude") {
        Write-Host "Mirroring Supreme Team to $ClaudeDestination"
        Install-SupremeTeam -TargetRoot $ClaudeDestination -SelectedTeams $selectedTeams
        $mirrorSummaries += "claude=$ClaudeDestination"
    }

    if (($hostTargets -contains "cursor") -and ($explicitCursorTarget -or (Test-SupremeTeamInstallPresent -TargetRoot $CursorDestination))) {
        Write-Host "Mirroring Supreme Team to $CursorDestination"
        Install-SupremeTeam -TargetRoot $CursorDestination -SelectedTeams $selectedTeams
        $mirrorSummaries += "cursor=$CursorDestination"
    }

    if ($hostTargets -contains "opencode") {
        Write-Host "Mirroring Supreme Team to $OpenCodeDestination"
        Install-SupremeTeam -TargetRoot $OpenCodeDestination -SelectedTeams $selectedTeams
        $mirrorSummaries += "opencode=$OpenCodeDestination"
    }

    if ($RegisterHooks) {
        Register-HarnessHooks -HostTargets $hostTargets -HookRoot (Join-Path $Destination "harness\hooks")
    }

    $mirrorStatus = if ($mirrorSummaries.Count -gt 0) { $mirrorSummaries -join "; " } else { "none" }
    $hookStatus = if ($RegisterHooks) { "requested" } else { "not requested" }
    $hostStatus = if ($hostTargets.Count -gt 0) { $hostTargets -join ", " } else { "none detected" }

    Write-Host ""
    Write-Host "Supreme Team installation complete."
    Write-Host "Target: $Destination"
    Write-Host "Host targets: $hostStatus"
    Write-Host "Host mirrors: $mirrorStatus"
    Write-Host "Teams: $(Format-TeamList -SelectedTeams $selectedTeams)"
    Write-Host "Hook registration: $hookStatus"
    Write-Host "Restart your assistant session if it was already running."
    if (-not $RegisterHooks) {
        Write-Host "Run again with -RegisterHooks to register runtime harness hooks for the selected hosts."
    }
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
