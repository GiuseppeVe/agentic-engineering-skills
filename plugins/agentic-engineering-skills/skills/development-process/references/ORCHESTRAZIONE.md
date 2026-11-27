# Orchestrazione

Guida per l'agente che coordina il lavoro e delega a sottoagenti o ad altri thread. Completa [PROCESSO.md](PROCESSO.md). Le skill `coordinating-implementation-plans`, `plan-orchestrator` e `task-implement` rimandano qui.

## Delega ai sottoagenti

Prima di delegare, chiedersi cosa il sottoagente dovrebbe indovinare o riscoprire. Il brief contiene:

- **Obiettivo** in una frase, **vincoli** (file, ambito, cose da non toccare) e **criterio di successo**.
- **Riferimenti:** ADR, spec, piani e file da leggere per primi.
- **Fatti e ipotesi** separati; i dettagli emersi solo in chat riportati esplicitamente.
- Rimandi a questi documenti per le regole di processo, senza riscriverle.

Contesto nuovo per esplorazioni e task autonomi. Per una review indipendente: contesto nuovo con sole evidenze, senza la propria diagnosi. Ogni sottoagente restituisce esito, evidenze (comandi, `file:linea`), ipotesi non verificate e cosa resta.

## Conduzione di un run

- **Avvio.** Quando il repository fornisce un preflight dell'host, chi avvia il run lo fa eseguire su ogni macchina prima del primo gate o push. Poi presenta all'owner, una sola volta, un elenco: i problemi del preflight e i push e merge previsti. Ciò che è nell'elenco non si chiede di nuovo. L'elenco non autorizza mai un'integrazione in `main`.
- **Trasporto del codice.** Il codice arriva alla macchina dei gate solo tramite git: push del branch o file bundle. Brief e messaggi non contengono patch né base64.
- **Gate.** Quando il repository fornisce un gate runner che si accoda da solo, i gate si chiedono con quello: nessun agente assegna slot o interroga lock.
- **Domande all'owner.** Una domanda non ferma il lavoro che non ne dipende: si prosegue e la si ripropone nel report successivo.
- **Esiti dei child.** Solo `done`, `partial` o `blocked`. Il master agisce su `partial`, `blocked`, conflitti e deviazioni dal piano; un `done` aggiorna lo stato senza un suo turno.
- **Messaggi all'owner.** Prima riga: «Ti serve: niente» oppure «Ti serve: <azione> in <link>». Il dettaglio segue. Ogni thread citato ha il link.

## Ciclo di vita di piani e pacchetti

Una mappa dei contratti raggruppa i piani in pacchetti; ogni pacchetto ha un branch `pkg/*` che alla fine contiene tutti i suoi piani.

**Piano → `pkg/*`.** PR del piano verso `pkg/*`; [fase PR](PROCESSO.md#fase-pr); con tutto verde l'agente avvisa l'owner («Ti serve: niente. Piano <id>: verde, lo porto in `pkg/<x>` (PR #N).») e unisce senza attendere.

**Integrazione continua.** Ogni mappa ha un branch `integration/<mappa>`, creato da `origin/main` all'avvio. Il thread che ha unito il piano nel `pkg/*` unisce subito quel `pkg/*` in `integration/<mappa>`, fa il push ed esegue la suite backend con il comando dei gate del repository. Un rosso torna al thread del piano che l'ha introdotto; un conflitto va al master come `blocked`. Niente force-push.

**Pacchetto → `main`.** Con tutti i piani in `pkg/*`: una sola PR da `pkg/*` verso `main`, aperta con la suite backend già verde su `integration/<mappa>`; fase PR; poi all'owner: «Ti serve: autorizzare il merge in `main` in <link PR>.»

**Stato.** Lo stato di piani e pacchetti si legge da GitHub, mai dal log dell'orchestratore: `gh pr list --base pkg/<x> --state merged --json number,title,body,mergeCommit`, associando PR e piano con la riga `Piano: <id>` del body. Una PR senza quella riga è «non associata» e non cambia la fase.

Quando la CI del repository controlla mandati e pacchetti, il master committa il documento di mandato prima di delegare un piano e il file di pacchetto alla creazione del pacchetto.

## Consegna dei child

Il messaggio finale di un thread avviato da un altro inizia con una riga di stato:

```text
esito=<done|partial|blocked> | pr=<URL|none> | sha=<sha|none> | base=<branch|none> | report=<percorso assoluto|none>
```

Il dettaglio sta sotto la riga o nel report. `done` solo se il compito è completo e verificato, con `sha` presente su origin; il lavoro accettato solo in locale è `partial`. Chi riceve verifica `sha` su origin con git o `gh`.

## Piani e limiti di convergenza

- I piani contengono contratti, interfacce, test e criteri di accettazione, non l'implementazione completa.
- Prima dell'implementazione il piano riceve una review avversariale su stati, concorrenza, cancellazione, autorizzazioni e privacy.
- I criteri di accettazione sono provabili con fixture; le prove native o live sono task separati.
- Due esiti negativi di review sullo stesso modulo: un ridisegno unico, con matrice stati/eventi.
- Tre slice dello stesso task senza accettazione: escalation all'owner.
- Il reviewer non indica l'unità di lavoro successiva.

## Thread OpenCode

Un thread su un'istanza OpenCode (DeepSeek via Vibe) funziona solo con il bridge loopback e il server OpenCode accesi. Script e procedura stanno nel repository che fornisce il bridge e nel riferimento `t3-deepseek-routing.md` della skill `plan-orchestrator`. Con `ECONNREFUSED` non ritentare: accendere il bridge. Non cambiare modello o provider di propria iniziativa.
