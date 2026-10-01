# RAMBLA online transcript review bridge

This free Google Apps Script web app stores only a timed transcript and its three
selection lists in a private Google Drive folder. Source video, audio, local
project files and API keys never enter the review payload.

## One-time setup (recommended)

Run the guided PowerShell from any PowerShell window:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "Z:\APP REEL TEST\qwen-embedding-smoke\api-first-v5-cloud\SETUP_REVISIONE_ONLINE.ps1"
```

It generates and saves the secret, copies the Apps Script source, opens Google,
validates the deployed URL, updates `.env.local`, restarts RAMBLA and checks the
new review controls. Google still requires the account owner to authorize and
deploy the Web App in the browser.

## Manual setup

1. Open <https://script.google.com/home/projects/create> with the Google account
   that should own the review files.
2. Replace the editor contents with `Code.gs` from this folder and save.
3. In **Project Settings → Script properties**, create
   `RAMBLA_OWNER_SECRET` with a long random value.
4. Choose **Deploy → New deployment → Web app**. Run it as yourself and allow
   access to anyone who must receive a review link. Copy the `/exec` URL.
5. Add these two lines to the repository-local `.env.local` file:

   ```text
   RAMBLA_REVIEW_WEBAPP_URL=https://script.google.com/macros/s/.../exec
   RAMBLA_REVIEW_OWNER_SECRET=the-same-random-value
   ```

6. Restart RAMBLA once. **CREA LINK REVISIONE** will become available.

The reviewer uses the generated capability link and presses **INVIA MODIFICHE**.
In RAMBLA press **AGGIORNA DAL REVISORE**. A transcript-signature check prevents
an obsolete review from overwriting selections after the transcript changes.

Google documents the web-app deployment flow at
<https://developers.google.com/apps-script/guides/web>.
