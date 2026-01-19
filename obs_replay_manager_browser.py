"""
OBS Replay Manager - Browser Dock Edition
Plugin che usa Custom Browser Dock per l'interfaccia
NON richiede PyQt5 - Usa tecnologie web standard
"""

import obspython as obs
import os
import sys
import threading
import time

# Importa il server HTTP
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

try:
    import replay_http_server as server
    SERVER_AVAILABLE = True
    SERVER_VERSION = "1.0-beta4"
except ImportError as e:
    SERVER_AVAILABLE = False
    SERVER_VERSION = None
    print(f"✗ Impossibile importare replay_http_server: {e}")

# Variabili globali
server_port = 8765


def load_replay_to_source(file_path, speed=None):
    """Carica un replay nella fonte multimediale SENZA avviare la riproduzione.

    Args:
        file_path: Percorso del file video
        speed: Velocità di riproduzione (0.1-2.0), None usa quella corrente dal server

    Il video viene caricato ma NON parte automaticamente.
    L'utente deve avviare manualmente la riproduzione (Stream Deck, hotkey, controlli OBS).
    """
    if not SERVER_AVAILABLE:
        return False

    media_source_name = server.media_source_name
    target_scene_name = server.target_scene_name
    auto_switch_scene = server.auto_switch_scene

    # Usa la velocità passata o quella corrente dal server
    playback_speed = speed if speed is not None else getattr(server, 'current_speed', 1.0)

    if not media_source_name or not target_scene_name:
        print("⚠ Nome fonte o scena non configurati")
        return False

    # Trova la sorgente direttamente per nome (più semplice e affidabile)
    source = obs.obs_get_source_by_name(media_source_name)

    if not source:
        print(f"⚠ Sorgente '{media_source_name}' non trovata")
        return False

    # Aggiorna le impostazioni della sorgente
    settings = obs.obs_data_create()
    obs.obs_data_set_string(settings, "local_file", file_path)
    obs.obs_data_set_bool(settings, "is_local_file", True)

    # Imposta la velocità di riproduzione (speed_percent: 100 = 1x, 50 = 0.5x, 200 = 2x)
    speed_percent = max(10, min(int(playback_speed * 100), 200))
    obs.obs_data_set_int(settings, "speed_percent", speed_percent)

    # Aggiorna la sorgente (questo può causare auto-play se la sorgente è attiva)
    obs.obs_source_update(source, settings)
    obs.obs_data_release(settings)

    # FERMA IMMEDIATAMENTE la riproduzione dopo l'update
    # Questo garantisce che il video sia caricato ma non in play
    obs.obs_source_media_stop(source)

    # Rilascia il riferimento alla sorgente
    obs.obs_source_release(source)

    # Cambia scena se richiesto
    if auto_switch_scene:
        scenes = obs.obs_frontend_get_scenes()
        for scene_source in scenes:
            if obs.obs_source_get_name(scene_source) == target_scene_name:
                obs.obs_frontend_set_current_scene(scene_source)
                break
        obs.source_list_release(scenes)

    speed_str = f" @ {playback_speed}x" if playback_speed != 1.0 else ""
    print(f"✓ Replay caricato: {os.path.basename(file_path)}{speed_str}")
    return True


def set_media_speed(speed):
    """Imposta la velocità di riproduzione della media source corrente"""
    if not SERVER_AVAILABLE:
        return False

    media_source_name = server.media_source_name
    target_scene_name = server.target_scene_name

    if not media_source_name or not target_scene_name:
        return False

    scenes = obs.obs_frontend_get_scenes()
    for scene_source in scenes:
        if obs.obs_source_get_name(scene_source) == target_scene_name:
            target_scene = obs.obs_scene_from_source(scene_source)
            scene_item = obs.obs_scene_find_source(target_scene, media_source_name)

            if scene_item:
                source = obs.obs_sceneitem_get_source(scene_item)
                if source:
                    settings = obs.obs_data_create()
                    speed_percent = int(speed * 100)
                    obs.obs_data_set_int(settings, "speed_percent", speed_percent)
                    obs.obs_source_update(source, settings)
                    obs.obs_data_release(settings)
                    obs.source_list_release(scenes)
                    print(f"✓ Velocità impostata: {speed}x")
                    return True
            break
    obs.source_list_release(scenes)
    return False


def open_replay_folder():
    """Apri cartella replay"""
    if not SERVER_AVAILABLE:
        return

    replay_folder = server.replay_folder

    if not replay_folder or not os.path.exists(replay_folder):
        return

    try:
        import subprocess
        import platform

        if platform.system() == 'Windows':
            os.startfile(replay_folder)
        elif platform.system() == 'Darwin':
            subprocess.Popen(['open', replay_folder])
        else:
            subprocess.Popen(['xdg-open', replay_folder])
    except Exception as e:
        print(f"Errore apertura cartella: {e}")


def check_and_handle_actions():
    """Controlla periodicamente se ci sono azioni da eseguire dal pannello web"""
    if not SERVER_AVAILABLE or not server.replay_files:
        return
    
    # Questo verrà chiamato periodicamente dal timer
    # In futuro si possono gestire azioni dalla web UI
    pass


# ===== FUNZIONI OBS =====

def script_description():
    if SERVER_AVAILABLE:
        return f"""<center><h2>OBS Instant Replay</h2></center>
        <p style='color: green;'><b>✓ Server attivo</b> (v{SERVER_VERSION})</p>
        <hr>
        <p><b>URL Pannello:</b></p>
        <p style='background: #333; padding: 8px; border-radius: 4px; font-family: monospace;'>
        http://localhost:{server_port}
        </p>
        <p style='font-size: 11px; color: #888; margin-top: 8px;'>
        Vai su <b>Pannelli → Custom Browser Docks</b> e aggiungi questo URL.
        </p>
        """
    else:
        return """<center><h2>OBS Instant Replay</h2></center>
        <p style='color: red;'><b>✗ Server non disponibile</b></p>
        <p>Assicurati che <code>replay_http_server.py</code> sia nella stessa cartella.</p>
        """


def script_properties():
    props = obs.obs_properties_create()

    obs.obs_properties_add_int(
        props, "server_port",
        "Porta Server",
        1024, 65535, 1
    )

    obs.obs_properties_add_text(
        props, "info_note",
        "Le altre impostazioni sono disponibili nel pannello web.",
        obs.OBS_TEXT_INFO
    )

    return props


def script_defaults(settings):
    obs.obs_data_set_default_int(settings, "server_port", 8765)


def script_update(settings):
    global server_port

    server_port = obs.obs_data_get_int(settings, "server_port")

    if SERVER_AVAILABLE:
        # Legge le impostazioni dal file di dati persistente
        server.load_persistent_data()
        server.scan_replay_folder()


def script_load(settings):
    global hotkey_id_load_latest, hotkey_id_load_second
    global hotkey_id_play_pause, hotkey_id_play_next, hotkey_id_open_folder

    print("\n" + "=" * 70)
    print("🎬 OBS Replay Manager - Browser Dock Edition")
    print("=" * 70)

    if not SERVER_AVAILABLE:
        print("✗ Server HTTP non disponibile")
        print("  Assicurati che replay_http_server.py sia nella stessa cartella")
        print("=" * 70 + "\n")
        return

    print(f"✓ Server HTTP disponibile ({SERVER_VERSION})")

    # Avvia server HTTP
    if server.start_server(server_port):
        print(f"✓ Server avviato su http://localhost:{server_port}")
        print(f"📌 URL pannello: http://localhost:{server_port}")
    else:
        print(f"✗ Impossibile avviare server sulla porta {server_port}")
        print(f"   Prova a cambiare la porta nelle impostazioni")

    print("=" * 70 + "\n")

    # Hotkeys - Caricamento replay
    hotkey_id_load_latest = obs.obs_hotkey_register_frontend(
        "replay_manager.load_latest",
        "Replay: Carica Ultimo",
        lambda pressed: load_latest_hotkey(pressed)
    )

    hotkey_id_load_second = obs.obs_hotkey_register_frontend(
        "replay_manager.load_second",
        "Replay: Carica Penultimo",
        lambda pressed: load_second_hotkey(pressed)
    )

    # Hotkeys - Controlli riproduzione
    hotkey_id_play_pause = obs.obs_hotkey_register_frontend(
        "replay_manager.play_pause",
        "Replay: Play/Pausa",
        lambda pressed: play_pause_hotkey(pressed)
    )

    hotkey_id_play_next = obs.obs_hotkey_register_frontend(
        "replay_manager.play_next",
        "Replay: Prossimo in Playlist",
        lambda pressed: play_next_hotkey(pressed)
    )

    # Hotkeys - Utilità
    hotkey_id_open_folder = obs.obs_hotkey_register_frontend(
        "replay_manager.open_folder",
        "Replay: Apri Cartella",
        lambda pressed: open_folder_hotkey(pressed)
    )

    # Carica hotkey salvate
    hotkey_save_array_latest = obs.obs_data_get_array(settings, "load_latest_hotkey")
    obs.obs_hotkey_load(hotkey_id_load_latest, hotkey_save_array_latest)
    obs.obs_data_array_release(hotkey_save_array_latest)

    hotkey_save_array_second = obs.obs_data_get_array(settings, "load_second_hotkey")
    obs.obs_hotkey_load(hotkey_id_load_second, hotkey_save_array_second)
    obs.obs_data_array_release(hotkey_save_array_second)

    hotkey_save_array_play_pause = obs.obs_data_get_array(settings, "play_pause_hotkey")
    obs.obs_hotkey_load(hotkey_id_play_pause, hotkey_save_array_play_pause)
    obs.obs_data_array_release(hotkey_save_array_play_pause)

    hotkey_save_array_play_next = obs.obs_data_get_array(settings, "play_next_hotkey")
    obs.obs_hotkey_load(hotkey_id_play_next, hotkey_save_array_play_next)
    obs.obs_data_array_release(hotkey_save_array_play_next)

    hotkey_save_array_open_folder = obs.obs_data_get_array(settings, "open_folder_hotkey")
    obs.obs_hotkey_load(hotkey_id_open_folder, hotkey_save_array_open_folder)
    obs.obs_data_array_release(hotkey_save_array_open_folder)

    # Timer per controllare azioni (ogni 500ms per reattività)
    obs.timer_add(check_actions_timer, 500)


def check_actions_timer():
    """Timer che controlla se ci sono azioni da eseguire"""
    if not SERVER_AVAILABLE:
        return

    media_source_name = server.media_source_name
    target_scene_name = server.target_scene_name

    # Controlla lo stato della media source
    try:
        if media_source_name and target_scene_name and (server.current_playing_video or server.current_ready_video):
            scenes = obs.obs_frontend_get_scenes()
            for scene_source in scenes:
                if obs.obs_source_get_name(scene_source) == target_scene_name:
                    target_scene = obs.obs_scene_from_source(scene_source)
                    scene_item = obs.obs_scene_find_source(target_scene, media_source_name)

                    if scene_item:
                        source = obs.obs_sceneitem_get_source(scene_item)
                        if source:
                            # Controlla lo stato della media source
                            media_state = obs.obs_source_media_get_state(source)
                            # OBS_MEDIA_STATE_STOPPED = 1, OBS_MEDIA_STATE_PLAYING = 2, OBS_MEDIA_STATE_ENDED = 5

                            if media_state == 5:  # ENDED
                                # Riproduzione terminata
                                server.current_playing_video = None
                                server.current_ready_video = None
                            elif media_state == 2 and server.current_ready_video:  # PLAYING
                                # Video READY è stato avviato manualmente
                                # In Studio Mode, verifica se la scena è in Program prima di passare a LIVE
                                studio_mode_active = obs.obs_frontend_preview_program_mode_active()
                                if studio_mode_active:
                                    # Ottieni la scena corrente in Program
                                    program_scene_source = obs.obs_frontend_get_current_scene()
                                    if program_scene_source:
                                        program_scene_name = obs.obs_source_get_name(program_scene_source)
                                        obs.obs_source_release(program_scene_source)
                                        # Solo se la scena è in Program, passa a LIVE
                                        if program_scene_name == target_scene_name:
                                            server.current_playing_video = server.current_ready_video
                                            server.current_ready_video = None
                                else:
                                    # Senza Studio Mode, passa subito a LIVE
                                    server.current_playing_video = server.current_ready_video
                                    server.current_ready_video = None
                            elif media_state == 1 and server.current_playing_video:  # STOPPED
                                # Video LIVE è stato fermato manualmente
                                server.current_playing_video = None
                    break
            obs.source_list_release(scenes)
    except Exception as e:
        pass

    # Controlla se ci sono azioni pendenti dalla web UI
    try:
        action = server.get_pending_action()
        if action:
            action_type = action.get('action')

            if action_type == 'load_replay':
                # Ottieni speed dalla action
                speed = action.get('speed', None)

                # Verifica se c'è un path diretto (per highlights) o un index
                if 'path' in action:
                    # Carica da path diretto
                    load_replay_to_source(action['path'], speed)
                else:
                    # Carica da index
                    index = action.get('index', 0)
                    if 0 <= index < len(server.replay_files):
                        load_replay_to_source(server.replay_files[index].path, speed)

            elif action_type == 'set_speed':
                # Imposta la velocità della media source
                speed = action.get('speed', 1.0)
                set_media_speed(speed)

            elif action_type == 'open_folder':
                # Apri la cartella replay
                open_replay_folder()
                print("✓ Cartella replay aperta da web UI")

    except Exception as e:
        print(f"Errore processing azione: {e}")


def load_latest_hotkey(pressed):
    """Hotkey per caricare ultimo replay (senza avviare riproduzione)"""
    if pressed and SERVER_AVAILABLE and server.replay_files:
        load_replay_to_source(server.replay_files[0].path)


def load_second_hotkey(pressed):
    """Hotkey per caricare penultimo replay (senza avviare riproduzione)"""
    if pressed and SERVER_AVAILABLE and len(server.replay_files) > 1:
        load_replay_to_source(server.replay_files[1].path)


def play_pause_hotkey(pressed):
    """Hotkey per Play/Pausa del video corrente"""
    if not pressed or not SERVER_AVAILABLE:
        return

    media_source_name = server.media_source_name
    target_scene_name = server.target_scene_name

    if not media_source_name or not target_scene_name:
        return

    scenes = obs.obs_frontend_get_scenes()
    for scene_source in scenes:
        if obs.obs_source_get_name(scene_source) == target_scene_name:
            target_scene = obs.obs_scene_from_source(scene_source)
            scene_item = obs.obs_scene_find_source(target_scene, media_source_name)

            if scene_item:
                source = obs.obs_sceneitem_get_source(scene_item)
                if source:
                    media_state = obs.obs_source_media_get_state(source)
                    # OBS_MEDIA_STATE_PLAYING = 2, OBS_MEDIA_STATE_PAUSED = 3
                    if media_state == 2:  # Playing -> Pause
                        obs.obs_source_media_play_pause(source, True)
                        print("⏸ Video in pausa")
                    else:  # Paused/Stopped -> Play
                        obs.obs_source_media_play_pause(source, False)
                        # Se era in READY mode, aggiorna lo stato
                        if server.current_ready_video:
                            server.current_playing_video = server.current_ready_video
                            server.current_ready_video = None
                        print("▶ Video in riproduzione")
            break
    obs.source_list_release(scenes)


def play_next_hotkey(pressed):
    """Hotkey per riprodurre il prossimo video nella playlist"""
    if not pressed or not SERVER_AVAILABLE:
        return

    # Chiama l'API del server per riprodurre il prossimo
    try:
        if hasattr(server, 'playlist_queue') and server.playlist_queue:
            # Simula la chiamata API play-next
            import urllib.request
            req = urllib.request.Request(
                f'http://localhost:{server_port}/api/queue/play-next',
                data=b'{}',
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            urllib.request.urlopen(req, timeout=2)
            print("⏭ Riproduzione prossimo in playlist")
    except Exception as e:
        print(f"⚠ Errore play next: {e}")


def open_folder_hotkey(pressed):
    """Hotkey per aprire la cartella replay"""
    if pressed and SERVER_AVAILABLE:
        open_replay_folder()


def script_unload():
    """Chiamato quando lo script viene scaricato"""
    print("\n" + "=" * 60)
    print("🎬 OBS Replay Manager - Arresto in corso...")
    print("=" * 60)

    # Rimuovi timer prima di tutto
    try:
        obs.timer_remove(check_actions_timer)
        print("✓ Timer rimosso")
    except Exception as e:
        print(f"⚠ Errore rimozione timer: {e}")

    # Ferma il server HTTP
    if SERVER_AVAILABLE:
        try:
            server.stop_server()
            print("✓ Server HTTP fermato")
        except Exception as e:
            print(f"⚠ Errore arresto server: {e}")

    # Unregister hotkeys
    try:
        hotkeys_removed = 0
        if 'hotkey_id_load_latest' in globals() and hotkey_id_load_latest != obs.OBS_INVALID_HOTKEY_ID:
            obs.obs_hotkey_unregister(hotkey_id_load_latest)
            hotkeys_removed += 1
        if 'hotkey_id_load_second' in globals() and hotkey_id_load_second != obs.OBS_INVALID_HOTKEY_ID:
            obs.obs_hotkey_unregister(hotkey_id_load_second)
            hotkeys_removed += 1
        if 'hotkey_id_play_pause' in globals() and hotkey_id_play_pause != obs.OBS_INVALID_HOTKEY_ID:
            obs.obs_hotkey_unregister(hotkey_id_play_pause)
            hotkeys_removed += 1
        if 'hotkey_id_play_next' in globals() and hotkey_id_play_next != obs.OBS_INVALID_HOTKEY_ID:
            obs.obs_hotkey_unregister(hotkey_id_play_next)
            hotkeys_removed += 1
        if 'hotkey_id_open_folder' in globals() and hotkey_id_open_folder != obs.OBS_INVALID_HOTKEY_ID:
            obs.obs_hotkey_unregister(hotkey_id_open_folder)
            hotkeys_removed += 1
        if hotkeys_removed > 0:
            print(f"✓ {hotkeys_removed} hotkey rimossi")
    except Exception as e:
        print(f"⚠ Errore rimozione hotkey: {e}")

    print("=" * 60)
    print("🎬 OBS Replay Manager - Scaricato correttamente")
    print("=" * 60 + "\n")


def script_save(settings):
    """Salva le impostazioni"""
    if 'hotkey_id_load_latest' in globals() and hotkey_id_load_latest != obs.OBS_INVALID_HOTKEY_ID:
        hotkey_save_array_latest = obs.obs_hotkey_save(hotkey_id_load_latest)
        obs.obs_data_set_array(settings, "load_latest_hotkey", hotkey_save_array_latest)
        obs.obs_data_array_release(hotkey_save_array_latest)

    if 'hotkey_id_load_second' in globals() and hotkey_id_load_second != obs.OBS_INVALID_HOTKEY_ID:
        hotkey_save_array_second = obs.obs_hotkey_save(hotkey_id_load_second)
        obs.obs_data_set_array(settings, "load_second_hotkey", hotkey_save_array_second)
        obs.obs_data_array_release(hotkey_save_array_second)

    if 'hotkey_id_play_pause' in globals() and hotkey_id_play_pause != obs.OBS_INVALID_HOTKEY_ID:
        hotkey_save_array = obs.obs_hotkey_save(hotkey_id_play_pause)
        obs.obs_data_set_array(settings, "play_pause_hotkey", hotkey_save_array)
        obs.obs_data_array_release(hotkey_save_array)

    if 'hotkey_id_play_next' in globals() and hotkey_id_play_next != obs.OBS_INVALID_HOTKEY_ID:
        hotkey_save_array = obs.obs_hotkey_save(hotkey_id_play_next)
        obs.obs_data_set_array(settings, "play_next_hotkey", hotkey_save_array)
        obs.obs_data_array_release(hotkey_save_array)

    if 'hotkey_id_open_folder' in globals() and hotkey_id_open_folder != obs.OBS_INVALID_HOTKEY_ID:
        hotkey_save_array = obs.obs_hotkey_save(hotkey_id_open_folder)
        obs.obs_data_set_array(settings, "open_folder_hotkey", hotkey_save_array)
        obs.obs_data_array_release(hotkey_save_array)


# Variabili hotkey
hotkey_id_load_latest = obs.OBS_INVALID_HOTKEY_ID
hotkey_id_load_second = obs.OBS_INVALID_HOTKEY_ID
hotkey_id_play_pause = obs.OBS_INVALID_HOTKEY_ID
hotkey_id_play_next = obs.OBS_INVALID_HOTKEY_ID
hotkey_id_open_folder = obs.OBS_INVALID_HOTKEY_ID
