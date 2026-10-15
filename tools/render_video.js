// Render every scene frame-by-frame (deterministic setT) and pipe JPEGs into ffmpeg.
// Usage: node tools/render_video.js [stills|video] [sceneIds...]
//   stills -> storyboard/<id>.png (one frame per scene, just after its last sentence)
//   video  -> build/vid/<id>.mp4 (every frame; 4 scenes in parallel)
// Env: TPL=path/to/template.html (default slides/video.tpl.html), PWCHROME=path to a Chromium binary (optional).
const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path'); const { spawn } = require('child_process');
const C = path.resolve(__dirname, '..'); const B = C + '/build';
const mode = process.argv[2] || 'video'; const only = process.argv.slice(3);
const TL = JSON.parse(fs.readFileSync(B + '/timeline.json', 'utf8'));
fs.copyFileSync(process.env.TPL || C + '/slides/video.tpl.html', C + '/slides/video.html');
const exe = process.env.PWCHROME || undefined;
async function scene(b, sc) {
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  await p.addInitScript(tl => { window.__TL = tl; }, TL);
  await p.goto('file://' + C + '/slides/video.html'); await p.waitForTimeout(300);
  await p.evaluate(id => setScene(id), sc.id);
  if (mode === 'stills') {
    fs.mkdirSync(C + '/storyboard', { recursive: true });
    const last = sc.sentences[sc.sentences.length - 1];
    const t = Math.min(sc.dur - 0.5, last.end + 0.3);
    await p.evaluate(t => setT(t), t); await p.screenshot({ path: `${C}/storyboard/${sc.id}.png` });
    console.log('still', sc.id);
  } else {
    fs.mkdirSync(B + '/vid', { recursive: true });
    const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', String(TL.fps), '-c:v', 'mjpeg', '-i', '-',
      '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-r', String(TL.fps), '-movflags', '+faststart', `${B}/vid/${sc.id}.mp4`]);
    ff.stderr.on('data', d => process.stderr.write(d));
    for (let f = 0; f < sc.frames; f++) {
      await p.evaluate(t => setT(t), f / TL.fps);
      const buf = await p.screenshot({ type: 'jpeg', quality: 93 });
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    }
    ff.stdin.end(); await new Promise(r => ff.on('close', r));
    console.log('done', sc.id, sc.frames);
  }
  await p.close();
}
(async () => {
  const b = await chromium.launch({ executablePath: exe });
  const list = TL.scenes.filter(s => !only.length || only.includes(s.id));
  const N = mode === 'stills' ? 1 : 4; let i = 0;
  await Promise.all(Array.from({ length: N }, async () => { while (i < list.length) { const sc = list[i++]; await scene(b, sc); } }));
  await b.close();
})();
