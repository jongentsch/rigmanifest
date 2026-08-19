param(
    [switch]$SidecarOnly
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$desktopRoot = Join-Path $repositoryRoot "desktop"
$python = Join-Path $repositoryRoot ".venv/Scripts/python.exe"
$sidecarDist = Join-Path $repositoryRoot "dist/sidecar"
$sidecarWork = Join-Path $repositoryRoot "build/sidecar"
$sidecarSource = Join-Path $repositoryRoot "src/rigmanifest/sidecar.py"
$binaryDirectory = Join-Path $desktopRoot "src-tauri/binaries"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Python environment not found at $python. Run the repository setup steps first."
}

$rustcCommand = Get-Command rustc -ErrorAction SilentlyContinue
$rustcPath = if ($rustcCommand) { $rustcCommand.Source } else { $null }
if (-not $rustcPath) {
    $rustcFallback = Join-Path $env:USERPROFILE ".cargo/bin/rustc.exe"
    if (Test-Path -LiteralPath $rustcFallback -PathType Leaf) {
        $rustcPath = $rustcFallback
        $env:Path = "$(Split-Path -Parent $rustcFallback);$env:Path"
    }
    else {
        throw "rustc was not found. Install the Tauri prerequisites first."
    }
}

$targetTriple = (& $rustcPath --print host-tuple).Trim()
if (-not $targetTriple) {
    throw "rustc did not return a host target triple."
}

New-Item -ItemType Directory -Force -Path $sidecarDist, $sidecarWork, $binaryDirectory | Out-Null

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --name rigmanifest-sidecar `
    --paths (Join-Path $repositoryRoot "src") `
    --hidden-import chirp.drivers.vx6 `
    --hidden-import chirp.drivers.uvk5 `
    --hidden-import chirp.drivers.anytone778uv `
    --collect-data chirp `
    --copy-metadata chirp `
    --distpath $sidecarDist `
    --workpath $sidecarWork `
    --specpath $sidecarWork `
    $sidecarSource

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller sidecar build failed with exit code $LASTEXITCODE."
}

$extension = if ($IsWindows -or $env:OS -eq "Windows_NT") { ".exe" } else { "" }
$builtSidecar = Join-Path $sidecarDist "rigmanifest-sidecar$extension"
$tauriSidecar = Join-Path $binaryDirectory "rigmanifest-sidecar-$targetTriple$extension"
Copy-Item -LiteralPath $builtSidecar -Destination $tauriSidecar -Force

$smokeStartInfo = New-Object System.Diagnostics.ProcessStartInfo
$smokeStartInfo.FileName = $tauriSidecar
$smokeStartInfo.Arguments = "--once"
$smokeStartInfo.UseShellExecute = $false
$smokeStartInfo.CreateNoWindow = $true
$smokeStartInfo.RedirectStandardInput = $true
$smokeStartInfo.RedirectStandardOutput = $true
$smokeStartInfo.RedirectStandardError = $true
$smokeProcess = New-Object System.Diagnostics.Process
$smokeProcess.StartInfo = $smokeStartInfo
$originalConsoleInputEncoding = [Console]::InputEncoding
$utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
try {
    # Process.StandardInput inherits Console.InputEncoding on Windows PowerShell 5.
    # A BOM-emitting encoding corrupts the first newline-delimited JSON request.
    [Console]::InputEncoding = $utf8WithoutBom
    [void]$smokeProcess.Start()
    $smokeProcess.StandardInput.WriteLine('{"id":"portable-smoke","method":"catalog"}')
    $smokeProcess.StandardInput.Close()
}
finally {
    [Console]::InputEncoding = $originalConsoleInputEncoding
}
$smokeResponse = $smokeProcess.StandardOutput.ReadToEnd()
$smokeError = $smokeProcess.StandardError.ReadToEnd()
$smokeProcess.WaitForExit()
if ($smokeProcess.ExitCode -ne 0) {
    throw "Frozen sidecar smoke test failed with exit code $($smokeProcess.ExitCode): $smokeError"
}
try {
    $smokePayload = $smokeResponse | ConvertFrom-Json -ErrorAction Stop
}
catch {
    throw "Frozen sidecar smoke test returned invalid JSON: $smokeResponse"
}
if ($smokePayload.id -ne "portable-smoke" -or -not $smokePayload.result.schema_version) {
    throw "Frozen sidecar smoke test returned an invalid response: $smokeResponse"
}

Write-Host "Portable sidecar ready: $tauriSidecar"

if (-not $SidecarOnly) {
    Push-Location $desktopRoot
    try {
        pnpm tauri build --config src-tauri/tauri.portable.conf.json
        if ($LASTEXITCODE -ne 0) {
            throw "Tauri portable bundle failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }

    $releaseDirectory = Join-Path $desktopRoot "src-tauri/target/release"
    $portableDirectory = Join-Path $repositoryRoot "build/portable-package/RigManifest"
    $portableArchive = Join-Path $repositoryRoot "dist/portable/RigManifest_0.1.0_x64-portable.zip"
    $portableArchiveDirectory = Split-Path -Parent $portableArchive
    New-Item -ItemType Directory -Force `
        -Path $portableDirectory, $portableArchiveDirectory | Out-Null
    Copy-Item -LiteralPath (Join-Path $releaseDirectory "rigmanifest-desktop.exe") `
        -Destination (Join-Path $portableDirectory "RigManifest.exe") -Force
    Copy-Item -LiteralPath (Join-Path $releaseDirectory "rigmanifest-sidecar.exe") `
        -Destination (Join-Path $portableDirectory "rigmanifest-sidecar.exe") -Force
    Copy-Item -LiteralPath (Join-Path $repositoryRoot "LICENSE") `
        -Destination (Join-Path $portableDirectory "LICENSE") -Force
    Get-ChildItem -LiteralPath $portableDirectory | Compress-Archive `
        -DestinationPath $portableArchive -Force
    Write-Host "No-install portable archive ready: $portableArchive"
}
