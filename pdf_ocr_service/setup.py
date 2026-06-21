#!/usr/bin/env python3
"""
Setup-Skript für PDF OCR Service
Erstellt ein Executable mit PyInstaller
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def check_requirements():
    """Prüft ob alle Voraussetzungen erfüllt sind"""
    print("Prüfe Voraussetzungen...")
    
    # Prüfen ob Python 3.8+ installiert ist
    if sys.version_info < (3, 8):
        print("Fehler: Python 3.8 oder höher ist erforderlich")
        return False
    
    # Prüfen ob PyInstaller installiert ist
    try:
        import PyInstaller
        print("✓ PyInstaller ist installiert")
    except ImportError:
        print("Fehler: PyInstaller ist nicht installiert")
        print("Installieren mit: pip install pyinstaller")
        return False
    
    # Prüfen ob pywin32 installiert ist
    try:
        import win32serviceutil
        print("✓ pywin32 ist installiert")
    except ImportError:
        print("Fehler: pywin32 ist nicht installiert")
        print("Installieren mit: pip install pywin32")
        return False
    
    # Prüfen ob Tesseract installiert ist
    try:
        import pytesseract
        tesseract_path = pytesseract.get_tesseract_version()
        print(f"✓ Tesseract ist installiert (Version: {tesseract_path})")
    except Exception as e:
        print(f"Warnung: Tesseract konnte nicht gefunden werden: {e}")
        print("Bitte installieren Sie Tesseract OCR von https://github.com/UB-Mannheim/tesseract/wiki")
    
    return True

def build_executable():
    """Erstellt das Executable mit PyInstaller"""
    print("\nErstelle Executable...")
    
    # PyInstaller-Befehl
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--windowed',
        '--name', 'pdf_ocr_service',
        '--clean',
        '--specpath', '.',
        'pdf_ocr_service.spec'
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✓ Executable erfolgreich erstellt")
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Fehler beim Erstellen des Executables: {e}")
        print(e.stderr)
        return False

def cleanup():
    """Bereinigt temporäre Dateien"""
    print("\nBereinige temporäre Dateien...")
    
    # Build-Verzeichnis entfernen
    build_dir = Path('build')
    if build_dir.exists():
        shutil.rmtree(build_dir)
        print("✓ Build-Verzeichnis entfernt")
    
    # Dist-Verzeichnis entfernen (außer das Executable)
    dist_dir = Path('dist')
    if dist_dir.exists():
        for item in dist_dir.iterdir():
            if item.name != 'pdf_ocr_service.exe':
                if item.is_file():
                    item.unlink()
                else:
                    shutil.rmtree(item)
        print("✓ Dist-Verzeichnis bereinigt")
    
    # .spec und .pyc Dateien entfernen
    for file in Path('.').glob('*.pyc'):
        file.unlink()
    
    for file in Path('.').glob('__pycache__'):
        shutil.rmtree(file)
    
    print("✓ Bereinigung abgeschlossen")

def main():
    """Hauptfunktion"""
    print("PDF OCR Service - Setup")
    print("=" * 40)
    
    # Voraussetzungen prüfen
    if not check_requirements():
        print("\nBitte beheben Sie die Fehler und versuchen Sie es erneut.")
        sys.exit(1)
    
    # Executable erstellen
    if not build_executable():
        print("\nFehler beim Erstellen des Executables.")
        sys.exit(1)
    
    # Bereinigen
    cleanup()
    
    print("\n" + "=" * 40)
    print("Setup abgeschlossen!")
    print("\nDas Executable 'pdf_ocr_service.exe' wurde erstellt.")
    print("\nZum Installieren des Dienstes:")
    print("1. Führen Sie die GUI aus: python main.py")
    print("2. Klicken Sie auf 'Dienst installieren' im Dienst-Menü")
    print("\nOder manuell:")
    print("pdf_ocr_service.exe --service install")
    print("pdf_ocr_service.exe --service start")

if __name__ == "__main__":
    main()
