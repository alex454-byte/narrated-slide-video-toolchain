# Mix VO + ducked music bed, two-pass loudnorm to -16 LUFS / -1.5 dBTP, concat scene videos, mux to final mp4.
import json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from script import cfg, ROOT
B = ROOT + '/build'; F = ROOT + '/final'
TL = json.load(open(B + '/timeline.json'))
if TL.get('estimated'):
    sys.exit('timeline.json was made with --estimate (no audio). Run python3 tools/audio.py first.')
def run(*a): return subprocess.run(a, check=True, capture_output=True, text=True)
os.makedirs(F, exist_ok=True)

music = os.path.exists(B + '/music_bed.wav')
if music:
    mix = ('[0:a]aformat=channel_layouts=stereo,asplit=2[vo][sc];'
           '[1:a][sc]sidechaincompress=threshold=0.03:ratio=4:attack=60:release=600[bed];'
           '[vo][bed]amix=inputs=2:normalize=0:duration=first[mix]')
    ins = ['-i', B + '/vo_raw.wav', '-i', B + '/music_bed.wav']
else:
    mix = '[0:a]aformat=channel_layouts=stereo[mix]'; ins = ['-i', B + '/vo_raw.wav']
run('ffmpeg', '-v', 'error', '-y', *ins, '-filter_complex', mix, '-map', '[mix]', '-ar', '48000', '-c:a', 'pcm_s24le', B + '/mix.wav')
m = run('ffmpeg', '-hide_banner', '-i', B + '/mix.wav', '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-').stderr
j = json.loads(m[m.rindex('{'):m.rindex('}') + 1])
ln = (f"loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}"
      f":measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
run('ffmpeg', '-v', 'error', '-y', '-i', B + '/mix.wav', '-af', ln + ',aresample=48000', '-c:a', 'pcm_s24le', B + '/mix_norm.wav')

with open(B + '/vid_concat.txt', 'w') as fh:
    for s in TL['scenes']: fh.write(f"file '{os.path.abspath(B + '/vid/' + s['id'] + '.mp4')}'\n")
run('ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', B + '/vid_concat.txt', '-c', 'copy', B + '/video_only.mp4')
run('ffmpeg', '-v', 'error', '-y', '-i', B + '/video_only.mp4', '-i', B + '/mix_norm.wav', '-map', '0:v', '-map', '1:a',
    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-shortest', '-movflags', '+faststart',
    '-metadata', f"title={cfg['title']}", f"{F}/{cfg.get('output_name', 'video')}.mp4")
print('measured input', j['input_i'], 'LUFS; music bed:', music)
