param([string]$Dosbox = "$PSScriptRoot\..\tools\dosbox-x\mingw-build\mingw\dosbox-x.exe")
$ErrorActionPreference='Stop'
$projectRoot=(Resolve-Path "$PSScriptRoot\..").Path
$testRoot=Join-Path $projectRoot 'build\floppy-test'
New-Item -ItemType Directory -Force $testRoot | Out-Null
foreach ($oldName in @('FAILED.TXT','OUTPUT.TXT','DIR.TXT')) {
    $oldPath=Join-Path $testRoot $oldName
    if (Test-Path -LiteralPath $oldPath) { Remove-Item -LiteralPath $oldPath }
}
[IO.File]::WriteAllText((Join-Path $testRoot 'QUIT.TXT'),"quit`r`n",[Text.Encoding]::ASCII)
$config=@"
[sdl]
output=surface
priority=normal,normal
[cpu]
core=dynamic
cycles=max
turbo=true
use dynamic core with fpu=true
[dos]
keyboardlayout=ru
[autoexec]
mount c "$testRoot"
imgmount a "$projectRoot\dist\TINY-RU.IMG" -t floppy
a:
dir > c:\DIR.TXT
TINY /P 0 < c:\QUIT.TXT > c:\OUTPUT.TXT
if errorlevel 1 echo failed > c:\FAILED.TXT
exit
"@
$configPath=Join-Path $testRoot 'floppy.conf'
[IO.File]::WriteAllText($configPath,$config,[Text.Encoding]::ASCII)
$process=Start-Process -FilePath (Resolve-Path $Dosbox).Path -ArgumentList @('-fastlaunch','-nogui','-conf',('"'+$configPath+'"')) -WorkingDirectory $testRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput "$testRoot\emulator.stdout.log" -RedirectStandardError "$testRoot\emulator.stderr.log"
if (-not $process.WaitForExit(60000)) { $process.Kill(); throw 'Floppy test timed out' }
if (((Test-Path "$testRoot\FAILED.TXT") -and (Get-Item "$testRoot\FAILED.TXT").Length -gt 0) -or -not (Test-Path "$testRoot\OUTPUT.TXT")) { throw 'Floppy test failed' }
Copy-Item "$testRoot\OUTPUT.TXT" "$projectRoot\reports\floppy-output.cp866.txt" -Force
Copy-Item "$testRoot\DIR.TXT" "$projectRoot\reports\floppy-directory.cp866.txt" -Force
Get-Item "$projectRoot\reports\floppy-output.cp866.txt" | Select-Object Length
