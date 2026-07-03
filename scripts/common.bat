@echo off
set "COMMON_INITIALIZED="

rem === DISPATCHER ============================================
if "%~1" neq "" (
    call :%~1 %2 %3 %4 %5 %6 %7 %8 %9
    exit /b %errorlevel%
)
exit /b 0

rem === INIT ==================================================
:init
setlocal enabledelayedexpansion
for %%i in ("%~dp0..") do set "PROJECT_ROOT=%%~fi\"
for /f "delims=#" %%a in ('prompt #$E#^& for %%b in ^(1^) do rem') do set "ESC=%%a"
set "LOG_FILE=%~1"
if defined LOG_FILE if exist "!LOG_FILE!" del /f /q "!LOG_FILE!" >nul 2>&1
if defined LOG_FILE echo ---- Log started %DATE% %TIME% ---- >"!LOG_FILE!"
set "_SV_PROJECT_ROOT=!PROJECT_ROOT!"
set "_SV_ESC=!ESC!"
set "_SV_LOG_FILE=!LOG_FILE!"
endlocal & set "PROJECT_ROOT=%_SV_PROJECT_ROOT%" & set "ESC=%_SV_ESC%" & set "LOG_FILE=%_SV_LOG_FILE%"
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
:check_internet
call :print_info "Checking internet connection..."
ping -n 1 -w 3000 8.8.8.8 >nul 2>&1
if errorlevel 1 ping -n 1 -w 3000 1.1.1.1 >nul 2>&1
if errorlevel 1 ping -n 1 -w 3000 google.com >nul 2>&1
if errorlevel 1 (
    call :print_err "No internet connection detected."
    exit /b 1
)
call :print_ok "Internet connection detected"
exit /b 0

rem === REQUIRE_PYTHON ========================================
:require_python
setlocal enabledelayedexpansion
set "PYTHON_CMD="

call :log "  Searching for Python..."

python --version >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=python"
if not defined PYTHON_CMD (
    py --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=py"
)
if not defined PYTHON_CMD (
    call :log "  Python command not found on PATH."
    endlocal & exit /b 1
)

for /f "tokens=2 delims= " %%v in ('!PYTHON_CMD! --version 2^>^&1') do set "PY_VERSION=%%v"
if not defined PY_VERSION (
    call :log "  Could not parse Python version."
    endlocal & exit /b 1
)

call :log "  Found Python !PY_VERSION! at '!PYTHON_CMD!'"

for /f "tokens=1,2 delims=." %%a in ("!PY_VERSION!") do (
    if %%a lss 3 (
        call :log "  Python major version %%a is too old (need 3.x)."
        endlocal & exit /b 1
    )
    if %%a equ 3 if %%b lss 12 (
        call :log "  Python version 3.%%b is too old (need 3.12+)."
        endlocal & exit /b 1
    )
)

set "_SV_PYTHON_CMD=!PYTHON_CMD!"
endlocal & set "PYTHON_CMD=%_SV_PYTHON_CMD%"
exit /b 0

rem === ENSURE_PYTHON =========================================
:ensure_python
setlocal enabledelayedexpansion
call :print_info "Checking Python installation..."

call :require_python
if not errorlevel 1 (
    for /f "tokens=2 delims= " %%v in ('!PYTHON_CMD! --version 2^>^&1') do set "PY_VERSION=%%v"
    call :print_ok "Python !PY_VERSION! detected at '!PYTHON_CMD!'"
    call :log "  Python executable: !PYTHON_CMD!"
    for /f "delims=" %%p in ('where !PYTHON_CMD! 2^>nul') do call :log "  Full path: %%p"
    set "_SV_PYTHON_CMD=!PYTHON_CMD!"
    endlocal & set "PYTHON_CMD=%_SV_PYTHON_CMD%"
    exit /b 0
)

echo.
call :print_info "Python 3.12+ is required but was not found."
call :print_info "Downloading and installing Python automatically..."

call :install_python
if errorlevel 1 endlocal & exit /b 1

call :require_python
if errorlevel 1 (
    call :print_err "Python installation could not be verified."
    call :log "  Python not found even after installation completed."
    endlocal & exit /b 1
)

for /f "tokens=2 delims= " %%v in ('!PYTHON_CMD! --version 2^>^&1') do set "PY_VERSION=%%v"
call :print_ok "Python !PY_VERSION! detected"
call :log "  PATH modified to include Python directories."

set "_SV_PATH=!PATH!"
set "_SV_PYTHON_CMD=!PYTHON_CMD!"
endlocal & set "PATH=%_SV_PATH%" & set "PYTHON_CMD=%_SV_PYTHON_CMD%"
exit /b 0

rem === INSTALL_PYTHON ========================================
:install_python
setlocal enabledelayedexpansion

set "PY_LATEST_VER=3.12.5"
set "PYTHON_URL=https://www.python.org/ftp/python/3.12.5/python-3.12.5-amd64.exe"
set "PYTHON_INSTALLER=%TEMP%\python-installer.exe"

call :log "Python version: !PY_LATEST_VER!"
call :log "Download URL: !PYTHON_URL!"
call :print_info "Downloading Python !PY_LATEST_VER!..."

powershell -NoProfile -Command "try { Invoke-WebRequest '!PYTHON_URL!' -OutFile '!PYTHON_INSTALLER!' -UseBasicParsing -TimeoutSec 120; exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    call :print_err "Failed to download Python installer."
    call :log "  URL: !PYTHON_URL!"
    if exist "!PYTHON_INSTALLER!" del /f /q "!PYTHON_INSTALLER!" >nul 2>&1
    endlocal & exit /b 1
)

if not exist "!PYTHON_INSTALLER!" (
    call :print_err "Downloaded file is missing."
    endlocal & exit /b 1
)

call :print_info "Installing Python !PY_LATEST_VER!..."

"!PYTHON_INSTALLER!" /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1
set "INSTALL_RESULT=!errorlevel!"

if exist "!PYTHON_INSTALLER!" del /f /q "!PYTHON_INSTALLER!" >nul 2>&1

if !INSTALL_RESULT! neq 0 (
    call :print_err "Python installer failed (exit code: !INSTALL_RESULT!)."
    call :log "  Installer exit code: !INSTALL_RESULT!"
    endlocal & exit /b 1
)

call :print_info "Python !PY_LATEST_VER! installed. Locating installation..."

rem Add standard Python install paths to current session PATH immediately
rem (the system PATH broadcast may not reach this cmd.exe instance)
for /d %%d in ("%ProgramFiles%\Python*") do (
    if exist "%%d\python.exe" (
        set "PYTHON_DIR=%%d\"
        call :log "  Found Python at %%d"
    )
)
if not defined PYTHON_DIR (
    for /d %%d in ("%ProgramFiles(x86)%\Python*") do (
        if exist "%%d\python.exe" (
            set "PYTHON_DIR=%%d\"
            call :log "  Found Python at %%d"
        )
    )
)
if not defined PYTHON_DIR (
    for /d %%d in ("!LocalAppData!\Programs\Python\Python*") do (
        if exist "%%d\python.exe" (
            set "PYTHON_DIR=%%d\"
            call :log "  Found Python at %%d (per-user)"
        )
    )
)
if defined PYTHON_DIR (
    set "PATH=!PYTHON_DIR!;!PYTHON_DIR!Scripts;!PATH!"
    call :log "  Added !PYTHON_DIR! and !PYTHON_DIR!Scripts to PATH"
)

rem Try direct python check
python --version >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%p in ('where python 2^>nul') do (
        set "PYTHON_DIR=%%~dp"
        call :log "  Python found via system PATH at !PYTHON_DIR!"
        set "PATH=!PYTHON_DIR!;!PYTHON_DIR!Scripts;!PATH!"
        call :print_ok "Python !PY_LATEST_VER! installed and located"
        call :log "  Python executable path: !PYTHON_DIR!python.exe"
        set "_SV_PATH=!PATH!"
        endlocal & set "PATH=%_SV_PATH%"
        exit /b 0
    )
)

rem Try py launcher
py --version >nul 2>&1
if not errorlevel 1 (
    call :print_ok "Python !PY_LATEST_VER! installed (via py launcher)"
    call :log "  Using py launcher - Python may not be on PATH"
    set "_SV_PATH=!PATH!"
    endlocal & set "PATH=%_SV_PATH%"
    exit /b 0
)

call :print_err "Could not locate Python after installation."
call :log "  Searched ProgramFiles\Python*, ProgramFiles(x86)\Python*, LocalAppData\Programs\Python\Python*"
endlocal & exit /b 1

rem === REQUIRE_NODE ==========================================
:require_node
setlocal enabledelayedexpansion
call :log "  Searching for Node.js..."
where node >nul 2>&1
if errorlevel 1 (
    call :log "  node command not found on PATH."
    endlocal & exit /b 1
)
for /f "tokens=*" %%v in ('node --version') do set "NODE_VERSION=%%v"
call :log "  Found Node.js !NODE_VERSION!"
set "_SV_NODE_CMD=node"
endlocal & set "NODE_CMD=%_SV_NODE_CMD%"
exit /b 0

rem === REQUIRE_NPM ===========================================
:require_npm
setlocal enabledelayedexpansion
call :log "  Searching for npm..."
where npm >nul 2>&1
if errorlevel 1 (
    call :log "  npm command not found on PATH."
    endlocal & exit /b 1
)
for /f "tokens=*" %%v in ('npm --version') do set "NPM_VERSION=%%v"
call :log "  Found npm !NPM_VERSION!"
set "_SV_NPM_CMD=npm"
endlocal & set "NPM_CMD=%_SV_NPM_CMD%"
exit /b 0

rem === ENSURE_NODE ===========================================
:ensure_node
setlocal enabledelayedexpansion
call :print_info "Checking Node.js installation..."

call :require_node
if not errorlevel 1 (
    for /f "tokens=*" %%v in ('node --version') do set "NODE_VERSION=%%v"
    call :print_ok "Node.js !NODE_VERSION! detected"
    call :log "  Node.js version: !NODE_VERSION!"
    for /f "delims=" %%p in ('where node 2^>nul') do call :log "  Node.js path: %%p"

    call :require_npm >nul 2>&1
    if not errorlevel 1 (
        for /f "tokens=*" %%v in ('npm --version') do set "NPM_VERSION=%%v"
        call :print_ok "npm !NPM_VERSION! detected"
        call :log "  npm version: !NPM_VERSION!"
        for /f "delims=" %%p in ('where npm 2^>nul') do call :log "  npm path: %%p"
    ) else (
        call :print_warn "npm not found, will reinstall Node.js"
        call :install_node
        if errorlevel 1 endlocal & exit /b 1
        call :require_node
        if errorlevel 1 endlocal & exit /b 1
        call :require_npm
        if errorlevel 1 endlocal & exit /b 1
    )

    set "_SV_PATH=!PATH!"
    set "_SV_NODE_CMD=node"
    endlocal & set "PATH=%_SV_PATH%" & set "NODE_CMD=%_SV_NODE_CMD%"
    exit /b 0
)

echo.
call :print_info "Node.js is required but was not found."
call :print_info "Downloading and installing Node.js LTS automatically..."

call :install_node
if errorlevel 1 endlocal & exit /b 1

call :require_node
if errorlevel 1 (
    call :print_err "Node.js installation could not be verified."
    call :log "  node not found even after installation completed."
    endlocal & exit /b 1
)

for /f "tokens=*" %%v in ('node --version') do set "NODE_VERSION=%%v"
call :print_ok "Node.js !NODE_VERSION! detected"
call :log "  Node.js version: !NODE_VERSION!"

call :require_npm
if errorlevel 1 (
    call :print_err "npm is not available after Node.js installation."
    call :log "  npm not found even after Node.js installation."
    endlocal & exit /b 1
)
for /f "tokens=*" %%v in ('npm --version') do set "NPM_VERSION=%%v"
call :print_ok "npm !NPM_VERSION! detected"
call :log "  npm version: !NPM_VERSION!"
call :log "  PATH modified to include Node.js directories."

set "_SV_PATH=!PATH!"
set "_SV_NODE_CMD=node"
set "_SV_NPM_CMD=npm"
endlocal & set "PATH=%_SV_PATH%" & set "NODE_CMD=%_SV_NODE_CMD%" & set "NPM_CMD=%_SV_NPM_CMD%"
exit /b 0

rem === INSTALL_NODE ==========================================
:install_node
setlocal enabledelayedexpansion

set "NODE_LATEST_VER=20.17.0"
set "NODE_URL=https://nodejs.org/dist/v20.17.0/node-v20.17.0-x64.msi"
set "NODE_INSTALLER=%TEMP%\node-installer.msi"

call :log "Node.js version: !NODE_LATEST_VER!"
call :log "Download URL: !NODE_URL!"
call :print_info "Downloading Node.js !NODE_LATEST_VER!..."

powershell -NoProfile -Command "try { Invoke-WebRequest '!NODE_URL!' -OutFile '!NODE_INSTALLER!' -UseBasicParsing -TimeoutSec 120; exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    call :print_err "Failed to download Node.js installer."
    call :log "  URL: !NODE_URL!"
    if exist "!NODE_INSTALLER!" del /f /q "!NODE_INSTALLER!" >nul 2>&1
    endlocal & exit /b 1
)

if not exist "!NODE_INSTALLER!" (
    call :print_err "Downloaded file is missing."
    endlocal & exit /b 1
)

call :print_info "Installing Node.js !NODE_LATEST_VER!..."

msiexec /i "!NODE_INSTALLER!" /qn /norestart
set "INSTALL_RESULT=!errorlevel!"

call :log "  msiexec exit code: !INSTALL_RESULT!"

if exist "!NODE_INSTALLER!" del /f /q "!NODE_INSTALLER!" >nul 2>&1

if !INSTALL_RESULT! neq 0 (
    call :print_err "Node.js installer failed (exit code: !INSTALL_RESULT!)."
    call :log "  Installer exit code: !INSTALL_RESULT!"
    endlocal & exit /b 1
)

call :print_info "Node.js !NODE_LATEST_VER! installed. Verifying..."

rem Add standard install paths to current session PATH
if exist "%ProgramFiles%\nodejs\" (
    set "PATH=%ProgramFiles%\nodejs;%PATH%"
    call :log "  Added %ProgramFiles%\nodejs to PATH"
)
if exist "%ProgramFiles(x86)%\nodejs\" (
    set "PATH=%ProgramFiles(x86)%\nodejs;%PATH%"
    call :log "  Added %ProgramFiles(x86)%\nodejs to PATH"
)
if exist "!AppData!\Programs\nodejs\" (
    set "PATH=!AppData!\Programs\nodejs;!PATH!"
    call :log "  Added !AppData!\Programs\nodejs to PATH"
)
if exist "!LocalAppData!\Programs\nodejs\" (
    set "PATH=!LocalAppData!\Programs\nodejs;!PATH!"
    call :log "  Added !LocalAppData!\Programs\nodejs to PATH"
)

where node >nul 2>&1
if errorlevel 1 (
    call :print_err "node command not found after installation."
    call :log "  node not found in any expected location."
    endlocal & exit /b 1
)
for /f "tokens=*" %%v in ('node --version') do set "NODE_VERSION=%%v"
call :print_ok "Node.js !NODE_VERSION! verified"
call :log "  Node.js !NODE_VERSION! verified"

where npm >nul 2>&1
if errorlevel 1 (
    call :print_err "npm command not found after Node.js installation."
    call :log "  npm not found after Node.js install."
    endlocal & exit /b 1
)
for /f "tokens=*" %%v in ('npm --version') do set "NPM_VERSION=%%v"
call :print_ok "npm !NPM_VERSION! verified"
call :log "  npm !NPM_VERSION! verified"

set "_SV_PATH=!PATH!"
set "_SV_NODE_CMD=node"
endlocal & set "PATH=%_SV_PATH%" & set "NODE_CMD=%_SV_NODE_CMD%"
exit /b 0

rem === CHECK_PORT ============================================
rem Returns: errorlevel 0 if port is in use (LISTENING), 1 if free
:check_port
set "PORT=%~1"
powershell -NoProfile -Command "$l = Get-NetTCPConnection -LocalPort %PORT% -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' }; if ($l) { exit 0 } else { exit 1 }" >nul 2>&1
exit /b %errorlevel%

rem === WAIT_FOR_HEALTH =======================================
:wait_for_health
setlocal enabledelayedexpansion
set "TARGET_URL=%~1"
set "MAX_WAIT=%~2"
if not defined MAX_WAIT set "MAX_WAIT=120"
set /a elapsed=0
set /a LAST_STATUS=30

call :print_info "Waiting for backend (max !MAX_WAIT!s)..."

:health_loop
if !elapsed! geq !MAX_WAIT! (
    call :print_err "Backend did not become healthy within !MAX_WAIT!s"
    endlocal & exit /b 1
)

if !elapsed! gtr 0 if !elapsed! geq !LAST_STATUS! (
    set /a LAST_STATUS=!elapsed!+30
    call :print_info "  Still waiting... (!elapsed!s of !MAX_WAIT!s)"
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
:confirm
set "prompt_msg=%~1"
if not defined prompt_msg set "prompt_msg=Are you sure?"
choice /c YN /n /m "%prompt_msg% [Y/N]: "
exit /b %errorlevel%

rem === WAIT_FOR_FRONTEND =====================================
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

rem === KILL_PORT ==============================================
rem Kills any process listening on the given TCP port.
rem Uses netstat + PID to find the exact process.
:kill_port
setlocal enabledelayedexpansion
set "PORT=%~1"
if not defined PORT endlocal & exit /b 0
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":!PORT!" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
endlocal
exit /b 0
