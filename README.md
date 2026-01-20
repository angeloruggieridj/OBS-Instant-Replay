# OBS Instant Replay

[![Version](https://img.shields.io/badge/version-1.0--beta4-blue.svg)](https://github.com/angeloruggieridj/OBS-Instant-Replay/releases)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[English](#english) | [Italiano](#italiano) | [Español](#español) | [Français](#français) | [Deutsch](#deutsch)

---

## English

Advanced replay management system for OBS Studio with integrated web interface.

### Features

- **Integrated Web Interface**: Browser dock directly in OBS Studio
- **Complete Replay Management**:
  - Grid view with video previews
  - Favorites system
  - Playlist/playback queue
  - Custom categories with colors
  - Hide videos
  - Advanced search and filters

- **Advanced Controls**:
  - Playback speed (0.1x - 2.0x)
  - Card size zoom (120-320px)
  - Light/dark themes
  - Create highlights video from favorites

- **READY Mode**: Video is loaded but waits for manual start (perfect for Stream Deck)

- **Auto-Update System**:
  - Check for updates from GitHub
  - Download and install updates directly from the app
  - Automatic backup of old files

### Requirements

- OBS Studio 28.0+ (with Python scripting support)
- Python 3.6+
- FFmpeg and FFprobe (in system PATH)

### Installation

#### Step 1: Install FFmpeg

**Windows:**
1. Download FFmpeg from [ffmpeg.org](https://ffmpeg.org/download.html) or use [gyan.dev builds](https://www.gyan.dev/ffmpeg/builds/)
2. Extract the archive to `C:\ffmpeg`
3. Add FFmpeg to system PATH:
   - Open "System Properties" > "Environment Variables"
   - Under "System variables", find "Path" and click "Edit"
   - Add `C:\ffmpeg\bin`
   - Click OK and restart your terminal
4. Verify installation: `ffmpeg -version`

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Linux (Fedora):**
```bash
sudo dnf install ffmpeg
```

#### Step 2: Install the Script

1. Download `obs_replay_manager_browser.py` and `replay_http_server.py`
2. Copy both files to your OBS Studio scripts directory:
   - **Windows**: `%APPDATA%\obs-studio\scripts\`
   - **macOS**: `~/Library/Application Support/obs-studio/scripts/`
   - **Linux**: `~/.config/obs-studio/scripts/`
3. In OBS Studio, go to `Tools > Scripts`
4. Click `+` and select `obs_replay_manager_browser.py`
5. Configure the replay folder in script settings
6. Set the media source name and target scene

#### Step 3: Add the Browser Dock

1. In OBS, go to `Docks > Custom Browser Docks`
2. Add a new dock:
   - **Name**: Replay Manager
   - **URL**: `http://localhost:8765`
3. Click "Apply"
4. The dock will appear in `View > Docks > Replay Manager`

### Usage

1. Start OBS Studio
2. The script will automatically start the HTTP server
3. Use the web interface to manage your replays
4. Load videos directly into the configured media source
5. Use right-click on video cards to assign categories

### Main Files

- `obs_replay_manager_browser.py`: Main OBS Studio script
- `replay_http_server.py`: HTTP server with REST API and web interface

---

## Italiano

Sistema avanzato di gestione replay per OBS Studio con interfaccia web integrata.

### Caratteristiche

- **Interfaccia Web Integrata**: Browser dock direttamente in OBS Studio
- **Gestione Completa Replay**:
  - Visualizzazione griglia con anteprime video
  - Sistema di preferiti
  - Playlist/coda di riproduzione
  - Categorie personalizzate con colori
  - Nascondi video
  - Ricerca e filtri avanzati

- **Controlli Avanzati**:
  - Velocità di riproduzione (0.1x - 2.0x)
  - Zoom dimensione card (120-320px)
  - Temi chiaro/scuro
  - Creazione video highlights dai preferiti

- **Modalità READY**: Il video viene caricato ma attende l'avvio manuale (perfetto per Stream Deck)

### Requisiti

- OBS Studio 28.0+ (con supporto Python scripting)
- Python 3.6+
- FFmpeg e FFprobe (nel PATH di sistema)

### Installazione

#### Passo 1: Installare FFmpeg

**Windows:**
1. Scarica FFmpeg da [ffmpeg.org](https://ffmpeg.org/download.html) o usa le build di [gyan.dev](https://www.gyan.dev/ffmpeg/builds/)
2. Estrai l'archivio in `C:\ffmpeg`
3. Aggiungi FFmpeg al PATH di sistema:
   - Apri "Proprietà del sistema" > "Variabili d'ambiente"
   - In "Variabili di sistema", trova "Path" e clicca "Modifica"
   - Aggiungi `C:\ffmpeg\bin`
   - Clicca OK e riavvia il terminale
4. Verifica l'installazione: `ffmpeg -version`

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

#### Passo 2: Installare lo Script

1. Scarica `obs_replay_manager_browser.py` e `replay_http_server.py`
2. Copia entrambi i file nella directory degli script di OBS Studio:
   - **Windows**: `%APPDATA%\obs-studio\scripts\`
   - **macOS**: `~/Library/Application Support/obs-studio/scripts/`
   - **Linux**: `~/.config/obs-studio/scripts/`
3. In OBS Studio, vai su `Strumenti > Script`
4. Clicca su `+` e seleziona `obs_replay_manager_browser.py`
5. Configura la cartella dei replay nelle impostazioni dello script
6. Imposta il nome della fonte multimediale e la scena target

#### Passo 3: Aggiungere il Browser Dock

1. In OBS, vai su `Pannelli > Custom Browser Docks`
2. Aggiungi un nuovo dock:
   - **Nome**: Replay Manager
   - **URL**: `http://localhost:8765`
3. Clicca "Applica"
4. Il dock apparirà in `Visualizza > Pannelli > Replay Manager`

### Utilizzo

1. Avvia OBS Studio
2. Lo script avvierà automaticamente il server HTTP
3. Utilizza l'interfaccia web per gestire i tuoi replay
4. Carica i video direttamente nella sorgente media configurata
5. Usa il tasto destro sulle card per assegnare categorie

---

## Español

Sistema avanzado de gestión de repeticiones para OBS Studio con interfaz web integrada.

### Características

- **Interfaz Web Integrada**: Panel de navegador directamente en OBS Studio
- **Gestión Completa de Repeticiones**:
  - Vista en cuadrícula con vistas previas de video
  - Sistema de favoritos
  - Lista de reproducción/cola
  - Categorías personalizadas con colores
  - Ocultar videos
  - Búsqueda y filtros avanzados

- **Controles Avanzados**:
  - Velocidad de reproducción (0.1x - 2.0x)
  - Zoom del tamaño de tarjeta (120-320px)
  - Temas claro/oscuro
  - Crear video de highlights desde favoritos

- **Modo READY**: El video se carga pero espera inicio manual (perfecto para Stream Deck)

### Requisitos

- OBS Studio 28.0+ (con soporte de scripts Python)
- Python 3.6+
- FFmpeg y FFprobe (en el PATH del sistema)

### Instalación

#### Paso 1: Instalar FFmpeg

**Windows:**
1. Descarga FFmpeg desde [ffmpeg.org](https://ffmpeg.org/download.html)
2. Extrae el archivo en `C:\ffmpeg`
3. Añade FFmpeg al PATH del sistema:
   - Abre "Propiedades del sistema" > "Variables de entorno"
   - En "Variables del sistema", busca "Path" y haz clic en "Editar"
   - Añade `C:\ffmpeg\bin`
   - Haz clic en OK y reinicia la terminal
4. Verifica la instalación: `ffmpeg -version`

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

#### Paso 2: Instalar el Script

1. Descarga `obs_replay_manager_browser.py` y `replay_http_server.py`
2. Copia ambos archivos en el directorio de scripts de OBS Studio:
   - **Windows**: `%APPDATA%\obs-studio\scripts\`
   - **macOS**: `~/Library/Application Support/obs-studio/scripts/`
   - **Linux**: `~/.config/obs-studio/scripts/`
3. En OBS Studio, ve a `Herramientas > Scripts`
4. Haz clic en `+` y selecciona `obs_replay_manager_browser.py`
5. Configura la carpeta de repeticiones en los ajustes del script

---

## Français

Système avancé de gestion des replays pour OBS Studio avec interface web intégrée.

### Fonctionnalités

- **Interface Web Intégrée**: Dock de navigateur directement dans OBS Studio
- **Gestion Complète des Replays**:
  - Affichage en grille avec aperçus vidéo
  - Système de favoris
  - Playlist/file d'attente de lecture
  - Catégories personnalisées avec couleurs
  - Masquer les vidéos
  - Recherche et filtres avancés

- **Contrôles Avancés**:
  - Vitesse de lecture (0.1x - 2.0x)
  - Zoom de la taille des cartes (120-320px)
  - Thèmes clair/sombre
  - Création de vidéo highlights à partir des favoris

- **Mode READY**: La vidéo est chargée mais attend un démarrage manuel (parfait pour Stream Deck)

### Prérequis

- OBS Studio 28.0+ (avec support des scripts Python)
- Python 3.6+
- FFmpeg et FFprobe (dans le PATH système)

### Installation

#### Étape 1: Installer FFmpeg

**Windows:**
1. Téléchargez FFmpeg depuis [ffmpeg.org](https://ffmpeg.org/download.html)
2. Extrayez l'archive dans `C:\ffmpeg`
3. Ajoutez FFmpeg au PATH système:
   - Ouvrez "Propriétés système" > "Variables d'environnement"
   - Dans "Variables système", trouvez "Path" et cliquez sur "Modifier"
   - Ajoutez `C:\ffmpeg\bin`
   - Cliquez sur OK et redémarrez le terminal
4. Vérifiez l'installation: `ffmpeg -version`

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

#### Étape 2: Installer le Script

1. Téléchargez `obs_replay_manager_browser.py` et `replay_http_server.py`
2. Copiez les deux fichiers dans le répertoire des scripts OBS Studio:
   - **Windows**: `%APPDATA%\obs-studio\scripts\`
   - **macOS**: `~/Library/Application Support/obs-studio/scripts/`
   - **Linux**: `~/.config/obs-studio/scripts/`
3. Dans OBS Studio, allez dans `Outils > Scripts`
4. Cliquez sur `+` et sélectionnez `obs_replay_manager_browser.py`
5. Configurez le dossier des replays dans les paramètres du script

---

## Deutsch

Fortschrittliches Replay-Verwaltungssystem für OBS Studio mit integrierter Web-Oberfläche.

### Funktionen

- **Integrierte Web-Oberfläche**: Browser-Dock direkt in OBS Studio
- **Vollständige Replay-Verwaltung**:
  - Rasteransicht mit Video-Vorschauen
  - Favoritensystem
  - Playlist/Wiedergabewarteschlange
  - Benutzerdefinierte Kategorien mit Farben
  - Videos ausblenden
  - Erweiterte Suche und Filter

- **Erweiterte Steuerung**:
  - Wiedergabegeschwindigkeit (0.1x - 2.0x)
  - Kartengrößen-Zoom (120-320px)
  - Helle/dunkle Themen
  - Highlights-Video aus Favoriten erstellen

- **READY-Modus**: Video wird geladen, wartet aber auf manuellen Start (perfekt für Stream Deck)

### Voraussetzungen

- OBS Studio 28.0+ (mit Python-Scripting-Unterstützung)
- Python 3.6+
- FFmpeg und FFprobe (im System-PATH)

### Installation

#### Schritt 1: FFmpeg installieren

**Windows:**
1. Laden Sie FFmpeg von [ffmpeg.org](https://ffmpeg.org/download.html) herunter
2. Entpacken Sie das Archiv nach `C:\ffmpeg`
3. Fügen Sie FFmpeg zum System-PATH hinzu:
   - Öffnen Sie "Systemeigenschaften" > "Umgebungsvariablen"
   - Unter "Systemvariablen" finden Sie "Path" und klicken Sie auf "Bearbeiten"
   - Fügen Sie `C:\ffmpeg\bin` hinzu
   - Klicken Sie auf OK und starten Sie das Terminal neu
4. Überprüfen Sie die Installation: `ffmpeg -version`

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

#### Schritt 2: Das Skript installieren

1. Laden Sie `obs_replay_manager_browser.py` und `replay_http_server.py` herunter
2. Kopieren Sie beide Dateien in das OBS Studio Skriptverzeichnis:
   - **Windows**: `%APPDATA%\obs-studio\scripts\`
   - **macOS**: `~/Library/Application Support/obs-studio/scripts/`
   - **Linux**: `~/.config/obs-studio/scripts/`
3. Gehen Sie in OBS Studio zu `Werkzeuge > Skripte`
4. Klicken Sie auf `+` und wählen Sie `obs_replay_manager_browser.py`
5. Konfigurieren Sie den Replay-Ordner in den Skripteinstellungen

---

## REST API

The HTTP server exposes various APIs for replay management:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/replays` | GET | List all replays |
| `/api/load` | POST | Load a replay in OBS |
| `/api/delete` | POST | Delete a replay |
| `/api/toggle-favorite` | POST | Add/remove from favorites |
| `/api/queue/add` | POST | Add to queue |
| `/api/queue/play-next` | POST | Play next in queue |
| `/api/category/create` | POST | Create new category |
| `/api/category/assign` | POST | Assign category to video |
| `/api/create-highlights` | POST | Generate highlights video |
| `/api/settings` | GET/POST | Get/set settings |

---

## Troubleshooting

### FFmpeg not found
- Ensure FFmpeg is installed and in your system PATH
- Restart OBS Studio after adding FFmpeg to PATH
- Run `ffmpeg -version` in terminal to verify installation

### Browser dock not showing
1. Restart OBS Studio
2. Check if another application is using port 8765
3. Manually add the dock via `Docks > Custom Browser Docks`

### Videos not loading
- Check that the media source name matches exactly
- Verify the target scene contains the media source
- Check the OBS script logs for errors

---

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

*The web interface is fully integrated into the Python file and does not require external HTML files.*
