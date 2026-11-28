# 0010 — Il comportamento con stato è modellato e approvato prima del piano

Stato: accettata (2026-11-28)

## Contesto

Quando l'esito dipende dallo stato o dall'ordine degli eventi, la spec in prosa lascia al piano e al codice scelte che chi decide non ha visto. L'ADR 0009 teneva `statechart` su richiesta, per flussi ad alto rischio e mai come passaggio del processo: il diagramma arrivava, quando arrivava, a codice scritto.

## Decisione

Per ogni modifica con transizioni che cambiano l'esito per l'utente, il design produce un modello persistente accanto alla spec e un diagramma con `statechart`; l'owner approva il comportamento prima del piano; il piano e la code review verificano il codice reale contro il modello. La procedura ha una sola fonte: `behavior-model.md` in `development-process`. Le modifiche senza transizioni significative vanno direttamente al piano.

Sostituisce il punto 1 dell'ADR 0009 solo per questo uso di `statechart`. L'invocazione automatica della skill resta spenta: la procedura chiede all'agente di leggerla e seguirla. Le skill locali di verifica formale (ADR 0009, punto 2) non cambiano; la loro valutazione in un prodotto resta un esperimento separato.

## Alternative scartate

- **Riaccendere l'invocazione automatica di `statechart`.** Scartata: la farebbe partire anche fuori dal design e cambierebbe l'adattamento della skill importata.
- **Un guard che blocca il piano senza approvazione.** Scartata: capire se un comportamento ha transizioni significative richiede giudizio, e un meccanismo di processo nuovo richiede prima una misura.

## Misura

Difetti di stato o di ordine degli eventi trovati dopo il merge nelle modifiche modellate, e cambi di comportamento emersi dopo l'approvazione.
