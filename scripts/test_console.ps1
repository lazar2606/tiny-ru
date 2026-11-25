param([string]$Dosbox = "$PSScriptRoot\..\tools\dosbox-x\mingw-build\mingw\dosbox-x.exe")
$ErrorActionPreference='Stop'
$projectRoot=(Resolve-Path "$PSScriptRoot\..").Path
$testRoot=Join-Path $projectRoot 'build\console-test'
New-Item -ItemType Directory -Force $testRoot | Out-Null
Copy-Item "$projectRoot\build\CPINPUT.EXE" $testRoot -Force
foreach ($name in @('CONSOLE.LOG','FAILED.TXT','DONE.TXT')) {
    $old=Join-Path $testRoot $name
    if (Test-Path -LiteralPath $old) { Remove-Item -LiteralPath $old }
}
$config=@"
[sdl]
autolock=false
output=surface
[cpu]
core=dynamic
cycles=max
use dynamic core with fpu=true
[dos]
keyboardlayout=ru
[autoexec]
mount c "$testRoot"
c:
keyb ru 866
CPINPUT > OUTPUT.TXT
if errorlevel 1 echo failed > FAILED.TXT
echo finished > DONE.TXT
exit
"@
$configPath=Join-Path $testRoot 'test.conf'
[IO.File]::WriteAllText($configPath,$config,[Text.Encoding]::ASCII)
$p=Start-Process -FilePath (Resolve-Path $Dosbox).Path -ArgumentList @('-fastlaunch','-nogui','-conf',('"'+$configPath+'"')) -WorkingDirectory $testRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput "$testRoot\emulator.stdout.log" -RedirectStandardError "$testRoot\emulator.stderr.log"
if (-not $p.WaitForExit(60000)) { $p.Kill(); throw 'Console probe timed out' }
if (-not (Test-Path "$testRoot\CONSOLE.LOG")) { throw 'Console probe produced no result' }
if ((Test-Path "$testRoot\FAILED.TXT") -and (Get-Item "$testRoot\FAILED.TXT").Length -gt 0) { throw 'Console probe failed' }
Copy-Item "$testRoot\CONSOLE.LOG" "$projectRoot\reports\improvement\dos-console.cp866.txt" -Force
Get-Content "$testRoot\CONSOLE.LOG" -Encoding ASCII | Select-Object -First 1
