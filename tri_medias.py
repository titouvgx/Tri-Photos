"""
tri_medias.py - V1.3
Trie toutes les photos et vidéos d'un dossier source (récursivement)
dans un dossier "Tri Officiel (YYYY-MM-DD)" par Année > Mois.
Les fichiers originaux ne sont PAS supprimés.
"""

import sys
import os
import traceback
import argparse
import shutil
from datetime import datetime
from pathlib import Path

# Fenêtre reste ouverte en cas de crash
def _on_crash(exc_type, exc_value, exc_tb):
    traceback.print_exception(exc_type, exc_value, exc_tb)
    input("\nAppuie sur Entrée pour fermer...")

sys.excepthook = _on_crash

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
        print(f"\nDossier introuvable : {source}\n")
        return

    date_du_jour = datetime.now().strftime("%Y-%m-%d")
    destination = source.parent / f"Tri Officiel ({date_du_jour})"

    print(f"\n{'='*55}")
    if dry_run:
        print("  TRI MEDIAS — DRY RUN (aucun fichier ne sera copie)")
    else:
        print("  TRI MEDIAS")
    print(f"{'='*55}")
    print(f"  Source      : {source}")
    print(f"  Destination : {destination}")
    print(f"{'='*55}\n")

    if not HEIC_SUPPORTE:
        print("  Attention : pillow-heif non installe — HEIC/HEIF classes via date de modification.")
        print("  Pour corriger : pip install pillow-heif\n")

    print("Scan en cours...", end=" ", flush=True)
    tous_les_fichiers = [
        f for f in source.rglob("*")
        if f.is_file()
        and f.suffix.lower() in EXTENSIONS_SUPPORTEES
        and not f.is_relative_to(destination)
    ]
    total = len(tous_les_fichiers)
    print(f"{total} fichiers trouves\n")

    if total == 0:
        print("Aucun fichier media trouve. Verifie le dossier source.")
        return

    copiés = ignorés = conflits = date_non_fiable = erreurs = 0
    années_trouvées = set()
    log_erreurs = []

    with tqdm(total=total, unit="fich.", ncols=75,
              bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]") as barre:
        for fichier in tous_les_fichiers:
            barre.set_description(fichier.name[:28].ljust(28))
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

    # Rapport final
    action = "A copier" if dry_run else "Copies  "
    dry_label = " (DRY RUN)" if dry_run else ""
    print(f"""
{'='*55}
  TRI TERMINE{dry_label}
{'='*55}
  Total trouve        : {total}
  {action}             : {copiés}
  Deja presents       : {ignorés}
  Conflits renommes   : {conflits}
  Dates non fiables   : {date_non_fiable}
  Erreurs             : {erreurs}
  Annees trouvees     : {', '.join(sorted(années_trouvées))}
  Resultat dans       : {destination}
{'='*55}""")

    if date_non_fiable > 0:
        print(f"\n  Attention : {date_non_fiable} fichier(s) classes via date de modification.")
        print("  (videos ou images sans EXIF — peut etre inexact si transfere via cloud)")

    if not dry_run:
        destination.mkdir(parents=True, exist_ok=True)
        rapport_path = destination / f"rapport_{date_du_jour}.txt"
        with open(rapport_path, "w", encoding="utf-8") as f:
            f.write(f"Rapport de tri — {date_du_jour}\n{'='*50}\n")
            f.write(f"Total trouve       : {total}\n")
            f.write(f"Copies             : {copiés}\n")
            f.write(f"Deja presents      : {ignorés}\n")
            f.write(f"Conflits renommes  : {conflits}\n")
            f.write(f"Dates non fiables  : {date_non_fiable}\n")
            f.write(f"Erreurs            : {erreurs}\n")
            f.write(f"Annees trouvees    : {', '.join(sorted(années_trouvées))}\n")
            f.write(f"Resultat dans      : {destination}\n")
        print(f"\n  Rapport : {rapport_path}")

        if log_erreurs:
            log_path = destination / "erreurs.log"
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("\n".join(log_erreurs))
            print(f"  Erreurs : {log_path}")

    print()


# -------------------------------------------------------
# LANCEMENT
# -------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trie photos et videos par Annee > Mois.")
    parser.add_argument("source", nargs="?", help="Dossier source a trier")
    parser.add_argument("--dry-run", action="store_true", help="Simule le tri sans copier")
    args = parser.parse_args()

    if not args.source:
        print("\n  TRI MEDIAS")
        print("  ─────────────────────────────\n")
        args.source = input("  Dossier a trier : ").strip().strip('"')
        dry = input("  Dry-run ? (o/n)  : ").strip().lower()
        args.dry_run = dry in ("o", "oui", "y", "yes")

    try:
        trier_medias(args.source, dry_run=args.dry_run)
    except Exception as e:
        print(f"\nErreur : {e}")
        traceback.print_exc()
    finally:
        input("\nAppuie sur Entree pour fermer...")
