$ErrorActionPreference = 'Stop'
$server = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'web\server.py'))
# Match this project's exact script argument, never terminate all Python processes.
$quoted = '"' + $server + '"'
$targets = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -in @('python.exe', 'pythonw.exe') -and
    $_.CommandLine -and (
        $_.CommandLine.Contains($quoted) -or
        $_.CommandLine.EndsWith(' ' + $server)
    )
}
foreach ($target in $targets) {
    Stop-Process -Id $target.ProcessId -ErrorAction SilentlyContinue
}
Write-Host 'Penrose web server stopped. Use Start-Web.cmd to restart.'
