@echo off
setlocal enabledelayedexpansion

set "ROOT=%~dp0"
set "VENV=%ROOT%.venv"
set "PYTHON=%VENV%\Scripts\python.exe"

cd /d "%ROOT%" || (
    echo Unable to switch to project directory %ROOT%
    exit /b 1
)

:menu
cls
echo ========================================
echo ArXiv Paper Tracker - Interactive Tool
echo ========================================
echo.
echo Please select an operation:
echo 1. Run full analysis
echo 2. Analyze single paper
echo 3. Exit
echo.
set /p choice="Enter your choice (1-3): "

if "%choice%"=="1" goto run_all
if "%choice%"=="2" goto run_single
if "%choice%"=="3" goto exit_tool

echo Invalid choice, please try again.
pause
goto menu

:run_all
echo === Running Full Analysis ===
if not exist "%PYTHON%" (
    echo Error: Virtual environment not found. Please configure the environment first.
    goto fail
)
"%PYTHON%" src\main.py || goto fail
echo Operation completed.
pause
goto menu

:run_single
echo === Single Paper Analysis ===
set /p arxiv_id="Enter arXiv ID (e.g., 2305.09582): "
if "%arxiv_id%"=="" (
    echo arXiv ID cannot be empty.
    pause
    goto menu
)
set /p pages="Enter number of pages to extract (default 10, or 'all'): "
if "%pages%"=="" set pages=10
if not exist "%PYTHON%" (
    echo Error: Virtual environment not found. Please configure the environment first.
    goto fail
)
"%PYTHON%" src\main.py --single %arxiv_id% -p %pages% || goto fail
echo Operation completed.
pause
goto menu

:fail
echo Operation failed, please check the command output.
pause
goto menu

:exit_tool
echo Thank you for using!
endlocal
exit /b 0
