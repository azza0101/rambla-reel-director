"""Build the experimental KURA effect for an existing Resolve Text+ clip."""
from pathlib import Path, PurePosixPath
import io
import re
import zipfile


TITLE_PACKAGE = Path(__file__).resolve().parents[1] / 'assets/resolve_titles/KURA_paper_title_v9.drfx'
TITLE_PREFIX = 'Edit/Titles/KURA_paper_title_v9/'
EFFECT_PREFIX = 'Edit/Effects/KURA_Paper_Text_Optimized/'
OPTIMIZED_TITLE_PREFIX = 'Edit/Titles/KURA_Paper_Title_Optimized/'


def source_title_setting() -> str:
    with zipfile.ZipFile(TITLE_PACKAGE) as source:
        return source.read(TITLE_PREFIX + 'KURA_paper_title_v9.setting').decode('utf-8-sig')


def _block_end(source: str, start: int) -> int:
    depth=0;quoted=False;escaped=False
    for i in range(source.index('{',start),len(source)):
        char=source[i]
        if quoted:
            if escaped: escaped=False
            elif char=='\\': escaped=True
            elif char=='"': quoted=False
        elif char=='"': quoted=True
        elif char=='{': depth+=1
        elif char=='}':
            depth-=1
            if depth==0:return i+1
    raise ValueError('Preset Fusion incompleto')


def convert_title_to_effect(source: str) -> str:
    title='KURA_paper_title_v9 = GroupOperator'
    if source.count(title)!=1:raise ValueError('Preset KURA v9 non riconosciuto')
    source=source.replace(title,'KURA_Paper_Text_Optimized = MacroOperator',1)
    matches=list(re.finditer(r'\bTemplate_\w+\s*=\s*InstanceInput\s*\{',source))
    if len(matches)!=13:raise ValueError('Controlli testo KURA non riconosciuti')
    for match in reversed(matches):
        end=_block_end(source,match.start())
        if source[end:end+1]==',':end+=1
        source=source[:match.start()]+source[end:]
    match=re.search(r'\bTemplate\s*=\s*TextPlus\s*\{',source)
    if not match:raise ValueError('Text+ originale non trovato')
    end=_block_end(source,match.start())
    replacement=('Template = PipeRouter { Inputs = { Input = Input { }, }, },\n'
                 'KURA_Input_AutoDomain = AutoDomain { Inputs = { Input = Input '
                 '{ SourceOp = "Template", Source = "Output", }, }, }')
    source=source[:match.start()]+replacement+source[end:]
    # The router immediately following the input is the only link that needs
    # redirection; the public MainInput continues to accept the original Text+.
    marker='PipeRouter4_1_1 = PipeRouter'
    start=source.find(marker)
    if start<0:raise ValueError('Ingresso immagine KURA non trovato')
    end=_block_end(source,start);block=source[start:end]
    if block.count('SourceOp = "Template"')!=1:raise ValueError('Ingresso immagine KURA ambiguo')
    block=block.replace('SourceOp = "Template"','SourceOp = "KURA_Input_AutoDomain"',1)
    source=source[:start]+block+source[end:]
    marker='Inputs = ordered() {';pos=source.find(marker)
    if pos<0:raise ValueError('Controlli Fusion non trovati')
    pos+=len(marker)
    return source[:pos]+'\n MainInput1 = InstanceInput { SourceOp = "Template", Source = "Input", },'+source[pos:]


def convert_optimized_title(source: str) -> str:
    title='KURA_paper_title_v9 = GroupOperator'
    if source.count(title)!=1:raise ValueError('Preset KURA v9 non riconosciuto')
    source=source.replace(title,'KURA_Paper_Title_Optimized = GroupOperator',1)
    match=re.search(r'\bTemplate\s*=\s*TextPlus\s*\{',source)
    if not match:raise ValueError('Text+ originale non trovato')
    end=_block_end(source,match.start())
    if source[end:end+1]!=',':raise ValueError('Struttura titolo KURA inattesa')
    end+=1
    domain=('\nKURA_Input_AutoDomain = AutoDomain { Inputs = { Input = Input '
            '{ SourceOp = "Template", Source = "Output", }, }, },\n')
    source=source[:end]+domain+source[end:]
    start=source.find('PipeRouter4_1_1 = PipeRouter')
    if start<0:raise ValueError('Ingresso immagine KURA non trovato')
    end=_block_end(source,start);block=source[start:end]
    if block.count('SourceOp = "Template"')!=1:raise ValueError('Ingresso immagine KURA ambiguo')
    block=block.replace('SourceOp = "Template"','SourceOp = "KURA_Input_AutoDomain"',1)
    return source[:start]+block+source[end:]


def build_optimized_title_package(target: Path) -> Path:
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(TITLE_PACKAGE) as original, zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as result:
        result.writestr(OPTIMIZED_TITLE_PREFIX+'KURA_Paper_Title_Optimized.setting',convert_optimized_title(source_title_setting()))
        for info in original.infolist():
            if info.is_dir() or not info.filename.startswith(TITLE_PREFIX) or info.filename.endswith('.setting'):continue
            relative=PurePosixPath(info.filename[len(TITLE_PREFIX):])
            if relative.is_absolute() or '..' in relative.parts:raise ValueError('Percorso risorsa KURA non sicuro')
            result.writestr(OPTIMIZED_TITLE_PREFIX+str(relative),original.read(info))
    return target


def build_effect_package(target: Path) -> Path:
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(TITLE_PACKAGE) as original, zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as result:
        result.writestr(EFFECT_PREFIX+'KURA_Paper_Text_Optimized.setting',convert_title_to_effect(source_title_setting()))
        for info in original.infolist():
            if info.is_dir() or not info.filename.startswith(TITLE_PREFIX) or info.filename.endswith('.setting'):continue
            relative=PurePosixPath(info.filename[len(TITLE_PREFIX):])
            if relative.is_absolute() or '..' in relative.parts:raise ValueError('Percorso risorsa KURA non sicuro')
            result.writestr(EFFECT_PREFIX+str(relative),original.read(info))
    return target


def build_effect_install_bundle(target: Path) -> Path:
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    buffer=io.BytesIO()
    with zipfile.ZipFile(TITLE_PACKAGE) as original, zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as effect:
        effect.writestr(EFFECT_PREFIX+'KURA_Paper_Text_Optimized.setting',convert_title_to_effect(source_title_setting()))
        for info in original.infolist():
            if info.is_dir() or not info.filename.startswith(TITLE_PREFIX) or info.filename.endswith('.setting'):continue
            relative=PurePosixPath(info.filename[len(TITLE_PREFIX):])
            if relative.is_absolute() or '..' in relative.parts:raise ValueError('Percorso risorsa KURA non sicuro')
            effect.writestr(EFFECT_PREFIX+str(relative),original.read(info))
    scripts=TITLE_PACKAGE.parent/'installer'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as result:
        result.writestr('KURA_Paper_Text_Optimized.drfx',buffer.getvalue())
        for name in ('Installa KURA Windows.cmd','Installa KURA Windows.ps1','Installa KURA Mac.command'):
            script=(scripts/name).read_text(encoding='utf8')
            script=script.replace('KURA_paper_title_v9_STANDALONE_FIXED.drfx','KURA_Paper_Text_Optimized.drfx')
            script=script.replace('Edit\\Titles\\KURA_paper_title_v9\\KURA_paper_title_v9.setting',
                                  'Edit\\Effects\\KURA_Paper_Text_Optimized\\KURA_Paper_Text_Optimized.setting')
            script=script.replace('Edit/Titles/KURA_paper_title_v9/KURA_paper_title_v9.setting',
                                  'Edit/Effects/KURA_Paper_Text_Optimized/KURA_Paper_Text_Optimized.setting')
            info=zipfile.ZipInfo(name);info.create_system=3
            info.external_attr=(0o100755 if name.endswith('.command') else 0o100644)<<16
            result.writestr(info,script.encode('utf8'))
        result.writestr('LEGGIMI.txt',(
            'PROVA: estrai tutto lo ZIP e avvia l\'installer per Windows o Mac.\n'
            'Riavvia Resolve dopo la prima installazione: nella pagina Edit cerca KURA Paper Text Optimized '
            'tra gli effetti Fusion e trascinalo su un Text+.\n'
            'Testo e font si regolano sul Text+; carta, texture, movimento e ombra si regolano nell\'effetto.\n'
            'I tempi di riproduzione dipendono dal computer.\n'))
    return target


def build_optimized_title_install_bundle(target: Path) -> Path:
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    buffer=io.BytesIO()
    with zipfile.ZipFile(TITLE_PACKAGE) as original, zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as title:
        title.writestr(OPTIMIZED_TITLE_PREFIX+'KURA_Paper_Title_Optimized.setting',convert_optimized_title(source_title_setting()))
        for info in original.infolist():
            if info.is_dir() or not info.filename.startswith(TITLE_PREFIX) or info.filename.endswith('.setting'):continue
            relative=PurePosixPath(info.filename[len(TITLE_PREFIX):])
            if relative.is_absolute() or '..' in relative.parts:raise ValueError('Percorso risorsa KURA non sicuro')
            title.writestr(OPTIMIZED_TITLE_PREFIX+str(relative),original.read(info))
    scripts=TITLE_PACKAGE.parent/'installer'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as result:
        result.writestr('KURA_Paper_Title_Optimized.drfx',buffer.getvalue())
        for name in ('Installa KURA Windows.cmd','Installa KURA Windows.ps1','Installa KURA Mac.command'):
            script=(scripts/name).read_text(encoding='utf8')
            script=script.replace('KURA_paper_title_v9_STANDALONE_FIXED.drfx','KURA_Paper_Title_Optimized.drfx')
            script=script.replace('Edit\\Titles\\KURA_paper_title_v9\\KURA_paper_title_v9.setting',
                                  'Edit\\Titles\\KURA_Paper_Title_Optimized\\KURA_Paper_Title_Optimized.setting')
            script=script.replace('Edit/Titles/KURA_paper_title_v9/KURA_paper_title_v9.setting',
                                  'Edit/Titles/KURA_Paper_Title_Optimized/KURA_Paper_Title_Optimized.setting')
            info=zipfile.ZipInfo(name);info.create_system=3
            info.external_attr=(0o100755 if name.endswith('.command') else 0o100644)<<16
            result.writestr(info,script.encode('utf8'))
        result.writestr('LEGGIMI.txt',(
            'PROVA: estrai lo ZIP ed esegui l\'installer per Windows o Mac.\n'
            'Dopo il riavvio di Resolve, cerca KURA Paper Title Optimized fra i titoli Fusion.\n'
            'Il titolo usa Montserrat Black; il font deve essere installato sul computer.\n'
            'Il titolo originale KURA v9 rimane disponibile.\n'))
    return target
