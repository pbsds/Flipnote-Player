pyinstaller --icon=icon.ico --onefile -n "Flipnote Player" --noconsole "Flipnote Player.py"
move "dist\Flipnote Player.exe" "Flipnote Player.exe"
rmdir dist
move "build\Flipnote Player\warnFlipnote Player.txt" "warnFlipnote Player.txt"
rmdir /s /q build
del "Flipnote Player.spec"
pause