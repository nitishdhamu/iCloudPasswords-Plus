# iCloud Passwords+

A lightweight, standalone Windows background utility that bridges the gap between the Apple iCloud Passwords desktop app and web browsers.

When iCloud generates a 6-digit OTP (One-Time Password) notification popup, this app instantly intercepts the window, hides it from your screen, and automatically types the 6 digits directly into your active browser field in milliseconds.

## Features
- **Ultra-Low Memory Usage**: Consumes only ~3.3 MB of RAM in the background.
- **Hardware-Level Speed**: Uses native Windows `SendInput` API calls for microsecond keystroke delivery.
- **Instant Background Startup**: Loads silently when you log in with zero administrator/UAC prompts.
- **Invisible Interception**: Hides the iCloud OTP dialog before it renders on your screen.
- **Zero Configuration**: Fully automatic and plug-and-play with no setup or config files.

## One-Command Installation

Open **PowerShell** (no administrator rights needed) and run:

```powershell
irm https://raw.githubusercontent.com/nitishdhamu/iCloudPasswords-Plus/main/install.ps1 | iex
```

**What this command does:**
1. Downloads and extracts the latest `iCloudPasswordsPlus.zip` from Releases.
2. Installs cleanly to `%LOCALAPPDATA%\Programs\iCloudPasswords+`.
3. Registers silent auto-start in Windows for the current user.
4. Launches the utility immediately.

## Uninstallation

You can uninstall anytime in either of two ways:
- **Windows Settings**: Go to **Settings > Apps > Installed Apps**, locate **iCloud Passwords+**, and click **Uninstall**.
- **PowerShell**: Run `& "$env:LOCALAPPDATA\Programs\iCloudPasswords+\uninstall.ps1"`

## How It Works

1. Sets a native Win32 `EVENT_OBJECT_SHOW` hook to detect dialogs spawned by the `icloud` process.
2. Moves and hides the window off-screen before it draws.
3. Extracts the 6-digit verification code using regular expressions.
4. Focuses the active browser field and types the code at the OS level.
5. Flushes working set memory back to the operating system.

## Requirements
- Windows 10 / 11 (64-bit)
- iCloud for Windows (with Passwords enabled)
- Chrome, Edge, Brave, or any Chromium-based browser with the iCloud Passwords extension

## License
MIT License
