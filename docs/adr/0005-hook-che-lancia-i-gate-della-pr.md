# 0005 — Un hook del plugin lancia i gate quando una PR esce dalla bozza

Stato: accettata (2026-11-26)

## Contesto

I gate girano su macchine proprie e pubblicano stati del commit (ADR 0003). Una regola scritta chiedeva agli agenti di rilanciarli su quelle macchine quando GitHub Actions non è disponibile. La regola non è stata seguita: le PR uscivano dalla bozza senza stati dei gate sulla head, e l'owner se ne accorgeva al momento del merge.

## Decisione

Il plugin registra un solo hook generale, a livello utente e non bloccante. Dopo un comando di shell riuscito che apre una PR non in bozza o la segna come pronta, l'hook chiama una convenzione del repository: se il `package.json` alla radice definisce lo script `gates:pr`, lo avvia in background passando la PR quando è nota, e dice all'agente dove si trova il log. Se lo script non c'è, non fa nulla.

L'hook lancia e basta: non blocca il comando, non attende, non verifica l'esito, non ricorda nulla e non scrive marker. È generale nello spirito dell'ADR 0002: il plugin conosce solo il nome della convenzione; quali sono i gate, dove girano e se per quella PR c'è qualcosa da eseguire lo decide il repository con il proprio script.

Il blocco del merge non sta nell'hook. Sta nella protezione del branch su GitHub, che richiede gli stati dei gate sulla head. Gli agenti operano con un account separato e senza diritti di amministrazione: la possibilità di scavalcare la protezione resta solo all'owner.

Questa decisione non restringe l'ADR 0001: l'hook vive nella factory e si installa a livello utente; nel repository di prodotto resta solo lo script che i gate avrebbero comunque.

## Alternative scartate

- **Solo la regola scritta.** Provata e inefficace: è il problema descritto nel contesto.
- **Un servizio sulle macchine dei gate che interroga GitHub a intervalli.** Scartata: è un processo in più da installare e tenere vivo, e non serve finché tutte le PR sono aperte dagli agenti, cioè da sessioni in cui l'hook è attivo.
- **Un hook di sessione dentro il repository di prodotto.** Scartata: è ciò che l'ADR 0001 ha tolto.

## Misura

Quota di PR non in bozza la cui head ha gli stati dei gate senza che qualcuno li abbia lanciati a mano. Alla data della decisione l'hook è coperto da test automatici ma non è ancora stato osservato in una sessione reale: il primo dato è la prima PR aperta dopo l'installazione di questa versione.
