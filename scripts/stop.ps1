Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   LLM Management System - STOPPING      " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

Write-Host "[*] 모든 서비스를 종료하고 컨테이너를 제거합니다..." -ForegroundColor White
docker-compose down

Write-Host ""
Write-Host "시스템이 안전하게 종료되었습니다." -ForegroundColor Green
