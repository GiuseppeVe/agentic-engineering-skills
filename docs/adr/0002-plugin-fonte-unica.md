# 0002 — Regole, skill e hook generali hanno una sola fonte: il plugin

Stato: accettata (2026-11-26)

## Contesto

Regole di processo, guida all'orchestrazione e skill esistevano in più copie: una per repository di prodotto, a volte due per client (Claude Code e Codex), più hook registrati a mano nel profilo utente. Le copie divergevano e una correzione fatta in un repository non arrivava agli altri.

## Decisione

Il plugin `agentic-engineering-skills` è l'unica fonte di regole di processo, skill e hook generali. Si installa a livello utente in Claude Code e Codex, quindi vale in ogni repository senza copie locali. Una regola generale si cambia con una PR su questo repository.

Ciò che vale per un solo repository (comandi dei suoi gate, nomi dei suoi stati, cartelle dei suoi documenti) sta nei documenti di quel repository, non nel plugin. Le skill generali parlano del «consumatore» e non nominano un prodotto.

## Alternative scartate

- **Una cartella condivisa di regole fuori dai repository, letta tramite `AGENTS.md`.** Scartata: vale solo sulla macchina che ha quella cartella e non copre skill e hook.
- **Copie sincronizzate da uno script.** Scartata: aggiunge un meccanismo da mantenere e lascia comunque modificabili le copie.
- **Note specifiche di un repository in fondo ai documenti generali.** Provata e tolta: rende il plugin dipendente dai prodotti e pubblica dettagli che appartengono a loro.

## Misura

Numero di copie di una stessa regola o skill fuori dal plugin: l'obiettivo è zero. Alla data della decisione restano copie di skill in due repository di prodotto, da togliere.
