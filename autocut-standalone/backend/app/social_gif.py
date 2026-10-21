"""Small animated contact sheet, executed in the existing media runtime."""
import argparse
import json
from pathlib import Path
import subprocess


def sample_times(duration):
    return [round(float(duration)*(.10+.16*i),3) for i in range(6)]


def make_gif(source, provider, output, *, full_cache=None, cookies=None):
    from PIL import Image, ImageOps
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    frames=[];local=Path(full_cache) if full_cache else None
    headers={}
    if local and local.is_file():
        metadata=json.loads(subprocess.run(['ffprobe','-v','error','-show_format','-of','json',str(local)],capture_output=True,text=True,check=True,timeout=10).stdout)
        duration=float(metadata['format']['duration']);media=str(local)
    else:
        if provider=='youtube_shorts':
            from .quality_video import _youtube_storyboard_frames
            try:
                frames=[Path(r['path']) for r in _youtube_storyboard_frames(source,output.parent,'hover-gif',6)]
            except Exception:
                frames=[]
        if len(frames)<4:
            frames=[]
            from yt_dlp import YoutubeDL
            options={'quiet':True,'no_warnings':True,'noplaylist':True,'socket_timeout':10,'retries':0,
                     'format':'b[height<=480]/best[height<=480]/best'}
            if cookies:options['cookiefile']=str(cookies)
            with YoutubeDL(options) as downloader: metadata=downloader.extract_info(source,download=False)
            duration=float(metadata.get('duration') or 0);media=metadata.get('url')
            headers=metadata.get('http_headers') or {}
            if not media or duration<=0:raise RuntimeError('Video timeline unavailable')
    if not frames:
        for index,second in enumerate(sample_times(duration)):
            frame=output.parent/f'hover-frame-{index}.jpg'
            command=['ffmpeg','-v','error','-y']
            if str(media).startswith(('https://','http://')):
                command+=['-rw_timeout','7000000']
                safe_headers=''.join(f'{k}: {v}\r\n' for k,v in headers.items() if '\r' not in str(v) and '\n' not in str(v))
                if safe_headers:command+=['-headers',safe_headers]
            command+=['-ss',str(second),'-i',str(media),'-frames:v','1','-vf','scale=180:320:force_original_aspect_ratio=decrease',str(frame)]
            subprocess.run(command,check=True,capture_output=True,timeout=12)
            frames.append(frame)
    images=[]
    for path in frames:
        with Image.open(path) as raw:
            images.append(ImageOps.pad(raw.convert('RGB'),(180,320),color='#080b10').quantize(colors=64))
    if len(images)<4:raise RuntimeError('Insufficient timeline samples')
    temporary=output.with_suffix('.pending.gif')
    images[0].save(temporary,format='GIF',save_all=True,append_images=images[1:],duration=450,loop=0,optimize=True)
    temporary.replace(output)
    output.with_suffix('.json').write_text(json.dumps({'samples':len(images),'width':180,'height':320,'timeline':'distributed'}))
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for field in ('source','provider','output','full-cache','cookies'):parser.add_argument('--'+field)
    args=parser.parse_args()
    make_gif(args.source,args.provider,args.output,full_cache=args.full_cache,cookies=args.cookies)
