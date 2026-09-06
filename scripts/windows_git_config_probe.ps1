<#
.SYNOPSIS
  A measurement, not a test: does a trusted-table entry read configuration out of a
  directory a standard user can write?

.DESCRIPTION
  Spec question q14. `C:\ProgramData` stays in ENV-06g's system class because "the
  toolchain reads configuration from it", and ENV-06a therefore requires it to pass
  IMG-01 — which the oracle probe measured it does not (evidence §3.23, mask
  0x001201BF grants BUILTIN\Users FILE_ADD_FILE). Whether that matters turns on a fact
  nobody has measured: does anything in the closed runnable set actually load from
  there, and can the subject reach it?

  Git decides it. Git for Windows reads a system-scope config below %ProgramData%, and
  git config can set `core.pager` and aliases — which this design's own effect table
  already treats as execution triggers when they arrive as `-c` flags. A planted config
  file reaches the same place without the flag, through a `git status` the closed set
  calls inert. That is the claim this script tests rather than asserts.

  Nothing here executes a pager or an alias. The marker value is inert text and every
  git invocation passes --no-pager. The planted file is removed and any pre-existing
  one restored, in a finally block.

.PARAMETER Out
  Path to write the JSON result to. The reading happens in review; this asserts nothing.
#>
[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$Out)

$ErrorActionPreference = 'Continue'

function Get-UsersAcl {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    try {
        $acl = Get-Acl -LiteralPath $Path
        $rules = @()
        foreach ($a in $acl.Access) {
            $rules += [ordered]@{
                identity    = [string]$a.IdentityReference
                rights      = [string]$a.FileSystemRights
                type        = [string]$a.AccessControlType
                inherited   = [bool]$a.IsInherited
            }
        }
        return [ordered]@{ owner = [string]$acl.Owner; access = $rules }
    } catch { return [ordered]@{ error = $_.Exception.Message } }
}

$result = [ordered]@{
    identity = [ordered]@{
        user      = "$env:USERDOMAIN\$env:USERNAME"
        is_admin  = ([Security.Principal.WindowsPrincipal] `
                     [Security.Principal.WindowsIdentity]::GetCurrent()
                    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    }
    git = [ordered]@{}
    program_data = [ordered]@{}
    write_test = [ordered]@{}
}

# --- 1. what git is, and which files it says it reads ----------------------------
$git = (Get-Command git -ErrorAction SilentlyContinue).Source
$result.git.exe = $git
if ($git) {
    $result.git.version = (& $git --no-pager --version) -join "`n"
    $result.git.list_show_origin_scope =
        (& $git --no-pager config --list --show-origin --show-scope 2>&1) -join "`n"
    $result.git.system_scope =
        (& $git --no-pager config --list --system --show-origin 2>&1) -join "`n"
    # `git config --show-origin --get` on a key nobody set exits 1; that is data, not failure.
    $result.git.pager_before =
        (& $git --no-pager config --show-origin --get core.pager 2>&1) -join "`n"
}

# --- 2. what lives under ProgramData, and who may write it -----------------------
$result.program_data.root_acl = Get-UsersAcl 'C:\ProgramData'
$children = @()
foreach ($name in 'Git', 'Python', 'nodejs', 'chocolatey', 'ripgrep') {
    $p = Join-Path 'C:\ProgramData' $name
    $children += [ordered]@{
        name   = $name
        path   = $p
        exists = [bool](Test-Path -LiteralPath $p)
        acl    = Get-UsersAcl $p
    }
}
$result.program_data.toolchain_dirs = $children
$cfg = 'C:\ProgramData\Git\config'
$result.program_data.git_config = [ordered]@{
    path   = $cfg
    exists = [bool](Test-Path -LiteralPath $cfg)
    acl    = Get-UsersAcl $cfg
}

# --- 3. the end-to-end test: plant, read back through git, restore ---------------
# This is the whole question. An ACL that permits a write proves nothing on its own if
# git never reads the file, and a config git reads proves nothing if the subject cannot
# write it. Only doing both, as this identity, answers q14.
$dir = 'C:\ProgramData\Git'
$backup = "$env:TEMP\git-config-probe-backup"
$createdDir = $false
$createdFile = $false
try {
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -ErrorAction Stop | Out-Null
        $createdDir = $true
    }
    if (Test-Path -LiteralPath $cfg) {
        Copy-Item -LiteralPath $cfg -Destination $backup -Force -ErrorAction Stop
    }
    # Inert text. Nothing runs it; the point is only whether git resolves it.
    @(
        '[probe]',
        "`tmarker = PROBE-MARKER-Q14",
        '[core]',
        "`tpager = probe-marker-not-executed"
    ) | Set-Content -LiteralPath $cfg -Encoding ascii -ErrorAction Stop
    $createdFile = $true
    $result.write_test.wrote = $true

    if ($git) {
        $result.write_test.marker_lookup =
            (& $git --no-pager config --show-origin --get probe.marker 2>&1) -join "`n"
        $result.write_test.marker_exit = $LASTEXITCODE
        $result.write_test.pager_lookup =
            (& $git --no-pager config --show-origin --get core.pager 2>&1) -join "`n"
        $result.write_test.pager_exit = $LASTEXITCODE
        $result.write_test.list_after =
            (& $git --no-pager config --list --show-origin --show-scope 2>&1) -join "`n"
    }
} catch {
    $result.write_test.wrote = $false
    $result.write_test.error = $_.Exception.Message
} finally {
    if ($createdFile) {
        if (Test-Path -LiteralPath $backup) {
            Copy-Item -LiteralPath $backup -Destination $cfg -Force -ErrorAction SilentlyContinue
            Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
        } else {
            Remove-Item -LiteralPath $cfg -Force -ErrorAction SilentlyContinue
        }
    }
    if ($createdDir) { Remove-Item -LiteralPath $dir -Force -Recurse -ErrorAction SilentlyContinue }
    $result.write_test.restored = -not (Test-Path -LiteralPath $cfg) -or (Test-Path -LiteralPath $backup)
}

$dirOut = Split-Path -Parent $Out
if ($dirOut -and -not (Test-Path -LiteralPath $dirOut)) {
    New-Item -ItemType Directory -Force -Path $dirOut | Out-Null
}
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Out -Encoding utf8
Write-Host "wrote $Out"
