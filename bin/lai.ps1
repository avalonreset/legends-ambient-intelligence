#Requires -Version 5.1
param(
  [Parameter(Position = 0)]
  [ValidateSet('doctor', 'help', 'status', 'ingest')]
  [string]$Command = 'help',
  [switch]$ArchiveOnly,
  [switch]$EjectWhenDone,
  [string]$Source
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$env:PYTHONPATH = (Join-Path $RepoRoot "src")

switch ($Command) {
  'doctor' {
    python -m legends_ambient doctor
    exit $LASTEXITCODE
  }
  'status' {
    python -m legends_ambient status
    exit $LASTEXITCODE
  }
  'ingest' {
    $argsList = @('ingest')
    if ($Source) { $argsList += @('--source', $Source) } else { $argsList += @('--device') }
    if ($EjectWhenDone) { $argsList += @('--eject') }
    python -m legends_ambient @argsList
    exit $LASTEXITCODE
  }
  'help' {
    python -m legends_ambient --help
    exit 0
  }
}
