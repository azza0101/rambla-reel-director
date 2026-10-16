"""Optional per-run AI accounting at the real provider boundary, never global."""
from contextlib import contextmanager
from contextvars import ContextVar
import json
import httpx
from .magic_store import fingerprint
from .magic_services import MagicWaitingInput

_CONTEXT = ContextVar('magic_provider_usage', default=None)


@contextmanager
def provider_scope(store, run_id, phase, check):
    token = _CONTEXT.set((store, run_id, phase, check))
    try:
        yield
    finally:
        _CONTEXT.reset(token)


def check_current():
    context = _CONTEXT.get()
    if context:
        context[3]()


def invoke_http(provider, payload, operation, *, visual=False):
    context = _CONTEXT.get()
    if context is None:
        return operation()
    store, run_id, phase, check = context
    check()
    signature = fingerprint(payload)
    row = store.read(run_id)
    for call in row['calls'].values():
        if call['provider'] == provider and call['input_signature'] == signature and call['status'] == 'completed':
            cached = call['result']
            return httpx.Response(cached['status_code'], content=cached['body'].encode(),
                headers=cached['headers'], request=httpx.Request('POST','https://cached-provider.invalid'))
    text = json.dumps(payload, ensure_ascii=False)
    visual = visual or '"image_url"' in text or '"inline_data"' in text or '"inlineData"' in text or '"type": "image"' in text
    call_id = store.begin_call(run_id, phase, provider, signature, visual=visual)
    try:
        response = operation()
    except httpx.TransportError as exc:
        # The server may have processed a timed-out request. Leave a durable
        # started entry; recovery marks it unknown rather than charging again.
        raise MagicWaitingInput('Risposta AI non confermata: richiesta conservata, nessun nuovo tentativo automatico') from exc
    headers = {k:v for k,v in response.headers.items()
               if k.lower() in {'content-type', 'retry-after'} or k.lower().startswith('x-ratelimit')}
    result = dict(status_code=response.status_code, body=response.text, headers=headers)
    store.finish_call(run_id, call_id, result=result,
                      error=f'HTTP {response.status_code}' if response.status_code >= 400 else None)
    check()
    return response
