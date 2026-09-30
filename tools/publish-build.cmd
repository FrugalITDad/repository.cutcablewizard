@echo off
rem Runs publish-build.ps1 without changing PowerShells execution policy.
rem Double-click to be prompted, or pass arguments, e.g.:
rem   publish-build.cmd -Zip "C:\Builds\cordcutter_plus-build-1.1.2.zip"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0publish-build.ps1" %*
if "%~1"=="" pause
