# Catalogue des patches

## Patches fonctionnels

### Ultimate Spider-Man (GameCube)
- **Playbook** : `ngc.playbooks.usm_french`
- **Methode** : Country code E->F dans boot.bin + audio FR (_FR.WBK) depuis PAL + pak texte PAL + films PAL
- **Resultat** : NTSC 60Hz + texte FR + audio FR + cinematiques FR
- **Notes** : Les DOL NTSC et PAL sont 100% identiques. Le country code controle la langue. Approche la plus propre possible.

### Paper Mario: The Thousand-Year Door (GameCube)
- **Playbook** : `ngc.playbooks.pm_french`
- **Methode** : Remplacement de msg/US/*.txt par msg/FR/*.txt du PAL + e/us/ par e/fr/
- **Resultat** : NTSC 60Hz + texte FR complet (260 fichiers)
- **Notes** : DOLs differents mais le texte est dans des .txt separes par langue. Le DOL NTSC charge msg/US/ qu'on remplace par le contenu FR. Pas de modif du DOL.

### Animal Crossing (GameCube)
- **Playbook** : `ngc.playbooks.ac_french`
- **Methode** : Extraction du TGC francais (forest_Frn_Final_PAL50.tgc) depuis le disque PAL, rebuild en ISO standalone
- **Resultat** : Version FR standalone (PAL 50Hz, forcable en 60Hz dans Dolphin)
- **Notes** : NTSC et PAL sont fondamentalement incompatibles (architectures differentes, TGC sub-discs dans PAL). Un vrai hybride NTSC+FR n'est pas faisable. Ce playbook extrait simplement la version FR du PAL.

## Patches impossibles / en attente

### Star Fox Assault (GameCube)
- **Status** : Impossible (approche simple)
- **Raison** : DOLs differents, 68 fichiers communs modifies (dont les .rel = modules de code), fichiers .fpc de niveau differents. Le code, les modules ET les donnees different entre NTSC et PAL.

### Animal Crossing (GameCube) - hybride NTSC+FR
- **Status** : Impossible
- **Raison** : NTSC et PAL ont des architectures completement differentes. NTSC = fichiers .arc/.rel, PAL = TGC sub-discs par langue. DOLs incompatibles (918 KB vs 132 KB). Aucun fichier commun sauf opening.bnr.

### Spyro: A Hero's Tail (GameCube)
- **Status** : Working (audio FR only, texte FR non activable en NTSC 60Hz)
- **Playbook** : `ngc.playbooks.spyro_aht_french`
- **Methode** : Patch in-place de Filelist.000 (archive Eurocom, format reverse engineered). Les 38 fichiers `eng_*.sfx` sont ecrases par les `fre_*.sfx` du PAL aux memes offsets + byte de langue 0x00->0x06 dans les sound banks.
- **Resultat** : NTSC 60Hz + audio FR (voix, dialogues, cinematiques). 38/42 fichiers patches (4 `_mini_sgt` skipped: FR legerement plus gros que EN, pas de gap).
- **Texte FR** : Le texte francais EXISTE dans text.edb (UTF-16-LE, 1.5 MB reel vs 2.4 KB dans le manifest). Le NTSC contient deja toutes les langues. MAIS le selecteur de langue texte est controle par le DOL, et le DOL NTSC est hardcode sur English. Tente : swap .sfx lang byte, PAL game.dmp, PAL DOL, country code P, full PAL sys/ — aucun n'active le texte FR avec le Filelist NTSC.
- **Conclusion** : Pour avoir texte FR, il faut utiliser le full PAL (sys/ + Filelist PAL) mais ca donne du 50Hz. Pas de solution propre NTSC 60Hz + texte FR sans reverse engineering du DOL PowerPC pour trouver et patcher le language index. Le patch audio-only reste le meilleur compromis.

