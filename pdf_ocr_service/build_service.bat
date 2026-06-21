@echo off
REM Batch-Datei zum Erstellen des PDF OCR Service Executables

cd /d %~dp0

echo Erstelle PDF OCR Service Executable...
python -m PyInstaller --onefile --windowed --name pdf_ocr_service --icon=NONE main.py

echo.
echo Executable wurde erstellt: pdf_ocr_service.exe

echo.
echo Zum Installieren des Dienstes:
echo 1. Führen Sie die GUI aus: python main.py
echo 2. Klicken Sie auf "Dienst installieren" im Dienst-Menü

echo.
echo Alternativ können Sie den Dienst manuell installieren mit:
echo pdf_ocr_service.exe --service install

echo.
echo Zum Starten des Dienstes:
echo pdf_ocr_service.exe --service start

pause
