$ErrorActionPreference = "Stop"

$gh = "${env:ProgramFiles}\GitHub CLI\gh.exe"
if (-not (Test-Path -LiteralPath $gh)) {
    $gh = "gh"
}

Write-Host "Grand Forno Instagram password -> GitHub Actions Secret" -ForegroundColor Cyan
Write-Host "Your password will not be printed or saved to a file." -ForegroundColor Yellow

$secure = Read-Host "Enter NEW Instagram password for grand_forno" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)

try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    $plain | & $gh secret set GRAND_FORNO_INSTAGRAM_PASSWORD

    if ($LASTEXITCODE -eq 0) {
        Write-Host "SUCCESS: GRAND_FORNO_INSTAGRAM_PASSWORD saved to GitHub Secrets." -ForegroundColor Green
    } else {
        Write-Host "FAILED: GitHub CLI could not save the secret. Exit code: $LASTEXITCODE" -ForegroundColor Red
    }
} finally {
    if ($bstr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
    $plain = $null
}

Read-Host "Press Enter to close"
