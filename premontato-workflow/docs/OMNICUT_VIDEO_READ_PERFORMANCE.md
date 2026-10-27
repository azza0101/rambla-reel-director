# Omni-Cut test 0.2.8 — Lettura video accelerata

## Scelta misurata

Richiesta del 27 ottobre 2026: provare un frame ogni due secondi, verificare GPU e metodi più rapidi. Spike eseguito con runtime installato 0.2.7, OpenCV 4.11 e RTX 4090, mentre il PC era in uso: tempi indicativi, non un benchmark di laboratorio. Nessuna modifica al plugin in esecuzione o al progetto Resolve.

Su un minuto dello stesso originale 4K H.264 25 fps:

| Metodo | Tempo |
|---|---:|
| Lettura CPU, circa 2 frame/s (attuale) | 14,77 s |
| Lettura CPU, 0,5 frame/s | 9,96 s |
| FFmpeg/NVDEC, 2 frame/s | 10,86 s |
| FFmpeg/NVDEC, 0,5 frame/s | 9,72 s |
| OpenCV/D3D11, 2 frame/s | 8,62 s |
| OpenCV/D3D11, 0,5 frame/s | 8,45 s |

In tre estratti iniziali (12 s, 12 s, 4,8 s), la decodifica assorbe circa 80–90% del tempo. Il campionamento a 0,5 frame/s perde tutti i volti in una clip di 4,8 s dove quello a 2 frame/s rileva una larga. Non viene quindi imposto come default: D3D11 mantenendo i campioni riduce il tempo osservato del 42% (1,7x), mentre ridurre anche i campioni aggiunge solo ~2% nel confronto hardware di un minuto. Non è una garanzia su ogni codec/PC né sul tempo totale del montaggio.

## Implementazione

Il solo analyze_video di YuNet tenta VideoCapture con CAP_FFMPEG e VIDEO_ACCELERATION_ANY su Windows. Legge il backend effettivo: D3D11, Hardware o CPU. Se l’apertura fallisce o la firma non è supportata, rilascia il tentativo e riapre sulla CPU; ANY può scegliere autonomamente CPU, che viene riportata come tale. Altri sistemi restano sul percorso CPU precedente. Nessuna nuova dipendenza, modello, chiamata esterna o modifica ai driver.

YuNet continua a inferire su CPU a larghezza 640 e circa 2 frame/s. Mantiene soglie, istogrammi, indici sorgente e classificazione precedenti. Il risultato riporta decode_backend e la revisione distingue la lettura GPU dalla CPU. La versione dell’analizzatore e la chiave di cache restano compatibili: i risultati esistenti validi non vengono invalidati per obbligare un nuovo passaggio. Le nuove clip beneficiano del nuovo lettore.

## Verifiche

213 test JavaScript e 209 Python superati, nessuno saltato. Nuovi test per richiesta hardware, rilascio del decoder rifiutato, firma non supportata, comportamento Linux e fallback automatico non spacciato per GPU. Test nativo del codice reale su clip sintetica H.264: D3D11 attivo, indici 0/12/24/36/48/60/72 identici alla CPU, differenza media pixel massima 3,14 livelli su 255. Test reale sulla clip breve: larga rilevata e intervallo 0–120 frame valido. Zero scritture Resolve. Non è un test di accuratezza su tutto il girato o un nuovo montaggio completo.

## Alternative studiate

- [OpenCV wheels](https://github.com/opencv/opencv-python): solo CPU per il DNN; compilare CUDA non è necessario per usare il decoder D3D11 già incluso.
- [OpenCV Zoo benchmark](https://github.com/opencv/opencv_zoo/blob/main/benchmark/README.md): YuNet è già leggero; GPU e quantizzazione non sono automaticamente più rapide per un modello piccolo.
- [MediaPipe/BlazeFace](https://developers.google.com/edge/mediapipe/solutions/vision/face_detector): alternative leggere CPU/GPU, ma sostituire il detector non elimina il costo dominante della decodifica e richiede una nuova verifica sui volti piccoli/laterali. Nessun modello nuovo installato.
- [ONNX Runtime DirectML](https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html): fattibile per inferenza GPU Windows con un pacchetto diverso, ma senza vantaggio end-to-end dimostrato per questa fase. Non aggiunto.

Per accelerazioni ulteriori ha senso profilare proxy/cache condivise e limitarne la lettura agli intervalli pertinenti. Il solo cambio del modello non promette ordini di grandezza di miglioramento.
