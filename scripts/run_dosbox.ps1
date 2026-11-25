param(
    [string]$Dosbox = "$PSScriptRoot\..\tools\dosbox-x\mingw-build\mingw\dosbox-x.exe",
    [string]$InputFile = "$PSScriptRoot\..\build\dos-test\INPUT.TXT",
    [int]$TimeoutSeconds = 7200,
    [int]$ReserveKB = 0,
    [ValidatePattern('^[a-zA-Z0-9_-]+$')][string]$TestName = 'dos-test',
    [string]$Executable = "$PSScriptRoot\..\dos\TINY.EXE",
    [string]$Weights = "$PSScriptRoot\..\dos\TINY.BIN",
    [switch]$AllowProgramFailure
)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$testRoot = Join-Path $projectRoot "build\$TestName"
New-Item -ItemType Directory -Force $testRoot | Out-Null
Copy-Item -LiteralPath (Resolve-Path -LiteralPath $Executable).Path -Destination "$testRoot\TINY.EXE" -Force
Copy-Item -LiteralPath (Resolve-Path -LiteralPath $Weights).Path -Destination "$testRoot\TINY.BIN" -Force
$inputResolved = (Resolve-Path -LiteralPath $InputFile).Path
$inputTarget = Join-Path $testRoot 'INPUT.TXT'
if ($inputResolved -ne $inputTarget) { Copy-Item -LiteralPath $inputResolved -Destination $inputTarget -Force }
$launch = 'TINY /P 0'
if ($ReserveKB -gt 0) { $launch = "loadfix -$ReserveKB $launch" }
foreach ($oldName in @('DONE.TXT','FAILED.TXT','OUTPUT.TXT')) {
    $oldPath = Join-Path $testRoot $oldName
    if (Test-Path -LiteralPath $oldPath) { Remove-Item -LiteralPath $oldPath }
}
$config = @"
[sdl]
autolock=false
output=surface
priority=normal,normal
[dosbox]
memsize=16
machine=svga_s3
[cpu]
core=dynamic
cputype=auto
cycles=max
turbo=true
stop turbo on key=false
use dynamic core with fpu=true
[dos]
keyboardlayout=ru
[autoexec]
mount c "$testRoot"
c:
keyb ru 866
mem > MEM.TXT
$launch < INPUT.TXT > OUTPUT.TXT
if errorlevel 1 echo failed > FAILED.TXT
echo finished > DONE.TXT
exit
"@
$configPath = Join-Path $testRoot 'test.conf'
[IO.File]::WriteAllText($configPath,$config,[Text.Encoding]::ASCII)
$process = Start-Process -FilePath (Resolve-Path -LiteralPath $Dosbox).Path -ArgumentList @('-fastlaunch','-nogui','-conf',('"' + $configPath + '"')) -WorkingDirectory $testRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput "$testRoot\emulator.stdout.log" -RedirectStandardError "$testRoot\emulator.stderr.log"
if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
    $process.Kill()
    throw "DOSBox-X test exceeded $TimeoutSeconds seconds; inspect $testRoot"
}
if (-not (Test-Path -LiteralPath "$testRoot\DONE.TXT")) { throw 'DOSBox-X did not complete the batch' }
if ((Test-Path -LiteralPath "$testRoot\FAILED.TXT") -and (Get-Item -LiteralPath "$testRoot\FAILED.TXT").Length -gt 0 -and -not $AllowProgramFailure) { throw 'TINY reported an error; inspect OUTPUT.TXT' }
Get-Item "$testRoot\OUTPUT.TXT", "$testRoot\MEM.TXT" | Select-Object FullName,Length
