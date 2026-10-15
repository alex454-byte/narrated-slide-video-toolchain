# Render the voiceover sentence-by-sentence with Kokoro (open source, voice af_heart), then build the
# scene timeline (build/timeline.json), captions (final/<output_name>.srt) and the VO track (build/vo_raw.wav).
#
#   python3 tools/audio.py              # real TTS (needs Kokoro + espeak-ng + ffmpeg)
#   python3 tools/audio.py --estimate   # no audio: estimate sentence lengths from word count,
#                                       # write timeline.json only (for previewing stills / layout)
import json, os, subprocess, hashlib, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from script import scenes, VARS, FPS, ROOT, cfg

VOICE = 'kokoro:' + cfg.get('voice', 'af_heart')
B = ROOT + '/build'
F = ROOT + '/final'
WPS = 2.6  # words per second, used only by --estimate

def run(*a): subprocess.run(a, check=True, capture_output=True)
def dur(f): return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], capture_output=True, text=True).stdout)

_pipe = None
def kokoro(text, out):
    global _pipe
    import numpy as np, soundfile as sf
    if _pipe is None:
        # Optional override: on some macOS installs the espeak-ng data bundled with espeakng_loader
        # is not found; point these at a system espeak-ng (e.g. from Homebrew) instead.
        lib, data = os.environ.get('ESPEAK_NG_LIB'), os.environ.get('ESPEAK_NG_DATA')
        if lib and data:
            import espeakng_loader as e
            e.get_library_path = lambda: lib
            e.get_data_path = lambda: data
        from kokoro import KPipeline
        _pipe = KPipeline(lang_code='a', repo_id='hexgrad/Kokoro-82M')
    sf.write(out, np.concatenate([a for _, _, a in _pipe(text, voice=VOICE.split(':')[1])]), 24000)

def render(text):
    """Synthesise one sentence (cached by hash of voice + text). Returns (wav path, seconds)."""
    h = hashlib.sha1((VOICE + text).encode()).hexdigest()[:12]
    wav = f'{B}/vo/{h}.wav'
    if not os.path.exists(wav):
        src = f'{B}/vo/{h}.src.wav'
        kokoro(text, src)
        # trim leading/trailing silence a touch, resample to 48 kHz mono
        run('ffmpeg', '-v', 'error', '-y', '-i', src, '-af',
            'silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.02,areverse,silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.05,areverse',
            '-ar', '48000', '-ac', '1', '-c:a', 'pcm_s16le', wav)
    return wav, dur(wav)

def estimate(text):
    return None, round(max(1.0, len(text.split()) / WPS), 3)

def chunks(text, maxc=62):
    """Split a caption into on-screen lines of at most ~maxc characters."""
    words, out, cur = text.split(), [], ''
    for w in words:
        if cur and len(cur) + 1 + len(w) > maxc:
            out.append(cur); cur = w
        else:
            cur = (cur + ' ' + w).strip()
        if re.search(r'[,:;]$', cur) and len(cur) > maxc * 0.55:
            out.append(cur); cur = ''
    if cur: out.append(cur)
    # avoid a tiny orphan last chunk
    if len(out) > 1 and len(out[-1]) < 14:
        last = out.pop(); out[-1] += ' ' + last
    return out

def build_timeline(scs, render_fn, fps=FPS):
    """Lay out scenes from measured sentence lengths. Returns (timeline, cues, audio segments, total seconds).
    Each scene is rounded up to whole frames; the rounding goes into its tail silence so audio and video stay in sync."""
    timeline, cues, segs, T = [], [], [], 0.0
    for sc in scs:
        t = sc['lead']; sents = []
        segs.append(('sil', sc['lead']))
        for s in sc['sentences']:
            wav, d = render_fn(s['say'])
            sents.append({'start': round(t, 3), 'end': round(t + d, 3), 'cap': s['cap']})
            cs = chunks(s['cap']); total = sum(len(c) for c in cs); ct = t
            for c in cs:
                cd = d * len(c) / total
                cues.append({'start': T + ct, 'end': T + ct + cd, 'text': c, 'scene': sc['id'], 'local': [ct, ct + cd]})
                ct += cd
            segs.append(('wav', wav)); t += d
            if s['gap']: segs.append(('sil', s['gap'])); t += s['gap']
        t += sc['tail']
        frames = int(-(-t * fps // 1))          # ceil to whole frames
        sd = frames / fps
        segs.append(('sil', sd - (t - sc['tail'])))  # tail + rounding
        timeline.append({'id': sc['id'], 'start': round(T, 3), 'dur': sd, 'frames': frames, 'sentences': sents,
                         'cues': [{'t0': round(c['local'][0], 3), 't1': round(c['local'][1], 3), 'text': c['text']} for c in cues if c['scene'] == sc['id']]})
        T += sd
    return timeline, cues, segs, T

def ts(x):
    ms = int(round(x * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'

def srt(cues):
    return ''.join(f"{i}\n{ts(c['start'])} --> {ts(c['end'])}\n{c['text']}\n\n" for i, c in enumerate(cues, 1))

def write_vo(segs):
    """Concatenate sentence WAVs and exact-length silences into build/vo_raw.wav."""
    lst = f'{B}/vo_concat.txt'
    with open(lst, 'w') as fh:
        for k, v in segs:
            if k == 'wav':
                fh.write(f"file '{os.path.abspath(v)}'\n")
            else:
                n = int(round(v * 48000))
                if n <= 0: continue
                f = f'{B}/vo/sil_{n}.wav'
                if not os.path.exists(f):
                    run('ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=mono', '-af', f'atrim=end_sample={n}', '-c:a', 'pcm_s16le', f)
                fh.write(f"file '{os.path.abspath(f)}'\n")
    run('ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c:a', 'pcm_s16le', f'{B}/vo_raw.wav')

def main(argv):
    est = '--estimate' in argv
    os.makedirs(B + '/vo', exist_ok=True); os.makedirs(F, exist_ok=True)
    timeline, cues, segs, T = build_timeline(scenes(), estimate if est else render)
    if not est:
        write_vo(segs)
        open(f"{F}/{cfg.get('output_name', 'video')}.srt", 'w').write(srt(cues))
    json.dump({'fps': FPS, 'total': T, 'vars': VARS, 'estimated': est, 'scenes': timeline}, open(B + '/timeline.json', 'w'), indent=1)
    for s in timeline: print(s['id'], f"{s['dur']:.2f}s", f"start {s['start']:.2f}")
    print('TOTAL', round(T, 2), 's', '(estimated, no audio written)' if est else f"| vo_raw {round(dur(B + '/vo_raw.wav'), 2)}")

if __name__ == '__main__':
    main(sys.argv[1:])
