"""Opt-in local FreeLLMAPI vision transport; no agent runtime or account rotation."""
import json
from types import SimpleNamespace
from urllib.parse import urlsplit
import httpx
from .gemini_interactions import GeminiAPIError
from .magic_usage import invoke_http


class FreeLLMVisualClient:
    contact_sheets=True
    max_candidates_per_batch=3
    provider_name='freellmapi'

    def __init__(self,api_key,*,endpoint='http://127.0.0.1:8831/v1/chat/completions',model='auto',http_client=None):
        if not api_key:raise ValueError('FreeLLMAPI token mancante')
        address=urlsplit(endpoint)
        if address.hostname not in {'127.0.0.1','localhost','::1'} or address.scheme!='http':
            raise ValueError('La prova FreeLLMAPI richiede un gateway localhost')
        self._key=api_key;self.endpoint=endpoint;self.model=model;self._http=http_client
        self.last_routed_via=None

    def generate_json(self,prompt,schema,*,image_inputs):
        if not 1<=len(image_inputs)<=3:raise ValueError('Inviare da una a tre tavole per richiesta')
        content=[{'type':'text','text':prompt+'\nReturn JSON only matching this schema: '+json.dumps(schema,separators=(',',':'))}]
        content += [{'type':'image_url','image_url':{'url':'data:'+p['mime_type']+';base64,'+p['data']}} for p in image_inputs]
        body={'model':self.model,'messages':[{'role':'user','content':content}],
              'response_format':{'type':'json_object'},'max_tokens':768,'temperature':0,'stream':False}
        headers={'Authorization':'Bearer '+self._key,'Content-Type':'application/json'}
        def post():
            if self._http is not None:return self._http.post(self.endpoint,json=body,headers=headers,timeout=50)
            with httpx.Client(timeout=httpx.Timeout(50,connect=5)) as client:
                return client.post(self.endpoint,json=body,headers=headers)
        response=invoke_http('freellmapi',body,post,visual=True)
        if response.status_code>=400:
            raise GeminiAPIError(f'FreeLLMAPI HTTP {response.status_code}: verifica visiva non disponibile')
        try:
            data=json.loads(response.json()['choices'][0]['message']['content'])
        except (ValueError,KeyError,IndexError,TypeError) as exc:
            raise ValueError('FreeLLMAPI: risposta JSON non valida') from exc
        self.last_routed_via=response.headers.get('x-routed-via',self.model)
        return SimpleNamespace(data=data,model=self.last_routed_via)
