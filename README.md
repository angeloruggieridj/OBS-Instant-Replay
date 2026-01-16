# OBS Instant Replay

Sistema avanzato di gestione replay per OBS Studio con interfaccia web integrata.

## Caratteristiche

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

## File Principali

- `obs_replay_manager_browser.py`: Script principale OBS Studio
- `replay_http_server_v4.py`: Server HTTP con API REST e interfaccia web

## Installazione

1. Copia i file nella directory degli script di OBS Studio
2. In OBS Studio, vai su `Strumenti > Script`
3. Clicca su `+` e seleziona `obs_replay_manager_browser.py`
4. Configura la cartella dei replay nelle impostazioni dello script

## Requisiti

- OBS Studio (con supporto Python)
- Python 3.x
- FFmpeg e FFprobe (nel PATH di sistema)

## Utilizzo

1. Avvia OBS Studio
2. Lo script creerà automaticamente un browser dock "Replay Manager"
3. Utilizza l'interfaccia web per gestire i tuoi replay
4. Carica i video direttamente nella sorgente media configurata

## API REST

Il server HTTP espone varie API per la gestione dei replay:

- `GET /api/replays`: Lista tutti i replay
- `POST /api/load`: Carica un replay in OBS
- `POST /api/delete`: Elimina un replay
- `POST /api/toggle-favorite`: Aggiungi/rimuovi dai preferiti
- `POST /api/queue/add`: Aggiungi alla coda
- `POST /api/category/create`: Crea nuova categoria
- `POST /api/create-highlights`: Genera video highlights

## Licenza

Progetto personale - Tutti i diritti riservati

## Note

L'interfaccia web è completamente integrata nel file Python e non richiede file HTML esterni.
