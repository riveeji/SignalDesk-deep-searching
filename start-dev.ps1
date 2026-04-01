$root = Split-Path -Parent $MyInvocation.MyCommand.Path

docker compose -p deepresearch up -d postgres | Out-Null
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root'; uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\\frontend'; npm run dev"
