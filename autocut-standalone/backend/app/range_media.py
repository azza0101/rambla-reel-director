"""Short-lived fixed-source byte-range bridge for Windows FFmpeg HTTPS.

Python verifies upstream TLS. Only an ephemeral loopback /media endpoint exists;
no caller-selected target, credential logging, external listener or persistent service.
"""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import threading
import time
import httpx


@contextmanager
def range_media(source_url,*,max_bytes=8*1024*1024,max_seconds=45):
    used=0;guard=threading.Lock();deadline=time.monotonic()+max_seconds
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            nonlocal used
            if self.path!='/media':self.send_error(404);return
            headers={}
            if self.headers.get('Range'):headers['Range']=self.headers['Range']
            try:
                with httpx.stream('GET',source_url,headers=headers,follow_redirects=True,timeout=12) as response:
                    response.raise_for_status()
                    self.send_response(response.status_code)
                    for key in ('Content-Length','Content-Range','Accept-Ranges','Content-Type'):
                        if key in response.headers:self.send_header(key,response.headers[key])
                    self.send_header('Connection','close');self.end_headers()
                    for chunk in response.iter_bytes():
                        with guard:
                            used+=len(chunk)
                            if used>max_bytes or time.monotonic()>deadline:return
                        self.wfile.write(chunk)
            except (OSError,httpx.HTTPError):return
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.05},daemon=True)
    thread.start()
    try:yield f'http://127.0.0.1:{server.server_port}/media'
    finally:server.shutdown();server.server_close();thread.join(timeout=1)
