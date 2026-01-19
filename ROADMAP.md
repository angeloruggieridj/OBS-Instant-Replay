# OBS Instant Replay - Roadmap

## Stato Attuale (v1.0-beta3)

### Funzionalità Implementate
- Interfaccia web integrata in OBS (Browser Dock)
- Griglia video con anteprime
- Sistema preferiti
- Playlist/coda di riproduzione
- Categorie personalizzate con colori
- Video nascosti
- Ricerca e filtri
- Controllo velocità (0.1x - 2.0x)
- Zoom dimensione card
- Temi chiaro/scuro
- Modalità READY/LIVE
- Creazione video highlights
- Sistema aggiornamenti automatici (Beta/Stable)
- Loading screen inizializzazione

---

## Funzionalità Proposte

### Priorità Alta

| Funzionalità | Descrizione | Complessità |
|--------------|-------------|-------------|
| **Shortcut tastiera** | Tasti rapidi per azioni comuni (play, next, favorite) | Media |
| **Drag & Drop playlist** | Riordinare elementi playlist trascinandoli | Media |
| **Rinomina video** | Possibilità di rinominare i replay dalla UI | Bassa |
| **Filtri avanzati** | Filtra per durata, data, dimensione file | Media |
| **Anteprima hover** | Preview video al passaggio del mouse | Alta |

### Priorità Media

| Funzionalità | Descrizione | Complessità |
|--------------|-------------|-------------|
| **Note/commenti** | Aggiungere note testuali ai video | Bassa |
| **Esporta/Importa config** | Backup e ripristino configurazioni | Bassa |
| **Statistiche utilizzo** | Dashboard con statistiche replay usati | Media |
| **Trim video rapido** | Tagliare inizio/fine video senza software esterni | Alta |
| **Multi-selezione** | Selezionare più video per azioni batch | Media |

### Priorità Bassa

| Funzionalità | Descrizione | Complessità |
|--------------|-------------|-------------|
| **Temi personalizzati** | Editor colori per creare temi custom | Media |
| **Multi-lingua** | Supporto localizzazione interfaccia | Media |
| **Notifiche desktop** | Alert quando nuovo replay disponibile | Bassa |
| **Picture-in-Picture** | Anteprima video in finestra flottante | Alta |
| **API documentata** | Documentazione REST API per integrazioni | Bassa |

### Idee Future

| Funzionalità | Descrizione | Complessità |
|--------------|-------------|-------------|
| **Integrazione Stream Deck** | Plugin nativo per Elgato Stream Deck | Alta |
| **Marcatori Twitch/YouTube** | Sincronizzazione con markers streaming | Alta |
| **Tagging AI** | Categorizzazione automatica con ML | Molto Alta |
| **Sincronizzazione cloud** | Backup configurazioni su cloud | Alta |
| **Modalità multi-source** | Gestire più media source contemporaneamente | Alta |

---

## Roadmap Rilasci

### v1.0-beta4 (Prossimo)
**Focus: Usabilità e gestione video**

- [ ] Shortcut da tastiera per azioni comuni
- [ ] Rinomina video dalla UI
- [ ] Filtro per data (oggi, settimana, mese)
- [ ] Conferma eliminazione video migliorata
- [ ] Fix bug segnalati

### v1.0-beta5
**Focus: Playlist avanzata**

- [ ] Drag & drop per riordinare playlist
- [ ] Multi-selezione video
- [ ] Azioni batch (elimina multipli, aggiungi a categoria)
- [ ] Esportazione playlist come file

### v1.0-RC1 (Release Candidate)
**Focus: Stabilità e polish**

- [ ] Esporta/Importa configurazioni
- [ ] Filtri avanzati (durata, dimensione)
- [ ] Ottimizzazioni performance
- [ ] Test approfonditi cross-platform
- [ ] Documentazione completa

### v1.0 (Stable Release)
**Focus: Prima release stabile**

- [ ] Tutti i bug critici risolti
- [ ] Documentazione utente completa
- [ ] Video tutorial
- [ ] Supporto community

---

## Post v1.0

### v1.1
**Focus: Funzionalità avanzate**

- [ ] Anteprima video al hover
- [ ] Note e commenti sui video
- [ ] Statistiche utilizzo
- [ ] Temi personalizzati

### v1.2
**Focus: Editing**

- [ ] Trim video rapido (taglia inizio/fine)
- [ ] Merge video selezionati
- [ ] Esportazione con preset qualità

### v2.0
**Focus: Integrazioni e AI**

- [ ] Plugin Stream Deck nativo
- [ ] Integrazione Twitch markers
- [ ] Multi-lingua interfaccia
- [ ] Categorizzazione automatica (AI)

---

## Come Contribuire

Se vuoi proporre nuove funzionalità o segnalare bug:

1. Apri una [Issue su GitHub](https://github.com/angeloruggieridj/OBS-Instant-Replay/issues)
2. Descrivi la funzionalità o il problema
3. Se possibile, includi screenshot o video

### Priorità delle richieste

Le richieste vengono valutate in base a:
- Numero di utenti che la richiedono
- Impatto sull'esperienza utente
- Complessità di implementazione
- Allineamento con la visione del progetto

---

## Note Tecniche

### Limitazioni attuali
- Richiede FFmpeg installato nel sistema
- Funziona solo con OBS Studio 28.0+
- Browser Dock richiede connessione localhost

### Architettura
- **obs_replay_manager_browser.py**: Script OBS principale
- **replay_http_server.py**: Server HTTP con UI integrata
- **Comunicazione**: REST API su porta 8765

### Stack tecnologico
- Python 3.6+
- HTTP Server nativo Python
- HTML/CSS/JavaScript vanilla (no framework)
- FFmpeg per elaborazione video

---

*Ultimo aggiornamento: Gennaio 2026*
