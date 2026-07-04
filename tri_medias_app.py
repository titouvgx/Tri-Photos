"""
tri_medias_app.py - V2.0 GUI
Interface graphique pour trier photos et vidéos par Année > Mois,
avec option de tri par Auteur puis par Date.

Compilation en .exe :
    pip install pyinstaller pillow pillow-heif piexif
    pyinstaller --onefile --windowed --name "Tri Médias" tri_medias_app.py
"""

import json
import re
import shutil
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "Pillow"], check=False)
    from PIL import Image
    from PIL.ExifTags import TAGS

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC_SUPPORTE = True
except ImportError:
    HEIC_SUPPORTE = False

try:
    import piexif
    PIEXIF_SUPPORTE = True
except ImportError:
    PIEXIF_SUPPORTE = False

# -------------------------------------------------------
# FORMATS SUPPORTÉS
# -------------------------------------------------------
EXTENSIONS_IMAGES = {
    ".jpg", ".jpeg", ".png", ".heic", ".heif", ".bmp", ".gif",
    ".tiff", ".tif", ".webp", ".raw", ".cr2", ".cr3", ".nef",
    ".arw", ".orf", ".rw2", ".dng", ".pef", ".srw", ".raf"
}
EXTENSIONS_VIDEOS = {
    ".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".m4v",
    ".3gp", ".mpg", ".mpeg", ".mts", ".m2ts", ".ts", ".webm",
    ".vob", ".ogv", ".divx"
}
EXTENSIONS_SUPPORTEES = EXTENSIONS_IMAGES | EXTENSIONS_VIDEOS

MOIS = {
    1: "01 - Janvier",   2: "02 - Février",  3: "03 - Mars",
    4: "04 - Avril",     5: "05 - Mai",       6: "06 - Juin",
    7: "07 - Juillet",   8: "08 - Août",      9: "09 - Septembre",
    10: "10 - Octobre", 11: "11 - Novembre", 12: "12 - Décembre",
}

# -------------------------------------------------------
# COULEURS
# -------------------------------------------------------
BG      = "#0f0f0f"
BG2     = "#1a1a1a"
BG3     = "#242424"
ACCENT  = "#4f8ef7"
ACCENT2 = "#3a6fd4"
SUCCESS = "#3ecf73"
WARNING = "#f5a623"
DANGER  = "#f75f5f"
TEXT    = "#f0f0f0"
TEXT2   = "#999999"
BORDER  = "#2e2e2e"

# -------------------------------------------------------
# CHEMIN DU JSON DE MAPPING
# -------------------------------------------------------
def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent

MAPPING_PATH = _base_dir() / "auteurs_mapping.json"


def charger_mapping() -> dict:
    if MAPPING_PATH.exists():
        try:
            with open(MAPPING_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def sauvegarder_mapping(mapping: dict):
    with open(MAPPING_PATH, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)


# -------------------------------------------------------
# LOGIQUE DE TRI — DATE (inchangée)
# -------------------------------------------------------
def get_date_exif(filepath: Path) -> datetime | None:
    try:
        with Image.open(filepath) as img:
            exif_data = img._getexif()
            if not exif_data:
                return None
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag in ("DateTimeOriginal", "DateTime", "DateTimeDigitized"):
                    return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None
    return None


def get_date(filepath: Path) -> tuple[datetime, bool]:
    if filepath.suffix.lower() in EXTENSIONS_IMAGES:
        date = get_date_exif(filepath)
        if date:
            return date, True
    return datetime.fromtimestamp(filepath.stat().st_mtime), False


def deja_copie(source: Path, cible: Path) -> bool:
    return cible.exists() and cible.stat().st_size == source.stat().st_size


def chemin_sans_conflit(dossier: Path, fichier_source: Path) -> Path | None:
    cible = dossier / fichier_source.name
    if not cible.exists():
        return cible
    if deja_copie(fichier_source, cible):
        return None
    stem = fichier_source.stem
    suffix = fichier_source.suffix
    compteur = 2
    while True:
        nouveau = dossier / f"{stem}_{compteur}{suffix}"
        if not nouveau.exists():
            return nouveau
        if deja_copie(fichier_source, nouveau):
            return None
        compteur += 1


# -------------------------------------------------------
# LOGIQUE DE TRI — AUTEUR (nouveau)
# -------------------------------------------------------
def get_auteur_brut(path: Path) -> str | None:
    if not PIEXIF_SUPPORTE:
        return None
    if path.suffix.lower() not in EXTENSIONS_IMAGES:
        return None
    try:
        exif = piexif.load(str(path))
        ifd0 = exif.get("0th", {})

        artist = ifd0.get(piexif.ImageIFD.Artist, b"")
        if isinstance(artist, bytes):
            artist = artist.decode("utf-8", errors="ignore").strip().rstrip("\x00")
        if artist:
            return artist

        owner = ifd0.get(42032, b"")
        if isinstance(owner, bytes):
            owner = owner.decode("utf-8", errors="ignore").strip().rstrip("\x00")
        if owner:
            return owner

        make  = ifd0.get(piexif.ImageIFD.Make, b"")
        model = ifd0.get(piexif.ImageIFD.Model, b"")
        if isinstance(make, bytes):
            make = make.decode("utf-8", errors="ignore").strip().rstrip("\x00")
        if isinstance(model, bytes):
            model = model.decode("utf-8", errors="ignore").strip().rstrip("\x00")
        combo = f"{make} {model}".strip()
        if combo:
            return combo
    except Exception:
        pass
    return None


def sanitize_folder_name(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip()


def resoudre_auteur(auteur_brut: str | None, mapping: dict) -> str:
    if auteur_brut is None:
        return "Sans_auteur"
    for cle, nom in mapping.items():
        if auteur_brut.strip().lower() == cle.strip().lower():
            return nom
    return sanitize_folder_name(auteur_brut)


# -------------------------------------------------------
# FENÊTRE : AJOUTER UN MAPPING
# -------------------------------------------------------
class DialogAjoutMapping(tk.Toplevel):
    def __init__(self, parent, brut_initial=""):
        super().__init__(parent)
        self.result = None
        self.title("Ajouter un mapping")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()

        pad = {"padx": 20, "pady": 8}

        tk.Label(self, text="Chaîne EXIF brute :", bg=BG, fg=TEXT2,
                 font=("Segoe UI", 9)).pack(anchor="w", **pad)
        self.entry_brut = tk.Entry(self, bg=BG3, fg=TEXT, insertbackground=TEXT,
                                   relief="flat", font=("Segoe UI", 10),
                                   highlightthickness=1, highlightbackground=BORDER,
                                   highlightcolor=ACCENT, width=40)
        self.entry_brut.pack(padx=20, ipady=6, fill="x")
        self.entry_brut.insert(0, brut_initial)

        tk.Label(self, text="Nom affiché :", bg=BG, fg=TEXT2,
                 font=("Segoe UI", 9)).pack(anchor="w", **pad)
        self.entry_nom = tk.Entry(self, bg=BG3, fg=TEXT, insertbackground=TEXT,
                                  relief="flat", font=("Segoe UI", 10),
                                  highlightthickness=1, highlightbackground=BORDER,
                                  highlightcolor=ACCENT, width=40)
        self.entry_nom.pack(padx=20, ipady=6, fill="x")

        row = tk.Frame(self, bg=BG)
        row.pack(pady=16, padx=20, fill="x")

        tk.Button(row, text="Annuler", bg=BG3, fg=TEXT2, relief="flat",
                  font=("Segoe UI", 9), cursor="hand2",
                  command=self.destroy).pack(side="right", padx=(8, 0), ipadx=10, ipady=6)
        tk.Button(row, text="OK", bg=ACCENT, fg="white", relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2",
                  command=self._ok).pack(side="right", ipadx=10, ipady=6)

        self.entry_brut.focus_set()

    def _ok(self):
        brut = self.entry_brut.get().strip()
        nom  = self.entry_nom.get().strip()
        if not brut or not nom:
            messagebox.showwarning("Champs vides", "Les deux champs sont requis.", parent=self)
            return
        self.result = (brut, nom)
        self.destroy()


# -------------------------------------------------------
# FENÊTRE : DÉTECTER LES AUTEURS DEPUIS LE DOSSIER
# -------------------------------------------------------
class DialogDetection(tk.Toplevel):
    def __init__(self, parent, auteurs_bruts: list[str], mapping: dict, on_save):
        super().__init__(parent)
        self.mapping = mapping
        self.on_save = on_save
        self.title("Auteurs détectés")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()
        self.geometry("500x420")

        tk.Label(self, text="Chaînes EXIF détectées — assigne un nom à chacune :",
                 bg=BG, fg=TEXT2, font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=(16, 8))

        frame = tk.Frame(self, bg=BG)
        frame.pack(fill="both", expand=True, padx=20)

        self.rows: list[tuple[str, tk.StringVar]] = []
        for brut in sorted(set(auteurs_bruts)):
            row = tk.Frame(frame, bg=BG2, pady=6)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=brut[:35], bg=BG2, fg=TEXT,
                     font=("Consolas", 9), width=36, anchor="w").pack(side="left", padx=8)
            var = tk.StringVar(value=mapping.get(brut, ""))
            e = tk.Entry(row, textvariable=var, bg=BG3, fg=TEXT, insertbackground=TEXT,
                         relief="flat", font=("Segoe UI", 9),
                         highlightthickness=1, highlightbackground=BORDER, width=18)
            e.pack(side="left", padx=8, ipady=4)
            self.rows.append((brut, var))

        tk.Button(self, text="Enregistrer", bg=ACCENT, fg="white", relief="flat",
                  font=("Segoe UI", 10, "bold"), cursor="hand2",
                  command=self._enregistrer).pack(pady=16, ipadx=16, ipady=8)

    def _enregistrer(self):
        for brut, var in self.rows:
            nom = var.get().strip()
            if nom:
                self.mapping[brut] = nom
            elif brut in self.mapping:
                del self.mapping[brut]
        self.on_save(self.mapping)
        self.destroy()


# -------------------------------------------------------
# APPLICATION PRINCIPALE
# -------------------------------------------------------
class TriMediasApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Tri Médias")
        self.root.geometry("740x700")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)

        self.source_var  = tk.StringVar()
        self.dry_run_var = tk.BooleanVar(value=False)
        self.mode_var    = tk.StringVar(value="date")
        self.en_cours    = False
        self.mapping     = charger_mapping()

        self._build_ui()

    # -------------------------------------------------------
    # CONSTRUCTION UI
    # -------------------------------------------------------
    def _build_ui(self):
        # En-tête
        header = tk.Frame(self.root, bg=BG, pady=20)
        header.pack(fill="x", padx=32)
        tk.Label(header, text="📁  Tri Médias", bg=BG, fg=TEXT,
                 font=("Segoe UI", 22, "bold")).pack(anchor="w")
        tk.Label(header, text="Classe automatiquement vos photos et vidéos par année et par mois.",
                 bg=BG, fg=TEXT2, font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 0))

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x", padx=32)

        body = tk.Frame(self.root, bg=BG, pady=16)
        body.pack(fill="x", padx=32)

        # Dossier source
        tk.Label(body, text="Dossier à trier", bg=BG, fg=TEXT2,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 6))

        row_source = tk.Frame(body, bg=BG)
        row_source.pack(fill="x")

        self.entry_source = tk.Entry(
            row_source, textvariable=self.source_var,
            bg=BG3, fg=TEXT, insertbackground=TEXT,
            relief="flat", font=("Segoe UI", 10),
            highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT
        )
        self.entry_source.pack(side="left", fill="x", expand=True, ipady=8, ipadx=8)

        tk.Button(row_source, text="  Parcourir  ", bg=BG3, fg=TEXT, relief="flat",
                  font=("Segoe UI", 10), cursor="hand2",
                  activebackground=BG2, activeforeground=TEXT,
                  highlightthickness=1, highlightbackground=BORDER,
                  command=self._parcourir).pack(side="left", padx=(8, 0), ipady=8)

        # Mode de tri
        tk.Label(body, text="Mode de tri", bg=BG, fg=TEXT2,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(16, 6))

        row_mode = tk.Frame(body, bg=BG)
        row_mode.pack(fill="x")

        for label, val in [("Par date", "date"), ("Par auteur puis par date", "auteur")]:
            tk.Radiobutton(
                row_mode, text=label, variable=self.mode_var, value=val,
                bg=BG, fg=TEXT, selectcolor=BG3, activebackground=BG,
                activeforeground=TEXT, font=("Segoe UI", 10), cursor="hand2",
                command=self._on_mode_change
            ).pack(side="left", padx=(0, 24))

        # Panneau mapping auteurs (masqué par défaut)
        self.frame_mapping = tk.LabelFrame(
            body, text="  Mapping auteurs  ", bg=BG, fg=TEXT2,
            font=("Segoe UI", 9), relief="flat",
            highlightthickness=1, highlightbackground=BORDER
        )

        tk.Label(self.frame_mapping, text="Chaîne EXIF", bg=BG, fg=TEXT2,
                 font=("Segoe UI", 8)).grid(row=0, column=0, sticky="w", padx=8, pady=(8, 2))
        tk.Label(self.frame_mapping, text="Nom affiché", bg=BG, fg=TEXT2,
                 font=("Segoe UI", 8)).grid(row=0, column=1, sticky="w", padx=8, pady=(8, 2))

        self.tree_mapping = ttk.Treeview(
            self.frame_mapping, columns=("brut", "nom"), show="headings",
            height=4, selectmode="browse"
        )
        self.tree_mapping.heading("brut", text="Chaîne EXIF")
        self.tree_mapping.heading("nom",  text="Nom affiché")
        self.tree_mapping.column("brut", width=260)
        self.tree_mapping.column("nom",  width=160)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background=BG2, foreground=TEXT,
                         fieldbackground=BG2, borderwidth=0, rowheight=22)
        style.configure("Treeview.Heading", background=BG3, foreground=TEXT2,
                         borderwidth=0, font=("Segoe UI", 9))
        style.map("Treeview", background=[("selected", ACCENT2)])

        self.tree_mapping.grid(row=1, column=0, columnspan=2, padx=8, pady=4, sticky="ew")

        row_btns = tk.Frame(self.frame_mapping, bg=BG)
        row_btns.grid(row=2, column=0, columnspan=2, sticky="w", padx=8, pady=(4, 10))

        for txt, cmd in [
            ("+ Ajouter",              self._mapping_ajouter),
            ("Supprimer",              self._mapping_supprimer),
            ("Détecter depuis source", self._mapping_detecter),
        ]:
            tk.Button(row_btns, text=txt, bg=BG3, fg=TEXT, relief="flat",
                      font=("Segoe UI", 9), cursor="hand2",
                      activebackground=BG2, activeforeground=TEXT,
                      command=cmd).pack(side="left", padx=(0, 6), ipadx=8, ipady=5)

        self._refresh_tree()

        # Dry-run + bouton lancer
        row_opts = tk.Frame(body, bg=BG)
        row_opts.pack(fill="x", pady=(14, 0))

        tk.Checkbutton(
            row_opts, text="Mode simulation (ne copie rien, juste un aperçu)",
            variable=self.dry_run_var,
            bg=BG, fg=TEXT2, selectcolor=BG3,
            activebackground=BG, activeforeground=TEXT,
            font=("Segoe UI", 9), cursor="hand2"
        ).pack(anchor="w")

        self.btn_lancer = tk.Button(
            body, text="🚀  Lancer le tri",
            bg=ACCENT, fg="white", relief="flat",
            font=("Segoe UI", 11, "bold"), cursor="hand2",
            activebackground=ACCENT2, activeforeground="white",
            command=self._lancer
        )
        self.btn_lancer.pack(fill="x", pady=(14, 0), ipady=10)

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x", padx=32, pady=(14, 0))

        # Barre de progression
        prog_frame = tk.Frame(self.root, bg=BG, pady=10)
        prog_frame.pack(fill="x", padx=32)

        row_prog = tk.Frame(prog_frame, bg=BG)
        row_prog.pack(fill="x")

        self.label_statut = tk.Label(row_prog, text="En attente…", bg=BG, fg=TEXT2,
                                     font=("Segoe UI", 9))
        self.label_statut.pack(side="left")

        self.label_compteur = tk.Label(row_prog, text="", bg=BG, fg=TEXT2,
                                       font=("Segoe UI", 9))
        self.label_compteur.pack(side="right")

        self.canvas_prog = tk.Canvas(prog_frame, height=8, bg=BG3,
                                     highlightthickness=0, relief="flat")
        self.canvas_prog.pack(fill="x", pady=(6, 0))
        self.barre_rect = self.canvas_prog.create_rectangle(0, 0, 0, 8, fill=ACCENT, outline="")

        # Journal
        log_frame = tk.Frame(self.root, bg=BG, pady=4)
        log_frame.pack(fill="both", expand=True, padx=32, pady=(0, 16))

        tk.Label(log_frame, text="Journal", bg=BG, fg=TEXT2,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 6))

        self.log = scrolledtext.ScrolledText(
            log_frame, bg=BG2, fg=TEXT2, font=("Consolas", 9), relief="flat",
            insertbackground=TEXT, state="disabled",
            highlightthickness=1, highlightbackground=BORDER, wrap="word"
        )
        self.log.pack(fill="both", expand=True)

        self.log.tag_config("ok",      foreground=SUCCESS)
        self.log.tag_config("warn",    foreground=WARNING)
        self.log.tag_config("err",     foreground=DANGER)
        self.log.tag_config("info",    foreground=ACCENT)
        self.log.tag_config("default", foreground=TEXT2)

    # -------------------------------------------------------
    # MODE DE TRI
    # -------------------------------------------------------
    def _on_mode_change(self):
        if self.mode_var.get() == "auteur":
            self.frame_mapping.pack(fill="x", pady=(12, 0))
        else:
            self.frame_mapping.pack_forget()

    # -------------------------------------------------------
    # GESTION MAPPING
    # -------------------------------------------------------
    def _refresh_tree(self):
        self.tree_mapping.delete(*self.tree_mapping.get_children())
        for brut, nom in self.mapping.items():
            self.tree_mapping.insert("", "end", values=(brut, nom))

    def _mapping_ajouter(self):
        dlg = DialogAjoutMapping(self.root)
        self.root.wait_window(dlg)
        if dlg.result:
            brut, nom = dlg.result
            self.mapping[brut] = nom
            sauvegarder_mapping(self.mapping)
            self._refresh_tree()

    def _mapping_supprimer(self):
        sel = self.tree_mapping.selection()
        if not sel:
            return
        brut = self.tree_mapping.item(sel[0])["values"][0]
        if brut in self.mapping:
            del self.mapping[brut]
            sauvegarder_mapping(self.mapping)
            self._refresh_tree()

    def _mapping_detecter(self):
        source_str = self.source_var.get().strip()
        if not source_str or not Path(source_str).exists():
            messagebox.showwarning("Dossier manquant",
                                   "Sélectionnez d'abord un dossier source.")
            return
        source = Path(source_str)

        def scanner():
            auteurs = set()
            for f in source.rglob("*"):
                if f.is_file() and f.suffix.lower() in EXTENSIONS_IMAGES:
                    brut = get_auteur_brut(f)
                    if brut:
                        auteurs.add(brut)
            self.root.after(0, _ouvrir_dialog, sorted(auteurs))

        def _ouvrir_dialog(auteurs):
            if not auteurs:
                messagebox.showinfo("Aucun auteur trouvé",
                                    "Aucune métadonnée auteur/appareil détectée.")
                return
            dlg = DialogDetection(self.root, auteurs, self.mapping, self._on_mapping_detecte)

        self.label_statut.config(text="Détection en cours…")
        threading.Thread(target=scanner, daemon=True).start()

    def _on_mapping_detecte(self, mapping: dict):
        self.mapping = mapping
        sauvegarder_mapping(self.mapping)
        self._refresh_tree()
        self.label_statut.config(text="Mapping mis à jour.")

    # -------------------------------------------------------
    # ACTIONS UI
    # -------------------------------------------------------
    def _parcourir(self):
        dossier = filedialog.askdirectory(title="Sélectionner le dossier à trier")
        if dossier:
            self.source_var.set(dossier)

    def _log(self, message: str, tag: str = "default"):
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_progression(self, actuel: int, total: int, nom_fichier: str = ""):
        pct = actuel / total if total > 0 else 0
        largeur = self.canvas_prog.winfo_width()
        self.canvas_prog.coords(self.barre_rect, 0, 0, largeur * pct, 8)
        self.label_compteur.config(text=f"{actuel} / {total}  ({int(pct*100)}%)")
        if nom_fichier:
            nom_court = nom_fichier[:55] + "…" if len(nom_fichier) > 55 else nom_fichier
            self.label_statut.config(text=nom_court)

    def _reset_ui(self, en_cours: bool):
        self.en_cours = en_cours
        self.btn_lancer.config(
            state="disabled" if en_cours else "normal",
            text="⏳  Tri en cours…" if en_cours else "🚀  Lancer le tri",
            bg="#2a2a2a" if en_cours else ACCENT
        )

    # -------------------------------------------------------
    # LANCEMENT
    # -------------------------------------------------------
    def _lancer(self):
        if self.en_cours:
            return
        source_str = self.source_var.get().strip()
        if not source_str:
            messagebox.showwarning("Dossier manquant", "Veuillez sélectionner un dossier source.")
            return
        source = Path(source_str)
        if not source.exists():
            messagebox.showerror("Dossier introuvable", f"Le dossier n'existe pas :\n{source}")
            return

        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self._set_progression(0, 1, "")
        self.label_statut.config(text="Démarrage…")
        self._reset_ui(True)

        mode = self.mode_var.get()
        thread = threading.Thread(
            target=self._tri_thread, args=(source, mode), daemon=True
        )
        thread.start()

    # -------------------------------------------------------
    # TRI DANS UN THREAD
    # -------------------------------------------------------
    def _tri_thread(self, source: Path, mode: str):
        dry_run = self.dry_run_var.get()
        try:
            date_du_jour = datetime.now().strftime("%Y-%m-%d")
            destination  = source.parent / f"Tri Officiel ({date_du_jour})"

            if dry_run:
                self._log("🧪  MODE SIMULATION — aucun fichier ne sera copié\n", "warn")

            self._log(f"📂  Source      : {source}", "info")
            self._log(f"📁  Destination : {destination}", "info")
            self._log(f"⚙️   Mode        : {'Par auteur puis par date' if mode == 'auteur' else 'Par date'}\n", "info")
            self._log("🔍  Scan en cours…", "default")

            tous_les_fichiers = [
                f for f in source.rglob("*")
                if f.is_file()
                and f.suffix.lower() in EXTENSIONS_SUPPORTEES
                and not f.is_relative_to(destination)
            ]

            total = len(tous_les_fichiers)
            self._log(f"📸  {total} fichiers trouvés\n", "ok")

            if total == 0:
                self._log("Aucun fichier média trouvé. Vérifiez le dossier source.", "warn")
                self.root.after(0, self._reset_ui, False)
                self.root.after(0, self.label_statut.config, {"text": "Aucun fichier trouvé."})
                return

            copiés = ignorés = conflits = date_non_fiable = erreurs = 0
            années_trouvées  = set()
            compteur_auteurs: dict[str, int] = {}
            log_erreurs      = []
            mapping          = dict(self.mapping)

            for i, fichier in enumerate(tous_les_fichiers, 1):
                self.root.after(0, self._set_progression, i, total, fichier.name)
                try:
                    date, fiable = get_date(fichier)
                    if not fiable:
                        date_non_fiable += 1

                    année = str(date.year)
                    mois  = MOIS[date.month]
                    années_trouvées.add(année)

                    if mode == "auteur":
                        auteur_brut = get_auteur_brut(fichier)
                        auteur      = resoudre_auteur(auteur_brut, mapping)
                        dossier_cible = destination / auteur / année / mois
                    else:
                        auteur        = None
                        dossier_cible = destination / année / mois

                    chemin_cible = chemin_sans_conflit(dossier_cible, fichier)

                    if chemin_cible is None:
                        ignorés += 1
                    else:
                        if chemin_cible.name != fichier.name:
                            conflits += 1
                        if not dry_run:
                            dossier_cible.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(fichier, chemin_cible)
                        copiés += 1
                        if auteur:
                            compteur_auteurs[auteur] = compteur_auteurs.get(auteur, 0) + 1

                    if i % 50 == 0:
                        tag = "ok" if fiable else "warn"
                        s   = "✅" if fiable else "⚠️ "
                        dest_label = f"{auteur}/{année}/{mois}" if auteur else f"{année}/{mois}"
                        self.root.after(0, self._log,
                            f"  {s} {i}/{total} — {fichier.name} → {dest_label}", tag)

                except Exception as e:
                    erreurs += 1
                    log_erreurs.append(f"ERREUR : {fichier} — {e}")
                    self.root.after(0, self._log, f"  ❌ {fichier.name} : {e}", "err")

            # --- Rapport final ---
            dry_label = " (SIMULATION)" if dry_run else ""
            rapport = [
                "",
                "═" * 52,
                f"  ✅  TRI TERMINÉ{dry_label}",
                "═" * 52,
                f"  📸  Total trouvé       : {total}",
                f"  ✅  Copiés             : {copiés}",
                f"  ⏭️   Déjà présents      : {ignorés}",
                f"  🔄  Conflits renommés  : {conflits}",
                f"  ⚠️   Dates non fiables  : {date_non_fiable}",
                f"  ❌  Erreurs            : {erreurs}",
                f"  📅  Années trouvées    : {', '.join(sorted(années_trouvées))}",
                f"  📁  Résultat dans      : {destination}",
                "═" * 52,
            ]

            if mode == "auteur" and compteur_auteurs:
                rapport.append("  👤  Répartition par auteur :")
                for auteur, nb in sorted(compteur_auteurs.items(), key=lambda x: -x[1]):
                    rapport.append(f"       • {auteur} : {nb} fichier(s)")
                if ignorés:
                    rapport.append(f"  ⏭️   {ignorés} doublon(s) ignorés (même contenu)")

            for ligne in rapport:
                tag = "ok" if "TERMINÉ" in ligne else "info" if "═" in ligne else "default"
                self.root.after(0, self._log, ligne, tag)

            if date_non_fiable > 0:
                self.root.after(0, self._log,
                    f"\n⚠️  {date_non_fiable} fichier(s) classés par date de modification "
                    f"(peut être inexacte pour vidéos/cloud).", "warn")

            if not dry_run:
                destination.mkdir(parents=True, exist_ok=True)
                rapport_path = destination / f"rapport_{date_du_jour}.txt"
                with open(rapport_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(rapport))
                self.root.after(0, self._log, f"\n📄  Rapport : {rapport_path}", "info")

                if log_erreurs:
                    log_path = destination / "erreurs.log"
                    with open(log_path, "w", encoding="utf-8") as f:
                        f.write("\n".join(log_erreurs))
                    self.root.after(0, self._log, f"📋  Erreurs : {log_path}", "warn")

            self.root.after(0, self.label_statut.config,
                            {"text": "✅  Terminé !" if not dry_run else "🧪  Simulation terminée"})

        except Exception as e:
            self.root.after(0, self._log, f"\n❌  Erreur critique : {e}", "err")
            self.root.after(0, self.label_statut.config, {"text": "❌  Erreur"})

        finally:
            self.root.after(0, self._reset_ui, False)


# -------------------------------------------------------
# LANCEMENT
# -------------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = TriMediasApp(root)
    root.mainloop()
