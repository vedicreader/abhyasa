# Screen guide, phase 1: "I don't get X" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On an abhyasa page, Hyper+E (or the Explain button) takes "I don't get X", and a tutor answers with a hand-drawn board over the page that points at the exact words, maths tokens, figure labels and demo controls on the screen, says one line for each step, and shows which tier (tutor, vault, web) it used, with its sources.

**Architecture:** The page captures what it shows (anchors) and posts it with the question to the `guide` block. The engine (`abhyasa.guide`, from `nbs/21_guide.ipynb`) guards the text for PII, asks the model on the ramabana job `guide`, and checks each JSON line of the reply against a closed command list and the anchors. If the model is not sure, it grounds in the vault, then in the web (research's word-for-word gate). A renderer in core JS draws the checked steps on an SVG layer tied to the anchors.

**Tech Stack:** nbdev 3 (engine), FastHTML blocks, ramabana (routing, `compose`, `accepts`, `masking_guard`), vishalakshi/rahasya (PII, under ramabana's guard), fossick (web, YouTube search), yt-dlp (timed captions), rupaka (`Rupaka.state`, `Rupaka.set`), KaTeX (`\htmlId`), Rough.js 4.6.6 and perfect-freehand 1.2.2 (MIT, vendored), Playwright (Chromium and WebKit).

**Spec:** `abhyasa-designs/screen-guide/design.md` (the section "Owner intent, 30 Oct 2026" is the source of truth) and `open-questions.md` (owner decisions).

## Global Constraints

- All UI text and spoken lines: ASD-STE100, US grade 9.
- Keys: left hand only. Hyper+E = ⌃⌥⇧⌘E: hold (≥ 300 ms) to talk, tap to type. Board keys: A again, S back, D next, Esc stop. Never take a key while the focus is in a text box.
- Every board says its tier: `tutor`, `vault` or `web`. A quote is word for word and links its source. With no source: "In the tutor's own words. No source found."
- Never store a page screenshot. Figure label boxes are cached; the image bytes are not.
- Every model call goes through ramabana routing (job `guide`, and `guide_vision` for figures). Tests use `Fake`.
- Page text, figure prompts and web queries pass ramabana's `masking_guard` before they leave the Mac. `cli.pii` = `refuse` refuses; any other value redacts.
- The model never sends JS, HTML, CSS or a URL. A line with an unknown op or key is dropped.
- Limits: 6 steps, 6 strokes a step, 60 lines, 600 bytes a line, 64 sketch points, `say` ≤ 160, `text` ≤ 60, quote 40 to 600 characters.
- A block never imports another block. Code goes in `abhyasa/blocks/guide/`, `nbs/21_guide.ipynb` and `abhyasa/core/board.{js,css}`. research.py is called, not changed.
- The first stroke of a tier 1 board: within about 2 to 3 s. Measured in `tools/guide_look.py`.

## Review Focus

- A reply that names an anchor that is not on the page (an old id, a made-up token): the line drops, the rest draws. Test in Task 1.
- A page with a secret (an `sk-…` key) in the passage: the key never reaches a model call or a web query. Test in Task 3.
- A demo whose gate is still closed: `demo_set` drops, so the board cannot show the result first. Test in Task 1.
- An htmx swap or a scroll in the middle of a board: the strokes follow their anchors or hide; they never float over the wrong text. Test in Task 7 (scroll) and Task 4 (anchor gone).
- Hyper+E while the focus is in the answer box: the key opens the guide, but A, S and D still type letters in the box. Test in Task 5.

---

### Task 1: The board language and its validator (engine)

**Files:**
- Create: `nbs/21_guide.ipynb` (exports `abhyasa/guide.py`), add it to `nbs/sidebar.yml`
- Test: the notebook's own test cells, and `tests/test_guide.py`

**Interfaces:**
- Produces: `OPS` (tuple of the 11 ops: `step circle box underline arrow label sketch point clear demo_set video_at`), `LIMITS` (dict), `norm_tex(s:str) -> str`, `anchor_why(at, ctx) -> str` ('' when good), `check_line(o:dict, ctx) -> str` (why it drops, or ''), `parse_board(text:str, ctx) -> AttrDict(steps, dropped, sure, need, failed)`; each step is `{n, say, strokes:[...], quote?}`.
- Anchor forms: `"passage"` (an anchor id), `{"a": id, "text": "words"}`, `{"a": id, "tex": "\\bar\\alpha_t"}`, `{"a": id, "label": "a"}` (a figure label), `{"a": id, "box": [x0,y0,x1,y1]}` and `{"a": id, "pt": [x,y]}` (0 to 1000 of the anchor).

- [ ] **Step 1: Write failing tests**: a good DDPM board parses to 3 steps; an unknown op, an unknown key, `html`/`url`/`<script` text, an anchor id not in `ctx.anchors`, a `tex` not in that formula's tokens, a `text` not in the anchor's text, a `label` not in the figure's labels, a sketch with 65 points, a 7th stroke and a 7th step all drop; `demo_set` drops when `ctx.demo.open` is false or a name is not a demo input; `video_at` drops when the quote is not in the cue at `t`; two dropped lines in a row set `failed`. `norm_tex('\\bar{\\alpha}_{t}') == norm_tex('\\bar\\alpha_t')`.
- [ ] **Step 2: Run** `uv run nbdev-prepare` then `uv run pytest tests/test_guide.py -q`. Expected: fails (no module).
- [ ] **Step 3: Implement** in the notebook. The first line may be `{"op":"v","n":1,"sure":0.0-1.0,"need":"none|vault|web"}`.
- [ ] **Step 4: Run** the same commands. Expected: pass.
- [ ] **Step 5: Commit** `Add the board language of the screen guide and its check`.

### Task 2: Context capture and figure labels

**Files:**
- Create: `abhyasa/blocks/guide/{__init__,cfg,app,ui}.py`, `abhyasa/blocks/guide/guide.js`, `guide.css`; add `guide` to `NAMES` (before `today`)
- Modify: `nbs/21_guide.ipynb` (context and figure parts)
- Test: `tests/blocks/test_guide.py`, `tests/test_guide.py`

**Interfaces:**
- Produces (engine): `clean_context(raw:dict) -> AttrDict` (keeps only known keys, cuts text to 300 characters an anchor and 6000 in all), `FIGURE_SP`, `figure_labels(vision, img:bytes, alt:str) -> dict[str, list[int]]`, `FigureCache(path)` with `get(key)`, `put(key, labels)` (keys are the SHA-1 of the image bytes; only boxes are kept).
- Produces (block): `POST /guide/figure` (body: the image bytes; query `alt`) -> `{key, labels}`; `page_extra` adds the guide assets, the Explain button and the box.
- Produces (JS): `texParts(tex, f)` (the TeX parts, tested with node), `abhyasaGuide.capture() -> {page, step, concept, anchors:[{id, kind, text, tex?, tokens?, labels?, inputs?}], demo:{inputs, open}, video?}`. Ids: element ids (`passage`, `figure`, `note`, `check`), `m1…` for each formula, `demo`, `in:<name>` for a demo input, `out:<n>` for a readout.

- [ ] **Step 1: Write failing tests**: `clean_context` drops unknown keys and cuts long text; `tex_tokens` of the DDPM formula holds `\bar\alpha_t`, `\sqrt{\bar\alpha_t}`, `\mathbf{x}_0` and `(1-\bar\alpha_t)`; `figure_labels` with a Fake vision reply gives `{'a': [...], 'b': [...]}` and drops boxes out of 0..1000; the route caches: a second post makes no vision call; the page has `#guide-go` with the text "Explain" and the guide script.
- [ ] **Step 2: Run** the tests. Expected: fail.
- [ ] **Step 3: Implement.** The vision call is `ramabana_agent().compose(text, image=bytes)` on `ramabana_oneshot('guide_vision', …)`, only when `accepts(spec, 'image')`; else no labels. `guide.js` wraps formula tokens with `\htmlId{g-<n>-<k>}` when it captures (KaTeX trust only for `\htmlId` with a `g-` id).
- [ ] **Step 4: Run** the tests. Expected: pass.
- [ ] **Step 5: Commit** `Read what the page shows for the guide, and find figure labels once`.

### Task 3: The three-tier gate, with the PII guard

**Files:**
- Modify: `nbs/21_guide.ipynb`, `pyproject.toml` (`ramabana>=0.2.95`, for `masking_guard`), `abhyasa/blocks/guide/app.py`
- Test: `tests/test_guide.py`, `tests/blocks/test_guide.py`

**Interfaces:**
- Consumes: `parse_board`, `clean_context`; `ground(q, sources)`, `research.web_search`, `research.web_fetch`, `research.pick_passage`, `research.verbatim`.
- Produces: `guard(s:str) -> str` (raises `Withheld` under `refuse`), `GUIDE_SP` (prompt `guide.board`), `board_prompt(ctx, said, sources=()) -> str`, `explain(ask, ctx, said, sources=(), search=None, fetch=None, web=True, note=None) -> AttrDict(tier, steps, sources, sure, ms)`, `SURE = 0.7`; `POST /guide/ask` (JSON body `{said, ctx}`) streams server-sent events: `{"wait": "…"}` lines, then `{"board": …}`.

- [ ] **Step 1: Write failing tests**: a sure reply gives tier `tutor` with one model call; an unsure reply with a vault hit gives tier `vault` and its source; an unsure reply with no vault hit and web on gives tier `web` and a word-for-word quote with its URL; web off gives tier `tutor` with "No source found."; a quote that is not word for word drops from the step; `sk-abcdefghijklmnopqrstu` in the passage reaches no `Fake` call and no search query; the route streams the board.
- [ ] **Step 2: Run.** Expected: fail.
- [ ] **Step 3: Implement.** `guard` builds `masking_guard(lambda: (mode, ner))` from ramabana's `setting('cli.pii')` and reads the text as a `page` read on a hosted model.
- [ ] **Step 4: Run.** Expected: pass.
- [ ] **Step 5: Commit** `Answer at once, from the vault or from the web, and guard what leaves the Mac`.

### Task 4: The renderer

**Files:**
- Create: `abhyasa/core/board.js`, `abhyasa/core/board.css`, `abhyasa/core/vendor/rough.min.js`, `abhyasa/core/vendor/perfect-freehand.js`, `abhyasa/core/vendor/LICENSES.md`
- Modify: `abhyasa/core/keys.py` (a `Guide` group), `tests/test_keys.py` (plain letters of `Guide` count)
- Test: `tests/test_board_js.py` (vendored hashes, no `innerHTML` with model text, keys skip text boxes)

**Interfaces:**
- Produces: `window.abhyasaBoard = {play(board), next(), back(), again(), stop(), boxOf(at)}`. Each stroke is kept as its anchor plus a 0..1000 offset and is drawn again on `scroll`, `resize` and a `ResizeObserver`. A stroke whose anchor left the page hides; when all go, the strip says "The page changed. Ask again."

- [ ] **Step 1: Write failing tests**: the vendor files match their pinned SHA-256; `LICENSES.md` names both MIT licences; `board.js` sets model text only with `textContent`; the key handler returns early for `textarea, input, select, [contenteditable]`.
- [ ] **Step 2: Run.** Expected: fail.
- [ ] **Step 3: Implement.** One step at a time, `speechSynthesis` speaks `say`; strokes start at word marks (`boundary`), else timed by letters. The strip shows the tier pill, the step, and the sources with links.
- [ ] **Step 4: Run.** Expected: pass.
- [ ] **Step 5: Commit** `Draw the board over the page and keep each mark on its anchor`.

### Task 5: The key and the Explain button

**Files:**
- Modify: `abhyasa/blocks/guide/guide.js`, `abhyasa/blocks/guide/ui.py`, `abhyasa/core/keys.py`
- Test: `tests/blocks/test_guide.py`

**Interfaces:**
- Consumes: the `#mic-float` data of the voice block (copied, not imported), `abhyasaMic`.
- Produces: Hyper+E on `window` in the capture phase. A release before 300 ms opens the one-line box `#guide-box`; a hold starts dictation into the box and sends it when the key goes up and the text is in. A release is the keyup of E or of any of the four modifiers (macOS sends no keyup for E while ⌘ is down).

- [ ] **Step 1: Write failing tests**: the keys table has `⌃⌥⇧⌘E` "Explain this: hold to talk, tap to type"; the page has the box with a label and the Explain button; `guide.js` checks all four modifiers.
- [ ] **Step 2–4:** run, implement, run.
- [ ] **Step 5: Commit** `Open the guide with Hyper+E or the Explain button`.

### Task 6: A YouTube explainer on a concept

**Status (30 Oct 2026):** built on `v0014-yt`, with fossick 0.1.24 (`read_yt(url, cues=True)` and `yt_link`). abhyasa has no
transcript parser.

- [x] fossick: `read_yt(url, cues=True)` gives `cues: [{start, end, text}]` in seconds, cached by id. `yt_link(id, s)`.
- [x] Engine (`nbs/21_guide.ipynb`, "The explainer video"): `video_id` (by `yt_link`), `find_explainer` (`search_yt`, the query
  through `guard`), `file_video` (`Vault.youtube`, then the cues from fossick's cache into the document meta with `set_meta`; the
  link passes `public_url`, so `allow_private=False`), `set_video`, `concept_video`, `video_of` and `video_source`. A concept
  keeps one video in its provenance as `src='video'`.
- [x] `cue_quote`: the board seeks to the start of the cue that holds the quote, and quotes it as the transcript says it, with
  `yt_link` to that time. The transcript is a source labelled *video* with the channel and title, so a step quote from it
  passes the word-for-word check, and the end line names it.
- [x] Gather agent: the tool `find_video(idea)` (`research.explainer_video`). The concept page: Find a video, paste a link,
  Remove the video. The walk step shows the video through the `step_needs` hook. The embed is youtube-nocookie with
  `enablejsapi=1` and no autoplay; the transcript is closed until you open it, and each time in it seeks the embed.
- [x] The ask route takes only the video id from the page. The cues come from the vault.
- [x] Tests with fakes for `search_yt` and `read_yt`. `guide_look` checks the seek time and the quote in Chromium and WebKit.

### Task 7: The browser check and the release checks

**Files:**
- Create: `tools/guide_look.py`

- [ ] **Step 1:** A walk step with the DDPM formula: ask "I don't get alpha bar" (Fake reply). Check that each circle lies on the box of `\bar\alpha_t`, that it stays on it after `scrollBy(0, 300)`, and the time from Send to the first stroke. A step with a triangle figure: Fake vision gives `a` and `b`; check that the points land on them. Chromium and WebKit. Screens to `design/screens/guide-*.png`.
- [ ] **Step 2:** Full pytest, `walk_look.py` alone, the docs build (`uv run nbdev-docs`).
- [ ] **Step 3: Commit** `Check the guide in Chromium and WebKit`, then push.
