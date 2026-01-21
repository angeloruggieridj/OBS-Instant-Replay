"""
OBS Instant Replay - Server HTTP
Versione: 1.0-beta4
Repository: https://github.com/angeloruggieridj/OBS-Instant-Replay

Funzionalità:
- Sistema preferiti/favorites
- Playlist/Queue management
- Categorie personalizzate
- Video nascosti
- Ricerca e filtri avanzati
- Controlli velocità
- Temi personalizzabili
- Zoom card
- Persistenza dati
- Verifica aggiornamenti da GitHub
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import sys
import threading
import urllib.parse
import urllib.request
from datetime import datetime
import queue
import subprocess
import tempfile

# Versione corrente
VERSION = "1.0-beta4"
GITHUB_REPO = "angeloruggieridj/OBS-Instant-Replay"
GITHUB_RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_ALL_RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
GITHUB_TAGS_URL = f"https://api.github.com/repos/{GITHUB_REPO}/tags"

# Variabili globali
replay_folder = ""
media_source_name = ""
target_scene_name = ""
auto_switch_scene = False
replay_files = []
filter_mask = ""
refresh_interval_seconds = 3
SERVER_PORT = 8765
action_queue = queue.Queue()

# Nuove variabili per funzionalità estese
favorites = set()  # Percorsi dei video preferiti
playlist_queue = []  # Coda di riproduzione
categories = {}  # {category_name: color}
video_categories = {}  # {file_path: category_name}
hidden_videos = set()  # Percorsi dei video nascosti
current_speed = 1.0  # Velocità di riproduzione corrente
current_theme = "default"  # Tema corrente
card_zoom = 200  # Dimensione card (120-320px)
current_playing_video = None  # Path del video attualmente in riproduzione
current_ready_video = None  # Path del video caricato ma non avviato (READY)
update_channel = "stable"  # Canale aggiornamenti: "stable" o "beta"
last_scan_time = None  # Timestamp dell'ultimo scan
video_durations_cache = {}  # Cache delle durate video {path: seconds}
highlights_files = []  # Lista dei file highlights creati

# File di persistenza
DATA_FILE = None

def init_data_file():
    """Inizializza il file di persistenza dati"""
    global DATA_FILE
    script_dir = os.path.dirname(os.path.abspath(__file__))
    DATA_FILE = os.path.join(script_dir, "replay_manager_data.json")
    load_persistent_data()

def load_persistent_data():
    """Carica dati persistenti da JSON"""
    global favorites, playlist_queue, categories, video_categories, hidden_videos
    global current_theme, card_zoom, current_speed, highlights_files
    global replay_folder, media_source_name, target_scene_name, auto_switch_scene
    global filter_mask, refresh_interval_seconds, update_channel

    if not DATA_FILE or not os.path.exists(DATA_FILE):
        return

    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        favorites = set(data.get('favorites', []))
        playlist_queue = data.get('playlist_queue', [])
        categories = data.get('categories', {})
        video_categories = data.get('video_categories', {})
        hidden_videos = set(data.get('hidden_videos', []))
        current_theme = data.get('current_theme', 'default')
        card_zoom = data.get('card_zoom', 200)
        current_speed = data.get('current_speed', 1.0)
        highlights_files = data.get('highlights_files', [])
        update_channel = data.get('update_channel', 'stable')

        # Impostazioni OBS
        replay_folder = data.get('replay_folder', '')
        media_source_name = data.get('media_source_name', 'Replay Source')
        target_scene_name = data.get('target_scene_name', '')
        auto_switch_scene = data.get('auto_switch_scene', False)
        filter_mask = data.get('filter_mask', '')
        refresh_interval_seconds = data.get('refresh_interval', 3)

        print(f"[DATA] Caricati: {len(favorites)} preferiti, {len(playlist_queue)} in coda, {len(categories)} categorie")
    except Exception as e:
        print(f"[DATA] Errore caricamento: {e}")

def save_persistent_data():
    """Salva dati persistenti su JSON"""
    if not DATA_FILE:
        return

    try:
        data = {
            'favorites': list(favorites),
            'playlist_queue': playlist_queue,
            'categories': categories,
            'video_categories': video_categories,
            'hidden_videos': list(hidden_videos),
            'current_theme': current_theme,
            'card_zoom': card_zoom,
            'current_speed': current_speed,
            'highlights_files': highlights_files,
            'update_channel': update_channel,
            # Impostazioni OBS
            'replay_folder': replay_folder,
            'media_source_name': media_source_name,
            'target_scene_name': target_scene_name,
            'auto_switch_scene': auto_switch_scene,
            'filter_mask': filter_mask,
            'refresh_interval': refresh_interval_seconds
        }

        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    except Exception as e:
        print(f"[DATA] Errore salvataggio: {e}")


def check_for_updates():
    """Verifica se sono disponibili aggiornamenti da GitHub

    Se update_channel == 'beta': considera pre-release + release stabili
    Se update_channel == 'stable': solo release stabili (non pre-release)
    """
    try:
        # Scarica tutte le release (include pre-release)
        req = urllib.request.Request(
            GITHUB_ALL_RELEASES_URL,
            headers={'User-Agent': 'OBS-Instant-Replay'}
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                all_releases = json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                all_releases = []
            else:
                raise

        # Filtra in base al canale
        target_release = None

        if all_releases:
            for release in all_releases:
                is_prerelease = release.get('prerelease', False)
                is_draft = release.get('draft', False)

                # Salta le bozze
                if is_draft:
                    continue

                # Canale Beta: accetta tutto (pre-release e stabili)
                # Canale Stable: solo release non pre-release
                if update_channel == 'beta' or not is_prerelease:
                    target_release = release
                    break  # Prendi la prima (più recente) che soddisfa i criteri

        if target_release:
            tag_name = target_release.get('tag_name', '')
            latest_version = tag_name.lstrip('v')
            release_notes = target_release.get('body', '')
            release_url = target_release.get('html_url', '')
            published_at = target_release.get('published_at', '')
            is_prerelease = target_release.get('prerelease', False)

            # Trova gli asset scaricabili dalla release
            assets = []
            for asset in target_release.get('assets', []):
                if asset.get('name', '').endswith('.py'):
                    assets.append({
                        'name': asset.get('name'),
                        'download_url': asset.get('browser_download_url'),
                        'size': asset.get('size', 0)
                    })

            # Se non ci sono assets .py allegati, genera URL raw dal repository
            if not assets:
                raw_base_url = f'https://raw.githubusercontent.com/{GITHUB_REPO}/{tag_name}'
                assets = [
                    {
                        'name': 'replay_http_server.py',
                        'download_url': f'{raw_base_url}/replay_http_server.py',
                        'size': 0
                    },
                    {
                        'name': 'obs_replay_manager_browser.py',
                        'download_url': f'{raw_base_url}/obs_replay_manager_browser.py',
                        'size': 0
                    }
                ]

            is_update_available = latest_version != VERSION

            return {
                'success': True,
                'current_version': VERSION,
                'latest_version': latest_version,
                'update_available': is_update_available,
                'is_prerelease': is_prerelease,
                'release_notes': release_notes,
                'release_url': release_url,
                'published_at': published_at,
                'assets': assets,
                'channel': update_channel
            }

        # Nessuna release trovata, prova con i tags
        req = urllib.request.Request(
            GITHUB_TAGS_URL,
            headers={'User-Agent': 'OBS-Instant-Replay'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            tags = json.loads(response.read().decode('utf-8'))

        if tags and len(tags) > 0:
            latest_tag_name = tags[0].get('name', '')
            latest_tag = latest_tag_name.lstrip('v')
            is_update_available = latest_tag != VERSION

            # Genera URL per scaricare direttamente dal repository
            raw_base_url = f'https://raw.githubusercontent.com/{GITHUB_REPO}/{latest_tag_name}'
            assets = [
                {
                    'name': 'replay_http_server.py',
                    'download_url': f'{raw_base_url}/replay_http_server.py',
                    'size': 0
                },
                {
                    'name': 'obs_replay_manager_browser.py',
                    'download_url': f'{raw_base_url}/obs_replay_manager_browser.py',
                    'size': 0
                }
            ]

            return {
                'success': True,
                'current_version': VERSION,
                'latest_version': latest_tag,
                'update_available': is_update_available,
                'is_prerelease': False,
                'release_notes': 'Nessuna nota di rilascio disponibile (solo tag)',
                'release_url': f'https://github.com/{GITHUB_REPO}/releases/tag/{latest_tag_name}',
                'published_at': '',
                'assets': assets,
                'channel': update_channel
            }

        return {
            'success': True,
            'current_version': VERSION,
            'latest_version': VERSION,
            'update_available': False,
            'is_prerelease': False,
            'release_notes': '',
            'release_url': '',
            'published_at': '',
            'assets': [],
            'channel': update_channel
        }

    except urllib.error.URLError as e:
        return {
            'success': False,
            'error': f'Errore di connessione: {str(e.reason)}',
            'current_version': VERSION
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'current_version': VERSION
        }


def browse_folder_dialog():
    """Apre un dialog nativo per selezionare una cartella"""
    try:
        import tkinter as tk
        from tkinter import filedialog

        # Crea una finestra root nascosta
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)  # Porta in primo piano

        # Apre il dialog per selezionare la cartella
        folder_path = filedialog.askdirectory(
            title="Seleziona la cartella dei Replay",
            initialdir=replay_folder if replay_folder else None
        )

        root.destroy()

        return folder_path if folder_path else None

    except Exception as e:
        print(f"[BROWSE] Errore apertura dialog: {e}")
        return None


def download_and_install_update(asset_url, asset_name):
    """Scarica e installa l'aggiornamento"""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # Scarica il file
        req = urllib.request.Request(
            asset_url,
            headers={'User-Agent': 'OBS-Instant-Replay'}
        )

        download_path = os.path.join(script_dir, asset_name + '.new')

        with urllib.request.urlopen(req, timeout=60) as response:
            with open(download_path, 'wb') as f:
                f.write(response.read())

        # Backup del file corrente
        if asset_name == 'replay_http_server.py':
            current_file = os.path.join(script_dir, 'replay_http_server.py')
            backup_file = os.path.join(script_dir, 'replay_http_server.py.backup')
            if os.path.exists(current_file):
                if os.path.exists(backup_file):
                    os.remove(backup_file)
                os.rename(current_file, backup_file)
            os.rename(download_path, current_file)

        elif asset_name == 'obs_replay_manager_browser.py':
            current_file = os.path.join(script_dir, 'obs_replay_manager_browser.py')
            backup_file = os.path.join(script_dir, 'obs_replay_manager_browser.py.backup')
            if os.path.exists(current_file):
                if os.path.exists(backup_file):
                    os.remove(backup_file)
                os.rename(current_file, backup_file)
            os.rename(download_path, current_file)

        return {'success': True, 'message': f'{asset_name} aggiornato. Riavvia OBS per applicare.'}

    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_ffmpeg_subprocess_args():
    """Ritorna argomenti subprocess per nascondere FFmpeg"""
    base_args = {
        'stdout': subprocess.DEVNULL,
        'stderr': subprocess.DEVNULL
    }

    if sys.platform == 'win32':
        # CREATE_NO_WINDOW = 0x08000000
        CREATE_NO_WINDOW = 0x08000000
        try:
            base_args['creationflags'] = CREATE_NO_WINDOW
        except:
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE
                base_args['startupinfo'] = startupinfo
            except:
                pass

    return base_args


def get_video_duration(video_path):
    """Ritorna la durata del video in secondi usando FFprobe"""
    global video_durations_cache

    # Usa cache se disponibile
    if video_path in video_durations_cache:
        return video_durations_cache[video_path]

    try:
        ffprobe_cmd = [
            'ffprobe', '-v', 'error', '-show_entries',
            'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]

        subprocess_args = get_ffmpeg_subprocess_args()
        subprocess_args['stdout'] = subprocess.PIPE
        subprocess_args['stderr'] = subprocess.PIPE
        subprocess_args['timeout'] = 5

        result = subprocess.run(ffprobe_cmd, **subprocess_args)

        if result.returncode == 0 and result.stdout:
            duration = float(result.stdout.decode('utf-8').strip())
            video_durations_cache[video_path] = duration
            return duration
    except:
        pass

    return None


class ReplayFile:
    def __init__(self, path, name, modified, size):
        self.path = path
        self.name = name
        self.modified = modified
        self.size = size
        self.extension = os.path.splitext(name)[1].lower()

    def get_mime_type(self):
        mime_types = {
            '.mp4': 'video/mp4',
            '.webm': 'video/webm',
            '.mkv': 'video/x-matroska',
            '.avi': 'video/x-msvideo',
            '.mov': 'video/quicktime',
            '.flv': 'video/x-flv'
        }
        return mime_types.get(self.extension, 'video/mp4')

    def to_dict(self, index=None):
        is_favorite = self.path in favorites
        is_hidden = self.path in hidden_videos
        category = video_categories.get(self.path)
        in_queue_index = -1

        # Trova posizione nella playlist
        for i, item in enumerate(playlist_queue):
            if item.get('path') == self.path:
                in_queue_index = i
                break

        # Calcola durata video
        duration = get_video_duration(self.path)
        duration_str = None
        if duration is not None:
            mins = int(duration // 60)
            secs = int(duration % 60)
            duration_str = f"{mins}:{secs:02d}"

        # Verifica lo stato del video
        is_playing = (self.path == current_playing_video)
        is_ready = (self.path == current_ready_video)

        return {
            'path': self.path,
            'name': self.name,
            'modified': self.modified,
            'timestamp': datetime.fromtimestamp(self.modified).strftime('%Y-%m-%d %H:%M:%S'),
            'size': self.size,
            'size_str': self.get_size_str(),
            'index': index,
            'favorite': is_favorite,
            'hidden': is_hidden,
            'category': category,
            'category_color': categories.get(category) if category else None,
            'in_queue': in_queue_index >= 0,
            'queue_index': in_queue_index,
            'extension': self.extension,
            'mime_type': self.get_mime_type(),
            'duration': duration,
            'duration_str': duration_str,
            'is_playing': is_playing,
            'is_ready': is_ready
        }

    def get_size_str(self):
        size_mb = self.size / (1024 * 1024)
        if size_mb < 1024:
            return f"{size_mb:.1f} MB"
        else:
            return f"{size_mb / 1024:.2f} GB"


def scan_replay_folder():
    """Scansiona cartella replay"""
    global replay_files, replay_folder, filter_mask, last_scan_time

    if not replay_folder or not os.path.exists(replay_folder):
        replay_files = []
        return

    # Aggiorna timestamp ultimo scan
    last_scan_time = datetime.now().strftime('%H:%M:%S')

    try:
        old_count = len(replay_files)
        video_extensions = ('.mp4', '.mkv', '.mov', '.avi', '.flv', '.webm')

        # Ottimizzazione: mappa dei file esistenti per riuso oggetti immutati
        existing_files_map = {rf.path: rf for rf in replay_files}
        files = []

        for file in os.listdir(replay_folder):
            if file.lower().endswith(video_extensions):
                if filter_mask and not file.startswith(filter_mask):
                    continue

                full_path = os.path.join(replay_folder, file)
                if os.path.isfile(full_path):
                    mtime = os.path.getmtime(full_path)
                    fsize = os.path.getsize(full_path)

                    # Riusa oggetto esistente se non modificato
                    if full_path in existing_files_map:
                        existing_rf = existing_files_map[full_path]
                        if existing_rf.modified == mtime and existing_rf.size == fsize:
                            files.append(existing_rf)
                            continue

                    # File nuovo o modificato
                    files.append(ReplayFile(
                        path=full_path,
                        name=file,
                        modified=mtime,
                        size=fsize
                    ))

        files.sort(key=lambda x: x.modified, reverse=True)
        replay_files = files

        new_count = len(replay_files)
        if new_count != old_count:
            diff = new_count - old_count
            print(f"[SCAN] Replay: {old_count} → {new_count} ({diff:+d})")

        # Pulisci favorites e hidden_videos da file non più esistenti
        cleanup_persistent_data()

    except Exception as e:
        print(f"[SCAN] Errore: {e}")
        replay_files = []


def cleanup_persistent_data():
    """Rimuove riferimenti a file non più esistenti"""
    global favorites, hidden_videos, video_categories

    existing_paths = {rf.path for rf in replay_files}

    # Pulisci hidden_videos
    hidden_videos = hidden_videos.intersection(existing_paths)

    # Pulisci video_categories
    video_categories = {k: v for k, v in video_categories.items() if k in existing_paths}

    # Pulisci favorites (sono path, quindi verifica esistenza)
    favorites = favorites.intersection(existing_paths)


def create_highlights_video(use_queue=True):
    """Crea video highlights dalla coda"""
    global replay_files, replay_folder, playlist_queue, video_categories, highlights_files

    # Usa sempre la coda
    if not playlist_queue:
        return None, "Nessun video in coda"

    video_list = []
    for item in playlist_queue:
        path = item['path']
        # Trova il ReplayFile corrispondente
        for rf in replay_files:
            if rf.path == path:
                video_list.append(rf)
                break

    if not video_list:
        return None, "Nessun video da processare"

    try:

        concat_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
        for replay in video_list:
            escaped_path = replay.path.replace('\\', '/').replace("'", "'\\''")
            concat_file.write(f"file '{escaped_path}'\n")
        concat_file.close()

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(replay_folder, f"Highlights_{timestamp}.mp4")

        ffmpeg_cmd = [
            'ffmpeg', '-f', 'concat', '-safe', '0',
            '-i', concat_file.name, '-c', 'copy', '-y', output_path
        ]

        print(f"[HIGHLIGHTS] Creazione: {len(video_list)} replay")

        subprocess_args = get_ffmpeg_subprocess_args()
        subprocess_args['timeout'] = 300

        try:
            result = subprocess.run(ffmpeg_cmd, **subprocess_args)
            returncode = result.returncode
        except subprocess.TimeoutExpired:
            print("[HIGHLIGHTS] Timeout")
            return None, "Timeout"
        except Exception as e:
            print(f"[HIGHLIGHTS] Errore: {e}")
            return None, str(e)
        finally:
            try:
                os.unlink(concat_file.name)
            except:
                pass

        if returncode == 0 and os.path.exists(output_path):
            print(f"[HIGHLIGHTS] ✓ Creato: {output_path}")
            highlights_files.append(output_path)
            save_persistent_data()
            scan_replay_folder()
            return output_path, None
        else:
            return None, f"FFmpeg error: {returncode}"

    except Exception as e:
        print(f"[HIGHLIGHTS] Errore: {e}")
        return None, str(e)


class ReplayAPIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def handle_one_request(self):
        """Override per gestire meglio gli errori di connessione"""
        try:
            super().handle_one_request()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            print(f"[HTTP] Errore gestione richiesta: {e}")


    def handle_one_request(self):
        """Override per gestire meglio gli errori di connessione"""
        try:
            super().handle_one_request()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            # Ignora errori di connessione comuni
            pass
        except Exception as e:
            print(f"[HTTP] Errore gestione richiesta: {e}")

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        if path == '/' or path == '/index.html':
            self.serve_html()

        elif path == '/api/replays':
            self.send_json({
                'replays': [r.to_dict(index=i)
                           for i, r in enumerate(replay_files) if r.path not in hidden_videos],
                'count': len([r for r in replay_files if r.path not in hidden_videos]),
                'total_count': len(replay_files),
                'folder': replay_folder,
                'filter': filter_mask,
                'favorites_count': len(favorites),
                'hidden_count': len(hidden_videos),
                'queue_count': len(playlist_queue),
                'last_scan_time': last_scan_time
            })

        elif path == '/api/config':
            self.send_json({
                'replay_folder': replay_folder,
                'media_source_name': media_source_name,
                'target_scene_name': target_scene_name,
                'auto_switch_scene': auto_switch_scene,
                'filter_mask': filter_mask,
                'refresh_interval': refresh_interval_seconds,
                'current_speed': current_speed,
                'current_theme': current_theme,
                'card_zoom': card_zoom,
                'update_channel': update_channel
            })

        elif path == '/api/scan':
            scan_replay_folder()
            self.send_json({'success': True, 'count': len(replay_files)})

        elif path == '/api/favorites':
            fav_list = []
            for i, rf in enumerate(replay_files):
                if rf.path in favorites:
                    fav_list.append(rf.to_dict(index=i))
            self.send_json({'favorites': fav_list, 'count': len(fav_list)})

        elif path == '/api/queue':
            self.send_json({'queue': playlist_queue, 'count': len(playlist_queue)})

        elif path == '/api/categories':
            cat_list = [{'name': name, 'color': color, 'count': sum(1 for c in video_categories.values() if c == name)}
                       for name, color in categories.items()]
            self.send_json({'categories': cat_list})

        elif path == '/api/hidden':
            hidden_list = [{'path': p, 'name': os.path.basename(p)} for p in hidden_videos]
            self.send_json({'hidden': hidden_list, 'count': len(hidden_videos)})

        elif path == '/api/highlights':
            highlights = []
            for path in highlights_files:
                if os.path.exists(path):
                    stat = os.stat(path)
                    duration = get_video_duration(path)
                    duration_str = None
                    if duration:
                        mins = int(duration // 60)
                        secs = int(duration % 60)
                        duration_str = f"{mins}:{secs:02d}"

                    highlights.append({
                        'path': path,
                        'name': os.path.basename(path),
                        'size': stat.st_size,
                        'size_str': f"{stat.st_size / (1024 * 1024):.1f} MB",
                        'created': datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                        'duration': duration,
                        'duration_str': duration_str
                    })
            self.send_json({'highlights': highlights, 'count': len(highlights)})

        elif path == '/api/version':
            self.send_json({
                'version': VERSION,
                'repository': GITHUB_REPO
            })

        elif path == '/api/check-updates':
            result = check_for_updates()
            self.send_json(result)

        elif path.startswith('/api/thumbnail/'):
            try:
                index = int(path.split('/')[-1])
                if 0 <= index < len(replay_files):
                    self.serve_thumbnail(replay_files[index].path)
                else:
                    self.send_error(404)
            except:
                self.send_error(404)

        elif path.startswith('/api/video/'):
            try:
                index = int(path.split('/')[-1])
                if 0 <= index < len(replay_files):
                    self.serve_video(replay_files[index])
                else:
                    self.send_error(404)
            except:
                self.send_error(404)

        else:
            self.send_error(404)

    
    def do_POST(self):
        global current_playing_video, current_ready_video, current_speed, current_theme, card_zoom
        global video_categories, favorites, hidden_videos, playlist_queue, categories
        global replay_folder, media_source_name, target_scene_name, auto_switch_scene, filter_mask, update_channel

        try:
            parsed_path = urllib.parse.urlparse(self.path)
            path = parsed_path.path

            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'

            try:
                data = json.loads(post_data.decode('utf-8'))
            except:
                data = {}

            if path == '/api/scan':
                scan_replay_folder()
                self.send_json({'success': True, 'count': len(replay_files)})

            elif path == '/api/load':
                video_path = data.get('path', '')
                # Verifica che il file esista
                if video_path and os.path.exists(video_path):
                    # Video caricato in modalità READY (pronto per avvio manuale)
                    current_ready_video = video_path
                    current_playing_video = None

                    action_queue.put({
                        'action': 'load_replay',
                        'path': video_path,
                        'speed': current_speed
                    })

                    self.send_json({'success': True})
                else:
                    self.send_json({'success': False, 'error': 'File non trovato'})

            elif path == '/api/delete':
                video_path = data.get('path', '')
                if video_path and os.path.exists(video_path):
                    try:
                        os.remove(video_path)
                        scan_replay_folder()
                        save_persistent_data()
                        self.send_json({'success': True})
                    except:
                        self.send_json({'success': False, 'error': 'Errore eliminazione'})
                else:
                    self.send_json({'success': False})

            elif path == '/api/toggle-favorite':
                video_path = data.get('path', '')
                if video_path and os.path.exists(video_path):
                    if video_path in favorites:
                        favorites.remove(video_path)
                        is_fav = False
                    else:
                        favorites.add(video_path)
                        is_fav = True
                    save_persistent_data()
                    self.send_json({'success': True, 'favorite': is_fav})
                else:
                    self.send_json({'success': False})

            elif path == '/api/queue/add':
                video_path = data.get('path', '')
                if video_path and os.path.exists(video_path):
                    if not any(item['path'] == video_path for item in playlist_queue):
                        video_name = os.path.basename(video_path)
                        playlist_queue.append({
                            'path': video_path,
                            'name': video_name
                        })
                        save_persistent_data()
                        self.send_json({'success': True, 'queue_count': len(playlist_queue)})
                    else:
                        self.send_json({'success': False, 'error': 'Already in queue'})
                else:
                    self.send_json({'success': False})

            elif path == '/api/queue/remove':
                queue_index = data.get('queue_index', -1)
                if 0 <= queue_index < len(playlist_queue):
                    playlist_queue.pop(queue_index)
                    save_persistent_data()
                    self.send_json({'success': True})
                else:
                    self.send_json({'success': False})

            elif path == '/api/queue/clear':
                playlist_queue.clear()
                save_persistent_data()
                self.send_json({'success': True})

            elif path == '/api/queue/reorder':
                from_index = data.get('from', -1)
                to_index = data.get('to', -1)
                if 0 <= from_index < len(playlist_queue) and 0 <= to_index < len(playlist_queue):
                    item = playlist_queue.pop(from_index)
                    playlist_queue.insert(to_index, item)
                    save_persistent_data()
                    self.send_json({'success': True})
                else:
                    self.send_json({'success': False})

            elif path == '/api/queue/move-to-top':
                index = data.get('index', -1)
                if 0 < index < len(playlist_queue):
                    item = playlist_queue.pop(index)
                    playlist_queue.insert(0, item)
                    save_persistent_data()
                    self.send_json({'success': True})
                else:
                    self.send_json({'success': False})

            elif path == '/api/queue/move-to-bottom':
                index = data.get('index', -1)
                if 0 <= index < len(playlist_queue) - 1:
                    item = playlist_queue.pop(index)
                    playlist_queue.append(item)
                    save_persistent_data()
                    self.send_json({'success': True})
                else:
                    self.send_json({'success': False})

            elif path == '/api/queue/play-next':
                if len(playlist_queue) > 0:
                    playlist_queue.pop(0)
                    save_persistent_data()

                    if len(playlist_queue) > 0:
                        next_item = playlist_queue[0]
                        next_path = next_item['path']

                        # Video caricato in modalità READY (pronto per avvio manuale)
                        current_ready_video = next_path
                        current_playing_video = None

                        action_queue.put({
                            'action': 'load_replay',
                            'path': next_path,
                            'speed': current_speed
                        })

                        self.send_json({'success': True, 'has_next': len(playlist_queue) > 1})
                    else:
                        current_playing_video = None
                        current_ready_video = None
                        self.send_json({'success': True, 'has_next': False})
                else:
                    self.send_json({'success': False, 'error': 'Queue empty'})

            elif path == '/api/category/create':
                name = data.get('name', '').strip()
                color = data.get('color', '#888')
                if name and name not in categories:
                    categories[name] = color
                    save_persistent_data()
                    self.send_json({'success': True})
                else:
                    self.send_json({'success': False, 'error': 'Invalid or duplicate name'})

            elif path == '/api/category/delete':
                name = data.get('name', '')
                if name in categories:
                    del categories[name]
                    video_categories = {k: v for k, v in video_categories.items() if v != name}
                    save_persistent_data()
                    self.send_json({'success': True})
                else:
                    self.send_json({'success': False})

            elif path == '/api/category/rename':
                old_name = data.get('old_name', '').strip()
                new_name = data.get('new_name', '').strip()
                if old_name in categories and new_name and new_name not in categories:
                    # Salva il colore
                    color = categories[old_name]
                    # Elimina la vecchia categoria
                    del categories[old_name]
                    # Crea la nuova con lo stesso colore
                    categories[new_name] = color
                    # Aggiorna tutti i video assegnati alla vecchia categoria
                    for path_key in list(video_categories.keys()):
                        if video_categories[path_key] == old_name:
                            video_categories[path_key] = new_name
                    save_persistent_data()
                    self.send_json({'success': True})
                else:
                    error = 'Categoria non trovata' if old_name not in categories else 'Nome già esistente o non valido'
                    self.send_json({'success': False, 'error': error})

            elif path == '/api/category/update-color':
                name = data.get('name', '').strip()
                color = data.get('color', '').strip()
                if name in categories and color:
                    categories[name] = color
                    save_persistent_data()
                    self.send_json({'success': True})
                else:
                    self.send_json({'success': False, 'error': 'Categoria non trovata'})

            elif path == '/api/category/assign':
                video_path = data.get('path', '')
                category = data.get('category')
                if video_path and os.path.exists(video_path):
                    if category:
                        video_categories[video_path] = category
                    elif video_path in video_categories:
                        del video_categories[video_path]
                    save_persistent_data()
                    self.send_json({'success': True})
                else:
                    self.send_json({'success': False})

            elif path == '/api/hide':
                video_path = data.get('path', '')
                if video_path and os.path.exists(video_path):
                    hidden_videos.add(video_path)
                    save_persistent_data()
                    self.send_json({'success': True})
                else:
                    self.send_json({'success': False})

            elif path == '/api/unhide':
                path_to_unhide = data.get('path', '')
                if path_to_unhide in hidden_videos:
                    hidden_videos.remove(path_to_unhide)
                    save_persistent_data()
                    self.send_json({'success': True})
                else:
                    self.send_json({'success': False})

            elif path == '/api/unhide-all':
                hidden_videos.clear()
                save_persistent_data()
                self.send_json({'success': True})

            elif path == '/api/speed':
                # Imposta la velocità per i prossimi video (non modifica il video corrente)
                speed = data.get('speed', 1.0)
                current_speed = max(0.1, min(2.0, speed))
                save_persistent_data()
                self.send_json({'success': True, 'speed': current_speed})

            elif path == '/api/theme':
                theme = data.get('theme', 'default')
                current_theme = theme
                save_persistent_data()
                self.send_json({'success': True, 'theme': current_theme})

            elif path == '/api/update-channel':
                global update_channel
                channel = data.get('channel', 'beta')
                if channel in ('stable', 'beta'):
                    update_channel = channel
                    save_persistent_data()
                    self.send_json({'success': True, 'channel': update_channel})
                else:
                    self.send_json({'success': False, 'error': 'Canale non valido'})

            elif path == '/api/zoom':
                zoom = data.get('zoom', 200)
                card_zoom = max(120, min(320, zoom))
                save_persistent_data()
                self.send_json({'success': True, 'zoom': card_zoom})

            elif path == '/api/playing/clear':
                current_playing_video = None
                self.send_json({'success': True})

            elif path == '/api/create-highlights':
                use_queue = data.get('use_queue', True)
                output_path, error = create_highlights_video(use_queue=use_queue)
                if output_path:
                    self.send_json({'success': True, 'path': output_path, 'name': os.path.basename(output_path)})
                else:
                    self.send_json({'success': False, 'error': error})

            elif path == '/api/highlights/delete':
                highlight_path = data.get('path', '')
                if highlight_path in highlights_files:
                    try:
                        if os.path.exists(highlight_path):
                            os.remove(highlight_path)
                        highlights_files.remove(highlight_path)
                        save_persistent_data()
                        self.send_json({'success': True})
                    except Exception as e:
                        self.send_json({'success': False, 'error': str(e)})
                else:
                    self.send_json({'success': False, 'error': 'Highlight non trovato'})

            elif path == '/api/highlights/load':
                highlight_path = data.get('path', '')
                if os.path.exists(highlight_path):
                    # Video caricato in modalità READY
                    current_ready_video = highlight_path
                    current_playing_video = None
                    action_queue.put({
                        'action': 'load_replay',
                        'index': -1,
                        'path': highlight_path,
                        'speed': current_speed
                    })
                    self.send_json({'success': True})
                else:
                    self.send_json({'success': False, 'error': 'File non trovato'})

            elif path == '/api/open-folder':
                action_queue.put({
                    'action': 'open_folder'
                })
                self.send_json({'success': True})

            elif path == '/api/browse-folder':
                # Apre un dialog nativo per selezionare una cartella
                selected = browse_folder_dialog()
                if selected:
                    self.send_json({'success': True, 'path': selected})
                else:
                    self.send_json({'success': False, 'error': 'Nessuna cartella selezionata'})

            elif path == '/api/install-update':
                asset_url = data.get('url', '')
                asset_name = data.get('name', '')
                if asset_url and asset_name:
                    result = download_and_install_update(asset_url, asset_name)
                    self.send_json(result)
                else:
                    self.send_json({'success': False, 'error': 'URL o nome file mancante'})

            elif path == '/api/obs-settings':
                global replay_folder, media_source_name, target_scene_name, auto_switch_scene, filter_mask

                new_folder = data.get('replay_folder', replay_folder)
                if new_folder and os.path.isdir(new_folder):
                    replay_folder = new_folder

                media_source_name = data.get('media_source_name', media_source_name)
                target_scene_name = data.get('target_scene_name', target_scene_name)
                auto_switch_scene = data.get('auto_switch_scene', auto_switch_scene)
                filter_mask = data.get('filter_mask', filter_mask)

                save_persistent_data()
                scan_replay_folder()

                self.send_json({
                    'success': True,
                    'replay_folder': replay_folder,
                    'media_source_name': media_source_name,
                    'target_scene_name': target_scene_name,
                    'auto_switch_scene': auto_switch_scene,
                    'filter_mask': filter_mask
                })

            elif path == '/api/config/export':
                # Esporta tutte le configurazioni
                config_data = {
                    'version': VERSION,
                    'export_date': datetime.now().isoformat(),
                    'settings': {
                        'replay_folder': replay_folder,
                        'media_source_name': media_source_name,
                        'target_scene_name': target_scene_name,
                        'auto_switch_scene': auto_switch_scene,
                        'filter_mask': filter_mask,
                        'current_speed': current_speed,
                        'current_theme': current_theme,
                        'card_zoom': card_zoom,
                        'update_channel': update_channel
                    },
                    'categories': categories,
                    'video_categories': video_categories,
                    'hidden_videos': list(hidden_videos),
                    'favorites': list(favorites)
                }
                self.send_json({'success': True, 'config': config_data})

            elif path == '/api/config/import':
                # Importa configurazioni
                config_data = data.get('config', {})
                if not config_data:
                    self.send_json({'success': False, 'error': 'Configurazione vuota'})
                else:
                    settings = config_data.get('settings', {})

                    # Importa impostazioni base (opzionali)
                    if 'replay_folder' in settings and os.path.isdir(settings['replay_folder']):
                        replay_folder = settings['replay_folder']
                    if 'media_source_name' in settings:
                        media_source_name = settings['media_source_name']
                    if 'target_scene_name' in settings:
                        target_scene_name = settings['target_scene_name']
                    if 'auto_switch_scene' in settings:
                        auto_switch_scene = settings['auto_switch_scene']
                    if 'filter_mask' in settings:
                        filter_mask = settings['filter_mask']
                    if 'current_speed' in settings:
                        current_speed = settings['current_speed']
                    if 'current_theme' in settings:
                        current_theme = settings['current_theme']
                    if 'card_zoom' in settings:
                        card_zoom = settings['card_zoom']
                    if 'update_channel' in settings:
                        update_channel = settings['update_channel']

                    # Importa categorie
                    if 'categories' in config_data:
                        categories = config_data['categories']

                    # Importa assegnazioni categorie video
                    if 'video_categories' in config_data:
                        video_categories = config_data['video_categories']

                    # Importa video nascosti
                    if 'hidden_videos' in config_data:
                        hidden_videos = set(config_data['hidden_videos'])

                    # Importa preferiti (se i video esistono ancora)
                    if 'favorites' in config_data:
                        favorites = set(config_data['favorites'])

                    # Salva tutto
                    save_persistent_data()
                    scan_replay_folder()

                    self.send_json({'success': True, 'message': 'Configurazione importata con successo'})

            else:
                self.send_error(404)

        except Exception as e:
            self.send_error(500)

    def send_json(self, data):
        response = json.dumps(data).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(response))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(response)

    def serve_video(self, replay_file):
        try:
            with open(replay_file.path, 'rb') as f:
                video_data = f.read()

            self.send_response(200)
            self.send_header('Content-Type', replay_file.get_mime_type())
            self.send_header('Content-Length', len(video_data))
            self.send_header('Accept-Ranges', 'bytes')
            self.end_headers()
            self.wfile.write(video_data)
        except:
            self.send_error(500)

    def serve_thumbnail(self, video_path):
        try:
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                thumbnail_path = tmp.name

            ffmpeg_cmd = [
                'ffmpeg', '-i', video_path, '-vframes', '1',
                '-vf', 'scale=320:-1', '-y', thumbnail_path
            ]

            subprocess_args = get_ffmpeg_subprocess_args()
            subprocess_args['timeout'] = 5

            try:
                result = subprocess.run(ffmpeg_cmd, **subprocess_args)
                returncode = result.returncode
            except:
                returncode = 1

            if returncode == 0 and os.path.exists(thumbnail_path):
                with open(thumbnail_path, 'rb') as f:
                    thumbnail_data = f.read()

                self.send_response(200)
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', len(thumbnail_data))
                self.send_header('Cache-Control', 'max-age=3600')
                self.end_headers()
                self.wfile.write(thumbnail_data)

                try:
                    os.unlink(thumbnail_path)
                except:
                    pass
            else:
                self.send_placeholder_image()
        except:
            self.send_placeholder_image()

    def send_placeholder_image(self):
        svg = '<svg width="320" height="180" xmlns="http://www.w3.org/2000/svg"><rect width="320" height="180" fill="#1e1e1e"/><text x="160" y="100" font-size="48" fill="#666" text-anchor="middle">🎬</text></svg>'
        self.send_response(200)
        self.send_header('Content-Type', 'image/svg+xml')
        self.send_header('Content-Length', len(svg))
        self.end_headers()
        self.wfile.write(svg.encode('utf-8'))

    def serve_html(self):
        html = get_html_interface()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))


def get_html_interface():
    return """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OBS Instant Replay</title>
<style>
/* ==================== CSS VARIABLES - THEMES ==================== */
:root {
    /* Default/Dark Theme */
    --bg-primary: #1a1a1a;
    --bg-secondary: #252525;
    --bg-tertiary: #2f2f2f;
    --bg-hover: #353535;
    --bg-active: #404040;
    --text-primary: #e0e0e0;
    --text-secondary: #a0a0a0;
    --text-tertiary: #707070;
    --border-color: #404040;
    --shadow: rgba(0, 0, 0, 0.5);
    --accent-primary: #4a9eff;
    --accent-hover: #5fadff;
    --accent-danger: #ff4444;
    --accent-warning: #ff9944;
    --accent-success: #44ff88;
    --favorite-color: #ffcc00;
}

[data-theme="light"] {
    --bg-primary: #f5f5f5;
    --bg-secondary: #ffffff;
    --bg-tertiary: #eeeeee;
    --bg-hover: #e8e8e8;
    --bg-active: #dddddd;
    --text-primary: #1a1a1a;
    --text-secondary: #555555;
    --text-tertiary: #888888;
    --border-color: #cccccc;
    --shadow: rgba(0, 0, 0, 0.1);
    --accent-primary: #2196f3;
    --accent-hover: #42a5f5;
    --accent-danger: #f44336;
    --accent-warning: #ff9800;
    --accent-success: #4caf50;
}

[data-theme="blue"] {
    --bg-primary: #0a1628;
    --bg-secondary: #132540;
    --bg-tertiary: #1a3558;
    --bg-hover: #224470;
    --bg-active: #2a5388;
    --text-primary: #c5d9f1;
    --text-secondary: #8ba8d0;
    --text-tertiary: #5577a0;
    --border-color: #2a5388;
    --accent-primary: #4a9eff;
    --accent-hover: #6bb0ff;
}

[data-theme="green"] {
    --bg-primary: #0d1f0d;
    --bg-secondary: #1a331a;
    --bg-tertiary: #264726;
    --bg-hover: #335b33;
    --bg-active: #407040;
    --text-primary: #c8f0c8;
    --text-secondary: #90d090;
    --text-tertiary: #5aa05a;
    --border-color: #407040;
    --accent-primary: #44ff88;
    --accent-hover: #66ffa0;
}

[data-theme="classic"] {
    --bg-primary: #2b2b2b;
    --bg-secondary: #3a3a3a;
    --bg-tertiary: #4a4a4a;
    --bg-hover: #555555;
    --bg-active: #606060;
    --text-primary: #f0f0f0;
    --text-secondary: #b0b0b0;
    --text-tertiary: #808080;
    --border-color: #555555;
    --accent-primary: #66aaff;
    --accent-hover: #7fbfff;
}

/* ==================== GLOBAL STYLES ==================== */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    overflow-x: hidden;
    transition: background-color 0.3s ease;
}

/* ==================== SCROLLBAR ==================== */
::-webkit-scrollbar {
    width: 12px;
    height: 12px;
}

::-webkit-scrollbar-track {
    background: var(--bg-secondary);
}

::-webkit-scrollbar-thumb {
    background: var(--bg-tertiary);
    border-radius: 6px;
    border: 2px solid var(--bg-secondary);
}

::-webkit-scrollbar-thumb:hover {
    background: var(--bg-hover);
}

/* ==================== HEADER ==================== */
.header {
    position: sticky;
    top: 0;
    z-index: 1000;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border-color);
    box-shadow: 0 2px 8px var(--shadow);
}

.header-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 20px;
    gap: 15px;
}

.header-logo {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 24px;
    font-weight: 700;
    color: var(--accent-primary);
}

.header-logo-icon {
    font-size: 32px;
}

.header-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    align-items: center;
}

.header-btn {
    padding: 8px 14px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    color: var(--text-primary);
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s ease;
    white-space: nowrap;
}

.header-btn:hover {
    background: var(--accent-primary);
    border-color: var(--accent-primary);
    color: #fff;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(52, 152, 219, 0.3);
}

.header-btn:active {
    transform: translateY(0);
    box-shadow: none;
}

.header-btn.primary {
    background: var(--accent-primary);
    border-color: var(--accent-primary);
    color: #fff;
}

.header-btn.primary:hover {
    background: var(--accent-primary-dark, #2980b9);
    border-color: var(--accent-primary-dark, #2980b9);
}

.header-btn .btn-icon {
    font-size: 15px;
    line-height: 1;
}

.header-btn .btn-text {
    font-size: 13px;
}

/* Su schermi piccoli nasconde il testo e mostra solo icone */
@media (max-width: 900px) {
    .header-btn .btn-text {
        display: none;
    }
    .header-btn {
        padding: 10px 12px;
    }
    .header-btn .btn-icon {
        font-size: 18px;
    }
}

.header-stats {
    display: flex;
    gap: 15px;
    align-items: center;
    color: var(--text-secondary);
    font-size: 14px;
}

.stat-item {
    display: flex;
    align-items: center;
    gap: 5px;
}

.stat-value {
    font-weight: 600;
    color: var(--accent-primary);
}

/* ==================== SEARCH BAR ==================== */
.search-bar {
    display: none;
    padding: 12px 20px;
    background: var(--bg-tertiary);
    border-top: 1px solid var(--border-color);
    animation: slideDown 0.3s ease;
}

.search-bar.active {
    display: block;
}

.search-input-wrapper {
    display: flex;
    gap: 10px;
}

.search-input {
    flex: 1;
    padding: 10px 15px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-primary);
    font-size: 14px;
}

.search-input::placeholder {
    color: var(--text-tertiary);
}

.search-clear-btn {
    padding: 10px 20px;
    background: var(--accent-danger);
    border: none;
    border-radius: 6px;
    color: white;
    cursor: pointer;
    font-size: 14px;
    transition: opacity 0.2s ease;
}

.search-clear-btn:hover {
    opacity: 0.8;
}

/* ==================== FILTERS BAR ==================== */
.filters-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 20px;
    background: var(--bg-secondary);
    border-top: 1px solid var(--border-color);
    flex-wrap: wrap;
}

.filter-btn {
    padding: 8px 14px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: 20px;
    color: var(--text-primary);
    cursor: pointer;
    font-size: 13px;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 5px;
}

.filter-btn:hover {
    background: var(--bg-hover);
}

.filter-btn.active {
    background: var(--accent-primary);
    color: white;
    border-color: var(--accent-primary);
}

/* Filter Dropdown */
.filter-dropdown-container {
    position: relative;
}

.filter-dropdown-trigger {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 14px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: 20px;
    cursor: pointer;
    transition: all 0.15s;
    font-size: 13px;
}

.filter-dropdown-trigger:hover {
    background: var(--bg-hover);
    border-color: var(--border-hover);
}

.filter-dropdown-trigger .filter-icon {
    font-size: 14px;
}

.filter-dropdown-trigger .filter-text {
    color: var(--text-primary);
    font-weight: 500;
}

.filter-dropdown-trigger .dropdown-arrow {
    font-size: 10px;
    color: var(--text-secondary);
    transition: transform 0.2s;
}

.filter-dropdown-container.open .dropdown-arrow {
    transform: rotate(180deg);
}

.filter-dropdown-menu {
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    min-width: 220px;
    background: #2a2a2a;
    border: 1px solid #444;
    border-radius: 12px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.4);
    z-index: 100;
    overflow: hidden;
    display: none;
}

.filter-dropdown-container.open .filter-dropdown-menu {
    display: block;
    animation: dropdownFadeIn 0.15s ease;
}

@keyframes dropdownFadeIn {
    from { opacity: 0; transform: translateY(-8px); }
    to { opacity: 1; transform: translateY(0); }
}

.filter-dropdown-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    cursor: pointer;
    transition: all 0.1s;
}

.filter-dropdown-item:hover {
    background: #3a3a3a;
}

.filter-dropdown-item.selected {
    background: linear-gradient(90deg, #264f78 0%, #1e3a5f 100%);
}

.filter-dropdown-item .item-checkbox {
    width: 18px;
    height: 18px;
    border: 2px solid #555;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s;
    flex-shrink: 0;
}

.filter-dropdown-item.selected .item-checkbox {
    background: #007acc;
    border-color: #007acc;
}

.filter-dropdown-item.selected .item-checkbox::after {
    content: '✓';
    color: #fff;
    font-size: 11px;
    font-weight: bold;
}

.filter-dropdown-item .item-color {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
}

.filter-dropdown-item .item-name {
    flex: 1;
    color: #ccc;
    font-size: 0.85rem;
}

.filter-dropdown-item.selected .item-name {
    color: #fff;
}

.filter-dropdown-item .item-count {
    color: #666;
    font-size: 0.75rem;
    padding: 2px 8px;
    background: rgba(255,255,255,0.08);
    border-radius: 10px;
}

.filter-dropdown-item.selected .item-count {
    background: rgba(0,0,0,0.2);
    color: #aaa;
}

/* ==================== VIDEO GRID ==================== */
.video-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(var(--card-width, 200px), 1fr));
    gap: 20px;
    padding: 20px;
    padding-bottom: 100px; /* Spazio per bottom-bar fisso */
    animation: fadeIn 0.5s ease;
}

/* ==================== VIDEO CARD ==================== */
.video-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    overflow: hidden;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    display: flex;
    flex-direction: column;
}

.video-card:hover {
    box-shadow: 0 8px 16px rgba(0, 0, 0, 0.4);
    border-color: var(--accent-primary);
}

.video-card:hover .video-thumbnail video {
    opacity: 1;
}

.video-card:hover .video-thumbnail img {
    opacity: 0;
}

.video-thumbnail {
    position: relative;
    width: 100%;
    aspect-ratio: 16/9;
    background: var(--bg-tertiary);
    overflow: hidden;
    border-radius: 12px 12px 0 0;
}

.video-thumbnail img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    transition: opacity 0.3s ease;
}

.video-thumbnail video {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    opacity: 0;
    transition: opacity 0.3s ease;
    pointer-events: none;
}

.video-badges {
    position: absolute;
    top: 8px;
    left: 8px;
    display: flex;
    flex-direction: column;
    gap: 5px;
}

.video-badge {
    padding: 4px 8px;
    background: rgba(0, 0, 0, 0.8);
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
    backdrop-filter: blur(10px);
}

.badge-duration {
    position: absolute;
    bottom: 8px;
    right: 8px;
    background: rgba(0, 0, 0, 0.75);
    color: white;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    backdrop-filter: blur(5px);
}

.badge-favorite {
    color: var(--favorite-color);
}

.badge-category {
    color: white;
}

.badge-queue {
    background: var(--accent-primary);
    color: white;
}

.badge-ready {
    position: absolute;
    top: 8px;
    right: 8px;
    background: #ff9800;
    color: white;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 700;
    border: 2px solid white;
    z-index: 10;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
}

/* Context Menu - Modern Style */
.context-menu {
    position: fixed;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 6px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4), 0 2px 8px rgba(0,0,0,0.2);
    z-index: 10000;
    min-width: 220px;
    max-width: 280px;
    backdrop-filter: blur(12px);
    animation: contextMenuIn 0.15s ease-out;
    overflow: hidden;
    display: none;
}

.context-menu.visible {
    display: block;
}

@keyframes contextMenuIn {
    from { opacity: 0; transform: scale(0.95) translateY(-4px); }
    to { opacity: 1; transform: scale(1) translateY(0); }
}

.context-menu-header {
    padding: 8px 12px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-secondary);
    font-weight: 600;
    border-bottom: 1px solid var(--border-color);
    margin-bottom: 4px;
}

.context-menu-item {
    padding: 10px 14px;
    cursor: pointer;
    transition: all 0.15s ease;
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 13px;
    color: var(--text-primary);
    border-radius: 8px;
    margin: 2px 0;
}

.context-menu-item:hover {
    background: var(--accent-primary);
    color: #fff;
    transform: translateX(2px);
}

.context-menu-item:hover .menu-icon {
    transform: scale(1.1);
}

.context-menu-item .menu-icon {
    font-size: 16px;
    width: 20px;
    text-align: center;
    transition: transform 0.15s ease;
}

.context-menu-item.active {
    background: rgba(var(--accent-primary-rgb, 52, 152, 219), 0.15);
    color: var(--accent-primary);
}

.context-menu-item.danger {
    color: var(--accent-danger);
}

.context-menu-item.danger:hover {
    background: var(--accent-danger);
    color: #fff;
}

.context-menu-separator {
    height: 1px;
    background: var(--border-color);
    margin: 6px 4px;
}

.context-menu-category {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 14px;
    cursor: pointer;
    border-radius: 8px;
    transition: all 0.15s ease;
    font-size: 13px;
    color: var(--text-primary);
}

.context-menu-category:hover {
    background: var(--bg-hover);
}

.context-menu-category.selected {
    background: rgba(var(--accent-primary-rgb, 52, 152, 219), 0.1);
}

.context-menu-category .category-dot {
    width: 12px;
    height: 12px;
    border-radius: 4px;
    flex-shrink: 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}

.context-menu-category .category-check {
    margin-left: auto;
    color: var(--accent-primary);
    font-weight: bold;
}

.color-picker-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 6px;
    padding: 8px 12px;
}

.color-picker-grid .color-preset {
    width: 28px;
    height: 28px;
}

.video-info {
    padding: 12px;
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.video-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.video-meta {
    font-size: 11px;
    color: var(--text-secondary);
    display: flex;
    flex-direction: column;
    gap: 3px;
}

.video-actions {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
    padding: 8px 12px;
    border-top: 1px solid var(--border-color);
}

.video-action-btn {
    padding: 6px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-primary);
    cursor: pointer;
    font-size: 16px;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
}

.video-action-btn:hover {
    background: var(--bg-hover);
}

.video-action-btn.active {
    background: var(--accent-primary);
    color: white;
}

.video-action-btn.danger:hover {
    background: var(--accent-danger);
    color: white;
}

.speed-btn {
    padding: 4px 8px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-secondary);
    cursor: pointer;
    font-size: 11px;
    transition: all 0.2s ease;
}

.speed-btn:hover {
    background: var(--bg-hover);
}

.speed-btn.active {
    background: var(--accent-primary);
    color: white;
    border-color: var(--accent-primary);
}

/* ==================== MODALS ==================== */
.modal {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.7);
    z-index: 2000;
    align-items: center;
    justify-content: center;
    animation: fadeIn 0.3s ease;
}

.modal.active {
    display: flex;
}

.modal-content {
    background: var(--bg-secondary);
    border-radius: 12px;
    max-width: 90%;
    max-height: 90vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    box-shadow: 0 10px 40px var(--shadow);
    animation: slideUp 0.3s ease;
}

.modal-header {
    padding: 20px;
    background: var(--bg-tertiary);
    border-bottom: 1px solid var(--border-color);
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.modal-title {
    font-size: 20px;
    font-weight: 700;
    display: flex;
    align-items: center;
    gap: 10px;
}

.modal-close-btn {
    width: 32px;
    height: 32px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-primary);
    cursor: pointer;
    font-size: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s ease;
}

.modal-close-btn:hover {
    background: var(--accent-danger);
    color: white;
}

.modal-body {
    padding: 20px;
    overflow-y: auto;
    flex: 1;
}

/* ==================== PLAYLIST MODAL ==================== */
.playlist-stats {
    display: flex;
    gap: 20px;
    padding: 15px;
    background: var(--bg-tertiary);
    border-radius: 8px;
    margin-bottom: 15px;
}

.playlist-stat {
    display: flex;
    flex-direction: column;
    gap: 5px;
}

.playlist-stat-label {
    font-size: 12px;
    color: var(--text-secondary);
}

.playlist-stat-value {
    font-size: 18px;
    font-weight: 700;
    color: var(--accent-primary);
}

.playlist-controls {
    display: flex;
    gap: 10px;
    margin-bottom: 20px;
    flex-wrap: wrap;
}

.playlist-control-btn {
    padding: 10px 16px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-primary);
    cursor: pointer;
    font-size: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
    transition: all 0.2s ease;
}

.playlist-control-btn:hover {
    background: var(--bg-hover);
}

.playlist-control-btn.primary {
    background: var(--accent-primary);
    color: white;
}

.playlist-control-btn.danger {
    background: var(--accent-danger);
    color: white;
}

.playlist-control-btn.loop.active {
    background: var(--accent-primary) !important;
    color: white !important;
    border-color: var(--accent-primary);
}

.now-playing {
    padding: 15px;
    background: var(--bg-tertiary);
    border: 2px solid var(--accent-primary);
    border-radius: 8px;
    margin-bottom: 20px;
    display: none;
}

.now-playing.active {
    display: block;
}

.now-playing-label {
    font-size: 12px;
    color: var(--text-secondary);
    margin-bottom: 8px;
}

.now-playing-title {
    font-size: 16px;
    font-weight: 600;
    color: var(--accent-primary);
}

.playlist-items {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.playlist-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    cursor: grab;
    transition: all 0.2s ease;
}

.playlist-item:hover {
    background: var(--bg-hover);
    border-color: var(--accent-primary);
}

.playlist-item.dragging {
    opacity: 0.5;
    cursor: grabbing;
}

.playlist-item-handle {
    font-size: 18px;
    color: var(--text-tertiary);
    cursor: grab;
}

.playlist-item-index {
    font-size: 14px;
    font-weight: 700;
    color: var(--accent-primary);
    min-width: 30px;
}

.playlist-item-name {
    flex: 1;
    font-size: 14px;
    color: var(--text-primary);
}

.playlist-item-controls {
    display: flex;
    gap: 4px;
    align-items: center;
}

.playlist-item-control-btn {
    padding: 4px 8px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-primary);
    cursor: pointer;
    font-size: 12px;
    transition: all 0.2s ease;
}

.playlist-item-control-btn:hover {
    background: var(--bg-hover);
    border-color: var(--accent-primary);
}

.playlist-item-remove {
    padding: 6px 12px;
    background: var(--accent-danger);
    border: none;
    border-radius: 4px;
    color: white;
    cursor: pointer;
    font-size: 12px;
    transition: opacity 0.2s ease;
}

.playlist-item-remove:hover {
    opacity: 0.8;
}

/* ==================== SETTINGS MODAL ==================== */
.settings-tabs {
    display: flex;
    gap: 5px;
    margin-bottom: 20px;
    border-bottom: 2px solid var(--border-color);
}

.settings-tab {
    padding: 12px 20px;
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--text-secondary);
    cursor: pointer;
    font-size: 14px;
    font-weight: 600;
    transition: all 0.2s ease;
    position: relative;
    bottom: -2px;
}

.settings-tab:hover {
    color: var(--text-primary);
}

.settings-tab.active {
    color: var(--accent-primary);
    border-bottom-color: var(--accent-primary);
}

.settings-panel {
    display: none;
}

.settings-panel.active {
    display: block;
    animation: fadeIn 0.3s ease;
}

.settings-section {
    margin-bottom: 25px;
}

.settings-section-title {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 12px;
    color: var(--accent-primary);
}

.settings-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    margin-bottom: 8px;
}

.settings-item-label {
    font-size: 14px;
    color: var(--text-primary);
}

.settings-item-description {
    font-size: 12px;
    color: var(--text-secondary);
    margin-top: 4px;
}

/* Toggle Switch */
.switch {
    position: relative;
    display: inline-block;
    width: 50px;
    height: 26px;
    flex-shrink: 0;
}

.switch input {
    position: absolute;
    opacity: 0;
    width: 100%;
    height: 100%;
    margin: 0;
    cursor: pointer;
    z-index: 1;
}

.slider {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: #555;
    transition: background-color 0.3s ease;
    border-radius: 26px;
}

.slider:before {
    position: absolute;
    content: "";
    height: 20px;
    width: 20px;
    left: 3px;
    top: 3px;
    background-color: white;
    transition: transform 0.3s ease;
    border-radius: 50%;
    box-shadow: 0 2px 4px rgba(0,0,0,0.3);
}

.switch input:checked + .slider {
    background-color: #10b981;
}

.switch input:checked + .slider:before {
    transform: translateX(24px);
}

.settings-input {
    padding: 8px 12px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-primary);
    font-size: 14px;
    min-width: 200px;
}

.theme-selector {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 10px;
}

.theme-option {
    padding: 15px;
    background: var(--bg-tertiary);
    border: 2px solid var(--border-color);
    border-radius: 8px;
    cursor: pointer;
    text-align: center;
    transition: all 0.2s ease;
    color: var(--text-primary);
}

.theme-option:hover {
    border-color: var(--accent-primary);
}

.theme-option.active {
    background: var(--accent-primary);
    color: white;
    border-color: var(--accent-primary);
}

.channel-btn {
    padding: 8px 14px;
    background: var(--bg-tertiary);
    border: 2px solid var(--border-color);
    border-radius: 8px;
    color: var(--text-primary);
    cursor: pointer;
    font-size: 13px;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s ease;
}

.channel-btn:hover {
    border-color: var(--accent-primary);
}

.channel-btn.active {
    background: var(--accent-primary);
    color: white;
    border-color: var(--accent-primary);
}

.theme-preview {
    width: 100%;
    height: 60px;
    border-radius: 4px;
    margin-bottom: 8px;
}

.category-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-height: 60px;
}

.category-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    transition: all 0.15s ease;
    position: relative;
}

.category-item:hover {
    border-color: var(--accent-primary);
    background: var(--bg-hover);
}

.category-color {
    width: 28px;
    height: 28px;
    border-radius: 6px;
    border: none;
    cursor: pointer;
    transition: transform 0.15s ease;
    flex-shrink: 0;
}

.category-color:hover {
    transform: scale(1.1);
}

.category-name {
    flex: 1;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
}

.category-name:hover {
    color: var(--accent-primary);
}

.category-name-input {
    flex: 1;
    padding: 6px 10px;
    background: var(--bg-secondary);
    border: 1px solid var(--accent-primary);
    border-radius: 4px;
    color: var(--text-primary);
    font-size: 14px;
    font-weight: 500;
}

.category-count {
    font-size: 12px;
    color: var(--text-secondary);
    background: var(--bg-secondary);
    padding: 4px 8px;
    border-radius: 10px;
}

.category-actions {
    display: flex;
    gap: 6px;
    opacity: 0;
    transition: opacity 0.15s ease;
}

.category-item:hover .category-actions {
    opacity: 1;
}

.category-btn {
    padding: 6px 10px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-secondary);
    cursor: pointer;
    font-size: 12px;
    transition: all 0.15s ease;
}

.category-btn:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
    border-color: var(--border-light);
}

.category-btn.delete:hover {
    background: var(--accent-danger);
    color: white;
    border-color: var(--accent-danger);
}

.category-btn.save {
    background: var(--accent-success);
    color: white;
    border-color: var(--accent-success);
}

.category-delete-btn {
    padding: 4px 8px;
    background: transparent;
    border: none;
    border-radius: 4px;
    color: var(--text-secondary);
    cursor: pointer;
    font-size: 14px;
    transition: all 0.15s ease;
    opacity: 0.5;
}

.category-item:hover .category-delete-btn {
    opacity: 1;
}

.category-delete-btn:hover {
    background: var(--accent-danger);
    color: white;
}

/* Color presets */
.color-presets {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-top: 8px;
}

.color-preset {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    cursor: pointer;
    border: 3px solid transparent;
    transition: all 0.15s ease;
}

.color-preset:hover {
    transform: scale(1.15);
}

.color-preset.selected {
    border-color: #fff;
    box-shadow: 0 0 0 2px var(--accent-primary);
}

/* Inline color picker */
.inline-color-picker {
    position: absolute;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 10px;
    display: flex;
    gap: 6px;
    z-index: 100;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    left: 40px;
    top: 50%;
    transform: translateY(-50%);
}

.inline-color-picker .color-preset {
    width: 24px;
    height: 24px;
    border-width: 2px;
}

.add-category-form {
    display: flex;
    gap: 10px;
}

.add-category-input {
    flex: 1;
    padding: 10px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-primary);
    font-size: 14px;
}

.color-picker {
    width: 50px;
    height: 38px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    cursor: pointer;
}

.add-category-btn {
    padding: 10px 20px;
    background: var(--accent-success);
    border: none;
    border-radius: 4px;
    color: white;
    cursor: pointer;
    font-size: 14px;
}

/* ==================== HIDDEN VIDEOS MODAL ==================== */
.hidden-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.hidden-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
}

.hidden-item-name {
    flex: 1;
    font-size: 14px;
    color: var(--text-primary);
}

.hidden-item-actions {
    display: flex;
    gap: 8px;
}

.hidden-item-btn {
    padding: 6px 12px;
    background: var(--accent-primary);
    border: none;
    border-radius: 4px;
    color: white;
    cursor: pointer;
    font-size: 12px;
}

.hidden-batch-actions {
    display: flex;
    gap: 10px;
    margin-bottom: 20px;
}

/* ==================== BOTTOM BAR ==================== */
.bottom-bar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: var(--bg-secondary);
    border-top: 1px solid var(--border-color);
    padding: 12px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    box-shadow: 0 -2px 8px var(--shadow);
    z-index: 500;
}

.speed-control {
    display: flex;
    align-items: center;
    gap: 10px;
}

.speed-label {
    font-size: 14px;
    color: var(--text-secondary);
}

.speed-buttons {
    display: flex;
    gap: 5px;
}

.speed-button {
    padding: 6px 12px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-primary);
    cursor: pointer;
    font-size: 13px;
    transition: all 0.2s ease;
}

.speed-button:hover {
    background: var(--bg-hover);
}

.speed-button.active {
    background: var(--accent-primary);
    color: white;
    border-color: var(--accent-primary);
}

.current-speed-display {
    font-size: 16px;
    font-weight: 700;
    color: var(--accent-primary);
    min-width: 60px;
    text-align: center;
}

.zoom-control {
    display: flex;
    align-items: center;
    gap: 10px;
}

.zoom-label {
    font-size: 14px;
    color: var(--text-secondary);
}

.zoom-btn {
    width: 30px;
    height: 30px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-primary);
    cursor: pointer;
    font-size: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s ease;
}

.zoom-btn:hover {
    background: var(--bg-hover);
}

.zoom-slider {
    width: 150px;
    height: 6px;
    background: var(--bg-tertiary);
    border-radius: 3px;
    outline: none;
    cursor: pointer;
}

.video-count-display {
    font-size: 14px;
    color: var(--text-secondary);
}

.video-count-number {
    font-weight: 700;
    color: var(--accent-primary);
}

/* ==================== ANIMATIONS ==================== */
@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

@keyframes slideUp {
    from { transform: translateY(20px); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
}

@keyframes slideDown {
    from { transform: translateY(-20px); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
}

/* ==================== RESPONSIVE ==================== */
@media (max-width: 768px) {
    .header-top {
        flex-direction: column;
        gap: 10px;
    }

    .header-stats {
        flex-wrap: wrap;
        justify-content: center;
    }

    .video-grid {
        grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
        gap: 15px;
        padding: 15px;
        padding-bottom: 120px; /* Maggiore spazio su mobile per bottom-bar più alto */
    }

    .bottom-bar {
        flex-direction: column;
        gap: 10px;
    }

    .modal-content {
        max-width: 95%;
        max-height: 95vh;
    }
}

/* ==================== UTILITIES ==================== */
.hidden {
    display: none !important;
}

.loading {
    opacity: 0.5;
    pointer-events: none;
}

.empty-state {
    text-align: center;
    padding: 60px 20px;
    color: var(--text-secondary);
}

.empty-state-icon {
    font-size: 64px;
    margin-bottom: 20px;
}

.empty-state-text {
    font-size: 18px;
    margin-bottom: 10px;
}

.empty-state-subtext {
    font-size: 14px;
}

/* Loading Overlay */
.loading-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: var(--bg-primary);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 99999;
    transition: opacity 0.3s ease, visibility 0.3s ease;
}

.loading-overlay.hidden {
    opacity: 0;
    visibility: hidden;
}

.loading-content {
    text-align: center;
}

.loading-spinner {
    width: 50px;
    height: 50px;
    border: 4px solid var(--border-color);
    border-top-color: var(--accent-primary);
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin: 0 auto 20px;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

.loading-text {
    font-size: 16px;
    color: var(--text-secondary);
}
</style>
</head>
<body data-theme="default">

<!-- ==================== LOADING OVERLAY ==================== -->
<div class="loading-overlay" id="loading-overlay">
    <div class="loading-content">
        <div class="loading-spinner"></div>
        <div class="loading-text">Caricamento configurazione...</div>
    </div>
</div>

<!-- ==================== HEADER ==================== -->
<div class="header">
    <div class="header-top">
        <div class="header-logo">
            <span class="header-logo-icon">⚡</span>
            <span>OBS Instant Replay</span>
        </div>

        <div class="header-actions">
            <button class="header-btn" onclick="toggleSearch()" title="Cerca">
                <span class="btn-icon">🔍</span>
                <span class="btn-text">Cerca</span>
            </button>
            <button class="header-btn" onclick="openPlaylistModal()" title="Playlist">
                <span class="btn-icon">📋</span>
                <span class="btn-text">Playlist</span>
            </button>
            <button class="header-btn" onclick="openHighlightsModal()" title="Highlights">
                <span class="btn-icon">✨</span>
                <span class="btn-text">Highlights</span>
            </button>
            <button class="header-btn" onclick="openSettingsModal()" title="Impostazioni">
                <span class="btn-icon">⚙️</span>
                <span class="btn-text">Impostazioni</span>
            </button>
            <button class="header-btn" onclick="openHiddenModal()" title="Video nascosti">
                <span class="btn-icon">👁️</span>
                <span class="btn-text">Nascosti</span>
            </button>
            <button class="header-btn" onclick="refreshReplays()" title="Aggiorna lista">
                <span class="btn-icon">🔄</span>
                <span class="btn-text">Aggiorna</span>
            </button>
        </div>

        <div class="header-stats">
            <div class="stat-item">
                <span>📹</span>
                <span class="stat-value" id="stat-total">0</span>
            </div>
            <div class="stat-item">
                <span>⭐</span>
                <span class="stat-value" id="stat-favorites">0</span>
            </div>
            <div class="stat-item">
                <span>👁️</span>
                <span class="stat-value" id="stat-hidden">0</span>
            </div>
            <div class="stat-item">
                <span>🕐</span>
                <span class="stat-value" id="last-scan-time">--:--:--</span>
            </div>
        </div>
    </div>

    <!-- Search Bar -->
    <div class="search-bar" id="search-bar">
        <div class="search-input-wrapper">
            <input type="text" class="search-input" id="search-input" placeholder="Cerca per nome file..." oninput="filterVideos()">
            <button class="search-clear-btn" onclick="clearSearch()">Cancella</button>
        </div>
    </div>

    <!-- Filters Bar -->
    <div class="filters-bar">
        <button class="filter-btn" id="filter-favorites" onclick="toggleFilter('favorites')">
            <span>⭐</span>
            <span>Preferiti</span>
        </button>
        <button class="filter-btn" id="filter-queue" onclick="toggleFilter('queue')">
            <span>📋</span>
            <span>In coda</span>
        </button>
        <div class="filter-dropdown-container" id="category-dropdown">
            <div class="filter-dropdown-trigger" onclick="toggleCategoryDropdown()">
                <span class="filter-icon">🏷️</span>
                <span class="filter-text" id="category-filter-text">Categorie</span>
                <span class="dropdown-arrow">▼</span>
            </div>
            <div class="filter-dropdown-menu" id="category-dropdown-menu">
                <!-- Items populated by JS -->
            </div>
        </div>
    </div>
</div>

<!-- ==================== VIDEO GRID ==================== -->
<div class="video-grid" id="video-grid">
    <!-- Video cards will be inserted here dynamically -->
</div>

<!-- ==================== PLAYLIST MODAL ==================== -->
<div class="modal" id="playlist-modal">
    <div class="modal-content" style="width: 600px;">
        <div class="modal-header">
            <div class="modal-title">
                <span>📋</span>
                <span>Playlist / Coda</span>
            </div>
            <button class="modal-close-btn" onclick="closePlaylistModal()">✕</button>
        </div>
        <div class="modal-body">
            <div class="playlist-stats">
                <div class="playlist-stat">
                    <div class="playlist-stat-label">Video in coda</div>
                    <div class="playlist-stat-value" id="playlist-count">0</div>
                </div>
                <div class="playlist-stat">
                    <div class="playlist-stat-label">Durata totale</div>
                    <div class="playlist-stat-value" id="playlist-duration">--:--</div>
                </div>
            </div>

            <div class="playlist-controls">
                <button class="playlist-control-btn primary" onclick="playPlaylist()">
                    <span>▶️</span>
                    <span>Play</span>
                </button>
                <button class="playlist-control-btn" onclick="stopPlaylist()">
                    <span>⏹️</span>
                    <span>Stop</span>
                </button>
                <button class="playlist-control-btn loop" onclick="toggleLoop()">
                    <span>🔁</span>
                    <span>Loop</span>
                </button>
                <button class="playlist-control-btn" onclick="shufflePlaylist()">
                    <span>🔀</span>
                    <span>Shuffle</span>
                </button>
                <button class="playlist-control-btn danger" onclick="clearPlaylist()">
                    <span>🗑️</span>
                    <span>Svuota</span>
                </button>
            </div>

            <div class="now-playing" id="now-playing">
                <div class="now-playing-label">In riproduzione:</div>
                <div class="now-playing-title" id="now-playing-title">--</div>
            </div>

            <div class="settings-section" style="margin-top: 20px;">
                <div class="settings-section-title">📋 Coda Riproduzione</div>
                <div class="playlist-items" id="playlist-items">
                    <!-- Playlist items will be inserted here -->
                </div>
                <div class="empty-state" id="playlist-empty" style="display: none;">
                    <div class="empty-state-icon">📋</div>
                    <div class="empty-state-text">Playlist vuota</div>
                    <div class="empty-state-subtext">Aggiungi video dalla griglia</div>
                </div>
                <div style="display: flex; gap: 10px; margin-top: 10px;">
                    <button class="playlist-control-btn primary" onclick="createHighlightsFromQueue()">
                        <span>✨</span>
                        <span>Crea Highlights da coda</span>
                    </button>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- ==================== HIGHLIGHTS MODAL ==================== -->
<div class="modal" id="highlights-modal">
    <div class="modal-content" style="width: 700px;">
        <div class="modal-header">
            <h2>✨ Highlights Creati</h2>
            <button class="modal-close-btn" onclick="closeHighlightsModal()">✕</button>
        </div>

        <div class="modal-body">
            <div id="highlights-list" style="max-height: 500px; overflow-y: auto;">
                <!-- Lista highlights generata dinamicamente -->
            </div>

            <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid var(--border-color); color: var(--text-secondary); font-size: 13px;">
                💡 <strong>Come creare highlights:</strong> Aggiungi video alla coda, riordina come preferisci, poi clicca "Crea Highlights da coda" nella sezione Playlist.
            </div>
        </div>
    </div>
</div>

<!-- ==================== SETTINGS MODAL ==================== -->
<div class="modal" id="settings-modal">
    <div class="modal-content" style="width: 700px;">
        <div class="modal-header">
            <div class="modal-title">
                <span>⚙️</span>
                <span>Impostazioni</span>
            </div>
            <button class="modal-close-btn" onclick="closeSettingsModal()">✕</button>
        </div>
        <div class="modal-body">
            <div class="settings-tabs">
                <button class="settings-tab active" onclick="switchSettingsTab('general')">Generale</button>
                <button class="settings-tab" onclick="switchSettingsTab('categories')">Categorie</button>
                <button class="settings-tab" onclick="switchSettingsTab('themes')">Temi</button>
                <button class="settings-tab" onclick="switchSettingsTab('info')">About</button>
            </div>

            <!-- General Panel -->
            <div class="settings-panel active" id="panel-general">
                <div class="settings-section">
                    <div class="settings-section-title">Configurazione OBS</div>
                    <div class="settings-item" style="flex-direction: column; align-items: stretch; gap: 8px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <div class="settings-item-label">Cartella Replay</div>
                                <div class="settings-item-description">Percorso della cartella contenente i replay</div>
                            </div>
                            <button class="header-btn" onclick="openFolder()" title="Apri cartella">
                                <span>📂</span>
                            </button>
                        </div>
                        <div style="display: flex; gap: 8px; align-items: center;">
                            <input type="text" class="settings-input" id="replay-folder-path" style="flex: 1;" placeholder="Seleziona cartella...">
                            <button class="header-btn" onclick="browseFolder()">
                                <span>📁</span>
                                <span>Sfoglia</span>
                            </button>
                        </div>
                    </div>
                    <div class="settings-item">
                        <div>
                            <div class="settings-item-label">Nome Media Source</div>
                            <div class="settings-item-description">Nome della sorgente multimediale in OBS</div>
                        </div>
                        <input type="text" class="settings-input" id="media-source-name" placeholder="es. Replay Source">
                    </div>
                    <div class="settings-item">
                        <div>
                            <div class="settings-item-label">Scena Target</div>
                            <div class="settings-item-description">Scena OBS dove caricare i replay</div>
                        </div>
                        <input type="text" class="settings-input" id="target-scene-name" placeholder="es. Replay Scene">
                    </div>
                    <div class="settings-item">
                        <div>
                            <div class="settings-item-label">Auto-switch scena</div>
                            <div class="settings-item-description">Cambia automaticamente scena quando carichi un video</div>
                        </div>
                        <label class="switch">
                            <input type="checkbox" id="auto-switch-scene">
                            <span class="slider"></span>
                        </label>
                    </div>
                </div>

                <div class="settings-section">
                    <div class="settings-section-title">Filtri</div>
                    <div class="settings-item">
                        <div>
                            <div class="settings-item-label">Filtro nome file</div>
                            <div class="settings-item-description">Mostra solo file che iniziano con questo testo</div>
                        </div>
                        <input type="text" class="settings-input" id="filter-mask" placeholder="es. Replay_">
                    </div>
                </div>

                <div class="settings-section" style="margin-top: 16px;">
                    <button class="header-btn primary" onclick="saveOBSSettings()" style="width: 100%; justify-content: center;">
                        <span>💾</span>
                        <span>Salva Impostazioni</span>
                    </button>
                </div>

                <div class="settings-section" style="margin-top: 16px;">
                    <div class="settings-section-title">Backup Configurazione</div>
                    <div class="settings-item-description" style="margin-bottom: 12px;">
                        Esporta o importa tutte le configurazioni, categorie e preferiti
                    </div>
                    <div style="display: flex; gap: 8px;">
                        <button class="header-btn" onclick="exportConfig()" style="flex: 1; justify-content: center;">
                            <span>📤</span>
                            <span>Esporta</span>
                        </button>
                        <button class="header-btn" onclick="importConfig()" style="flex: 1; justify-content: center;">
                            <span>📥</span>
                            <span>Importa</span>
                        </button>
                    </div>
                    <input type="file" id="import-config-input" accept=".json" style="display: none;" onchange="handleConfigImport(event)">
                </div>
            </div>

            <!-- Categories Panel -->
            <div class="settings-panel" id="panel-categories">
                <div class="settings-section">
                    <div class="settings-section-title">Nuova Categoria</div>
                    <div class="add-category-form" style="margin-bottom: 12px;">
                        <input type="text" class="add-category-input" id="new-category-name" placeholder="Nome categoria...">
                        <button class="add-category-btn" onclick="addCategory()">Aggiungi</button>
                    </div>
                    <div class="color-presets" id="color-presets">
                        <div class="color-preset selected" data-color="#e74c3c" style="background:#e74c3c;" onclick="selectPresetColor(this)"></div>
                        <div class="color-preset" data-color="#e67e22" style="background:#e67e22;" onclick="selectPresetColor(this)"></div>
                        <div class="color-preset" data-color="#f1c40f" style="background:#f1c40f;" onclick="selectPresetColor(this)"></div>
                        <div class="color-preset" data-color="#2ecc71" style="background:#2ecc71;" onclick="selectPresetColor(this)"></div>
                        <div class="color-preset" data-color="#1abc9c" style="background:#1abc9c;" onclick="selectPresetColor(this)"></div>
                        <div class="color-preset" data-color="#3498db" style="background:#3498db;" onclick="selectPresetColor(this)"></div>
                        <div class="color-preset" data-color="#9b59b6" style="background:#9b59b6;" onclick="selectPresetColor(this)"></div>
                        <div class="color-preset" data-color="#e91e63" style="background:#e91e63;" onclick="selectPresetColor(this)"></div>
                        <div class="color-preset" data-color="#607d8b" style="background:#607d8b;" onclick="selectPresetColor(this)"></div>
                    </div>
                </div>

                <div class="settings-section">
                    <div class="settings-section-title">Le Tue Categorie</div>
                    <div class="category-list" id="category-list">
                        <!-- Categories will be inserted here -->
                    </div>
                </div>
            </div>

            <!-- Themes Panel -->
            <div class="settings-panel" id="panel-themes">
                <div class="settings-section">
                    <div class="settings-section-title">Seleziona Tema</div>
                    <div class="theme-selector">
                        <div class="theme-option active" data-theme="default" onclick="setTheme('default')">
                            <div class="theme-preview" style="background: linear-gradient(135deg, #1a1a1a, #4a9eff);"></div>
                            <div>Dark (Default)</div>
                        </div>
                        <div class="theme-option" data-theme="light" onclick="setTheme('light')">
                            <div class="theme-preview" style="background: linear-gradient(135deg, #f5f5f5, #2196f3);"></div>
                            <div>Light</div>
                        </div>
                        <div class="theme-option" data-theme="blue" onclick="setTheme('blue')">
                            <div class="theme-preview" style="background: linear-gradient(135deg, #0a1628, #4a9eff);"></div>
                            <div>Blue (Acri)</div>
                        </div>
                        <div class="theme-option" data-theme="green" onclick="setTheme('green')">
                            <div class="theme-preview" style="background: linear-gradient(135deg, #0d1f0d, #44ff88);"></div>
                            <div>Green (Rachni)</div>
                        </div>
                        <div class="theme-option" data-theme="classic" onclick="setTheme('classic')">
                            <div class="theme-preview" style="background: linear-gradient(135deg, #2b2b2b, #66aaff);"></div>
                            <div>Classic</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- About Panel -->
            <div class="settings-panel" id="panel-info">
                <div class="settings-section">
                    <div class="settings-section-title">OBS Instant Replay</div>
                    <div class="settings-item" style="flex-direction: column; align-items: flex-start; gap: 12px;">
                        <div style="display: flex; width: 100%; justify-content: space-between; align-items: center;">
                            <div>
                                <div class="settings-item-label">Versione corrente: <span id="current-version">--</span></div>
                                <div class="settings-item-description" id="update-status">Clicca per verificare aggiornamenti</div>
                            </div>
                            <button class="header-btn" id="check-updates-btn" onclick="checkForUpdates()">
                                <span>🔄</span>
                                <span>Verifica</span>
                            </button>
                        </div>
                        <div id="update-info" style="display: none; width: 100%; padding: 12px; background: var(--bg-secondary); border-radius: 8px; border: 1px solid var(--border-color);">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                                <div>
                                    <strong style="color: var(--accent-success);">Nuova versione disponibile: <span id="new-version">--</span></strong>
                                    <span id="prerelease-badge" style="display: none; margin-left: 8px; padding: 2px 6px; background: var(--accent-warning); color: #000; border-radius: 4px; font-size: 10px; font-weight: bold;">BETA</span>
                                </div>
                                <a id="release-link" href="#" target="_blank" style="color: var(--accent-primary); font-size: 12px;">Vedi su GitHub</a>
                            </div>
                            <div id="release-notes" style="font-size: 12px; color: var(--text-secondary); margin-bottom: 12px; max-height: 100px; overflow-y: auto;"></div>
                            <div id="update-assets" style="display: flex; gap: 8px; flex-wrap: wrap;"></div>
                        </div>
                    </div>

                    <div class="settings-item" style="margin-top: 12px;">
                        <div>
                            <div class="settings-item-label">Canale aggiornamenti</div>
                            <div class="settings-item-description">Beta include versioni di test, Stabile solo release ufficiali</div>
                        </div>
                        <div class="channel-selector" style="display: flex; gap: 8px;">
                            <button class="channel-btn" id="channel-beta" onclick="setUpdateChannel('beta')">
                                <span>🧪</span> Beta
                            </button>
                            <button class="channel-btn" id="channel-stable" onclick="setUpdateChannel('stable')">
                                <span>✅</span> Stabile
                            </button>
                        </div>
                    </div>
                </div>

                <div class="settings-section">
                    <div class="settings-section-title">Informazioni</div>
                    <div class="settings-item">
                        <div class="settings-item-label">Server HTTP</div>
                        <div class="settings-item-description" id="server-url">http://localhost:8765</div>
                    </div>
                    <div class="settings-item">
                        <div class="settings-item-label">Repository</div>
                        <div class="settings-item-description">
                            <a href="https://github.com/angeloruggieridj/OBS-Instant-Replay" target="_blank" style="color: var(--accent-primary);">github.com/angeloruggieridj/OBS-Instant-Replay</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- ==================== HIDDEN VIDEOS MODAL ==================== -->
<div class="modal" id="hidden-modal">
    <div class="modal-content" style="width: 600px;">
        <div class="modal-header">
            <div class="modal-title">
                <span>👁️</span>
                <span>Video Nascosti</span>
            </div>
            <button class="modal-close-btn" onclick="closeHiddenModal()">✕</button>
        </div>
        <div class="modal-body">
            <div class="hidden-batch-actions">
                <button class="playlist-control-btn primary" onclick="unhideAll()">
                    <span>👁️</span>
                    <span>Mostra tutti</span>
                </button>
            </div>

            <div class="hidden-list" id="hidden-list">
                <!-- Hidden items will be inserted here -->
            </div>

            <div class="empty-state" id="hidden-empty" style="display: none;">
                <div class="empty-state-icon">👁️</div>
                <div class="empty-state-text">Nessun video nascosto</div>
                <div class="empty-state-subtext">I video nascosti appariranno qui</div>
            </div>
        </div>
    </div>
</div>

<!-- ==================== BOTTOM BAR ==================== -->
<div class="bottom-bar">
    <div class="speed-control">
        <span class="speed-label">Velocità:</span>
        <div class="speed-buttons">
            <button class="speed-button" data-speed="0.5" onclick="setGlobalSpeed(0.5)">0.5x</button>
            <button class="speed-button active" data-speed="1" onclick="setGlobalSpeed(1)">1x</button>
            <button class="speed-button" data-speed="1.5" onclick="setGlobalSpeed(1.5)">1.5x</button>
            <button class="speed-button" data-speed="2" onclick="setGlobalSpeed(2)">2x</button>
        </div>
        <div class="current-speed-display" id="current-speed-display">1.0x</div>
    </div>

    <div class="zoom-control">
        <span class="zoom-label">Zoom:</span>
        <button class="zoom-btn" onclick="adjustZoom(-20)">−</button>
        <input type="range" class="zoom-slider" id="zoom-slider" min="120" max="320" step="1" value="200" oninput="setZoom(this.value)">
        <button class="zoom-btn" onclick="adjustZoom(20)">+</button>
    </div>

    <div class="video-count-display">
        <span>Video: </span>
        <span class="video-count-number" id="bottom-video-count">0</span>
    </div>
</div>

<!-- ==================== JAVASCRIPT ==================== -->
<script>
// ==================== GLOBAL STATE ====================
let allReplays = [];
let currentFilter = {
    search: '',
    favorites: false,
    queue: false,
    category: ''
};
let playlistQueue = [];
let categories = {};
let hiddenVideos = [];
let currentSpeed = 1.0;
let currentTheme = 'default';
let cardZoom = 200;
let draggedItem = null;
let autoRefreshInterval = null;
let statusRefreshInterval = null;
let playlistIsPlaying = false;
let playlistLoopEnabled = false;
let currentQueueIndex = 0;

// ==================== INITIALIZATION ====================
async function init() {
    await loadConfig();
    await loadCategories();
    await loadReplays();
    await loadVersion();
    startAutoRefresh();

    // Nascondi loading overlay
    const loadingOverlay = document.getElementById('loading-overlay');
    if (loadingOverlay) {
        loadingOverlay.classList.add('hidden');
    }
}

function startAutoRefresh() {
    const scanInterval = 5000; // 5 secondi per scan completo (ridotto da 3s)

    // Pulisci intervalli esistenti per evitare memory leak
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }
    if (statusRefreshInterval) {
        clearInterval(statusRefreshInterval);
        statusRefreshInterval = null;
    }

    // Auto-refresh completo ogni 5 secondi (con scan)
    autoRefreshInterval = setInterval(async () => {
        try {
            // FORZA scan prima di ricaricare
            await apiCall('/api/scan', 'POST');
            await loadReplays();

            // Aggiorna orario scan nell'header
            const now = new Date();
            const timeStr = now.toLocaleTimeString('it-IT', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
            const lastScanElement = document.getElementById('last-scan-time');
            if (lastScanElement) {
                lastScanElement.textContent = timeStr;
            }
        } catch (e) {
            console.error('[AutoRefresh] Error:', e);
        }
    }, scanInterval);
}

// ==================== API CALLS ====================
async function apiCall(endpoint, method = 'GET', data = null) {
    try {
        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            }
        };

        if (data) {
            options.body = JSON.stringify(data);
        }

        const response = await fetch(endpoint, options);
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        showNotification('Errore di comunicazione con il server', 'error');
        return null;
    }
}

async function loadConfig() {
    const data = await apiCall('/api/config');
    if (data) {
        currentSpeed = data.current_speed || 1.0;
        currentTheme = data.current_theme || 'default';
        cardZoom = data.card_zoom || 200;

        // Apply loaded config
        document.body.setAttribute('data-theme', currentTheme);
        document.getElementById('zoom-slider').value = cardZoom;
        setZoom(cardZoom);
        updateSpeedDisplay();

        // Update OBS settings
        if (data.replay_folder) {
            document.getElementById('replay-folder-path').value = data.replay_folder;
        }
        if (data.media_source_name) {
            document.getElementById('media-source-name').value = data.media_source_name;
        }
        if (data.target_scene_name) {
            document.getElementById('target-scene-name').value = data.target_scene_name;
        }
        document.getElementById('auto-switch-scene').checked = data.auto_switch_scene || false;
        if (data.filter_mask) {
            document.getElementById('filter-mask').value = data.filter_mask;
        }

        // Update channel selector
        const channel = data.update_channel || 'beta';
        updateChannelUI(channel);
    }
}

async function saveOBSSettings() {
    const settings = {
        replay_folder: document.getElementById('replay-folder-path').value,
        media_source_name: document.getElementById('media-source-name').value,
        target_scene_name: document.getElementById('target-scene-name').value,
        auto_switch_scene: document.getElementById('auto-switch-scene').checked,
        filter_mask: document.getElementById('filter-mask').value
    };

    const result = await apiCall('/api/obs-settings', 'POST', settings);

    if (result && result.success) {
        showNotification('Impostazioni salvate', 'success');
        await loadReplays();
    } else {
        showNotification('Errore nel salvataggio', 'error');
    }
}

async function browseFolder() {
    // Usa l'API del server per aprire il dialog nativo del sistema operativo
    const btn = event.target.closest('button');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span>⏳</span><span>Apertura...</span>';
    btn.disabled = true;

    try {
        const result = await apiCall('/api/browse-folder', 'POST', {});

        if (result && result.success && result.path) {
            document.getElementById('replay-folder-path').value = result.path;
            showNotification('Cartella selezionata', 'success');
        } else if (result && !result.success) {
            // L'utente ha annullato, nessun messaggio di errore
        }
    } catch (e) {
        showNotification('Errore apertura dialog', 'error');
    }

    btn.innerHTML = originalText;
    btn.disabled = false;
}

async function exportConfig() {
    try {
        const result = await apiCall('/api/config/export', 'POST', {});

        if (result && result.success && result.config) {
            const configJson = JSON.stringify(result.config, null, 2);
            const defaultFileName = `obs-instant-replay-config-${new Date().toISOString().split('T')[0]}.json`;

            // Prova a usare il File System Access API (permette di scegliere dove salvare)
            if (window.showSaveFilePicker) {
                try {
                    const handle = await window.showSaveFilePicker({
                        suggestedName: defaultFileName,
                        types: [{
                            description: 'JSON Configuration',
                            accept: { 'application/json': ['.json'] }
                        }]
                    });
                    const writable = await handle.createWritable();
                    await writable.write(configJson);
                    await writable.close();
                    showNotification('Configurazione esportata', 'success');
                    return;
                } catch (e) {
                    // L'utente ha annullato o API non supportata, usa fallback
                    if (e.name === 'AbortError') return;
                }
            }

            // Fallback: download diretto
            const blob = new Blob([configJson], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = defaultFileName;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            showNotification('Configurazione esportata', 'success');
        } else {
            showNotification('Errore esportazione', 'error');
        }
    } catch (e) {
        showNotification('Errore esportazione: ' + e.message, 'error');
    }
}

function importConfig() {
    document.getElementById('import-config-input').click();
}

async function handleConfigImport(event) {
    const file = event.target.files[0];
    if (!file) return;

    try {
        const text = await file.text();
        const config = JSON.parse(text);

        // Verifica che sia un file di configurazione valido
        if (!config.version || !config.settings) {
            showNotification('File di configurazione non valido', 'error');
            return;
        }

        // Conferma importazione
        if (!confirm(`Importare la configurazione da "${file.name}"?\\n\\nQuesto sovrascriverà le impostazioni attuali.`)) {
            return;
        }

        const result = await apiCall('/api/config/import', 'POST', { config });

        if (result && result.success) {
            showNotification('Configurazione importata con successo', 'success');
            // Ricarica la pagina per applicare le nuove impostazioni
            setTimeout(() => location.reload(), 1000);
        } else {
            showNotification('Errore importazione: ' + (result?.error || 'Sconosciuto'), 'error');
        }
    } catch (e) {
        showNotification('Errore lettura file: ' + e.message, 'error');
    }

    // Reset input file
    event.target.value = '';
}

async function loadReplays() {
    const data = await apiCall('/api/replays');
    if (data) {
        allReplays = data.replays || [];

        // Update statistics
        document.getElementById('stat-total').textContent = data.count || 0;
        document.getElementById('stat-favorites').textContent = data.favorites_count || 0;
        document.getElementById('stat-hidden').textContent = data.hidden_count || 0;
        document.getElementById('bottom-video-count').textContent = data.count || 0;

        // Update last scan time
        if (data.last_scan_time) {
            document.getElementById('last-scan-time').textContent = data.last_scan_time;
        }

        // Apply filters and render
        filterVideos();
    }
}

async function refreshReplays() {
    showNotification('Aggiornamento in corso...', 'info');
    await apiCall('/api/scan');
    await loadReplays();
    showNotification('Aggiornamento completato', 'success');
}

// ==================== HEADER FUNCTIONS ====================
function toggleSearch() {
    const searchBar = document.getElementById('search-bar');
    searchBar.classList.toggle('active');
    if (searchBar.classList.contains('active')) {
        document.getElementById('search-input').focus();
    }
}

function clearSearch() {
    document.getElementById('search-input').value = '';
    currentFilter.search = '';
    filterVideos();
}

async function openPlaylistModal() {
    await loadPlaylist();
    renderPlaylist();
    document.getElementById('playlist-modal').classList.add('active');
}

function openSettingsModal() {
    document.getElementById('settings-modal').classList.add('active');
    switchSettingsTab('general');
}

async function openHiddenModal() {
    await loadHiddenVideos();
    renderHiddenVideos();
    document.getElementById('hidden-modal').classList.add('active');
}

function closePlaylistModal() {
    document.getElementById('playlist-modal').classList.remove('active');
}

function closeSettingsModal() {
    document.getElementById('settings-modal').classList.remove('active');
}

function closeHiddenModal() {
    document.getElementById('hidden-modal').classList.remove('active');
}

async function openHighlightsModal() {
    await renderHighlights();
    document.getElementById('highlights-modal').classList.add('active');
}

function closeHighlightsModal() {
    document.getElementById('highlights-modal').classList.remove('active');
}

async function renderHighlights() {
    const data = await apiCall('/api/highlights');
    const highlights = data ? (data.highlights || []) : [];
    const listDiv = document.getElementById('highlights-list');

    if (highlights.length === 0) {
        listDiv.innerHTML = `
            <div style="text-align: center; padding: 40px; color: var(--text-secondary);">
                <div style="font-size: 48px; margin-bottom: 16px;">🎬</div>
                <div style="font-size: 16px; margin-bottom: 8px;">Nessun highlights creato</div>
                <div style="font-size: 13px;">Crea il tuo primo highlights dalla sezione Playlist</div>
            </div>
        `;
        return;
    }

    listDiv.innerHTML = highlights.map(h => `
        <div style="display: flex; align-items: center; padding: 12px; border: 1px solid var(--border-color); border-radius: 8px; margin-bottom: 10px; background: var(--bg-tertiary);">
            <div style="flex: 1;">
                <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 4px;">${h.name}</div>
                <div style="font-size: 12px; color: var(--text-secondary);">
                    📅 ${h.created} • ⏱️ ${h.duration_str || 'N/A'} • 💾 ${h.size_str}
                </div>
            </div>
            <div style="display: flex; gap: 8px;">
                <button class="video-action-btn" onclick="loadHighlightFile('${h.path.replace(/'/g, "\\'")}');" title="Carica in OBS" style="padding: 8px 12px;">▶️ Carica</button>
                <button class="video-action-btn" onclick="deleteHighlightFile('${h.path.replace(/'/g, "\\'")}');" title="Elimina" style="padding: 8px 12px; color: var(--accent-danger);">🗑️</button>
            </div>
        </div>
    `).join('');
}

async function loadHighlightFile(path) {
    await loadVideo(path);
    closeHighlightsModal();
    showNotification('Highlights caricato in OBS', 'success');
}

async function deleteHighlightFile(filePath) {
    if (!confirm('Eliminare questo file highlights?')) return;
    await apiCall('/api/delete', 'POST', { path: filePath });
    await loadReplays();
    await renderHighlights();
    showNotification('Highlights eliminato', 'success');
    document.getElementById('highlights-modal').classList.remove('active');
}

// ==================== FILTER FUNCTIONS ====================
function toggleFilter(filterType) {
    const btn = document.getElementById(`filter-${filterType}`);

    if (filterType === 'favorites') {
        currentFilter.favorites = !currentFilter.favorites;
        btn.classList.toggle('active', currentFilter.favorites);
    } else if (filterType === 'queue') {
        currentFilter.queue = !currentFilter.queue;
        btn.classList.toggle('active', currentFilter.queue);
    }

    filterVideos();
}

function filterVideos() {
    // Get search term
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        currentFilter.search = searchInput.value.toLowerCase();
    }

    // Category filter is now set via selectCategory()

    // Apply filters
    let filtered = allReplays.filter(replay => {
        // Search filter
        if (currentFilter.search && !replay.name.toLowerCase().includes(currentFilter.search)) {
            return false;
        }

        // Favorites filter
        if (currentFilter.favorites && !replay.favorite) {
            return false;
        }

        // Queue filter
        if (currentFilter.queue && !replay.in_queue) {
            return false;
        }

        // Category filter
        if (currentFilter.category && replay.category !== currentFilter.category) {
            return false;
        }

        return true;
    });

    renderVideoGrid(filtered);
}

// ==================== VIDEO CARD FUNCTIONS ====================
function renderVideoGrid(replays = allReplays) {
    const grid = document.getElementById('video-grid');

    // Rimuovi sempre l'empty-state se esiste
    const emptyState = grid.querySelector('.empty-state');
    if (emptyState) {
        emptyState.remove();
    }

    if (replays.length === 0) {
        grid.innerHTML = `
            <div class="empty-state" style="grid-column: 1 / -1;">
                <div class="empty-state-icon">📹</div>
                <div class="empty-state-text">Nessun video trovato</div>
                <div class="empty-state-subtext">Controlla i filtri o aggiungi nuovi replay</div>
            </div>
        `;
        return;
    }

    // Ottieni le card esistenti
    const existingCards = grid.querySelectorAll('.video-card');
    const existingPaths = new Set();
    existingCards.forEach(card => {
        existingPaths.add(card.dataset.path);
    });

    // Costruisci set di path dei replay da mostrare
    const replayPaths = new Set(replays.map(r => r.path));

    // Rimuovi card non più presenti (con cleanup risorse)
    existingCards.forEach(card => {
        const cardPath = card.dataset.path;
        if (!replayPaths.has(cardPath)) {
            // Cleanup video element per liberare memoria
            const video = card.querySelector('video');
            if (video) {
                video.pause();
                video.src = '';
                video.load();
            }
            card.remove();
        }
    });

    // Aggiorna o crea card per ogni replay
    replays.forEach((replay, position) => {
        const existingCard = grid.querySelector(`.video-card[data-path="${CSS.escape(replay.path)}"]`);

        if (existingCard) {
            // Aggiorna solo i badge e le info, non ricreare il video
            updateCardBadges(existingCard, replay);
        } else {
            // Crea nuova card
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = createVideoCard(replay);
            const newCard = tempDiv.firstElementChild;

            // Inserisci nella posizione corretta
            const children = grid.children;
            if (position < children.length) {
                grid.insertBefore(newCard, children[position]);
            } else {
                grid.appendChild(newCard);
            }
        }
    });

    // Riordina le card se necessario
    replays.forEach((replay, position) => {
        const card = grid.querySelector(`.video-card[data-path="${CSS.escape(replay.path)}"]`);
        if (card && card !== grid.children[position]) {
            grid.insertBefore(card, grid.children[position]);
        }
    });
}

function updateCardBadges(card, replay) {
    const thumbnail = card.querySelector('.video-thumbnail');

    // Aggiorna URL thumbnail e video (l'indice potrebbe essere cambiato)
    const img = thumbnail.querySelector('img');
    const video = thumbnail.querySelector('video');
    const newThumbnailUrl = `/api/thumbnail/${replay.index}?t=${replay.modified}`;
    const newVideoUrl = `/api/video/${replay.index}?t=${replay.modified}`;

    if (img && !img.src.endsWith(newThumbnailUrl)) {
        img.src = newThumbnailUrl;
    }
    if (video) {
        const sources = video.querySelectorAll('source');
        let needsReload = false;
        sources.forEach(source => {
            if (!source.src.endsWith(newVideoUrl)) {
                source.src = newVideoUrl;
                needsReload = true;
            }
        });
        // Ricarica solo se URL cambiato E video non in riproduzione (hover)
        if (needsReload && video.paused) {
            video.load();
        }
    }

    // Rimuovi badge READY esistente prima di aggiungere quello nuovo
    const existingReady = thumbnail.querySelector('.badge-ready');
    if (existingReady) existingReady.remove();

    // Aggiungi badge READY se il video è pronto
    if (replay.is_ready) {
        const badge = document.createElement('div');
        badge.className = 'badge-ready';
        badge.innerHTML = '● READY';
        thumbnail.appendChild(badge);
    }

    // Aggiorna badge in alto a sinistra (categoria, preferito, coda)
    const badgesContainer = card.querySelector('.video-badges');
    const badges = [];

    // Categoria prima
    if (replay.category) {
        const categoryColor = replay.category_color || '#888';
        badges.push(`<div class="video-badge badge-category" style="background-color: ${categoryColor}; color: white;">${replay.category}</div>`);
    }

    if (replay.favorite) {
        badges.push('<div class="video-badge badge-favorite">⭐ Preferito</div>');
    }

    if (replay.in_queue) {
        badges.push(`<div class="video-badge badge-queue">#${replay.queue_index + 1} Coda</div>`);
    }

    badgesContainer.innerHTML = badges.join('');

    // Aggiorna badge durata (in basso a destra)
    let durationBadge = thumbnail.querySelector('.badge-duration');
    if (replay.duration_str) {
        if (!durationBadge) {
            durationBadge = document.createElement('div');
            durationBadge.className = 'badge-duration';
            thumbnail.appendChild(durationBadge);
        }
        durationBadge.textContent = replay.duration_str;
    } else if (durationBadge) {
        durationBadge.remove();
    }

    // Aggiorna pulsante preferito
    const favBtn = card.querySelector('.video-action-btn');
    if (favBtn) {
        if (replay.favorite) {
            favBtn.classList.add('active');
        } else {
            favBtn.classList.remove('active');
        }
    }
}

function createVideoCard(replay) {
    const badges = [];
    // Escape path per uso in attributi HTML
    const escapedPath = replay.path.replace(/\\\\/g, '\\\\\\\\').replace(/'/g, "\\\\'");

    // Badge READY (posizionato in alto a destra)
    let statusBadge = '';
    if (replay.is_ready) {
        statusBadge = '<div class="badge-ready">● READY</div>';
    }

    // Badge categoria (in alto a sinistra)
    if (replay.category) {
        const categoryColor = replay.category_color || '#888';
        badges.push(`<div class="video-badge badge-category" style="background-color: ${categoryColor}; color: white;">${replay.category}</div>`);
    }

    if (replay.favorite) {
        badges.push('<div class="video-badge badge-favorite">⭐ Preferito</div>');
    }

    if (replay.in_queue) {
        badges.push(`<div class="video-badge badge-queue">#${replay.queue_index + 1} Coda</div>`);
    }

    // Badge durata (separato, in basso a destra)
    const durationBadge = replay.duration_str ? `<div class="badge-duration">${replay.duration_str}</div>` : '';

    return `
        <div class="video-card" data-path="${replay.path}" data-name="${replay.name}" oncontextmenu="showContextMenu(event, this); return false;">
            <div class="video-thumbnail">
                <img src="/api/thumbnail/${replay.index}?t=${replay.modified}" alt="${replay.name}">
                <video muted loop preload="none">
                    <source src="/api/video/${replay.index}?t=${replay.modified}" type="${replay.mime_type}">
                    <source src="/api/video/${replay.index}?t=${replay.modified}">
                </video>
                ${statusBadge}
                <div class="video-badges">
                    ${badges.join('')}
                </div>
                ${durationBadge}
            </div>

            <div class="video-info">
                <div class="video-name" title="${replay.name}">${replay.name}</div>
                <div class="video-meta">
                    <div>📅 ${replay.timestamp}</div>
                    <div>💾 ${replay.size_str}</div>
                </div>
            </div>

            <div class="video-actions">
                <button class="video-action-btn ${replay.favorite ? 'active' : ''}" onclick="toggleFavorite('${escapedPath}')" title="Preferito">⭐</button>
                <button class="video-action-btn" onclick="loadVideo('${escapedPath}')" title="Carica in OBS">▶️</button>
                <button class="video-action-btn" onclick="addToQueue('${escapedPath}')" title="Aggiungi a coda">📋</button>
            </div>
        </div>
    `;
}

async function toggleFavorite(path) {
    const result = await apiCall('/api/toggle-favorite', 'POST', { path });
    if (result && result.success) {
        await loadReplays();
        showNotification(result.favorite ? 'Aggiunto ai preferiti' : 'Rimosso dai preferiti', 'success');
    }
}

async function addToQueue(path) {
    const result = await apiCall('/api/queue/add', 'POST', { path });
    if (result && result.success) {
        await loadReplays();
        showNotification('Aggiunto alla coda', 'success');
    } else if (result && result.error === 'Already in queue') {
        showNotification('Video già in coda', 'warning');
    }
}

async function loadVideo(path) {
    const result = await apiCall('/api/load', 'POST', { path });
    if (result && result.success) {
        showNotification('Video caricato (pronto per avvio)', 'success');
        // Forza refresh immediato per mostrare badge
        await loadReplays();
    }
}

async function hideVideo(path) {
    if (confirm('Nascondere questo video?')) {
        const result = await apiCall('/api/hide', 'POST', { path });
        if (result && result.success) {
            await loadReplays();
            showNotification('Video nascosto', 'success');
        }
    }
}

async function deleteVideo(path, name) {
    if (confirm(`Eliminare definitivamente "${name}"?`)) {
        const result = await apiCall('/api/delete', 'POST', { path });
        if (result && result.success) {
            await loadReplays();
            showNotification('Video eliminato', 'success');
        }
    }
}

async function setVideoSpeed(path, speed) {
    await loadVideo(path);
    await setGlobalSpeed(speed);
    showNotification(`Video caricato a velocità ${speed}x`, 'success');
}

// ==================== CONTEXT MENU FUNCTIONS ====================
let contextMenuPath = '';

function showContextMenu(event, cardElement) {
    event.preventDefault();
    const videoPath = cardElement.dataset.path;
    contextMenuPath = videoPath;

    const replay = allReplays.find(r => r.path === videoPath);
    if (!replay) return;

    // Escape path per onclick handlers
    const escapedPath = videoPath.replace(/\\\\/g, '\\\\\\\\').replace(/'/g, "\\\\'");

    // Remove existing menu
    const existing = document.getElementById('context-menu');
    if (existing) existing.remove();

    // Create new menu element with modern styling
    const menu = document.createElement('div');
    menu.id = 'context-menu';
    menu.className = 'context-menu visible';

    const isFav = replay.favorite;
    const hasCategory = replay.category && categories[replay.category];

    let html = '';

    // Favorite action
    html += `<div class="context-menu-item ${isFav ? 'active' : ''}" onclick="toggleFavorite('${escapedPath}'); hideContextMenu();">`;
    html += `<span class="menu-icon">${isFav ? '★' : '☆'}</span>`;
    html += `<span>${isFav ? 'Rimuovi da preferiti' : 'Aggiungi a preferiti'}</span>`;
    html += `</div>`;

    // Add to queue
    html += `<div class="context-menu-item" onclick="addToQueue('${escapedPath}'); hideContextMenu();">`;
    html += `<span class="menu-icon">📋</span>`;
    html += `<span>Aggiungi a playlist</span>`;
    html += `</div>`;

    html += `<div class="context-menu-separator"></div>`;

    // Category header
    html += `<div class="context-menu-header">Categoria</div>`;

    // No category option
    const noCategory = !replay.category;
    html += `<div class="context-menu-category ${noCategory ? 'selected' : ''}" onclick="assignCategory('${escapedPath}', null); hideContextMenu();">`;
    html += `<span class="category-dot" style="background: #555;"></span>`;
    html += `<span>Nessuna</span>`;
    if (noCategory) html += `<span class="category-check">✓</span>`;
    html += `</div>`;

    // Category options
    Object.entries(categories).forEach(([name, data]) => {
        const isActive = replay.category === name;
        const color = data.color || data;
        html += `<div class="context-menu-category ${isActive ? 'selected' : ''}" onclick="assignCategory('${escapedPath}', '${name.replace(/'/g, "\\\\'")}'); hideContextMenu();">`;
        html += `<span class="category-dot" style="background: ${color};"></span>`;
        html += `<span>${name}</span>`;
        if (isActive) html += `<span class="category-check">✓</span>`;
        html += `</div>`;
    });

    if (Object.keys(categories).length === 0) {
        html += `<div style="padding: 8px 14px; color: var(--text-secondary); font-size: 12px; font-style: italic;">Nessuna categoria creata</div>`;
    }

    menu.innerHTML = html;
    document.body.appendChild(menu);

    // Smart positioning - calculate best position
    const rect = menu.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const margin = 8;

    let posX = event.clientX;
    let posY = event.clientY;

    // Horizontal positioning - prefer right, flip to left if needed
    if (posX + rect.width + margin > viewportWidth) {
        posX = Math.max(margin, posX - rect.width);
    }

    // Vertical positioning - prefer below, flip above if needed
    if (posY + rect.height + margin > viewportHeight) {
        posY = Math.max(margin, viewportHeight - rect.height - margin);
    }

    menu.style.left = posX + 'px';
    menu.style.top = posY + 'px';

    // Close on click outside
    setTimeout(() => {
        document.addEventListener('click', function closeMenu(e) {
            if (!menu.contains(e.target)) {
                menu.remove();
                document.removeEventListener('click', closeMenu);
            }
        });
    }, 10);
}

function hideContextMenu() {
    const menu = document.getElementById('context-menu');
    if (menu) menu.remove();
    contextMenuPath = '';
}

async function assignCategory(videoPath, categoryName) {
    const result = await apiCall('/api/category/assign', 'POST', {
        path: videoPath,
        category: categoryName
    });

    if (result && result.success) {
        await loadReplays();
        showNotification(categoryName ? `Categoria assegnata: ${categoryName}` : 'Categoria rimossa', 'success');
    }
    hideContextMenu();
}

// ==================== PLAYLIST FUNCTIONS ====================
async function loadPlaylist() {
    const data = await apiCall('/api/queue');
    if (data) {
        playlistQueue = data.queue || [];
        document.getElementById('playlist-count').textContent = playlistQueue.length;

        // Calculate total duration
        let totalSeconds = 0;
        for (const item of playlistQueue) {
            const replay = allReplays.find(r => r.path === item.path);
            if (replay && replay.duration) {
                totalSeconds += replay.duration;
            }
        }

        if (totalSeconds > 0) {
            const mins = Math.floor(totalSeconds / 60);
            const secs = Math.floor(totalSeconds % 60);
            document.getElementById('playlist-duration').textContent = `${mins}:${secs < 10 ? '0' : ''}${secs}`;
        } else {
            document.getElementById('playlist-duration').textContent = '--:--';
        }
    }
}

function renderPlaylist() {
    const container = document.getElementById('playlist-items');
    const emptyState = document.getElementById('playlist-empty');

    if (playlistQueue.length === 0) {
        container.style.display = 'none';
        emptyState.style.display = 'block';
        return;
    }

    container.style.display = 'flex';
    emptyState.style.display = 'none';

    container.innerHTML = playlistQueue.map((item, index) => `
        <div class="playlist-item" draggable="true" data-index="${index}">
            <span class="playlist-item-handle">⋮⋮</span>
            <span class="playlist-item-index">#${index + 1}</span>
            <span class="playlist-item-name">${item.name}</span>
            <div class="playlist-item-controls">
                <button class="playlist-item-control-btn" onclick="moveQueueItemToTop(${index})" title="Sposta in cima">⬆️⬆️</button>
                <button class="playlist-item-control-btn" onclick="moveQueueItemUp(${index})" title="Sposta su">⬆️</button>
                <button class="playlist-item-control-btn" onclick="moveQueueItemDown(${index})" title="Sposta giù">⬇️</button>
                <button class="playlist-item-control-btn" onclick="moveQueueItemToBottom(${index})" title="Sposta in fondo">⬇️⬇️</button>
                <button class="playlist-item-remove" onclick="removeFromPlaylist(${index})">✕</button>
            </div>
        </div>
    `).join('');

    setupPlaylistDragDrop();
}

async function playPlaylist() {
    if (playlistQueue.length === 0) {
        showNotification('Playlist vuota', 'warning');
        return;
    }

    playlistIsPlaying = true;
    currentQueueIndex = 0;
    await playVideoFromQueue(0);
    showNotification('Playlist avviata', 'success');
}

async function playVideoFromQueue(index) {
    if (!playlistIsPlaying) return;

    if (index >= playlistQueue.length) {
        // Fine playlist
        if (playlistLoopEnabled) {
            // Loop: ricomincia da capo
            currentQueueIndex = 0;
            await playVideoFromQueue(0);
        } else {
            // Stop
            stopPlaylist();
            showNotification('Playlist completata', 'success');
        }
        return;
    }

    const video = playlistQueue[index];

    // Carica video in OBS
    await loadVideo(video.path);

    // Mostra "now playing"
    const nowPlaying = document.getElementById('now-playing');
    const nowPlayingTitle = document.getElementById('now-playing-title');
    nowPlaying.classList.add('active');
    nowPlayingTitle.textContent = video.name;

    // Trova durata video
    const replay = allReplays.find(r => r.path === video.path);
    const duration = replay ? replay.duration : 30; // default 30s se non disponibile
    const durationMs = (duration || 30) * 1000;

    console.log(`[PLAYLIST] Playing ${video.name} (${duration}s)`);

    // Schedula prossimo video
    setTimeout(() => {
        if (playlistIsPlaying) {
            currentQueueIndex++;
            playVideoFromQueue(currentQueueIndex);
        }
    }, durationMs);
}

function stopPlaylist() {
    playlistIsPlaying = false;
    const nowPlaying = document.getElementById('now-playing');
    nowPlaying.classList.remove('active');
    showNotification('Playlist fermata', 'info');
}

async function playNextInQueue() {
    // Chiamato quando un video finisce (richiede integrazione OBS)
    const result = await apiCall('/api/queue/play-next', 'POST');
    if (result && result.success) {
        if (result.has_next) {
            await loadReplays();
            const nowPlayingTitle = document.getElementById('now-playing-title');
            if (playlistQueue.length > 0) {
                nowPlayingTitle.textContent = playlistQueue[0].name;
            }
            showNotification('Prossimo video caricato', 'success');
        } else {
            stopPlaylist();
            showNotification('Playlist completata', 'success');
        }
    }
}

function toggleLoop() {
    playlistLoopEnabled = !playlistLoopEnabled;

    const btn = event.target.closest('.playlist-control-btn');
    if (playlistLoopEnabled) {
        btn.classList.add('active');
        btn.style.background = 'var(--accent-primary)';
        btn.style.color = 'white';
        showNotification('Loop playlist attivato', 'success');
    } else {
        btn.classList.remove('active');
        btn.style.background = '';
        btn.style.color = '';
        showNotification('Loop playlist disattivato', 'info');
    }
}

async function shufflePlaylist() {
    if (playlistQueue.length < 2) return;

    // Fisher-Yates shuffle
    for (let i = playlistQueue.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [playlistQueue[i], playlistQueue[j]] = [playlistQueue[j], playlistQueue[i]];
    }

    renderPlaylist();
    showNotification('Playlist mescolata', 'success');
}

async function clearPlaylist() {
    if (confirm('Svuotare la playlist?')) {
        const result = await apiCall('/api/queue/clear', 'POST');
        if (result && result.success) {
            await loadPlaylist();
            renderPlaylist();
            showNotification('Playlist svuotata', 'success');
        }
    }
}

async function removeFromPlaylist(queueIndex) {
    const result = await apiCall('/api/queue/remove', 'POST', { queue_index: queueIndex });
    if (result && result.success) {
        await loadPlaylist();
        await loadReplays(); // Refresh to update queue badges
        renderPlaylist();
        showNotification('Rimosso dalla coda', 'success');
    }
}

async function moveQueueItemToTop(index) {
    if (index <= 0) return;
    const result = await apiCall('/api/queue/move-to-top', 'POST', { index: index });
    if (result && result.success) {
        await loadPlaylist();
        renderPlaylist();
        showNotification('Spostato in cima', 'success');
    }
}

async function moveQueueItemUp(index) {
    if (index <= 0) return;
    const result = await apiCall('/api/queue/reorder', 'POST', { from: index, to: index - 1 });
    if (result && result.success) {
        await loadPlaylist();
        renderPlaylist();
        showNotification('Spostato su', 'success');
    }
}

async function moveQueueItemDown(index) {
    if (index >= playlistQueue.length - 1) return;
    const result = await apiCall('/api/queue/reorder', 'POST', { from: index, to: index + 1 });
    if (result && result.success) {
        await loadPlaylist();
        renderPlaylist();
        showNotification('Spostato giù', 'success');
    }
}

async function moveQueueItemToBottom(index) {
    if (index >= playlistQueue.length - 1) return;
    const result = await apiCall('/api/queue/move-to-bottom', 'POST', { index: index });
    if (result && result.success) {
        await loadPlaylist();
        renderPlaylist();
        showNotification('Spostato in fondo', 'success');
    }
}

async function createHighlightsFromQueue() {
    if (playlistQueue.length === 0) {
        showNotification('Nessun video in coda', 'warning');
        return;
    }

    if (!confirm(`Creare highlights da ${playlistQueue.length} video?`)) {
        return;
    }

    showNotification('Creazione highlights in corso...', 'info');

    const result = await apiCall('/api/create-highlights', 'POST', { use_queue: true });
    if (result && result.success) {
        showNotification(`Highlights creato: ${result.name}`, 'success');

        // Mostra bottone per caricare
        if (confirm('Caricare il video highlights ora?')) {
            await refreshReplays();
            const highlightsVideo = allReplays.find(r => r.name === result.name);
            if (highlightsVideo) {
                await loadVideo(highlightsVideo.path);
            }
        }
    } else {
        showNotification('Errore creazione highlights: ' + (result?.error || 'Unknown'), 'error');
    }
}

// ==================== HIGHLIGHTS FUNCTIONS ====================
async function loadHighlightsList() {
    const result = await apiCall('/api/highlights', 'GET');
    if (result && result.highlights) {
        renderHighlightsList(result.highlights);
    }
}

function renderHighlightsList(highlights) {
    const listContainer = document.getElementById('highlights-list');

    if (highlights.length === 0) {
        listContainer.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">✨</div>
                <div class="empty-state-text">Nessun highlights creato</div>
                <div class="empty-state-subtext">Crea il tuo primo highlights dalla sezione Playlist</div>
            </div>
        `;
        return;
    }

    listContainer.innerHTML = highlights.map(h => `
        <div class="highlight-item" style="
            padding: 15px;
            margin-bottom: 10px;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            display: flex;
            align-items: center;
            gap: 15px;
        ">
            <div style="flex: 1; min-width: 0;">
                <div style="font-weight: 600; margin-bottom: 5px; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                    ${h.name}
                </div>
                <div style="font-size: 12px; color: var(--text-secondary); display: flex; gap: 15px; flex-wrap: wrap;">
                    <span>📅 ${h.created}</span>
                    ${h.duration_str ? `<span>⏱️ ${h.duration_str}</span>` : ''}
                    <span>💾 ${h.size_str}</span>
                </div>
            </div>
            <div style="display: flex; gap: 8px;">
                <button
                    onclick="loadHighlight('${h.path.replace(/'/g, "\\'")}')"
                    style="
                        padding: 8px 16px;
                        background: var(--accent-primary);
                        color: white;
                        border: none;
                        border-radius: 6px;
                        cursor: pointer;
                        font-size: 13px;
                        font-weight: 600;
                        display: flex;
                        align-items: center;
                        gap: 5px;
                    "
                    onmouseover="this.style.opacity='0.9'"
                    onmouseout="this.style.opacity='1'"
                >
                    <span>▶️</span>
                    <span>Carica</span>
                </button>
                <button
                    onclick="deleteHighlight('${h.path.replace(/'/g, "\\'")}')"
                    style="
                        padding: 8px 16px;
                        background: #dc3545;
                        color: white;
                        border: none;
                        border-radius: 6px;
                        cursor: pointer;
                        font-size: 13px;
                        font-weight: 600;
                        display: flex;
                        align-items: center;
                        gap: 5px;
                    "
                    onmouseover="this.style.opacity='0.9'"
                    onmouseout="this.style.opacity='1'"
                >
                    <span>🗑️</span>
                    <span>Elimina</span>
                </button>
            </div>
        </div>
    `).join('');
}

async function loadHighlight(path) {
    const result = await apiCall('/api/highlights/load', 'POST', { path: path });
    if (result && result.success) {
        showNotification('Highlights caricato in OBS', 'success');
        closeHighlightsModal();
    } else {
        showNotification('Errore caricamento highlights: ' + (result?.error || 'Unknown'), 'error');
    }
}

async function deleteHighlight(path) {
    if (!confirm('Eliminare questo highlights?')) {
        return;
    }

    const result = await apiCall('/api/highlights/delete', 'POST', { path: path });
    if (result && result.success) {
        showNotification('Highlights eliminato', 'success');
        await loadHighlightsList();
    } else {
        showNotification('Errore eliminazione highlights: ' + (result?.error || 'Unknown'), 'error');
    }
}

function setupPlaylistDragDrop() {
    const items = document.querySelectorAll('.playlist-item');

    items.forEach(item => {
        item.addEventListener('dragstart', handleDragStart);
        item.addEventListener('dragover', handleDragOver);
        item.addEventListener('drop', handleDrop);
        item.addEventListener('dragend', handleDragEnd);
    });
}

function handleDragStart(e) {
    draggedItem = this;
    this.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
}

function handleDragOver(e) {
    if (e.preventDefault) {
        e.preventDefault();
    }
    e.dataTransfer.dropEffect = 'move';
    return false;
}

async function handleDrop(e) {
    if (e.stopPropagation) {
        e.stopPropagation();
    }

    if (draggedItem !== this) {
        const fromIndex = parseInt(draggedItem.dataset.index);
        const toIndex = parseInt(this.dataset.index);

        const result = await apiCall('/api/queue/reorder', 'POST', {
            from: fromIndex,
            to: toIndex
        });

        if (result && result.success) {
            await loadPlaylist();
            renderPlaylist();
        }
    }

    return false;
}

function handleDragEnd(e) {
    this.classList.remove('dragging');
}

// ==================== SETTINGS FUNCTIONS ====================
function switchSettingsTab(tabName) {
    // Hide all panels
    document.querySelectorAll('.settings-panel').forEach(panel => {
        panel.classList.remove('active');
    });

    // Remove active from all tab buttons
    document.querySelectorAll('.settings-tab').forEach(tab => {
        tab.classList.remove('active');
    });

    // Show selected panel
    const panel = document.getElementById(`panel-${tabName}`);
    if (panel) {
        panel.classList.add('active');
    }

    // Find and activate the correct tab button
    document.querySelectorAll('.settings-tab').forEach(tab => {
        if (tab.getAttribute('onclick')?.includes(`'${tabName}'`)) {
            tab.classList.add('active');
        }
    });
}

async function loadCategories() {
    const data = await apiCall('/api/categories');
    if (data) {
        categories = {};
        (data.categories || []).forEach(cat => {
            categories[cat.name] = {
                color: cat.color,
                count: cat.count
            };
        });
        renderCategories();
        updateCategoryFilter();
    }
}

function renderCategories() {
    const list = document.getElementById('category-list');

    if (Object.keys(categories).length === 0) {
        list.innerHTML = '<div class="empty-state-text">Nessuna categoria</div>';
        return;
    }

    list.innerHTML = Object.entries(categories).map(([name, data]) => `
        <div class="category-item" oncontextmenu="showCategoryContextMenu(event, '${name.replace(/'/g, "\\'")}', '${data.color}')">
            <div class="category-color" style="background-color: ${data.color};" title="Tasto destro per cambiare colore"></div>
            <div class="category-name">${name}</div>
            <div class="category-count">${data.count} video</div>
            <button class="category-delete-btn" onclick="deleteCategory('${name.replace(/'/g, "\\'")}')">✕</button>
        </div>
    `).join('');
}

// Context menu per categorie (tasto destro)
function showCategoryContextMenu(event, categoryName, currentColor) {
    event.preventDefault();

    // Rimuovi menu esistente
    const existing = document.getElementById('category-context-menu');
    if (existing) existing.remove();

    const menu = document.createElement('div');
    menu.id = 'category-context-menu';
    menu.className = 'context-menu visible';

    let html = `
        <div class="context-menu-header">${categoryName}</div>
        <div class="context-menu-item" onclick="renameCategory('${categoryName.replace(/'/g, "\\'")}'); hideCategoryContextMenu();">
            <span class="menu-icon">✏️</span>
            <span>Rinomina</span>
        </div>
        <div class="context-menu-separator"></div>
        <div class="context-menu-header">Cambia colore</div>
        <div class="color-picker-grid">
    `;

    const colors = ['#e74c3c', '#e67e22', '#f1c40f', '#2ecc71', '#1abc9c', '#3498db', '#9b59b6', '#e91e63', '#607d8b'];
    colors.forEach(color => {
        const selected = color === currentColor ? 'selected' : '';
        html += `<div class="color-preset ${selected}" style="background:${color};" onclick="changeCategoryColor('${categoryName.replace(/'/g, "\\'")}', '${color}'); hideCategoryContextMenu();"></div>`;
    });

    html += `
        </div>
        <div class="context-menu-separator"></div>
        <div class="context-menu-item danger" onclick="deleteCategory('${categoryName.replace(/'/g, "\\'")}'); hideCategoryContextMenu();">
            <span class="menu-icon">🗑️</span>
            <span>Elimina</span>
        </div>
    `;

    menu.innerHTML = html;
    document.body.appendChild(menu);

    // Posizionamento
    const rect = menu.getBoundingClientRect();
    let posX = event.clientX;
    let posY = event.clientY;

    if (posX + rect.width + 8 > window.innerWidth) {
        posX = Math.max(8, posX - rect.width);
    }
    if (posY + rect.height + 8 > window.innerHeight) {
        posY = Math.max(8, window.innerHeight - rect.height - 8);
    }

    menu.style.left = posX + 'px';
    menu.style.top = posY + 'px';

    // Chiudi al click fuori
    setTimeout(() => {
        document.addEventListener('click', function closeMenu(e) {
            if (!menu.contains(e.target)) {
                menu.remove();
                document.removeEventListener('click', closeMenu);
            }
        });
    }, 10);
}

function hideCategoryContextMenu() {
    const menu = document.getElementById('category-context-menu');
    if (menu) menu.remove();
}

function updateCategoryFilter() {
    const menu = document.getElementById('category-dropdown-menu');
    const filterText = document.getElementById('category-filter-text');
    if (!menu) return;

    const totalVideos = allReplays.length;
    let html = '';

    // All categories option
    const allSelected = !currentFilter.category;
    html += `<div class="filter-dropdown-item ${allSelected ? 'selected' : ''}" onclick="selectCategory(null); event.stopPropagation();">
        <span class="item-checkbox"></span>
        <span class="item-color" style="background:#666;"></span>
        <span class="item-name">Tutte le categorie</span>
        <span class="item-count">${totalVideos}</span>
    </div>`;

    // Category options
    Object.entries(categories).forEach(([name, data]) => {
        const isSelected = currentFilter.category === name;
        html += `<div class="filter-dropdown-item ${isSelected ? 'selected' : ''}" onclick="selectCategory('${name.replace(/'/g, "\\'")}'); event.stopPropagation();">
            <span class="item-checkbox"></span>
            <span class="item-color" style="background:${data.color};"></span>
            <span class="item-name">${name}</span>
            <span class="item-count">${data.count}</span>
        </div>`;
    });

    menu.innerHTML = html;

    // Update trigger text
    if (filterText) {
        if (currentFilter.category) {
            filterText.textContent = currentFilter.category;
        } else {
            filterText.textContent = 'Categorie';
        }
    }
}

function toggleCategoryDropdown() {
    const container = document.getElementById('category-dropdown');
    container.classList.toggle('open');
}

function selectCategory(category) {
    currentFilter.category = category;
    document.getElementById('category-dropdown').classList.remove('open');
    updateCategoryFilter();
    filterVideos();
}

// Close dropdown when clicking outside
document.addEventListener('click', (e) => {
    const dropdown = document.getElementById('category-dropdown');
    if (dropdown && !dropdown.contains(e.target)) {
        dropdown.classList.remove('open');
    }
});

// Funzione per selezionare un colore preset
function selectPresetColor(el) {
    document.querySelectorAll('.color-preset').forEach(p => p.classList.remove('selected'));
    el.classList.add('selected');
}

// Funzione per ottenere il colore preset selezionato
function getSelectedPresetColor() {
    const selected = document.querySelector('.color-preset.selected');
    return selected ? selected.dataset.color : '#e74c3c';
}

async function addCategory() {
    const nameInput = document.getElementById('new-category-name');
    const name = nameInput.value.trim();
    const color = getSelectedPresetColor();

    if (!name) {
        showNotification('Inserisci un nome per la categoria', 'warning');
        return;
    }

    const result = await apiCall('/api/category/create', 'POST', { name, color });

    if (result && result.success) {
        nameInput.value = '';
        await loadCategories();
        showNotification('Categoria creata', 'success');
    } else {
        showNotification('Errore: nome duplicato o non valido', 'error');
    }
}

// Funzione per rinominare una categoria
async function renameCategory(oldName) {
    const newName = prompt('Nuovo nome per la categoria:', oldName);
    if (newName && newName.trim() && newName.trim() !== oldName) {
        const result = await apiCall('/api/category/rename', 'POST', {
            old_name: oldName,
            new_name: newName.trim()
        });
        if (result && result.success) {
            await loadCategories();
            await loadReplays();
            showNotification('Categoria rinominata', 'success');
        } else {
            showNotification(result?.error || 'Errore nella rinomina', 'error');
        }
    }
}

// Funzione per cambiare colore di una categoria
async function changeCategoryColor(name, newColor) {
    const result = await apiCall('/api/category/update-color', 'POST', {
        name: name,
        color: newColor
    });
    if (result && result.success) {
        await loadCategories();
        await loadReplays();
        showNotification('Colore aggiornato', 'success');
    } else {
        showNotification('Errore aggiornamento colore', 'error');
    }
}

// Mostra il picker colori inline per una categoria esistente
function showColorPickerForCategory(name, currentColor, btn) {
    // Rimuovi eventuali picker aperti
    document.querySelectorAll('.inline-color-picker').forEach(p => p.remove());

    const picker = document.createElement('div');
    picker.className = 'inline-color-picker';
    picker.innerHTML = `
        <div class="color-preset ${currentColor === '#e74c3c' ? 'selected' : ''}" data-color="#e74c3c" style="background:#e74c3c;"></div>
        <div class="color-preset ${currentColor === '#e67e22' ? 'selected' : ''}" data-color="#e67e22" style="background:#e67e22;"></div>
        <div class="color-preset ${currentColor === '#f1c40f' ? 'selected' : ''}" data-color="#f1c40f" style="background:#f1c40f;"></div>
        <div class="color-preset ${currentColor === '#2ecc71' ? 'selected' : ''}" data-color="#2ecc71" style="background:#2ecc71;"></div>
        <div class="color-preset ${currentColor === '#1abc9c' ? 'selected' : ''}" data-color="#1abc9c" style="background:#1abc9c;"></div>
        <div class="color-preset ${currentColor === '#3498db' ? 'selected' : ''}" data-color="#3498db" style="background:#3498db;"></div>
        <div class="color-preset ${currentColor === '#9b59b6' ? 'selected' : ''}" data-color="#9b59b6" style="background:#9b59b6;"></div>
        <div class="color-preset ${currentColor === '#e91e63' ? 'selected' : ''}" data-color="#e91e63" style="background:#e91e63;"></div>
        <div class="color-preset ${currentColor === '#607d8b' ? 'selected' : ''}" data-color="#607d8b" style="background:#607d8b;"></div>
    `;

    picker.querySelectorAll('.color-preset').forEach(p => {
        p.onclick = async (e) => {
            e.stopPropagation();
            const color = p.dataset.color;
            picker.remove();
            await changeCategoryColor(name, color);
        };
    });

    btn.parentElement.appendChild(picker);

    // Chiudi picker cliccando fuori
    setTimeout(() => {
        document.addEventListener('click', function closePicker(e) {
            if (!picker.contains(e.target)) {
                picker.remove();
                document.removeEventListener('click', closePicker);
            }
        });
    }, 10);
}

async function deleteCategory(name) {
    if (confirm(`Eliminare la categoria "${name}"?`)) {
        const result = await apiCall('/api/category/delete', 'POST', { name });
        if (result && result.success) {
            await loadCategories();
            await loadReplays();
            showNotification('Categoria eliminata', 'success');
        }
    }
}

async function loadVersion() {
    const data = await apiCall('/api/version');
    if (data) {
        document.getElementById('current-version').textContent = data.version;
    }
}

async function checkForUpdates() {
    const btn = document.getElementById('check-updates-btn');
    const status = document.getElementById('update-status');
    const updateInfo = document.getElementById('update-info');

    btn.disabled = true;
    btn.innerHTML = '<span>⏳</span><span>Verificando...</span>';
    status.textContent = 'Verifica in corso...';

    const data = await apiCall('/api/check-updates');

    btn.disabled = false;
    btn.innerHTML = '<span>🔄</span><span>Verifica aggiornamenti</span>';

    if (!data || !data.success) {
        status.textContent = data?.error || 'Errore durante la verifica';
        updateInfo.style.display = 'none';
        showNotification('Errore verifica aggiornamenti', 'error');
        return;
    }

    document.getElementById('current-version').textContent = data.current_version;

    if (data.update_available) {
        status.textContent = 'Aggiornamento disponibile!';
        status.style.color = 'var(--accent-success)';
        updateInfo.style.display = 'block';
        document.getElementById('new-version').textContent = data.latest_version;
        document.getElementById('release-link').href = data.release_url;
        document.getElementById('release-notes').textContent = data.release_notes || 'Nessuna nota di rilascio';

        // Mostra badge pre-release se applicabile
        const prereleaseBadge = document.getElementById('prerelease-badge');
        if (prereleaseBadge) {
            prereleaseBadge.style.display = data.is_prerelease ? 'inline' : 'none';
        }

        // Mostra pulsanti per scaricare gli asset
        const assetsContainer = document.getElementById('update-assets');
        assetsContainer.innerHTML = '';

        if (data.assets && data.assets.length > 0) {
            // Pulsante per installare tutti i file
            if (data.assets.length > 1) {
                const btnAll = document.createElement('button');
                btnAll.className = 'header-btn primary';
                btnAll.innerHTML = `<span>⬇️</span><span>Installa tutto</span>`;
                btnAll.onclick = () => installAllUpdates(data.assets);
                assetsContainer.appendChild(btnAll);
            }

            // Pulsanti singoli per ogni file
            data.assets.forEach(asset => {
                if (asset.name.endsWith('.py')) {
                    const btn = document.createElement('button');
                    btn.className = 'header-btn';
                    btn.innerHTML = `<span>📥</span><span>${asset.name}</span>`;
                    btn.onclick = () => installUpdate(asset.download_url, asset.name);
                    assetsContainer.appendChild(btn);
                }
            });
        }

        showNotification(`Nuova versione disponibile: ${data.latest_version}`, 'success');
    } else {
        status.textContent = `Hai l'ultima versione (${data.current_version})`;
        status.style.color = 'var(--text-secondary)';
        updateInfo.style.display = 'none';
        showNotification('Sei già aggiornato!', 'success');
    }
}

async function setUpdateChannel(channel) {
    const result = await apiCall('/api/update-channel', 'POST', { channel });
    if (result && result.success) {
        // Aggiorna UI pulsanti canale
        document.querySelectorAll('.channel-btn').forEach(btn => btn.classList.remove('active'));
        document.getElementById(`channel-${channel}`).classList.add('active');

        const channelName = channel === 'beta' ? 'Beta (include pre-release)' : 'Stabile';
        showNotification(`Canale aggiornamenti: ${channelName}`, 'success');
    }
}

function updateChannelUI(channel) {
    document.querySelectorAll('.channel-btn').forEach(btn => btn.classList.remove('active'));
    const btn = document.getElementById(`channel-${channel}`);
    if (btn) btn.classList.add('active');
}

async function installUpdate(url, name) {
    if (!confirm(`Vuoi installare l'aggiornamento per ${name}?\n\nOBS Studio dovrà essere riavviato dopo l'installazione.`)) {
        return;
    }

    showNotification(`Scaricamento ${name}...`, 'info');

    const result = await apiCall('/api/install-update', 'POST', { url, name });

    if (result && result.success) {
        showNotification(result.message, 'success');
        alert(`${name} aggiornato con successo!\n\nRiavvia OBS Studio per applicare le modifiche.`);
    } else {
        showNotification(`Errore: ${result?.error || 'Sconosciuto'}`, 'error');
    }
}

async function installAllUpdates(assets) {
    if (!confirm(`Vuoi installare tutti gli aggiornamenti (${assets.length} file)?\n\nOBS Studio dovrà essere riavviato dopo l'installazione.`)) {
        return;
    }

    let successCount = 0;
    let errorCount = 0;

    for (const asset of assets) {
        if (asset.name.endsWith('.py')) {
            showNotification(`Scaricamento ${asset.name}...`, 'info');
            const result = await apiCall('/api/install-update', 'POST', {
                url: asset.download_url,
                name: asset.name
            });

            if (result && result.success) {
                successCount++;
            } else {
                errorCount++;
                showNotification(`Errore: ${asset.name} - ${result?.error || 'Sconosciuto'}`, 'error');
            }
        }
    }

    if (errorCount === 0) {
        showNotification(`Tutti i file (${successCount}) aggiornati con successo!`, 'success');
        alert(`Aggiornamento completato!\n\n${successCount} file aggiornati.\n\nRiavvia OBS Studio per applicare le modifiche.`);
    } else {
        showNotification(`Aggiornamento parziale: ${successCount} OK, ${errorCount} errori`, 'warning');
        alert(`Aggiornamento parziale.\n\n${successCount} file aggiornati, ${errorCount} errori.\n\nRiavvia OBS Studio per applicare le modifiche.`);
    }
}

async function setTheme(theme) {
    currentTheme = theme;
    document.body.setAttribute('data-theme', theme);

    // Update theme selector
    document.querySelectorAll('.theme-option').forEach(option => {
        option.classList.remove('active');
        if (option.dataset.theme === theme) {
            option.classList.add('active');
        }
    });

    // Save to server
    await apiCall('/api/theme', 'POST', { theme });
    showNotification(`Tema cambiato: ${theme}`, 'success');
}

async function openFolder() {
    await apiCall('/api/open-folder', 'POST');
    showNotification('Apertura cartella...', 'info');
}

// ==================== HIDDEN VIDEOS FUNCTIONS ====================
async function loadHiddenVideos() {
    const data = await apiCall('/api/hidden');
    if (data) {
        hiddenVideos = data.hidden || [];
    }
}

function renderHiddenVideos() {
    const list = document.getElementById('hidden-list');
    const emptyState = document.getElementById('hidden-empty');

    if (hiddenVideos.length === 0) {
        list.style.display = 'none';
        emptyState.style.display = 'block';
        return;
    }

    list.style.display = 'flex';
    emptyState.style.display = 'none';

    list.innerHTML = hiddenVideos.map(video => `
        <div class="hidden-item">
            <div class="hidden-item-name">${video.name}</div>
            <div class="hidden-item-actions">
                <button class="hidden-item-btn" onclick="unhideVideo('${video.path}')">Mostra</button>
            </div>
        </div>
    `).join('');
}

async function unhideVideo(path) {
    const result = await apiCall('/api/unhide', 'POST', { path });
    if (result && result.success) {
        await loadHiddenVideos();
        await loadReplays();
        renderHiddenVideos();
        showNotification('Video ripristinato', 'success');
    }
}

async function unhideAll() {
    if (confirm('Mostrare tutti i video nascosti?')) {
        const result = await apiCall('/api/unhide-all', 'POST');
        if (result && result.success) {
            await loadHiddenVideos();
            await loadReplays();
            renderHiddenVideos();
            showNotification('Tutti i video ripristinati', 'success');
        }
    }
}

// ==================== SPEED & ZOOM FUNCTIONS ====================
async function setGlobalSpeed(speed) {
    currentSpeed = speed;

    // Update button states
    document.querySelectorAll('.speed-button').forEach(btn => {
        btn.classList.remove('active');
        if (parseFloat(btn.dataset.speed) === speed) {
            btn.classList.add('active');
        }
    });

    // Update display
    updateSpeedDisplay();

    // Save to server
    await apiCall('/api/speed', 'POST', { speed });
}

function updateSpeedDisplay() {
    document.getElementById('current-speed-display').textContent = currentSpeed.toFixed(1) + 'x';
}

function setZoom(zoom) {
    cardZoom = parseInt(zoom);

    // Applica direttamente al grid
    const grid = document.getElementById('video-grid');
    if (grid) {
        grid.style.gridTemplateColumns = `repeat(auto-fill, minmax(${cardZoom}px, 1fr))`;
    }

    // Aggiorna anche la variabile CSS per compatibilità
    document.documentElement.style.setProperty('--card-width', cardZoom + 'px');

    // Save to server
    apiCall('/api/zoom', 'POST', { zoom: cardZoom });
}

function adjustZoom(delta) {
    const slider = document.getElementById('zoom-slider');
    const newZoom = Math.max(120, Math.min(320, cardZoom + delta));
    slider.value = newZoom;
    setZoom(newZoom);
}

// ==================== UTILITY FUNCTIONS ====================
function formatFileSize(bytes) {
    const mb = bytes / (1024 * 1024);
    if (mb < 1024) {
        return mb.toFixed(1) + ' MB';
    }
    return (mb / 1024).toFixed(2) + ' GB';
}

function formatDuration(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return mins + ':' + (secs < 10 ? '0' : '') + secs;
}

let notificationTimeout = null;

function showNotification(message, type = 'info') {
    console.log(`[${type.toUpperCase()}] ${message}`);

    // Create notification element if it doesn't exist
    let notif = document.getElementById('app-notification');
    if (!notif) {
        notif = document.createElement('div');
        notif.id = 'app-notification';
        notif.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            box-shadow: 0 4px 12px var(--shadow);
            z-index: 10000;
            min-width: 250px;
            display: none;
            animation: slideUp 0.3s ease;
        `;
        document.body.appendChild(notif);
    }

    // Color based on type
    const colors = {
        success: 'var(--accent-success)',
        error: 'var(--accent-danger)',
        warning: 'var(--accent-warning)',
        info: 'var(--accent-primary)'
    };

    notif.style.borderLeftColor = colors[type] || colors.info;
    notif.style.borderLeftWidth = '4px';
    notif.textContent = message;
    notif.style.display = 'block';

    // Auto hide after 3 seconds
    if (notificationTimeout) clearTimeout(notificationTimeout);
    notificationTimeout = setTimeout(() => {
        notif.style.display = 'none';
    }, 3000);
}

// ==================== VIDEO HOVER PREVIEW ====================
document.addEventListener('DOMContentLoaded', () => {
    init();

    // Setup hover video preview
    document.addEventListener('mouseover', (e) => {
        const card = e.target.closest('.video-card');
        if (card) {
            const video = card.querySelector('video');
            if (video && video.paused) {
                video.play().catch(() => {});
            }
        }
    });

    document.addEventListener('mouseout', (e) => {
        const card = e.target.closest('.video-card');
        if (card) {
            const video = card.querySelector('video');
            if (video && !video.paused) {
                video.pause();
                video.currentTime = 0;
            }
        }
    });

    // Close modals on background click
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('active');
            }
        });
    });
});
</script>

</body>
</html>"""


server_thread = None
server_instance = None

def start_server(port=None):
    global server_thread, server_instance, SERVER_PORT
    if port: SERVER_PORT = port
    if server_thread and server_thread.is_alive():
        return True

    # Inizializza persistenza dati
    init_data_file()

    try:
        server_instance = HTTPServer(('localhost', SERVER_PORT), ReplayAPIHandler)
        server_thread = threading.Thread(target=server_instance.serve_forever, daemon=True)
        server_thread.start()
        print(f"✓ Server HTTP v4 avviato su http://localhost:{SERVER_PORT}")
        return True
    except Exception as e:
        print(f"✗ Errore server: {e}")
        return False

def stop_server():
    global server_instance, server_thread
    if server_instance:
        try:
            print("[SERVER] Arresto server in corso...")

            # Salva dati prima di chiudere
            save_persistent_data()

            # Crea un thread separato per lo shutdown per evitare deadlock
            def shutdown_thread():
                try:
                    server_instance.shutdown()
                except:
                    pass

            shutdown = threading.Thread(target=shutdown_thread, daemon=True)
            shutdown.start()
            shutdown.join(timeout=1.0)

            # Chiudi il server
            try:
                server_instance.server_close()
            except:
                pass

            # Aspetta che il thread del server termini
            if server_thread and server_thread.is_alive():
                server_thread.join(timeout=1.0)

            server_instance = None
            server_thread = None
            print("✓ Server fermato correttamente")
        except Exception as e:
            print(f"⚠ Errore durante arresto server: {e}")

def update_settings(folder, source, scene, auto_switch):
    global replay_folder, media_source_name, target_scene_name, auto_switch_scene
    replay_folder = folder
    media_source_name = source
    target_scene_name = scene
    auto_switch_scene = auto_switch

def get_pending_action():
    try:
        return action_queue.get_nowait()
    except:
        return None
