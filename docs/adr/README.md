# Software factory: idea e decisioni

## L'idea

La software factory è l'insieme di harness, framework, coding agent e workflow con cui il codice viene scritto, verificato e consegnato dagli agenti AI. È un prodotto a sé: ha un proprio repository (questo), proprie regole e proprie decisioni, distinte da quelle dei prodotti che costruisce.

## A cosa serve

- **Un solo posto per il metodo.** Regole di processo, guida all'orchestrazione, skill e hook generali vivono qui e si installano come plugin a livello utente. Ogni repository di prodotto riceve lo stesso metodo senza copiarlo.
- **Repository di prodotto fatti solo di prodotto.** In un repository di prodotto restano il codice, i suoi documenti e i controlli automatici legati a Git e alla CI. Chi lavora sul prodotto non incontra macchinari di processo.
- **Agenti liberi di lavorare, controlli dove costano poco.** Il controllo sta nei punti in cui il codice cambia stato (commit, push, PR, merge) e non in ogni azione della sessione. Un meccanismo che rallenta gli agenti senza una misura che lo giustifichi viene tolto.
- **Decisioni che non si ridiscutono a ogni sessione.** Un agente che riparte senza contesto trova qui perché la factory è fatta così e cosa è già stato scartato.

## Cosa contiene questa cartella

Gli ADR registrano le decisioni sulla factory, non sui prodotti. Le decisioni di un prodotto restano negli ADR del suo repository.

Un ADR è breve e ha quattro parti: contesto, decisione, alternative scartate con il motivo, misura che la giustifica. Nessun guard li fa rispettare: valgono perché sono letti. Una decisione si cambia con un nuovo ADR che sostituisce il precedente e lo dichiara.

Questo repository è pubblico: un ADR non contiene nomi di clienti, credenziali, percorsi di macchine o dettagli riservati di un prodotto.

## Indice

| N. | Decisione | Stato |
| --- | --- | --- |
| [0001](0001-repository-di-prodotto-solo-hook-git-e-ci.md) | Nei repository di prodotto restano solo hook Git e CI | Accettata |
| [0002](0002-plugin-fonte-unica.md) | Regole, skill e hook generali hanno una sola fonte: il plugin | Accettata |
| [0003](0003-gate-su-macchine-proprie.md) | I gate girano su macchine proprie e pubblicano stati del commit | Accettata |
| [0004](0004-watchdog-di-inattivita-spento.md) | Il watchdog di inattività dei thread è spento | Accettata, esecuzione in attesa |
| [0005](0005-hook-che-lancia-i-gate-della-pr.md) | Un hook del plugin lancia i gate quando una PR esce dalla bozza | Accettata |
| [0006](0006-analisi-statica-condivisa-e-hook-su-modifica.md) | Analisi statica condivisa con Oxlint e feedback rapido su modifica | Accettata |
| [0007](0007-confine-plugin-workspace-prodotto.md) | Confine a tre livelli: plugin pubblico, workspace della factory e repository di prodotto | Accettata |
| [0008](0008-verifica-leggera-e-plan-implement-a-slice.md) | Verifica leggera orientata ai layer deterministici e orchestrazione `plan-implement` a slice | Accettata |
| [0009](0009-verifica-formale-statechart-e-skill-locali-di-prodotto.md) | Verifica formale con `statechart` ed eccezione per skill locali di verifica formale nei repository di prodotto | Accettata, sostituita in parte dalla 0010 |
| [0010](0010-modello-di-comportamento-approvato-prima-del-piano.md) | Il comportamento con stato è modellato e approvato prima del piano | Accettata |
