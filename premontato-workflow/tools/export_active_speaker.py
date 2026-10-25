"""Developer-only conversion: torch==2.5.1, onnx==1.17.0; not used by installed plugin."""
from pathlib import Path
import copy
import sys,torch,numpy as np,onnxruntime as ort,json,hashlib
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--source-directory',required=True,type=Path);parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
base=args.source_directory.resolve();args.output.parent.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(base))
from model.Model import ASD_Model
class Inference(torch.nn.Module):
 def __init__(self):
  super().__init__();self.model=ASD_Model();self.head=torch.nn.Linear(128,2)
 def forward(self,audio,video):
  a=self.model.forward_audio_frontend(audio);v=self.model.forward_visual_frontend(video)
  return self.head(self.model.forward_audio_visual_backend(a,v))[:,1]
torch.set_num_threads(2)
for name in ['finetuning_TalkSet']:
 state=torch.load(base/'weight'/f'{name}.model',map_location='cpu',weights_only=True)
 model=Inference();model.model.load_state_dict({k[len('model.'):]:v for k,v in state.items() if k.startswith('model.')});model.head.load_state_dict({k[len('lossAV.FC.'):]:v for k,v in state.items() if k.startswith('lossAV.FC.')});model.eval()
 reference=copy.deepcopy(model)
 model.model.audioEncoder.pool1=torch.nn.MaxPool2d((1,3),stride=(1,2),padding=(0,1));model.model.audioEncoder.pool2=torch.nn.MaxPool2d((1,3),stride=(1,2),padding=(0,1))
 a=torch.randn(1,200,13);v=torch.rand(1,50,112,112)*255
 out=args.output
 torch.onnx.export(model,(a,v),str(out),input_names=['audio','video'],output_names=['scores'],opset_version=17,dynamic_axes={'audio':{1:'audio_frames'},'video':{1:'video_frames'},'scores':{0:'video_frames'}})
 sess=ort.InferenceSession(str(out),providers=['CPUExecutionProvider'])
 errors=[]
 for length in [25,50,75]:
  a=torch.randn(1,length*4,13);v=torch.rand(1,length,112,112)*255
  with torch.no_grad(): expected=reference(a,v).numpy()
  actual=sess.run(None,{'audio':a.numpy(),'video':v.numpy()})[0];errors.append(float(np.max(np.abs(expected-actual))))
 assert max(errors)<.001,errors
 print(json.dumps({'model':name,'bytes':out.stat().st_size,'onnx_max_errors':errors,'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}),flush=True)
