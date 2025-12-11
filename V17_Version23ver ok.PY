# Updated V17_Version22ver ok.PY
# Fix: quando la finestra principale veniva ridimensionata non veniva salvata la geometria
# Aggiunto: persistenza larghezze (Treeview / colonne) in ui_layout.json con debounce
# MODIFICA: la sezione "Cantanti" è stata spostata e suddivisa in due colonne posizionate sotto la colonna "Gestione lista".
import tkinter as tk
from tkinter import ttk, font, simpledialog, messagebox, filedialog
import json
import os
import sys
import datetime
import hashlib
import time
import socket
import random
import threading

# Sintesi vocale (gTTS)
try:
    from gtts import gTTS
    import tempfile
    from playsound import playsound
    GTTS_AVAILABLE = True
except ImportError:
    # playsound may be absent; gTTS may be absent
    try:
        from playsound import playsound
    except Exception:
        playsound = None
    GTTS_AVAILABLE = False

# Sintesi vocale locale (pyttsx3, supporta più voci)
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

# Riproduzione suono ding.wav (usando winsound su Windows)
try:
    import winsound
    WINSOUND_AVAILABLE = True
except ImportError:
    winsound = None
    WINSOUND_AVAILABLE = False

# simpleaudio: permette play / stop per WAV (più controllo rispetto a playsound)
try:
    import simpleaudio as sa
    SIMPLEAUDIO_AVAILABLE = True
except Exception:
    sa = None
    SIMPLEAUDIO_AVAILABLE = False

# Gestione volume per-app con pycaw
try:
    from ctypes import POINTER, cast
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, ISimpleAudioVolume
    PYCAW_AVAILABLE = True
except ImportError:
    PYCAW_AVAILABLE = False

# Tentativo di supporto riproduzione video (imageio + Pillow)
try:
    import imageio
    from PIL import Image, ImageTk, ImageSequence
    IMAGEIO_AVAILABLE = True
    # compatibilità resampling per diverse versioni di Pillow
    try:
        RESAMPLE_LANCZOS = Image.Resampling.LANCZOS
    except Exception:
        if hasattr(Image, "LANCZOS"):
            RESAMPLE_LANCZOS = Image.LANCZOS
        elif hasattr(Image, "ANTIALIAS"):
            RESAMPLE_LANCZOS = Image.ANTIALIAS
        else:
            RESAMPLE_LANCZOS = getattr(Image, "BICUBIC", 1)
    # massimo fattore di ingrandimento per evitare upscaling eccessivo (imposta a None per senza limite)
    MAX_UPSCALE = 3.0
except Exception:
    IMAGEIO_AVAILABLE = False
    RESAMPLE_LANCZOS = None
    MAX_UPSCALE = 1.0

from list_data import ListData

DATA_FILENAME = "waiting_list.txt"
LICENSE_FILE = "license.txt"
TRIAL_DURATION_SEC = 180  # 3 minuti

# Posizioni separate per Annuncio e Video
ANNUNCIO_POS_FILE = "annuncio_pos.json"
VIDEO_POS_FILE = "video_pos.json"

# File layout persistente
LAYOUT_FILE = "ui_layout.json"

AUDIO_ENABLED = False  # di default non attivo

# Voci ITA online (gTTS)
ONLINE_TTS_VOICES = [
    ("Italiana Femminile (gTTS online)", "it", "f", "gtts"),
    ("Italiana Maschile (simulata, gTTS online)", "it", "m", "gtts"),
]

CURRENT_TTS_LANGUAGE = "it"
CURRENT_TTS_GENDER = "f"
CURRENT_TTS_ENGINE = "gtts"
CURRENT_PYTTSX3_VOICE_ID = None

# Nome del file che definisce i suoni per i pulsanti
SOUND_DEF_FILE = "sound.txt"
MAX_SOUND_BUTTONS = 8

def get_italian_voices_pyttsx3():
    voci = []
    if not PYTTSX3_AVAILABLE:
        return []
    try:
        engine = pyttsx3.init()
        for v in engine.getProperty('voices'):
            langs = []
            try:
                langs = [l.decode().lower() for l in v.languages]
            except Exception:
                langs = [str(l).lower() for l in v.languages]
            if any(l.startswith('it') for l in langs) or 'italian' in v.name.lower():
                voci.append({
                    "label": f"{v.name} (offline)",
                    "id": v.id,
                    "engine": "pyttsx3",
                })
        engine.stop()
    except Exception:
        pass
    return voci

def get_all_voice_options():
    voci = []
    for label, lang, gender, engine in ONLINE_TTS_VOICES:
        voci.append((label, lang, gender, engine))
    for voce in get_italian_voices_pyttsx3():
        voci.append((voce["label"], voce["id"], None, "pyttsx3"))
    return voci

ALL_VOICE_OPTIONS = get_all_voice_options()

def get_data_file_path():
    try:
        base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    except Exception:
        base = os.getcwd()
    return os.path.join(base, DATA_FILENAME)

def get_license_file_path():
    try:
        base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    except Exception:
        base = os.getcwd()
    return os.path.join(base, LICENSE_FILE)

def get_sound_def_file_path():
    try:
        base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    except Exception:
        base = os.getcwd()
    return os.path.join(base, SOUND_DEF_FILE)

def get_layout_file_path():
    try:
        base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    except Exception:
        base = os.getcwd()
    return os.path.join(base, LAYOUT_FILE)

DATA_FILE = get_data_file_path()
LICENSE_PATH = get_license_file_path()
SOUND_DEF_PATH = get_sound_def_file_path()
LAYOUT_PATH = get_layout_file_path()

# Utility generiche per salvare/caricare posizioni (annuncio rimane x,y)
def save_position(x, y, filename):
    try:
        with open(filename, "w") as f:
            json.dump({"x": x, "y": y}, f)
    except Exception:
        pass

def load_position(filename):
    try:
        with open(filename, "r") as f:
            data = json.load(f)
            return data.get("x", None), data.get("y", None)
    except Exception:
        return None, None

def save_annuncio_position(x, y):
    save_position(x, y, ANNUNCIO_POS_FILE)

def load_annuncio_position():
    return load_position(ANNUNCIO_POS_FILE)

# Nuove funzioni: salva/leggi geometria completa per la popup video (x,y,w,h)
def save_video_position(x, y, w=None, h=None):
    try:
        data = {"x": x, "y": y}
        if w is not None:
            data["w"] = w
        if h is not None:
            data["h"] = h
        with open(VIDEO_POS_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass

def load_video_position():
    try:
        with open(VIDEO_POS_FILE, "r") as f:
            data = json.load(f)
            x = data.get("x", None)
            y = data.get("y", None)
            w = data.get("w", None)
            h = data.get("h", None)
            return x, y, w, h
    except Exception:
        return None, None, None, None

def get_machine_id():
    try:
        username = os.environ.get("USERNAME") or os.environ.get("USER") or "user"
        hostname = socket.gethostname()
        return f"{username}@{hostname}"
    except Exception:
        return "user@local"

def generate_license_code(machine_id):
    base = f"IVANLM-{machine_id}-2024-SECRET"
    code = hashlib.sha256(base.encode()).hexdigest().upper()
    return code[:24]

def check_license():
    machine_id = get_machine_id()
    code = None
    if os.path.exists(LICENSE_PATH):
        with open(LICENSE_PATH, "r") as f:
            code = f.read().strip()
    valid = code == generate_license_code(machine_id)
    return valid

def save_license(license_code):
    with open(LICENSE_PATH, "w") as f:
        f.write(license_code.strip())

def show_license_activation(root):
    machine_id = get_machine_id()
    code = simpledialog.askstring("Attiva Licenza",
        f"Inserisci il codice di attivazione per questa macchina:\n\nID: {machine_id}\n\n(contattare l'autore per riceverlo)",
        parent=root)
    if code:
        if code.strip() == generate_license_code(machine_id):
            save_license(code.strip())
            messagebox.showinfo("Licenza attivata", "Licenza correttamente attivata! Riavviare il programma.")
            root.quit()
            root.destroy()
        else:
            messagebox.showerror("Errore", "Codice di attivazione non valido.")

def backup_waiting_list():
    if os.path.exists(DATA_FILE):
        now = datetime.datetime.now()
        backup_name = f"waiting_list_backup_{now.strftime('%Y%m%d_%H%M%S')}.txt"
        backup_path = os.path.join(os.path.dirname(DATA_FILE), backup_name)
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as src, open(backup_path, "w", encoding="utf-8") as dst:
                dst.write(src.read())
        except Exception:
            pass

def song_color(n):
    gradient_colors = [
        "#00FF00",  # 0 - Verde fluo
        "#FFFF00",  # 1 - Giallo fluo
        "#00FFFF",  # 2 - Ciano fluo
        "#FF00FF",  # 3 - Magenta fluo
        "#FF0000",  # 4 - Rosso fluo
        "#FF8000",  # 5 - Arancione fluo
        "#00FFEA",  # 6 - Turchese fluo
    ]
    return gradient_colors[max(0, min(n, 6))]

def format_seconds(seconds):
    try:
        total = int(max(0, seconds))
        hours, rem = divmod(total, 3600)
        minutes, secs = divmod(rem, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
    except Exception:
        return "-"

def play_notification_sound():
    if WINSOUND_AVAILABLE:
        try:
            base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
            sound_file = os.path.join(base, "ding.wav")
            if os.path.exists(sound_file):
                winsound.PlaySound(sound_file, winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                print("Il file ding.wav non è stato trovato in:", sound_file)
        except Exception as e:
            print("Errore riproduzione ding.wav:", e)

def mute_other_apps():
    if not PYCAW_AVAILABLE:
        return
    try:
        sessions = AudioUtilities.GetAllSessions()
        current_pid = os.getpid()
        for session in sessions:
            proc = session.Process
            if proc is None or proc.pid != current_pid:
                try:
                    simple_audio = session._ctl.QueryInterface(ISimpleAudioVolume)
                    simple_audio.SetMute(1, None)
                except Exception as e:
                    print(f"Errore mute sessione: {e}")
    except Exception as e:
        print("Errore mute altre app:", e)

def unmute_other_apps():
    if not PYCAW_AVAILABLE:
        return
    try:
        sessions = AudioUtilities.GetAllSessions()
        current_pid = os.getpid()
        for session in sessions:
            proc = session.Process
            if proc is None or proc.pid != current_pid:
                try:
                    simple_audio = session._ctl.QueryInterface(ISimpleAudioVolume)
                    simple_audio.SetMute(0, None)
                except Exception as e:
                    print(f"Errore unmute sessione: {e}")
    except Exception as e:
        print("Errore unmute altre app:", e)

def pronuncia_testo(test, app=None):
    global CURRENT_TTS_LANGUAGE, CURRENT_TTS_GENDER, CURRENT_TTS_ENGINE, CURRENT_PYTTSX3_VOICE_ID
    if not AUDIO_ENABLED:
        print("Sintesi vocale non attiva.")
        return
    voce_sel = None
    if app is not None and hasattr(app, "voice_var"):
        voce_sel = app.voice_var.get()
    else:
        voce_sel = ALL_VOICE_OPTIONS[0][0]
    voce = next((v for v in ALL_VOICE_OPTIONS if v[0] == voce_sel), ALL_VOICE_OPTIONS[0])
    voce_label, voce_id_or_lang, voce_gender, voce_engine = voce
    if voce_engine == "pyttsx3" and PYTTSX3_AVAILABLE:
        def tts_worker():
            mute_other_apps()
            play_notification_sound()
            time.sleep(2)
            try:
                engine = pyttsx3.init()
                engine.setProperty('voice', voce_id_or_lang)
                engine.say(test)
                engine.runAndWait()
            except Exception as e:
                print("Errore sintesi vocale (pyttsx3):", e)
            finally:
                unmute_other_apps()
        threading.Thread(target=tts_worker, daemon=True).start()
    elif voce_engine == "gtts" and GTTS_AVAILABLE:
        def tts_worker():
            mute_other_apps()
            play_notification_sound()
            time.sleep(2)
            try:
                tts = gTTS(text=test, lang=voce_id_or_lang, slow=False)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                    temp_path = fp.name
                    tts.save(temp_path)
                if voce_gender == "m":
                    tts_slow = gTTS(text=test, lang=voce_id_or_lang, slow=True)
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp2:
                        temp_path2 = fp2.name
                        tts_slow.save(temp_path2)
                    playsound(temp_path2)
                    os.remove(temp_path2)
                else:
                    playsound(temp_path)
                os.remove(temp_path)
            except Exception as e:
                print("Errore sintesi vocale (gTTS):", e)
            finally:
                unmute_other_apps()
        threading.Thread(target=tts_worker, daemon=True).start()
    else:
        print("Sintesi vocale non disponibile per la voce selezionata.")

# --- Nuove funzioni per gestione pulsanti suoni ----------------
def load_sound_defs():
    """
    Carica SOUND_DEF_PATH e restituisce lista di dizionari:
    [{'label': 'Sirena', 'file': 'Sirena.wav'}, ...]
    Se il file non esiste o è vuoto ritorna lista vuota.
    Limita a MAX_SOUND_BUTTONS voci.
    """
    defs = []
    try:
        if not os.path.exists(SOUND_DEF_PATH):
            return defs
        with open(SOUND_DEF_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # supporta anche separatore "|" e ";" e tab
                parts = [p.strip() for p in line.replace("\t", "|").replace(";", "|").split("|")]
                if len(parts) >= 2:
                    label = parts[0] or "Suono"
                    filename = parts[1]
                    defs.append({"label": label, "file": filename})
                else:
                    # fallback: usa tutta la riga come label e file vuoto
                    defs.append({"label": line, "file": ""})
                if len(defs) >= MAX_SOUND_BUTTONS:
                    break
    except Exception:
        pass
    return defs

def resolve_sound_path(filename):
    """
    Risolve filename: se è percorso assoluto lo usa, altrimenti lo cerca nella cartella dell'app.
    """
    if not filename:
        return None
    if os.path.isabs(filename) and os.path.exists(filename):
        return filename
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(base, filename)
    if os.path.exists(candidate):
        return candidate
    # anche proviamo direttamente la stringa (nel caso l'utente abbia inserito percorso relativo diverso)
    if os.path.exists(filename):
        return filename
    return None

# ----------------------------------------------------------------

class WindowDisplay:
    def __init__(self, root, main_app):
        self.root = root
        self.main_app = main_app
        self.root.title("Lista d'attesa - Display | www.ivanlivemusic.com")
        self.root.configure(bg="white")
        self.root.withdraw()
        frm = tk.Frame(self.root, bg="white")
        frm.pack(fill=tk.BOTH, expand=True)
        self.display_table = tk.Frame(frm, bg="white")
        self.display_table.pack(fill=tk.BOTH, expand=True)
        # Bind per salvare resize della "display table" nel file di log
        try:
            self.display_table.bind("<Configure>", lambda e: self.main_app.on_column_configure("DisplayTable", e.width))
        except Exception:
            pass
        self.refresh_display_table()

    def refresh_display_table(self):
        for widget in self.display_table.winfo_children():
            widget.destroy()
        headers = ["N°", "Nome"]
        if self.main_app.display_show_wait:
            headers.append("Attesa")
        col_values = [[] for _ in headers]
        for it in self.main_app.items:
            if not it.get("stopped"):
                col_values[0].append(str(it["num"]))
                col_values[1].append(it["name"])
                if self.main_app.display_show_wait:
                    col_values[2].append(self.main_app.compute_wait_text_for_item(it))
        col_widths = []
        for i, head in enumerate(headers):
            max_data = max([len(head)] + [len(v) for v in col_values[i]]) if col_values[i] else len(head)
            col_widths.append(max(4, min(max_data + 2, 14)))
        bigfont = self.main_app.display_font
        boldfont = font.Font(family=bigfont.actual("family"), size=bigfont.actual("size"), weight="bold")
        for col, title in enumerate(headers):
            lbl = tk.Label(self.display_table, text=title, font=boldfont,
                           bg="#e0e0e0", anchor="center", relief="ridge", width=col_widths[col])
            lbl.grid(row=0, column=col, sticky="nsew", padx=1, pady=1)
        visible_items_all = [it for it in self.main_app.items if not it.get("stopped")]
        start = self.main_app.display_page * self.main_app.display_max_rows
        end = start + self.main_app.display_max_rows
        visible_items = visible_items_all[start:end]
        for row_idx, it in enumerate(visible_items, start=1):
            songs = it.get("songs", 0)
            highlight_row = it.get("highlighted", False)
            values = [str(it["num"]), it["name"]]
            if self.main_app.display_show_wait:
                values.append(self.main_app.compute_wait_text_for_item(it))
            bg = "#CCCCCC" if highlight_row else song_color(songs)
            for col, val in enumerate(values):
                fg = "black"
                align = "w"
                if headers[col] == "Attesa":
                    align = "e"
                lbl = tk.Label(self.display_table, text=val, font=bigfont,
                               bg=bg, fg=fg, anchor=align,
                               width=col_widths[col], relief="ridge")
                lbl.grid(row=row_idx, column=col, sticky="nsew", padx=1, pady=1)
        for c in range(len(headers)):
            self.display_table.grid_columnconfigure(c, weight=1)
        num_items = len(visible_items_all)
        max_page = max(0, (num_items - 1) // self.main_app.display_max_rows)
        if hasattr(self.main_app, "page_label"):
            self.main_app.page_label.config(text=f"Pagina {self.main_app.display_page+1} di {max_page+1}")

class WaitingListApp:
    def __init__(self, root):
        self.root = root
        self.license_valid = check_license()
        if not self.license_valid:
            self.trial_start = time.time()
            self.trial_end = self.trial_start + TRIAL_DURATION_SEC
            self.root.after(1000, self.check_trial)
            self.add_license_menu()
        self.root.title("Lista d'attesa - Controllo | www.ivanlivemusic.com")
        self.items = []
        self.next_id = 1
        self.data_modified = False
        self.display_font_size = 18
        self.display_font_bold = False
        self.display_font = font.Font(size=self.display_font_size, weight="normal")
        self.display_max_rows = 20
        self.display_page = 0
        self.display_show_wait = True
        self.data = ListData()
        self.load_data_from_listdata()
        for it in self.items:
            if "stopped" not in it:
                it["stopped"] = False
            if "wait_sec" not in it:
                it["wait_sec"] = random.randint(210, 270)
            if "songs" not in it:
                it["songs"] = 0
            if "highlighted" not in it:
                it["highlighted"] = False
        default_font = font.nametofont("TkDefaultFont")
        standard_size = default_font.cget("size") or 10
        self.control_font = font.Font(size=standard_size)
        # Reference to the video/GIF popup window (so we can toggle/close it)
        self.video_popup_window = None

        # Stato riproduzione suoni (per poter fermare il suono se si preme lo stesso pulsante)
        self.current_play_obj = None        # oggetto restituito da simpleaudio.play()
        self.current_play_method = None     # 'simpleaudio' | 'winsound' | 'playsound' | None
        self.current_sound_path = None
        self.playsound_thread = None

        # Carica definizioni suoni per pulsanti
        self.sound_defs = load_sound_defs()
        self.sound_btns = []

        # Path file log per resize
        try:
            base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
        except Exception:
            base = os.getcwd()
        self.resize_log_path = os.path.join(base, "resize_log.txt")
        # memorizza larghezze precedenti per evitare scritture duplicate
        self.prev_col_widths = {}
        # memorizza dimensioni precedenti delle finestre per evitare scritture duplicate
        self.prev_window_sizes = {}

        # layout persistente
        self.layout_path = LAYOUT_PATH
        self.layout = self.load_layout_file()
        self._layout_save_after_id = None

        self.root.withdraw()
        self.build_control_window()
        # assicurati che widget siano creati prima di applicare layout
        self.root.update_idletasks()
        # applica eventuali valori salvati (es. larghezze)
        self.apply_layout()
        self.build_display_window()
        self.center_windows_side_by_side_with_header_check()
        self.root.deiconify()
        self.display.root.deiconify()

        # Bind per salvare resize della finestra principale e della finestra display
        try:
            # bind alla top-level principale
            self.root.bind("<Configure>", lambda e: self.on_window_configure("MainWindow", e))
        except Exception:
            pass
        try:
            # bind alla finestra display (top-level)
            self.display.root.bind("<Configure>", lambda e: self.on_window_configure("DisplayWindow", e))
        except Exception:
            pass

        self.refresh_trees()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        try:
            self.display.root.protocol("WM_DELETE_WINDOW", self.on_close)
        except Exception:
            pass

    # --- Layout persistente: load / save / apply / schedule ---
    def load_layout_file(self):
        try:
            if os.path.exists(self.layout_path):
                with open(self.layout_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def save_layout_file(self):
        try:
            with open(self.layout_path, "w", encoding="utf-8") as f:
                json.dump(self.layout, f, indent=2)
        except Exception:
            pass

    def schedule_save_layout(self, delay=300):
        try:
            if self._layout_save_after_id:
                try:
                    self.root.after_cancel(self._layout_save_after_id)
                except Exception:
                    pass
            self._layout_save_after_id = self.root.after(delay, lambda: (setattr(self, "_layout_save_after_id", None), self.save_layout_file()))
        except Exception:
            # fallback immediato
            self.save_layout_file()

    def apply_layout(self):
        """
        Applica valori salvati di layout (es. minsize della colonna dell'albero / width del right_side_frame).
        Viene chiamata dopo build_control_window e update_idletasks.
        """
        try:
            # se esiste una larghezza salvata per 'AlberoFrame' usala come minsize per la colonna 0 di 'mid'
            tree_w = None
            right_w = None
            if isinstance(self.layout, dict):
                tree_w = self.layout.get("AlberoFrame")
                right_w = self.layout.get("RightSide")
            # applica minsize per la colonna albero (mid deve essere accessibile)
            try:
                # mid è creato in build_control_window come variabile locale: salviamo self.mid nella build
                if hasattr(self, "mid") and tree_w:
                    try:
                        self.mid.grid_columnconfigure(0, minsize=int(tree_w))
                    except Exception:
                        pass
                if hasattr(self, "right_side_frame") and right_w:
                    try:
                        self.right_side_frame.config(width=int(right_w))
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            pass

    # ---------------------------------------------------------

    def add_license_menu(self):
        menubar = tk.Menu(self.root)
        lic_menu = tk.Menu(menubar, tearoff=0)
        lic_menu.add_command(label="Attiva Licenza...", command=lambda: show_license_activation(self.root))
        menubar.add_cascade(label="Licenza", menu=lic_menu)
        self.root.config(menu=menubar)

    def check_trial(self):
        now = time.time()
        seconds_left = int(self.trial_end - now)
        if seconds_left > 0:
            m, s = divmod(seconds_left, 60)
            self.root.title(f"Versione di prova ({m}:{s:02d} rimasti) - Lista d'attesa | www.ivanlivemusic.com")
            self.root.after(1000, self.check_trial)
        else:
            messagebox.showwarning("Trial Terminato", "Il periodo di prova è terminato.\nAttiva la licenza per continuare a usare il programma.")
            self.root.quit()
            self.root.destroy()

    def center_windows_side_by_side_with_header_check(self):
        control_width = 700
        control_height = 650
        display_width = 301
        display_height = 817
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x0 = int((sw - (control_width + display_width + 32)) // 2)
        y0 = max(0, int((sh - max(control_height, display_height)) // 2))
        self.root.geometry(f"{control_width}x{control_height}+{x0}+{y0}")
        x_disp = x0 + control_width + 32
        self.display.root.geometry(f"{display_width}x{display_height}+{x_disp}+{y0}")

    def load_data_from_listdata(self):
        self.items = self.data.get_data()
        self.next_id = max([item["num"] for item in self.items], default=0) + 1

    def save_data_to_listdata(self):
        self.data.data = self.items
        self.data.save_data()

    # --- Nuove funzioni per logging resize ---
    def log_resize_event(self, name, width):
        """Append a timestamped line to the resize_log.txt file.
        'width' can be an int (for columns) or a string like '800x600' for windows.
        """
        try:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.resize_log_path, "a", encoding="utf-8") as f:
                f.write(f"{ts} - {name} resized to {width}\n")
        except Exception:
            pass

    def on_column_configure(self, name, width):
        """Called on <Configure> for frames / widgets representing 'tables'.
        Writes to file only when width actually changes and persists layout for later runs."""
        try:
            w = int(width)
        except Exception:
            try:
                w = int(self.root.winfo_width())
            except Exception:
                w = width
        prev = self.prev_col_widths.get(name)
        if prev != w:
            self.prev_col_widths[name] = w
            # log come prima
            self.log_resize_event(name, f"{w}px")
            # salva anche nella struttura di layout persistente per 'AlberoFrame' e per il right_side_frame
            try:
                # usa nomi coerenti con apply_layout
                if name in ("AlberoFrame", "Treeview", "AlberoFrame"):
                    self.layout["AlberoFrame"] = w
                    # se abbiamo il right side frame, memorizza anche la sua larghezza
                    if hasattr(self, "right_side_frame"):
                        try:
                            rw = self.right_side_frame.winfo_width()
                            self.layout["RightSide"] = int(rw)
                        except Exception:
                            pass
                    # schedule save con debounce
                    self.schedule_save_layout()
                elif name in ("Gestione lista", "Extra"):
                    # tieni traccia opzionale per debug o riuso
                    self.layout[name] = w
                    self.schedule_save_layout()
                else:
                    # generico
                    self.layout[name] = w
                    self.schedule_save_layout()
            except Exception:
                pass

    def on_window_configure(self, name, event):
        """Called when a top-level window is moved/resized. Logs width x height changes."""
        try:
            widget = event.widget
            try:
                top = widget.winfo_toplevel()
            except Exception:
                top = widget
            if name == "MainWindow" and top != self.root:
                return
            if name == "DisplayWindow" and getattr(self, "display", None) and top != self.display.root:
                return
            try:
                w = int(event.width)
                h = int(event.height)
            except Exception:
                try:
                    w = widget.winfo_width()
                    h = widget.winfo_height()
                except Exception:
                    return
            prev = self.prev_window_sizes.get(name)
            if prev != (w, h):
                self.prev_window_sizes[name] = (w, h)
                self.log_resize_event(name, f"{w}x{h}px")
        except Exception:
            pass

    # ---------------------------------------------------------

    def build_control_window(self):
        frm = ttk.Frame(self.root, padding=8)
        frm.pack(fill=tk.BOTH, expand=True)
        self.frm = frm  # reference if needed

        # --- NUOVO: frame dei pulsanti suoni (in alto) ---
        sounds_frame = ttk.Frame(frm)
        sounds_frame.pack(fill=tk.X, pady=(0,8))
        # crea fino a MAX_SOUND_BUTTONS pulsanti
        self.sound_btns = []
        for i in range(MAX_SOUND_BUTTONS):
            if i < len(self.sound_defs):
                lbl = self.sound_defs[i].get("label", f"Suono {i+1}")
                fname = self.sound_defs[i].get("file", "")
                btn = ttk.Button(sounds_frame, text=lbl, width=12, command=(lambda j=i: self.on_sound_button(j)))
            else:
                btn = ttk.Button(sounds_frame, text="-", width=12, state="disabled")
            btn.grid(row=0, column=i, padx=2)
            self.sound_btns.append(btn)
        # piccolo pulsante per ricaricare sound.txt senza riavviare
        reload_btn = ttk.Button(sounds_frame, text="Ricarica Suoni", command=self.reload_sound_defs)
        reload_btn.grid(row=0, column=MAX_SOUND_BUTTONS, padx=(10,0))

        top = ttk.Frame(frm)
        top.pack(fill=tk.X, pady=4)
        top.columnconfigure(0, weight=1, uniform="a")
        top.columnconfigure(1, weight=1, uniform="a")
        label_nome = ttk.Label(top, text="Nome:", font=self.control_font)
        label_note = ttk.Label(top, text="Note:", font=self.control_font)
        label_nome.grid(row=0, column=0, sticky="w", padx=(0, 8))
        label_note.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.name_var = tk.StringVar()
        self.entry_name = ttk.Entry(top, textvariable=self.name_var, font=self.control_font)
        self.entry_name.grid(row=1, column=0, sticky="ew", padx=(0, 8), ipady=4)
        self.entry_name.bind("<Return>", lambda e: self.add_person())
        self.note_var = tk.StringVar()
        self.entry_note = ttk.Entry(top, textvariable=self.note_var, font=self.control_font)
        self.entry_note.grid(row=1, column=1, sticky="ew", padx=(8, 0), ipady=4)
        label_songs = ttk.Label(top, text="Canzoni:", font=self.control_font)
        label_songs.grid(row=0, column=2, sticky="w", padx=(8, 0))
        self.songs_var = tk.IntVar(value=0)
        self.entry_songs = ttk.Spinbox(top, from_=0, to=6, textvariable=self.songs_var, width=4, font=self.control_font)
        self.entry_songs.grid(row=1, column=2, sticky="ew", padx=(8, 0), ipady=4)

        # mid contiene l'albero (a sinistra) e la colonna dei controlli (a destra)
        mid = ttk.Frame(frm)
        mid.pack(fill=tk.BOTH, expand=True)
        self.mid = mid  # keep reference for apply_layout
        # Usare grid dentro 'mid' per garantire che la colonna sinistra (albero) si allarghi e la colonna destra mantenga larghezza fissa
        mid.grid_columnconfigure(0, weight=1)
        mid.grid_columnconfigure(1, weight=0)
        mid.grid_rowconfigure(0, weight=1)

        # Frame per l'albero (left) - ora con grid
        tree_frame = ttk.Frame(mid)
        tree_frame.grid(row=0, column=0, sticky="nsew")
        self.tree_frame = tree_frame  # reference per applying layout
        columns = ("numero", "nome", "attesa", "note", "canzoni", "stop")
        style = ttk.Style()
        style.configure("Control.Treeview", font=self.control_font)
        style.configure("Control.Treeview.Heading", font=self.control_font)
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse", style="Control.Treeview")
        self.tree.heading("numero", text="Num")
        self.tree.heading("nome", text="Nome")
        self.tree.heading("attesa", text="Tempo attesa")
        self.tree.heading("note", text="Note")
        self.tree.heading("canzoni", text="Canzoni")
        self.tree.heading("stop", text="STOP")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.tag_configure("highlighted", background="#CCCCCC")
        self.tree.tag_configure("stopped", background="#FF3131")
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)
        # Bind per salvare resize della Treeview (considerata "tabella")
        try:
            self.tree_frame.bind("<Configure>", lambda e: self.on_column_configure("AlberoFrame", e.width))
        except Exception:
            pass

        # Right column frame (contiene due colonne verticali: Gestione lista e Extra affiancate)
        right_side_frame = ttk.Frame(mid, width=240)
        right_side_frame.grid(row=0, column=1, sticky="ns", padx=(8,0))
        self.right_side_frame = right_side_frame  # reference for layout persistence
        # Impediamo al grid di ridimensionare il frame destro oltre la larghezza impostata
        right_side_frame.grid_propagate(False)

        # Qui impiliamo due colonne (due frame affiancati) dentro right_side_frame usando pack con side=LEFT
        # Colonna 1: Gestione lista (verticale)
        col_gestione = ttk.Frame(right_side_frame)
        col_gestione.pack(side=tk.LEFT, fill=tk.Y, expand=False, padx=(0,6))
        section_lista = ttk.LabelFrame(col_gestione, text="Gestione lista", padding=(6,6))
        section_lista.pack(fill=tk.X, pady=(4,4))
        # Pulsanti disposti verticalmente
        ttk.Button(section_lista, text="Sposta ←", command=self.move_selected_up).pack(side=tk.TOP, padx=4, pady=4, fill=tk.X)
        ttk.Button(section_lista, text="Sposta →", command=self.move_selected_down).pack(side=tk.TOP, padx=4, pady=4, fill=tk.X)
        ttk.Button(section_lista, text="Porta ▲", command=self.move_selected_to_start).pack(side=tk.TOP, padx=4, pady=4, fill=tk.X)
        ttk.Button(section_lista, text="Porta ▼", command=self.move_selected_to_end).pack(side=tk.TOP, padx=4, pady=4, fill=tk.X)
        ttk.Button(section_lista, text="Sospeso", command=self.toggle_highlight_selected).pack(side=tk.TOP, padx=4, pady=4, fill=tk.X)
        ttk.Button(section_lista, text="Via o No ?", command=self.toggle_stop_selected).pack(side=tk.TOP, padx=4, pady=4, fill=tk.X)
        self.display_wait_btn = ttk.Button(section_lista, text=self.get_display_wait_text(), command=self.toggle_display_wait)
        self.display_wait_btn.pack(side=tk.TOP, padx=4, pady=4, fill=tk.X)
        tk.Button(section_lista, text="Svuota lista", command=self.clear_list, bg="red", fg="white").pack(side=tk.TOP, padx=4, pady=4, fill=tk.X)

        # Colonna 2: Extra (verticale), affiancata a Gestione lista
        col_extra = ttk.Frame(right_side_frame)
        col_extra.pack(side=tk.LEFT, fill=tk.Y, expand=False)
        section_extra = ttk.LabelFrame(col_extra, text="Extra", padding=(6,6))
        section_extra.pack(fill=tk.X, pady=(4,4))
        ttk.Button(section_extra, text="Legenda", command=self.toggle_legenda).pack(side=tk.TOP, padx=4, pady=4, fill=tk.X)
        ttk.Button(section_extra, text="Annuncio", command=self.annuncio_popup).pack(side=tk.TOP, padx=4, pady=4, fill=tk.X)
        # NUOVO BOTTONE: Video (apre popup per mostrare GIF animato o video)
        ttk.Button(section_extra, text="Video", command=self.toggle_video_popup).pack(side=tk.TOP, padx=4, pady=4, fill=tk.X)
        ttk.Button(section_extra, text="Prossimo Cantante", command=self.popup_prossimo_cantante).pack(side=tk.TOP, padx=4, pady=4, fill=tk.X)
        self.audio_btn = ttk.Button(section_extra, text=self.get_audio_btn_text(), command=self.toggle_audio)
        self.audio_btn.pack(side=tk.TOP, padx=4, pady=4, fill=tk.X)
        self.voice_var = tk.StringVar(value=ALL_VOICE_OPTIONS[0][0])
        self.voice_menu = ttk.Combobox(
            section_extra,
            textvariable=self.voice_var,
            values=[label for label, _, _, _ in ALL_VOICE_OPTIONS],
            state="readonly",
            width=30
        )
        self.voice_menu.pack(side=tk.TOP, padx=4, pady=4, fill=tk.X)
        self.voice_menu.bind("<<ComboboxSelected>>", self.on_voice_select)
        tk.Button(section_extra, text="Chiudi", command=self.on_close, bg="orange", fg="black").pack(side=tk.TOP, padx=4, pady=4, fill=tk.X)

        # Bind di configure per registrare resize delle "colonne di gestione" (anche i due frame destro)
        try:
            tree_frame.bind("<Configure>", lambda e: self.on_column_configure("AlberoFrame", e.width))
            col_gestione.bind("<Configure>", lambda e: self.on_column_configure("Gestione lista", e.width))
            col_extra.bind("<Configure>", lambda e: self.on_column_configure("Extra", e.width))
        except Exception:
            pass

        # --- NUOVA SEZIONE CANTANTI (ALLINEATA SOTTO 'Gestione lista') ---
        # Ora la LabelFrame "Cantanti" è figlia di col_gestione in modo da rimanere allineata sotto Gestione lista.
        cantanti_section = ttk.LabelFrame(col_gestione, text="Cantanti", padding=(6,6))
        cantanti_section.pack(side=tk.TOP, fill=tk.X, pady=(8, 4))

        # dentro cantanti_section creiamo due colonne affiancate (sinistra espandente, destra non espandente)
        cant_col_left = ttk.Frame(cantanti_section)
        cant_col_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,4))
        cant_col_right = ttk.Frame(cantanti_section)
        # destra non espandente per mantenere l'allineamento sotto Gestione lista
        cant_col_right.pack(side=tk.LEFT, fill=tk.Y, expand=False, padx=(4,0))

        # Left column buttons (Aggiungi, Modifica nome, Note)
        ttk.Button(cant_col_left, text="Aggiungi", command=self.add_person).pack(side=tk.TOP, padx=4, pady=4, fill=tk.X)
        ttk.Button(cant_col_left, text="Modifica nome", command=self.edit_selected_name).pack(side=tk.TOP, padx=4, pady=4, fill=tk.X)
        ttk.Button(cant_col_left, text="Note", command=self.edit_selected_note).pack(side=tk.TOP, padx=4, pady=4, fill=tk.X)

        # Right column buttons (Elimina, N° Canzoni)
        ttk.Button(cant_col_right, text="Elimina", command=self.delete_selected_name).pack(side=tk.TOP, padx=4, pady=4, fill=tk.X)
        ttk.Button(cant_col_right, text="N° Canzoni", command=self.edit_selected_songs).pack(side=tk.TOP, padx=4, pady=4, fill=tk.X)
        # ---------------------------------------------------------

        section_display = ttk.LabelFrame(frm, text="Display", padding=(6,6))
        section_display.pack(fill=tk.X, pady=(4, 8))
        font_label = ttk.Label(section_display, text="Font display:", font=self.control_font)
        font_label.pack(side=tk.LEFT, padx=4)
        self.display_font_size_var = tk.IntVar(value=self.display_font_size)
        font_spin = ttk.Spinbox(section_display, from_=8, to=72, textvariable=self.display_font_size_var, width=4, font=self.control_font)
        font_spin.pack(side=tk.LEFT, padx=4)
        self.display_font_bold_var = tk.BooleanVar(value=self.display_font_bold)
        bold_check = ttk.Checkbutton(
            section_display, text="Grassetto", variable=self.display_font_bold_var,
            command=self.update_display_font_style, style="TCheckbutton"
        )
        bold_check.pack(side=tk.LEFT, padx=4)
        righe_label = ttk.Label(section_display, text="Righe per pagina (display):", font=self.control_font)
        righe_label.pack(side=tk.LEFT, padx=(16, 4))
        self.display_max_rows_var = tk.IntVar(value=self.display_max_rows)
        rows_spin = ttk.Spinbox(section_display, from_=1, to=100, textvariable=self.display_max_rows_var, width=4, font=self.control_font)
        rows_spin.pack(side=tk.LEFT, padx=4)
        ttk.Button(section_display, text="Applica", command=self.apply_display_settings).pack(side=tk.LEFT, padx=8)
        btn_prev = ttk.Button(section_display, text="Pagina ←", command=self.prev_display_page)
        btn_prev.pack(side=tk.LEFT, padx=(0,2))
        self.page_label = ttk.Label(section_display, text="", font=self.control_font)
        self.page_label.pack(side=tk.LEFT, padx=2)
        btn_next = ttk.Button(section_display, text="Pagina →", command=self.next_display_page)
        btn_next.pack(side=tk.LEFT, padx=(2,0))
        self.legenda_window = None

    # Funzioni per gestione riproduzione / stop dei suoni
    def stop_current_play(self):
        """Ferma il suono in riproduzione (se possibile)."""
        try:
            if self.current_play_method == 'simpleaudio' and self.current_play_obj:
                try:
                    self.current_play_obj.stop()
                except Exception:
                    pass
            elif self.current_play_method == 'winsound' and WINSOUND_AVAILABLE:
                try:
                    # stop alla riproduzione winsound async
                    winsound.PlaySound(None, winsound.SND_PURGE)
                except Exception:
                    try:
                        winsound.PlaySound(None, winsound.SND_ASYNC)
                    except Exception:
                        pass
            elif self.current_play_method == 'playsound':
                # playsound non supporta stop — notifica l'utente
                # Non possiamo interrompere threads blocking di playsound in modo sicuro.
                # Mostriamo solo un messaggio informativo.
                print("Impossibile interrompere riproduzione (playsound non supporta stop).")
            # reset dello stato
            self.current_play_obj = None
            self.current_play_method = None
            self.current_sound_path = None
            self.playsound_thread = None
        except Exception as e:
            print("Errore stop suono:", e)
            self.current_play_obj = None
            self.current_play_method = None
            self.current_sound_path = None
            self.playsound_thread = None

    def start_play(self, path):
        """Avvia la riproduzione e memorizza stato per permettere lo stop successivo."""
        if not path or not os.path.exists(path):
            messagebox.showinfo("Audio non trovato", f"File audio non trovato: {path}\nControlla {SOUND_DEF_PATH}", parent=self.root)
            return
        # Prima ferma eventuale riproduzione attiva
        self.stop_current_play()
        try:
            lower = path.lower()
            # preferiamo simpleaudio per WAV (controllo stop)
            if SIMPLEAUDIO_AVAILABLE and lower.endswith(".wav"):
                try:
                    wave_obj = sa.WaveObject.from_wave_file(path)
                    play_obj = wave_obj.play()
                    self.current_play_obj = play_obj
                    self.current_play_method = 'simpleaudio'
                    self.current_sound_path = path
                    # thread non necessario; simpleaudio è non-blocking
                    return
                except Exception as e:
                    print("Errore simpleaudio:", e)
            # su Windows possiamo usare winsound per WAV (consente stop)
            if WINSOUND_AVAILABLE and lower.endswith(".wav"):
                try:
                    winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                    self.current_play_method = 'winsound'
                    self.current_sound_path = path
                    return
                except Exception as e:
                    print("Errore winsound:", e)
            # fallback: playsound (blocking) in thread — non stoppabile
            if playsound:
                def worker(p, app_self=self):
                    try:
                        app_self.current_play_method = 'playsound'
                        app_self.current_sound_path = p
                        playsound(p)
                    except Exception as e:
                        print("Errore playsound:", e)
                    finally:
                        # al termine, resetta stato solo se il file corrisponde
                        try:
                            if app_self.current_sound_path == p:
                                app_self.current_play_method = None
                                app_self.current_sound_path = None
                                app_self.playsound_thread = None
                        except Exception:
                            pass
                t = threading.Thread(target=worker, args=(path,), daemon=True)
                t.start()
                self.playsound_thread = t
                return
            # se arriviamo qui non abbiamo metodi di riproduzione
            messagebox.showinfo("Riproduzione non disponibile", "Nessun metodo disponibile per riprodurre l'audio (installare 'simpleaudio' o usare Windows).", parent=self.root)
        except Exception as e:
            print("Errore avvio riproduzione:", e)

    def reload_sound_defs(self):
        self.sound_defs = load_sound_defs()
        # aggiorna etichette e stati pulsanti
        for i in range(MAX_SOUND_BUTTONS):
            btn = self.sound_btns[i] if i < len(self.sound_btns) else None
            if not btn:
                continue
            if i < len(self.sound_defs):
                lbl = self.sound_defs[i].get("label", f"Suono {i+1}")
                btn.config(text=lbl, state="normal", command=(lambda j=i: self.on_sound_button(j)))
            else:
                btn.config(text="-", state="disabled", command=lambda: None)

    def on_sound_button(self, idx):
        """
        Se il pulsante corrisponde al file attualmente in riproduzione lo ferma.
        Altrimenti ferma eventuale riproduzione e avvia il nuovo file.
        """
        if idx < 0 or idx >= len(self.sound_defs):
            return
        sd = self.sound_defs[idx]
        fname = sd.get("file", "")
        path = resolve_sound_path(fname)
        if not path:
            messagebox.showinfo("Audio non trovato", f"File audio non trovato: {fname}\nControlla {SOUND_DEF_PATH}", parent=self.root)
            return
        # Se lo stesso file è in riproduzione -> stop
        if self.current_sound_path and os.path.abspath(path) == os.path.abspath(self.current_sound_path):
            self.stop_current_play()
            return
        # Altrimenti avvia la riproduzione (ferma prima eventuale precedente)
        self.start_play(path)

    def toggle_video_popup(self):
        """
        Se la popup video è aperta la chiude; altrimenti la apre.
        Questo permette di premere più volte il bottone Video per chiudere/aprire.
        """
        try:
            if self.video_popup_window and self.video_popup_window.winfo_exists():
                try:
                    # chiudi la finestra esistente
                    self.video_popup_window.destroy()
                except Exception:
                    pass
                self.video_popup_window = None
                return
        except Exception:
            # fallback: nessuna popup valida
            self.video_popup_window = None
        # apri una nuova popup
        self.video_popup()

    def on_voice_select(self, event=None):
        global CURRENT_TTS_LANGUAGE, CURRENT_TTS_GENDER, CURRENT_TTS_ENGINE, CURRENT_PYTTSX3_VOICE_ID
        idx = self.voice_menu.current()
        if idx >= 0:
            label, id_or_lang, gender, engine = ALL_VOICE_OPTIONS[idx]
            if engine == "gtts":
                CURRENT_TTS_LANGUAGE = id_or_lang
                CURRENT_TTS_GENDER = gender
                CURRENT_TTS_ENGINE = "gtts"
                CURRENT_PYTTSX3_VOICE_ID = None
            elif engine == "pyttsx3":
                CURRENT_TTS_ENGINE = "pyttsx3"
                CURRENT_PYTTSX3_VOICE_ID = id_or_lang

    def get_display_wait_text(self):
        return "Attesa Si" if self.display_show_wait else "Attesa No"

    def get_audio_btn_text(self):
        if not GTTS_AVAILABLE and not PYTTSX3_AVAILABLE:
            return "Audio non disponibile"
        return "Audio ON" if AUDIO_ENABLED else "Audio OFF"

    def toggle_audio(self):
        global AUDIO_ENABLED
        if not GTTS_AVAILABLE and not PYTTSX3_AVAILABLE:
            messagebox.showinfo("Audio", "Sintesi vocale non disponibile (gTTS/pyttsx3 non installato).")
            return
        AUDIO_ENABLED = not AUDIO_ENABLED
        self.audio_btn.config(text=self.get_audio_btn_text())

    def toggle_display_wait(self):
        self.display_show_wait = not self.display_show_wait
        self.display_wait_btn.config(text=self.get_display_wait_text())
        self.display.refresh_display_table()

    def toggle_legenda(self):
        if self.legenda_window and self.legenda_window.winfo_exists():
            self.legenda_window.destroy()
            self.legenda_window = None
        else:
            self.legenda_window = tk.Toplevel(self.root)
            self.legenda_window.title("Legenda colori canzoni")
            self.legenda_window.geometry("600x120")
            self.legenda_window.minsize(400, 80)
            self.legenda_window.resizable(True, True)
            gradient_colors = [
                ("#00FF00", "0"),
                ("#FFFF00", "1"),
                ("#00FFFF", "2"),
                ("#FF00FF", "3"),
                ("#FF0000", "4"),
                ("#FF8000", "5"),
                ("#00FFEA", "6"),
            ]
            sospeso_color = "#CCCCCC"
            frame = tk.Frame(self.legenda_window)
            frame.pack(expand=True, fill=tk.BOTH, padx=8, pady=8)
            self.legenda_boxes = []
            for i, (color, numero) in enumerate(gradient_colors):
                box = tk.Frame(frame, bg=color, bd=2, relief="ridge")
                label = tk.Label(box, text=numero, bg=color, fg="black", font=("Arial", 13, "bold"))
                label.place(relx=0.5, rely=0.5, anchor="center")
                box.grid(row=0, column=i, padx=4, pady=4, sticky="nsew")
                box.grid_propagate(False)
                frame.grid_columnconfigure(i, weight=1, uniform="color")
                self.legenda_boxes.append(box)
            sospeso_idx = len(gradient_colors)
            box_sosp = tk.Frame(frame, bg=sospeso_color, bd=2, relief="ridge")
            label_s = tk.Label(box_sosp, text="S", bg=sospeso_color, fg="black", font=("Arial", 13, "bold"))
            label_s.place(relx=0.5, rely=0.5, anchor="center")
            box_sosp.grid(row=0, column=sospeso_idx, padx=4, pady=4, sticky="nsew")
            box_sosp.grid_propagate(False)
            frame.grid_columnconfigure(sospeso_idx, weight=1, uniform="color")
            self.legenda_boxes.append(box_sosp)
            def resize_boxes(event):
                w = event.width
                h = event.height
                n = len(self.legenda_boxes)
                box_w = max(30, int(w / n) - 8)
                box_h = max(28, h - 16)
                for b in self.legenda_boxes:
                    b.config(width=box_w, height=box_h)
            frame.bind("<Configure>", resize_boxes)
            self.legenda_window.protocol("WM_DELETE_WINDOW", self.toggle_legenda)

    def on_tree_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell":
            col = self.tree.identify_column(event.x)
            if col == "#6":
                sel = self.tree.identify_row(event.y)
                if sel:
                    idx = self.find_index_by_id(sel)
                    self.toggle_stop(idx)

    def on_tree_double_click(self, event):
        sel = self.tree.selection()
        if sel:
            self.edit_selected_name()

    def toggle_stop_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Seleziona una persona.")
            return
        iid = sel[0]
        idx = self.find_index_by_id(iid)
        if idx is not None:
            self.toggle_stop(idx)

    def toggle_stop(self, idx):
        if idx is None:
            return
        self.items[idx]["stopped"] = not self.items[idx].get("stopped", False)
        self.data_modified = True
        self.save_data_to_listdata()
        self.refresh_trees()
        iid = str(self.items[idx]["num"])
        self.tree.selection_set(iid)
        self.tree.see(iid)

    def apply_display_settings(self):
        self.update_display_font_size()
        self.update_display_max_rows()

    def update_display_font_size(self):
        new_size = self.display_font_size_var.get()
        if new_size < 8:
            new_size = 8
        if new_size > 72:
            new_size = 72
        self.display_font_size = new_size
        self.update_display_font_style()

    def update_display_font_style(self):
        self.display_font_bold = self.display_font_bold_var.get()
        weight = "bold" if self.display_font_bold else "normal"
        self.display_font = font.Font(size=self.display_font_size, weight=weight)
        self.display.refresh_display_table()

    def update_display_max_rows(self):
        n = self.display_max_rows_var.get()
        if n < 1:
            n = 1
        self.display_max_rows = n
        self.display_page = 0
        self.display.refresh_display_table()

    def prev_display_page(self):
        if self.display_page > 0:
            self.display_page -= 1
            self.display.refresh_display_table()

    def next_display_page(self):
        max_page = max(0, (len([it for it in self.items if not it.get("stopped")]) - 1) // self.display_max_rows)
        if self.display_page < max_page:
            self.display_page += 1
            self.display.refresh_display_table()

    def build_display_window(self):
        self.display = WindowDisplay(tk.Toplevel(self.root), self)

    def refresh_trees(self):
        try:
            self.tree.delete(*self.tree.get_children())
            for it in self.items:
                iid = str(it["num"])
                att = self.compute_wait_text_for_item(it)
                note = it.get("note", "")
                songs = it.get("songs", 0)
                stop_text = "STOP" if it.get("stopped") else ""
                tags = ()
                if it.get("highlighted"):
                    tags += ("highlighted",)
                if it.get("stopped"):
                    tags += ("stopped",)
                color_tag = f"song_color_{songs}"
                self.tree.tag_configure(color_tag, background=song_color(songs))
                tags += (color_tag,)
                self.tree.insert(
                    "", "end", iid=iid,
                    values=(it["num"], it["name"], att, note, songs, stop_text), tags=tags
                )
        except Exception:
            pass
        self.display.refresh_display_table()

    def find_index_by_id(self, id_):
        sid = str(id_)
        for idx, it in enumerate(self.items):
            if str(it.get("num")) == sid:
                return idx
        return None

    def compute_wait_text_for_item(self, item):
        try:
            idx = self.find_index_by_id(item["num"])
            if idx is None:
                return "-"
            if item.get("highlighted"):
                return "-"
            if item.get("stopped"):
                return "-"
            secs = 0
            for i in range(idx):
                # CORRETTO: controllo senza virgolette errate
                if not self.items[i].get("highlighted") and not self.items[i].get("stopped"):
                    secs += self.items[i].get("wait_sec", 210)
            return format_seconds(secs)
        except Exception:
            return "-"

    def add_person(self):
        name = self.name_var.get().strip()
        note = self.note_var.get().strip()
        songs = self.songs_var.get() if self.songs_var else 0
        if not name:
            messagebox.showwarning("Attenzione", "Inserire un nome.")
            return
        max_num = max([item["num"] for item in self.items], default=0)
        new_num = max_num + 1
        random_wait_sec = random.randint(210, 270)
        new_item = {
            "num": new_num,
            "name": name,
            "highlighted": False,
            "note": note,
            "stopped": False,
            "wait_sec": random_wait_sec,
            "songs": songs
        }
        insert_pos = None
        for idx, item in enumerate(self.items):
            if item["num"] == max_num:
                insert_pos = idx + 1
        if insert_pos is None:
            self.items.append(new_item)
        else:
            self.items.insert(insert_pos, new_item)
        self.next_id = new_num + 1
        self.name_var.set("")
        self.note_var.set("")
        self.songs_var.set(0)
        self.data_modified = True
        self.save_data_to_listdata()
        self.refresh_trees()

    def edit_selected_name(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Selezionare una persona da modificare.")
            return
        iid = sel[0]
        idx = self.find_index_by_id(iid)
        if idx is None:
            return
        old = self.items[idx]["name"]
        new = simpledialog.askstring("Modifica nome", "Inserisci nuovo nome:", initialvalue=old, parent=self.root)
        if new is None:
            return
        new = new.strip()
        if new == "":
            messagebox.showwarning("Attenzione", "Nome non valido.")
            return
        self.items[idx]["name"] = new
        self.data_modified = True
        self.save_data_to_listdata()
        self.refresh_trees()

    def edit_selected_note(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Selezionare una persona da modificare.")
            return
        iid = sel[0]
        idx = self.find_index_by_id(iid)
        if idx is None:
            return
        old = self.items[idx].get("note", "")
        new = simpledialog.askstring("Modifica note", "Inserisci nuova nota:", initialvalue=old, parent=self.root)
        if new is None:
            return
        new = new.strip()
        self.items[idx]["note"] = new
        self.data_modified = True
        self.save_data_to_listdata()
        self.refresh_trees()

    def edit_selected_songs(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Selezionare una persona da modificare.")
            return
        iid = sel[0]
        idx = self.find_index_by_id(iid)
        if idx is None:
            return
        old = self.items[idx].get("songs", 0)
        new = simpledialog.askinteger("Modifica numero canzoni", "Numero di canzoni (0-6):", initialvalue=old, minvalue=0, maxvalue=6, parent=self.root)
        if new is None:
            return
        self.items[idx]["songs"] = max(0, min(6, new))
        self.data_modified = True
        self.save_data_to_listdata()
        self.refresh_trees()

    def delete_selected_name(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Selezionare una persona da eliminare.")
            return
        iid = sel[0]
        idx = self.find_index_by_id(iid)
        if idx is not None:
            nome = self.items[idx]["name"]
            if messagebox.askyesno("Conferma eliminazione", f"Eliminare '{nome}' dalla lista?"):
                del self.items[idx]
                self.data_modified = True
                self.save_data_to_listdata()
                self.refresh_trees()

    def move_selected_up(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Seleziona una persona.")
            return
        iid = sel[0]
        idx = self.find_index_by_id(iid)
        if idx is None or idx == 0:
            return
        self.items[idx - 1], self.items[idx] = self.items[idx], self.items[idx - 1]
        self.data_modified = True
        self.save_data_to_listdata()
        self.refresh_trees()
        self.tree.selection_set(iid)
        self.tree.see(iid)

    def move_selected_down(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Seleziona una persona.")
            return
        iid = sel[0]
        idx = self.find_index_by_id(iid)
        if idx is None or idx >= len(self.items) - 1:
            return
        self.items[idx + 1], self.items[idx] = self.items[idx], self.items[idx + 1]
        self.data_modified = True
        self.save_data_to_listdata()
        self.refresh_trees()
        self.tree.selection_set(iid)
        self.tree.see(iid)

    def move_selected_to_start(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Seleziona una persona.")
            return
        iid = sel[0]
        idx = self.find_index_by_id(iid)
        if idx is None or idx == 0:
            return
        it = self.items.pop(idx)
        self.items.insert(0, it)
        self.data_modified = True
        self.save_data_to_listdata()
        self.refresh_trees()
        self.tree.selection_set(iid)
        self.tree.see(iid)

    def move_selected_to_end(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Seleziona una persona.")
            return
        iid = sel[0]
        idx = self.find_index_by_id(iid)
        if idx is None or idx == len(self.items) - 1:
            return
        it = self.items.pop(idx)
        self.items.append(it)
        self.data_modified = True
        self.save_data_to_listdata()
        self.refresh_trees()
        self.tree.selection_set(iid)
        self.tree.see(iid)

    def toggle_highlight_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Seleziona una persona.")
            return
        iid = sel[0]
        idx = self.find_index_by_id(iid)
        if idx is None:
            return
        self.items[idx]["highlighted"] = not self.items[idx].get("highlighted", False)
        self.data_modified = True
        self.save_data_to_listdata()
        self.refresh_trees()
        self.tree.selection_set(iid)
        self.tree.see(iid)

    def clear_list(self):
        if not self.items and self.next_id == 1:
            return
        if messagebox.askyesno("Conferma", "Svuotare completamente la lista e azzerare il contatore?"):
            backup_waiting_list()
            self.items = []
            self.next_id = 1
            self.data_modified = True
            self.save_data_to_listdata()
            self.refresh_trees()

    def call_next(self):
        sel = self.tree.selection()
        if not sel:
            self.show_auto_close_popup("Seleziona una persona dalla lista.")
            return
        iid = sel[0]
        idx = self.find_index_by_id(iid)
        if idx is None:
            self.show_auto_close_popup("Selezione non valida.")
            return
        person = self.items[idx]
        testo = f"Prossimo:\n\n#{person['num']} - {person['name']}"
        self.show_auto_close_popup(testo)

    def annuncio_popup(self):
        msg = simpledialog.askstring("Annuncio", "Inserisci il messaggio da annunciare:", parent=self.root)
        if not msg:
            return
        self.show_auto_close_popup(msg, title="Annuncio")
        if AUDIO_ENABLED:
            pronuncia_testo(msg, self)

    def show_auto_close_popup(self, testo, title="Prossimo"):
        popup_width = 600
        popup_height = 280
        saved_x, saved_y = load_annuncio_position()
        if saved_x is not None and saved_y is not None:
            xpos, ypos = saved_x, saved_y
        else:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            xpos = int((sw - popup_width) / 2)
            ypos = int((sh - popup_height) / 2)
        popup = tk.Toplevel(self.root)
        popup.title(title)
        popup.geometry(f"{popup_width}x{popup_height}+{xpos}+{ypos}")
        popup.attributes('-topmost', True)
        big_font = font.Font(size=38, weight="bold")
        if title == "Annuncio" or title == "Messaggio":
            bg = "#FFCCCC"
        else:
            bg = "#CCE3FF"
        lbl = tk.Label(popup, text=testo, font=big_font, wraplength=550, justify="center", bg=bg, fg="black")
        lbl.pack(expand=True, fill=tk.BOTH, padx=15, pady=15)
        popup.after(10000, popup.destroy)
        def on_configure(event):
            if event.widget == popup:
                try:
                    geo = popup.geometry()
                    parts = geo.split('+')
                    if len(parts) == 3:
                        pos_x = int(parts[1])
                        pos_y = int(parts[2])
                        save_annuncio_position(pos_x, pos_y)
                except Exception:
                    pass
        popup.bind('<Configure>', on_configure)

    def video_popup(self):
        # Chiede all'utente di caricare un file GIF animato o un video.
        filetypes = [
            ("GIF animate", "*.gif"),
            ("Video files", "*.mp4;*.avi;*.mov;*.mkv"),
            ("All files", "*.*")
        ]
        path = filedialog.askopenfilename(title="Seleziona un file GIF o Video", filetypes=filetypes, parent=self.root)
        if not path:
            return

        popup_width = 800
        popup_height = 600
        saved_x, saved_y, saved_w, saved_h = load_video_position()
        if saved_x is not None and saved_y is not None and saved_w is not None and saved_h is not None:
            xpos, ypos, width, height = saved_x, saved_y, saved_w, saved_h
        else:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            xpos = int((sw - popup_width) / 2)
            ypos = int((sh - popup_height) / 2)
            width, height = popup_width, popup_height

        ext = os.path.splitext(path)[1].lower()

        # Default background for popup
        popup_bg = "#FFFFFF"

        # If it's a GIF and Pillow is available, try to detect GIF background color and use it
        if ext == ".gif":
            try:
                from PIL import Image, ImageSequence as _ImageSequence
                img = Image.open(path)
                bg_hex = None
                # 1) check palette background index
                try:
                    bg_index = img.info.get("background", None)
                    pal = img.getpalette()
                    if bg_index is not None and pal:
                        idx = int(bg_index)
                        if idx * 3 + 2 < len(pal):
                            r = pal[idx * 3]
                            g = pal[idx * 3 + 1]
                            b = pal[idx * 3 + 2]
                            bg_hex = f"#{r:02x}{g:02x}{b:02x}"
                except Exception:
                    bg_hex = None
                # 2) check explicit background info stored as tuple/list
                if not bg_hex:
                    try:
                        bg_info = img.info.get("background", None)
                        if isinstance(bg_info, (tuple, list)) and len(bg_info) >= 3:
                            r, g, b = bg_info[:3]
                            bg_hex = f"#{r:02x}{g:02x}{b:02x}"
                    except Exception:
                        pass
                # 3) sample a corner pixel from first frame (top-left) as fallback
                if not bg_hex:
                    try:
                        first_frame = next(_ImageSequence.Iterator(img))
                        pix = first_frame.convert("RGBA").getpixel((0, 0))
                        r, g, b = pix[:3]
                        bg_hex = f"#{r:02x}{g:02x}{b:02x}"
                    except Exception:
                        bg_hex = None
                if bg_hex:
                    popup_bg = bg_hex
            except Exception:
                # If anything fails, keep default white
                popup_bg = "#FFFFFF"
        else:
            # For non-GIF (video) keep a neutral black background
            popup_bg = "#000000"

        popup = tk.Toplevel(self.root)
        popup.title("Animazione Video")
        popup.geometry(f"{width}x{height}+{xpos}+{ypos}")
        popup.attributes('-topmost', True)

        # Keep a reference so toggle can close it
        self.video_popup_window = popup

        # Imposta lo sfondo della popup sul colore rilevato dalla GIF (o fallback)
        try:
            popup.configure(bg=popup_bg)
        except Exception:
            popup.configure(bg="#FFFFFF")

        container = tk.Frame(popup, bg=popup_bg)
        container.pack(expand=True, fill=tk.BOTH)

        # Label che conterrà le immagini (frame GIF o frame video)
        display_label = tk.Label(container, bg=popup_bg)
        display_label.pack(expand=True, fill=tk.BOTH)

        # Flag per interrompere l'animazione quando la popup viene chiusa
        playback_state = {"running": True, "after_id": None}

        def on_popup_close():
            # salva geometria corrente (posizione + dimensione) prima di chiudere
            try:
                px = popup.winfo_x()
                py = popup.winfo_y()
                pw = popup.winfo_width()
                ph = popup.winfo_height()
                save_video_position(px, py, pw, ph)
            except Exception:
                pass
            playback_state["running"] = False
            try:
                if playback_state.get("after_id"):
                    popup.after_cancel(playback_state["after_id"])
            except Exception:
                pass
            try:
                popup.destroy()
            except Exception:
                pass
            # assicurati di resettare il riferimento alla popup in app
            try:
                if getattr(self, "video_popup_window", None) is popup:
                    self.video_popup_window = None
            except Exception:
                self.video_popup_window = None

        popup.protocol("WM_DELETE_WINDOW", on_popup_close)

        def on_configure(event):
            # Quando la finestra viene spostata/ridimensionata aggiorna anche il file (debounced non implementato,
            # ma salvataggio è leggero)
            if event.widget == popup:
                try:
                    geo = popup.geometry()
                    parts = geo.split('+')
                    if len(parts) == 3:
                        pos_x = int(parts[1])
                        pos_y = int(parts[2])
                        # usa dimensione attuale della finestra
                        w = popup.winfo_width()
                        h = popup.winfo_height()
                        save_video_position(pos_x, pos_y, w, h)
                except Exception:
                    pass

        popup.bind('<Configure>', on_configure)

        try:
            if ext == ".gif":
                # Preferisci usare Pillow per preservare la trasparenza della GIF compositandola sullo sfondo del popup.
                pil_available = False
                try:
                    from PIL import Image, ImageTk, ImageSequence
                    pil_available = True
                except Exception:
                    pil_available = False

                if pil_available:
                    try:
                        img = Image.open(path)
                    except Exception:
                        messagebox.showerror("Errore", "Impossibile aprire la GIF con Pillow.", parent=popup)
                        # salva geometria anche in caso di errore
                        on_popup_close()
                        return

                    frames_tk = []
                    durations = []
                    # popup_bg (hex) -> RGBA tuple
                    try:
                        if isinstance(popup_bg, str) and popup_bg.startswith("#") and len(popup_bg) == 7:
                            r = int(popup_bg[1:3], 16)
                            g = int(popup_bg[3:5], 16)
                            b = int(popup_bg[5:7], 16)
                            bg_rgba = (r, g, b, 255)
                        else:
                            bg_rgba = (255, 255, 255, 255)
                    except Exception:
                        bg_rgba = (255, 255, 255, 255)

                    # carica frames preservando trasparenza e compositando sul background del popup
                    try:
                        for frame in ImageSequence.Iterator(img):
                            duration = frame.info.get("duration", 100)
                            durations.append(duration)
                            if frame.mode != "RGBA":
                                frame_rgba = frame.convert("RGBA")
                            else:
                                frame_rgba = frame.copy()
                            # composita su background dell'area del frame
                            bg = Image.new("RGBA", frame_rgba.size, bg_rgba)
                            composed = Image.alpha_composite(bg, frame_rgba)
                            frames_tk.append(composed)
                    except Exception:
                        frames_tk = []
                        durations = []

                    if not frames_tk:
                        # Fallback non-Pillow: usa PhotoImage come prima
                        frames = []
                        i = 0
                        try:
                            while True:
                                frame = tk.PhotoImage(file=path, format=f"gif -index {i}")
                                frames.append(frame)
                                i += 1
                        except Exception:
                            pass
                        if not frames:
                            messagebox.showerror("Errore", "Impossibile caricare la GIF.", parent=popup)
                            on_popup_close()
                            return

                        def animate_gif_fallback(idx=0):
                            if not playback_state["running"]:
                                return
                            try:
                                frame = frames[idx % len(frames)]
                                display_label.config(image=frame, bg=popup_bg)
                                display_label.image = frame
                                playback_state["after_id"] = popup.after(100, lambda: animate_gif_fallback(idx + 1))
                            except Exception:
                                pass

                        animate_gif_fallback()
                        popup.after(15000, on_popup_close)
                        return

                    # Converti i PIL Image composti in ImageTk.PhotoImage (ridimensionando dinamicamente e adattando ALL'AREA della popup mantenendo PROPORZIONI)
                    pil_frames_photo = []

                    def prepare_photo_images():
                        pil_frames_photo.clear()
                        # usa la dimensione effettiva della label che mostra l'immagine (questo permette di adattare esattamente all'area visibile)
                        cw = display_label.winfo_width() or popup.winfo_width() or width
                        ch = display_label.winfo_height() or popup.winfo_height() or height
                        # assicurati valori minimi validi
                        max_w = max(1, cw)
                        max_h = max(1, ch)
                        for pil_img in frames_tk:
                            pw, ph = pil_img.size
                            # calcola ratio per adattare esattamente all'area disponibile mantenendo proporzioni
                            try:
                                ratio = min(max_w / pw, max_h / ph)
                                if ratio <= 0:
                                    ratio = 1.0
                                # limita upscaling se definito
                                if MAX_UPSCALE and ratio > MAX_UPSCALE:
                                    ratio = MAX_UPSCALE
                            except Exception:
                                ratio = 1.0
                            new_w = max(1, int(pw * ratio))
                            new_h = max(1, int(ph * ratio))
                            if new_w != pw or new_h != ph:
                                # usa resample compatibile se disponibile
                                try:
                                    resized = pil_img.resize((new_w, new_h), resample=RESAMPLE_LANCZOS)
                                except Exception:
                                    resized = pil_img.resize((new_w, new_h))
                            else:
                                resized = pil_img
                            # ImageTk.PhotoImage non supporta alpha completo con tkinter background, quindi abbiamo già compositato il bg
                            tkimg = ImageTk.PhotoImage(resized.convert("RGB"))
                            pil_frames_photo.append(tkimg)

                    # animazione usando le durate originali (in ms)
                    def animate_pil_gif(idx=0):
                        if not playback_state["running"]:
                            return
                        if not pil_frames_photo:
                            prepare_photo_images()
                        try:
                            frame_idx = idx % len(pil_frames_photo)
                            tkimg = pil_frames_photo[frame_idx]
                            display_label.config(image=tkimg, bg=popup_bg)
                            display_label.image = tkimg
                            duration = durations[frame_idx] if frame_idx < len(durations) else 100
                            # durata minima per evitare 0
                            delay = max(20, int(duration))
                            playback_state["after_id"] = popup.after(delay, lambda: animate_pil_gif(idx + 1))
                        except Exception:
                            pass

                    # ricalcola immagini quando la finestra viene ridimensionata per mantenere adattamento
                    def on_resize_rebuild(event):
                        # ricalcola solo se l'evento riguarda la popup o la label
                        if event.widget in (popup, display_label):
                            try:
                                # pulisci cache e ricostruisci con le nuove dimensioni
                                prepare_photo_images()
                            except Exception:
                                pass

                    popup.bind("<Configure>", on_resize_rebuild)
                    display_label.bind("<Configure>", on_resize_rebuild)
                    # avvia l'animazione
                    animate_pil_gif()
                    popup.after(15000, on_popup_close)
                    return

                else:
                    # Se Pillow non è disponibile, mantieni il comportamento precedente con tk.PhotoImage
                    frames = []
                    i = 0
                    try:
                        while True:
                            frame = tk.PhotoImage(file=path, format=f"gif -index {i}")
                            frames.append(frame)
                            i += 1
                    except Exception:
                        pass
                    if not frames:
                        messagebox.showerror("Errore", "Impossibile caricare la GIF.", parent=popup)
                        on_popup_close()
                        return

                    def animate_gif(idx=0):
                        if not playback_state["running"]:
                            return
                        try:
                            frame = frames[idx % len(frames)]
                            display_label.config(image=frame, bg=popup_bg)
                            display_label.image = frame
                            playback_state["after_id"] = popup.after(100, lambda: animate_gif(idx + 1))
                        except Exception:
                            pass

                    animate_gif()
                    popup.after(15000, on_popup_close)
                    return

            else:
                # Tentativo di riprodurre video con imageio + Pillow (se disponibili)
                if not IMAGEIO_AVAILABLE:
                    messagebox.showinfo("Riproduzione video non disponibile",
                                        "Per riprodurre video sono necessari i pacchetti 'imageio' e 'Pillow' (installare con pip). "
                                        "Al momento è possibile riprodurre solo GIF animate.",
                                        parent=popup)
                    popup.after(4000, on_popup_close)
                    return

                try:
                    reader = imageio.get_reader(path)
                except Exception as e:
                    messagebox.showerror("Errore apertura video", f"Impossibile aprire il file video: {e}", parent=popup)
                    on_popup_close()
                    return

                meta = {}
                try:
                    meta = reader.get_meta_data()
                except Exception:
                    meta = {}
                fps = meta.get("fps", None) or meta.get("fps", 24)
                delay_ms = int(1000 / fps) if fps > 0 else 40

                # Funzione per iterare i frames in after loop (mostrati come ImageTk)
                frame_iter = reader.iter_data()
                pil_images_cache = []

                # Calcola bg_rgba dal popup background per compositing
                try:
                    bg_color = popup_bg
                    if isinstance(bg_color, str) and bg_color.startswith("#") and len(bg_color) == 7:
                        br = int(bg_color[1:3], 16)
                        bg = int(bg_color[3:5], 16)
                        bb = int(bg_color[5:7], 16)
                        video_bg_rgba = (br, bg, bb, 255)
                    else:
                        video_bg_rgba = (0, 0, 0, 255)
                except Exception:
                    video_bg_rgba = (0, 0, 0, 255)

                def play_video_frame():
                    if not playback_state["running"]:
                        try:
                            reader.close()
                        except Exception:
                            pass
                        return
                    try:
                        frame = next(frame_iter)
                    except StopIteration:
                        # Fine del video: chiudi popup
                        try:
                            reader.close()
                        except Exception:
                            pass
                        on_popup_close()
                        return
                    except Exception:
                        try:
                            reader.close()
                        except Exception:
                            pass
                        on_popup_close()
                        return
                    try:
                        # frame è un ndarray; converti in PIL Image
                        pil = Image.fromarray(frame)
                        # converti ad RGBA e composita sul nostro colore di sfondo (in modo che il colore risulti coerente con la GIF)
                        if pil.mode != "RGBA":
                            pil_rgba = pil.convert("RGBA")
                        else:
                            pil_rgba = pil
                        bgimage = Image.new("RGBA", pil_rgba.size, video_bg_rgba)
                        composed = Image.alpha_composite(bgimage, pil_rgba)
                        pil = composed
                        # ridimensiona mantenendo aspect ratio per adattarsi al popup (consentendo upscaling fino a MAX_UPSCALE)
                        pw, ph = pil.size
                        # usa dimensione effettiva della label/area
                        cw = display_label.winfo_width() or popup.winfo_width() or width
                        ch = display_label.winfo_height() or popup.winfo_height() or height
                        max_w = max(1, cw)
                        max_h = max(1, ch)
                        try:
                            ratio = min(max_w / pw, max_h / ph)
                            if ratio <= 0:
                                ratio = 1.0
                            if MAX_UPSCALE and ratio > MAX_UPSCALE:
                                ratio = MAX_UPSCALE
                        except Exception:
                            ratio = 1.0
                        new_w = max(1, int(pw * ratio))
                        new_h = max(1, int(ph * ratio))
                        if new_w != pw or new_h != ph:
                            try:
                                pil = pil.resize((new_w, new_h), resample=RESAMPLE_LANCZOS)
                            except Exception:
                                pil = pil.resize((new_w, new_h))
                        tkimg = ImageTk.PhotoImage(pil.convert("RGB"))
                        display_label.config(image=tkimg, bg=popup_bg)
                        display_label.image = tkimg
                    except Exception:
                        pass
                    playback_state["after_id"] = popup.after(delay_ms, play_video_frame)

                # Avvia riproduzione (in main thread via after)
                play_video_frame()
                return

        except Exception as e:
            messagebox.showerror("Errore", f"Errore durante la riproduzione: {e}", parent=popup)
            on_popup_close()
            return

    def popup_prossimo_cantante(self):
        sel = self.tree.selection()
        if not sel:
            self.show_auto_close_popup("Seleziona una persona dalla lista.", title="Prossimo Cantante")
            return
        iid = sel[0]
        idx = self.find_index_by_id(iid)
        if idx is None:
            self.show_auto_close_popup("Selezione non valida.", title="Prossimo Cantante")
            return
        person = self.items[idx]
        nome = person.get("name", "")
        testo = f"Prossimo Cantante\n\n{nome}"
        self.show_auto_close_popup(testo, title="Prossimo Cantante")
        if (GTTS_AVAILABLE or PYTTSX3_AVAILABLE) and AUDIO_ENABLED:
            frase_audio = f"Il prossimo cantante è {nome}"
            pronuncia_testo(frase_audio, self)

    def on_close(self):
        try:
            if self.data_modified:
                self.save_data_to_listdata()
            try:
                # se la popup video è aperta, chiudila prima di uscire
                if getattr(self, "video_popup_window", None) and getattr(self.video_popup_window, "winfo_exists", lambda: False)():
                    try:
                        self.video_popup_window.destroy()
                    except Exception:
                        pass
                    self.video_popup_window = None
            except Exception:
                pass
            # stop eventuale suono in riproduzione prima di uscire
            try:
                self.stop_current_play()
            except Exception:
                pass
            try:
                # salva immediatamente layout pendente
                if self._layout_save_after_id:
                    try:
                        self.root.after_cancel(self._layout_save_after_id)
                    except Exception:
                        pass
                    self._layout_save_after_id = None
                self.save_layout_file()
            except Exception:
                pass
            try:
                self.display.root.destroy()
            except Exception:
                pass
            self.root.quit()
            self.root.destroy()
        except Exception:
            try:
                self.root.destroy()
            except Exception:
                pass

def main():
    root = tk.Tk()
    app = WaitingListApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()