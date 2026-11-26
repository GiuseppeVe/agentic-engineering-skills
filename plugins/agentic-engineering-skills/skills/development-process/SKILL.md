---
name: development-process
description: Use when working in a repository that follows this workflow and you need its general process rules - mandate and Git boundaries, verification, the PR phase, the closing report, subagent briefs, run conduct, and the plan and package lifecycle.
---

# Processo di sviluppo

Fonte unica delle regole generali di processo. Sono indicazioni: nessun hook le impone. Le altre skill rimandano a questi due documenti e non li riscrivono.

- [Processo](references/PROCESSO.md): mandato e Git, verifiche, fase PR, chiusura.
- [Orchestrazione](references/ORCHESTRAZIONE.md): delega ai sottoagenti, conduzione di un run, ciclo di vita di piani e pacchetti, consegna dei child, limiti di convergenza.

Leggi solo il documento e la sezione che servono al compito. Le istruzioni del repository in cui lavori prevalgono dove sono più specifiche: comandi dei gate, nomi degli stati e cartelle dei documenti stanno nei documenti di quel repository.

Per l'inventario e la pulizia dei worktree di un repository: `node scripts/worktrees.mjs` (sola lettura; `--remove-merged --yes` rimuove solo i worktree uniti e puliti e non cancella branch).
