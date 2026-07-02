@echo off
title smallerDOCS Updater
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "LOG_FILE=%SCRIPT_DIR%update.log"

call "%SCRIPT_DIR%scripts\common.bat" :init "%LOG_FILE%"
if errorlevel 1 (
    echo Failed to initialize.
    pause
    exit /b 1
)

echo.
call "%SCRIPT_DIR%scripts\common.bat" :log "========================================"
call "%SCRIPT_DIR%scripts\common.bat" :log "  smallerDOCS - Update"
call "%SCRIPT_DIR%scripts\common.bat" :log "========================================"
echo.

rem === STEP 1: Check Python and Node ============================
call "%SCRIPT_DIR%scripts\common.bat" :require_python
if errorlevel 1 goto :error_pause

call "%SCRIPT_DIR%scripts\common.bat" :require_node
if errorlevel 1 goto :error_pause

rem === STEP 2: Check for Git ====================================
echo.
call "%SCRIPT_DIR%scripts\common.bat" :print_info "Checking for Git..."

where git >nul 2>&1
if errorlevel 1 (
    echo.
    call "%SCRIPT_DIR%scripts\common.bat" :print_warn "Git is not installed."
    call "%SCRIPT_DIR%scripts\common.bat" :log "  Automatic source code updates require Git."
    call "%SCRIPT_DIR%scripts\common.bat" :log "  You can manually download the latest version from:"
    call "%SCRIPT_DIR%scripts\common.bat" :log "  https://github.com/anomalyco/smallerDOCS"
    echo.
    call "%SCRIPT_DIR%scripts\common.bat" :print_info "Continuing with dependency updates only..."
) else (
    for /f "tokens=*" %%v in ('git --version') do set "GIT_VERSION=%%v"
    call "%SCRIPT_DIR%scripts\common.bat" :log "Found !GIT_VERSION!"

    rem Pull latest changes
    call "%SCRIPT_DIR%scripts\common.bat" :print_info "Pulling latest source code..."
    >>"%LOG_FILE%" 2>&1 (
        cd /d "%SCRIPT_DIR%"
        git pull
    )
    if errorlevel 1 (
        call "%SCRIPT_DIR%scripts\common.bat" :print_warn "Git pull had issues. Continuing anyway..."
    ) else (
        call "%SCRIPT_DIR%scripts\common.bat" :print_ok "Source code updated"
    )
)

rem === STEP 3: Update backend packages ==========================
echo.
call "%SCRIPT_DIR%scripts\common.bat" :print_info "Updating backend Python packages..."

>>"%LOG_FILE%" 2>&1 (
    "%SCRIPT_DIR%backend\.venv\Scripts\python.exe" -m pip install --upgrade -r "%SCRIPT_DIR%backend\requirements.txt"
)
if errorlevel 1 (
    call "%SCRIPT_DIR%scripts\common.bat" :print_warn "Backend update had issues."
) else (
    call "%SCRIPT_DIR%scripts\common.bat" :print_ok "Backend packages updated"
)

rem === STEP 4: Update frontend packages ==========================
echo.
call "%SCRIPT_DIR%scripts\common.bat" :print_info "Updating frontend packages..."

>>"%LOG_FILE%" 2>&1 (
    cd /d "%SCRIPT_DIR%frontend"
    npm update
)
if errorlevel 1 (
    call "%SCRIPT_DIR%scripts\common.bat" :print_warn "npm update had issues."
) else (
    call "%SCRIPT_DIR%scripts\common.bat" :print_ok "Frontend packages updated"
)

rem === STEP 5: Rebuild frontend ==================================
echo.
call "%SCRIPT_DIR%scripts\common.bat" :print_info "Rebuilding frontend..."

>>"%LOG_FILE%" 2>&1 (
    cd /d "%SCRIPT_DIR%frontend"
    npm run build
)
if errorlevel 1 (
    call "%SCRIPT_DIR%scripts\common.bat" :print_err "Frontend rebuild failed."
    call "%SCRIPT_DIR%scripts\common.bat" :log "  Check update.log for build errors."
    goto :error_pause
)
call "%SCRIPT_DIR%scripts\common.bat" :print_ok "Frontend rebuilt successfully"

rem === DONE ====================================================
echo.
call "%SCRIPT_DIR%scripts\common.bat" :print_ok "========================================"
call "%SCRIPT_DIR%scripts\common.bat" :print_ok "  Update complete!"
call "%SCRIPT_DIR%scripts\common.bat" :print_ok "========================================"
echo.
pause
exit /b 0

rem === ERROR ===================================================
:error_pause
echo.
call "%SCRIPT_DIR%scripts\common.bat" :print_err "Update failed."
call "%SCRIPT_DIR%scripts\common.bat" :log "  Check %LOG_FILE% for details."
echo.
pause
exit /b 1
