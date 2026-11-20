@echo off
setlocal
set "HHC="
if exist "C:\Program Files (x86)\HTML Help Workshop\hhc.exe" set "HHC=C:\Program Files (x86)\HTML Help Workshop\hhc.exe"
if exist "C:\Program Files\HTML Help Workshop\hhc.exe" set "HHC=C:\Program Files\HTML Help Workshop\hhc.exe"
if "%HHC%"=="" (
    where hhc.exe >nul 2>&1 && set "HHC=hhc.exe"
)
if "%HHC%"=="" (
    echo [Error] Microsoft HTML Help Workshop (hhc.exe) is not installed.
    echo Install HTML Help Workshop or open ..\html\index.html directly in your browser.
    exit /b 1
)
echo Compiling pyaudiogaming.chm...
"%HHC%" pyaudiogaming.hhp
echo Done! Output: %cd%\pyaudiogaming.chm
