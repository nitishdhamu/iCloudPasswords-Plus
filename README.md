# iCloud Passwords+

A lightweight, standalone Windows background utility that bridges the gap between the Apple "iCloud Passwords" desktop app and web browsers.

When iCloud generates a 6-digit OTP (One-Time Password) notification popup, this app instantly intercepts the window, hides it from the screen, and automatically types the 6 digits into your active browser field.

## Features
- **Zero Dependencies**: A fully compiled `.exe` that requires no Python installation.
- **Instant Interception**: Catches iCloud OTP popups in under 15ms using Win32 API hooks.
- **Zero Distraction**: Hides the iCloud popup completely so it doesn't block your screen.

## One-Command Installation

You don't need to download any ZIP files or installers. Simply open **PowerShell** as a regular user and paste this exact command:

```powershell
irm https://raw.githubusercontent.com/nitishdhamu/iCloudPasswords-Plus/main/install.ps1 | iex
```

**What this command does:**
1. Downloads and unzips the latest `iCloudPasswordsPlus.zip` from this repository's Releases.
2. Installs it cleanly to `%LOCALAPPDATA%\Programs\iCloudPasswords+`.
3. Registers it to automatically run silently in the background when you turn on your PC.
4. Starts the app instantly.

*(To uninstall, simply navigate to Windows **Settings > Apps > Installed Apps**, locate **iCloud Passwords+**, and click Uninstall).*

## Usage

After installation, the app runs entirely in the background.
### Manual Stop
To stop the app manually, open Task Manager, locate `iCloudPasswordsPlus`, and click End Task.

## How It Works

- The app uses `ctypes.windll.user32` to set an `EVENT_OBJECT_SHOW` hook, looking for standard Windows dialogs (`#32770`) spawned by the `icloud` process.
- When an OTP popup appears, it strips the visibility flags, moving it off-screen.
- It then scans the hidden window for the 6-digit regex pattern.
- It uses native keyboard inputs to simulate keystrokes directly into the active browser field.

## Requirements
- Windows 10 / 11
- iCloud for Windows (with Passwords enabled)

## License
MIT License
