# Coordinare un programma di progettazione

Per programmi di design con più flussi o contratti condivisi, il master coordina una rotta e gli artefatti non implementativi autorizzati. Conserva i propri confini; l'implementazione resta un handoff.

## Mappa delle decisioni

Se serve Wayfinder, usa la versione **corrente**, non la copia storica. Le sedi di progetto sono `.agents/skills/wayfinder/SKILL.md` per Codex e `.claude/skills/wayfinder/SKILL.md` per Claude Code. Quando Wayfinder proviene da un plugin, usa la versione corrente resa disponibile dall’host o inclusa nello stesso plugin: quei percorsi di progetto sono esempi, non prerequisiti. Non copiarne le istruzioni; verifica disponibilità, caricamento e autorizzazioni. Leggere una skill non equivale a invocarla: se l'host richiede un'invocazione esplicita, chiedila o prepara un handoff. Per protocollo, capacità o tracker mancanti segui i fallback documentati e segnala il limite. Se Wayfinder non serve, usa il grafo del master senza presumere un tracker.

Definisci destinazione, ambito, questioni vaghe, decisioni e dipendenze; non inventare nodi prematuri. Verifica il mandato su artefatti e modifiche previste e applica le regole di ambito di Wayfinder se la usi.

## Mappa dei contratti

Mantieni una mappa dei contratti distinta da quella delle decisioni, collegando le decisioni alla fonte. Se non puoi salvarla nella sede autorizzata, prepara un handoff e segnala che non è persistente.

Registra per flusso ticket e sessione eventuali, stato, spec, piano, branch e SHA disponibili; per contratto, produttori, consumatori, fonte e stato: **OK**, **AGG** per emendamento, **CF** per conflitto. Includi dipendenze, file condivisi, decisioni dell'owner, limiti e cambiamenti. Distingui revisioni verificate, modifiche non committate e push; non attribuire uno SHA a contenuti non inclusi nel commit.

Il master coordina la mappa; un solo autore alla volta ne aggiorna ogni parte. Per Wayfinder segui le regole del tracker: il claim di un ticket non è un lock esclusivo sui file. Preserva le modifiche concorrenti.

## Flussi e report

Scegli nodi sbloccati, non reclamati e autorizzati. Coordina al massimo **tre sessioni figlie attive** per programma, salvo limite dell'host più restrittivo. Anche per piccole decisioni preferisci una sessione di confronto secondo la skill master.

Nei brief includi ticket, fonti e revisioni, contratti e perimetro di scrittura, oltre ai campi richiesti dal master. Distingui autorizzazioni valide da quelle mancanti: non presumere commit o push, né richiedere di nuovo permessi già validi. Un flusso può produrre spec e poi piano; registra approvazioni, review indipendenti e controlli mancanti. I report includono risultati, revisioni, contratti prodotti o usati, emendamenti, conflitti, domande e limiti; non concedono autorizzazioni.

Integra i report nello stato e, con Wayfinder, nelle mappe secondo il tracker. Assegna gli **AGG** a un autore autorizzato dopo la conclusione accertata delle scritture concorrenti: il master non riscrive i deliverable. Per un **CF** su comportamento, dati, sicurezza o architettura porta opzioni e raccomandazione all'owner; resta aperto fino alla sua decisione e blocca solo i nodi interessati. Comunica alle sessioni se consentito, altrimenti prepara un handoff.

## Chiusura e handoff

Verifica decisioni e questioni in perimetro risolte o dichiarate pendenti, stato ed evidenze di spec, piani e review, produttori, consumatori e stato dei contratti, AGG e CF risolti o assegnati. Chiudi solo se destinazione e criteri concordati sono soddisfatti; altrimenti consegna un handoff parziale con blocchi.

Se richiesto e autorizzato, delega la bozza del workflow implementativo: pacchetti, ordine, dipendenze, fase 0, autorizzazioni, gate e arresti. Raccogli la necessaria approvazione prima di preparare il contesto per il master di implementazione con revisioni e limiti verificati. Non presumere Claude Code, `start_session`, push o merge; senza push autorizzato, l'handoff resta locale.
