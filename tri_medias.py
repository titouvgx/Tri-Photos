"""
tri_medias.py - V1.4
Trie toutes les photos et vidéos d'un dossier source (récursivement)
dans un dossier "Tri Officiel (YYYY-MM-DD)" par Année > Mois.
Les fichiers originaux ne sont PAS supprimés.
"""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
except ImportError:
    print("Pillow non installé. Lance : pip install Pillow pillow-heif rich")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
    )
    from rich.table import Table
    from rich import box
    from rich.text import Text
except ImportError:
    print("rich non installé. Lance : pip install rich")
    sys.exit(1)

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC_SUPPORTE = True
except ImportError:
    HEIC_SUPPORTE = False

console = Console()

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
# TRI PRINCIPAL
# -------------------------------------------------------
def trier_medias(dossier_source: str, dry_run: bool = False):
    source = Path(dossier_source).resolve()

    if not source.exists():
        console.print(f"\n[bold red]✗ Dossier introuvable :[/] {source}\n")
        sys.exit(1)

    date_du_jour = datetime.now().strftime("%Y-%m-%d")
    nom_destination = f"Tri Officiel ({date_du_jour})"
    destination = source.parent / nom_destination

    # En-tête
    titre = "🧪 TRI MÉDIAS — DRY RUN" if dry_run else "📷 TRI MÉDIAS"
    console.print()
    console.print(Panel.fit(
        f"[bold cyan]{titre}[/]\n"
        f"[dim]Source      :[/] {source}\n"
        f"[dim]Destination :[/] {destination}"
        + ("\n\n[bold yellow]Aucun fichier ne sera copié[/]" if dry_run else ""),
        border_style="cyan",
        padding=(1, 3),
    ))
    console.print()

    if not HEIC_SUPPORTE:
        console.print("[yellow]⚠ pillow-heif non installé — HEIC/HEIF (iPhone) classés via date de modification.[/]")
        console.print("[dim]  Pour corriger : pip install pillow-heif[/]\n")

    # Scan
    with console.status("[cyan]Scan en cours...[/]", spinner="dots"):
        tous_les_fichiers = [
            f for f in source.rglob("*")
            if f.is_file()
            and f.suffix.lower() in EXTENSIONS_SUPPORTEES
            and not f.is_relative_to(destination)
        ]

    total = len(tous_les_fichiers)
    console.print(f"[bold]📸 {total} fichiers trouvés[/]\n")

    if total == 0:
        console.print("[yellow]Aucun fichier média trouvé. Vérifie le dossier source.[/]")
        return

    copiés = 0
    ignorés = 0
    conflits = 0
    date_non_fiable = 0
    erreurs = 0
    années_trouvées = set()
    log_erreurs = []

    # Barre de progression
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}[/]", justify="left"),
        BarColumn(bar_width=35, style="cyan", complete_style="bold green"),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
        expand=False,
    )

    with progress:
        tache = progress.add_task("Tri en cours", total=total)

        for fichier in tous_les_fichiers:
            progress.update(tache, description=fichier.name[:35].ljust(35))
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

            progress.advance(tache)

    # -------------------------------------------------------
    # RAPPORT FINAL
    # -------------------------------------------------------
    console.print()

    table = Table(
        box=box.ROUNDED,
        border_style="cyan",
        show_header=False,
        padding=(0, 2),
        title="[bold]Rapport de tri[/]" + (" [yellow](DRY RUN)[/]" if dry_run else ""),
        title_style="bold cyan",
    )
    table.add_column(justify="left",  style="dim")
    table.add_column(justify="right", style="bold")

    action = "À copier" if dry_run else "Copiés"
    table.add_row("📸 Total trouvé",      str(total))
    table.add_row(f"✅ {action}",         f"[green]{copiés}[/]")
    table.add_row("⏭  Déjà présents",    f"[dim]{ignorés}[/]")
    table.add_row("🔄 Conflits renommés", f"[yellow]{conflits}[/]" if conflits else "0")
    table.add_row("⚠  Dates non fiables", f"[yellow]{date_non_fiable}[/]" if date_non_fiable else "0")
    table.add_row("❌ Erreurs",           f"[red]{erreurs}[/]" if erreurs else "[green]0[/]")
    table.add_row("📅 Années trouvées",   ", ".join(sorted(années_trouvées)))
    table.add_row("📁 Résultat dans",     str(destination))

    console.print(table)

    if date_non_fiable > 0:
        console.print()
        console.print(Panel(
            f"[yellow]{date_non_fiable} fichier(s) classés via date de modification[/]\n"
            "[dim]Vidéos ou images sans EXIF — la date peut être inexacte si les fichiers\n"
            "ont été transférés ou synchronisés via cloud. Vérifie manuellement.[/]",
            title="[yellow]⚠ Attention[/]",
            border_style="yellow",
            padding=(0, 2),
        ))

    if not dry_run:
        destination.mkdir(parents=True, exist_ok=True)

        rapport_path = destination / f"rapport_{date_du_jour}.txt"
        with open(rapport_path, "w", encoding="utf-8") as f:
            f.write(f"Rapport de tri — {date_du_jour}\n")
            f.write("=" * 50 + "\n")
            f.write(f"Total trouvé       : {total}\n")
            f.write(f"Copiés             : {copiés}\n")
            f.write(f"Déjà présents      : {ignorés}\n")
            f.write(f"Conflits renommés  : {conflits}\n")
            f.write(f"Dates non fiables  : {date_non_fiable}\n")
            f.write(f"Erreurs            : {erreurs}\n")
            f.write(f"Années trouvées    : {', '.join(sorted(années_trouvées))}\n")
            f.write(f"Résultat dans      : {destination}\n")

        console.print(f"\n[dim]📄 Rapport : {rapport_path}[/]")

        if log_erreurs:
            log_path = destination / "erreurs.log"
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("\n".join(log_erreurs))
            console.print(f"[dim]📋 Erreurs : {log_path}[/]")

    console.print()


# -------------------------------------------------------
# LANCEMENT
# -------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trie photos et vidéos par Année > Mois.")
    parser.add_argument("source", nargs="?", help="Dossier source à trier")
    parser.add_argument("--dry-run", action="store_true", help="Simule le tri sans copier aucun fichier")
    args = parser.parse_args()

    # Mode interactif si double-clic (aucun argument fourni)
    if not args.source:
        console.print()
        console.print(Panel.fit(
            "[bold cyan]📷 TRI MÉDIAS[/]\n"
            "[dim]Aucun dossier spécifié — mode interactif[/]",
            border_style="cyan",
            padding=(1, 3),
        ))
        console.print()
        source = console.input("[bold]📂 Chemin du dossier à trier :[/] ").strip().strip('"')
        dry = console.input("[bold]🧪 Dry-run ? (o/n) :[/] ").strip().lower()
        args.source = source
        args.dry_run = dry in ("o", "oui", "y", "yes")

    trier_medias(args.source, dry_run=args.dry_run)
    input("\nAppuie sur Entrée pour fermer...")
