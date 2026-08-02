[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$seedSignerRoot = Join-Path $projectRoot "seedsigner"
$kruxRoot = Join-Path $projectRoot "krux"
$seedSignerPython = Join-Path $seedSignerRoot ".venv\Scripts\pythonw.exe"
$kruxPython = Join-Path $kruxRoot ".venv\Scripts\pythonw.exe"
$seedSignerScript = Join-Path $seedSignerRoot "desktop_emulator.py"
$kruxScript = Join-Path $kruxRoot "simulator\simulator.py"
$logsRoot = Join-Path $projectRoot "logs"

foreach ($requiredPath in @($seedSignerPython, $kruxPython, $seedSignerScript, $kruxScript)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Required file is missing: $requiredPath"
    }
}

New-Item -ItemType Directory -Path $logsRoot -Force | Out-Null

Add-Type -AssemblyName System.Windows.Forms
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Text;

public static class SimulatorWindow {
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("user32.dll")]
    private static extern bool EnumWindows(EnumWindowsProc callback, IntPtr lParam);

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

    [DllImport("user32.dll")]
    private static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int maxLength);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool SetWindowPos(IntPtr hWnd, IntPtr insertAfter, int x, int y, int width, int height, uint flags);

    [DllImport("user32.dll")]
    private static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);

    [StructLayout(LayoutKind.Sequential)]
    private struct RECT {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    public static IntPtr FindForProcess(int targetProcessId) {
        IntPtr result = IntPtr.Zero;
        EnumWindows(delegate(IntPtr hWnd, IntPtr lParam) {
            uint processId;
            GetWindowThreadProcessId(hWnd, out processId);
            if (processId == targetProcessId && IsWindowVisible(hWnd)) {
                result = hWnd;
                return false;
            }
            return true;
        }, IntPtr.Zero);
        return result;
    }

    public static IntPtr FindByTitle(string targetTitle) {
        IntPtr result = IntPtr.Zero;
        EnumWindows(delegate(IntPtr hWnd, IntPtr lParam) {
            if (!IsWindowVisible(hWnd)) {
                return true;
            }
            StringBuilder title = new StringBuilder(512);
            GetWindowText(hWnd, title, title.Capacity);
            if (title.ToString() == targetTitle) {
                result = hWnd;
                return false;
            }
            return true;
        }, IntPtr.Zero);
        return result;
    }

    public static int Width(IntPtr hWnd) {
        RECT rect;
        GetWindowRect(hWnd, out rect);
        return rect.Right - rect.Left;
    }

    public static int Height(IntPtr hWnd) {
        RECT rect;
        GetWindowRect(hWnd, out rect);
        return rect.Bottom - rect.Top;
    }

    public static bool Position(IntPtr hWnd, int x, int y) {
        const uint SWP_NOSIZE = 0x0001;
        const uint SWP_NOZORDER = 0x0004;
        const uint SWP_NOACTIVATE = 0x0010;
        return SetWindowPos(hWnd, IntPtr.Zero, x, y, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE);
    }
}
"@

function Wait-ForWindow {
    param(
        [Parameter(Mandatory = $true)] [System.Diagnostics.Process] $Process,
        [Parameter(Mandatory = $true)] [string] $ExpectedTitle,
        [int] $TimeoutSeconds = 25
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        $windowHandle = [SimulatorWindow]::FindForProcess($Process.Id)
        if ($windowHandle -eq [IntPtr]::Zero) {
            $windowHandle = [SimulatorWindow]::FindByTitle($ExpectedTitle)
        }
        if ($windowHandle -ne [IntPtr]::Zero) {
            return $windowHandle
        }

        Start-Sleep -Milliseconds 150
        $Process.Refresh()
    }

    return [IntPtr]::Zero
}

$workArea = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
$sideMargin = 24
$centerGap = 20
$maxWindowWidth = [Math]::Floor(($workArea.Width - (2 * $sideMargin) - $centerGap) / 2)
$windowHeight = [Math]::Min(768, $workArea.Height - (2 * $sideMargin))
$windowWidth = [Math]::Round($windowHeight * 0.625)

if ($windowWidth -gt $maxWindowWidth) {
    $windowWidth = $maxWindowWidth
    $windowHeight = [Math]::Round($windowWidth / 0.625)
}

$windowWidth = [Math]::Max(360, $windowWidth)
$windowHeight = [Math]::Max(576, $windowHeight)
$windowY = $workArea.Y + [Math]::Floor(($workArea.Height - $windowHeight) / 2)
$leftCenter = $workArea.X + [Math]::Floor($workArea.Width / 4)
$rightCenter = $workArea.X + [Math]::Floor(($workArea.Width * 3) / 4)
$leftX = $leftCenter - [Math]::Floor($windowWidth / 2)
$rightX = $rightCenter - [Math]::Floor($windowWidth / 2)
$geometry = "${windowWidth}x${windowHeight}+${leftX}+${windowY}"

$seedSignerErrorLog = Join-Path $logsRoot "seedsigner-error.log"
$seedSignerOutputLog = Join-Path $logsRoot "seedsigner-output.log"
$kruxErrorLog = Join-Path $logsRoot "krux-error.log"
$kruxOutputLog = Join-Path $logsRoot "krux-output.log"

$instanceId = [Guid]::NewGuid().ToString("N").Substring(0, 8)
$seedSignerTitle = "SeedSigner Simulator [$instanceId]"
$kruxTitle = "Krux Simulator [$instanceId]"

$seedSignerProcess = Start-Process `
    -FilePath $seedSignerPython `
    -ArgumentList @($seedSignerScript, "--geometry", $geometry, "--title", "`"$seedSignerTitle`"") `
    -WorkingDirectory $seedSignerRoot `
    -RedirectStandardError $seedSignerErrorLog `
    -RedirectStandardOutput $seedSignerOutputLog `
    -PassThru

$previousSdlPosition = $env:SDL_VIDEO_WINDOW_POS
$previousKruxTitle = $env:KRUX_SIMULATOR_TITLE
$env:SDL_VIDEO_WINDOW_POS = "${rightX},${windowY}"
$env:KRUX_SIMULATOR_TITLE = $kruxTitle
try {
    $kruxProcess = Start-Process `
        -FilePath $kruxPython `
        -ArgumentList @($kruxScript, "--device", "maixpy_amigo", "--sd") `
        -WorkingDirectory $kruxRoot `
        -RedirectStandardError $kruxErrorLog `
        -RedirectStandardOutput $kruxOutputLog `
        -PassThru
}
finally {
    $env:SDL_VIDEO_WINDOW_POS = $previousSdlPosition
    $env:KRUX_SIMULATOR_TITLE = $previousKruxTitle
}

$seedSignerWindow = Wait-ForWindow -Process $seedSignerProcess -ExpectedTitle $seedSignerTitle
$kruxWindow = Wait-ForWindow -Process $kruxProcess -ExpectedTitle $kruxTitle

if ($seedSignerWindow -eq [IntPtr]::Zero -or $kruxWindow -eq [IntPtr]::Zero) {
    throw "A simulator window did not open. Check $logsRoot for the startup error."
}

$seedSignerOuterWidth = [SimulatorWindow]::Width($seedSignerWindow)
$seedSignerOuterHeight = [SimulatorWindow]::Height($seedSignerWindow)
$kruxOuterWidth = [SimulatorWindow]::Width($kruxWindow)
$kruxOuterHeight = [SimulatorWindow]::Height($kruxWindow)

$seedSignerX = $leftCenter - [Math]::Floor($seedSignerOuterWidth / 2)
$seedSignerY = $workArea.Y + [Math]::Floor(($workArea.Height - $seedSignerOuterHeight) / 2)
$kruxX = $rightCenter - [Math]::Floor($kruxOuterWidth / 2)
$kruxY = $workArea.Y + [Math]::Floor(($workArea.Height - $kruxOuterHeight) / 2)

[SimulatorWindow]::Position($seedSignerWindow, $seedSignerX, $seedSignerY) | Out-Null
[SimulatorWindow]::Position($kruxWindow, $kruxX, $kruxY) | Out-Null
