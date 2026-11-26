# 0003 — I gate girano su macchine proprie e pubblicano stati del commit

Stato: accettata (2026-11-26)

## Contesto

I check obbligatori di una PR giravano su GitHub Actions. Quando Actions non è disponibile per il repository (per esempio per limiti di fatturazione) i check restano rossi qualunque sia il codice: il segnale non dice più nulla e ogni merge richiede un'eccezione.

## Decisione

I gate (suite di test, test end-to-end) girano su macchine controllate dall'owner, sullo SHA esatto della PR, e pubblicano il risultato come stato del commit su GitHub. La PR si legge dagli stati del commit. Il workflow di Actions resta nel repository come definizione dei comandi e torna utile se Actions torna disponibile, ma non è la fonte del verdetto.

Un gate non eseguito resta «non verificato» e va dichiarato: non si sostituisce con un controllo più stretto e non si considera verde.

## Alternative scartate

- **Aspettare Actions.** Scartata: lascia ogni PR senza verdetto per un tempo che non dipende dal lavoro.
- **Verifiche locali riportate a mano nel testo della PR.** Scartata come regola: non sono legate allo SHA e non si leggono a colpo d'occhio. Restano ammesse come ripiego dichiarato.
- **Togliere i check obbligatori dalla protezione del branch.** Non decisa qui: è una scelta dell'owner sul singolo repository.

## Misura

Quota di PR unite con tutti gli stati dei gate verdi sulla head. Alla data della decisione il runner dei gate esiste ma la suite completa non è ancora stata eseguita sulla macchina dedicata: finché non lo è, questa decisione è verificata solo in parte.
