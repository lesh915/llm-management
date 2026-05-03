Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   LLM Management System - STATUS        " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

docker-compose ps

Write-Host ""
Write-Host "로그를 보려면 'docker-compose logs -f [서비스명]'을 실행하세요." -ForegroundColor Gray
