# Architecture walkthrough video

Inputs: `docs/orgalyst.architecture.json` (archify source, `meta.animation: "trace"`), delivered with
`node ~/.claude/skills/archify/bin/archify.mjs deliver architecture <json> <html> --quality showcase --repo-root <repo>`.

1. `script.json` holds the five narration segments (zh / en) and their measured durations.
2. Narration: `edge-tts --voice zh-CN-XiaoyiNeural` / `en-US-AriaNeural` (`--rate +5%`) per segment.
3. `rec.js` (puppeteer-core + system Chrome, 1920×1080, Present mode) records one screencast per segment while clicking the guided-view chapters, story beats, a node passport, the theme toggle and the export menu.
4. `assemble.py <zh|en>` retimes each screencast to its narration, overlays the caption PNGs (PIL), adds title / end cards and concatenates with ffmpeg.
5. GIF: segments a2 + a4 (raw, no captions), cropped to the diagram panel, 720 px, 6 fps, 96 colours.
