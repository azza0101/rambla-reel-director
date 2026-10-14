# Export selettivo e CUT nativo in Resolve

## Richiesta e risultato atteso
La sezione 7 deve avere un unico pulsante di invio e una tendina con Video/montaggio CUT, Subs, Frasi evidenziate, B-roll, Social clips e Coperture generiche. È possibile inviare solo il CUT senza piano editoriale o ricerche media. Il video CUT viene creato in Resolve utilizzando il video lungo originale, con clip separate e tagli nativi, audio originale sincronizzato e tutte le maniglie disponibili nella sorgente. Non viene importato come singolo MP4 già montato.
Il download MP4 del CUT è una funzione separata sotto il player dell'anteprima CUT.

## Stato attuale verificato
- CUT salva una mappa a frame `source_in_frame/source_out_frame` esclusiva e `edited_in_frame/edited_out_frame`.
- I progetti confermati conservano `cut-origin.json`, il piano congelato e il percorso della sorgente originale.
- Il pacchetto Resolve è persistente, associato alla sessione del bridge, e applicato solo dopo APPLICA.
- Il middleware blocca tutti gli export dei progetti CUT. Il bridge e il creatore della timeline non ricevono ancora la mappa CUT.
- Il pulsante esistente prepara tutte le componenti senza una selezione esplicita.

## Flusso utente
1. In 7: tendina COSA ESPORTARE, selezioni salvate per progetto.
2. Video/montaggio CUT selezionabile se esiste un originale video disponibile e un piano CUT valido. Nei progetti importati dal bridge che contengono solo la guida audio questa voce è disattivata con motivazione; non si duplica il montaggio esistente.
3. Sui progetti video CUT il default include il montaggio nativo. Subs/frasi/media vengono inclusi solo se selezionati e disponibili. Le voci senza contenuti mostrano conteggio zero e non impongono le altre fasi del workflow.
4. Un unico INVIA A RESOLVE prepara una fotografia delle componenti scelte e della revisione CUT, con progresso e conferma di ricezione del bridge.
5. Il bridge mostra il riepilogo e segnala che Video CUT crea una nuova timeline. APPLICA resta l'unico comando che modifica Resolve.
6. Sotto l'anteprima CUT: SCARICA MP4 CUT, con generazione osservabile se il render completo della revisione non è già disponibile.

## Timeline nativa
- La sorgente importata nel Media Pool è il file lungo originale, verificato per identità e disponibilità. Non `clean.mp4` e non `preview-*.mp4`.
- Nuova timeline con nome numerato, senza modificare la timeline preesistente o le impostazioni globali del progetto.
- FPS reali della sorgente, incluso il caso frazionario; non assumere 30 FPS.
- Formato Full HD con orientamento della sorgente: 1920×1080 landscape, 1080×1920 portrait, 1080×1080 square. Per altri rapporti si conserva l'aspect ratio con lato corto 1080 e dimensioni pari. Considerare la rotazione della sorgente.
- Per ogni segmento CUT, inserire video e audio da `[source_in_frame, source_out_frame)` in posizione `timeline_start_frame + edited_in_frame`. Convertire esplicitamente l'OUT esclusivo del piano nell'OUT previsto dall'API Resolve.
- Audio e video usano gli stessi intervalli e lo stesso posizionamento. La durata di ogni segmento deve essere uguale in sorgente e destinazione; nessun retime implicito.
- I tagli del preset pause sono parte della stessa mappa. Le clip rimangono estendibili sul file lungo.
- Gli import successivi sulla stessa timeline CUT possono aggiungere componenti solo dopo verifica dell'identità/revisione della base; non usare la timeline focused arbitraria se non corrisponde al CUT.
- Le eventuali take alternative conservate nel piano rimangono su una traccia superiore disabilitata, ancorate ai tempi montati; non aggiungere audio alternativo attivo al parlato finale.

## Componenti opzionali
- Subs: soli sottotitoli scelti, ai tempi del testo pulito.
- Frasi: clip titolo separate, sopra tutti i video, colore giallo.
- B-roll: coperture locali selezionate, sopra il video base, colore viola.
- Social clips: clip selezionate dei provider social, distinte nell'export da stock e immagini.
- Coperture generiche: sole clip selezionate, in coda al CUT con il distacco previsto, colore beige.
- Nessun download/import per componenti non selezionate. La separazione avviene prima di scaricare i media, non solo dopo la preparazione.
- Un export con tutte le voci deselezionate non parte e mostra una spiegazione.

## Contratto e sicurezza operativa
Estendere il pacchetto con componenti esplicite e `native_cut`: revisione, sorgente originale verificata, metadati formato/FPS, segmenti e alternative. Quando il progetto è derivato, usare il piano congelato di `cut-origin.json`, non una revisione successiva del progetto padre.
Mantenere il blocco CUT per combinazioni non supportate; sostituirlo con un preflight specifico, non rimuoverlo globalmente. Video-only deve funzionare senza template titoli o sottotitoli. La nuova timeline viene considerata completata solo dopo verifica dei frame, durata, conteggi e file sorgente. Un errore identifica l'operazione e la timeline parziale; il retry non aggiunge due volte le stesse clip.
Il bridge deve ricevere la versione aggiornata insieme al backend, mostrando una diagnosi chiara se non supporta il pacchetto.

## Verifica richiesta
1. Test selezioni: video-only, subs-only, frasi-only, media selettivi e tutto; i componenti esclusi non causano download o dipendenze inutili.
2. Test frame: OUT esclusivo/inclusivo, zero, ultima parola, FPS 24/25/30 e 30000/1001, audio/video con durata identica.
3. Test sincronizzazione: tutte le componenti riferite alla stessa revisione del CUT, nessuna doppia applicazione della mappa.
4. Test Resolve: nuova timeline su originale lungo, confronto conteggi/IN/OUT/recordFrame contro la mappa; portrait e landscape 1080p, FPS invariati, altre timeline e marker non toccati.
5. Test MP4: download del render completo della revisione, non del proxy dell'anteprima; revisioni obsolete non distribuite.

## Confine della prima implementazione
Il CUT nativo riguarda il video lungo caricato nel plugin. Il taglio distruttivo di una timeline Resolve preesistente con più file/tracce non è implicitamente autorizzato da questo export: il bridge continua a usare la base esistente per i normali overlay. Un futuro CUT su guida proveniente da montaggio multitraccia richiede la mappa dei media originali e un proprio preflight.
