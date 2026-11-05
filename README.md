# Acquevenete per Home Assistant

Integrazione custom (installabile via HACS) che porta i consumi idrici del
portale self-service di Acquevenete dentro Home Assistant, con **dettaglio
giornaliero** (risoluzione 1 m³), pronti per la dashboard Energia → Acqua.

> ⚠️ **Non ufficiale.** Usa endpoint non documentati del portale
> `sol.acquevenete.it`. Può smettere di funzionare se Acquevenete cambia il sito.
> Nessuna affiliazione con Acquevenete.

## Cosa fa

- Effettua il **login al portale** con le tue credenziali e ricava da solo il
  token della webapi (che ruota a ogni accesso), rinnovandolo quando scade.
- Legge la telemetria giornaliera del contatore smart e la espone in due sensori.
- Ricostruisce l'intero **storico giornaliero** e lo tiene aggiornato nelle
  statistiche a lungo termine, così la dashboard Energia mostra da subito tutta
  la cronologia invece di partire da zero.

## Entità create

- `sensor.<nome>_water_meter` — indice cumulativo del contatore in m³,
  `state_class: total_increasing`, aggiornato ~1 volta al giorno. È la sorgente
  di verità con lo storico completo attaccato alle proprie statistiche.
- `sensor.<nome>_daily_consumption` — consumo dell'ultimo giorno disponibile in
  m³. Espone come attributo `reference_date` la data a cui il valore si riferisce
  (la telemetria può avere qualche giorno di ritardo, quindi non è sempre
  "oggi").

## Installazione (HACS)

1. HACS → menu ⋮ → **Repository personalizzati**.
2. Aggiungi `https://github.com/matteobreschig/hacs-acquevenete`,
   categoria **Integration**.
3. Installa **Acquevenete** e riavvia Home Assistant.
4. Impostazioni → Dispositivi e servizi → **Aggiungi integrazione** →
   Acquevenete.

## Configurazione

L'integrazione fa il login al posto tuo: inserisci **e-mail** e **password** del
portale. Il token webapi viene ricavato in automatico e rinnovato quando scade.

Ti serve solo il **codice fornitura** nel formato `12345678-1`. Lo trovi nella bolletta.

## Dashboard Energia → Acqua

Aggiungi in Impostazioni → Dashboard → Energia → **Consumo acqua** il sensore
`..._water_meter`: contiene già lo storico completo. Da solo basta per una
dashboard corretta.

## Servizio `acquevenete.import_history`

Ribalta l'intero storico giornaliero sulle statistiche a lungo termine di un
`statistic_id` a tua scelta.

```yaml
action: acquevenete.import_history
data:
  statistic_id: sensor.<entita_target>
```

È idempotente: puoi rilanciarlo, riscrive lo stesso storico senza duplicare.
Nota: la storia finisce nelle **statistiche**, non negli stati, quindi la vedi in
Strumenti per sviluppatori → **Statistiche**, in una scheda *Statistics Graph* o
nella dashboard Energia — non necessariamente nel valore live del sensore.

## Note tecniche

Acquevenete non offre API pubbliche: l'integrazione si comporta come il browser
quando accedi al portale self-service.

- **Login.** Il portale è un'applicazione ASP.NET WebForms. Prima di inviare le
  credenziali l'integrazione apre la pagina di login e ne legge i campi nascosti
  (`__VIEWSTATE`, `__VIEWSTATEGENERATOR`, `__AntiXsrfToken`), che il server si
  aspetta di ricevere indietro insieme a email e password.
- **Token.** Ad accesso riuscito il portale imposta un cookie `sol-<sessione>-at`
  il cui valore è un GUID: è il token che compare nel percorso delle chiamate
  `/webapi/api/v1/...`. Cambia a ogni login, per questo dopo un po' smette di
  funzionare.
- **Rinnovo automatico.** Una sessione scaduta si riconosce da una risposta
  diversa da 200, da un rimando HTML alla pagina di login oppure da dati vuoti.
  In questi casi l'integrazione rifà il login una volta e ripete la richiesta.
- **Credenziali errate.** Il portale non restituisce un errore esplicito: il
  cookie del token semplicemente non arriva, ed è questo il segnale usato per
  avvisarti.
- **Dati.** I consumi arrivano dall'endpoint del grafico settimanale, che dentro
  ogni settimana contiene una lettura giornaliera del contatore smart. Il
  portale viene interrogato ogni 6 ore.
- **Nessuna dipendenza esterna.** L'integrazione usa solo librerie già presenti
  in Home Assistant.

## Limiti noti

- Risoluzione massima **giornaliera** (1 m³): il portale non espone dati orari.
- I dati giornalieri sono telemetria grezza (`SMART METERING`, non validata):
  possono avere piccoli ritardi o correzioni rispetto alle letture di saldo.

## Come è stato sviluppato

Questa integrazione è stata scritta con l'aiuto di Claude (Anthropic), un
assistente basato sull'intelligenza artificiale. Ho definito io obiettivi e
requisiti, ho analizzato il funzionamento del portale e ho provato ogni versione
sulla mia installazione di Home Assistant con un contatore reale. Il codice
generato è stato rivisto prima di ogni rilascio, ma segnala pure con una issue
qualsiasi comportamento strano.

## Disclaimer

Progetto personale, fornito "così com'è", senza garanzie. I marchi citati
appartengono ai rispettivi proprietari.
