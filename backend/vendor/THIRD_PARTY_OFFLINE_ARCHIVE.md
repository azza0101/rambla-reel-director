# Offline Resolve archive dependencies

- `pr2resolve/` is based on [Ersiter/pr2resolve](https://github.com/Ersiter/pr2resolve), commit `61c8c9ec2a76496721718130f250c5b64fccd789`, MIT licensed. Imports were made package-relative. The original license is in that directory.
- `resolve_offline/fusion-title.xml` and the composition framing used by `backend/app/offline_resolve_archive.py` are based on [better-davinci-resolve-mcp](https://github.com/KiwiSingh/better-davinci-resolve-mcp), commit `a0ce8e7873a79700d3a7ecd10ef10910553e5493`, MIT licensed. The original license is in that directory.

The format is undocumented and version-dependent. The RMBL writer fails explicitly for unsupported media instead of claiming a complete export. Resolve 21.1 was used for local restore tests; other versions require validation.
