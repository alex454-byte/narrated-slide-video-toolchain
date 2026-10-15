# Synthesise a soft ambient pad bed locally (pure sine synthesis in ffmpeg: no samples, no copyright).
import json, os, subprocess
ROOT = os.path.dirname(os.path.abspath(__file__)) + '/..'
B = ROOT + '/build/music'; os.makedirs(B, exist_ok=True)
total = json.load(open(ROOT + '/build/timeline.json'))['total']
def run(*a): subprocess.run(a, check=True, capture_output=True)

CH = {  # Hz: Dmaj9, Bm7(add11), Gmaj7, Asus2
  'D': [73.42, 146.83, 220.00, 277.18, 329.63, 369.99],
  'B': [61.74, 123.47, 185.00, 220.00, 293.66, 329.63],
  'G': [49.00,  98.00, 146.83, 185.00, 246.94, 293.66],
  'A': [55.00, 110.00, 164.81, 220.00, 246.94, 329.63],
}
SEG = 10.0
for k, fs in CH.items():
    amps = [0.30, 0.22, 0.16, 0.12, 0.10, 0.08]
    terms = []
    for i, (f, a) in enumerate(zip(fs, amps)):
        lfo = f'(0.75+0.25*sin(2*PI*{0.07 + 0.03*i:.3f}*t+{i}))'
        terms.append(f'{a}*{lfo}*(sin(2*PI*{f}*t)+0.6*sin(2*PI*{f*1.0035:.3f}*t))')
    expr = '+'.join(terms)
    run('ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'aevalsrc={expr}:s=48000:d={SEG}',
        '-af', f'lowpass=f=900,lowpass=f=1400,afade=t=in:d=3,afade=t=out:st={SEG-3}:d=3,volume=0.25',
        '-ac', '1', f'{B}/{k}.wav')

order = []
n = 0
while (len(order)) * (SEG - 3) < total + 6:
    order.append('DBGA'[n % 4]); n += 1
inputs = sum([['-i', f'{B}/{k}.wav'] for k in order], [])
g, last = [], '[0:a]'
for i in range(1, len(order)):
    out = f'[x{i}]'; g.append(f'{last}[{i}:a]acrossfade=d=3:c1=qsin:c2=qsin{out}'); last = out
g.append(f'{last}aecho=0.8:0.7:180|420:0.25|0.15,atrim=0:{total:.3f},afade=t=in:d=2.5,afade=t=out:st={total-3.5:.3f}:d=3.5,loudnorm=I=-31:TP=-9:LRA=7[m]')
run('ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', ';'.join(g), '-map', '[m]', '-ar', '48000', '-ac', '2', ROOT + '/build/music_bed.wav')
print('music bed', total, 's,', len(order), 'segments')
