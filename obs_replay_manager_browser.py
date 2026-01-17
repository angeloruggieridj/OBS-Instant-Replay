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
    SERVER_VERSION = "1.0-beta1"
except ImportError as e:
    SERVER_AVAILABLE = False
    SERVER_VERSION = None
    print(f"✗ Impossibile importare replay_http_server: {e}")

# Variabili globali
replay_folder = ""
media_source_name = ""
target_scene_name = ""
auto_switch_scene = False
server_port = 8765
dock_created = False


def load_replay_to_source(file_path, auto_play=True):
    """Carica un replay nella fonte multimediale"""
    global media_source_name, target_scene_name, auto_switch_scene
    
    if not media_source_name or not target_scene_name:
        print("⚠ Nome fonte o scena non configurati")
        return False
    
    scenes = obs.obs_frontend_get_scenes()
    target_scene = None
    
    for scene_source in scenes:
        scene_name = obs.obs_source_get_name(scene_source)
        if scene_name == target_scene_name:
            target_scene = obs.obs_scene_from_source(scene_source)
            break
    
    obs.source_list_release(scenes)
    
    if not target_scene:
        print(f"⚠ Scena '{target_scene_name}' non trovata")
        return False
    
    scene_item = obs.obs_scene_find_source(target_scene, media_source_name)
    
    if scene_item:
        source = obs.obs_sceneitem_get_source(scene_item)
    else:
        settings = obs.obs_data_create()
        source = obs.obs_source_create("ffmpeg_source", media_source_name, settings, None)
        obs.obs_data_release(settings)
        
        if source:
            obs.obs_scene_add(target_scene, source)
    
    if source:
        settings = obs.obs_data_create()
        obs.obs_data_set_string(settings, "local_file", file_path)
        obs.obs_data_set_bool(settings, "is_local_file", True)
        obs.obs_data_set_bool(settings, "looping", False)
        obs.obs_data_set_bool(settings, "hw_decode", True)

        # READY mode: disabilita restart_on_activate per evitare avvio automatico
        # Questo è fondamentale in Studio Mode dove la transizione attiverebbe il video
        if auto_play:
            obs.obs_data_set_bool(settings, "restart_on_activate", True)
        else:
            obs.obs_data_set_bool(settings, "restart_on_activate", False)
            obs.obs_data_set_bool(settings, "close_when_inactive", False)

        obs.obs_source_update(source, settings)
        obs.obs_data_release(settings)

        # Gestione riproduzione
        if auto_play:
            obs.obs_source_media_restart(source)
        else:
            # READY mode: ferma e vai all'inizio senza riprodurre
            obs.obs_source_media_stop(source)
            # Imposta il tempo a 0 per essere pronti all'avvio
            obs.obs_source_media_set_time(source, 0)
        
        if auto_switch_scene:
            scenes = obs.obs_frontend_get_scenes()
            for scene_source in scenes:
                if obs.obs_source_get_name(scene_source) == target_scene_name:
                    obs.obs_frontend_set_current_scene(scene_source)
                    break
            obs.source_list_release(scenes)
        
        print(f"✓ Replay caricato: {os.path.basename(file_path)}")
        return True
    
    return False


def open_replay_folder():
    """Apri cartella replay"""
    global replay_folder
    
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
    desc = """<center><h2>🎬 OBS Replay Manager - Browser Dock</h2></center>
    <p><b>Plugin con pannello Browser integrato</b></p>
    <hr>
    """

    if SERVER_AVAILABLE:
        desc += f"""<p style='color: green;'><b>✓ Server HTTP disponibile ({SERVER_VERSION})</b></p>
        <p><b>Il pannello sarà creato automaticamente all'avvio.</b></p>
        <p>Dopo aver configurato qui sotto:</p>
        <ol>
            <li>Clicca sul pulsante "Crea/Apri Pannello Browser" qui sotto</li>
            <li>Oppure vai su: <b>Pannelli → Custom Browser Docks → Replay Manager</b></li>
            <li>Oppure vai su: <b>View → Docks → Replay Manager</b></li>
        </ol>
        <p style='color: #999; font-size: 12px;'>
        URL Pannello: http://localhost:{server_port}
        </p>
        <p style='background: #2a2a2a; padding: 10px; border-radius: 5px; margin-top: 10px;'>
        <b>💡 Nota:</b> Se il pannello non appare, prova a:
        <br>1. Riavviare OBS
        <br>2. Cliccare nuovamente "Crea/Apri Pannello Browser"
        <br>3. Controllare che nessun altro programma usi la porta {server_port}
        </p>
        """
    else:
        desc += """<p style='color: red;'><b>✗ Server HTTP non disponibile</b></p>
        <p>Assicurati che il file <code>replay_http_server.py</code> sia nella stessa cartella di questo script.</p>
        """
    
    desc += """
    <hr>
    <p style='font-size: 11px; color: #666;'>
    <b>Vantaggi Browser Dock:</b><br>
    ✓ Nessuna dipendenza PyQt5<br>
    ✓ Interfaccia moderna e responsive<br>
    ✓ Nessun rischio di crash<br>
    ✓ Facile da personalizzare
    </p>
    """
    
    return desc


def script_properties():
    props = obs.obs_properties_create()
    
    # Pulsante per creare/aprire il dock
    if SERVER_AVAILABLE:
        obs.obs_properties_add_button(
            props,
            "create_dock",
            "🌐 Crea/Apri Pannello Browser",
            create_dock_callback
        )
        
        obs.obs_properties_add_text(
            props, "dock_info",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            obs.OBS_TEXT_INFO
        )
    
    obs.obs_properties_add_text(
        props, "header",
        "═══════════ CONFIGURAZIONE ═══════════",
        obs.OBS_TEXT_INFO
    )
    
    obs.obs_properties_add_path(
        props, "replay_folder",
        "📁 Cartella Replay",
        obs.OBS_PATH_DIRECTORY,
        None, None
    )
    
    obs.obs_properties_add_text(
        props, "media_source_name",
        "🎥 Nome Fonte Multimediale",
        obs.OBS_TEXT_DEFAULT
    )
    
    scene_list = obs.obs_properties_add_list(
        props, "target_scene",
        "🎬 Scena Target",
        obs.OBS_COMBO_TYPE_LIST,
        obs.OBS_COMBO_FORMAT_STRING
    )
    
    scenes = obs.obs_frontend_get_scenes()
    for scene_source in scenes:
        scene_name = obs.obs_source_get_name(scene_source)
        obs.obs_property_list_add_string(scene_list, scene_name, scene_name)
    obs.source_list_release(scenes)
    
    obs.obs_properties_add_bool(
        props, "auto_switch_scene",
        "↪️ Passa automaticamente alla scena"
    )
    
    obs.obs_properties_add_text(
        props, "filter_mask",
        "🔍 Filtro Nome File (es: Replay )",
        obs.OBS_TEXT_DEFAULT
    )
    
    obs.obs_properties_add_int_slider(
        props, "refresh_interval_seconds",
        "⏱️ Intervallo Auto-Refresh (secondi)",
        1, 60, 1
    )
    
    obs.obs_properties_add_int(
        props, "server_port",
        "🌐 Porta Server (richiede riavvio)",
        8765, 65535, 1
    )
    
    return props


def script_defaults(settings):
    obs.obs_data_set_default_string(settings, "media_source_name", "Replay Source")
    obs.obs_data_set_default_bool(settings, "auto_switch_scene", False)
    obs.obs_data_set_default_int(settings, "server_port", 8765)
    obs.obs_data_set_default_string(settings, "filter_mask", "")
    obs.obs_data_set_default_int(settings, "refresh_interval_seconds", 3)


def script_update(settings):
    global replay_folder, media_source_name, target_scene_name
    global auto_switch_scene, server_port
    
    replay_folder = obs.obs_data_get_string(settings, "replay_folder")
    media_source_name = obs.obs_data_get_string(settings, "media_source_name")
    target_scene_name = obs.obs_data_get_string(settings, "target_scene")
    auto_switch_scene = obs.obs_data_get_bool(settings, "auto_switch_scene")
    server_port = obs.obs_data_get_int(settings, "server_port")
    
    filter_mask = obs.obs_data_get_string(settings, "filter_mask")
    refresh_interval = obs.obs_data_get_int(settings, "refresh_interval_seconds")
    
    if SERVER_AVAILABLE:
        server.update_settings(replay_folder, media_source_name, target_scene_name, auto_switch_scene)
        server.filter_mask = filter_mask
        server.scan_replay_folder()
        # Comunica refresh interval al frontend
        server.refresh_interval_seconds = refresh_interval


def create_dock_callback(props, prop):
    """Callback per creare/aprire il dock browser"""
    create_browser_dock()
    return True


def create_browser_dock():
    """Crea il Custom Browser Dock"""
    global dock_created
    
    if not SERVER_AVAILABLE:
        print("✗ Server non disponibile")
        return
    
    try:
        # Crea dock usando obs_frontend_add_dock
        # Questo è supportato da OBS 28.0+
        dock_name = "Replay Manager"
        dock_url = f"http://localhost:{server_port}"
        
        print(f"Tentativo creazione dock: {dock_name}")
        print(f"URL: {dock_url}")
        
        # Nota: obs_frontend_add_dock non è sempre disponibile in obspython
        # In alternativa, creiamo una Browser Source che l'utente può aggiungere manualmente
        
        print("\n" + "=" * 60)
        print("📌 ISTRUZIONI PER AGGIUNGERE IL PANNELLO BROWSER:")
        print("=" * 60)
        print(f"1. In OBS, vai su: Pannelli → Custom Browser Docks")
        print(f"2. Clicca 'Add' o '+'")
        print(f"3. Nome Dock: Replay Manager")
        print(f"4. URL: http://localhost:{server_port}")
        print(f"5. Clicca 'Apply' o 'OK'")
        print("=" * 60)
        print(f"📍 Poi troverai il pannello in: Pannelli → Replay Manager")
        print("=" * 60 + "\n")
        
        dock_created = True
        
    except Exception as e:
        print(f"✗ Errore creazione dock: {e}")
        import traceback
        traceback.print_exc()


def script_load(settings):
    global hotkey_id_load_latest, hotkey_id_load_second

    print("\n" + "=" * 70)
    print("🎬 OBS Replay Manager - Browser Dock Edition")
    print("=" * 70)

    if not SERVER_AVAILABLE:
        print("✗ Server HTTP non disponibile")
        print("  Assicurati che replay_http_server_v4.py sia nella stessa cartella")
        print("=" * 70 + "\n")
        return

    print(f"✓ Server HTTP disponibile ({SERVER_VERSION})")
    
    # Avvia server HTTP
    if server.start_server(server_port):
        print(f"✓ Server avviato su http://localhost:{server_port}")
        print(f"\n📌 Per aggiungere il pannello browser:")
        print(f"   1. Vai su: Pannelli → Custom Browser Docks")
        print(f"   2. Clicca '+' o 'Add'")
        print(f"   3. Nome: Replay Manager")
        print(f"   4. URL: http://localhost:{server_port}")
        print(f"   5. Clicca 'Apply'\n")
        
        # Prova a creare il dock automaticamente
        # (questo potrebbe non funzionare su tutte le versioni di OBS)
        create_browser_dock()
    else:
        print(f"✗ Impossibile avviare server sulla porta {server_port}")
        print(f"   Prova a cambiare la porta nelle impostazioni")
    
    print("=" * 70 + "\n")
    
    # Hotkeys
    hotkey_id_load_latest = obs.obs_hotkey_register_frontend(
        "replay_manager.load_latest",
        "Carica Ultimo Replay",
        lambda pressed: load_latest_hotkey(pressed)
    )
    
    hotkey_id_load_second = obs.obs_hotkey_register_frontend(
        "replay_manager.load_second",
        "Carica Penultimo Replay",
        lambda pressed: load_second_hotkey(pressed)
    )
    
    # Carica hotkey salvate
    hotkey_save_array_latest = obs.obs_data_get_array(settings, "load_latest_hotkey")
    obs.obs_hotkey_load(hotkey_id_load_latest, hotkey_save_array_latest)
    obs.obs_data_array_release(hotkey_save_array_latest)
    
    hotkey_save_array_second = obs.obs_data_get_array(settings, "load_second_hotkey")
    obs.obs_hotkey_load(hotkey_id_load_second, hotkey_save_array_second)
    obs.obs_data_array_release(hotkey_save_array_second)
    
    # Timer per controllare azioni (ogni 500ms per reattività)
    obs.timer_add(check_actions_timer, 500)


def check_actions_timer():
    """Timer che controlla se ci sono azioni da eseguire"""
    if not SERVER_AVAILABLE:
        return

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
                # Ottieni auto_play dalla action
                auto_play = action.get('auto_play', True)

                # Verifica se c'è un path diretto (per highlights) o un index
                if 'path' in action:
                    # Carica da path diretto
                    load_replay_to_source(action['path'], auto_play)
                    status = "LIVE" if auto_play else "READY"
                    print(f"✓ Highlights caricato ({status}): {os.path.basename(action['path'])}")
                else:
                    # Carica da index
                    index = action.get('index', 0)
                    if 0 <= index < len(server.replay_files):
                        load_replay_to_source(server.replay_files[index].path, auto_play)
                        status = "LIVE" if auto_play else "READY"
                        print(f"✓ Replay caricato ({status}): {server.replay_files[index].name}")

            elif action_type == 'open_folder':
                # Apri la cartella replay
                open_replay_folder()
                print("✓ Cartella replay aperta da web UI")

    except Exception as e:
        print(f"Errore processing azione: {e}")


def load_latest_hotkey(pressed):
    """Hotkey per caricare ultimo replay"""
    if pressed and SERVER_AVAILABLE and server.replay_files:
        load_replay_to_source(server.replay_files[0].path)


def load_second_hotkey(pressed):
    """Hotkey per caricare penultimo replay"""
    if pressed and SERVER_AVAILABLE and len(server.replay_files) > 1:
        load_replay_to_source(server.replay_files[1].path)


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
        if 'hotkey_id_load_latest' in globals() and hotkey_id_load_latest != obs.OBS_INVALID_HOTKEY_ID:
            obs.obs_hotkey_unregister(hotkey_id_load_latest)
            print("✓ Hotkey rimossi")
    except Exception as e:
        print(f"⚠ Errore rimozione hotkey: {e}")

    print("=" * 60)
    print("🎬 OBS Replay Manager - Scaricato correttamente")
    print("=" * 60 + "\n")


def script_save(settings):
    """Salva le impostazioni"""
    if 'hotkey_id_load_latest' in globals():
        hotkey_save_array_latest = obs.obs_hotkey_save(hotkey_id_load_latest)
        obs.obs_data_set_array(settings, "load_latest_hotkey", hotkey_save_array_latest)
        obs.obs_data_array_release(hotkey_save_array_latest)
    
    if 'hotkey_id_load_second' in globals():
        hotkey_save_array_second = obs.obs_hotkey_save(hotkey_id_load_second)
        obs.obs_data_set_array(settings, "load_second_hotkey", hotkey_save_array_second)
        obs.obs_data_array_release(hotkey_save_array_second)


# Variabili hotkey
hotkey_id_load_latest = obs.OBS_INVALID_HOTKEY_ID
hotkey_id_load_second = obs.OBS_INVALID_HOTKEY_ID
