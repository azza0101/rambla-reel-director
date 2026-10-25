"""MFCC compatible with python_speech_features (James Lyons, MIT)."""
import numpy as np
def mfcc(audio):
 x=np.asarray(audio,dtype=np.float64);x=np.concatenate((x[:1],x[1:]-.97*x[:-1]))
 count=1+max(0,int(np.ceil((len(x)-400)/160)));pad=np.pad(x,(0,max(0,(count-1)*160+400-len(x))))
 frames=pad[np.arange(count)[:,None]*160+np.arange(400)[None,:]]
 power=np.abs(np.fft.rfft(frames,512))**2/512;energy=np.maximum(power.sum(1),np.finfo(float).eps)
 mel=np.linspace(0,2595*np.log10(1+8000/700),28);bins=np.floor(513*700*(10**(mel/2595)-1)/16000).astype(int);filters=np.zeros((26,257))
 for i in range(26):
  for j in range(bins[i],bins[i+1]):filters[i,j]=(j-bins[i])/(bins[i+1]-bins[i])
  for j in range(bins[i+1],bins[i+2]):filters[i,j]=(bins[i+2]-j)/(bins[i+2]-bins[i+1])
 feat=np.log(np.maximum(power@filters.T,np.finfo(float).eps));dct=np.cos(np.pi/26*(np.arange(26)+.5)[None,:]*np.arange(13)[:,None])*np.sqrt(2/26);dct[0]/=np.sqrt(2)
 out=feat@dct.T;out*=1+11*np.sin(np.pi*np.arange(13)/22);out[:,0]=np.log(energy)
 return out.astype(np.float32)
