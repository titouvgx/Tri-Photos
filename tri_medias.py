"""
tri_medias.py - V1.6
Trie toutes les photos et vidéos d'un dossier source (récursivement)
dans un dossier "Tri Officiel (YYYY-MM-DD)" par Année > Mois.
Les fichiers originaux ne sont PAS supprimés.
"""

import sys
import os
import traceback

# Active les couleurs ANSI sur Windows 10/11
os.system("")

# Intercepte tout crash — la fenêtre reste toujours ouverte
def _on_crash(exc_type, exc_value, exc_tb):
    print("\n" + "=" * 55)
    print("ERREUR AU LANCEMENT :")
    traceback.print_exception(exc_type, exc_value, exc_tb)
    print("=" * 55)
    try:
        base = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
        log = os.path.join(base, "erreur_lancement.log")
        with open(log, "w", encoding="utf-8") as f:
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
        print(f"Log écrit : {log}")
    except Exception:
        pass
    input("\nAppuie sur Entrée pour fermer...")

sys.excepthook = _on_crash

import argparse
import shutil
from datetime import datetime
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:
    print("tqdm non installé. Lance : pip install tqdm Pillow pillow-heif")
    input("\nAppuie sur Entrée pour fermer...")
    sys.exit(1)

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
except ImportError:
    print("Pillow non installé. Lance : pip install Pillow pillow-heif tqdm")
    input("\nAppuie sur Entrée pour fermer...")
    sys.exit(1)

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC_SUPPORTE = True
except ImportError:
    HEIC_SUPPORTE = False

# -------------------------------------------------------
# ANSI
# -------------------------------------------------------
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

def c(texte, couleur):
    return f"{couleur}{texte}{RESET}"

def box(titre, lignes, couleur=CYAN):
    largeur = max(len(titre), max(len(l) for l in lignes)) + 4
    sep = couleur + "─" * largeur + RESET
    print(f"\n{couleur}┌{sep}┐{RESET}")
    print(f"{couleur}│{RESET} {BOLD}{titre}{RESET}{' ' * (largeur - len(titre) - 1)}{couleur}│{RESET}")
    print(f"{couleur}├{sep}┤{RESET}")
    for ligne in lignes:
        print(f"{couleur}│{RESET} {ligne}{' ' * (largeur - len(ligne) - 1)}{couleur}│{RESET}")
    print(f"{couleur}└{sep}┘{RESET}\n")

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
# LECTURE DATE EXIF
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
    timestamp = filepath.stat().st_mtime
    return datetime.fromtimestamp(timestamp), False


# -------------------------------------------------------
# GESTION DES CONFLITS DE NOM
# -------------------------------------------------------
def deja_copie(source: Path, cible: Path) -> bool:
    return cible.exists() and cible.stat().st_size == source.stat().st_size


def chemin_sans_conflit(dossier: Path, fichier_source: Path) -> Path | None:
    cible = dossier / fichier_source.name
    if not cible.exists():
        return cible
    if deja_copie(fichier_source, cible):
        return None
    stem, suffix = fichier_source.stem, fichier_source.suffix
    compteur = 2
    while True:
        nouveau = dossier / f"{stem}_{compteur}{suffix}"
        if not nouveau.exists():
            return nouveau
        if deja_copie(fichier_source, nouveau):
            return None
        compteur += 1


# -------------------------------------------------------
# TRI PRINCIPAL
# -------------------------------------------------------
def trier_medias(dossier_source: str, dry_run: bool = False):
    source = Path(dossier_source).resolve()

    if not source.exists():
        print(c(f"\n✗ Dossier introuvable : {source}\n", RED))
        return

    date_du_jour = datetime.now().strftime("%Y-%m-%d")
    destination = source.parent / f"Tri Officiel ({date_du_jour})"

    titre = "TRI MÉDIAS — DRY RUN" if dry_run else "📷 TRI MÉDIAS"
    lignes = [
        f"Source      : {source}",
        f"Destination : {destination}",
    ]
    if dry_run:
        lignes.append(c("Aucun fichier ne sera copié", YELLOW))
    box(titre, lignes)

    if not HEIC_SUPPORTE:
        print(c("⚠  pillow-heif non installé — HEIC/HEIF classés via date de modification.", YELLOW))
        print(c("   Pour corriger : pip install pillow-heif\n", DIM))

    print(c("Scan en cours...", CYAN), end=" ", flush=True)
    tous_les_fichiers = [
        f for f in source.rglob("*")
        if f.is_file()
        and f.suffix.lower() in EXTENSIONS_SUPPORTEES
        and not f.is_relative_to(destination)
    ]
    print(c(f"{len(tous_les_fichiers)} fichiers trouvés\n", BOLD))

    total = len(tous_les_fichiers)
    if total == 0:
        print(c("Aucun fichier média trouvé. Vérifie le dossier source.", YELLOW))
        return

    copiés = ignorés = conflits = date_non_fiable = erreurs = 0
    années_trouvées = set()
    log_erreurs = []

    with tqdm(total=total, unit="fich.", ncols=80, colour="cyan",
              bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]") as barre:
        for fichier in tous_les_fichiers:
            barre.set_description(fichier.name[:30].ljust(30))
            try:
                date, fiable = get_date(fichier)
                if not fiable:
                    date_non_fiable += 1

                année = str(date.year)
                mois = MOIS[date.month]
                années_trouvées.add(année)

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

            except Exception as e:
                erreurs += 1
                log_erreurs.append(f"ERREUR : {fichier} — {e}")

            barre.update(1)

    # -------------------------------------------------------
    # RAPPORT
    # -------------------------------------------------------
    action = "À copier  " if dry_run else "Copiés    "
    dry_label = " (DRY RUN)" if dry_run else ""

    def stat(label, val, couleur=None):
        s = f"{label} : {val}"
        return c(s, couleur) if couleur else s

    lignes_rapport = [
        stat(f"✅ {action}", copiés, GREEN),
        stat("⏭  Déjà présents  ", ignorés, DIM),
        stat("🔄 Conflits renommés", conflits, YELLOW if conflits else None),
        stat("⚠  Dates non fiables", date_non_fiable, YELLOW if date_non_fiable else None),
        stat("❌ Erreurs          ", erreurs, RED if erreurs else GREEN),
        stat("📅 Années trouvées  ", ", ".join(sorted(années_trouvées))),
        stat("📁 Résultat dans    ", str(destination)),
    ]
    box(f"Rapport de tri{dry_label}", lignes_rapport)

    if date_non_fiable > 0:
        print(c(f"⚠  {date_non_fiable} fichier(s) classés via date de modification", YELLOW))
        print(c("   (vidéos/images sans EXIF — peut être inexact si transféré via cloud)\n", DIM))

    if not dry_run:
        destination.mkdir(parents=True, exist_ok=True)
        rapport_path = destination / f"rapport_{date_du_jour}.txt"
        with open(rapport_path, "w", encoding="utf-8") as f:
            f.write(f"Rapport de tri — {date_du_jour}\n{'='*50}\n")
            f.write(f"Total trouvé       : {total}\n")
            f.write(f"Copiés             : {copiés}\n")
            f.write(f"Déjà présents      : {ignorés}\n")
            f.write(f"Conflits renommés  : {conflits}\n")
            f.write(f"Dates non fiables  : {date_non_fiable}\n")
            f.write(f"Erreurs            : {erreurs}\n")
            f.write(f"Années trouvées    : {', '.join(sorted(années_trouvées))}\n")
            f.write(f"Résultat dans      : {destination}\n")
        print(c(f"📄 Rapport : {rapport_path}", DIM))

        if log_erreurs:
            log_path = destination / "erreurs.log"
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("\n".join(log_erreurs))
            print(c(f"📋 Erreurs : {log_path}", DIM))


# -------------------------------------------------------
# LANCEMENT
# -------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trie photos et vidéos par Année > Mois.")
    parser.add_argument("source", nargs="?", help="Dossier source à trier")
    parser.add_argument("--dry-run", action="store_true", help="Simule le tri sans copier")
    args = parser.parse_args()

    if not args.source:
        print(f"\n{BOLD}{CYAN}📷 TRI MÉDIAS{RESET}")
        print(f"{DIM}─────────────────────────────{RESET}\n")
        args.source = input("📂 Dossier à trier : ").strip().strip('"')
        dry = input("🧪 Dry-run ? (o/n)  : ").strip().lower()
        args.dry_run = dry in ("o", "oui", "y", "yes")

    try:
        trier_medias(args.source, dry_run=args.dry_run)
    except Exception as e:
        print(c(f"\nErreur : {e}", RED))
        traceback.print_exc()
    finally:
        input("\nAppuie sur Entrée pour fermer...")
