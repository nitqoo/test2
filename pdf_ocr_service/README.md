# PDF OCR Service

Ein Windows-Programm mit GUI, das Ordner auf neue PDF-Dateien überwacht, automatisch OCR durchführt und die Dateien in definierte Zielverzeichnisse verschiebt. Läuft als Windows-Dienst unabhängig von der Benutzeranmeldung.

## Funktionen

- **Ordnerüberwachung**: Überwacht einen oder mehrere Ordner auf neue PDF-Dateien
- **Automatische OCR-Verarbeitung**: Führt automatisch OCR auf neuen PDFs durch
- **Zielordner-Verwaltung**: Jeder Eingangsordner kann einen eigenen Zielordner haben
- **Windows-Dienst**: Läuft als Hintergrunddienst, unabhängig von Benutzeranmeldung
- **GUI**: Benutzerfreundliche Oberfläche für Konfiguration und Verwaltung
- **Protokollierung**: Ausführliche Protokollierung aller Aktivitäten

## Voraussetzungen

### Software-Voraussetzungen

1. **Python 3.8 oder höher**
2. **Tesseract OCR** (muss installiert sein)
   - Download: https://github.com/UB-Mannheim/tesseract/wiki
   - Standardinstallationspfad: `C:\Program Files\Tesseract-OCR\tesseract.exe`
3. **Deutsche Sprachdaten für Tesseract**
   - Wird für bessere OCR-Ergebnisse mit deutschen Texten benötigt

### Python-Pakete

Die benötigten Pakete sind in `requirements.txt` aufgelistet:

```bash
pip install -r requirements.txt
```

## Installation

### 1. Python-Pakete installieren

```bash
cd pdf_ocr_service
pip install -r requirements.txt
```

### 2. Tesseract OCR installieren

1. Laden Sie Tesseract OCR von https://github.com/UB-Mannheim/tesseract/wiki herunter
2. Installieren Sie es mit den Standardoptionen
3. Stellen Sie sicher, dass der Pfad in der Konfiguration korrekt ist (Standard: `C:\Program Files\Tesseract-OCR\tesseract.exe`)

### 3. Deutsche Sprachdaten installieren (optional, aber empfohlen)

Nach der Installation von Tesseract:
1. Öffnen Sie die Eingabeaufforderung als Administrator
2. Führen Sie folgende Befehle aus:
   ```bash
   tesseract --list-langs
   tesseract --download deu
   tesseract --download eng
   ```

## Verwendung

### Als normale Anwendung starten

```bash
python main.py
```

### Als Windows-Dienst installieren und starten

1. **Executable erstellen** (erforderlich für den Dienst):
   ```bash
   python build_service.bat
   ```
   oder manuell:
   ```bash
   python -m PyInstaller --onefile --windowed --name pdf_ocr_service --icon=NONE main.py
   ```

2. **Dienst installieren**:
   - Starten Sie die GUI: `python main.py`
   - Klicken Sie auf "Dienst installieren" im Dienst-Menü
   - Oder manuell: `pdf_ocr_service.exe --service install`

3. **Dienst starten**:
   - In der GUI: "Dienst starten" im Dienst-Menü
   - Oder manuell: `pdf_ocr_service.exe --service start`

4. **Dienst stoppen**:
   - In der GUI: "Dienst stoppen" im Dienst-Menü
   - Oder manuell: `pdf_ocr_service.exe --service stop`

5. **Dienst deinstallieren**:
   - In der GUI: "Dienst deinstallieren" im Dienst-Menü
   - Oder manuell: `pdf_ocr_service.exe --service uninstall`

## GUI-Bedienung

### Ordnerverwaltung

1. **Ordnerzuordnung hinzufügen**:
   - Klicken Sie auf "Hinzufügen"
   - Wählen Sie den Quellordner (Eingangsordner) aus
   - Wählen Sie den Zielordner aus
   - Die Zuordnung wird gespeichert und in der Liste angezeigt

2. **Ordnerzuordnung bearbeiten**:
   - Wählen Sie eine Zuordnung aus der Liste aus
   - Klicken Sie auf "Bearbeiten"
   - Ändern Sie die gewünschten Werte

3. **Ordnerzuordnung entfernen**:
   - Wählen Sie eine Zuordnung aus der Liste aus
   - Klicken Sie auf "Entfernen"
   - Bestätigen Sie die Löschung

4. **Überwachung starten/stoppen**:
   - Klicken Sie auf "Überwachung starten", um die Überwachung zu aktivieren
   - Klicken Sie auf "Überwachung stoppen", um die Überwachung zu beenden

### Einstellungen

- **Tesseract Pfad**: Pfad zur Tesseract-Executable
- **Temp-Verzeichnis**: Verzeichnis für temporäre Dateien
- **Log-Level**: Detailgrad der Protokollierung (DEBUG, INFO, WARNING, ERROR)

### Protokoll

- Zeigt das aktuelle Protokoll an
- Kann aktualisiert oder gelöscht werden

## Konfiguration

Die Konfiguration wird in `config.json` gespeichert:

```json
{
  "watched_folders": [
    {
      "source_folder": "C:\\Scanner\\Eingang",
      "target_folder": "C:\\Scanner\\Archiv",
      "enabled": true
    }
  ],
  "tesseract_path": "C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
  "service_enabled": false,
  "log_level": "INFO",
  "temp_dir": "C:\\Temp\\PDF_OCR_Service"
}
```

## Problembehandlung

### Häufige Probleme

1. **Tesseract nicht gefunden**:
   - Stellen Sie sicher, dass Tesseract installiert ist
   - Überprüfen Sie den Pfad in den Einstellungen

2. **Dienst startet nicht**:
   - Stellen Sie sicher, dass das Executable erstellt wurde
   - Prüfen Sie die Berechtigungen (als Administrator ausführen)
   - Überprüfen Sie das Protokoll auf Fehlermeldungen

3. **OCR funktioniert nicht**:
   - Stellen Sie sicher, dass die PDF-Dateien lesbar sind
   - Prüfen Sie, ob die Sprachdaten installiert sind
   - Testen Sie Tesseract manuell: `tesseract test.png output -l deu`

4. **Dateien werden nicht verschoben**:
   - Prüfen Sie die Berechtigungen für die Zielordner
   - Stellen Sie sicher, dass die Ordner existieren

### Protokollierung

Alle Aktivitäten werden in `service.log` protokolliert. Bei Problemen:

1. Öffnen Sie die Protokolldatei
2. Suchen Sie nach Fehlermeldungen
3. Überprüfen Sie die Zeitstempel der Fehler

## Technische Details

### Architektur

- **GUI**: PyQt6 für die Benutzeroberfläche
- **Dienst**: Windows-Dienst mit pywin32
- **Dateiüberwachung**: watchdog-Bibliothek
- **OCR**: pytesseract mit Tesseract OCR
- **PDF-Verarbeitung**: pdf2image für die Konvertierung von PDF zu Bildern

### Ablauf

1. Dateibeobachter erkennt neue PDF-Datei
2. Datei wird in die Warteschlange gelegt
3. Verarbeitungs-Thread nimmt die Datei aus der Warteschlange
4. PDF wird in Bilder konvertiert
5. OCR wird auf jedem Bild durchgeführt
6. Ergebnisse werden gespeichert
7. Original-PDF wird in den Zielordner kopiert
8. OCR-Text wird in einer separaten Textdatei gespeichert

## Lizenz

Dieses Projekt steht unter der MIT-Lizenz.

## Beiträge

Beiträge sind willkommen! Bitte öffnen Sie ein Issue oder einen Pull Request.
