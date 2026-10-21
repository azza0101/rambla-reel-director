"""Resolve-only native clipboard shortcuts. No AI, MCP, or extra dependency."""
import os,struct,sys,time
from pathlib import Path
import xml.etree.ElementTree as ET


class Reader:
    def __init__(self,data):self.data=data;self.pos=0
    def number(self):
        if self.pos+4>len(self.data):raise ValueError('Preset tastiera incompleto')
        value=struct.unpack_from('>I',self.data,self.pos)[0];self.pos+=4
        return value
    def blob(self):
        length=self.number()
        if length>2_000_000 or self.pos+length>len(self.data):raise ValueError('Preset tastiera non valido')
        value=self.data[self.pos:self.pos+length];self.pos+=length
        return value


def decode_presets(data):
    reader=Reader(data)
    if reader.number()!=1:raise ValueError('Versione preset tastiera non supportata')
    count=reader.number()
    if count>100:raise ValueError('Troppi preset tastiera')
    presets={}
    for _ in range(count):
        name=reader.blob().decode('utf-16-be');mapping=Reader(reader.blob())
        if mapping.number()!=1:raise ValueError('Mappa tastiera non supportata')
        actions={};entries=mapping.number()
        if entries>5000:raise ValueError('Troppi comandi tastiera')
        for _ in range(entries):
            action=mapping.blob().decode('utf-16-be');sequence_count=mapping.number()
            if sequence_count>16:raise ValueError('Sequenza tastiera non supportata')
            sequences=[]
            for _ in range(sequence_count):
                key_count=mapping.number()
                if key_count>4:raise ValueError('Sequenza tastiera troppo lunga')
                sequences.append([mapping.number() for _ in range(key_count)])
            if sequences and len(sequences[0])==1:actions[action]=sequences[0][0]
        presets[name]=actions
    return presets


def preferences():
    if sys.platform!='win32':raise RuntimeError('Spostamento nativo nella stessa timeline: collaudato solo su Windows. Usa Nuova timeline su questo sistema.')
    folder=Path(os.environ['APPDATA'])/'Blackmagic Design/DaVinci Resolve/Preferences'
    settings=ET.parse(folder/'config.user.xml').getroot()
    if settings.findtext('IsTimelineBackupsEnabled')!='true':
        raise RuntimeError('Attiva Timeline Backups nelle preferenze Resolve prima di applicare sulla stessa timeline')
    raw=ET.parse(folder/'keyboard.preset.xml').getroot().findtext('PresetListBA')
    active=settings.findtext('CustomKeyboardPreset');presets=decode_presets(bytes.fromhex(raw or ''))
    if active not in presets:raise RuntimeError('Preset tastiera Resolve non verificabile: nessuna clip spostata')
    actions={name:presets[active].get(name) for name in ('viewActiveWindowSelectionTimeline','editSelectAll','editCut','editPaste')}
    if not all(actions.values()):raise RuntimeError('Scorciatoie timeline/taglia/incolla mancanti: nessuna clip spostata')
    for value in actions.values():
        if value&0x10000000 or not 32<=(value&0x01ffffff)<=126:
            raise RuntimeError('Scorciatoia non supportata: nessuna clip spostata')
    return actions


class WindowsResolveInput:
    def __init__(self,project_name):
        self.actions=preferences()
        import ctypes
        from ctypes import wintypes as W
        self.ctypes=ctypes;self.user=ctypes.WinDLL('user32',use_last_error=True)
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        self.user.GetForegroundWindow.restype=W.HWND
        self.user.GetWindowTextW.argtypes=[W.HWND,W.LPWSTR,ctypes.c_int]
        self.user.IsWindowVisible.argtypes=[W.HWND]
        self.user.SetForegroundWindow.argtypes=[W.HWND]
        self.user.IsIconic.argtypes=[W.HWND]
        self.user.ShowWindow.argtypes=[W.HWND,ctypes.c_int]
        self.user.IsWindowEnabled.argtypes=[W.HWND]
        self.user.GetWindowThreadProcessId.argtypes=[W.HWND,ctypes.POINTER(W.DWORD)]
        self.user.AttachThreadInput.argtypes=[W.DWORD,W.DWORD,W.BOOL]
        self.kernel.GetCurrentThreadId.restype=W.DWORD
        candidates=[]
        callback_type=ctypes.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
        def visit(hwnd,param):
            title=ctypes.create_unicode_buffer(1024);self.user.GetWindowTextW(hwnd,title,1024)
            if self.user.IsWindowVisible(hwnd) and title.value.startswith('DaVinci Resolve') and title.value.endswith(' - '+project_name):candidates.append(hwnd)
            return True
        self.user.EnumWindows.argtypes=[callback_type,W.LPARAM]
        callback=callback_type(visit);self.user.EnumWindows(callback,0)
        if len(candidates)!=1:raise RuntimeError('Finestra principale Resolve non identificabile: nessuna clip spostata')
        self.hwnd=candidates[0]
        # Verify the process, rather than trusting another window's title.
        pid=W.DWORD();self.user.GetWindowThreadProcessId(self.hwnd,ctypes.byref(pid))
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];kernel.OpenProcess.restype=W.HANDLE
        kernel.QueryFullProcessImageNameW.argtypes=[W.HANDLE,W.DWORD,W.LPWSTR,ctypes.POINTER(W.DWORD)]
        kernel.CloseHandle.argtypes=[W.HANDLE]
        handle=kernel.OpenProcess(0x1000,False,pid.value)
        if not handle:raise RuntimeError('Processo Resolve non verificabile')
        try:
            size=W.DWORD(32768);path=ctypes.create_unicode_buffer(size.value)
            if not kernel.QueryFullProcessImageNameW(handle,0,path,ctypes.byref(size)) or Path(path.value).name.lower()!='resolve.exe':raise RuntimeError('La finestra non appartiene a Resolve')
        finally:kernel.CloseHandle(handle)
        class Keyboard(ctypes.Structure):_fields_=[('vk',W.WORD),('scan',W.WORD),('flags',W.DWORD),('time',W.DWORD),('extra',ctypes.c_size_t)]
        class Mouse(ctypes.Structure):_fields_=[('dx',W.LONG),('dy',W.LONG),('data',W.DWORD),('flags',W.DWORD),('time',W.DWORD),('extra',ctypes.c_size_t)]
        class Union(ctypes.Union):_fields_=[('keyboard',Keyboard),('mouse',Mouse)]
        class Input(ctypes.Structure):_fields_=[('type',W.DWORD),('data',Union)]
        self.Keyboard,self.Input=Keyboard,Input
        self.user.SendInput.argtypes=[W.UINT,ctypes.POINTER(Input),ctypes.c_int]
        self.user.SendInput.restype=W.UINT

    def _command(self,name):
        ctypes=self.ctypes
        if not self.user.IsWindowEnabled(self.hwnd):raise RuntimeError('Resolve ha una finestra modale aperta: operazione sospesa')
        if self.user.IsIconic(self.hwnd):self.user.ShowWindow(self.hwnd,9)
        self.user.SetForegroundWindow(self.hwnd)
        if self.user.GetForegroundWindow()!=self.hwnd:
            # Explicit Apply may originate in the integration window. Temporarily
            # join input queues to activate its Resolve parent; never change OS policy.
            foreground=self.user.GetForegroundWindow()
            owner=self.user.GetWindowThreadProcessId(foreground,None)
            current=self.kernel.GetCurrentThreadId()
            message=ctypes.wintypes.MSG()
            self.user.PeekMessageW(ctypes.byref(message),None,0,0,0)
            attached=bool(owner and owner!=current and self.user.AttachThreadInput(current,owner,True))
            try:self.user.SetForegroundWindow(self.hwnd)
            finally:
                if attached:self.user.AttachThreadInput(current,owner,False)
        if self.user.GetForegroundWindow()!=self.hwnd:raise RuntimeError('Focus Resolve non disponibile: operazione sospesa')
        if any(self.user.GetAsyncKeyState(vk)&0x8000 for vk in (0x10,0x11,0x12,0x5b,0x5c)):
            raise RuntimeError('Rilascia i tasti modificatori prima di applicare il CUT')
        value=self.actions[name];modifiers=[vk for flag,vk in [(0x04000000,0x11),(0x02000000,0x10),(0x08000000,0x12)] if value&flag]
        keys=modifiers+[value&0x01ffffff]
        events=[]
        for vk,flags in [(vk,0) for vk in keys]+[(vk,2) for vk in reversed(keys)]:
            event=self.Input();event.type=1;event.data.keyboard=self.Keyboard(vk,0,flags,0,0);events.append(event)
        batch=(self.Input*len(events))(*events)
        if self.user.GetForegroundWindow()!=self.hwnd:raise RuntimeError('Focus cambiato prima del comando: operazione sospesa')
        sent=self.user.SendInput(len(events),batch,ctypes.sizeof(self.Input))
        if sent!=len(events):raise RuntimeError('Comando nativo non completato: verifica la timeline prima di riprovare')
        time.sleep(.15)

    def focus_timeline(self):self._command('viewActiveWindowSelectionTimeline')
    def select_all(self):self._command('editSelectAll')
    def cut(self):self._command('editCut')
    def paste(self):self._command('editPaste')
