@echo off
title smallerDOCS Launcher
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "LOG_FILE=%SCRIPT_DIR%run.log"

call "%SCRIPT_DIR%scripts\common.bat" :init "%LOG_FILE%"
if errorlevel 1 (
    echo Failed to initialize.
    pause
    exit /b 1
)

echo.
call "%SCRIPT_DIR%scripts\common.bat" :log "========================================"
call "%SCRIPT_DIR%scripts\common.bat" :log "  smallerDOCS - Starting Application"
call "%SCRIPT_DIR%scripts\common.bat" :log "========================================"
echo.

rem === STEP 1: Verify prerequisites ============================
call "%SCRIPT_DIR%scripts\common.bat" :require_python
if errorlevel 1 goto :need_install

call "%SCRIPT_DIR%scripts\common.bat" :require_node
if errorlevel 1 goto :need_install

rem Check virtual environment exists
if not exist "%SCRIPT_DIR%backend\.venv\Scripts\python.exe" (
    call "%SCRIPT_DIR%scripts\common.bat" :print_err "Backend virtual environment not found."
    goto :need_install
)

rem Check frontend dependencies
if not exist "%SCRIPT_DIR%frontend\node_modules\.package-lock.json" (
    if not exist "%SCRIPT_DIR%frontend\node_modules" (
        call "%SCRIPT_DIR%scripts\common.bat" :print_err "Frontend dependencies not installed."
        goto :need_install
    )
)

rem Check frontend build exists
if not exist "%SCRIPT_DIR%frontend\.next" (
    call "%SCRIPT_DIR%scripts\common.bat" :print_warn "Frontend build not found. Running build..."
    >>"%LOG_FILE%" 2>&1 (
        cd /d "%SCRIPT_DIR%frontend"
        npm run build
    )
    if errorlevel 1 (
        call "%SCRIPT_DIR%scripts\common.bat" :print_err "Frontend build failed."
        goto :error_pause
    )
    call "%SCRIPT_DIR%scripts\common.bat" :print_ok "Frontend built"
)

rem === STEP 2: Check ports ======================================
echo.
call "%SCRIPT_DIR%scripts\common.bat" :print_info "Checking port availability..."

call "%SCRIPT_DIR%scripts\common.bat" :check_port 8000
if not errorlevel 1 (
    call "%SCRIPT_DIR%scripts\common.bat" :print_err "Port 8000 is already in use."
    call "%SCRIPT_DIR%scripts\common.bat" :log "  Another application is using port 8000."
    call "%SCRIPT_DIR%scripts\common.bat" :log "  Close the other application or change its port configuration."
    goto :error_pause
)

call "%SCRIPT_DIR%scripts\common.bat" :check_port 3000
if not errorlevel 1 (
    call "%SCRIPT_DIR%scripts\common.bat" :print_err "Port 3000 is already in use."
    call "%SCRIPT_DIR%scripts\common.bat" :log "  Another application is using port 3000."
    call "%SCRIPT_DIR%scripts\common.bat" :log "  Close the other application or change its port configuration."
    goto :error_pause
)

call "%SCRIPT_DIR%scripts\common.bat" :print_ok "Ports 8000 and 3000 are available"

rem === STEP 3: Start backend ====================================
echo.
call "%SCRIPT_DIR%scripts\common.bat" :print_info "Starting backend server..."

start "smallerDOCS Backend" /MIN /D "%SCRIPT_DIR%backend" "%SCRIPT_DIR%backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

call "%SCRIPT_DIR%scripts\common.bat" :wait_for_health "http://127.0.0.1:8000/health" 120
if errorlevel 1 (
    taskkill /F /FI "WINDOWTITLE eq smallerDOCS Backend" >nul 2>&1
    goto :error_pause
)

rem === STEP 4: Start frontend ====================================
echo.
call "%SCRIPT_DIR%scripts\common.bat" :print_info "Starting frontend..."

start "smallerDOCS Frontend" /D "%SCRIPT_DIR%frontend" cmd /c "npm start" 2>nul

call "%SCRIPT_DIR%scripts\common.bat" :wait_for_frontend 60
if errorlevel 1 (
    call "%SCRIPT_DIR%scripts\common.bat" :print_warn "Frontend did not respond via npm start, trying dev server..."
    start "smallerDOCS Frontend" /D "%SCRIPT_DIR%frontend" cmd /c "npm run dev" 2>nul
    call "%SCRIPT_DIR%scripts\common.bat" :wait_for_frontend 60
    if errorlevel 1 (
        call "%SCRIPT_DIR%scripts\common.bat" :print_warn "Frontend start delayed, continuing..."
    )
)

call "%SCRIPT_DIR%scripts\common.bat" :print_ok "Frontend is running"

rem === STEP 5: Open browser ====================================
echo.
call "%SCRIPT_DIR%scripts\common.bat" :print_info "Opening application in your default browser..."
start http://localhost:3000

rem === DONE ====================================================
echo.
call "%SCRIPT_DIR%scripts\common.bat" :print_ok "========================================"
call "%SCRIPT_DIR%scripts\common.bat" :print_ok "  smallerDOCS is running!"
call "%SCRIPT_DIR%scripts\common.bat" :print_ok "========================================"
echo.
call "%SCRIPT_DIR%scripts\common.bat" :log "  Backend:  http://127.0.0.1:8000"
call "%SCRIPT_DIR%scripts\common.bat" :log "  Frontend: http://localhost:3000"
echo.
echo  Close the "smallerDOCS Backend" and "smallerDOCS Frontend"
echo  windows to stop the application.
echo.
pause
exit /b 0

rem === NEED INSTALL ============================================
:need_install
echo.
call "%SCRIPT_DIR%scripts\common.bat" :print_err "Prerequisites are missing."
call "%SCRIPT_DIR%scripts\common.bat" :log "  Please run install.bat first to set up the application."
echo.
pause
exit /b 1

rem === ERROR ===================================================
:error_pause
echo.
call "%SCRIPT_DIR%scripts\common.bat" :print_err "Failed to start smallerDOCS."
call "%SCRIPT_DIR%scripts\common.bat" :log "  Check %LOG_FILE% for details."
echo.
pause
exit /b 1
