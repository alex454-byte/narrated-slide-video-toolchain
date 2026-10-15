# Synthetic tests for the engine: no TTS, browser or ffmpeg required.
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
import audio, check, script

FAKE = [
    {'id': 'a', 'lead': 0.5, 'tail': 1.0, 'sentences': [
        {'say': 'one two three', 'cap': 'one two three', 'gap': 0.3},
        {'say': 'four five', 'cap': 'four five', 'gap': 0}]},
    {'id': 'b', 'lead': 0.4, 'tail': 0.7, 'sentences': [
        {'say': 'six', 'cap': 'six', 'gap': 0}]},
]
LENS = {'one two three': 1.234, 'four five': 0.9, 'six': 0.5}
fake_render = lambda text: (f'/fake/{text}.wav', LENS[text])

class Timeline(unittest.TestCase):
    def setUp(self):
        self.tl, self.cues, self.segs, self.T = audio.build_timeline(FAKE, fake_render, fps=30)

    def test_sentence_starts_follow_lead_and_gaps(self):
        a = self.tl[0]['sentences']
        self.assertEqual(a[0]['start'], 0.5)
        self.assertAlmostEqual(a[1]['start'], 0.5 + 1.234 + 0.3, places=3)

    def test_scene_rounds_up_to_whole_frames(self):
        for s in self.tl:
            self.assertEqual(s['frames'], round(s['dur'] * 30))
        raw = 0.5 + 1.234 + 0.3 + 0.9 + 1.0
        self.assertGreaterEqual(self.tl[0]['dur'], raw)
        self.assertLess(self.tl[0]['dur'] - raw, 1 / 30)

    def test_audio_segments_sum_to_video_length(self):
        sil = sum(v for k, v in self.segs if k == 'sil')
        speech = sum(LENS[os.path.basename(v)[:-4]] for k, v in self.segs if k == 'wav')
        self.assertAlmostEqual(sil + speech, self.T, places=6)
        self.assertAlmostEqual(self.T, sum(s['dur'] for s in self.tl), places=6)

    def test_second_scene_starts_where_first_ends(self):
        self.assertAlmostEqual(self.tl[1]['start'], self.tl[0]['dur'], places=3)
        self.assertAlmostEqual(self.cues[-1]['start'], self.tl[0]['dur'] + 0.4, places=6)

class Captions(unittest.TestCase):
    def test_chunks_respect_width_and_keep_words(self):
        text = 'Then a headless browser renders each frame, and ffmpeg joins the frames, the voice and a soft music bed.'
        cs = audio.chunks(text)
        self.assertEqual(' '.join(cs).split(), text.split())
        self.assertTrue(all(len(c) <= 62 + 14 for c in cs))

    def test_no_tiny_orphan(self):
        cs = audio.chunks('a' * 55 + ' bb cc dd ee')
        self.assertGreaterEqual(len(cs[-1]), 14)

    def test_srt_format(self):
        s = audio.srt([{'start': 0, 'end': 1.5, 'text': 'hi'}, {'start': 3661.25, 'end': 3662, 'text': 'yo'}])
        self.assertIn('1\n00:00:00,000 --> 00:00:01,500\nhi\n', s)
        self.assertIn('2\n01:01:01,250 --> 01:01:02,000\nyo\n', s)

    def test_estimate_has_a_floor(self):
        self.assertEqual(audio.estimate('hi')[1], 1.0)

class Words(unittest.TestCase):
    def test_words(self):
        self.assertEqual(script.words(30), 'thirty')
        self.assertEqual(script.words(42), 'forty-two')
        self.assertEqual(script.words(105), 'one hundred and five')
        with self.assertRaises(ValueError): script.words(1000)

class TemplateCheck(unittest.TestCase):
    def test_bundled_template_matches_script(self):
        html = open(os.path.join(script.ROOT, 'slides', 'video.tpl.html')).read()
        self.assertEqual(check.problems(html, script.scenes(), script.VARS), [])

    def test_catches_mismatches(self):
        html = ('<section id="a"><div data-at="5"></div><div data-at="x1"></div><b data-var="nope"></b></section>'
                '<section id="orphan"></section>')
        p = check.problems(html, FAKE, {})
        self.assertTrue(any('beyond 2' in x for x in p))
        self.assertTrue(any('bad data-at' in x for x in p))
        self.assertTrue(any('nope' in x for x in p))
        self.assertTrue(any('no <section id="b">' in x for x in p))
        self.assertTrue(any('orphan' in x for x in p))

if __name__ == '__main__':
    unittest.main()
