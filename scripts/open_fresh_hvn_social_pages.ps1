param(
  [ValidateSet("signup", "upload")]
  [string]$Mode = "signup",
  [string]$ProfileDirectory = "Profile 8"
)

$ErrorActionPreference = "Stop"

$Chrome = Join-Path $env:LOCALAPPDATA "Google\Chrome\Application\chrome.exe"
if (!(Test-Path $Chrome)) {
  $Chrome = "chrome.exe"
}

$Pages = @{
  tiktok = @{
    signup = "https://www.tiktok.com/signup"
    upload = "https://www.tiktok.com/upload"
  }
  pinterest = @{
    signup = "https://www.pinterest.com/business/create/"
    upload = "https://www.pinterest.com/pin-creation-tool/"
  }
  x = @{
    signup = "https://x.com/i/flow/signup"
    upload = "https://x.com/compose/post"
  }
  threads = @{
    signup = "https://www.threads.net/"
    upload = "https://www.threads.net/"
  }
  whatsapp = @{
    signup = "https://web.whatsapp.com/"
    upload = "https://web.whatsapp.com/"
  }
}

foreach ($name in $Pages.Keys) {
  $url = $Pages[$name][$Mode]
  Start-Process -FilePath $Chrome -ArgumentList "--profile-directory=$ProfileDirectory", $url
  Start-Sleep -Milliseconds 600
}

Write-Host "Opened Fresh HVN social $Mode pages in Chrome $ProfileDirectory."
Write-Host "Use brand name: Fresh HVN"
Write-Host "Use order phone/WhatsApp: 7045027768"
