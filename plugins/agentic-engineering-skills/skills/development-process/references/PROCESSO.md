# Processo di sviluppo

Regole di processo per gli agenti che lavorano in un repository che adotta questo workflow. Valgono come indicazioni: nessun hook le impone. Nel repository restano solo i gate che automatizzano i controlli: hook git e job di CI.

## Mandato e Git

- Discovery, audit e pianificazione sono in sola lettura.
- Implementazione, commit, push, PR e operazioni live sono ambiti distinti: operare in quello autorizzato. Credenziali e strumenti disponibili non ampliano il mandato.
- Prima di chiedere all'owner, esaurire le vie legittime nel mandato. Chiedere solo decisioni di prodotto o di contratto, permessi e credenziali.
- Deploy, risorse cloud, credenziali e decisioni di prodotto richiedono l'owner.
- Percorso: decisioni risolte → spec → review owner → piano → implementazione circoscritta → verifica e review → integrazione autorizzata.
- Codice, configurazione e test si modificano in un branch e in un worktree dedicati (`<root-repo>/.worktrees/<nome>`); il checkout su `main` serve a leggere lo stato corrente. Le sole modifiche documentali sono esenti.
- Stage dei soli percorsi toccati, mai `git add .`. Niente push diretto a `main`, force-push o reset distruttivi.
- Preservare il lavoro altrui: controllare stato, branch, SHA e diff prima di editare o committare. Chi apre un worktree o un branch lo chiude a fine lavoro, oppure lo elenca nel report finale con percorso, branch e stato. L'inventario dei worktree di un repository, ovunque stiano su disco, si ottiene con `scripts/worktrees.mjs` di questa skill; la rimozione riguarda solo quelli uniti e puliti e parte su richiesta dell'owner.
- Il merge in `main` richiede l'autorizzazione esplicita dell'owner per quella PR. Il merge verso branch non-`main` è dell'agente.

## Verifiche

- Dichiarare completata un'azione solo dopo averne verificato il risultato. Un merge si riporta con numero di PR e branch base; un push con lo SHA presente su origin.
- Prove proporzionate al contratto modificato. Test di persistenza, browser o servizi reali non si sostituiscono con mock.
- Skip e controlli non eseguiti non sono pass. Un gate saltato resta non verificato, mai verde. Non indebolire i gate.
- Tenere distinti: accettato in locale, disponibile in remoto, integrato nel target, verificato sullo SHA in esecuzione.
- Gate rosso: riprodurlo, correggere nel perimetro le regressioni del diff, registrare a parte i problemi preesistenti.
- In messaggi, prove e commenti PR non compaiono token, trascrizioni personali né output grezzi degli strumenti.

## Fase PR

Ordine su ogni PR, a ogni livello (piano verso `pkg/*`, pacchetto verso `main`, PR singola):

1. **Apertura.** PR in bozza dal branch di lavoro. Nel body: `Impatto ADR: nessuno | NNNN | nuovo`, `Piano: nessuno | <id>` (per PR con base `pkg/*`), `Documenti: nessuno | <percorsi di spec, piano e ADR>`. Reviewer e fixer leggono i percorsi da lì: un brief di review non li ripete.
2. **Controllo locale veloce:** typecheck, lint, test dei file toccati.
3. **Review indipendente dell'intero diff**, in un thread nuovo e in sola lettura, avviata subito dopo il push e senza attese di approvazione. In parallelo il thread della PR esegue `simplify` e knip sul diff. Una sola review indipendente per SHA. Output: finding P0–P3 con `file:linea` e scenario di errore.
4. **Correzioni in un solo commit.** Ogni finding si valuta contro codice, contratto e prove: si conferma se fondato, si respinge motivando. Un solo thread corregge, esegue i gate e fa un solo push.
5. **Gate completi una volta, sulla head congelata.** Quando la PR esce dalla bozza, l'hook del plugin lancia il comando `gates:pr` del repository, se il repository lo definisce; dove l'hook non agisce, li lancia l'agente con il comando dei gate del repository. Il lancio non è un esito: chi attende reagisce a qualunque esito finale, anche rosso o assente alla scadenza. La prova è lo stato del commit su GitHub, con il file di esito come dettaglio quando il repository lo produce.
6. **Review del solo delta**, in parallelo ai gate, se le correzioni hanno toccato codice, configurazione o test.
7. **Uscita dalla bozza** a review conclusa: è il momento in cui partono i gate del passo 5. Gli stati dei gate verdi sulla head sono la condizione del merge. Un check di GitHub Actions rosso solo per billing non è un blocco.

Limiti:

- Dopo due giri di correzione il thread consegna `partial` con i conflitti aperti invece di proseguire.
- Una PR di sola documentazione passa con i guard dei documenti e la verifica dell'agente: niente suite, niente review indipendente.
- Ogni nuova head richiede di nuovo i gate del passo 5.

## Chiusura

Per ogni sessione sostanziale riportare: contesto (repository, branch, SHA), percorsi modificati, stato di integrazione (locale, pubblicato, integrato) con commit o PR, verifiche con comando ed esito, ciò che non è stato eseguito e perché, rischi residui, prossimo passo. Worktree, branch e file temporanei lasciati vanno elencati.

## Bilancio del processo

Un nuovo hook o script di processo entra solo con la misura che vuole migliorare e togliendone uno esistente.
