
SET DIR=%cd%
SET QGIS_PROFILE=default

SET PLUGIN=Discovery
SET SRC=%DIR%\%PLUGIN%

SET DEST=%UserProfile%\AppData\Roaming\QGIS\QGIS3\profiles\%QGIS_PROFILE%\python\plugins

SET DEST_PLUGIN=%DEST%\%PLUGIN%

rd %DEST_PLUGIN% /s /q

xcopy %SRC% %DEST_PLUGIN% /s/i/h/e/k/f/c

