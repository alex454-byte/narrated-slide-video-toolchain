# The voiceover script. Each sentence: (spoken text, caption text or None, pause-after seconds).
# Each scene: (id, lead-in seconds, tail seconds, sentences). Scene ids must match <section id> in the template.
# Numbers come from config.json only (falls back to config.example.json).
import json, os

ROOT = os.path.dirname(os.path.abspath(__file__)) + '/..'

def load_config():
    for name in ('config.json', 'config.example.json'):
        p = os.path.join(ROOT, name)
        if os.path.exists(p):
            return json.load(open(p))
    raise FileNotFoundError('config.json (or config.example.json) not found')

cfg = load_config()
FPS = int(cfg.get('fps', 30))
EX = int(cfg['example_seconds'])

ONES = 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split()
TENS = 'x x twenty thirty forty fifty sixty seventy eighty ninety'.split()
def words(n):
    n = int(n)
    if n < 20: return ONES[n]
    if n < 100: return TENS[n // 10] + ('' if n % 10 == 0 else '-' + ONES[n % 10])
    if n < 1000: return ONES[n // 100] + ' hundred' + ('' if n % 100 == 0 else ' and ' + words(n % 100))
    raise ValueError(n)

# Values the slides can show with data-var="key" (same numbers as the narration).
VARS = {
    'title': cfg['title'],
    'fps': FPS,
    'example_seconds': EX,
    'example_frames': f'{FPS * EX:,}',
}

S = [
 ('intro', 0.9, 1.0, [
   ('How this toolchain works.', None, 0.35),
   ('You write a short script, and it becomes a narrated video with captions.', None, 0)]),
 ('pipeline', 0.5, 1.2, [
   ('First, each sentence is turned into speech by an open-source voice model, and its length is measured.', None, 0.35),
   ('Those lengths become the timeline. Every element on a slide is timed to the sentence it belongs to.', None, 0.35),
   ('Then a headless browser renders each frame, and ffmpeg joins the frames, the voice and a soft music bed.', None, 0)]),
 ('numbers', 0.5, 2.0, [
   (f'Numbers come from one config file. At {words(FPS)} frames per second, a {words(EX)} second video is {FPS * EX:,} frames.',
    f'Numbers come from one config file. At {FPS} frames per second, a {EX}-second video is {FPS * EX:,} frames.', 0.35),
   ('Change the config, rebuild, and the narration, captions and slides still agree.', None, 0)]),
]

def scenes():
    out = []
    for sid, lead, tail, sents in S:
        out.append({'id': sid, 'lead': lead, 'tail': tail,
                    'sentences': [{'say': a, 'cap': b or a, 'gap': g} for a, b, g in sents]})
    return out

if __name__ == '__main__':
    tot = sum(len(s['say'].split()) for sc in scenes() for s in sc['sentences'])
    print('scenes', len(S), 'words', tot); print(json.dumps(VARS, indent=1))
