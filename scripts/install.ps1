[CmdletBinding()]
param(
    [ValidateSet("All", "Design", "Build", "Review", "Browser", "Release", "Safety", "Testing")]
    [string[]]$Team = @("All"),

    [ValidateSet("Auto", "Codex", "Claude", "Cursor", "OpenCode", "Copilot")]
    [string[]]$Target = @("Auto"),

    [string]$Destination = (Join-Path $env:USERPROFILE ".agents\skills"),

    [string]$CodexDestination = (Join-Path $env:USERPROFILE ".codex\skills"),

    [switch]$RegisterHooks,

    [ValidateSet("User", "Project", "Local")]
    [string]$HooksScope = "User",

    [switch]$HooksYes,

    [switch]$InstallClaude,

    [string]$ClaudeDestination = (Join-Path $env:USERPROFILE ".claude\skills"),

    [string]$CursorDestination = (Join-Path $env:USERPROFILE ".cursor\skills"),

    [string]$OpenCodeDestination = (Join-Path $env:USERPROFILE ".config\opencode\skills"),

    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path $PSScriptRoot -Parent
$sourceRoot = Join-Path $repoRoot "skills"
$itemsFile = Join-Path $PSScriptRoot "install-items.txt"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

# The installer only replaces or removes what it can show it installed. Every
# install root gets a manifest listing the items the last run put there, and
# every directory it creates carries a marker file. A file is owned when the
# manifest lists it and a directory when it carries the marker. Anything else
# that shares a managed name is moved to a backup folder, never deleted.
$manifestName = ".supremeteam-manifest"
$manifestHeader = "supremeteam-manifest 1"
$markerName = ".supremeteam-managed"
$stageMarkerName = ".supremeteam-stage"

# install-items.txt is the one item list; install.sh reads the same file.
$script:coreItems = @()
$script:seedItems = @()
$script:supersededItems = [ordered]@{}
$script:teamItems = [ordered]@{}
$script:legacyItems = [ordered]@{}
$script:allTeamNames = @()
$script:managedItems = @()
$script:oldItems = @()
$script:backupDirs = @()
$script:manifestForeign = $false
$script:stage = ""
$script:stageRoot = ""
$script:stageCommitted = $false
$script:backupDir = ""
$script:hooksDeclined = $false
$script:hooksFailed = 0

# Names become path components, so they are checked before any path is built
# from them: no separators, no leading dot or dash, nothing a wildcard would match.
function Test-ValidName {
    param([string]$Name)

    return $Name -match '^[A-Za-z0-9_][A-Za-z0-9._-]*$'
}

function Import-ItemList {
    if (-not (Test-Path -LiteralPath $itemsFile -PathType Leaf)) {
        throw "Missing item list at '$itemsFile'."
    }

    foreach ($line in (Get-Content -LiteralPath $itemsFile)) {
        $text = $line.Trim()
        if ($text -eq "" -or $text.StartsWith("#")) {
            continue
        }

        $fields = @($text -split '\s+')
        $kind = $fields[0]
        $members = @($fields | Select-Object -Skip 1)
        if ($members.Count -eq 0) {
            throw "Invalid record in ${itemsFile}: $text"
        }

        $name = $members[0]
        $rest = @($members | Select-Object -Skip 1)
        if (-not (Test-ValidName -Name $name)) {
            throw "Invalid name '$name' in $itemsFile."
        }

        if ($kind -eq "core" -or $kind -eq "seed") {
            if ($rest.Count -ne 0) {
                throw "'$kind $name' takes exactly one name in $itemsFile."
            }

            $script:coreItems += $name
            if ($kind -eq "seed") {
                $script:seedItems += $name
            }
        }
        elseif ($kind -eq "supersedes") {
            if ($rest.Count -eq 0) {
                throw "'$kind $name' lists no files in $itemsFile."
            }

            foreach ($member in $rest) {
                if (-not (Test-ValidName -Name $member)) {
                    throw "Invalid name '$member' in $itemsFile."
                }
            }

            if ($script:supersededItems.Contains($name)) {
                $script:supersededItems[$name] = @($script:supersededItems[$name]) + $rest
            }
            else {
                $script:supersededItems[$name] = $rest
            }
        }
        elseif ($kind -eq "team" -or $kind -eq "legacy") {
            if ($rest.Count -eq 0) {
                throw "'$kind $name' lists no items in $itemsFile."
            }

            foreach ($member in $rest) {
                if (-not (Test-ValidName -Name $member)) {
                    throw "Invalid name '$member' in $itemsFile."
                }
            }

            if ($kind -eq "team") {
                $table = $script:teamItems
            }
            else {
                $table = $script:legacyItems
            }

            if ($table.Contains($name)) {
                $table[$name] = @($table[$name]) + $rest
            }
            else {
                $table[$name] = $rest
            }
        }
        else {
            throw "Unknown record '$kind' in $itemsFile."
        }
    }

    $script:allTeamNames = @($script:teamItems.Keys)
    if ($script:coreItems.Count -eq 0 -or $script:allTeamNames.Count -eq 0) {
        throw "$itemsFile lists no core or team items."
    }

    $script:managedItems = @($script:coreItems)
    foreach ($teamName in $script:allTeamNames) {
        foreach ($item in $script:teamItems[$teamName]) {
            if ($script:managedItems -notcontains $item) {
                $script:managedItems += $item
            }
        }
    }

    foreach ($dir in $script:legacyItems.Keys) {
        if ($script:managedItems -contains $dir) {
            throw "Legacy directory '$dir' is also an installed item in $itemsFile."
        }
    }

    foreach ($seedName in $script:supersededItems.Keys) {
        if ($script:seedItems -notcontains $seedName) {
            throw "'supersedes $seedName' names a file that is not a seed in $itemsFile."
        }

        foreach ($copyName in $script:supersededItems[$seedName]) {
            $copyPath = Join-Path (Join-Path $PSScriptRoot "superseded") $copyName
            if (-not (Test-Path -LiteralPath $copyPath -PathType Leaf)) {
                throw "Missing superseded copy '$copyName' at '$copyPath'."
            }
        }
    }
}

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
            foreach ($teamName in $script:allTeamNames) {
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

# Core items and the selected teams' items, each once.
function Get-InstallItems {
    param([string[]]$SelectedTeams)

    $items = @($script:coreItems)

    foreach ($teamName in $SelectedTeams) {
        foreach ($item in $script:teamItems[$teamName]) {
            if ($items -notcontains $item) {
                $items += $item
            }
        }
    }

    return $items
}

function Resolve-FullPath {
    param([string]$Path)

    $full = [System.IO.Path]::GetFullPath($ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path))
    $pathRoot = [System.IO.Path]::GetPathRoot($full)
    if ($full.Length -gt $pathRoot.Length) {
        $full = $full.TrimEnd([char[]]@('\', '/'))
    }

    return $full
}

# The path with every link on it followed, so a junction or symbolic link that leads to
# the profile directory is refused as the profile directory, as install.sh refuses it.
# A path that cannot be followed is returned as written, which is what it compared as before.
function Resolve-PhysicalPath {
    param([string]$Path)

    try {
        $full = Resolve-FullPath -Path $Path
        $resolved = [System.IO.Path]::GetPathRoot($full)
        $pending = @($full.Substring($resolved.Length) -split '[\\/]' | Where-Object { $_ -ne "" })
        $hops = 0

        while ($pending.Count -gt 0) {
            $candidate = Join-Path $resolved $pending[0]
            $pending = @($pending | Select-Object -Skip 1)
            $item = Get-Item -LiteralPath $candidate -Force -ErrorAction SilentlyContinue

            if ($null -ne $item -and (Test-ReparsePoint -Item $item) -and $null -ne $item.Target -and $hops -lt 32) {
                $target = @($item.Target)[0]
                if (-not [System.IO.Path]::IsPathRooted($target)) {
                    $target = Join-Path (Split-Path $candidate -Parent) $target
                }

                $hops++
                $followed = Resolve-FullPath -Path $target
                $resolved = [System.IO.Path]::GetPathRoot($followed)
                $pending = @(@($followed.Substring($resolved.Length) -split '[\\/]' | Where-Object { $_ -ne "" }) + $pending)
            }
            else {
                $resolved = $candidate
            }
        }

        return $resolved
    }
    catch {
        return Resolve-FullPath -Path $Path
    }
}

function Test-PathWithin {
    param(
        [string]$Child,
        [string]$Parent
    )

    $childPrefix = $Child.TrimEnd('\') + "\"
    $parentPrefix = $Parent.TrimEnd('\') + "\"

    return $childPrefix.StartsWith($parentPrefix, [System.StringComparison]::OrdinalIgnoreCase)
}

# An install root is a skills folder, so a drive root, the profile directory and
# its parents, anything overlapping this checkout, and the current directory
# spelled as a relative path (unless it already holds an install) are refused
# before anything is written. A full path to the current directory is deliberate.
function Assert-SafeRoot {
    param(
        [string]$Label,
        [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        throw "The $Label destination is empty."
    }

    $resolved = Resolve-PhysicalPath -Path $Path
    $homePath = Resolve-PhysicalPath -Path $env:USERPROFILE

    if (Test-Path -LiteralPath $resolved -PathType Leaf) {
        throw "'$resolved' exists and is not a directory."
    }

    if ($resolved -eq [System.IO.Path]::GetPathRoot($resolved)) {
        throw "Refusing to install into the filesystem root ($Label destination)."
    }

    if (Test-PathWithin -Child $homePath -Parent $resolved) {
        throw "Refusing to install into '$resolved' ($Label destination): it is your home directory or one of its parents."
    }

    if (Test-PathWithin -Child (Resolve-PhysicalPath -Path $repoRoot) -Parent $resolved) {
        throw "Refusing to install into '$resolved' ($Label destination): it contains the Supreme Team checkout."
    }

    if (Test-PathWithin -Child $resolved -Parent (Resolve-PhysicalPath -Path $sourceRoot)) {
        throw "Refusing to install into '$resolved' ($Label destination): it is inside the skills source directory."
    }

    if (-not [System.IO.Path]::IsPathRooted($Path) -and ($resolved -eq (Resolve-PhysicalPath -Path (Get-Location).ProviderPath)) -and -not (Test-SupremeTeamInstallPresent -TargetRoot $resolved)) {
        throw "Refusing to install into '$resolved' ($Label destination): it is the current directory and holds no Supreme Team install. Pass the skills folder's full path instead."
    }
}

function Test-ReparsePoint {
    param([System.IO.FileSystemInfo]$Item)

    return [bool]($Item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)
}

# The directory entry called $Name under $Root, or $null. Unlike Get-Item it also
# finds a link whose target is gone.
function Get-EntryInfo {
    param(
        [string]$Root,
        [string]$Name
    )

    $found = @(Get-ChildItem -LiteralPath $Root -Force -Filter $Name -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq $Name })

    if ($found.Count -eq 0) {
        return $null
    }

    return $found[0]
}

# Reads the record of the last run. Something at its path that is not a record
# (another file, a link, a directory) is not the installer's to overwrite.
function Read-Manifest {
    param([string]$Root)

    $script:oldItems = @()
    $script:manifestForeign = $false
    $file = Join-Path $Root $manifestName

    $info = Get-EntryInfo -Root $Root -Name $manifestName
    if ($null -eq $info) {
        return
    }

    if ($info.PSIsContainer -or (Test-ReparsePoint -Item $info)) {
        $script:manifestForeign = $true
        return
    }

    $lines = @(Get-Content -LiteralPath $file)
    if ($lines.Count -eq 0 -or $lines[0].Trim() -ne $manifestHeader) {
        Write-Warning "Ignoring $file, which is not a Supreme Team install record."
        $script:manifestForeign = $true
        return
    }

    foreach ($line in $lines) {
        if ($line.StartsWith("item ")) {
            $name = $line.Substring(5).Trim()
            if ((Test-ValidName -Name $name) -and ($script:oldItems -notcontains $name)) {
                $script:oldItems += $name
            }
        }
    }
}

# Returns absent, owned or foreign for $Root\$Name. A link is never owned, so it
# is moved aside as a link and never followed.
function Get-ItemState {
    param(
        [string]$Root,
        [string]$Name
    )

    $item = Get-EntryInfo -Root $Root -Name $Name

    if ($null -eq $item) {
        return "absent"
    }

    if (Test-ReparsePoint -Item $item) {
        return "foreign"
    }

    if ($item.PSIsContainer) {
        $marker = Get-EntryInfo -Root $item.FullName -Name $markerName
        if ($null -ne $marker -and -not $marker.PSIsContainer -and -not (Test-ReparsePoint -Item $marker)) {
            return "owned"
        }

        return "foreign"
    }

    if ($script:oldItems -contains $Name) {
        return "owned"
    }

    return "foreign"
}

# SHA-256 of a file's bytes with the CR of every CRLF dropped, the fold the catalog's
# own hashes use and install.sh's same_text applies. Latin-1 turns each byte into one
# character and back, so nothing but the CRLF pairs changes.
function Get-FoldedHash {
    param(
        [string]$Path
    )

    $latin1 = [System.Text.Encoding]::GetEncoding("iso-8859-1")
    $folded = $latin1.GetString([System.IO.File]::ReadAllBytes($Path)).Replace("`r`n", "`n")
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        return [System.BitConverter]::ToString($sha.ComputeHash($latin1.GetBytes($folded)))
    }
    finally {
        $sha.Dispose()
    }
}

# True when $Root\$Name is a regular file that is a copy an earlier release shipped
# (install-items.txt, supersedes), whichever line endings its checkout gave it: it was
# never edited, so it is the installer's own. Folded hashes are compared, the same
# proof install.sh gets from cmp.
function Test-SupersededSeed {
    param(
        [string]$Root,
        [string]$Name
    )

    $item = Get-EntryInfo -Root $Root -Name $Name
    if ($null -eq $item -or $item.PSIsContainer -or (Test-ReparsePoint -Item $item)) {
        return $false
    }

    if (-not $script:supersededItems.Contains($Name)) {
        return $false
    }

    $installed = Get-FoldedHash -Path $item.FullName
    foreach ($copyName in $script:supersededItems[$Name]) {
        $copy = Join-Path (Join-Path $PSScriptRoot "superseded") $copyName
        if ((Get-FoldedHash -Path $copy) -eq $installed) {
            return $true
        }
    }

    return $false
}

# A directory from an older layout is recognised only while it holds nothing but
# the entries that layout put there.
function Test-LegacyDirectory {
    param(
        [string]$Root,
        [string]$Name
    )

    $item = Get-EntryInfo -Root $Root -Name $Name
    if ($null -eq $item -or -not $item.PSIsContainer -or (Test-ReparsePoint -Item $item)) {
        return $false
    }

    $entries = @(Get-ChildItem -LiteralPath $item.FullName -Force)
    if ($entries.Count -eq 0) {
        return $false
    }

    foreach ($entry in $entries) {
        if ($script:legacyItems[$Name] -notcontains $entry.Name) {
            return $false
        }
    }

    return $true
}

function Test-SupremeTeamInstallPresent {
    param([string]$TargetRoot)

    if (-not (Test-Path -LiteralPath $TargetRoot -PathType Container)) {
        return $false
    }

    if (Test-Path -LiteralPath (Join-Path $TargetRoot $manifestName) -PathType Leaf) {
        return $true
    }

    foreach ($item in $script:managedItems) {
        if (Test-Path -LiteralPath (Join-Path (Join-Path $TargetRoot $item) $markerName) -PathType Leaf) {
            return $true
        }
    }

    # An install from before the ownership records existed.
    return (Test-Path -LiteralPath (Join-Path $TargetRoot "admiral\SKILL.md") -PathType Leaf) -and
        (Test-Path -LiteralPath (Join-Path $TargetRoot "gatekeeper-admiral\SKILL.md") -PathType Leaf)
}

# Windows PowerShell 5.1's Remove-Item -Recurse can follow a link out of the tree
# and delete what it points at, so every link inside is removed as a link first.
function Remove-LinksWithin {
    param([string]$Directory)

    foreach ($entry in @(Get-ChildItem -LiteralPath $Directory -Force)) {
        if (Test-ReparsePoint -Item $entry) {
            $entry.Delete()
        }
        elseif ($entry.PSIsContainer) {
            Remove-LinksWithin -Directory $entry.FullName
        }
    }
}

# The only place anything is deleted: a staging directory this installer created,
# recognised by its name and by the marker written inside it. Items that are
# replaced or dropped are moved into it first, so what it holds is all the
# installer's own.
function Remove-StageDirectory {
    param([string]$Path)

    if (-not (Split-Path $Path -Leaf).StartsWith(".supremeteam-stage.")) {
        return
    }

    if (-not (Test-Path -LiteralPath (Join-Path $Path $stageMarkerName) -PathType Leaf)) {
        return
    }

    Remove-LinksWithin -Directory $Path
    Remove-Item -LiteralPath $Path -Recurse -Force
}

# An aborted run puts back an owned item it had moved aside whose replacement never
# landed, so the install is left as it was found. A committed run keeps its removals.
function Restore-RetiredItems {
    $retiredRoot = Join-Path $script:stage "old"

    foreach ($retired in @(Get-ChildItem -LiteralPath $retiredRoot -Force -ErrorAction SilentlyContinue)) {
        if ($null -eq (Get-EntryInfo -Root $script:stageRoot -Name $retired.Name)) {
            Move-Item -LiteralPath $retired.FullName -Destination (Join-Path $script:stageRoot $retired.Name)
        }
    }
}

function Clear-Stage {
    if ($script:stage -ne "") {
        try {
            if (-not $script:stageCommitted) {
                Restore-RetiredItems
            }

            Remove-StageDirectory -Path $script:stage
        }
        catch {
            Write-Warning "Could not clean up the staging folder '$($script:stage)': $($_.Exception.Message)"
        }

        $script:stage = ""
    }
}

# An interrupted run can leave its staging directory behind.
function Clear-OldStages {
    param([string]$TargetRoot)

    $candidates = @(Get-ChildItem -LiteralPath $TargetRoot -Directory -Force -Filter ".supremeteam-stage.*" -ErrorAction SilentlyContinue)
    foreach ($candidate in $candidates) {
        if (-not (Test-ReparsePoint -Item $candidate)) {
            Remove-StageDirectory -Path $candidate.FullName
        }
    }
}

function Copy-ToStage {
    param([string]$ItemName)

    $sourcePath = Join-Path $sourceRoot $ItemName
    $newRoot = Join-Path $script:stage "new"
    $sourceItem = Get-Item -LiteralPath $sourcePath

    if ($sourceItem.PSIsContainer) {
        Copy-Item -LiteralPath $sourcePath -Destination $newRoot -Recurse -Force
        [System.IO.File]::WriteAllText((Join-Path (Join-Path $newRoot $ItemName) $markerName), "supremeteam-managed 1`n", $utf8NoBom)
    }
    else {
        Copy-Item -LiteralPath $sourcePath -Destination $newRoot -Force
    }
}

# The backup folder sits next to the install root, not inside it, so a host that
# scans the root for skills never picks up the moved-aside copies.
function New-BackupDirectory {
    param([string]$TargetRoot)

    $base = "${TargetRoot}.supremeteam-backup"
    $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd'T'HHmmss'Z'")

    try {
        New-Item -ItemType Directory -Force -Path $base | Out-Null
    }
    catch {
        throw "Cannot create the backup folder '$base'; nothing was changed."
    }

    $candidate = Join-Path $base $stamp
    $attempt = 0
    while (Test-Path -LiteralPath $candidate) {
        $attempt++
        if ($attempt -ge 100) {
            throw "Cannot create a backup folder under '$base'; nothing was changed."
        }

        $candidate = Join-Path $base "$stamp-$attempt"
    }

    New-Item -ItemType Directory -Path $candidate | Out-Null
    $script:backupDir = $candidate
}

# Moves the staged copy of $ItemName into place. What is there now is moved aside
# first: an owned copy into the staging directory, anything else into the backup
# folder. If the final move fails, the previous copy is put back.
function Move-IntoPlace {
    param(
        [string]$Root,
        [string]$ItemName,
        [string]$State
    )

    $targetPath = Join-Path $Root $ItemName
    $stagedPath = Join-Path (Join-Path $script:stage "new") $ItemName
    $retiredPath = Join-Path (Join-Path $script:stage "old") $ItemName
    $backupPath = Join-Path $script:backupDir $ItemName

    if ($State -eq "owned") {
        Move-Item -LiteralPath $targetPath -Destination $retiredPath
    }
    elseif ($State -eq "foreign") {
        Move-Item -LiteralPath $targetPath -Destination $backupPath
    }

    try {
        Move-Item -LiteralPath $stagedPath -Destination $targetPath
    }
    catch {
        if ($State -eq "owned") {
            Move-Item -LiteralPath $retiredPath -Destination $targetPath
        }
        elseif ($State -eq "foreign") {
            Move-Item -LiteralPath $backupPath -Destination $targetPath
        }

        throw "Could not install '$ItemName' into '$Root'; the previous copy was put back."
    }
}

function Write-Manifest {
    param(
        [string]$Root,
        [string[]]$SelectedTeams,
        [string[]]$Items
    )

    $lines = @(
        $manifestHeader,
        ("installed_at " + (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")),
        ("teams " + ($SelectedTeams -join " "))
    )
    foreach ($item in $Items) {
        $lines += "item $item"
    }

    $stagedPath = Join-Path $script:stage "manifest"
    [System.IO.File]::WriteAllText($stagedPath, (($lines -join "`n") + "`n"), $utf8NoBom)
    Move-Item -LiteralPath $stagedPath -Destination (Join-Path $Root $manifestName) -Force
}

function Assert-InstalledLayout {
    param(
        [string]$Root,
        [string[]]$Items
    )

    foreach ($item in $Items) {
        Assert-PathPresent -Path (Join-Path $Root $item) -Description "installed item '$item'"
    }
}

function Write-ItemList {
    param(
        [string]$Label,
        [string[]]$Items
    )

    if (@($Items).Count -gt 0) {
        Write-Host "  ${Label}: $(@($Items) -join ' ')"
    }
}

function Install-SupremeTeam {
    param(
        [string]$TargetRoot,
        [string[]]$SelectedTeams,
        [string[]]$Items
    )

    $root = Resolve-FullPath -Path $TargetRoot
    Read-Manifest -Root $root

    $manifestPath = Join-Path $root $manifestName
    if (Test-Path -LiteralPath $manifestPath -PathType Container) {
        throw "'$manifestPath' is a directory; move it away and run the installer again."
    }

    $addItems = @()
    $replaceItems = @()
    $keptItems = @()
    $refreshedItems = @()
    $foreignItems = @()
    $staleItems = @()
    $unselectedItems = @()
    $retiredItems = @()
    $asideItems = @()

    foreach ($item in $Items) {
        $state = Get-ItemState -Root $root -Name $item
        if ($state -ne "absent" -and $script:seedItems -contains $item) {
            if (Test-SupersededSeed -Root $root -Name $item) {
                $replaceItems += $item
                $refreshedItems += $item
            }
            else {
                $keptItems += $item
            }

            continue
        }

        if ($state -eq "absent") {
            $addItems += $item
        }
        elseif ($state -eq "owned") {
            $replaceItems += $item
        }
        else {
            $foreignItems += $item
        }
    }

    foreach ($item in $script:oldItems) {
        if (($Items -notcontains $item) -and ((Get-ItemState -Root $root -Name $item) -eq "owned")) {
            $staleItems += $item
            if ($script:managedItems -contains $item) {
                $unselectedItems += $item
            }
            else {
                $retiredItems += $item
            }
        }
    }

    # Moved aside without being replaced: a recognised old-layout directory, and
    # a file, link or directory sitting where the record belongs.
    foreach ($dir in $script:legacyItems.Keys) {
        if (Test-LegacyDirectory -Root $root -Name $dir) {
            $asideItems += $dir
        }
    }

    if ($script:manifestForeign) {
        $asideItems += $manifestName
    }

    if ($DryRun) {
        Write-ItemList -Label "would add" -Items $addItems
        Write-ItemList -Label "would replace" -Items $replaceItems
        Write-ItemList -Label "would replace, an unedited copy from an earlier release" -Items $refreshedItems
        Write-ItemList -Label "would keep, yours" -Items $keptItems
        Write-ItemList -Label "would remove, not selected this run" -Items $unselectedItems
        Write-ItemList -Label "would remove, no longer shipped" -Items $retiredItems
        Write-ItemList -Label "would move aside to ${root}.supremeteam-backup, not recorded as installed by Supreme Team" -Items @($foreignItems + $asideItems)
        return
    }

    New-Item -ItemType Directory -Force -Path $root | Out-Null
    Clear-OldStages -TargetRoot $root
    $script:stage = Join-Path $root (".supremeteam-stage." + [guid]::NewGuid().ToString("N").Substring(0, 8))
    $script:stageRoot = $root
    $script:stageCommitted = $false
    New-Item -ItemType Directory -Path $script:stage | Out-Null
    [System.IO.File]::WriteAllText((Join-Path $script:stage $stageMarkerName), "supremeteam-stage 1`n", $utf8NoBom)
    New-Item -ItemType Directory -Path (Join-Path $script:stage "new") | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $script:stage "old") | Out-Null

    # Everything that can fail for lack of space or permission happens here,
    # before the first change to an item that is already in place.
    foreach ($item in @($addItems + $replaceItems + $foreignItems)) {
        Copy-ToStage -ItemName $item
    }

    $script:backupDir = ""
    if (($foreignItems.Count + $asideItems.Count) -gt 0) {
        New-BackupDirectory -TargetRoot $root
    }

    foreach ($item in $addItems) {
        Move-IntoPlace -Root $root -ItemName $item -State "absent"
    }
    foreach ($item in $replaceItems) {
        Move-IntoPlace -Root $root -ItemName $item -State "owned"
    }
    foreach ($item in $foreignItems) {
        Move-IntoPlace -Root $root -ItemName $item -State "foreign"
    }
    foreach ($item in $staleItems) {
        Move-Item -LiteralPath (Join-Path $root $item) -Destination (Join-Path (Join-Path $script:stage "old") $item)
    }
    foreach ($item in $asideItems) {
        Move-Item -LiteralPath (Join-Path $root $item) -Destination (Join-Path $script:backupDir $item)
    }

    Write-Manifest -Root $root -SelectedTeams $SelectedTeams -Items $Items
    $script:stageCommitted = $true
    Assert-InstalledLayout -Root $root -Items $Items
    Clear-Stage

    $newCount = $addItems.Count + $foreignItems.Count
    Write-Host "  installed $($newCount + $replaceItems.Count) items ($newCount new, $($replaceItems.Count) replaced)"
    Write-Host "  recorded in $(Join-Path $root $manifestName)"
    Write-ItemList -Label "kept, yours" -Items $keptItems
    Write-ItemList -Label "replaced, an unedited copy from an earlier release" -Items $refreshedItems
    Write-ItemList -Label "removed, not selected this run" -Items $unselectedItems
    Write-ItemList -Label "removed, no longer shipped" -Items $retiredItems
    if ($script:backupDir -ne "") {
        Write-Host "  moved aside, not recorded as installed by Supreme Team and unchanged, to $($script:backupDir):"
        foreach ($item in @($foreignItems + $asideItems)) {
            Write-Host "    $item"
        }

        $script:backupDirs += $script:backupDir
    }
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

function Test-CommandAvailable {
    param([string]$Name)

    try {
        return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
    }
    catch {
        return $false
    }
}

function Get-MinimumPythonVersion {
    # skills/runtime-manifest.yaml is the runtime contract and is plain JSON.
    # Reading it here keeps the installer from refusing an interpreter the
    # project declares supported. The fallback covers an unreadable manifest.
    $manifest = Join-Path $sourceRoot "runtime-manifest.yaml"

    try {
        if (Test-Path -LiteralPath $manifest) {
            $value = (Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json).runtime.python.minimum
            if ($value -match '^\d+\.\d+$') {
                return $value
            }
        }
    }
    catch {
        # fall through to the default
    }

    return "3.13"
}

function Test-PythonMinimumVersion {
    param(
        [string]$Command,
        [string[]]$Arguments = @()
    )

    $parts = (Get-MinimumPythonVersion) -split '\.'
    $probe = "import sys; raise SystemExit(0 if sys.version_info >= ($($parts[0]), $($parts[1])) else 1)"

    try {
        & $Command @Arguments -c $probe *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Find-CompatiblePythonCommand {
    $candidates = @(
        @{ Command = "py"; Arguments = @("-3") },
        @{ Command = "python"; Arguments = @() },
        @{ Command = "python3"; Arguments = @() },
        @{ Command = "python3.14"; Arguments = @() },
        @{ Command = "python3.13"; Arguments = @() }
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
        $minimum = Get-MinimumPythonVersion
        Write-Warning "No Python $minimum+ interpreter was found. Skill files will still be copied, but hook verification and registration require Python $minimum or newer."
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

function Register-HarnessHooks {
    param(
        [string[]]$HostTargets,
        [string]$HookRoot
    )

    if ($HostTargets.Count -eq 0) {
        Write-Host "Hook registration skipped: no host targets were detected. Pass -Target Codex,Claude,Cursor,OpenCode,Copilot to choose explicitly."
        return
    }

    $helper = Join-Path $repoRoot "scripts\install_hooks.py"
    Assert-PathPresent -Path $helper -Description "hook registration helper"

    # A registration that cannot run is reported in the summary and ends in a failing
    # exit status, after the skills it follows were installed; it never stops the script
    # before the operator is told what was and was not done.
    $python = Find-CompatiblePythonCommand
    if ($null -eq $python) {
        Write-Warning "Python $(Get-MinimumPythonVersion) or newer is required to register runtime harness hooks."
        $script:hooksFailed = 1
        return
    }

    $hookArgs = @($helper, "--hook-root", $HookRoot)
    foreach ($hostName in $HostTargets) {
        $hookArgs += @("--target", $hostName)
    }
    $hookArgs += @("--scope", $HooksScope.ToLowerInvariant())
    if ($HooksYes) {
        $hookArgs += "--yes"
    }

    $pythonArgs = @($python.Arguments)
    & $python.Command @pythonArgs @hookArgs
    # Exit 3 is the operator answering no at the preview: nothing was written.
    if ($LASTEXITCODE -eq 3) {
        $script:hooksDeclined = $true
    }
    elseif ($LASTEXITCODE -ne 0) {
        $script:hooksFailed = $LASTEXITCODE
    }
}

try {
    Import-ItemList
    Assert-PathPresent -Path $sourceRoot -Description "skills source directory"
    foreach ($item in $script:managedItems) {
        Assert-PathPresent -Path (Join-Path $sourceRoot $item) -Description "source item '$item'"
    }

    $selectedTeams = @(Resolve-TeamSelection -RequestedTeams $Team)
    $installItems = @(Get-InstallItems -SelectedTeams $selectedTeams)
    $hostTargets = @(Resolve-HostTargets -RequestedTargets $Target)
    $normalizedRequestedTargets = @($Target | ForEach-Object { $_.ToLowerInvariant() })
    $explicitCodexTarget = $normalizedRequestedTargets -contains "codex"
    $explicitCursorTarget = $normalizedRequestedTargets -contains "cursor"
    Write-PythonReadinessWarning

    $installRoots = @(@{ Label = "common"; Path = $Destination })

    if (($hostTargets -contains "codex") -and ($explicitCodexTarget -or (Test-SupremeTeamInstallPresent -TargetRoot $CodexDestination))) {
        $installRoots += @{ Label = "codex"; Path = $CodexDestination }
    }

    if ($hostTargets -contains "claude") {
        $installRoots += @{ Label = "claude"; Path = $ClaudeDestination }
    }

    if (($hostTargets -contains "cursor") -and ($explicitCursorTarget -or (Test-SupremeTeamInstallPresent -TargetRoot $CursorDestination))) {
        $installRoots += @{ Label = "cursor"; Path = $CursorDestination }
    }

    if ($hostTargets -contains "opencode") {
        $installRoots += @{ Label = "opencode"; Path = $OpenCodeDestination }
    }

    foreach ($entry in $installRoots) {
        Assert-SafeRoot -Label $entry.Label -Path $entry.Path
    }

    if ($DryRun) {
        Write-Host "Dry run: nothing will be written."
    }

    $mirrorSummaries = @()

    foreach ($entry in $installRoots) {
        if ($entry.Label -eq "common") {
            Write-Host "Installing Supreme Team to $($entry.Path)"
        }
        else {
            Write-Host "Mirroring Supreme Team to $($entry.Path)"
            $mirrorSummaries += "$($entry.Label)=$($entry.Path)"
        }

        Install-SupremeTeam -TargetRoot $entry.Path -SelectedTeams $selectedTeams -Items $installItems
    }

    if ($DryRun) {
        Write-Host ""
        Write-Host "Dry run complete: nothing was written."
        return
    }

    if ($RegisterHooks) {
        Register-HarnessHooks -HostTargets $hostTargets -HookRoot (Join-Path $Destination "harness\hooks")
    }

    $mirrorStatus = if ($mirrorSummaries.Count -gt 0) { $mirrorSummaries -join "; " } else { "none" }
    $hostStatus = if ($hostTargets.Count -gt 0) { $hostTargets -join ", " } else { "none detected" }
    $backupStatus = if ($script:backupDirs.Count -gt 0) { "Moved aside, kept unchanged: $($script:backupDirs -join '; ')" } else { "Moved aside: nothing" }
    if (-not $RegisterHooks) {
        $hookStatus = "not requested"
    }
    elseif ($hostTargets.Count -eq 0) {
        $hookStatus = "skipped (no host detected)"
    }
    elseif ($script:hooksDeclined) {
        $hookStatus = "declined (nothing was written)"
    }
    elseif ($script:hooksFailed -ne 0) {
        $hookStatus = "failed (exit status $($script:hooksFailed); see the messages above)"
    }
    else {
        $hookStatus = "completed"
    }

    Write-Host ""
    if ($script:hooksFailed -eq 0) {
        Write-Host "Supreme Team installation complete."
    }
    else {
        Write-Host "Supreme Team skills are installed, but hook registration failed."
    }

    Write-Host "Target: $Destination"
    Write-Host "Host targets: $hostStatus"
    Write-Host "Host mirrors: $mirrorStatus"
    Write-Host "Teams: $(Format-TeamList -SelectedTeams $selectedTeams)"
    Write-Host "Installed items: $($installItems.Count) in $($installRoots.Count) location(s)"
    Write-Host $backupStatus
    Write-Host "Hook registration: $hookStatus"
    Write-Host "Restart your assistant session if it was already running."
    if ((-not $RegisterHooks) -or $script:hooksDeclined -or ($script:hooksFailed -ne 0)) {
        Write-Host ""
        Write-Host "=================================================================="
        Write-Host "RUNTIME HOOKS ARE NOT REGISTERED: Supreme Team is installed without its enforcement layer."
        Write-Host "Without the three hooks the assistant is only advised, never stopped: a guarded or frozen"
        Write-Host "path can be written, a lifecycle request can bypass admiral, and a run heartbeat goes stale."
        Write-Host "Register them (the installer previews every file it would change and asks first):"
        Write-Host "    powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -RegisterHooks"
        Write-Host "Then restart the assistant and confirm with: py -3 `"$Destination\harness\hooks\check_readiness.py`" --host auto --require-hooks"
        Write-Host "=================================================================="
    }
    if (-not $RegisterHooks) {
        Write-Host "To register runtime harness hooks for the selected hosts, run this installer again from a checkout with -RegisterHooks, or preview the registration with: python `"$Destination\harness\hooks\repair_registration.py`" --host <host> --scope project"
    }

    if ($script:hooksFailed -ne 0) {
        Write-Host "Fix what the registration reported, then run this installer again with -RegisterHooks, or preview the registration with: python `"$Destination\harness\hooks\repair_registration.py`" --host <host> --scope $($HooksScope.ToLowerInvariant())"
        exit $script:hooksFailed
    }
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
finally {
    Clear-Stage
}
