#Requires -Version 5.1
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$PackName = 'legends-ambient-intelligence'
$SkillTarget = Join-Path $RepoRoot "skills\$PackName"
$SkillFile = Join-Path $SkillTarget 'SKILL.md'

if (-not (Test-Path -LiteralPath $SkillFile -PathType Leaf)) {
  throw "Primary skill missing: $SkillFile"
}

function Set-SkillLink {
  param(
    [string]$AgentName,
    [string]$LinkPath,
    [string]$TargetPath
  )
  $parent = Split-Path -Parent $LinkPath
  if (-not (Test-Path -LiteralPath $parent)) {
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
  }
  if (Test-Path -LiteralPath $LinkPath) {
    $item = Get-Item -LiteralPath $LinkPath -Force
    $isLink = [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)
    if ($isLink) {
      if ($item.Target -eq $TargetPath -or $item.LinkTarget -eq $TargetPath) {
        Write-Host "OK [$AgentName] already linked: $LinkPath"
        return
      }
      Remove-Item -LiteralPath $LinkPath -Force
    } else {
      Write-Host "WARN [$AgentName] not a link, skip: $LinkPath"
      return
    }
  }
  try {
    New-Item -ItemType SymbolicLink -Path $LinkPath -Target $TargetPath -Force | Out-Null
    Write-Host "OK [$AgentName] symlink: $LinkPath -> $TargetPath"
  } catch {
    try {
      cmd /c mklink /J "$LinkPath" "$TargetPath" | Out-Null
      Write-Host "OK [$AgentName] junction: $LinkPath -> $TargetPath"
    } catch {
      Write-Host "FAIL [$AgentName] $_"
    }
  }
}

$homes = @(
  @{ Name = 'grok'; Path = (Join-Path $env:USERPROFILE '.grok\skills') },
  @{ Name = 'codex'; Path = (Join-Path $env:USERPROFILE '.codex\skills') },
  @{ Name = 'claude'; Path = (Join-Path $env:USERPROFILE '.claude\skills') },
  @{ Name = 'gemini'; Path = (Join-Path $env:USERPROFILE '.gemini\skills') }
)

# Linux service homes when present
foreach ($extra in @(
  '/var/lib/omnigent/.grok/skills',
  '/var/lib/omnigent/.codex/skills',
  '/var/lib/omnigent/.claude/skills'
)) {
  if (Test-Path $extra) {
    $homes += @{ Name = (Split-Path $extra -Parent | Split-Path -Leaf); Path = $extra }
  }
}

foreach ($h in $homes) {
  if (-not $h.Path) { continue }
  $link = Join-Path $h.Path $PackName
  Set-SkillLink -AgentName $h.Name -LinkPath $link -TargetPath $SkillTarget
}

Write-Host "setup-multi-agent complete for $PackName"
