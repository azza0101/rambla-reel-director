from html.parser import HTMLParser

class SearchPageEvidence(HTMLParser):
    """Inspect document elements/text, excluding scripts and hidden templates."""
    def __init__(self):
        super().__init__();self.stack=[];self.text=[];self.login_required=False;self.signed_in=False;self.title=[];self.in_title=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);style=a.get('style','').replace(' ','').lower()
        hidden=tag in {'script','style','template','noscript'} or 'hidden' in a or a.get('aria-hidden')=='true' or 'display:none' in style or 'visibility:hidden' in style
        blocked=hidden or any(self.stack)
        if tag not in {'input','img','br','hr','meta','link','source','area','base','embed','param','wbr'}:self.stack.append(blocked)
        if tag=='title':self.in_title=True
        if blocked:return
        if tag=='input' and a.get('type','').lower()=='password':self.login_required=True
        if a.get('href','').startswith('/accounts/edit/') or a.get('data-e2e')=='profile-icon':self.signed_in=True
    def handle_endtag(self,tag):
        if tag=='title':self.in_title=False
        if self.stack:self.stack.pop()
    def handle_data(self,data):
        if self.in_title:self.title.append(data)
        if not any(self.stack):self.text.append(data)
    @property
    def visible_text(self):return ' '.join(' '.join(self.text).lower().split())

def inspect_search_html(html):
    result=SearchPageEvidence();result.feed(html);return result
