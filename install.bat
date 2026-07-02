@echo off
title smallerDOCS Installer
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "LOG_FILE=%SCRIPT_DIR%install.log"

rem Initialize common utilities
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

rem === STEP 2: Detect Python ==================================
:retry_python
call "%SCRIPT_DIR%scripts\common.bat" :require_python
if errorlevel 1 (
    echo.
    echo  =================================================================
    echo   Python 3.12 or newer is required but was not found.
    echo.
    echo   1. Visit https://www.python.org/downloads/
    echo   2. Download Python 3.12 or newer
    echo   3. Run the installer
    echo   4. IMPORTANT: Check "Add Python to PATH" during installation
    echo   5. After installation, restart this installer
    echo  =================================================================
    echo.
    pause
    goto retry_python
)

rem === STEP 3: Detect Node.js ==================================
:retry_node
call "%SCRIPT_DIR%scripts\common.bat" :require_node
if errorlevel 1 (
    echo.
    echo  =================================================================
    echo   Node.js is required but was not found.
    echo.
    echo   1. Visit https://nodejs.org/
    echo   2. Download the latest LTS version
    echo   3. Run the installer
    echo   4. After installation, restart this installer
    echo  =================================================================
    echo.
    pause
    goto retry_node
)

rem === STEP 4: Detect npm =====================================
call "%SCRIPT_DIR%scripts\common.bat" :require_npm
if errorlevel 1 goto :error_pause

rem === STEP 5: Create virtual environment ======================
echo.
call "%SCRIPT_DIR%scripts\common.bat" :print_info "Creating Python virtual environment..."

if not exist "%SCRIPT_DIR%backend\.venv" (
    >>"%LOG_FILE%" 2>&1 (
        cd /d "%SCRIPT_DIR%backend"
        "%PYTHON_CMD%" -m venv .venv
    )
    if errorlevel 1 (
        call "%SCRIPT_DIR%scripts\common.bat" :print_err "Failed to create virtual environment."
        goto :error_pause
    )
    call "%SCRIPT_DIR%scripts\common.bat" :print_ok "Virtual environment created"
) else (
    call "%SCRIPT_DIR%scripts\common.bat" :print_ok "Virtual environment already exists"
)

rem === STEP 6: Upgrade pip ====================================
call "%SCRIPT_DIR%scripts\common.bat" :print_info "Upgrading pip..."

>>"%LOG_FILE%" 2>&1 (
    "%SCRIPT_DIR%backend\.venv\Scripts\python.exe" -m pip install --upgrade pip
)
if errorlevel 1 (
    call "%SCRIPT_DIR%scripts\common.bat" :print_warn "pip upgrade had warnings, continuing..."
)

rem === STEP 7: Install backend dependencies ====================
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

rem === STEP 8: Install frontend dependencies ====================
echo.
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

rem === STEP 9: Build frontend ==================================
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

rem === STEP 10: Download OCR models ============================
echo.
call "%SCRIPT_DIR%scripts\common.bat" :print_info "Downloading OCR models (this may take a while)..."

rem Start backend to trigger model download
start "smallerDOCS_Install_Backend" /MIN /D "%SCRIPT_DIR%backend" "%SCRIPT_DIR%backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

rem Wait for health endpoint (models are loaded when healthy)
call "%SCRIPT_DIR%scripts\common.bat" :wait_for_health "http://127.0.0.1:8000/health" 120
set "health_result=!errorlevel!"

rem Stop the backend
taskkill /F /FI "WINDOWTITLE eq smallerDOCS_Install_Backend" >nul 2>&1
timeout /t 2 /nobreak >nul

if !health_result! neq 0 (
    call "%SCRIPT_DIR%scripts\common.bat" :print_err "OCR model download may not have completed."
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
