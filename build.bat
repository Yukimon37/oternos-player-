@echo off
echo Pulling latest updates...
git pull
echo.
echo Building Void Player...
C:\Users\Ikari\AppData\Local\Programs\Python\Python312\Scripts\pyinstaller.exe --onefile --noconsole --name void_player void_player.py
echo.
echo Done! Your new exe is in the dist folder.
pause
