$PythonArgs = $args
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$candidates = @()
foreach ($name in @('python', 'python3', 'py')) {
    $command = Get-Command $name -ErrorAction SilentlyContinue
    if ($command -and $command.Source -notlike '*\Microsoft\WindowsApps\*') { $candidates += $command.Source }
}
# Резервный Python из установленного Codex, если отдельный Python не установлен.
$bundled = 'C:\Program Files\WindowsApps\OpenAI.CodexPrimaryRuntime.v26-1112-737-0_26.1112.737.0_x64__3k8sg7r9htsxt\dependencies\python\python.exe'
if (Test-Path -LiteralPath $bundled) { $candidates += $bundled }
foreach ($candidate in ($candidates | Select-Object -Unique)) {
    & $candidate -X utf8 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) {
        & $candidate -X utf8 @PythonArgs
        exit $LASTEXITCODE
    }
}
Write-Host 'Нужен Python 3.10 или новее. Установите Python с python.org и включите Add Python to PATH.'
exit 1
