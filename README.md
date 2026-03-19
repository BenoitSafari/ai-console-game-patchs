# ai-console-game-patchs

Outils Python pour creer des versions hybrides NTSC 60Hz + francais de jeux retro, en combinant les fichiers des versions NTSC (gameplay rapide) et PAL (contenu francais).

## Consoles supportees

### GameCube (`ngc/`)

Module complet : parser/builder ISO GameCube en pur Python, extraction TGC, et playbooks par jeu.

**Outil requis** : [DolphinTool](https://dolphin-emu.org/) (inclus dans Dolphin Emulator)

```
# Ajouter DolphinTool au PATH, par exemple :
# Windows : ajouter "C:\Program Files (portable)\dolphin-dev" au PATH systeme
# Le module cherche d'abord dans le PATH, puis dans les emplacements connus en fallback
```

### PSX (`psx/`)

A venir. Necessitera `mkpsxiso` / `dumpsxiso`.

## Structure du projet

```
ai-console-game-patchs/
  ngc/              Module GameCube (package Python)
    core.py         Parser/builder ISO GC pur Python
    dolphin.py      Helpers DolphinTool (extract, convert)
    playbooks/      Scripts de patch par jeu
  psx/              Module PSX (a venir)
  out/              ROMs patchees (gitignored)
  unpacked/         Fichiers extraits temporaires (gitignored)
  PLAYBOOKS.md      Catalogue de tous les patches tentes
```

## Utilisation

Placer les ROMs sources (NTSC + PAL) dans le meme dossier que ce projet (ou passer `--ntsc`/`--pal`).

```bash
# Depuis la racine du projet :
python -m ngc.playbooks.usm_french      # Ultimate Spider-Man
python -m ngc.playbooks.pm_french       # Paper Mario TTYD
python -m ngc.playbooks.ac_french       # Animal Crossing (extraction TGC)

# CLI generique :
python -m ngc list game.iso
python -m ngc extract game.iso output_dir/
```

## Convention de nommage des ROMs

```
GameName-(Region)(Languages)(GameID)[RevN].rvz
```

Exemples :
```
Ultimate_SpiderMan-(NTSC-U)(En)(GUTE52)(Rev0).rvz
Ultimate_SpiderMan-(PAL)(Fr)(GUTF52)(Rev0).rvz
Paper_Mario_TTYD-(NTSC-U)(Hack)(Fr)(G8ME01)[Rev0].rvz
```
