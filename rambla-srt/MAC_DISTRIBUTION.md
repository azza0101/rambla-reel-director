# Distribuzione Mac

La candidata include un installer di sistema shell senza runtime esterni. Il collaudo fisico Mac e la firma/notarizzazione non sono stati eseguiti su questo host Windows.

Per una distribuzione pubblica con doppio clic:
1. Su un Mac con Xcode Command Line Tools e Resolve Studio 21, eseguire la suite e collaudare caricamento SDK, export e update dal menu.
2. Impostare `SRT_INSTALLER_IDENTITY` al certificato **Developer ID Installer** e `SRT_NOTARY_PROFILE` al profilo `notarytool` già configurato in Keychain, quindi eseguire `bash tools/build-mac-pkg.sh`. Il builder genera payload e `.pkg`; usa lo stesso installer verificato e l'SDK locale della macchina destinataria.
3. Il builder firma con `productsign`, notarizza con `xcrun notarytool submit --wait`, applica il ticket con `stapler` e verifica firma e `spctl`. Ogni errore interrompe il processo; il builder rifiuta l'avvio senza identità e profilo. Non includere credenziali nel repository.
4. Verificare il pacchetto su Mac pulito Apple Silicon e Intel supportati. Non disabilitare Gatekeeper/quarantena, non pubblicare come firmato un artefatto senza ticket.

Le credenziali Apple e un Mac reale non sono disponibili in questa sessione: questo documento non sostituisce quei controlli. Il pacchetto shell non viene presentato come notarizzato.
