# Static self-check: does the slide template agree with the script? No audio, browser or ffmpeg needed.
# Checks: every scene has a <section>, every data-at beat index exists, every data-var key is defined.
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from script import scenes, VARS, ROOT

SPEC = re.compile(r'^(@[\d.]+|\d+([+-][\d.]+)?)$')

def sections(html):
    """Map section id -> its inner HTML."""
    return {m.group(1): m.group(2) for m in re.finditer(r'<section id="([^"]+)">(.*?)</section>', html, re.S)}

def problems(html, scs, vars_):
    html = re.sub(r'<!--.*?-->', '', html, flags=re.S)  # ignore documentation comments
    out, secs = [], sections(html)
    ids = [s['id'] for s in scs]
    if len(set(ids)) != len(ids): out.append('duplicate scene ids in script')
    for sc in scs:
        body = secs.get(sc['id'])
        if body is None: out.append(f"scene {sc['id']}: no <section id=\"{sc['id']}\"> in template"); continue
        n = len(sc['sentences'])
        for attr, spec in re.findall(r'data-(at|out)="([^"]*)"', body):
            if not SPEC.match(spec): out.append(f"scene {sc['id']}: bad data-{attr}=\"{spec}\""); continue
            if spec[0] != '@' and int(re.match(r'\d+', spec).group()) > n:
                out.append(f"scene {sc['id']}: data-{attr}=\"{spec}\" refers to sentence beyond {n}")
    for k in re.findall(r'data-var="([^"]+)"', html):
        if k not in vars_: out.append(f'data-var="{k}" not defined in VARS')
    for sid in secs:
        if sid not in ids: out.append(f'section {sid}: no matching scene in script (never rendered)')
    return out

if __name__ == '__main__':
    tpl = os.environ.get('TPL', ROOT + '/slides/video.tpl.html')
    p = problems(open(tpl).read(), scenes(), VARS)
    for x in p: print('FAIL', x)
    print('OK' if not p else f'{len(p)} problem(s)'); sys.exit(1 if p else 0)
