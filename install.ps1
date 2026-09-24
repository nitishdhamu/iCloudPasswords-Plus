$ProgressPreference = 'SilentlyContinue'
Write-Host "Installing iCloud Passwords+..." -ForegroundColor Cyan

$InstallDir = "$env:LOCALAPPDATA\Programs\iCloudPasswords+"

# 1. Create installation directory
if (!(Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
}

# 2. Stop any existing running instances
Stop-Process -Name "iCloudPasswordsPlus" -Force -ErrorAction SilentlyContinue

# 3. Fetch latest release from GitHub
Write-Host "Fetching latest release from GitHub..."
$repo = "nitishdhamu/iCloudPasswords-Plus"
try {
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/releases/latest"
    $asset = $release.assets | Where-Object { $_.name -eq "iCloudPasswordsPlus.zip" }
    
    if (!$asset) {
        Write-Host "ERROR: Could not find iCloudPasswordsPlus.zip in the latest GitHub release." -ForegroundColor Red
        exit 1
    }

    $zipPath = "$InstallDir\iCloudPasswordsPlus.zip"
    Write-Host "Downloading iCloudPasswordsPlus.zip..."
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zipPath

    Write-Host "Extracting files..."
    Expand-Archive -Path $zipPath -DestinationPath $InstallDir -Force
    Remove-Item -Path $zipPath -Force
} catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# 4. Register standard Startup Key (Requires NO Administrator privileges)
Write-Host "Registering silent background startup..."
Unregister-ScheduledTask -TaskName "iCloudPasswordsPlus" -Confirm:$false -ErrorAction SilentlyContinue

# Clean up legacy startup entries from previous versions
Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "iCloudPassLauncher" -ErrorAction SilentlyContinue
Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "iCloudPass" -ErrorAction SilentlyContinue
Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run" -Name "iCloudPass" -ErrorAction SilentlyContinue
Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run" -Name "iCloudPassLauncher" -ErrorAction SilentlyContinue
Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder" -Name "iCloudPass.vbs" -ErrorAction SilentlyContinue
Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder" -Name "iCloudAutoTyper.vbs" -ErrorAction SilentlyContinue

$registryPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
Set-ItemProperty -Path $registryPath -Name "iCloudPasswordsPlus" -Value "`"$InstallDir\iCloudPasswordsPlus.exe`""

# 5. Create Uninstaller and Register in Windows Settings ("Installed Apps")
Write-Host "Registering uninstaller in Windows Settings..."
$uninstallScript = @"
Stop-Process -Name "iCloudPasswordsPlus" -Force -ErrorAction SilentlyContinue
Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "iCloudPasswordsPlus" -ErrorAction SilentlyContinue
Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "iCloudPassLauncher" -ErrorAction SilentlyContinue
Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "iCloudPass" -ErrorAction SilentlyContinue
Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run" -Name "iCloudPass" -ErrorAction SilentlyContinue
Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run" -Name "iCloudPassLauncher" -ErrorAction SilentlyContinue
Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder" -Name "iCloudPass.vbs" -ErrorAction SilentlyContinue
Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder" -Name "iCloudAutoTyper.vbs" -ErrorAction SilentlyContinue
Remove-Item -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\iCloudPasswordsPlus" -Recurse -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1
Remove-Item -Path "`$env:LOCALAPPDATA\Programs\iCloudPasswords+" -Recurse -Force -ErrorAction SilentlyContinue
"@
Set-Content -Path "$InstallDir\uninstall.ps1" -Value $uninstallScript

$uninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\iCloudPasswordsPlus"
if (!(Test-Path $uninstallKey)) { New-Item -Path $uninstallKey -Force | Out-Null }
Set-ItemProperty -Path $uninstallKey -Name "DisplayName" -Value "iCloud Passwords+"
Set-ItemProperty -Path $uninstallKey -Name "DisplayVersion" -Value "1.0.0"
Set-ItemProperty -Path $uninstallKey -Name "Publisher" -Value "Nitish Dhamu"
Set-ItemProperty -Path $uninstallKey -Name "DisplayIcon" -Value "$InstallDir\iCloudPasswordsPlus.exe"
Set-ItemProperty -Path $uninstallKey -Name "UninstallString" -Value "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$InstallDir\uninstall.ps1`""
Set-ItemProperty -Path $uninstallKey -Name "NoModify" -Value 1 -Type DWord
Set-ItemProperty -Path $uninstallKey -Name "NoRepair" -Value 1 -Type DWord

# 6. Start the App
Start-Process -FilePath "$InstallDir\iCloudPasswordsPlus.exe" -WindowStyle Hidden

Write-Host "======================================================" -ForegroundColor Green
Write-Host "   INSTALLATION COMPLETE!                             " -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host "iCloud Passwords+ is now running silently in the background."
