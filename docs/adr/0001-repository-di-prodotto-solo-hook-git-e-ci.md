# 0001 — Nei repository di prodotto restano solo hook Git e CI

Stato: accettata (2026-11-26)

## Contesto

Un repository di prodotto aveva accumulato macchinari di processo eseguiti dentro la sessione dell'agente: hook di avvio e chiusura sessione, guardia sui comandi, registro degli agenti, manifest di consegna, verificatore e marker delle PR, script di pulizia. Ogni meccanismo era nato per un problema reale, ma l'insieme bloccava gli agenti: una sessione aperta in quel repository spendeva più tempo a soddisfare i meccanismi che a lavorare, e un compito sul processo stesso non riusciva a concludersi dall'interno.

## Decisione

In un repository di prodotto restano solo i controlli automatici legati a Git e alla CI: hook Git (pre-commit, pre-push), gate eseguiti sullo SHA, guard dei documenti, workflow di CI. Nessun hook di sessione dell'agente e nessuno script di processo che l'agente deve invocare per poter procedere.

Le regole di processo stanno nella factory (ADR 0002).

## Alternative scartate

- **Alleggerire i meccanismi lasciandoli nel repository.** Scartata: il costo veniva dall'insieme, non da un singolo pezzo, e ogni alleggerimento richiedeva di passare dagli stessi meccanismi.
- **Tenere gli hook di sessione solo come avvisi.** Scartata: un avviso che non blocca viene ignorato, uno che blocca riporta al problema di partenza.

## Misura

La rimozione nel primo repository ha tolto 87 file e 10.679 righe senza toccare il codice del prodotto; hook Git e guard sono rimasti verdi. Resta da misurare l'effetto sui tempi delle sessioni: il confronto è tra la durata di un compito tipo prima e dopo.
