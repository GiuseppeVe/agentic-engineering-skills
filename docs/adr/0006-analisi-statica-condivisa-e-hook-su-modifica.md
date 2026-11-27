# 0006 — Analisi statica condivisa con Oxlint e feedback rapido su modifica

Stato: accettata (2026-11-27)

## Contesto

I repository di prodotto generati dagli agenti avevano copertura di analisi statica disomogenea: alcuni pacchetti avevano un linter solo sintattico con regole chiave spente, altri nessun linter affatto. Difetti ricorrenti del codice generato (promise non gestite, `catch {}` vuoti, optional chaining insicuro, stringificazioni `[object Object]`, regole React 19 sui render e accessibilità tastiera) arrivavano fino alla review o al merge.

Un audit su oltre 3.500 file JS/TS ha inoltre mostrato che:

- il linter integrato di Bun (`bun lint`) non è ancora presente nella release stabile (1.4.5) ed è confinato alle build canary;
- il type-checker integrato di Bun (`bun check`) diverge sul DOM rispetto a TypeScript 5.8 usato dai repository;
- Oxlint (1.95.x + `oxlint-tsgolint`) gira stabile su Windows e Linux come dipendenza bloccata nel lockfile npm, copre nativamente anche le regole React 19, completa la passata sintattica in 1–3 secondi sull'intero repository e legge il formato `.oxlintrc.json` compatibile anche con futuri rilasci stabili di `bun lint`.

## Decisione

1. **Preset canonici nella factory.** La cartella [`standards/static-analysis/`](../../standards/static-analysis/README.md) conserva i preset condivisi e depurati dal rumore: `base-ts-js.oxlintrc.json`, `react-web.oxlintrc.json` e `ruff.toml` per gli script Python.
2. **Architettura a due velocità.**
   - **Feedback rapido:** controllo sintattico sui soli file modificati (hook `PostToolUse` e `pre-commit`, sotto 200 ms per file).
   - **Verifica profonda:** Oxlint `--type-aware` in `pre-push` e CI insieme a `tsc` (che resta autoritativo per compilazione e tipi) e `knip`.
3. **Hook `PostToolUse` non bloccante su modifica.** Il plugin registra [`edit-lint.mjs`](../../plugins/agentic-engineering-skills/hooks/edit-lint.mjs) su `Edit|Write|MultiEdit|apply_patch`. Se il repository ha un `.oxlintrc.json` e `oxlint` locale installato, l'hook controlla in sola lettura i soli file JS/TS modificati; resta silenzioso quando non ci sono errori o quando il repository non configura Oxlint; non modifica mai file e termina sempre con codice 0. L'enforcement resta nei gate Git e CI del repository (ADR 0001).
4. **Adozione a ratchet nei repository esistenti.** I gate bloccano subito qualunque errore nei file toccati dal diff rispetto alla base, senza paralizzare le PR sul debito storico fuori diff e senza spegnere regole valide.

## Alternative scartate

- **`bun lint` come gate CI della factory.** Scartata oggi: non è ancora nella release stabile e introdurrebbe un secondo binario globale da tenere allineato fra macchine locali, server di gate e CI. Il formato `.oxlintrc.json` lascia comunque aperta la migrazione a costo quasi zero quando sarà stabile.
- **ESLint type-aware su tutti i repository.** Scartata: troppo lento nel ciclo iterativo degli agenti e più pesante da mantenere per pacchetto.
- **Biome.** Scartata: copertura type-aware cross-file inferiore su TypeScript e nessuna lettura nativa di `.oxlintrc.json` o dei plugin ESLint/React Compiler.
- **Auto-fix silenzioso nell'hook (`--fix`).** Scartata: mutare un file dietro le spalle dell'agente dopo una modifica introduce drift di contesto.

## Misura

Riduzione degli errori di analisi statica che raggiungono `pre-push`, CI o review indipendente, a parità di tempo di turno (< 200 ms per modifica in caso verde) e con zero blocchi introdotti su file non modificati.
