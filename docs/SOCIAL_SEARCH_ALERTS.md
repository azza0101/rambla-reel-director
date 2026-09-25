# Social search intervention alerts

Discovery emits provider_attention immediately after a request reports CAPTCHA, login requirement or request failure. The active provider shelf shows an alert with a focus-window action and manual recovery instructions. The alert survives terminal status and interrupted variation runs do not consume a round. Partial results remain saved; CAPTCHA/login interrupted runs are classified incomplete instead of successful empty searches.

After manual resolution the user must start the search again; automatic continuation from the exact interrupted query is not implemented.

Validation: 588 tests passed; rendered JS syntax and backend compilation checked. Real CAPTCHA not triggered.
