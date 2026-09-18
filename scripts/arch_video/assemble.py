import json, subprocess, sys
lang=sys.argv[1]; sc=json.load(open('script.json'))
segdir='seg' if lang=='zh' else 'seg_en'; tts='tts' if lang=='zh' else 'tts_en'; dk='dur' if lang=='zh' else 'dur_en'
def run(c): subprocess.run(c,check=True,capture_output=True)
def dur(f): return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',f]).decode())
parts=[]
# title card 2.8 s, end card 3.5 s
for kind,t in (('title',2.8),('end',3.5)):
    o=f'{segdir}/{kind}.mp4'
    run(['ffmpeg','-y','-v','error','-loop','1','-i',f'cap/{kind}_{lang}.png','-f','lavfi','-i','anullsrc=r=44100:cl=stereo','-t',str(t),'-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-r','30','-c:a','aac','-b:a','128k','-shortest',o])
parts.append(f'{segdir}/title.mp4')
for s in sc:
    raw=f'{segdir}/{s["id"]}_raw.mp4'; D=dur(raw); T=s[dk]+0.35; factor=T/D
    o=f'{segdir}/{s["id"]}.mp4'
    run(['ffmpeg','-y','-v','error','-i',raw,'-i',f'cap/{s["id"]}_{lang}.png','-i',f'{tts}/{s["id"]}.mp3',
         '-filter_complex',f'[0:v]setpts={factor:.5f}*PTS[v0];[v0][1:v]overlay=0:0:format=auto[v];[2:a]apad=pad_dur=0.35,aresample=44100[a]',
         '-map','[v]','-map','[a]','-t',f'{T:.3f}','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-r','30','-c:a','aac','-b:a','128k','-ar','44100','-ac','2',o])
    parts.append(o); print(s['id'],'raw',round(D,2),'->',round(T,2))
parts.append(f'{segdir}/end.mp4')
open(f'{segdir}/list.txt','w').write(''.join(f"file '{p.split('/')[-1]}'\n" for p in parts))
out=f'orgalyst_architecture_{lang}.mp4'
run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',f'{segdir}/list.txt','-c','copy','-movflags','+faststart',out])
print(out, round(dur(out),1),'s')
