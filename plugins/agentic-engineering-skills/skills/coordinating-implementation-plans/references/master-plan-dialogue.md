# Dialogo master–piano

Leggi questo riferimento al lancio e a ogni ripresa, prima di creare o
riprendere un thread-piano. Descrive il lato master di un unico protocollo: la
definizione condivisa di mandato, domanda, decisione, aggiornamento e report è
in [programme-messages.md](../../plan-orchestrator/references/programme-messages.md);
il thread-piano applica la propria parte da
[reporting-to-master.md](../../plan-orchestrator/references/reporting-to-master.md).
I due riferimenti non duplicano il protocollo: fissano il comportamento del
ruolo e rimandano alla stessa definizione. Il trasporto è dell’host; evidenze,
gate e formato di merge restano del progetto consumatore.

## Ingresso, recapito e mandato

Al lancio prendi dal brief, e a ogni ripresa riconcilia con il ledger e lo stato
reale:

- il recapito raggiungibile del master, il mandato del piano, la base o
  revisione, il risultato atteso e il manifesto verificabile;
- le decisioni riservate già concesse e i punti di stop;
- il percorso di integrazione autorizzato e gli obblighi pendenti.

Registra nella mappa e nello stato canonico del master (§3 della skill), per
ogni piano, recapito, revisione, ambito delle decisioni, risorse e stato. Il
ledger del run appartiene al thread-piano: leggilo per riconciliare, non
riscriverlo. Non inventare un recapito mancante e non trattare un brief vecchio
come un nuovo mandato.

Il thread-piano riceve recapito e mandato e li passa ai propri thread di task.
Le domande seguono questa direzione:

| Chi domanda | A chi | Contenuto |
| --- | --- | --- |
| Thread di task | Thread-piano | Domanda sul proprio mandato |
| Thread-piano | Master | Solo il dubbio residuo di flusso o la scelta riservata, con mandato, azione sospesa, scelta proposta e conseguenza |
| Master | Owner | Solo la scelta riservata, con scelta precisa, effetto osservabile e passo dipendente |
| Master | Piani coinvolti | Decisione correlata alla domanda, con ambito e revisione; solo i piani coinvolti |

Una domanda già coperta dal mandato, dalle fonti approvate o da una decisione in
vigore non sale: il thread che la riceve la risolve localmente e registra la
base. Il master non inoltra al piano una risposta che il piano poteva darsi, e
non sostituisce una prova mancante con una decisione.

## Dal brief alla risposta consegnata

1. Il brief identifica recapito, mandato e decisioni riservate. Il piano crea o
   riprende branch, worktree e thread di task.
2. Un aggiornamento informativo si associa al mandato vigente. L’eventuale
   conferma di ricezione conserva l’identità della consegna tecnica, non crea un
   passo e non concede autorità.
3. Il piano invia al master solo il dubbio residuo di flusso. Il master verifica
   prima se esiste una decisione applicabile nel mandato, nelle fonti o nello
   stato; se esiste, risponde citandola e registra la base.
4. Se il dubbio riguarda ordine di integrazione o risorse condivise, il master
   decide entro il mandato. Se la proposta cambia struttura, contratto,
   comportamento, perimetro o un’autorizzazione riservata e le fonti lasciano
   aperta la scelta, il master prepara la domanda per l’owner: scelta precisa,
   effetto osservabile, passo che resta fermo.
5. La decisione identifica la domanda, l’ambito e la revisione a cui si applica,
   e nomina chi ha deciso. Se cambia la consegna, il master emette un mandato
   distinto che cita quello superato; il vecchio mandato non viene riscritto.
6. Il master comunica la risposta solo ai piani coinvolti e registra nello stato
   decisione, ambito e revisione. Una domanda ripetuta riceve la decisione
   vigente se ambito e revisione combaciano; se sono cambiati, il master
   rivaluta e registra la nuova decisione. Una decisione duplicata produce un
   solo passo.
7. Il piano riprende solo le azioni sbloccate e il passo successivo cita la
   decisione. Un ACK in chat senza passo osservato non dimostra la ripresa.
8. Il report di consegna si verifica contro il mandato: base, risultato atteso e
   manifesto. Un report tardivo resta attribuito al mandato originale; una
   decisione successiva mantiene precedenza solo nel proprio ambito.
9. Se la consegna è incerta, il master verifica la ricezione prima di
   reinviare. Al risveglio riconcilia domande aperte, decisioni da consegnare e
   risultati sopraggiunti tramite notifiche dell’host o uno snapshot compatto.

## Casi discriminanti

- **Sync autorizzato.** Il piano chiede quando sincronizzare una branch: è un
  dubbio di flusso che il master decide entro il mandato. La domanda arriva dal
  piano e la decisione torna al piano; non coinvolge l’owner se il mandato copre
  già la scelta. Se la decisione cambia la base, nasce un mandato distinto che
  cita il precedente.
- **Cambio di garanzia da main a pkg.** Sostituire un gate che richiede
  disponibilità in `main` con la disponibilità nel pacchetto richiede una base
  approvata per l’equivalenza oppure una decisione dell’owner. Il piano manda
  la domanda al master, che non la decide e la porta all’owner completa di
  scelta, effetto e passo dipendente; la risposta torna al piano tramite il
  master. Un contratto di prodotto mancante segue lo stesso percorso,
  mentre un dubbio sul sync resta nel mandato.
- **K2 con PR individuale in bozza.** Se il mandato prevede una PR aggregata, il
  prossimo passo segue il percorso aggregato; la bozza individuale può restare
  tale e non riceve un via libera al merge.
- **Programma preesistente con PR diretta verso main.** Conserva quel percorso
  di integrazione e applica gli stessi criteri di prova.

## Stato del consumatore e readiness

Prima di suggerire un’azione verifica il percorso di integrazione autorizzato.
Leggi la superficie di stato esistente del consumatore e registra head,
perimetro e destinazione; un’azione suggerita dal comando non è
un’autorizzazione. Tieni separati fatti osservati, perimetro richiesto, prove
disponibili, readiness e autorizzazione al merge.

Dichiara readiness solo quando le prove richieste dal repository coprono il
perimetro e la revisione effettivi. Una nuova head invalida le prove legate alla
precedente. Con fonte illeggibile, mandato cambiato o gate saltato, esplicita la
verifica residua; un’eccezione vale soltanto entro l’ambito autorizzato. Un tip
già in `main` non chiude il pacchetto se resta un piano obbligatorio aperto, e
il contenimento della revisione richiesta va verificato prima di dichiararla
inclusa.

| Riga di accettazione della spec | Classificazione del master |
| --- | --- |
| PR fuori bozza con review mancante o gate fallito | Readiness aperta: riporta la prova mancante o il fallimento, nessun via libera |
| Nuovo push dopo review positiva | Rivaluta le prove sulla revisione corrente; quelle della head precedente non valgono |
| K4 confluisce tramite K6 e il tip richiesto di K4 avanza | Verifica il contenimento della nuova revisione prima di dichiararla inclusa |
| K2 ha una PR individuale in bozza e il mandato prevede una PR aggregata | Il prossimo passo segue il percorso aggregato; la bozza individuale può restare |
| Il tip è in main e resta un piano obbligatorio aperto | Il tip risulta integrato e il pacchetto resta aperto |
| Fonte indisponibile, mandato cambiato o gate saltato | Esplicita la prova residua e l’eventuale eccezione nel suo ambito |
| Programma preesistente con PR diretta verso main | Conserva il percorso diretto e applica gli stessi criteri di prova |

La presenza di questa griglia non dimostra l’output del comando di stato: il
confronto con l’output effettivo del consumatore usa la superficie di stato
esistente e resta una verifica separata.

## Risorse, stop e ripresa

Per una risorsa contesa rendi visibili host, titolare, prossimo richiedente e
condizione di rilascio. Al rilascio assegna la risorsa al prossimo piano
compatibile e avvisalo prima che lo slot venga usato; l’avviso non amplia il
mandato.

Una domanda sospende solo l’azione dipendente: il lavoro indipendente già
autorizzato prosegue, e uno stop esplicito dell’owner ferma le azioni incluse
nel suo ambito. Dopo la ricognizione un task leggero autorizzato può avanzare
mentre un altro resta bloccato. Alla ripresa ripartono solo le azioni sbloccate
e ciascuna cita la decisione che la consente.

## Confini

Dipendenza, isolamento del workspace, review, commit e integrazione restano nel
[runtime protocol](../../plan-orchestrator/references/runtime-protocol.md). Il
dialogo non aggira un gate di dipendenza, una revisione o un confine di commit,
e una domanda o una decisione non sostituisce una prova mancante.
