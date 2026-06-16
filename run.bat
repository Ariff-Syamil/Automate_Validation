@echo off
:: ============================================================================
:: Automate Validation – Quick Launcher
:: ============================================================================
:: Usage:
::   run.bat              Launch the GUI
::   run.bat gui          Launch the GUI
::   run.bat validate     Validate test cases (Automate 5)
::   run.bat report       Generate Markdown report
::   run.bat report csv   Generate CSV report to automate_5_results.csv
::   run.bat summary      Print priority / automation-status counts
:: ============================================================================

setlocal
@REM set "ROOT=%~dp0"
@REM set "VENV=%ROOT%.venv"
set "PYTHON="C:\Users\midrus\AppData\Local\Programs\Python\Python313\python.exe""

:: Check for venv
if not exist "%PYTHON%" (
    echo [setup] Creating virtual environment...
    python -m venv "%VENV%"
    echo [setup] Installing dependencies...
    "%PYTHON%" -m pip install --upgrade pip >nul 2>&1
    "%PYTHON%" -m pip install -r "%ROOT%requirements.txt"
    echo.
)

:: Default command is "gui"
set "CMD=%~1"
if "%CMD%"=="" set "CMD=gui"

:: ── GUI ─────────────────────────────────────────────────────────────────────
if /i "%CMD%"=="gui" (
    echo [automate_validation] Launching GUI...
    start "" "%PYTHON%" "%ROOT%scripts\gui.py"
    goto :eof
)

:: ── Validate ────────────────────────────────────────────────────────────────
if /i "%CMD%"=="validate" (
    set "VER=%~2"
    if "%VER%"=="" set "VER=automate_5"
    echo [automate_validation] Validating %VER%...
    "%PYTHON%" "%ROOT%scripts\manage_tests.py" validate %VER%
    goto :eof
)

:: ── Report ──────────────────────────────────────────────────────────────────
if /i "%CMD%"=="report" (
    set "FMT=%~2"
    if "%FMT%"=="" set "FMT=markdown"
    if /i "%FMT%"=="csv" (
        echo [automate_validation] Generating CSV report...
        "%PYTHON%" "%ROOT%scripts\manage_tests.py" report automate_5 --format csv -o "%ROOT%automate_5_results.csv"
    ) else (
        echo [automate_validation] Generating Markdown report...
        "%PYTHON%" "%ROOT%scripts\manage_tests.py" report automate_5
    )
    goto :eof
)

:: ── Summary ─────────────────────────────────────────────────────────────────
if /i "%CMD%"=="summary" (
    "%PYTHON%" "%ROOT%scripts\manage_tests.py" summary automate_5
    goto :eof
)

echo Unknown command: %CMD%
echo Usage: run.bat [gui ^| validate ^| report ^| report csv ^| summary]
