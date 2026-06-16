Write-Host "🚀 Starting Sentiment Project (Conda)..." -ForegroundColor Cyan

$projectRoot = $PSScriptRoot
$condaEnv = "sentiment"

# ---------- 启动后端 ----------
Write-Host "🔧 Starting backend (FastAPI)..." -ForegroundColor Green
Start-Process powershell -ArgumentList `
    "-NoExit", `
    "-Command", `
    "conda activate $condaEnv; cd '$projectRoot'; python -m uvicorn main:app --reload"

# ---------- 启动前端 ----------
Write-Host "🎨 Starting frontend (Vite)..." -ForegroundColor Green
Start-Process powershell -ArgumentList `
    "-NoExit", `
    "-Command", `
    "cd '$projectRoot/frontend'; npm run dev"

Write-Host "✅ All services started!" -ForegroundColor Yellow
Write-Host "🌐 Frontend: http://localhost:5173"
Write-Host "🔗 Backend:  http://127.0.0.1:8000"
