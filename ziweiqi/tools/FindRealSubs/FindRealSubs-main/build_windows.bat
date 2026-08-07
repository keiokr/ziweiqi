@echo off
setlocal
cd /d %~dp0
if not exist dist mkdir dist
go mod tidy
go build -trimpath -ldflags "-s -w" -o dist\FindRealSubs.exe .
echo.
echo Build done:
echo   %cd%\dist\FindRealSubs.exe
pause
