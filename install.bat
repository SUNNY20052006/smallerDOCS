@echo off
title smallerDOCS Installer
setlocal enabledelayedexpansion

rem Self-elevate to administrator if not already running as admin
net session >nul 2>&1
if errorlevel 1 (
    echo Requesting administrator privileges...
    powershell -NoProfile -Command "$p = Start-Process -FilePath '%~f0' -Verb RunAs -Wait -PassThru; exit $p.ExitCode"
    exit /b %errorlevel%
)

set "SCRIPT_DIR=%~dp0"
set "LOG_FILE=%SCRIPT_DIR%install.log"

call "%SCRIPT_DIR%scripts\common.bat" :init "%LOG_FILE%"
if errorlevel 1 (
    echo Failed to initialize installer.
    pause
    exit /b 1
)

echo.
call "%SCRIPT_DIR%scripts\common.bat" :log "========================================"
call "%SCRIPT_DIR%scripts\common.bat" :log "  smallerDOCS - Installation"
call "%SCRIPT_DIR%scripts\common.bat" :log "========================================"
echo.

rem === STEP 1: Check internet =================================
call "%SCRIPT_DIR%scripts\common.bat" :check_internet
if errorlevel 1 goto :error_pause

rem === STEP 2: Ensure Python 3.12+ =============================
echo.
call "%SCRIPT_DIR%scripts\common.bat" :log "--- Python ---"
call "%SCRIPT_DIR%scripts\common.bat" :ensure_python
if errorlevel 1 goto :error_pause

rem === STEP 3: Ensure Node.js & npm ============================
echo.
call "%SCRIPT_DIR%scripts\common.bat" :log "--- Node.js ---"
call "%SCRIPT_DIR%scripts\common.bat" :ensure_node
if errorlevel 1 goto :error_pause

rem === STEP 4: Create virtual environment ======================
echo.
call "%SCRIPT_DIR%scripts\common.bat" :log "--- Backend Setup ---"
call "%SCRIPT_DIR%scripts\common.bat" :print_info "Creating Python virtual environment..."

if not exist "%SCRIPT_DIR%backend\.venv" (
    >>"%LOG_FILE%" 2>&1 (
        cd /d "%SCRIPT_DIR%backend"
        "!PYTHON_CMD!" -m venv .venv
    )
    if errorlevel 1 (
        call "%SCRIPT_DIR%scripts\common.bat" :print_err "Failed to create virtual environment."
        goto :error_pause
    )
    call "%SCRIPT_DIR%scripts\common.bat" :print_ok "Virtual environment created"
) else (
    call "%SCRIPT_DIR%scripts\common.bat" :print_ok "Virtual environment already exists"
)

rem === STEP 5: Upgrade pip =====================================
call "%SCRIPT_DIR%scripts\common.bat" :print_info "Upgrading pip..."

>>"%LOG_FILE%" 2>&1 (
    "%SCRIPT_DIR%backend\.venv\Scripts\python.exe" -m pip install --upgrade pip
)
if errorlevel 1 (
    call "%SCRIPT_DIR%scripts\common.bat" :print_warn "pip upgrade had warnings, continuing..."
)

rem === STEP 6: Install backend dependencies ====================
echo.
call "%SCRIPT_DIR%scripts\common.bat" :print_info "Installing backend dependencies..."

>>"%LOG_FILE%" 2>&1 (
    "%SCRIPT_DIR%backend\.venv\Scripts\python.exe" -m pip install -r "%SCRIPT_DIR%backend\requirements.txt"
)
if errorlevel 1 (
    call "%SCRIPT_DIR%scripts\common.bat" :print_err "Failed to install backend dependencies."
    goto :error_pause
)
call "%SCRIPT_DIR%scripts\common.bat" :print_ok "Backend dependencies installed"

rem === STEP 7: Install frontend dependencies ====================
echo.
call "%SCRIPT_DIR%scripts\common.bat" :log "--- Frontend Setup ---"
call "%SCRIPT_DIR%scripts\common.bat" :print_info "Installing frontend dependencies..."

>>"%LOG_FILE%" 2>&1 (
    cd /d "%SCRIPT_DIR%frontend"
    npm install
)
if errorlevel 1 (
    call "%SCRIPT_DIR%scripts\common.bat" :print_err "Failed to install frontend dependencies."
    goto :error_pause
)
call "%SCRIPT_DIR%scripts\common.bat" :print_ok "Frontend dependencies installed"

rem === STEP 8: Build frontend ==================================
echo.
call "%SCRIPT_DIR%scripts\common.bat" :print_info "Building frontend..."

>>"%LOG_FILE%" 2>&1 (
    cd /d "%SCRIPT_DIR%frontend"
    npm run build
)
if errorlevel 1 (
    call "%SCRIPT_DIR%scripts\common.bat" :print_err "Frontend build failed."
    call "%SCRIPT_DIR%scripts\common.bat" :log "  Check install.log for build errors."
    goto :error_pause
)
call "%SCRIPT_DIR%scripts\common.bat" :print_ok "Frontend built successfully"

rem === STEP 9: Download OCR models ==============================
echo.
call "%SCRIPT_DIR%scripts\common.bat" :log "--- OCR Models ---"
call "%SCRIPT_DIR%scripts\common.bat" :print_info "Downloading OCR models..."
call "%SCRIPT_DIR%scripts\common.bat" :log "  This may take 2-5 minutes on a slow connection."
call "%SCRIPT_DIR%scripts\common.bat" :log "  Models are downloaded once and cached. This is not a frozen installer."

start "smallerDOCS_Install_Backend" /MIN /D "%SCRIPT_DIR%backend" "%SCRIPT_DIR%backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

call "%SCRIPT_DIR%scripts\common.bat" :wait_for_health "http://127.0.0.1:8000/health" 300
set "health_result=!errorlevel!"

call "%SCRIPT_DIR%scripts\common.bat" :kill_port 8000
timeout /t 2 /nobreak >nul

if !health_result! neq 0 (
    call "%SCRIPT_DIR%scripts\common.bat" :print_warn "OCR model download may not have completed."
    call "%SCRIPT_DIR%scripts\common.bat" :log "  The models will be downloaded when you first run the application."
)

rem === DONE ====================================================
echo.
call "%SCRIPT_DIR%scripts\common.bat" :print_ok "========================================"
call "%SCRIPT_DIR%scripts\common.bat" :print_ok "  Installation complete!"
call "%SCRIPT_DIR%scripts\common.bat" :print_ok "========================================"
echo.
call "%SCRIPT_DIR%scripts\common.bat" :log "You can now run smallerDOCS by double-clicking run.bat"
echo.
pause
exit /b 0

rem === ERROR HANDLER ==========================================
:error_pause
echo.
call "%SCRIPT_DIR%scripts\common.bat" :print_err "Installation failed."
call "%SCRIPT_DIR%scripts\common.bat" :log "  Check %LOG_FILE% for details."
echo.
pause
exit /b 1
