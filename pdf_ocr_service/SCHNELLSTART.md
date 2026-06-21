# Schnellstart-Anleitung für PDF OCR Service

## 🚀 Installation in 5 Schritten

### 1. Voraussetzungen installieren

```bash
# Python 3.8+ installieren (falls nicht vorhanden)
# https://www.python.org/downloads/

# Benötigte Python-Pakete installieren
pip install -r requirements.txt
```

### 2. Tesseract OCR installieren

1. **Tesseract herunterladen**: https://github.com/UB-Mannheim/tesseract/wiki
2. **Installieren** mit Standardoptionen
3. **Deutsche Sprachdaten installieren** (wichtig für deutsche Texte):
   ```bash
   tesseract --download deu
   tesseract --download eng
   ```

### 3. Executable erstellen

```bash
# Methode 1: Mit Setup-Skript
python setup.py

# Methode 2: Mit Batch-Datei
build_service.bat

# Methode 3: Manuell
python -m PyInstaller --onefile --windowed --name pdf_ocr_service main.py
```

### 4. Dienst installieren und starten

```bash
# Dienst installieren
pdf_ocr_service.exe --service install

# Dienst starten
pdf_ocr_service.exe --service start
```

### 5. GUI starten und konfigurieren

```bash
python main.py
```

## 📁 Ordner einrichten

1. **Eingangsordner erstellen** (z.B. `C:\Scanner\Eingang`)
2. **Zielordner erstellen** (z.B. `C:\Scanner\Archiv`)
3. In der GUI:
   - Auf "Hinzufügen" klicken
   - Eingangsordner auswählen
   - Zielordner auswählen
   - "Überwachung starten" klicken

## 🎯 Testen

1. Kopieren Sie eine PDF-Datei in den Eingangsordner
2. Warten Sie einige Sekunden
3. Prüfen Sie den Zielordner - es sollten appear:
   - Die ursprüngliche PDF-Datei
   - Eine Textdatei mit dem OCR-Ergebnis

## 🔧 Wichtige Einstellungen

- **Tesseract Pfad**: Muss zum Installationsort von Tesseract zeigen
- **Temp-Verzeichnis**: Sollte Schreibrechte haben
- **Log-Level**: INFO für normale Nutzung, DEBUG für Fehleranalyse

## 📊 Überwachung

- **Status**: Wird in der Statusleiste angezeigt
- **Protokoll**: Alle Aktivitäten werden in `service.log` gespeichert
- **Dienststatus**: Wird automatisch alle 5 Sekunden aktualisiert

## 🛠 Problembehandlung

### Dienst startet nicht
- **Lösung**: Als Administrator ausführen
- **Prüfen**: `pdf_ocr_service.exe --service install`

### OCR funktioniert nicht
- **Prüfen**: Tesseract-Pfad in den Einstellungen
- **Testen**: `tesseract --version` in der Eingabeaufforderung

### Dateien werden nicht verschoben
- **Prüfen**: Berechtigungen für die Zielordner
- **Prüfen**: Protokoll auf Fehlermeldungen

## 📚 Dokumentation

- **Vollständige Anleitung**: Siehe `README.md`
- **Technische Details**: Im Code kommentiert
- **API-Dokumentation**: In den Python-Dateien

## 🎉 Fertig!

Ihr PDF OCR Service ist jetzt einsatzbereit und läuft als Windows-Dienst im Hintergrund!
