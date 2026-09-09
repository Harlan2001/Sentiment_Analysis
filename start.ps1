# Sentiment 项目一键启动脚本（uv 虚拟环境）
# - 后端 FastAPI + 前端 Vite 各开一个独立窗口（带标题区分）
# - 启动前预检：虚拟环境 / 前端依赖 / 端口占用，缺一即提示并退出
# - 后端就绪后做一次 /health 探测，输出可访问地址（本机 + 局域网）

$projectRoot = $PSScriptRoot
$venvPath = "$projectRoot\.venv"
$backendPort = 8000      # 与 CLAUDE.md / Vite 代理 / 提示信息保持一致
$backendUrl = "http://127.0.0.1:$backendPort"

Write-Host "========== Sentiment Project (uv) ==========" -ForegroundColor Cyan

# ---------- 预检 1：后端虚拟环境 ----------
$pythonExe = "$venvPath\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    Write-Host "[X] 未找到虚拟环境: $pythonExe" -ForegroundColor Red
    Write-Host "    请先执行:  uv sync" -ForegroundColor Yellow
    exit 1
}

# ---------- 预检 2：前端依赖 ----------
$nodeModules = "$projectRoot\frontend\node_modules"
if (-not (Test-Path $nodeModules)) {
    Write-Host "[X] 未找到前端依赖: $nodeModules" -ForegroundColor Red
    Write-Host "    请先执行:  cd frontend; npm install" -ForegroundColor Yellow
    exit 1
}

# ---------- 预检 3：后端端口占用 ----------
function Test-LocalPortInUse([int]$port) {
    return [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}
if (Test-LocalPortInUse $backendPort) {
    Write-Host "[X] 端口 $backendPort 已被其他进程占用，请先释放后重试。" -ForegroundColor Red
    Write-Host "    查看占用:  netstat -ano | findstr :$backendPort" -ForegroundColor Yellow
    exit 1
}

# ---------- 启动后端（独立窗口，标题区分） ----------
Write-Host "正在启动后端 (FastAPI)..." -ForegroundColor Green
$backendCmd = "`$Host.UI.RawUI.WindowTitle = 'Sentiment 后端 (FastAPI)'; " +
              "Set-Location '$projectRoot'; " +
              "& '$pythonExe' -m uvicorn main:app --host 0.0.0.0 --port $backendPort --reload"
Start-Process powershell -ArgumentList @('-NoExit', '-Command', $backendCmd)

# ---------- 启动前端（独立窗口，标题区分） ----------
Write-Host "正在启动前端 (Vite)..." -ForegroundColor Green
$frontendCmd = "`$Host.UI.RawUI.WindowTitle = 'Sentiment 前端 (Vite)'; " +
               "Set-Location '$projectRoot\frontend'; " +
               "npm run dev"
Start-Process powershell -ArgumentList @('-NoExit', '-Command', $frontendCmd)

# ---------- 等待后端就绪 ----------
Write-Host "等待后端就绪 ..." -ForegroundColor Gray
$ready = $false
foreach ($i in 1..60) {
    Start-Sleep -Seconds 1
    try {
        $resp = Invoke-RestMethod -Uri "$backendUrl/health" -TimeoutSec 2
        if ($resp.status -eq 'ok') { $ready = $true; break }
    } catch {
        # 服务尚未就绪，继续等待
    }
}

# ---------- 输出访问地址 ----------
$lanIp = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
          Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
          Select-Object -First 1 -ExpandProperty IPAddress)

Write-Host ""
Write-Host "========== 启动完成 ==========" -ForegroundColor Cyan
if ($ready) {
    Write-Host "  [OK] 后端已就绪" -ForegroundColor Green
} else {
    Write-Host "  [!] 后端未在 60 秒内就绪，请查看后端窗口日志（可能是数据库/LLM 未就绪）。" -ForegroundColor Yellow
}
Write-Host "  前端地址       : http://localhost:5173"
Write-Host "  后端地址(本机) : $backendUrl"
if ($lanIp) {
    Write-Host "  后端地址(局域网): http://$lanIp`:$backendPort"
} else {
    Write-Host "  后端地址(局域网): 未获取到局域网 IP（内网访问不可用）"
}
Write-Host "========================================" -ForegroundColor Cyan
