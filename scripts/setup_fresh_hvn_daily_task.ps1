param(
  [string]$TaskName = "Fresh HVN Daily Instagram YouTube Post",
  [string]$Time = "10:30",
  [string]$ProfileDirectory = "Profile 8",
  [switch]$SkipInstagram,
  [switch]$SkipYouTube
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $Root "venv\Scripts\python.exe"
if (!(Test-Path $Python)) {
  $Python = "python"
}

$Args = @("scripts\fresh_hvn_daily.py", "--publish", "--profile-directory", "`"$ProfileDirectory`"")
if ($SkipInstagram) {
  $Args += "--skip-instagram"
}
if ($SkipYouTube) {
  $Args += "--skip-youtube"
}
$Command = "cd /d `"$Root`" && `"$Python`" $($Args -join ' ')"
$Action = New-ScheduledTaskAction `
  -Execute "cmd.exe" `
  -Argument "/c $Command"
$Trigger = New-ScheduledTaskTrigger -Daily -At $Time
$Settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -StartWhenAvailable `
  -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $Action `
  -Trigger $Trigger `
  -Settings $Settings `
  -Description "Generate and publish one Fresh HVN beverage Reel/Short daily." `
  -Force | Out-Null

Write-Host "Scheduled task created: $TaskName"
Write-Host "Daily run time: $Time"
Write-Host "Command: $Command"
Write-Host ""
Write-Host "Important: keep Windows logged in/unlocked and Chrome $ProfileDirectory logged into fresh_hvn."
