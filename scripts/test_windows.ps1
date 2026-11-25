param([string]$Executable="$PSScriptRoot\..\windows\TINYWIN.EXE")
$ErrorActionPreference='Stop'
$root=(Resolve-Path "$PSScriptRoot\..").Path
$exe=(Resolve-Path -LiteralPath $Executable).Path
$work=Join-Path $root 'build\windows-test'
$reports=Join-Path $root 'reports\windows'
New-Item -ItemType Directory -Force $work,$reports | Out-Null
$utf8=New-Object Text.UTF8Encoding($false,$true)
$cp866=[Text.Encoding]::GetEncoding(866)
$checks=New-Object Collections.Generic.List[string]

function Run-Tiny([string]$path,[byte[]]$payload,[string]$arguments='/P 0') {
    $start=New-Object Diagnostics.ProcessStartInfo
    $start.FileName=$path
    $start.Arguments=$arguments
    $start.WorkingDirectory=$work
    $start.UseShellExecute=$false
    $start.CreateNoWindow=$true
    $start.RedirectStandardInput=$true
    $start.RedirectStandardOutput=$true
    $start.RedirectStandardError=$true
    $start.StandardOutputEncoding=$utf8
    $start.StandardErrorEncoding=$utf8
    $process=New-Object Diagnostics.Process
    $process.StartInfo=$start
    [void]$process.Start()
    $outTask=$process.StandardOutput.ReadToEndAsync()
    $errTask=$process.StandardError.ReadToEndAsync()
    $process.StandardInput.BaseStream.Write($payload,0,$payload.Length)
    $process.StandardInput.Close()
    if (-not $process.WaitForExit(180000)) { $process.Kill(); throw 'Windows runtime timed out' }
    $result=[pscustomobject]@{Code=$process.ExitCode;Text=$outTask.GetAwaiter().GetResult();Error=$errTask.GetAwaiter().GetResult()}
    $process.Dispose()
    return $result
}
function Require($condition,[string]$message) { if (-not $condition) { throw $message } }
function Canonical([string]$s) { return $s.Trim().ToLowerInvariant().TrimEnd([char[]]'.!?').Trim() }

$rows=@([IO.File]::ReadAllLines((Join-Path $root 'data\russia-final\control.jsonl'),$utf8) | ForEach-Object { $_ | ConvertFrom-Json })
$payload=$utf8.GetBytes((($rows | ForEach-Object {$_.question}) -join "`r`n")+"`r`nquit`r`n")
$run=Run-Tiny $exe $payload
Require ($run.Code -eq 0) $run.Error
Require ($run.Text.Contains('Windows x64')) 'Windows title missing'
$answers=[regex]::Matches($run.Text,'\n>   ([^\r\n]*)\r?\n   \[')
Require ($answers.Count -eq $rows.Count) 'Lost or extra input lines'
$groups=@{}
$details=@()
for ($i=0;$i -lt $rows.Count;$i++) {
    $row=$rows[$i];$answer=$answers[$i].Groups[1].Value
    $ok=@($row.answers | ForEach-Object {Canonical $_}) -contains (Canonical $answer)
    if (-not $groups.ContainsKey($row.split)) { $groups[$row.split]=@{correct=0;total=0} }
    $groups[$row.split].total++
    if ($ok) { $groups[$row.split].correct++ }
    $details+=@{question=$row.question;answer=$answer;correct=$ok;split=$row.split}
}
foreach ($key in @($groups.Keys)) { $groups[$key].accuracy=$groups[$key].correct / $groups[$key].total }
$evaluation=@{total=$rows.Count;metrics=$groups;examples=$details;weights_sha256=(Get-FileHash (Join-Path (Split-Path $exe) 'TINY.BIN')).Hash.ToLower()}
[IO.File]::WriteAllText((Join-Path $reports 'evaluation.json'),($evaluation | ConvertTo-Json -Depth 8),$utf8)
[IO.File]::WriteAllText((Join-Path $reports 'output.utf8.txt'),$run.Text,$utf8)
Require ($groups.russia_familiar.correct -ge 990) 'Unexpected inference regression'
$checks.Add('1200 real Windows inferences, UTF-8 streams, model loaded outside working directory')

$sample=$rows[0]
foreach ($mode in @('utf8-bom','cp866','cp1251')) {
    $text=$sample.question+"`r`nquit`r`n"
    $arguments='/P 0'
    if ($mode -eq 'utf8-bom') { $bytes=[byte[]](0xEF,0xBB,0xBF)+$utf8.GetBytes($text) }
    elseif ($mode -eq 'cp866') { $bytes=$cp866.GetBytes($text);$arguments+=' /CP866' }
    else { $bytes=[Text.Encoding]::GetEncoding(1251).GetBytes($text);$arguments+=' /CP1251' }
    $r=Run-Tiny $exe $bytes $arguments
    Require ($r.Code -eq 0 -and $r.Text.Contains($sample.answers[0])) "Encoding failed: $mode"
    $checks.Add($mode)
}
foreach ($ending in @("`r","`n","`r`n",'')) {
    $r=Run-Tiny $exe ($utf8.GetBytes('quit'+$ending))
    Require ($r.Code -eq 0 -and -not $r.Text.Contains('72')) 'Line ending failed'
}
$checks.Add('CR, LF, CRLF, EOF without final newline')
$letter=[char]0x044F
$tooLong=([string]$letter)*73
$overflow='a'*5000
$r=Run-Tiny $exe ($utf8.GetBytes($tooLong+"`r`n"+$overflow+"`r`n"+$sample.question+"`r`nquit`r`n"))
Require ($r.Code -eq 0 -and $r.Text.Contains($sample.answers[0])) 'Overflow consumed next question'
Require (([regex]::Matches($r.Text,'72')).Count -eq 2) 'Expected two length rejections'
$checks.Add('73 Russian characters, 5000-byte line, next question preserved')

$unicode=Join-Path $work (([string][char]0x0422)+([char]0x0435)+([char]0x0441)+([char]0x0442)+' Tiny')
New-Item -ItemType Directory -Force $unicode | Out-Null
Copy-Item -LiteralPath $exe -Destination (Join-Path $unicode 'TINYWIN.EXE') -Force
Copy-Item -LiteralPath (Join-Path (Split-Path $exe) 'TINY.BIN') -Destination $unicode -Force
$r=Run-Tiny (Join-Path $unicode 'TINYWIN.EXE') ($utf8.GetBytes($sample.question+"`nquit`n"))
Require ($r.Code -eq 0 -and $r.Text.Contains($sample.answers[0])) 'Unicode executable path failed'
$checks.Add('Cyrillic executable directory with spaces')

$broken=Join-Path $work 'broken'
New-Item -ItemType Directory -Force $broken | Out-Null
Copy-Item -LiteralPath $exe -Destination (Join-Path $broken 'TINYWIN.EXE') -Force
foreach ($blob in @([byte[]]@(),[byte[]](66,65,68,33))) {
    [IO.File]::WriteAllBytes((Join-Path $broken 'TINY.BIN'),$blob)
    $r=Run-Tiny (Join-Path $broken 'TINYWIN.EXE') ($utf8.GetBytes("quit`n"))
    Require ($r.Code -ne 0) 'Corrupt weights accepted'
}
$checks.Add('Empty and invalid model rejected')

$checks | ForEach-Object { Write-Output ('PASS '+$_) }
[IO.File]::WriteAllText((Join-Path $reports 'checks.json'),($checks | ConvertTo-Json),$utf8)
$groups | ConvertTo-Json -Depth 4
