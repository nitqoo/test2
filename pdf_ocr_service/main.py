#!/usr/bin/env python3
"""
PDF OCR Service - Hauptprogramm mit GUI
Überwacht Ordner auf neue PDF-Dateien, führt OCR durch und verschiebt sie in Zielordner.
Läuft als Windows-Dienst oder als normales Programm.
"""

import sys
import os
import json
import logging
import threading
import queue
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# Qt Imports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem, QFileDialog,
    QInputDialog, QMessageBox, QTabWidget, QGroupBox, QFormLayout,
    QLineEdit, QCheckBox, QTextEdit, QStatusBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QIcon, QAction

# Dienst-Imports (nur auf Windows)
import win32serviceutil
import win32service
import win32event
import servicemanager

# OCR und Dateiverarbeitung
import pytesseract
from pdf2image import convert_from_path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PIL import Image  # Für pymupdf-Bildverarbeitung

# Konfiguration
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "service.log")

# Logging konfigurieren
def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Logging für das Programm einrichten"""
    logger = logging.getLogger("PDF_OCR_Service")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Handler für Datei
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    
    # Handler für Konsole
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()


class FolderMapping:
    """Repräsentiert eine Ordnerzuordnung (Quellordner -> Zielordner)"""
    
    def __init__(self, source_folder: str, target_folder: str, enabled: bool = True):
        self.source_folder = source_folder
        self.target_folder = target_folder
        self.enabled = enabled
    
    def to_dict(self) -> Dict:
        return {
            "source_folder": self.source_folder,
            "target_folder": self.target_folder,
            "enabled": self.enabled
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'FolderMapping':
        return cls(
            source_folder=data.get("source_folder", ""),
            target_folder=data.get("target_folder", ""),
            enabled=data.get("enabled", True)
        )
    
    def __repr__(self) -> str:
        return f"FolderMapping({self.source_folder} -> {self.target_folder})"


class ConfigManager:
    """Verwaltet die Konfiguration des Programms"""
    
    def __init__(self, config_file: str = CONFIG_FILE):
        self.config_file = config_file
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Konfiguration aus Datei laden"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Standardkonfiguration zurückgeben
            return {
                "watched_folders": [],
                "tesseract_path": "C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
                "service_enabled": False,
                "log_level": "INFO",
                "temp_dir": os.path.join(os.path.expanduser("~"), "AppData", "Local", "PDF_OCR_Service", "temp")
            }
    
    def save_config(self):
        """Konfiguration in Datei speichern"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            logger.info(f"Konfiguration in {self.config_file} gespeichert")
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Konfiguration: {e}")
    
    def get_folder_mappings(self) -> List[FolderMapping]:
        """Alle Ordnerzuordnungen abrufen"""
        mappings = []
        for mapping_data in self.config.get("watched_folders", []):
            mappings.append(FolderMapping.from_dict(mapping_data))
        return mappings
    
    def add_folder_mapping(self, source_folder: str, target_folder: str) -> bool:
        """Neue Ordnerzuordnung hinzufügen"""
        # Prüfen ob Quelle schon existiert
        for mapping in self.get_folder_mappings():
            if mapping.source_folder.lower() == source_folder.lower():
                logger.warning(f"Quellordner {source_folder} existiert bereits in der Konfiguration")
                return False
        
        new_mapping = FolderMapping(source_folder, target_folder)
        self.config.setdefault("watched_folders", []).append(new_mapping.to_dict())
        self.save_config()
        logger.info(f"Neue Ordnerzuordnung hinzugefügt: {source_folder} -> {target_folder}")
        return True
    
    def remove_folder_mapping(self, source_folder: str) -> bool:
        """Ordnerzuordnung entfernen"""
        initial_count = len(self.config.get("watched_folders", []))
        self.config["watched_folders"] = [
            mapping for mapping in self.config.get("watched_folders", [])
            if mapping.get("source_folder", "").lower() != source_folder.lower()
        ]
        
        if len(self.config.get("watched_folders", [])) < initial_count:
            self.save_config()
            logger.info(f"Ordnerzuordnung entfernt: {source_folder}")
            return True
        return False
    
    def update_folder_mapping(self, old_source: str, new_source: str, new_target: str, enabled: bool) -> bool:
        """Ordnerzuordnung aktualisieren"""
        for mapping in self.config.get("watched_folders", []):
            if mapping.get("source_folder", "").lower() == old_source.lower():
                mapping["source_folder"] = new_source
                mapping["target_folder"] = new_target
                mapping["enabled"] = enabled
                self.save_config()
                logger.info(f"Ordnerzuordnung aktualisiert: {old_source} -> {new_source}")
                return True
        return False
    
    @property
    def tesseract_path(self) -> str:
        return self.config.get("tesseract_path", "C:\\Program Files\\Tesseract-OCR\\tesseract.exe")
    
    @tesseract_path.setter
    def tesseract_path(self, value: str):
        self.config["tesseract_path"] = value
        self.save_config()
    
    @property
    def service_enabled(self) -> bool:
        return self.config.get("service_enabled", False)
    
    @service_enabled.setter
    def service_enabled(self, value: bool):
        self.config["service_enabled"] = value
        self.save_config()
    
    @property
    def log_level(self) -> str:
        return self.config.get("log_level", "INFO")
    
    @log_level.setter
    def log_level(self, value: str):
        self.config["log_level"] = value
        self.save_config()
    
    @property
    def temp_dir(self) -> str:
        return self.config.get("temp_dir", os.path.join(os.path.expanduser("~"), "AppData", "Local", "PDF_OCR_Service", "temp"))
    
    @temp_dir.setter
    def temp_dir(self, value: str):
        self.config["temp_dir"] = value
        self.save_config()


class PDFProcessor:
    """Verarbeitet PDF-Dateien mit OCR"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.temp_dir = config_manager.temp_dir
        
        # Temp-Verzeichnis erstellen
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Tesseract-Pfad setzen
        pytesseract.pytesseract.tesseract_cmd = config_manager.tesseract_path
    
    def process_pdf(self, pdf_path: str, target_folder: str) -> Tuple[bool, str]:
        """
        Verarbeitet eine PDF-Datei mit OCR und erstellt eine durchsuchbare PDF.
        Gibt (Erfolg, Nachricht) zurück.
        """
        try:
            logger.info(f"Verarbeite PDF: {pdf_path}")

            # Zielordner erstellen falls nicht vorhanden
            os.makedirs(target_folder, exist_ok=True)

            # Dateinamen für die durchsuchbare PDF
            pdf_name = os.path.basename(pdf_path)
            base_name = os.path.splitext(pdf_name)[0]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_pdf_path = os.path.join(target_folder, f"{base_name}_OCR_{timestamp}.pdf")

            # PDF mit pymupdf öffnen
            import fitz  # pymupdf
            pdf_document = fitz.open(pdf_path)

            # OCR auf jeder Seite durchführen und Text in die PDF einfügen
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)

                # Bild der Seite extrahieren
                pix = page.get_pixmap(dpi=300)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                # OCR auf dem Bild durchführen
                text = pytesseract.image_to_string(img, lang='deu+eng')

                # Text in die PDF-Seite einfügen (unsichtbar, aber durchsuchbar)
                page.insert_textbox(
                    fitz.Rect(0, 0, pix.width, pix.height),
                    text,
                    fontsize=1,  # Sehr kleine Schriftgröße
                    color=(0, 0, 0, 0),  # Vollständig transparent
                    overlay=True
                )

            # Durchsuchbare PDF speichern
            pdf_document.save(output_pdf_path)
            pdf_document.close()

            logger.info(f"Durchsuchbare PDF erstellt: {output_pdf_path}")

            # Original-PDF in Zielordner verschieben
            import shutil
            shutil.move(pdf_path, os.path.join(target_folder, pdf_name))

            return True, f"Erfolgreich verarbeitet. Durchsuchbare PDF: {output_pdf_path}"
            
        except Exception as e:
            logger.error(f"Fehler bei der OCR-Verarbeitung von {pdf_path}: {e}", exc_info=True)
            return False, f"Fehler bei der Verarbeitung: {str(e)}"


class FileWatcher(FileSystemEventHandler):
    """Überwacht Dateisystemereignisse für neue PDF-Dateien"""
    
    def __init__(self, processor: PDFProcessor, folder_mappings: List[FolderMapping], queue: queue.Queue):
        super().__init__()
        self.processor = processor
        self.folder_mappings = folder_mappings
        self.queue = queue
        self.processed_files = set()  # Verhindert doppelte Verarbeitung
    
    def on_created(self, event):
        """Wird aufgerufen, wenn eine Datei erstellt wird"""
        if not event.is_directory:
            file_path = event.src_path
            if file_path.lower().endswith('.pdf'):
                # Prüfen ob die Datei schon verarbeitet wurde
                if file_path not in self.processed_files:
                    self.processed_files.add(file_path)
                    
                    # Finde die passende Ordnerzuordnung
                    for mapping in self.folder_mappings:
                        if mapping.enabled and file_path.startswith(mapping.source_folder):
                            # In die Warteschlange legen
                            self.queue.put((file_path, mapping.target_folder))
                            logger.info(f"Neue PDF gefunden: {file_path} -> Ziel: {mapping.target_folder}")
                            break
    
    def on_modified(self, event):
        """Wird aufgerufen, wenn eine Datei modifiziert wird"""
        # Nicht benötigt für diese Anwendung
        pass


class ProcessingThread(QThread):
    """Thread für die Verarbeitung der PDF-Dateien"""
    
    processing_signal = pyqtSignal(str, str, bool, str)  # file_path, target_folder, success, message
    
    def __init__(self, processor: PDFProcessor, queue: queue.Queue, parent=None):
        super().__init__(parent)
        self.processor = processor
        self.queue = queue
        self._running = True
    
    def run(self):
        """Hauptschleife für die Verarbeitung"""
        logger.info("Verarbeitungs-Thread gestartet")
        
        while self._running:
            try:
                # Auf neue Dateien in der Warteschlange warten
                file_path, target_folder = self.queue.get(timeout=1)
                
                # Datei verarbeiten
                success, message = self.processor.process_pdf(file_path, target_folder)
                
                # Signal an GUI senden
                self.processing_signal.emit(file_path, target_folder, success, message)
                
                # Warteschlange als erledigt markieren
                self.queue.task_done()
                
            except queue.Empty:
                # Keine Dateien in der Warteschlange, weiter warten
                continue
            except Exception as e:
                logger.error(f"Fehler im Verarbeitungs-Thread: {e}", exc_info=True)
    
    def stop(self):
        """Thread beenden"""
        self._running = False
        self.wait()


class ServiceWorker(QObject):
    """Worker für den Windows-Dienst"""
    
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.processor = PDFProcessor(config_manager)
        self.queue = queue.Queue()
        self.observer = None
        self.watcher = None
    
    def start(self):
        """Dienst starten"""
        logger.info("PDF OCR Dienst wird gestartet...")
        
        # Ordnerzuordnungen laden
        folder_mappings = self.config_manager.get_folder_mappings()
        enabled_mappings = [m for m in folder_mappings if m.enabled]
        
        if not enabled_mappings:
            logger.warning("Keine aktivierten Ordnerzuordnungen gefunden. Dienst läuft, aber überwacht keine Ordner.")
        
        # Dateibeobachter starten
        self.watcher = FileWatcher(self.processor, enabled_mappings, self.queue)
        self.observer = Observer()
        
        for mapping in enabled_mappings:
            if os.path.isdir(mapping.source_folder):
                self.observer.schedule(self.watcher, mapping.source_folder, recursive=True)
                logger.info(f"Überwache Ordner: {mapping.source_folder}")
            else:
                logger.error(f"Quellordner existiert nicht: {mapping.source_folder}")
        
        self.observer.start()
        
        # Verarbeitungs-Thread starten
        self.processing_thread = threading.Thread(
            target=self._process_queue,
            daemon=True
        )
        self.processing_thread.start()
        
        logger.info("PDF OCR Dienst erfolgreich gestartet")
    
    def _process_queue(self):
        """Verarbeitet die Warteschlange"""
        while True:
            try:
                file_path, target_folder = self.queue.get()
                success, message = self.processor.process_pdf(file_path, target_folder)
                
                if success:
                    logger.info(f"Erfolgreich verarbeitet: {file_path} -> {target_folder}")
                else:
                    logger.error(f"Fehler bei Verarbeitung: {file_path} -> {target_folder}: {message}")
                
                self.queue.task_done()
            except Exception as e:
                logger.error(f"Fehler in der Verarbeitungs-Warteschlange: {e}", exc_info=True)
    
    def stop(self):
        """Dienst stoppen"""
        logger.info("PDF OCR Dienst wird gestoppt...")
        
        if self.observer:
            self.observer.stop()
            self.observer.join()
        
        logger.info("PDF OCR Dienst erfolgreich gestoppt")


class PDFOCRService(win32serviceutil.ServiceFramework):
    """Windows-Dienst für PDF OCR"""
    
    _svc_name_ = 'PDFOCRService'
    _svc_display_name_ = 'PDF OCR Service'
    _svc_description_ = 'Überwacht Ordner auf neue PDF-Dateien, führt OCR durch und verschiebt sie in Zielordner.'
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.worker = None
        self.config_manager = ConfigManager()
    
    def SvcStop(self):
        """Dienst stoppen"""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        
        if self.worker:
            self.worker.stop()
        
        logger.info("Dienst-Stoppsignal empfangen")
    
    def SvcDoRun(self):
        """Dienst-Hauptschleife"""
        logger.info("PDF OCR Dienst startet...")
        
        # Worker initialisieren und starten
        self.worker = ServiceWorker(self.config_manager)
        self.worker.start()
        
        # Auf Stop-Signal warten
        win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
        
        # Aufräumen
        if self.worker:
            self.worker.stop()


class MainWindow(QMainWindow):
    """Hauptfenster der GUI"""
    
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.processor = PDFProcessor(config_manager)
        self.queue = queue.Queue()
        self.observer = None
        self.watcher = None
        self.processing_thread = None
        
        self.setWindowTitle("PDF OCR Service")
        self.setWindowIcon(QIcon.fromTheme("document-text"))
        self.setGeometry(100, 100, 800, 600)
        
        self.init_ui()
        self.load_folder_mappings()
        self.update_service_status()
        
        # Timer für regelmäßige Überprüfung des Dienststatus
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_service_status)
        self.status_timer.start(5000)  # Alle 5 Sekunden
    
    def init_ui(self):
        """UI initialisieren"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        
        # Tab-Widget für verschiedene Ansichten
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)
        
        # Tab für Ordnerverwaltung
        folders_tab = QWidget()
        tab_widget.addTab(folders_tab, "Ordnerverwaltung")
        self.init_folders_tab(folders_tab)
        
        # Tab für Einstellungen
        settings_tab = QWidget()
        tab_widget.addTab(settings_tab, "Einstellungen")
        self.init_settings_tab(settings_tab)
        
        # Tab für Protokoll
        log_tab = QWidget()
        tab_widget.addTab(log_tab, "Protokoll")
        self.init_log_tab(log_tab)
        
        # Statusleiste
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Bereit")
        
        # Menüleiste
        self.create_menu()
    
    def create_menu(self):
        """Menüleiste erstellen"""
        menubar = self.menuBar()
        
        # Datei-Menü
        file_menu = menubar.addMenu("Datei")
        
        # Dienst-Menü
        service_menu = menubar.addMenu("Dienst")
        
        install_action = QAction("Dienst installieren", self)
        install_action.triggered.connect(self.install_service)
        service_menu.addAction(install_action)
        
        uninstall_action = QAction("Dienst deinstallieren", self)
        uninstall_action.triggered.connect(self.uninstall_service)
        service_menu.addAction(uninstall_action)
        
        start_action = QAction("Dienst starten", self)
        start_action.triggered.connect(self.start_service)
        service_menu.addAction(start_action)
        
        stop_action = QAction("Dienst stoppen", self)
        stop_action.triggered.connect(self.stop_service)
        service_menu.addAction(stop_action)
        
        service_menu.addSeparator()
        
        exit_action = QAction("Beenden", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
    
    def init_folders_tab(self, tab: QWidget):
        """Tab für Ordnerverwaltung initialisieren"""
        layout = QVBoxLayout(tab)
        
        # Gruppe für überwachte Ordner
        folders_group = QGroupBox("Überwachte Ordner")
        layout.addWidget(folders_group)
        
        folders_layout = QVBoxLayout(folders_group)
        
        # Liste der Ordnerzuordnungen
        self.folder_list = QListWidget()
        self.folder_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        folders_layout.addWidget(self.folder_list)
        
        # Buttons für Ordnerverwaltung
        buttons_layout = QHBoxLayout()
        folders_layout.addLayout(buttons_layout)
        
        add_btn = QPushButton("Hinzufügen")
        add_btn.clicked.connect(self.add_folder_mapping)
        buttons_layout.addWidget(add_btn)
        
        edit_btn = QPushButton("Bearbeiten")
        edit_btn.clicked.connect(self.edit_folder_mapping)
        buttons_layout.addWidget(edit_btn)
        
        remove_btn = QPushButton("Entfernen")
        remove_btn.clicked.connect(self.remove_folder_mapping)
        buttons_layout.addWidget(remove_btn)
        
        # Gruppe für Überwachungsstatus
        status_group = QGroupBox("Überwachungsstatus")
        layout.addWidget(status_group)
        
        status_layout = QVBoxLayout(status_group)
        
        self.watch_status_label = QLabel("Überwachung: Inaktiv")
        status_layout.addWidget(self.watch_status_label)
        
        # Buttons für Überwachung
        watch_buttons_layout = QHBoxLayout()
        status_layout.addLayout(watch_buttons_layout)
        
        self.start_watch_btn = QPushButton("Überwachung starten")
        self.start_watch_btn.clicked.connect(self.start_watching)
        watch_buttons_layout.addWidget(self.start_watch_btn)
        
        self.stop_watch_btn = QPushButton("Überwachung stoppen")
        self.stop_watch_btn.clicked.connect(self.stop_watching)
        self.stop_watch_btn.setEnabled(False)
        watch_buttons_layout.addWidget(self.stop_watch_btn)
    
    def init_settings_tab(self, tab: QWidget):
        """Tab für Einstellungen initialisieren"""
        layout = QVBoxLayout(tab)
        
        # Gruppe für Tesseract-Einstellungen
        tesseract_group = QGroupBox("Tesseract OCR")
        layout.addWidget(tesseract_group)
        
        tesseract_layout = QFormLayout(tesseract_group)
        
        self.tesseract_path_edit = QLineEdit(self.config_manager.tesseract_path)
        tesseract_layout.addRow("Tesseract Pfad:", self.tesseract_path_edit)
        
        tesseract_browse_btn = QPushButton("Durchsuchen...")
        tesseract_browse_btn.clicked.connect(self.browse_tesseract_path)
        tesseract_layout.addRow("", tesseract_browse_btn)
        
        # Gruppe für Temp-Verzeichnis
        temp_group = QGroupBox("Temporäres Verzeichnis")
        layout.addWidget(temp_group)
        
        temp_layout = QFormLayout(temp_group)
        
        self.temp_dir_edit = QLineEdit(self.config_manager.temp_dir)
        temp_layout.addRow("Temp-Verzeichnis:", self.temp_dir_edit)
        
        temp_browse_btn = QPushButton("Durchsuchen...")
        temp_browse_btn.clicked.connect(self.browse_temp_dir)
        temp_layout.addRow("", temp_browse_btn)
        
        # Gruppe für Protokollierung
        log_group = QGroupBox("Protokollierung")
        layout.addWidget(log_group)
        
        log_layout = QFormLayout(log_group)
        
        self.log_level_combo = QLineEdit(self.config_manager.log_level)
        log_layout.addRow("Log-Level:", self.log_level_combo)
        
        # Speichern-Button
        save_btn = QPushButton("Einstellungen speichern")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)
    
    def init_log_tab(self, tab: QWidget):
        """Tab für Protokoll initialisieren"""
        layout = QVBoxLayout(tab)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        # Button zum Aktualisieren des Protokolls
        refresh_btn = QPushButton("Protokoll aktualisieren")
        refresh_btn.clicked.connect(self.refresh_log)
        layout.addWidget(refresh_btn)
        
        # Button zum Löschen des Protokolls
        clear_btn = QPushButton("Protokoll löschen")
        clear_btn.clicked.connect(self.clear_log)
        layout.addWidget(clear_btn)
    
    def load_folder_mappings(self):
        """Ordnerzuordnungen in die Liste laden"""
        self.folder_list.clear()
        
        mappings = self.config_manager.get_folder_mappings()
        for mapping in mappings:
            item = QListWidgetItem(f"{mapping.source_folder} -> {mapping.target_folder}")
            item.setData(Qt.ItemDataRole.UserRole, mapping.source_folder)
            if not mapping.enabled:
                item.setText(f"[DEAKTIVIERT] {mapping.source_folder} -> {mapping.target_folder}")
            self.folder_list.addItem(item)
    
    def add_folder_mapping(self):
        """Neue Ordnerzuordnung hinzufügen"""
        source_folder = QFileDialog.getExistingDirectory(
            self, "Quellordner auswählen"
        )
        
        if not source_folder:
            return
        
        target_folder = QFileDialog.getExistingDirectory(
            self, "Zielordner auswählen"
        )
        
        if not target_folder:
            return
        
        # Prüfen ob die Zuordnung hinzugefügt werden konnte
        if self.config_manager.add_folder_mapping(source_folder, target_folder):
            self.load_folder_mappings()
            QMessageBox.information(self, "Erfolg", "Ordnerzuordnung erfolgreich hinzugefügt")
        else:
            QMessageBox.warning(self, "Fehler", "Diese Ordnerzuordnung existiert bereits")
    
    def edit_folder_mapping(self):
        """Ordnerzuordnung bearbeiten"""
        selected_items = self.folder_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Fehler", "Bitte wählen Sie eine Ordnerzuordnung aus")
            return
        
        item = selected_items[0]
        old_source = item.data(Qt.ItemDataRole.UserRole)
        
        # Aktuelle Zuordnung finden
        mappings = self.config_manager.get_folder_mappings()
        current_mapping = None
        for mapping in mappings:
            if mapping.source_folder == old_source:
                current_mapping = mapping
                break
        
        if not current_mapping:
            QMessageBox.warning(self, "Fehler", "Ordnerzuordnung nicht gefunden")
            return
        
        # Dialog für neue Werte
        new_source, ok = QInputDialog.getText(
            self, "Quellordner", "Neuer Quellordner:",
            text=current_mapping.source_folder
        )
        
        if not ok:
            return
        
        new_target, ok = QInputDialog.getText(
            self, "Zielordner", "Neuer Zielordner:",
            text=current_mapping.target_folder
        )
        
        if not ok:
            return
        
        # Prüfen ob aktiviert
        enabled, ok = QInputDialog.getText(
            self, "Aktiviert", "Aktiviert (true/false):",
            text=str(current_mapping.enabled)
        )
        
        if not ok:
            return
        
        enabled_bool = enabled.lower() == 'true'
        
        # Zuordnung aktualisieren
        if self.config_manager.update_folder_mapping(
            old_source, new_source, new_target, enabled_bool
        ):
            self.load_folder_mappings()
            QMessageBox.information(self, "Erfolg", "Ordnerzuordnung erfolgreich aktualisiert")
        else:
            QMessageBox.warning(self, "Fehler", "Ordnerzuordnung konnte nicht aktualisiert werden")
    
    def remove_folder_mapping(self):
        """Ordnerzuordnung entfernen"""
        selected_items = self.folder_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Fehler", "Bitte wählen Sie eine Ordnerzuordnung aus")
            return
        
        item = selected_items[0]
        source_folder = item.data(Qt.ItemDataRole.UserRole)
        
        confirm = QMessageBox.question(
            self, "Bestätigung",
            f"Möchten Sie die Ordnerzuordnung für {source_folder} wirklich entfernen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            if self.config_manager.remove_folder_mapping(source_folder):
                self.load_folder_mappings()
                QMessageBox.information(self, "Erfolg", "Ordnerzuordnung erfolgreich entfernt")
            else:
                QMessageBox.warning(self, "Fehler", "Ordnerzuordnung konnte nicht entfernt werden")
    
    def browse_tesseract_path(self):
        """Tesseract-Pfad auswählen"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Tesseract-Executable auswählen",
            self.tesseract_path_edit.text(),
            "Executable Files (*.exe);;All Files (*)"
        )
        
        if file_path:
            self.tesseract_path_edit.setText(file_path)
    
    def browse_temp_dir(self):
        """Temp-Verzeichnis auswählen"""
        dir_path = QFileDialog.getExistingDirectory(
            self, "Temp-Verzeichnis auswählen",
            self.temp_dir_edit.text()
        )
        
        if dir_path:
            self.temp_dir_edit.setText(dir_path)
    
    def save_settings(self):
        """Einstellungen speichern"""
        self.config_manager.tesseract_path = self.tesseract_path_edit.text()
        self.config_manager.temp_dir = self.temp_dir_edit.text()
        self.config_manager.log_level = self.log_level_combo.text()
        
        # Logger neu konfigurieren
        global logger
        logger = setup_logging(self.config_manager.log_level)
        
        QMessageBox.information(self, "Erfolg", "Einstellungen erfolgreich gespeichert")
    
    def start_watching(self):
        """Überwachung starten"""
        if self.observer and self.observer.is_alive():
            QMessageBox.warning(self, "Fehler", "Überwachung läuft bereits")
            return
        
        # Ordnerzuordnungen laden
        folder_mappings = self.config_manager.get_folder_mappings()
        enabled_mappings = [m for m in folder_mappings if m.enabled]
        
        if not enabled_mappings:
            QMessageBox.warning(self, "Fehler", "Keine aktivierten Ordnerzuordnungen zum Überwachen")
            return
        
        # Dateibeobachter starten
        self.watcher = FileWatcher(self.processor, enabled_mappings, self.queue)
        self.observer = Observer()
        
        for mapping in enabled_mappings:
            if os.path.isdir(mapping.source_folder):
                self.observer.schedule(self.watcher, mapping.source_folder, recursive=True)
                logger.info(f"Überwache Ordner: {mapping.source_folder}")
            else:
                logger.error(f"Quellordner existiert nicht: {mapping.source_folder}")
                QMessageBox.warning(
                    self, "Fehler",
                    f"Quellordner existiert nicht: {mapping.source_folder}"
                )
        
        self.observer.start()
        
        # Verarbeitungs-Thread starten
        self.processing_thread = ProcessingThread(self.processor, self.queue)
        self.processing_thread.processing_signal.connect(self.on_processing_complete)
        self.processing_thread.start()
        
        # UI aktualisieren
        self.watch_status_label.setText("Überwachung: Aktiv")
        self.start_watch_btn.setEnabled(False)
        self.stop_watch_btn.setEnabled(True)
        self.status_bar.showMessage("Überwachung aktiv")
        
        logger.info("Überwachung gestartet")
    
    def stop_watching(self):
        """Überwachung stoppen"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
        
        if self.processing_thread:
            self.processing_thread.stop()
            self.processing_thread = None
        
        # UI aktualisieren
        self.watch_status_label.setText("Überwachung: Inaktiv")
        self.start_watch_btn.setEnabled(True)
        self.stop_watch_btn.setEnabled(False)
        self.status_bar.showMessage("Überwachung inaktiv")
        
        logger.info("Überwachung gestoppt")
    
    def on_processing_complete(self, file_path: str, target_folder: str, success: bool, message: str):
        """Wird aufgerufen, wenn eine Datei verarbeitet wurde"""
        if success:
            logger.info(f"Verarbeitung erfolgreich: {file_path} -> {target_folder}")
            self.status_bar.showMessage(f"Erfolg: {message}")
        else:
            logger.error(f"Verarbeitung fehlgeschlagen: {file_path} -> {target_folder}: {message}")
            self.status_bar.showMessage(f"Fehler: {message}")
        
        # Protokoll aktualisieren
        self.refresh_log()
    
    def refresh_log(self):
        """Protokoll aktualisieren"""
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                log_content = f.read()
            self.log_text.setPlainText(log_content)
        except FileNotFoundError:
            self.log_text.setPlainText("Kein Protokoll verfügbar")
        except Exception as e:
            self.log_text.setPlainText(f"Fehler beim Laden des Protokolls: {e}")
    
    def clear_log(self):
        """Protokoll löschen"""
        confirm = QMessageBox.question(
            self, "Bestätigung",
            "Möchten Sie das Protokoll wirklich löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                with open(LOG_FILE, 'w', encoding='utf-8') as f:
                    f.write("")
                self.log_text.clear()
                logger.info("Protokoll gelöscht")
            except Exception as e:
                QMessageBox.warning(self, "Fehler", f"Protokoll konnte nicht gelöscht werden: {e}")
    
    def update_service_status(self):
        """Dienststatus aktualisieren"""
        try:
            # Prüfen ob der Dienst installiert ist
            service_name = PDFOCRService._svc_name_
            try:
                status = win32serviceutil.QueryServiceStatus(service_name)
                if status[1] == win32service.SERVICE_RUNNING:
                    self.status_bar.showMessage(f"Dienst: Läuft (PID: {status[2]})")
                elif status[1] == win32service.SERVICE_STOPPED:
                    self.status_bar.showMessage("Dienst: Gestoppt")
                else:
                    self.status_bar.showMessage(f"Dienst: Status {status[1]}")
            except Exception:
                self.status_bar.showMessage("Dienst: Nicht installiert")
        except Exception as e:
            logger.error(f"Fehler beim Abfragen des Dienststatus: {e}")
            self.status_bar.showMessage("Dienststatus: Unbekannt")
    
    def install_service(self):
        """Dienst installieren"""
        try:
            # Pfad zum Dienst-Executable
            service_exe = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "pdf_ocr_service.exe"
            )
            
            if not os.path.exists(service_exe):
                QMessageBox.warning(
                    self, "Fehler",
                    f"Dienst-Executable nicht gefunden: {service_exe}. "
                    "Bitte erstellen Sie zuerst das Executable mit pyinstaller."
                )
                return
            
            # Dienst installieren
            win32serviceutil.InstallService(
                PDFOCRService._svc_name_,
                PDFOCRService._svc_display_name_,
                service_exe,
                startType=win32service.SERVICE_AUTO_START
            )
            
            QMessageBox.information(self, "Erfolg", "Dienst erfolgreich installiert")
            self.update_service_status()
            
        except Exception as e:
            logger.error(f"Fehler beim Installieren des Dienstes: {e}", exc_info=True)
            QMessageBox.warning(self, "Fehler", f"Dienst konnte nicht installiert werden: {e}")
    
    def uninstall_service(self):
        """Dienst deinstallieren"""
        try:
            win32serviceutil.RemoveService(PDFOCRService._svc_name_)
            QMessageBox.information(self, "Erfolg", "Dienst erfolgreich deinstalliert")
            self.update_service_status()
        except Exception as e:
            logger.error(f"Fehler beim Deinstallieren des Dienstes: {e}", exc_info=True)
            QMessageBox.warning(self, "Fehler", f"Dienst konnte nicht deinstalliert werden: {e}")
    
    def start_service(self):
        """Dienst starten"""
        try:
            win32serviceutil.StartService(PDFOCRService._svc_name_)
            QMessageBox.information(self, "Erfolg", "Dienst erfolgreich gestartet")
            self.update_service_status()
        except Exception as e:
            logger.error(f"Fehler beim Starten des Dienstes: {e}", exc_info=True)
            QMessageBox.warning(self, "Fehler", f"Dienst konnte nicht gestartet werden: {e}")
    
    def stop_service(self):
        """Dienst stoppen"""
        try:
            win32serviceutil.StopService(PDFOCRService._svc_name_)
            QMessageBox.information(self, "Erfolg", "Dienst erfolgreich gestoppt")
            self.update_service_status()
        except Exception as e:
            logger.error(f"Fehler beim Stoppen des Dienstes: {e}", exc_info=True)
            QMessageBox.warning(self, "Fehler", f"Dienst konnte nicht gestoppt werden: {e}")
    
    def closeEvent(self, event):
        """Fenster schließen"""
        # Überwachung stoppen
        self.stop_watching()
        
        # Dienststatus aktualisieren
        self.update_service_status()
        
        event.accept()


def main():
    """Hauptfunktion"""
    app = QApplication(sys.argv)
    
    # Konfiguration laden
    config_manager = ConfigManager()
    
    # Hauptfenster anzeigen
    window = MainWindow(config_manager)
    window.show()
    
    # Anwendung starten
    sys.exit(app.exec())


if __name__ == "__main__":
    # Prüfen ob als Dienst gestartet
    if len(sys.argv) > 1 and sys.argv[1] == "--service":
        # Als Dienst starten
        win32serviceutil.HandleCommandLine(PDFOCRService)
    else:
        # Als normale Anwendung starten
        main()
