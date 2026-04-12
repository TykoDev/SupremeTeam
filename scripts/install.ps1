[CmdletBinding()]
param(
    [ValidateSet("All", "Design", "Build", "Review", "Azure")]
    [string[]]$Team = @("All"),

    [string]$Destination = (Join-Path $env:USERPROFILE ".agents\skills"),

    [switch]$InstallClaude,

    [string]$ClaudeDestination = (Join-Path $env:USERPROFILE ".claude\skills")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path $PSScriptRoot -Parent
$sourceRoot = Join-Path $repoRoot "skills"

$coreItems = @(
    "admiral",
    "gatekeeper-admiral",
    "references",
    "save-protocol.md"
)

$teamDirectories = @{
    design = "design"
    build = "build"
    review = "review"
    azure = "azure"
}

$allTeamNames = @("design", "build", "review", "azure")
$managedItems = $coreItems + @("design", "build", "review", "azure")

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

    foreach ($item in $managedItems) {
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

    Assert-PathPresent -Path (Join-Path $sourceRoot "design\tech-stacks") -Description "design tech-stack directory"
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

    if ($SelectedTeams -contains "design") {
        Assert-PathPresent -Path (Join-Path $TargetRoot "design\tech-stacks") -Description "installed design tech-stack directory"
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

try {
    Assert-SourceLayout

    $selectedTeams = Resolve-TeamSelection -RequestedTeams $Team

    Write-Host "Installing Supreme Team to $Destination"
    Install-SupremeTeam -TargetRoot $Destination -SelectedTeams $selectedTeams

    if ($InstallClaude) {
        Write-Host "Mirroring Supreme Team to $ClaudeDestination"
        Install-SupremeTeam -TargetRoot $ClaudeDestination -SelectedTeams $selectedTeams
    }

    $claudeStatus = if ($InstallClaude) { $ClaudeDestination } else { "not requested" }

    Write-Host ""
    Write-Host "Supreme Team installation complete."
    Write-Host "Target: $Destination"
    Write-Host "Teams: $(Format-TeamList -SelectedTeams $selectedTeams)"
    Write-Host "Claude mirror: $claudeStatus"
    Write-Host "Restart your assistant session if it was already running."
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}