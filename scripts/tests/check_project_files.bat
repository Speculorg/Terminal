@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ====================================================
:: Script: check_project_files.bat
:: Description: This script recursively scans the current workspace directory,
::              displays the file and directory tree structure with proper tree symbols,
::              and logs the output along with detailed debug information.
::
:: Version: 0.2
:: Author: Speculorg Team
:: Date: 2025.04.06
::
:: History:
::   0.1 - Initial implementation with debug logging, detailed timestamps,
::         improved prefix formation, unified command-line processing,
::         and enhanced directory existence check.
::   0.2 - Added runtime environment information block before directory traversal,
::         and simplified finish block to remove duplicate output.
:: ====================================================

:: ====================================================
:: Configuration Parameters (Speculorg Standards)
:: ====================================================
set "WORKSPACE_ROOT=%CD%"            REM Workspace root directory
set "DEBUG_MODE=true"                  REM Debug mode enabled by default
set "SHOW_PROGRESS=true"               REM Show progress messages
set "MAX_DEPTH=10"                     REM Maximum recursion depth
set "EXCLUDE_DIRS=.git,.vscode,__pycache__"  REM Directories to exclude (comma-separated)
set "EXCLUDE_FILES=*.pyc,*.pyo,*.pyd,*.so,*.dll,*.exe" REM Files to exclude (wildcards)

:: Tree symbols for output
set "DIR_SYMBOL=📁"
set "FILE_SYMBOL=📄"
set "TREE_BRANCH=├──"
set "TREE_LAST=└──"
set "TREE_PIPE=│   "
set "TREE_SPACE=    "

:: ====================================================
:: Logging Initialization
:: ====================================================
:: Create timestamp in format YYYY.MM.DD_HH-MM
set "timestamp=%date:~6,4%.%date:~3,2%.%date:~0,2%_%time:~0,2%-%time:~3,2%"
:: Remove leading spaces from hour if any
set "timestamp=%timestamp: =0%"
set "LOG_FILE=%WORKSPACE_ROOT%\logs\%timestamp%_check_project_files_result.log"

if not exist "%WORKSPACE_ROOT%\logs" mkdir "%WORKSPACE_ROOT%\logs"

:: Write header to log file
(
    echo Speculorg - Project Structure Report
    echo Date: %timestamp%
    echo ---------------------------------------------
    echo:
) > "%LOG_FILE%"

:: ====================================================
:: Command Line Arguments Processing
:: ====================================================
:parse_args
if "%~1"=="" goto :main
if /i "%~1"=="--debug" (
    set "DEBUG_MODE=true"
    shift
    goto :parse_args
)
if /i "%~1"=="--no-progress" (
    set "SHOW_PROGRESS=false"
    shift
    goto :parse_args
)
if /i "%~1"=="--max-depth" (
    if "%~2"=="" (
        call :log_debug "ERROR: --max-depth requires a value."
        goto :show_help
    )
    set "MAX_DEPTH=%~2"
    shift
    shift
    goto :parse_args
)
if /i "%~1"=="--workspace" (
    if "%~2"=="" (
        call :log_debug "ERROR: --workspace requires a path."
        goto :show_help
    )
    set "WORKSPACE_ROOT=%~2"
    shift
    shift
    goto :parse_args
)
if /i "%~1"=="--help" goto :show_help
call :log_debug "ERROR: Unknown parameter: %~1"
goto :show_help

:show_help
echo.
echo Usage: %~nx0 [options]
echo Options:
echo   --debug              Enable debug mode.
echo   --no-progress        Hide progress messages.
echo   --max-depth N        Set maximum recursion depth (default: 10).
echo   --workspace PATH     Set workspace root directory.
echo   --help               Show this help message.
echo.
exit /b 1

:: ====================================================
:: Main Logic: Traverse and Log Project Structure
:: ====================================================
:main
:: Check if workspace directory exists
if not exist "%WORKSPACE_ROOT%" (
    call :log_debug "ERROR: Workspace directory '%WORKSPACE_ROOT%' does not exist."
    exit /b 1
)

:: Get the name of the workspace root folder
for %%I in ("%WORKSPACE_ROOT%") do set "ROOT_NAME=%%~nxI"
call :log_debug "Processing root directory: %WORKSPACE_ROOT%"

:: ====================================================
:: Runtime Environment Information
:: ====================================================
for /f "delims=" %%v in ('ver') do set "OS_VERSION=%%v"
(
    echo.
    echo Runtime Environment Information:
    echo - Workspace Root: %WORKSPACE_ROOT%
    echo - OS Version: %OS_VERSION%
    echo - Maximum Recursion Depth: %MAX_DEPTH%
    echo - Debug Mode: %DEBUG_MODE%
    echo.
) >> "%LOG_FILE%"

if "%SHOW_PROGRESS%"=="true" (
    echo.
    echo Runtime Environment Information:
    echo - Workspace Root: %WORKSPACE_ROOT%
    echo - OS Version: %OS_VERSION%
    echo - Maximum Recursion Depth: %MAX_DEPTH%
    echo - Debug Mode: %DEBUG_MODE%
    echo.
)

echo %DIR_SYMBOL% %ROOT_NAME%/ >> "%LOG_FILE%"
if "%SHOW_PROGRESS%"=="true" echo %DIR_SYMBOL% %ROOT_NAME%/

:: Start recursive processing: arguments: current directory, current prefix (empty), current depth (0)
call :process_dir "%WORKSPACE_ROOT%" "" 0

goto :finish

:: ====================================================
:: Function: log_debug
:: Description: Logs a debug message with a timestamp if DEBUG_MODE is enabled.
:: Arguments: %1 - Message to log.
:: ====================================================
:log_debug
if /i "%DEBUG_MODE%"=="true" (
    set "debug_time=%date% %time%"
    echo [DEBUG] [%debug_time%] %~1 >> "%LOG_FILE%"
    if "%SHOW_PROGRESS%"=="true" echo [DEBUG] [%debug_time%] %~1
)
exit /b

:: ====================================================
:: Function: process_dir
:: Description: Recursively processes a directory, logs files and subdirectories.
:: Arguments:
::   %1 - Current directory (quoted)
::   %2 - Prefix for tree formatting (e.g., spaces and pipes)
::   %3 - Current recursion depth (number)
:: ====================================================
:process_dir
setlocal enabledelayedexpansion
set "current_dir=%~1"
set "prefix=%~2"
set /a depth=%~3

:: Check if current directory exists, skip if not
if not exist "!current_dir!" (
    call :log_debug "WARNING: Directory '!current_dir!' does not exist. Skipping..."
    endlocal
    exit /b
)

:: Check depth limit
if !depth! GEQ %MAX_DEPTH% (
    endlocal
    exit /b
)

:: Create an array of items with type and name, preserving the order from 'dir'
set "item_count=0"
for /f "delims=" %%A in ('dir /b /a-d "!current_dir!" 2^>nul') do (
    call :is_excluded_file "%%A"
    if errorlevel 1 (
        set /a item_count+=1
        set "item_!item_count!_type=file"
        set "item_!item_count!_name=%%A"
    )
)
for /f "delims=" %%A in ('dir /b /ad "!current_dir!" 2^>nul') do (
    call :is_excluded_dir "%%A"
    if errorlevel 1 (
        set /a item_count+=1
        set "item_!item_count!_type=dir"
        set "item_!item_count!_name=%%A"
    )
)

:: Process each item in the list
for /l %%I in (1,1,!item_count!) do (
    set "is_last_item=0"
    if %%I EQU !item_count! set "is_last_item=1"
    set "current_item_type=!item_%%I_type!"
    set "current_item_name=!item_%%I_name!"
    if "!current_item_type!"=="file" (
        if !is_last_item! EQU 1 (
            echo !prefix!%TREE_LAST% %FILE_SYMBOL% !current_item_name! >> "%LOG_FILE%"
            if "%SHOW_PROGRESS%"=="true" echo !prefix!%TREE_LAST% %FILE_SYMBOL% !current_item_name!
        ) else (
            echo !prefix!%TREE_BRANCH% %FILE_SYMBOL% !current_item_name! >> "%LOG_FILE%"
            if "%SHOW_PROGRESS%"=="true" echo !prefix!%TREE_BRANCH% %FILE_SYMBOL% !current_item_name!
        )
    ) else (
        if !is_last_item! EQU 1 (
            echo !prefix!%TREE_LAST% %DIR_SYMBOL% !current_item_name!/ >> "%LOG_FILE%"
            if "%SHOW_PROGRESS%"=="true" echo !prefix!%TREE_LAST% %DIR_SYMBOL% !current_item_name!/
            set "new_prefix=!prefix!%TREE_SPACE%"
        ) else (
            echo !prefix!%TREE_BRANCH% %DIR_SYMBOL% !current_item_name!/ >> "%LOG_FILE%"
            if "%SHOW_PROGRESS%"=="true" echo !prefix!%TREE_BRANCH% %DIR_SYMBOL% !current_item_name!/
            set "new_prefix=!prefix!%TREE_PIPE%"
        )
        call :process_dir "!current_dir!\!current_item_name!" "!new_prefix!" !depth!+1
    )
)

endlocal
exit /b

:: ====================================================
:: Function: is_excluded_file
:: Description: Checks if a file should be excluded based on EXCLUDE_FILES patterns.
:: Returns: errorlevel 0 if file is excluded, 1 if not.
:: Arguments: %1 - Filename
:: ====================================================
:is_excluded_file
set "fname=%~1"
for %%e in (%EXCLUDE_FILES%) do (
    echo "%fname%" | findstr /i /e /r /c:"%%e" >nul && exit /b 0
)
exit /b 1

:: ====================================================
:: Function: is_excluded_dir
:: Description: Checks if a directory should be excluded based on EXCLUDE_DIRS.
:: Returns: errorlevel 0 if directory is excluded, 1 if not.
:: Arguments: %1 - Directory name
:: ====================================================
:is_excluded_dir
set "dname=%~1"
for %%e in (%EXCLUDE_DIRS%) do (
    if /i "%%e"=="%dname%" exit /b 0
)
exit /b 1

:: ====================================================
:: Finish
:: ====================================================
:finish
:: Create a temporary file with the finish message
(
    echo.
    echo ---------------------------------------------
    echo Processing completed.
    echo ---------------------------------------------
    echo Results saved in: %LOG_FILE%
    echo.
) > "%TEMP%\finish_message.txt"

:: Append the finish message to the log file
type "%TEMP%\finish_message.txt" >> "%LOG_FILE%"

:: If progress output is enabled, display the finish message on the console
if "%SHOW_PROGRESS%"=="true" type "%TEMP%\finish_message.txt"

:: Clean up temporary file
del "%TEMP%\finish_message.txt"

endlocal
exit /b
