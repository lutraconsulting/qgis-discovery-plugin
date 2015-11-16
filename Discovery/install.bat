@echo off
echo By default this script installs for the current user.
echo To install for all users, edit this script and set DEST accordingly
echo ""
echo Press ENTER to continue or CTRL+C to abort.

rem Install for current user
SET DEST=%HOMEPATH%\.qgis2\python\plugins\PostGIS_Search

mkdir %DEST%
xcopy /y *.py %DEST%
xcopy /y *.png %DEST%
xcopy /y metadata.txt %DEST%
xcopy /y *.ui %DEST%
xcopy /y *.ini %DEST%
