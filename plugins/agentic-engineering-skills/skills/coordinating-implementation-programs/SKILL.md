---
name: coordinating-implementation-programs
description: "Coordina una mappa approvata di piani di implementazione, avviando thread in parallelo e gestendo dipendenze, integrazione e chiusura."
---

# Coordinare una mappa di implementazione

Coordina il programma approvato; sei l’unico autore della sua mappa dei
contratti. Delega esecuzione e review ai thread-piano. Per un piano isolato
usa direttamente `sequential-task-orchestrator`.

## 1. Fonti, dipendenze e parallelismo

Leggi istruzioni delle repository, workflow, mappa, spec e piani approvati.
In ripresa riconcilia queste fonti con ledger, thread, branch e PR reali;
la recenza di un documento o una checklist non dimostrano integrazione.

Per ogni dipendenza identifica consumatore, componente, produttore, target
con revisione e prove di disponibilità. Un commit nel solo branch del
produttore non sblocca il consumatore. Prefissi e integrazioni parziali
seguono il workflow; conserva lo stato necessario a riprenderli.

**Avvia più thread-piano in parallelo** con prerequisiti soddisfatti: usa la
mappa per verificare l’assenza di collisioni o la loro gestione esplicita
(ownership, compatibilità, coordinamento). Applica gli ordini e i punti di
stop della mappa alle attività coinvolte; lascia avanzare gli altri piani.
Rispetta risorse e limiti dell’host. La sequenza interna di ciascun
orchestratore non impone una sequenza globale fra piani.

Preserva checkout, fork, sessioni e processi estranei al programma anche
nelle pulizie. Porta all’owner conflitti fra fonti, cambi di contratto o
comportamenti non coperti; usa il mandato già concesso per i passi ordinari.

Autorizza gli orchestratori di implementazione solo entro il perimetro
definito da mappa dei contratti, piani e spec approvati. Per ogni singola
richiesta fuori perimetro, attendi il permesso esplicito dell’utente prima
di autorizzarla. Un’eccezione concessa non autorizza richieste successive.

## 2. Assegna un thread a ogni piano

Crea **un thread-piano visibile all’utente** con
`sequential-task-orchestrator`. Questo crea a sua volta **thread distinti
di implementazione e review per task**, secondo la propria skill, e possiede
ledger, intero ciclo PR, merge autorizzato e cleanup del run.

Questi ruoli richiedono thread, **non subagents né processi CLI sostitutivi**.
Se l’host non li offre, segnala il blocco. Restano ammessi i comandi di gate
e review locale previsti dalla repository. Il master non crea un secondo
thread di verifica della PR.

Fornisci un brief con:

- workflow; piano, spec e mappa leggibili, con revisione/SHA;
- task o prefisso, risultati attesi, dipendenze e punti di stop;
- `sequential-task-orchestrator`, progetto, branch, base SHA e vincoli di worktree;
- `pr_base`; `integration_target` solo per integrazione per-task esplicitamente prevista;
- autorizzazioni, limiti, fallimenti noti della base e report richiesto.

Risolvi i riferimenti mancanti prima del lancio. Nei nuovi run l’orchestratore
crea branch e worktree; nelle riprese riconcilia quelli esistenti col ledger.
Passa fonti e vincoli senza introdurre algoritmi o riscrivere il comportamento.

## 3. Segui i thread e aggiorna la mappa

Usa gli strumenti dell’host, con notifiche o snapshot compatti. Registra
nello stato canonico piano, ID confermato, host, branch/worktree, revisioni
e stato. Tieni separati gli ID provvisori: creazioni e proposte pendenti
occupano uno slot, senza essere thread avviati confermati.

Timeout, messaggi accodati e fine turno non completano un piano. Per prove
mancanti continua sullo stesso thread. Se attende l’owner, indica l’azione
necessaria e mantieni lo slot anche quando non puoi fermarlo o archiviarlo.
Crea un sostituto solo dopo fallimento definitivo o chiusura confermata,
riconciliando identità, output e stato Git. Non aggirare dinieghi tramite
altri thread. I piani compatibili proseguono negli slot disponibili.

Verifica report contro commit, target, worktree e risultati effettivi;
distingui skill invocate, concluse e correzioni applicate. Rimanda fix e
riverifiche allo stesso thread-piano. Per blocchi identifica causa,
responsabile e condizione di sblocco, applicando solo retry autorizzati.

Aggiorna la mappa dopo merge, decisioni o cambi di dipendenza, con prove e
revisioni; avvisa i thread interessati. Consultala prima di assegnazioni e
handoff. Risolvi i conflitti di contenuto nel thread competente.

## 4. Verifica readiness, autorizza e chiudi

Il thread-piano segue il ciclo PR canonico della repository, comprese review
indipendente, ottimizzazioni, riverifiche e attività post-merge. In Alfe AI app
la fonte è `docs/development/CODING_STANDARDS.md`, sezione «PR review e merge»,
risolta nella repository del run. Mantieni procedure e comandi in quella fonte.

Ricevi PR, base, head finale, prove di readiness e blocchi. L’accettazione
dei task, un reminder o un checker positivo non sostituiscono tali prove.
Quando i prerequisiti sono soddisfatti, dai il via libera al thread-piano:
questo esegue il merge autorizzato, verifica il target e completa post-merge,
cleanup e aggiornamenti documentali/indici richiesti.

Il via libera del master non amplia il mandato: rispetta l’autorizzazione
esplicita per merge in `main` e gli eventuali gate per comando della repository,
riusando gli OK validi. Un target indicato non concede permessi.

Verifica SHA di integrazione, controlli e cleanup nel report di chiusura;
aggiorna la mappa e archivia il thread solo dopo chiusura effettiva. Sblocca
le voci dipendenti secondo la mappa, senza attendere gli altri piani compatibili.

Riporta stato per piano/pacchetto, prossime azioni, blocchi e decisioni richieste,
distinguendo pass, fail e non eseguito, implementazione, integrazione e rilascio.
Concludi il programma quando tutte le unità e le chiusure previste sono verificate,
oppure l’owner ne ha ridefinito il perimetro.
