param([string]$OutputDirectory=(Join-Path $PSScriptRoot '..\review\catalog-smoke'),[string]$FfmpegPath='C:\Program Files\FFmpeg\ffmpeg.exe',[string]$NodePath='C:\Program Files\nodejs\node.exe')
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\review'))
$out=[IO.Path]::GetFullPath($OutputDirectory)
if(!$out.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Usare una nuova cartella sotto review per i soli media sintetici'}
if(Test-Path -LiteralPath $out){throw 'La cartella fixture esiste già: sceglierne una nuova, nessun file viene sovrascritto'}
New-Item -ItemType Directory -Path $out -Force|Out-Null
$voice=New-Object -ComObject SAPI.SpVoice
$stream=New-Object -ComObject SAPI.SpFileStream
$stream.Open((Join-Path $out 'catalog-speech.wav'),3)
try{$voice.AudioOutputStream=$stream;$voice.Rate=0;$voice.Speak('Ho nascosto le chiavi della macchina nel frigorifero. La barca rossa sta affondando vicino al porto. Ho nascosto le chiavi della macchina nel frigorifero.')|Out-Null}finally{$stream.Close()}
& $FfmpegPath -nostdin -y -loglevel error -f lavfi -i 'color=c=blue:s=320x180:r=25' -i (Join-Path $out 'catalog-speech.wav') -shortest -c:v libx264 -pix_fmt yuv420p -c:a aac (Join-Path $out 'catalog-mixed.mp4')
if($LASTEXITCODE -ne 0){throw 'Generazione clip mista fallita'}
Copy-Item -LiteralPath (Join-Path $out 'catalog-mixed.mp4') -Destination (Join-Path $out 'catalog-takes.mp4')
& $FfmpegPath -nostdin -y -loglevel error -f lavfi -i 'color=c=red:s=320x180:r=25' -t 3 -an -c:v libx264 -pix_fmt yuv420p (Join-Path $out 'catalog-no-audio.mp4')
if($LASTEXITCODE -ne 0){throw 'Generazione clip senza audio fallita'}
$js=@'
const fs=require('node:fs'),path=require('node:path');
const text='INT. CASA - GIORNO\nMARIO\nHo nascosto le chiavi della macchina nel frigorifero.\nEXT. MARE - GIORNO\nLUCA\nLa barca rossa sta affondando vicino al porto.';
const stream='BT /F1 12 Tf 50 760 Td 16 TL '+text.split('\n').map((line,i)=>(i?'T* ':'')+'('+line+') Tj').join('\n')+' ET';
const objects=['<< /Type /Catalog /Pages 2 0 R >>','<< /Type /Pages /Kids [3 0 R] /Count 1 >>','<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>','<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>','<< /Length '+Buffer.byteLength(stream)+' >>\nstream\n'+stream+'\nendstream'];
let pdf='%PDF-1.4\n',offsets=[];for(const [i,obj] of objects.entries()){offsets.push(Buffer.byteLength(pdf));pdf+=(i+1)+' 0 obj\n'+obj+'\nendobj\n';}const xref=Buffer.byteLength(pdf);pdf+='xref\n0 6\n0000000000 65535 f \n'+offsets.map(n=>String(n).padStart(10,'0')+' 00000 n \n').join('')+'trailer << /Size 6 /Root 1 0 R >>\nstartxref\n'+xref+'\n%%EOF';fs.writeFileSync(path.join(process.argv[1],'catalog-script.pdf'),pdf);
'@
& $NodePath -e $js $out
if($LASTEXITCODE -ne 0){throw 'Generazione PDF fallita'}
Write-Output ('Fixture sintetiche: '+$out)
