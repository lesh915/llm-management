Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   LLM Management System - STARTING      " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# .env 파일 체크
if (!(Test-Path ".env")) {
    Write-Host "[!] .env 파일이 없습니다. .env.example을 복사하여 생성해주세요." -ForegroundColor Red
    exit
}

Write-Host "[1/2] 도커 컨테이너를 실행합니다..." -ForegroundColor White
docker-compose up -d

Write-Host "[2/2] 서비스 초기화를 확인합니다..." -ForegroundColor White
Start-Sleep -Seconds 3

Write-Host ""
Write-Host "전체 시스템이 시작되었습니다!" -ForegroundColor Green
Write-Host "------------------------------------------" -ForegroundColor Gray
Write-Host " - Web Dashboard:  http://localhost:47001" -ForegroundColor Yellow
Write-Host " - API Docs:       http://localhost:47000/docs" -ForegroundColor Yellow
Write-Host " - Flower (Tasks): http://localhost:47004" -ForegroundColor Yellow
Write-Host "------------------------------------------" -ForegroundColor Gray
Write-Host "상태를 확인하려면 .\scripts\status.ps1 을 실행하세요." -ForegroundColor Gray
