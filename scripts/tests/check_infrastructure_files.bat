@echo off
setlocal enabledelayedexpansion

REM Set workspace root path
set "WORKSPACE_ROOT=D:\SO_Src\Terminal"


REM Get the current date and time in the required format: YYYY.MM.DD_HH-MM
for /f "tokens=1-3 delims=." %%a in ("%date:~6,4%.%date:~3,2%.%date:~0,2%") do set "formattedDate=%%a.%%b.%%c"
for /f "tokens=1,2 delims=:" %%a in ("%time:~0,5%") do set "formattedTime=%%a-%%b"
set "timestamp=%formattedDate%_%formattedTime%"

set "LOG_FILE=%WORKSPACE_ROOT%\logs\%timestamp%_check_infrastructure_files_result.log"

REM Create logs directory if not exists
if not exist "%WORKSPACE_ROOT%\logs" (
    echo Creating logs directory...
    mkdir "%WORKSPACE_ROOT%\logs"
    if errorlevel 1 (
        echo ERROR: Failed to create logs directory
        exit /b 1
    )
)

REM Initialize log file
echo [%date% %time%] Starting infrastructure check > "%LOG_FILE%"
echo Workspace root: %WORKSPACE_ROOT% >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

REM Check main directories
echo Checking main directories... >> "%LOG_FILE%"
for %%d in (docker services modules configs scripts logs) do (
    if exist "%WORKSPACE_ROOT%\%%d" (
        echo [OK] Directory %%d exists >> "%LOG_FILE%"
    ) else (
        echo [ERROR] Directory %%d is missing >> "%LOG_FILE%"
    )
)
echo. >> "%LOG_FILE%"

REM Check services
echo Checking services... >> "%LOG_FILE%"
for %%s in (infrastructure-service management-service security-service) do (
    echo Checking service: %%s >> "%LOG_FILE%"
    
    REM Check service source directory
    if exist "%WORKSPACE_ROOT%\services\%%s" (
        echo [OK] Service source directory exists >> "%LOG_FILE%"
        
        REM Check service files
        for %%f in (main.py README.md) do (
            if exist "%WORKSPACE_ROOT%\services\%%s\%%f" (
                echo [OK] File %%f exists in service %%s >> "%LOG_FILE%"
            ) else (
                echo [ERROR] File %%f is missing in service %%s >> "%LOG_FILE%"
            )
        )
        
        REM Check config directory
        if exist "%WORKSPACE_ROOT%\services\%%s\config" (
            echo [OK] Config directory exists in service %%s >> "%LOG_FILE%"
            for %%c in (README.md config.yml) do (
                if exist "%WORKSPACE_ROOT%\services\%%s\config\%%c" (
                    echo [OK] Config file %%c exists in service %%s >> "%LOG_FILE%"
                ) else (
                    echo [ERROR] Config file %%c is missing in service %%s >> "%LOG_FILE%"
                )
            )
        ) else (
            echo [ERROR] Config directory is missing in service %%s >> "%LOG_FILE%"
        )
    ) else (
        echo [ERROR] Service source directory is missing for %%s >> "%LOG_FILE%"
    )
    
    REM Check docker directory
    if exist "%WORKSPACE_ROOT%\docker\%%s" (
        echo [OK] Docker directory exists for service %%s >> "%LOG_FILE%"
        for %%d in (Dockerfile requirements.txt README.md) do (
            if exist "%WORKSPACE_ROOT%\docker\%%s\%%d" (
                echo [OK] Docker file %%d exists for service %%s >> "%LOG_FILE%"
            ) else (
                echo [ERROR] Docker file %%d is missing for service %%s >> "%LOG_FILE%"
            )
        )
    ) else (
        echo [ERROR] Docker directory is missing for service %%s >> "%LOG_FILE%"
    )
    echo. >> "%LOG_FILE%"
)

REM Check modules
echo Checking modules... >> "%LOG_FILE%"
for %%m in (
    infrastructure-consul-module infrastructure-vault-module infrastructure-database-module
    infrastructure-docker-module infrastructure-redis-module infrastructure-rabbitmq-module
    infrastructure-celery-module infrastructure-keycloak-module infrastructure-traefik-module
    infrastructure-opentelemetry-module infrastructure-prometheus-module infrastructure-grafana-module
    infrastructure-sentry-module infrastructure-elk-module
    management-logs-module management-configurations-module management-users-module
    security-audit-module security-authentication-module security-authorization-module
) do (
    echo Checking module: %%m >> "%LOG_FILE%"
    
    REM Check module source directory
    if exist "%WORKSPACE_ROOT%\modules\%%m" (
        echo [OK] Module source directory exists >> "%LOG_FILE%"
        
        REM Check module files
        for %%f in (main.py README.md) do (
            if exist "%WORKSPACE_ROOT%\modules\%%m\%%f" (
                echo [OK] File %%f exists in module %%m >> "%LOG_FILE%"
            ) else (
                echo [ERROR] File %%f is missing in module %%m >> "%LOG_FILE%"
            )
        )
        
        REM Check config directory
        if exist "%WORKSPACE_ROOT%\modules\%%m\config" (
            echo [OK] Config directory exists in module %%m >> "%LOG_FILE%"
            for %%c in (README.md config.yml) do (
                if exist "%WORKSPACE_ROOT%\modules\%%m\config\%%c" (
                    echo [OK] Config file %%c exists in module %%m >> "%LOG_FILE%"
                ) else (
                    echo [ERROR] Config file %%c is missing in module %%m >> "%LOG_FILE%"
                )
            )
        ) else (
            echo [ERROR] Config directory is missing in module %%m >> "%LOG_FILE%"
        )
    ) else (
        echo [ERROR] Module source directory is missing for %%m >> "%LOG_FILE%"
    )
    
    REM Check docker directory
    if exist "%WORKSPACE_ROOT%\docker\%%m" (
        echo [OK] Docker directory exists for module %%m >> "%LOG_FILE%"
        for %%d in (Dockerfile requirements.txt README.md) do (
            if exist "%WORKSPACE_ROOT%\docker\%%m\%%d" (
                echo [OK] Docker file %%d exists for module %%m >> "%LOG_FILE%"
            ) else (
                echo [ERROR] Docker file %%d is missing for module %%m >> "%LOG_FILE%"
            )
        )
    ) else (
        echo [ERROR] Docker directory is missing for module %%m >> "%LOG_FILE%"
    )
    echo. >> "%LOG_FILE%"
)

REM Check docker-compose.yml
echo Checking docker-compose.yml... >> "%LOG_FILE%"
if exist "%WORKSPACE_ROOT%\docker\docker-compose.yml" (
    echo [OK] docker-compose.yml exists >> "%LOG_FILE%"
) else (
    echo [ERROR] docker-compose.yml is missing >> "%LOG_FILE%"
)

REM Check environment files
echo Checking environment files... >> "%LOG_FILE%"
for %%e in (.env.develop .env.release) do (
    if exist "%WORKSPACE_ROOT%\configs\%%e" (
        echo [OK] Environment file %%e exists >> "%LOG_FILE%"
    ) else (
        echo [ERROR] Environment file %%e is missing >> "%LOG_FILE%"
    )
)

echo. >> "%LOG_FILE%"
echo [%date% %time%] Infrastructure check completed >> "%LOG_FILE%"

REM Display completion message
echo Infrastructure check completed. Results saved to %LOG_FILE%

endlocal