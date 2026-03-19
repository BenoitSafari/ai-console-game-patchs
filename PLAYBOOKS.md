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
- **Status** : Partiellement reverse engineered, crash au boot
- **Playbook** : `ngc.playbooks.spyro_aht_french`
- **Roadmap** : `ngc/playbooks/spyro_aht_french_roadmap.txt`
- **Ce qui fonctionne** : Format Filelist.bin decode (header 16B + entries 28B chacune), archive repaquetee avec 42 fichiers audio FR (eng_* -> fre_*), Filelist.bin/txt regeneres
- **Ce qui crashe** : "Invalid read from 0xdbd5feac" au boot. Cause probable : les 19,472 bytes de "tail data" dans Filelist.bin (apres les entries) contiennent probablement une hash table ou des offsets qui n'ont pas ete mis a jour. Le fichier Filelist.cfi (52 KB, role inconnu) pourrait aussi contenir des checksums invalides.

