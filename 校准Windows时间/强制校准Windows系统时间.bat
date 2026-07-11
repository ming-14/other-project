@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: 强制校准 Windows 系统时间
:: 需要以管理员权限运行

:: 检查是否以管理员权限运行
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 请求管理员权限...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo ===== Windows 系统时间强制校准 =====

:: 显示当前时间
for /f "tokens=*" %%a in ('wmic os get localdatetime ^| find "."') do set dt=%%a
set CURRENT_DATE=%dt:~0,4%-%dt:~4,2%-%dt:~6,2% %dt:~8,2%:%dt:~10,2%:%dt:~12,2%
echo.
echo [当前系统时间] %CURRENT_DATE%

net stop w32time /y >nul 2>&1
w32tm /unregister >nul 2>&1
w32tm /register
net start w32time >nul 2>&1

:: 配置 NTP 服务器并强制同步
w32tm /config /manualpeerlist:"time.windows.com time.nist.gov pool.ntp.org" /syncfromflags:manual /reliable:yes /update

echo.
echo 正在从 NTP 服务器获取时间...
w32tm /resync /force

:: 显示同步后的时间
echo [同步后时间] %date% %time%

:: 显示时间服务状态
echo.
echo ===== 时间服务状态 =====
w32tm /query /status

echo.
echo ===== 时间源信息 =====
w32tm /query /peers

echo.
echo [完成] 系统时间校准完毕！
