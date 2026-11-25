param([string]$Executable="$PSScriptRoot\..\windows\TINYWIN.EXE")
$ErrorActionPreference='Stop'
$root=(Resolve-Path "$PSScriptRoot\..").Path
$exe=(Resolve-Path -LiteralPath $Executable).Path
$probe=Join-Path $root 'build\windows-console-probe.exe'
$reports=Join-Path $root 'reports\windows'
if (-not (Test-Path -LiteralPath $probe)) { throw 'Build tests/windows_console_probe.c with -municode first; see README.md' }
New-Item -ItemType Directory -Force $reports | Out-Null
$arguments=@(('"'+$exe+'"'),('"'+$reports+'\console.utf8.txt"'),('"'+$reports+'\console.json"'))
$process=Start-Process -FilePath $probe -ArgumentList $arguments -WindowStyle Hidden -PassThru
if (-not $process.WaitForExit(60000)) { $process.Kill(); throw 'Console probe timed out' }
if ($process.ExitCode -ne 0) { throw 'Unicode console probe failed; see reports/windows/console.json' }
$result=Get-Content -LiteralPath "$reports\console.json" -Raw | ConvertFrom-Json
if (-not $result.ok) { throw 'Unicode console probe did not pass' }
$result | ConvertTo-Json
