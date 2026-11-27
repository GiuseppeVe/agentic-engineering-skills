# 0007 — Confine a tre livelli: plugin pubblico, workspace della factory e repository di prodotto

Stato: accettata (2026-11-27)

## Contesto

L'ADR 0002 ha reso il plugin `agentic-engineering-skills` l'unica fonte delle regole di processo, ma nella pratica due problemi restavano aperti:

- `development-process` teneva insieme le regole del lavoro quotidiano e l'orchestrazione di programmi multi-pacchetto, in italiano mentre il resto delle skill implementative era in inglese;
- le skill di implementazione contenevano nomi di modelli hardcoded e non era esplicitato dove dovessero stare le scelte specifiche dell'operatore (topologia dei repository, macchine dei gate, routing dei modelli, convenzioni di lingua) rispetto al metodo pubblico e ai singoli repository di prodotto.

## Decisione

1. **Separazione a tre livelli.**
   - **Plugin pubblico (`agentic-engineering-skills`):** contiene solo il metodo portabile e agnostico rispetto a prodotti, macchine e modelli specifici. Tutte le skill del plugin sono scritte in inglese e usano profili di ruolo invece di nomi o versioni di modelli hardcoded.
   - **Workspace locale della factory dell'operatore:** contiene la topologia e le preferenze operative dell'operatore (indice dei repository, macchine/runner disponibili, routing concreto dei modelli, eventuali convenzioni di lingua per i report).
   - **Repository di prodotto:** contiene solo codice del prodotto, documenti di prodotto, hook Git, CI e i valori locali dei controlli (comandi di verifica, nomi degli stati, standard di codice locali — ADR 0001).
2. **Divisione di `development-process` per carico cognitivo e di contesto.**
   - `references/daily-workflow.md`: regole sempre applicabili al lavoro quotidiano (mandato e Git, verifica, fase PR, chiusura, bilancio del processo).
   - `references/program-orchestration.md`: regole caricate solo quando si coordinano piani multi-task o programmi multi-pacchetto (delega, preflight, ciclo piani/pacchetti, consegna dei child, limiti di convergenza).

## Alternative scartate

- **Mantenere un mix italiano/inglese e modelli di default dentro le skill del plugin.** Scartata: ogni uscita di un nuovo modello rende obsolete più skill e i termini di stato (`done` vs `complete`) tendono a divergere tra lingue.
- **Inserire la topologia locale dell'operatore nel plugin pubblico.** Scartata: viola la portabilità del plugin e rischia di esporre dettagli privati.
- **Spostare tutto il metodo nel workspace locale.** Scartata per lo stesso motivo dell'ADR 0002: vale su una sola macchina e non distribuisce skill e hook come plugin versionato.

## Misura

Zero riferimenti a prodotti specifici, macchine o versioni hardcoded di modelli dentro le skill del plugin (verificato da `audit:public` e dai test di contratto); separazione netta tra caricamento del flusso quotidiano e regole di programma multi-pacchetto.
