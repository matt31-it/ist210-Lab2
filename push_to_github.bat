@echo off
setlocal
set GIT_EXE="C:\Program Files\Microsoft SQL Server Management Studio 22\Release\Common7\IDE\CommonExtensions\Microsoft\TeamFoundation\Team Explorer\Git\cmd\git.exe"

if "%~1"=="" (
    echo ========================================================
    echo      IST 210 Lab 2 - Push Repository to GitHub
    echo ========================================================
    echo.
    echo Usage: push_to_github.bat ^<GitHub-Repo-URL^>
    echo Example: push_to_github.bat https://github.com/your-username/ist210-lab2.git
    echo.
    set /p REPO_URL="Enter your GitHub repository URL: "
) else (
    set REPO_URL=%~1
)

if "%REPO_URL%"=="" (
    echo No repository URL provided. Aborting.
    pause
    exit /b 1
)

echo.
echo Setting remote origin to %REPO_URL% ...
%GIT_EXE% remote remove origin 2>nul
%GIT_EXE% remote add origin %REPO_URL%
%GIT_EXE% branch -M main
echo Pushing main branch to GitHub...
%GIT_EXE% push -u origin main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] Your repository has been pushed to GitHub!
    echo Submit your repository URL on Canvas for Lab 2.
) else (
    echo.
    echo [NOTE] Push failed. Make sure you are authenticated with GitHub or have configured a Personal Access Token / SSH key.
)
pause
