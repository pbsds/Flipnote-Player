pyinstaller --onefile -n "Flipnote Player" --console "Flipnote Player.py"
move "dist\Flipnote Player.exe" "Flipnote Player.exe"
rmdir dist
move "build\Flipnote Player\warnFlipnote Player.txt" "warnFlipnote Player.txt"
rmdir /s /q build
del "Flipnote Player.spec"
pause