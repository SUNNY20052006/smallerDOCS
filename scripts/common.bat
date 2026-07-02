@echo off
set "COMMON_INITIALIZED="

rem === DISPATCHER ============================================
rem When called with arguments, dispatch to the requested label
if "%~1" neq "" (
    call :%~1 %2 %3 %4 %5 %6 %7 %8 %9
    exit /b %errorlevel%
)
exit /b 0

rem === INIT ==================================================
rem Sets PROJECT_ROOT, ESC, LOG_FILE
:init
setlocal enabledelayedexpansion
for %%i in ("%~dp0..") do set "PROJECT_ROOT=%%~fi\"
for /f "delims=#" %%a in ('prompt #$E#^& for %%b in ^(1^) do rem') do set "ESC=%%a"
set "LOG_FILE=%~1"
if defined LOG_FILE if exist "!LOG_FILE!" del /f /q "!LOG_FILE!" >nul 2>&1
if defined LOG_FILE echo ---- Log started %DATE% %TIME% ---- >"!LOG_FILE!"
endlocal & set "PROJECT_ROOT=%PROJECT_ROOT%" & set "ESC=%ESC%" & set "LOG_FILE=%LOG_FILE%"
exit /b 0

rem === LOG ===================================================
:log
echo %~1
if defined LOG_FILE >>"%LOG_FILE%" echo %DATE% %TIME% - %~1
exit /b 0

rem === PRINT_OK ==============================================
:print_ok
if not defined ESC for /f "delims=#" %%a in ('prompt #$E#^& for %%b in ^(1^) do rem') do set "ESC=%%a"
echo %ESC%[32m[OK]%ESC%[0m %~1
if defined LOG_FILE >>"%LOG_FILE%" echo %DATE% %TIME% - [OK] %~1
exit /b 0

rem === PRINT_ERR =============================================
:print_err
if not defined ESC for /f "delims=#" %%a in ('prompt #$E#^& for %%b in ^(1^) do rem') do set "ESC=%%a"
echo %ESC%[31m[ER]%ESC%[0m %~1
if defined LOG_FILE >>"%LOG_FILE%" echo %DATE% %TIME% - [ER] %~1
exit /b 0

rem === PRINT_WARN ============================================
:print_warn
if not defined ESC for /f "delims=#" %%a in ('prompt #$E#^& for %%b in ^(1^) do rem') do set "ESC=%%a"
echo %ESC%[33m[!]%ESC%[0m %~1
if defined LOG_FILE >>"%LOG_FILE%" echo %DATE% %TIME% - [WARN] %~1
exit /b 0

rem === PRINT_INFO ============================================
:print_info
if not defined ESC for /f "delims=#" %%a in ('prompt #$E#^& for %%b in ^(1^) do rem') do set "ESC=%%a"
echo %ESC%[36m[i]%ESC%[0m %~1
if defined LOG_FILE >>"%LOG_FILE%" echo %DATE% %TIME% - [INFO] %~1
exit /b 0

rem === CHECK_INTERNET ========================================
rem Returns: errorlevel 0 if connected, 1 otherwise
:check_internet
call :print_info "Checking internet connection..."
ping -n 1 -w 3000 8.8.8.8 >nul 2>&1
if errorlevel 1 ping -n 1 -w 3000 1.1.1.1 >nul 2>&1
if errorlevel 1 (
    call :print_err "No internet connection detected."
    exit /b 1
)
call :print_ok "Internet connection detected"
exit /b 0

rem === REQUIRE_PYTHON ========================================
rem Returns: errorlevel 0 if Python 3.12+ found, 1 otherwise
rem Sets: PYTHON_CMD to "python" or "py"
:require_python
setlocal enabledelayedexpansion
call :print_info "Checking Python installation..."
set "PYTHON_CMD="

python --version >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=python"
if not defined PYTHON_CMD (
    py --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=py"
)
if not defined PYTHON_CMD (
    call :print_err "Python is not installed."
    call :log "  Visit https://www.python.org/downloads/ to install Python 3.12+"
    call :log "  IMPORTANT: Check 'Add Python to PATH' during installation"
    endlocal & exit /b 1
)

for /f "tokens=2 delims= " %%v in ('!PYTHON_CMD! --version 2^>^&1') do set "PY_VERSION=%%v"
if not defined PY_VERSION (
    call :print_err "Could not determine Python version."
    endlocal & exit /b 1
)
call :log "Found Python version: !PY_VERSION!"

for /f "tokens=1,2 delims=." %%a in ("!PY_VERSION!") do (
    if %%a lss 3 (
        call :print_err "Python 3.12+ required, found !PY_VERSION!"
        endlocal & exit /b 1
    )
    if %%a equ 3 if %%b lss 12 (
        call :print_err "Python 3.12+ required, found !PY_VERSION!"
        endlocal & exit /b 1
    )
)
call :print_ok "Python !PY_VERSION! detected"
endlocal & set "PYTHON_CMD=%PYTHON_CMD%"
exit /b 0

rem === REQUIRE_NODE ==========================================
rem Returns: errorlevel 0 if Node.js found, 1 otherwise
rem Sets: NODE_CMD to "node"
:require_node
setlocal enabledelayedexpansion
call :print_info "Checking Node.js installation..."

where node >nul 2>&1
if errorlevel 1 (
    call :print_err "Node.js is not installed."
    call :log "  Visit https://nodejs.org/ to download the latest LTS version"
    endlocal & exit /b 1
)

for /f "tokens=*" %%v in ('node --version') do set "NODE_VERSION=%%v"
call :log "Found Node.js !NODE_VERSION!"
call :print_ok "Node.js !NODE_VERSION! detected"
endlocal & set "NODE_CMD=node"
exit /b 0

rem === REQUIRE_NPM ===========================================
rem Returns: errorlevel 0 if npm found, 1 otherwise
rem Sets: NPM_CMD to "npm"
:require_npm
setlocal enabledelayedexpansion
call :print_info "Checking npm installation..."

where npm >nul 2>&1
if errorlevel 1 (
    call :print_err "npm is not installed."
    call :log "  npm should be included with Node.js."
    call :log "  Reinstall Node.js from https://nodejs.org/"
    endlocal & exit /b 1
)

for /f "tokens=*" %%v in ('npm --version') do set "NPM_VERSION=%%v"
call :log "Found npm !NPM_VERSION!"
call :print_ok "npm !NPM_VERSION! detected"
endlocal & set "NPM_CMD=npm"
exit /b 0

rem === CHECK_PORT ============================================
rem Returns: errorlevel 0 if port is in use, 1 if free
:check_port
set "port=%~1"
netstat -ano 2>nul | findstr /C:":%port% " >nul 2>&1
if errorlevel 1 exit /b 1
exit /b 0

rem === WAIT_FOR_HEALTH =======================================
rem Usage: call "scripts\common.bat" :wait_for_health <url> <max_seconds>
rem Returns: errorlevel 0 if healthy within timeout, 1 otherwise
:wait_for_health
setlocal enabledelayedexpansion
set "TARGET_URL=%~1"
set "MAX_WAIT=%~2"
if not defined MAX_WAIT set "MAX_WAIT=120"
set /a elapsed=0

call :print_info "Waiting for backend (max !MAX_WAIT!s)..."

:health_loop
if !elapsed! geq !MAX_WAIT! (
    call :print_err "Backend did not become healthy within !MAX_WAIT!s"
    endlocal & exit /b 1
)

powershell -NoProfile -Command ^
    "try { $r = Invoke-RestMethod -Uri '!TARGET_URL!' -ErrorAction Stop; if ($r.status -eq 'ok' -and $r.ocr_engine_loaded -eq $true) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1

if not errorlevel 1 (
    call :print_ok "Backend is healthy and OCR models loaded"
    endlocal & exit /b 0
)

timeout /t 3 /nobreak >nul
set /a elapsed+=3
goto health_loop

rem === CONFIRM ===============================================
rem Returns: errorlevel 0 if Yes, 1 if No
:confirm
set "prompt_msg=%~1"
if not defined prompt_msg set "prompt_msg=Are you sure?"
choice /c YN /n /m "%prompt_msg% [Y/N]: "
exit /b %errorlevel%

rem === WAIT_FOR_FRONTEND =====================================
rem Returns: errorlevel 0 if frontend responds within timeout, 1 otherwise
:wait_for_frontend
setlocal enabledelayedexpansion
set "MAX_WAIT=%~1"
if not defined MAX_WAIT set "MAX_WAIT=60"
set /a elapsed=0

call :print_info "Waiting for frontend (max !MAX_WAIT!s)..."

:fe_loop
if !elapsed! geq !MAX_WAIT! (
    call :print_err "Frontend did not respond within !MAX_WAIT!s"
    endlocal & exit /b 1
)

powershell -NoProfile -Command ^
    "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:3000' -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1

if not errorlevel 1 (
    endlocal & exit /b 0
)

timeout /t 2 /nobreak >nul
set /a elapsed+=2
goto fe_loop
