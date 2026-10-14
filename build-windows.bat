@echo off
rem One command for the Windows PC: build, test, package and benchmark SailingSim (see docs\windows\README.md).
rem Double-click it, or run from a terminal with options, e.g.  build-windows.bat -Visual   or   build-windows.bat -SkipTests
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\all.ps1" %*
set CODE=%ERRORLEVEL%
echo.
if "%CODE%"=="0" echo All steps passed.
if not "%CODE%"=="0" echo A step failed, exit %CODE%. Logs are in Artifacts\.
rem Keep the window open when double-clicked.
echo %CMDCMDLINE% | find /i "%~0" >nul && pause
exit /b %CODE%
