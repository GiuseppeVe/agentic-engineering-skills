# 0008 — Verifica leggera orientata ai layer deterministici e orchestrazione `plan-implement` a slice

Stato: accettata (2026-11-27)

## Contesto

L'analisi delle sessioni reali e del catalogo skill ha evidenziato due attriti strutturali:

- **Orchestrazione a 4 livelli e review moltiplicate.** Un piano passava attraverso coordinatore di programma → `plan-orchestrator` → thread `task-implement` per singolo task → subagenti a pacchetti (`packet-contract`), con una review clean-room su ogni singolo micro-task affidata impropriamente a `test-driven-development`, seguita dalla review integrale della PR e dalla delta review. Questo moltiplicava i passaggi sullo stesso diff e azzerava il contesto dell'implementer tra task contigui dello stesso modulo.
- **Verifica dispersa ma duplicata.** Le regole anti-green-washing e la riproduzione rossa dei bug mancavano di una sede coerente, mentre la code review è già coperta dalle funzionalità native dell'host e i controlli meccanici stanno convergendo nei layer deterministici del repository (tipi, analisi statica, dead-code, suite comportamentali).

## Decisione

1. **Verifica leggera senza nuove skill.**
   - Nessuna skill dedicata `code-review` (si usa la review nativa dell'host) e nessuna skill separata `verify-before-claim` o `diagnosing-bugs`.
   - `development-process/references/daily-workflow.md` ospita la disciplina di **Verification** a piramide inversa: esecuzione ordinata dei layer deterministici del repository (L1 tipi/schemi → L2 analisi statica/lint/dead-code → L3 test comportamentali, contract, property e runtime reale), divieto di green-washing (un retry singolo non rende verde una suite fallita; skip/timeout/file esclusi restano non verificati; evidenza `final_state` legata allo SHA o diff finale; distinzione tra preesistente riprodotto sulla base e flake sullo stesso SHA) e promozione dei bug meccanici ripetuti verso L2.
   - `test-driven-development` si focalizza su scrittura test-first, riproduzione rossa prima del fix dei bug e scelta dell'oracolo adatto (unitario, contract cross-pacchetto, property-based, decodifica reale), senza più fare da reviewer generico.
2. **Sostituzione di `plan-orchestrator` e `task-implement` con `plan-implement` a 2 livelli.**
   - `task-implement` e il sottolivello `packet-contract` sono eliminati; `plan-orchestrator` è rinominato `plan-implement`.
   - Il controller `plan-implement` non scrive il codice delle slice: raggruppa i task contigui dello stesso modulo in **slice coerenti** (seguendo eventuali slice dichiarate in `writing-plans`) e li delega a **subagenti implementer persistenti per slice** (paralleli in worktree isolati solo quando le slice sono disgiunte).
   - Sulle slice marcate `risk: standard` la verifica intermedia è deterministica (TDD + layer L1/L2/L3 del repository + controllo `REQ-NNN` del controller); sulle slice marcate `risk: high` (autenticazione, privacy, persistenza/migrazioni, contratti condivisi) scatta un checkpoint di review nativa clean-room tramite subagente separato.
   - Lo slice implementer lascia il diff non committato; `plan-implement` verifica `REQ-NNN` e prove (più eventuale review `risk: high`) e committa ciascuna slice accettata sul branch del piano. La review completa della PR avviene una sola volta sulla head integrata (review nativa dell'host + `simplify`).
   - Stato unificato ovunque: `done | partial | blocked`.
3. **Contratto di consegna della slice tenuto deliberatamente leggero (aperto a revisione empirica).**
   - Lo slice implementer restituisce solo stato, `REQ-NNN`/comandi verificati, file toccati e blocchi o rischi aperti, senza schemi rigidi pesanti che comprimano l'agenticità. Un formato più rigido si introduce solo se i run reali dimostrano un problema misurabile.

## Alternative scartate

- **Aggiungere tre nuove skill (`code-review`, `verify-before-claim`, `diagnosing-bugs`).** Scartata: appesantisce il catalogo e duplica la review nativa dell'host e il trigger di `test-driven-development` sui bug fix.
- **Mantenere i 4 livelli con `task-implement` e la review separata per ogni micro-task.** Scartata: produceva fino a 5–6 passaggi di review sullo stesso codice e cold-start continui sullo stesso modulo.
- **Far implementare il codice direttamente al controller `plan-implement` senza subagenti.** Scartata: mantiene il contesto del controller pulito sul piano e sui requisiti delegando l'esecuzione ai subagenti di slice e di review.

## Misura

Riduzione dei giri di review e dei cold-start per piano rispetto ai run pre-1.5; tasso di difetti sfuggiti dalle slice `standard` fino alla PR; osservazione sui primi run reali dell'adeguatezza del contratto di consegna leggero delle slice.
