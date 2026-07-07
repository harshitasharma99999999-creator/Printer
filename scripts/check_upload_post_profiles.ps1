$ErrorActionPreference = "Stop"

Write-Host "Upload-Post profile diagnostic" -ForegroundColor Cyan
Write-Host "Paste the Upload-Post API key. It will not be printed or saved." -ForegroundColor Yellow

$secure = Read-Host "Enter Upload-Post API key" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)

try {
    $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    $headers = @{ Authorization = "Apikey $apiKey" }
    $base = "https://api.upload-post.com/api"
    $paths = @(
        "/uploadposts/me",
        "/uploadposts/users"
    )

    foreach ($path in $paths) {
        $url = "$base$path"
        Write-Host "`nTrying $url" -ForegroundColor DarkCyan
        try {
            $response = Invoke-RestMethod -Uri $url -Headers $headers -Method Get -TimeoutSec 60
            $response | ConvertTo-Json -Depth 8
            if ($path -eq "/uploadposts/users") {
                Write-Host "`nUse the profile.username value whose social_accounts.instagram is connected as UPLOAD_POST_USER." -ForegroundColor Green
                break
            }
        } catch {
            $status = $_.Exception.Response.StatusCode.value__
            Write-Host "Failed HTTP $status" -ForegroundColor DarkYellow
            if ($_.ErrorDetails.Message) {
                Write-Host $_.ErrorDetails.Message
            }
        }
    }
} finally {
    if ($bstr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
    $apiKey = $null
}

Read-Host "Press Enter to close"
