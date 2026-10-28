# Gemma 4 locale — build di prova

Attivazione: Impostazioni → Gemma 4 locale → Attiva e seleziona modello. Scegliere un llama-server.exe compatibile e i pesi ufficiali Gemma 4 12B QAT Q4_0 in formato GGUF. Runtime e pesi restano esterni all'installer; non vengono duplicati a ogni aggiornamento. La configurazione resta nella cartella dati del prodotto.

Il motore parte su localhost con credenziale casuale di sessione; non invia i dati a Groq o OpenRouter e si arresta con il pannello. Se manca memoria o l'avvio fallisce, l'errore non autorizza un passaggio online. La scelta dei fornitori online resta esplicita nelle impostazioni.

La classificazione usa i contratti esistenti del montaggio. Modello e cache sono distinti dai servizi online. Il ragionamento interno è disattivato e l'output è vincolato a JSON. Gli eventi editoriali vengono verificati singolarmente: quelli privi di ancore verbatim o ruoli validi sono esclusi e conteggiati nella sintesi; la regia deterministica esistente continua a funzionare.

Limiti: non è provata una qualità superiore al servizio online. Il test su tutte le trascrizioni riguarda l'assegnazione alle scene, non un montaggio completo. La catalogazione corrente conserva il proprio motore: questo aggiornamento collega Gemma al percorso dialoghi e regia del montaggio. La guardia sui nomi usa i personaggi forniti dal copione: non riconosce automaticamente tutti gli alias narrativi. Il risultato multi-scena sperimentale non introduce timecode o tagli inventati e non è ancora integrato nel contratto delle battute.

Verifiche del 28 ottobre 2026: 244 test JavaScript e 223 Python; prova reale del client con 12/12 abbinamenti nel campione già noto, cache riutilizzata in circa 2 ms, avvio automatico e un evento editoriale validato. Nessun nuovo collaudo nativo della timeline Resolve effettuato per questa build. Queste misure non costituiscono una valutazione indipendente dell'intero montaggio.
