# Decisions

These are the decisions that a maintainer must know. Each entry gives the decision, the reason, the date, and where it is in
the code. For the rules on how to work in this repo, see [CLAUDE.md](../CLAUDE.md). For how to run and release, see
[develop.md](develop.md). The old plans and design notes are in the git history (before 3 Nov 2026).

## Product and learning

**A walk is a map of 3 to 7 big ideas.** A walk from a source has its main claim and 3 to 7 big ideas. Details, such as sizes
and scores, stay on the page as reading, with no checks. Why: a long list of facts does not teach a person; the big ideas do.
2 Nov 2026. `MAP_SP` and `PLAN_SP` in `nbs/04_path.ipynb`; the setting `walks.steps` in `nbs/00_learner.ipynb`.

**Each idea keeps `core` and `wrong`.** `core` is the idea in plain words, with no sizes or scores. `wrong` is the list of
wrong ideas that learners often have. An old idea gets them when the learner meets it. Why: the check, the grade and the
feedback all need the idea and its common errors. 2 Nov 2026. `Learning.update` in `nbs/00_learner.ipynb`;
`nbs/02_sources.ipynb`; `nbs/04_path.ipynb`.

**Checks ask for understanding, in plain words.** A check asks the learner to explain, predict, compare, apply the idea to a
new case, or judge a wrong idea. It never asks to recall a fact. It uses the real names. An analogy shows only as "where does
this analogy break?". Why: the owner said that the checks were "so specific" and did not test understanding. 2 Nov 2026.
`FACETS` in `nbs/03_tutor.ipynb`.

**The grade looks for the core idea.** The grade passes the core idea in the learner's own words. Extra points only add. From
depth 4, a pass also needs an edge case or a new case. A recital of the page fails. A slip is not a misconception. A
misconception stays only when it is a known wrong idea or it shows two times. Feedback names the gap. Why: a grade on
keywords passes a copy and fails a real answer. 2 Nov 2026. `grade_prompt` and `Tutor._grade` in `nbs/03_tutor.ipynb`.

**Teach for the level of the learner.** Each teaching prompt gets the shared rules (`teach.human`) and a level line from the
learner model: new, a gap, shaky, fading or solid, the needs that are missing, and the profile. Shaky or a gap: simple, one
idea at a time, a concrete case first, the gap first. Solid: short, with an edge case. Why: the owner said the text was "too
literal" for a human to learn from. 2 Nov 2026. `HUMAN` and `level_line` in `nbs/00_learner.ipynb`.

**Plain English check.** Text that the tutor writes for the learner must be plain English at grade 9. When rupaka's
`plain_why` finds problems, the tutor writes the text again one time. The new text stays only when it is better and keeps the
numbers and the maths. Why: plain words are easier to learn from. Plain words are not literal words. 2 Nov 2026. `plainly`
and the setting `checks.readable` in `nbs/00_learner.ipynb`; `rupaka.agent.plain`.

**Sources and trust.** Each fact that abhyasa shows comes with a source that the learner can see and open. A quote must be
word for word in its source, or abhyasa leaves it out. Text with no source is labelled as the tutor's own words. A missing
source is a visible state. Why: the owner said, "How can I trust the knowledge without seeing the source. That's
fundamental." 29 Oct 2026. `verbatim` in `nbs/02_sources.ipynb`; the research of a walk in `nbs/04_path.ipynb`.

**Research is safe by default.** Each fetch refuses a private address. The research agent reads only the folders of the
sources and its own clones, never a link or a key file. Text that goes out passes `ramabana.guard`. Why: research runs on
the learner's Mac with the learner's files. 30 Oct 2026. `fetch_opts` and `check_url` in `nbs/02_sources.ipynb`; `guard`
in `nbs/01_models.ipynb`.

**A notebook walk uses the notebook as it is.** One idea for each section that teaches, in its own words and code, with a
check. A setup section, such as the imports, is not an idea. Leela opens a learning copy with the demos of the walk. abhyasa
never writes the learner's notebook. Why: the notebook is the learner's own work. 2 to 3 Nov 2026. `notebook_walk` and
`copy_path` in `nbs/04_path.ipynb`; `abhyasa/contract.py`; `abhyasa/core/leela.py`.

**Code runs only in Leela.** Model-written code never runs in abhyasa. A "try" or "code" ask goes to Leela. A 3D explainer is
a JSON scene that rupaka draws, never code. Leela writes results back with `Learning.record`, and it never writes the walk
document. Why: one writer for each walk, and no model code in the web app. 28 Oct 2026. `show` in `nbs/05_show.ipynb`;
`tests/test_leela_api.py` lists the names that Leela imports.

**Follow-up boards build on top.** A follow-up question keeps the board that shows: the old marks stay, the old panel stays
at the top, and the new part comes under it. The guide gets the last 3 questions on the page and forgets them on a new page,
after 10 minutes, or on ×. Why: the learner asks "why?" about what is on the screen. 1 to 3 Nov 2026. `THREAD_RULE` in
`nbs/05_show.ipynb`.

**Pages are calm, with three surfaces.** The page is for reading, raised is for what you do, sunken is for what you look up.
Each main screen has one main button. The accent colour is for primary actions only. Each text colour has a contrast of
4.5:1 or more on each surface, in each theme. Why: the page must stay bookish, not a dashboard. 30 Oct 2026. `--raised`,
`--sunken` and `--lift` in `abhyasa/core/base.css`.

## Architecture

**Six engine notebooks, and no old module names.** The engine is `00_learner`, `01_models`, `02_sources`, `03_tutor`,
`04_path` and `05_show`. Each imports only from the ones above it. The old modules (`abhyasa.store`, `abhyasa.walk`, …) are
gone, with no aliases. A monkeypatch goes on the module whose code looks up the name. Why: a patch through an alias hides
where the code is and breaks with the import order. The owner said, "fix it properly even if leela needs to be changed." 2 Nov
2026. `nbs/`; `tests/test_old_modules.py`.

**The web app is made from blocks and hooks.** A block is a folder in `abhyasa/blocks/` with `cfg.py`, `ui.py`, `app.py` and its
own CSS and JS. A block uses only the capabilities in its `CAPS`. Blocks add to each other's pages through hooks, and a block
never imports another block. Why: each part can change, or go to Leela, on its own. 25 Oct 2026. `abhyasa/blocks/__init__.py`
(`NAMES`); `abhyasa/core/hooks.py`; `tests/test_blocks.py`.

**The board is in rupaka.** The screen guide board (its ops, panel shapes, checks, JS and CSS) comes from `rupaka.board`.
abhyasa and Leela both use it, and abhyasa keeps only the prompt and the page context. Why: one copy for two apps; about 3,400
lines left abhyasa. 2 Nov 2026. `from rupaka.board import …` in `nbs/05_show.ipynb` and `abhyasa/core/ui.py`.

**rishi is the model broker, and ramabana is the agent layer.** Each model call goes through ramabana (routing, fallback,
set-aside of a model that fails, the PII guard, cost). rishi does the calls. abhyasa does not call `make_backend` by itself.
The research of a walk is a ramabana agent with sub-agents. Why: routing and fallback in one place, and tools later. 31 Oct to
2 Nov 2026. `ramabana_lead` and `guard` in `nbs/01_models.ipynb`; the floors in `pyproject.toml`.

**Use the packages, and patch them upstream.** Before you write a helper, look for one with kosha. A gap gets a small upstream
patch and a release; then abhyasa raises its floor. abhyasa keeps only the learning logic and the UI. Why: the packages are
tested, and copies drift. 30 Oct to 1 Nov 2026. `pyproject.toml`; `tests/test_deps.py`.

**Each job has Stop and Do it again.** Each background job (a demo, a 3D explainer, a walk, a change from the walk box, Make
this walk again, a notebook, a course plan, a talk, research, a model download) is a stored row. Stop ends it at its next safe
point, and a result that comes after Stop does not stay. Why: the ledger has no stop ask, so abhyasa keeps a halt mark on the
row. 3 Nov 2026. `job_start`, `job_end`, `stop_job` and `halted` in `nbs/00_learner.ipynb`.

## Voices

**Pocket TTS, OpenAI and the browser. No Kokoro.** The voices are Pocket TTS on this Mac (voice `caro_davy`), OpenAI (hosted,
needs a key) and the browser. An old `kokoro` or `hf` setting speaks with Pocket TTS. Speech to text on this Mac is Qwen3-ASR,
with Whisper second. Do not add Kokoro or another local voice again without the owner. Why: fewer engines, and no GPL parts
(Kokoro's phonemizer and espeak-ng). 2 Nov 2026. `OUT_ENGINES` and `OUT_DFLT` in `nbs/01_models.ipynb`; the `voice` extra in
`pyproject.toml`.

## Release

**Release order.** Write the CHANGELOG entry by hand, `nbdev-prepare`, push, and check that CI and Pages pass. Then
`nbdev-release-git` and `nbdev-pypi`. `nbdev-release-git` does not mark the release Latest, so mark it on GitHub
(`gh api -X PATCH repos/<owner>/abhyasa/releases/<id> -f make_latest=true`). Never `nbdev-release-gh`. Why: hand-written
notes, and GitHub showed an old release as Latest. 3 Nov 2026. `CLAUDE.md`; `CHANGELOG.md`.

**The real-data crawl is a release gate.** Before a release, run the app on a copy of the real vault and settings, GET each
page route with real ids, do the main actions, and look at the server log and the browser console. Check that the Mac pin has
each extra that a feature needs. Why: 0.0.15 had a Sources 500 and a missing `voice` extra that tests on a temporary vault did
not find. 31 Oct 2026. [develop.md](develop.md); `mac/Resources/Pin/pyproject.toml`.

**Check the docs build before a push.** Run `uv run --frozen nbdev-proc-nbs --force`. Pages runs only the cells with an
import, `#| export` or `show_doc`, so a test cell must have its imports in a cell of their own. Plain `nbdev-docs` can pass on
an old `_proc`. Why: CI passed while Pages failed in 0.0.16. 3 Nov 2026. `nbs/`.

**Order across repos.** Release rupaka first, then abhyasa, then Leela, then the Mac app (`make ship V=<version>` after the pin
and `make lock`). Why: each one pins the one before it. 2 Nov 2026. [develop.md](develop.md).

## Testing

**Never use the real vault.** Tests use `temp_learning()`. A manual test runs on a copy in `/tmp`. A copied `vault.db` still
points at the real `.usearch` index files, so copy them too and change their paths in the copy first. Why: a test must not
change the learner's data. 31 Oct 2026. `temp_learning` in `nbs/00_learner.ipynb`; [develop.md](develop.md).

**Browser checks use a test browser only.** Use Playwright's bundled Chromium, or `$FASTCDP_CHROME`. Never the owner's Chrome,
port 9223 or `~/.cache/fastcdp/cdp-chrome`. One browser at a time, closed in a `finally`. Do not run a test that takes the
focus while the owner works. Why: the owner works on the same Mac. 25 Oct 2026. `CLAUDE.md`.

**Model calls stay out of CI.** Tests use fake models. The eval with real models (`tools/eval_understanding.py`) is opt-in and
runs on a vault copy, before and after a change to the chain from idea to feedback. Why: real calls cost money and change from
run to run. 2 Nov 2026. `tools/eval_understanding.py`.
