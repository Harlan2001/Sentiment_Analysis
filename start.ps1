Write-Host "Starting Sentiment Project (uv)..." -ForegroundColor Cyan

$projectRoot = $PSScriptRoot
$venvPath = "$projectRoot\.venv"

# ---------- 启动后端 ----------
Write-Host "Starting backend (FastAPI)..." -ForegroundColor Green
Start-Process powershell -ArgumentList `
    "-NoExit", `
    "-Command", `
    "`$env:VIRTUAL_ENV = '$venvPath'; `$env:PATH = '$venvPath\Scripts;' + `$env:PATH; cd '$projectRoot'; python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

# ---------- 启动前端 ----------
Write-Host "Starting frontend (Vite)..." -ForegroundColor Green
Start-Process powershell -ArgumentList `
    "-NoExit", `
    "-Command", `
    "cd '$projectRoot/frontend'; npm run dev"

Write-Host "All services started!" -ForegroundColor Yellow
Write-Host "Frontend: http://localhost:5173"
Write-Host "Backend local:  http://127.0.0.1:8000" #本机
Write-Host "Backend internal:  http://10.253.3.41:8000" #内部网络
