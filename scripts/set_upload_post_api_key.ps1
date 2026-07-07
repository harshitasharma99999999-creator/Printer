$ErrorActionPreference = "Stop"

$gh = "${env:ProgramFiles}\GitHub CLI\gh.exe"
if (-not (Test-Path -LiteralPath $gh)) {
    $gh = "gh"
}

Write-Host "Upload-Post API key -> GitHub Actions Secret" -ForegroundColor Cyan
Write-Host "Paste your Upload-Post API key. It will not be printed or saved to a file." -ForegroundColor Yellow

$secure = Read-Host "Enter Upload-Post API key" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)

try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    $plain | & $gh secret set UPLOAD_POST_API_KEY

    if ($LASTEXITCODE -eq 0) {
        Write-Host "SUCCESS: UPLOAD_POST_API_KEY saved to GitHub Secrets." -ForegroundColor Green
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
