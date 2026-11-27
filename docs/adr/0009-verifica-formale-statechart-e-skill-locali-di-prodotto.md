# 0009 — Verifica formale con `statechart` ed eccezione per skill locali di verifica formale nei repository di prodotto

Stato: accettata (2026-11-27)

## Contesto

I layer deterministici descritti in ADR 0008 (L1 tipi/schemi, L2 analisi statica, L3 test comportamentali e di contratto) coprono bene regressioni meccaniche e casi previsti, ma arrivano con difficoltà a race condition, ordini rari di eventi e macchine a stati complesse dove un bug ha costo alto. Per quei casi, il model checking (es. TLA+ con TLC) accompagnato da uno statechart leggibile nel linguaggio di chi decide riduce la superficie di review e permette di verificare il comportamento rispetto all'intento.

Le skill `create-formal-verification-skill` e `maintain-formal-verification-skill` (importate da `cursor/plugins/pstack`, licenza MIT) generano e mantengono una skill locale legata a file, invarianti, comandi e commit di sincronizzazione specifici del repository di prodotto. Gli ADR 0001, 0002 e 0007 vietano invece copie di skill di processo nei repository di prodotto per evitare duplicazione e drift del metodo.

## Decisione

1. **Aggiunta di tre skill esplicite di verifica formale nel plugin.**
   - Il plugin `agentic-engineering-skills` distribuisce `statechart`, `create-formal-verification-skill` e `maintain-formal-verification-skill` (adattate con invocazione esplicita su Codex e Claude Code, senza il corpus di test interno di `statechart`).
   - Le tre skill restano on-demand (`disable-model-invocation: true` e `allow_implicit_invocation: false`), pensate per flussi stateful, protocolli e invarianti ad alto rischio (`risk: high`), non come passaggio obbligatorio su ogni PR di routine.
2. **Eccezione circoscritta ad ADR 0001, ADR 0002 e ADR 0007.**
   - Le skill di **processo, orchestrazione e workflow generale** restano unicamente nel plugin utente `agentic-engineering-skills` (ADR 0002).
   - Come **eccezione esplicita**, una skill locale di **verifica formale specifica del codice di un prodotto** (generata e mantenuta tramite `create-formal-verification-skill` e `maintain-formal-verification-skill`, contenente solo target, proprietà, comandi di verifica, record di copertura e commit di sincronizzazione di quel repository) può risiedere dentro il repository di prodotto nei percorsi standard degli host (`.agents/skills/` / `.claude/skills/`).
   - Resta vietato inserire in un repository di prodotto skill di verifica generiche con feature map parallele (`create-verification-skill` / `maintain-verification-skill`) o copie di skill di processo.
3. **Disciplina leggera per verifiche live in `development-process`.**
   - Senza aggiungere skill dedicate alle verifiche live, `development-process/references/daily-workflow.md` integra tre regole sintetiche: health-check dell'istanza prima di guidare prove live o dopo un errore, teardown limitato ai soli processi avviati dal run preservando gli artefatti di prova, e verifica empirica di cosa salti davvero una modalità dry-run.

## Alternative scartate

- **Salvare le verifiche formali solo come runbook Markdown senza skill locale nel prodotto.** Scartata dall'owner: la skill locale dedicata a un invariante critico rende la riesecuzione e il controllo di drift immediatamente scopribili dagli agenti quando toccano i file coperti.
- **Importare anche `create-verification-skill` e `maintain-verification-skill`.** Scartata: duplicano la documentazione operativa e le suite E2E/contract già presenti nei repository di prodotto e introducono una feature map parallela soggetta a drift continuo, in contrasto con la verifica leggera di ADR 0008.
- **Includere nel payload distribuito del plugin i 377 file del corpus di test interno di `statechart`.** Scartata: quasi raddoppierebbe il numero di file copiati nelle cache utente degli host senza aggiungere alcuna capacità operativa agli agenti (il corpus è escluso con `excludePaths: ["scripts/test/"]` in `manifests/skill-sources.json`, quindi non entra né nel payload né in `manifests/patches/statechart.patch`; l'hash upstream nel lock copre comunque l'intera cartella pinnata).

## Misura

Numero di bug di stato o race condition individuati tramite `statechart` / verifica formale prima del merge su flussi ad alto rischio; zero copie di skill di processo nei repository di prodotto (eccezione limitata esclusivamente alle skill locali di verifica formale con `sync commit`).
