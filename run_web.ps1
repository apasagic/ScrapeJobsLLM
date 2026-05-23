$env:HF_HUB_OFFLINE = if ($env:HF_HUB_OFFLINE) { $env:HF_HUB_OFFLINE } else { "1" }
$env:TRANSFORMERS_OFFLINE = if ($env:TRANSFORMERS_OFFLINE) { $env:TRANSFORMERS_OFFLINE } else { "1" }
$env:WEB_PORT = if ($env:WEB_PORT) { $env:WEB_PORT } else { "5001" }

Set-Location -LiteralPath $PSScriptRoot
& "$PSScriptRoot\.venv\Scripts\python.exe" "$PSScriptRoot\app_web.py"
