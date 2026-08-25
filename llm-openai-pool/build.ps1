# openai-pool 构建脚本
# 用法: .\build.ps1

$ErrorActionPreference = "Stop"

Write-Host "=== 运行测试 ==="
go test ./... -count=1 -timeout=60s
if ($LASTEXITCODE -ne 0) {
    Write-Host "测试失败,退出" -ForegroundColor Red
    exit 1
}

Write-Host "=== 编译 ==="
go build -ldflags="-s -w" -o openai-pool.exe .
if ($LASTEXITCODE -ne 0) {
    Write-Host "编译失败" -ForegroundColor Red
    exit 1
}

Write-Host "=== 完成 ===" -ForegroundColor Green
Write-Host "  产物: openai-pool.exe ($((Get-Item openai-pool.exe).Length / 1MB -as [int]) MB)"
Write-Host "  启动: .\openai-pool.exe -config config.json"