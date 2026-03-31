@echo off
setlocal enabledelayedexpansion

set "ROOT=%~dp0"
set "VENV=%ROOT%.venv"
set "PYTHON=%VENV%\Scripts\python.exe"
set "THINKING_MODE=0"
set "THINKING_TEXT=OFF"

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
echo 1. Run full analysis (auto date)
echo 2. Run analysis for specific date
echo 3. Analyze single paper (arXiv ID)
echo 4. Analyze local PDF file
echo 5. Cache management
echo 6. Toggle thinking mode [%THINKING_TEXT%]
echo 7. Exit
echo.
set /p choice="Enter your choice (1-7): "

if "%choice%"=="1" goto run_all
if "%choice%"=="2" goto run_date
if "%choice%"=="3" goto run_arxiv
if "%choice%"=="4" goto run_local_pdf
if "%choice%"=="5" goto cache_menu
if "%choice%"=="6" goto toggle_thinking
if "%choice%"=="7" goto exit_tool

echo Invalid choice, please try again.
pause
goto menu

:toggle_thinking
if "%THINKING_MODE%"=="0" (
    set "THINKING_MODE=1"
    set "THINKING_TEXT=ON"
    echo Thinking mode ENABLED - AI will perform deeper analysis.
) else (
    set "THINKING_MODE=0"
    set "THINKING_TEXT=OFF"
    echo Thinking mode DISABLED - Standard analysis mode.
)
pause
goto menu

:run_all
echo === Running Full Analysis (Auto Date) ===
if not exist "%PYTHON%" (
    echo Error: Virtual environment not found. Please configure the environment first.
    goto fail
)
"%PYTHON%" src\main.py || goto fail
echo Operation completed.
pause
goto menu

:run_date
echo === Run Analysis for Specific Date ===
echo Format: YYYYMMDD or YYYYMMDD:YYYYMMDD (range)
echo Example: 20251225 or 20251220:20251225
set /p date_input="Enter date or date range: "
if "%date_input%"=="" (
    echo Date cannot be empty.
    pause
    goto menu
)
if not exist "%PYTHON%" (
    echo Error: Virtual environment not found. Please configure the environment first.
    goto fail
)
"%PYTHON%" src\main.py --date %date_input% || goto fail
echo Operation completed.
pause
goto menu

:run_arxiv
echo === Single Paper Analysis (arXiv ID) ===
echo Thinking mode: %THINKING_TEXT%
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
if "%THINKING_MODE%"=="1" (
    "%PYTHON%" src\main.py --arxiv %arxiv_id% -p %pages% --thinking || goto fail
) else (
    "%PYTHON%" src\main.py --arxiv %arxiv_id% -p %pages% || goto fail
)
echo Operation completed.
pause
goto menu

:run_local_pdf
echo === Local PDF Analysis ===
echo Thinking mode: %THINKING_TEXT%
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

if "%THINKING_MODE%"=="1" (
    "%PYTHON%" src\main.py --pdf "!selected_pdf!" -p %pages% --thinking || goto fail
) else (
    "%PYTHON%" src\main.py --pdf "!selected_pdf!" -p %pages% || goto fail
)
echo Operation completed.
pause
goto menu

:invalid_pdf
echo Invalid choice, please try again.
pause
goto menu

:cache_menu
cls
echo === Cache Management ===
echo 1. View cache statistics
echo 2. Clear all cache
echo 3. Clear classification cache
echo 4. Clear analysis cache
echo 5. Clear translation cache
echo 6. Back to main menu
echo.
set /p cache_choice="Enter your choice (1-6): "

if "%cache_choice%"=="1" goto cache_stats
if "%cache_choice%"=="2" goto cache_clear_all
if "%cache_choice%"=="3" goto cache_clear_classification
if "%cache_choice%"=="4" goto cache_clear_analysis
if "%cache_choice%"=="5" goto cache_clear_translation
if "%cache_choice%"=="6" goto menu

echo Invalid choice, please try again.
pause
goto cache_menu

:cache_stats
"%PYTHON%" src\main.py --cache-stats
pause
goto cache_menu

:cache_clear_all
"%PYTHON%" src\main.py --clear-cache
pause
goto cache_menu

:cache_clear_classification
"%PYTHON%" src\main.py --clear-cache classification
pause
goto cache_menu

:cache_clear_analysis
"%PYTHON%" src\main.py --clear-cache analysis
pause
goto cache_menu

:cache_clear_translation
"%PYTHON%" src\main.py --clear-cache translation
pause
goto cache_menu

:fail
echo Operation failed, please check the command output.
pause
goto menu

:exit_tool
echo Thank you for using!
endlocal
exit /b 0
