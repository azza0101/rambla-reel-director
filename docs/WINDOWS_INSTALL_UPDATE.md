# Installazione RMBL B ROLL v0120

Trasferisci RMBL-B-ROLL-Setup-v0120.exe sul PC Windows 10/11 x64 ed eseguilo. Installa app standalone e launcher bridge; i collegamenti sono sul Desktop. Per il solo programma usa RMBL B ROLL; Resolve non serve. Per il bridge serve Resolve installato separatamente, scripting su Local. Nessun MCP necessario.

Il setup include dipendenze Python offline, FFmpeg e GitHub CLI. Se Python 3.12 non e presente usa winget e internet per installarlo. Se winget non e disponibile installa Python 3.12 x64 da python.org e riapri il setup. Il setup comprende il template KURA gia fornito dal progetto e lo installa senza chiamare Resolve. Non comprende Resolve, account o media. La variante PERSONALE locale include le API esistenti; la variante standard GitHub non contiene segreti. I login social devono essere eseguiti nel browser del nuovo PC. Il gateway FreeLLMAPI sperimentale non e distribuito: il client Gemini nativo resta disponibile.

SEARCH UPDATE in alto nell'app e nel bridge controlla la release GitHub. Repository privato: il setup PERSONALE v0120 puo includere il token tecnico dedicato gia configurato, quindi non richiede login GitHub. Il pacchetto standard usa il login GitHub autorizzato. Non usare token condivisi o chiavi API incorporate. Conferma l'aggiornamento solo quando non ci sono render, ricerche o importazioni in corso. Si riavvia RMBL, non Resolve. Il bridge si aggiorna automaticamente quando libero. La copia di sviluppo rifiuta l'auto-aggiornamento.

Dati: %LOCALAPPDATA%\RMBL B ROLL\rambla-data
Programma: %LOCALAPPDATA%\RMBL B ROLL\app
Credenziali del programma: app\.env.local, conservate dagli aggiornamenti.
Backup codice: %LOCALAPPDATA%\RMBL B ROLL\install-backups\DATA-VERSIONE\code
Rollback: avvia ROLLBACK_RMBL.ps1 nella cartella backup. Nessun progetto viene eliminato.

Alternativa ZIP: estrai e avvia INSTALL_RMBL_B_ROLL.cmd. Non copiare la cartella di sviluppo o la sua .env.local a persone esterne.

ASSISTENZA in alto su app e bridge permette di vedere, copiare o inviare diagnostica sanitizzata. Invio automatico inizialmente disattivato, attivabile al primo avvio. Le segnalazioni non avviano una sessione Codex: si analizzano durante l’assistenza e le correzioni arrivano con SEARCH UPDATE.
