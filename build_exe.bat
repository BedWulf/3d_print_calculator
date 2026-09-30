@echo off
REM Сборка standalone .exe (запускать на Windows, Python 3.10+ установлен).
REM Результат: dist\Price3DCalc.exe — один файл, работает на любом ПК без Python.
pip install -r requirements.txt || goto :err
pyinstaller --noconfirm --onefile --windowed --name Price3DCalc main.py || goto :err
echo.
echo Готово: dist\Price3DCalc.exe
goto :eof
:err
echo Сборка завершилась с ошибкой.
exit /b 1
