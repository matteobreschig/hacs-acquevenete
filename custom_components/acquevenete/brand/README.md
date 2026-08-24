# Brand images

Da Home Assistant **2026.3** le integrazioni custom includono icona e logo
direttamente qui, in questa cartella `brand/`. Home Assistant le serve tramite
`/api/brands/integration/acquevenete/<file>` e hanno priorità sulla CDN dei brand.
Il nome della cartella dell'integrazione deve coincidere con il `domain` del
`manifest.json` (`acquevenete`), e così è.

## I file (segnaposto: SOSTITUISCILI)

Le immagini attuali sono **placeholder generici** (una goccia d'acqua), NON il
logo ufficiale di Acquevenete. Sostituiscile con quello reale, rispettando le
dimensioni:

| File          | Dimensioni       | Note                                  |
|---------------|------------------|---------------------------------------|
| `icon.png`    | 256×256 (1:1)    | quadrata, sfondo trasparente          |
| `icon@2x.png` | 512×512 (1:1)    | versione hDPI                         |
| `logo.png`    | max 256 px lato  | orizzontale, sfondo trasparente       |
| `logo@2x.png` | max 512 px lato  | versione hDPI                         |

Opzionali: `dark_icon.png` / `dark_logo.png` (e relativi `@2x`) per il tema scuro.

## Dove prendere il logo ufficiale

Recupera il logo dal materiale ufficiale di Acquevenete (sito istituzionale /
eventuale press kit) e ridimensionalo alle misure sopra, mantenendo la
trasparenza. Il marchio resta di proprietà di Acquevenete: qui è usato solo per
identificare la fornitura all'interno di Home Assistant.

## Avvertenza HACS

Con HA ≥ 2026.3 l'icona compare correttamente in Impostazioni → Dispositivi e
servizi e nelle pagine dei dispositivi. Il pannello Download di **HACS** al
momento potrebbe ancora mostrare un segnaposto "icon not available": è un limite
noto lato HACS (continua a leggere dalla propria CDN e non dal proxy locale di
HA), non un problema di questa integrazione.
