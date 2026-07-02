@echo off
title smallerDOCS Uninstaller
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"

rem Initialize common (no log file for uninstall)
call "%SCRIPT_DIR%scripts\common.bat" :init
if errorlevel 1 (
    echo Failed to initialize.
    pause
    exit /b 1
)

echo.
call "%SCRIPT_DIR%scripts\common.bat" :print_warn "========================================"
call "%SCRIPT_DIR%scripts\common.bat" :print_warn "  smallerDOCS - Uninstall"
call "%SCRIPT_DIR%scripts\common.bat" :print_warn "========================================"
echo.
call "%SCRIPT_DIR%scripts\common.bat" :log "This will remove installed dependencies and caches."
call "%SCRIPT_DIR%scripts\common.bat" :log "Your source code and documents will NOT be affected."
echo.

rem === STEP 1: Confirm =========================================
call "%SCRIPT_DIR%scripts\common.bat" :confirm "Are you sure you want to uninstall smallerDOCS?"
if errorlevel 2 goto :cancelled

echo.
call "%SCRIPT_DIR%scripts\common.bat" :print_info "Uninstalling..."

rem === STEP 2: Remove virtual environment ======================
if exist "%SCRIPT_DIR%backend\.venv" (
    call "%SCRIPT_DIR%scripts\common.bat" :print_info "Removing Python virtual environment..."
    rmdir /s /q "%SCRIPT_DIR%backend\.venv" >nul 2>&1
    if errorlevel 1 (
        call "%SCRIPT_DIR%scripts\common.bat" :print_warn "Could not remove .venv (may require admin rights)"
    ) else (
        call "%SCRIPT_DIR%scripts\common.bat" :print_ok "Virtual environment removed"
    )
) else (
    call "%SCRIPT_DIR%scripts\common.bat" :log "Virtual environment not found, skipping"
)

rem === STEP 3: Remove node_modules ==============================
if exist "%SCRIPT_DIR%frontend\node_modules" (
    call "%SCRIPT_DIR%scripts\common.bat" :print_info "Removing frontend dependencies..."
    rmdir /s /q "%SCRIPT_DIR%frontend\node_modules" >nul 2>&1
    if errorlevel 1 (
        call "%SCRIPT_DIR%scripts\common.bat" :print_warn "Could not remove node_modules (may require admin rights)"
    ) else (
        call "%SCRIPT_DIR%scripts\common.bat" :print_ok "Frontend dependencies removed"
    )
) else (
    call "%SCRIPT_DIR%scripts\common.bat" :log "node_modules not found, skipping"
)

rem === STEP 4: Remove .next build cache =========================
if exist "%SCRIPT_DIR%frontend\.next" (
    call "%SCRIPT_DIR%scripts\common.bat" :print_info "Removing frontend build cache..."
    rmdir /s /q "%SCRIPT_DIR%frontend\.next" >nul 2>&1
    if errorlevel 1 (
        call "%SCRIPT_DIR%scripts\common.bat" :print_warn "Could not remove .next (may require admin rights)"
    ) else (
        call "%SCRIPT_DIR%scripts\common.bat" :print_ok "Build cache removed"
    )
) else (
    call "%SCRIPT_DIR%scripts\common.bat" :log ".next not found, skipping"
)

rem === STEP 5: Remove __pycache__ directories ===================
call "%SCRIPT_DIR%scripts\common.bat" :print_info "Removing Python cache files..."
set "CACHE_COUNT=0"
for /f "delims=" %%d in ('dir /s /b /ad "%SCRIPT_DIR%" 2^>nul ^| findstr /E /I "__pycache__"') do (
    rmdir /s /q "%%d" >nul 2>&1
    if not errorlevel 1 set /a CACHE_COUNT+=1
)
if !CACHE_COUNT! gtr 0 (
    call "%SCRIPT_DIR%scripts\common.bat" :print_ok "Removed !CACHE_COUNT! Python cache director(ies)"
) else (
    call "%SCRIPT_DIR%scripts\common.bat" :log "No Python cache found"
)

rem === STEP 6: Remove log files =================================
call "%SCRIPT_DIR%scripts\common.bat" :print_info "Removing log files..."
for %%f in ("%SCRIPT_DIR%install.log" "%SCRIPT_DIR%run.log" "%SCRIPT_DIR%update.log") do (
    if exist "%%f" (
        del /f /q "%%f" >nul 2>&1
    )
)
call "%SCRIPT_DIR%scripts\common.bat" :print_ok "Log files removed"

rem === DONE ====================================================
echo.
call "%SCRIPT_DIR%scripts\common.bat" :print_ok "========================================"
call "%SCRIPT_DIR%scripts\common.bat" :print_ok "  Uninstall complete!"
call "%SCRIPT_DIR%scripts\common.bat" :print_ok "========================================"
echo.
call "%SCRIPT_DIR%scripts\common.bat" :log "To complete the removal, you may delete this folder manually."
echo.
pause
exit /b 0

rem === CANCELLED ===============================================
:cancelled
echo.
call "%SCRIPT_DIR%scripts\common.bat" :print_info "Uninstall cancelled."
echo.
pause
exit /b 0
