# 0004 — Il watchdog di inattività dei thread è spento

Stato: accettata (2026-11-26), esecuzione in attesa

## Contesto

L'harness in uso era stato esteso con un watchdog che, quando un thread figlio resta inattivo, mette in coda nel thread padre un avviso da verificare. Lo scopo era non perdere figli bloccati.

## Decisione

Il watchdog viene spento passando alla build dell'harness che non lo avvia. Un thread padre che delega aspetta la consegna del figlio con lo strumento di attesa dell'harness e, se serve, ne legge lo stato di propria iniziativa.

## Alternative scartate

- **Alzare la soglia di inattività.** Scartata: gli avvisi inutili arrivavano su figli che stavano lavorando o avevano già consegnato, non su figli lenti.
- **Tenerlo e ignorare gli avvisi.** Scartata: ogni avviso costa un turno del thread padre e interrompe il lavoro in corso.

## Misura

In una sessione di lavoro lunga il watchdog ha prodotto quattro avvisi, nessuno dei quali ha portato a un'azione. Il criterio per riaccenderlo è un caso documentato di figlio bloccato che l'attesa normale non ha rilevato.

Lo spegnimento richiede la chiusura dell'harness e va fatto dall'owner da fuori: finché non è eseguito, gli avvisi continuano ad arrivare.
