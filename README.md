# 📸 tri_medias — Guide complet

Script Python qui trie automatiquement toutes tes photos et vidéos
par **Année > Mois**, sans toucher aux fichiers originaux.

---

## 🧠 Comment ça fonctionne ?

Tu lances le script sur ton PC et tu lui indiques où se trouvent tes photos
(dossier local, disque dur externe, clé USB, peu importe).

```
Ton PC
  └── tri_medias.exe (ou python tri_medias.py)
        └── Tu lui dis : "va chercher dans E:\Photos"
              └── Il parcourt TOUT E:\Photos (et tous les sous-dossiers)
                    └── Il crée E:\Tri Officiel (2026-06-08)\
                          ├── 2005\
                          │   ├── 03 - Mars\
                          │   └── 07 - Juillet\
                          ├── 2018\
                          │   └── 12 - Décembre\
                          └── 2024\
                              └── 01 - Janvier\
```

> ✅ Les fichiers originaux ne sont **jamais supprimés ni déplacés**.
> Le script **copie** uniquement. Tu peux le relancer sans risque.

---

## 🚀 Utilisation rapide (sans Python)

Télécharge `tri_medias.exe` et lance-le depuis PowerShell :

```
# Simuler d'abord (aucune copie)
.\tri_medias.exe C:\Users\Titou\Pictures --dry-run

# Lancer pour de vrai
.\tri_medias.exe C:\Users\Titou\Pictures
```

---

## ⚙️ Utilisation avec Python

### Installation (à faire une seule fois)

```
pip install Pillow pillow-heif rich
```

- **Pillow** — lit les métadonnées EXIF (date de prise de vue réelle)
- **pillow-heif** — support des photos iPhone (HEIC/HEIF)
- **rich** — interface colorée avec barre de progression

### Lancer le script

```
python tri_medias.py <chemin_vers_tes_photos>
```

---

## 📂 Exemples

```
# Disque dur externe (E:)
python tri_medias.py E:\

# Dossier spécifique
python tri_medias.py E:\MesPhotos

# Dossier Images du PC
python tri_medias.py C:\Users\Titou\Pictures

# Clé USB (F:)
python tri_medias.py F:\

# Simuler sans copier (recommandé avant le premier lancement)
python tri_medias.py E:\ --dry-run
```

---

## 📊 Ce que fait le script

| Situation | Comportement |
|---|---|
| Fichier avec EXIF (JPG, HEIC...) | Classé à la date de prise de vue réelle |
| Fichier sans EXIF (vidéos, PNG...) | Classé à la date de modification (avertissement affiché) |
| Deux fichiers avec le même nom et même taille | Le doublon est ignoré (déjà copié) |
| Deux fichiers avec le même nom mais contenu différent | Renommé automatiquement en `_2`, `_3`... |
| Erreur sur un fichier | Logué dans `erreurs.log`, le reste continue |

À la fin, un fichier `rapport_YYYY-MM-DD.txt` est créé dans le dossier de destination.

---

## 🗂️ Formats supportés

**Images** — JPG, JPEG, PNG, HEIC, HEIF, BMP, GIF, TIFF, TIF, WEBP,
RAW, CR2, CR3, NEF, ARW, ORF, RW2, DNG, PEF, SRW, RAF

**Vidéos** — MP4, MOV, AVI, MKV, WMV, FLV, M4V, 3GP, MPG, MPEG,
MTS, M2TS, TS, WEBM, VOB, OGV, DIVX

---

## ❓ FAQ

**Mes photos originales sont-elles supprimées ?**
Non. Le script copie uniquement. Tes originaux restent intacts.

**Que se passe-t-il si une photo n'a pas de date EXIF ?**
La date de dernière modification du fichier est utilisée en fallback.
Un avertissement est affiché dans le rapport final.

**Puis-je relancer le script sur le même dossier ?**
Oui. Les fichiers déjà copiés (même nom, même taille) sont automatiquement ignorés.

**Combien de temps pour 100 Go ?**
Entre 5 et 30 minutes selon que tu as un SSD ou un HDD.
