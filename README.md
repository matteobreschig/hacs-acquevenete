# Acquevenete per Home Assistant

Integrazione custom (installabile via HACS) che legge i consumi acqua dal portale
self-service di Acquevenete e li porta in Home Assistant con **dettaglio giornaliero**
(risoluzione 1 m³), pronti per la dashboard Energia → Acqua.

> ⚠️ Non ufficiale. Usa endpoint non documentati del portale, in cui il GUID
> dell'account fa da chiave nell'URL. Può smettere di funzionare se Acquevenete
> cambia le API o se il token scade.

## Cosa crea

- **Sensore** `sensor.acquevenete_..._water_meter`: indice cumulativo del contatore
  in m³, `state_class: total_increasing`, aggiornato ~1 volta al giorno. Utile per
  automazioni, rilevamento perdite, lettura corrente.
- **Statistica esterna** `acquevenete:<fornitura>_consumption`: l'intera serie
  storica giornaliera dei consumi (somma), ricostruita dal contatore e mantenuta
  aggiornata a ogni poll. È quella da aggiungere alla dashboard Acqua per avere
  subito lo storico invece di aspettare mesi.

## Credenziali e numero fornitura

L'integrazione fa il **login al posto tuo**: inserisci e-mail e password del
portale. Il token webapi viene ricavato in automatico dopo il login (dal cookie
`sol-<sessione>-at`) e rinnovato da solo quando scade — non devi più incollarlo
a mano.

Ti serve solo il **numero di fornitura** nel formato `12345678-1`. Lo trovi nella
sezione consumi del portale, oppure dalla scheda Network del browser (F12) nelle
chiamate `.../api/v1/supply-week-consumption-chart/<GUID>/<FORNITURA>/1/`: è il
`<FORNITURA>`.

> ⚠️ Le credenziali vengono salvate da Home Assistant in chiaro in
> `.storage/core.config_entries` (standard per le integrazioni con login).
> Tienile su un'istanza a cui accedi solo tu e non committarle mai.

## Installazione (HACS)

1. HACS → Integrazioni → menu ⋮ → **Repository personalizzati**.
2. Incolla l'URL del tuo repo GitHub, categoria **Integration**, aggiungi.
3. Installa "Acquevenete", riavvia Home Assistant.
4. Impostazioni → Dispositivi e servizi → **Aggiungi integrazione** → Acquevenete.
5. Inserisci e-mail, password e numero fornitura.

## Dashboard Acqua

Impostazioni → Dashboard → Energia → **Consumo acqua** → aggiungi la statistica
`acquevenete:<fornitura>_consumption` (per lo storico) oppure il sensore
`total_increasing` (solo dati da adesso in poi).

## Logo e icona

Il logo sta nella cartella `custom_components/acquevenete/brand/` (meccanismo
inline di HA ≥ 2026.3). Le immagini incluse sono **segnaposto generici**: vedi
`brand/README.md` per sostituirle con il logo ufficiale nelle dimensioni corrette.

## Note e limiti

- La granularità massima disponibile dal portale è **giornaliera** (1 m³). Non
  esistono dati orari.
- I dati giornalieri sono telemetria grezza (`SMART METERING`, non validata):
  possono avere piccoli ritardi o correzioni rispetto alle letture di saldo
  fatturate.
- Il parametro `page` (default `1`) è il segmento finale dell'URL del week-chart.
  Se noti giorni recenti mancanti, prova a cambiarlo.
- Il cambio contatore (indice che riparte da 0) è gestito: `total_increasing` e il
  calcolo dello storico trattano il calo come reset.
