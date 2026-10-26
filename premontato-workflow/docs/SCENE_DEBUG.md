# Debug dei confini di scena — 0.12.1 trial

Accanto a **Crea timeline**, l'opzione **Debug scene** è attiva inizialmente.
Nelle nuove timeline di premontaggio:

- fra scene differenti del copione viene inserito un gap vuoto di 2 secondi;
- V4, chiamata DEBUG scene, contiene SCENA 01, SCENA 02 ecc. per l'intera durata di ciascuna scena;
- la numerazione segue la posizione della scena nel copione analizzato;
- parlato e audio mono restano su V2/A2 e le coperture video su V3;
- gap e titoli sono disattivabili insieme prima della creazione; non modificano l'analisi, il piano narrativo o le timeline esistenti.

I confini derivano dagli ID delle battute, senza altre chiamate LLM. Se un taglio non è riconducibile al copione, la modalità debug richiede di ricalcolare il piano oppure disattivare il debug. Non inventa una scena.

La preferenza viene salvata nella bozza del progetto Premontato. I titoli sono piccoli video QuickTime RLE con alpha, generati da FFmpeg già incluso nel runtime. Le PNG inserite come still da Resolve 21.1 restano di durata fissa: per questo non vengono usate direttamente. I video sono persistenti nella cartella assets/scene-debug dei dati Premontato e riutilizzati per numero, durata, fps e formato. Non cancellarli mentre sono referenziati da timeline. Non sono titoli Fusion editabili.

Catalogazione giornata mantiene le SELECTS separate per scena: questa opzione riguarda il premontaggio di una o più scene, non crea un montaggio dell'intera giornata.

## Verifica

Test-first dei confini, sincronizzazione audio/reazioni, merge escluso fra scene e rifiuto/rimozione della sola nuova timeline se il titolo non è verificabile. Test del generatore con durata esatta, alpha trasparente e cache.

Collaudo API reale su Resolve 21.1.0.17 nel progetto aperto test-mcp, autorizzato dall'utente: sorgenti sintetiche, due scene, gap di 50 frame a 25 fps, titoli 130 e 80 frame su V4 e reazione di 40 frame su V3. Lettura nativa di posizioni/durate/tracce e verifica che impostazioni e contenuto di tutte le timeline preesistenti restino invariati. Nessun uso del mouse.

La prima prova PNG ha confermato il limite dei 125 frame. Il primo test alpha ha rilevato il nome colore Cyan non supportato per clip; corretto in Teal e verificato con readback. Entrambi i problemi sono coperti nella soluzione finale.

Build di prova, nessuna pubblicazione stabile e nessuna installazione automatica sulla copia di produzione.

Suite finali: 158 test JavaScript e 186 test Python superati. Test nativo iniziale: 2,623 secondi inclusi inserimento e readback, con asset già generati; non è un benchmark di trascrizione o montaggio.
