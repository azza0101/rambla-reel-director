$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$root=Split-Path -Parent $PSScriptRoot
$folder=Join-Path $root 'runtime\models\semantic'
$lock=Get-Content -Raw (Join-Path $folder 'model-lock.json')|ConvertFrom-Json
foreach($name in @('model.onnx','tokenizer.json')){
 $info=$lock.files.$name
 $dest=Join-Path $folder $name
 if(!(Test-Path -LiteralPath $dest) -or (Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLowerInvariant() -ne $info.sha256){
  $url='https://huggingface.co/'+$lock.repository+'/resolve/'+$lock.revision+'/'+$info.source
  Invoke-WebRequest -Uri $url -OutFile $dest
 }
 if((Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLowerInvariant() -ne $info.sha256){throw ('Hash modello non valido: '+$name)}
}

$sfaceFolder=Join-Path $root 'runtime\models\sface'
$sfaceLock=Get-Content -Raw (Join-Path $sfaceFolder 'model-lock.json')|ConvertFrom-Json
$sfaceDest=Join-Path $sfaceFolder 'model.onnx'
if(!(Test-Path -LiteralPath $sfaceDest) -or (Get-FileHash -LiteralPath $sfaceDest -Algorithm SHA256).Hash.ToLowerInvariant() -ne $sfaceLock.sha256){
 Invoke-WebRequest -Uri ('https://media.githubusercontent.com/media/'+$sfaceLock.repository+'/'+$sfaceLock.revision+'/'+$sfaceLock.source) -OutFile $sfaceDest
}
if((Get-FileHash -LiteralPath $sfaceDest -Algorithm SHA256).Hash.ToLowerInvariant() -ne $sfaceLock.sha256){throw 'Hash modello SFace non valido'}
