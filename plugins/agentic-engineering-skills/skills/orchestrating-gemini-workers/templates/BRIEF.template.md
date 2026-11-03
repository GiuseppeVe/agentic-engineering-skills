# Brief <ID> — <titolo breve del task>

Leggi prima `AGENTS.md` in questa cartella: regole permanenti, valgono sempre.

## FILE CHE SCRIVI

- `<path/al/file1.ts>`
- `<path/al/file2.ts>` (se applicabile)

Nessun altro file. Uno scritto fuori da questa lista fa buttare l'intero task.
<Se lo script produce output non tracciato (SVG/JSON di debug ecc.), dichiaralo
qui esplicitamente come "non conta come file scritto".>

## Cosa fare

<Descrizione autosufficiente del task. Il worker non ha visto la
conversazione: ogni numero, formato o nome che gli serve va scritto qui,
non solo referenziato.>

## Divieti espliciti

- Niente build/packaging.
- Niente modifiche a file di configurazione.
- <altri divieti specifici del task>

## Criteri di accettazione

<Elenco NUMERICO, ricavato da te indipendentemente da questo brief. Es.:
"la funzione X deve restituire 42 per l'input Y", "il file deve contenere
esattamente N record". Se un criterio fallisce, il task NON è finito: il
worker deve correggere, non solo segnalare.>

## Report finale

Chiudi con il blocco `=== REPORT ===` richiesto da `AGENTS.md`.
