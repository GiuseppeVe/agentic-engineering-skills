# File di pacchetto

Il master committa questo file nel branch `pkg/*` quando crea il pacchetto e lo
aggiorna nello stesso passo in cui aggiunge un piano alla mappa. Il consumatore
fissa la cartella e il nome del file, che deriva dal branch senza `pkg/`. Un controllo di CI lo legge
sulla PR `pkg/*` → `main` e la blocca finché un piano elencato non è integrato:
la PR del piano deve risultare unita nel branch del pacchetto e il suo merge
commit deve stare nella storia della head. Ricreare il branch da un commit
precedente al merge riapre il piano.

Un piano esce dal pacchetto solo per decisione dell'owner, espressa con
l'etichetta `exclude:<piano>` sulla PR verso `main`: il controllo accetta
l'esclusione solo se l'ultimo evento di etichettatura viene da un account owner.
Non rimuovere un piano dal file per farlo passare.

Un solo blocco `json`:

```json
{
  "package": "K4",
  "branch": "pkg/k4-sources",
  "plans": [
    { "id": "K4-A", "pr": 576 },
    { "id": "K4-B" }
  ]
}
```

`pr` si aggiunge quando la PR del piano si apre; un piano senza `pr` è pendente.
