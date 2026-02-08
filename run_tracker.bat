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
echo arXiv Paper Tracker - Interactive Tool
echo ========================================
echo.
echo Please select an operation:
echo 1. Run full analysis
echo 2. Analyze single paper (arXiv ID)
echo 3. Analyze local PDF
echo 4. Exit
echo.
set /p choice="Enter your choice (1-4): "

if "%choice%"=="1" goto run_all
if "%choice%"=="2" goto run_single
if "%choice%"=="3" goto run_local_pdf
if "%choice%"=="4" goto exit_tool

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
echo === Single Paper Analysis (arXiv ID) ===
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
"%PYTHON%" src\main.py --arxiv %arxiv_id% -p %pages% || goto fail
echo Operation completed.
pause
goto menu

:run_local_pdf
echo === Local PDF Analysis ===
if not exist "papers" (
    echo Papers folder not found. Creating 'papers' folder...
    mkdir papers
    echo Please put your PDF files in the 'papers' folder and try again.
    pause
    goto menu
)

echo.
echo Available PDF files in 'papers' folder:
echo.
set count=0
for %%f in (papers\*.pdf) do (
    set /a count+=1
    echo !count!. %%~nxf
    set "pdf_!count!=%%f"
)

if %count%==0 (
    echo No PDF files found in 'papers' folder.
    echo Please put your PDF files in the 'papers' folder and try again.
    pause
    goto menu
)

echo.
set /p pdf_choice="Enter the number of PDF to analyze (0 to cancel): "
if "%pdf_choice%"=="0" goto menu
if %pdf_choice% lss 1 goto invalid_pdf
if %pdf_choice% gtr %count% goto invalid_pdf

set "selected_pdf=!pdf_%pdf_choice%!"
echo Selected: !selected_pdf!
echo.

set /p pages="Enter number of pages to extract (default 10, or 'all'): "
if "%pages%"=="" set pages=10

if not exist "%PYTHON%" (
    echo Error: Virtual environment not found. Please configure the environment first.
    goto fail
)

"%PYTHON%" src\main.py --pdf "!selected_pdf!" -p %pages% || goto fail
echo Operation completed.
pause
goto menu

:invalid_pdf
echo Invalid choice, please try again.
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
