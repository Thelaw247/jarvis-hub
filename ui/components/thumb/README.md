# jv-thumb (N5a)

A picture of a thing **with its big label** (HUD v2 §5). `.thumb = { src, kind, alt }` (contracts `common $defs.thumb`).

`<jv-thumb label="PPS 7 · Q7" fallback="course|person|room|monogram" text="GE 122" ratio="wide|page|square" size="small">`

- The box has a fixed aspect ratio (from `ratio`, else the thumb's kind: slide/video/design 16:9, page 4:3 top crop,
  course/person square), so nothing shifts when the picture arrives. Images load lazily and decode async.
- No picture, or it fails to load: a course monogram ("GE" over "122"), initials for people ("ST"), or a big
  room code ("ENGR" over "1B71"). Helpers `initials(name)` and `monogram(code)` are exported.
- `size="small"`: 48 px (80 × 45 wide, 64 × 48 page), no label overlay, for beside a label.

Pictures come from `GET /api/thumb/<key>.webp` (`jarvis_hub/thumbs.py`). The made-up demo pictures live in
`demo/` and are drawn by `python tools/make_demo_thumbs.py` (never his real files). Keys:
`file-pps7-p1`, `file-pps7-p3`, `file-pps7-hints-p1`, `file-lab4-p1`, `slides-ge122-l21`, `slides-chem142-l18`,
`video-ge122-l21`, `course-ge-122`, `course-chem-142`, `course-math-133`, `design-cedar` (all `.webp`;
`python tools/make_demo_thumbs.py --list` prints what each shows, for the alt text).

Scene: `?scene=component:thumb` (pictures, every fallback, a picture that fails, small).

A `size="small"` thumb keeps its size in a flex row (it was squeezed under the label in narrow glass panels).
