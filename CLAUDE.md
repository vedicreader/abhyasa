# Working in this repo

nbdev 3 on hatchling. Two kinds of code live here:

- The engine (`store`, `model`, `llm`, `tutor`, `sources`, `voice`, `ground`, `nb`, `demo`, `journey`, `profile`, `method`, `research`, `detect`, `edit`): the notebooks under `nbs/` are the
  source, and `abhyasa/*.py` is generated. Edit the notebook. Run `uv run nbdev-prepare` (with a hyphen). Never edit a generated file.
- The web app (`abhyasa/app.py`, `abhyasa/core/`, `abhyasa/blocks/`): plain Python written by hand, tested with `uv run pytest`.

## Blocks

The web app is made from blocks, as in lego, leela and vedicreader. A block is a folder in `abhyasa/blocks/` with `cfg.py`
(`Routes`), `ui.py` (FT pieces), `app.py` (`CAPS` and `connect(app, ctx)`), and its own `.css` and `.js`.

- `NAMES` in `blocks/__init__.py` sets the connect order. `tests/test_blocks.py` checks that it matches the folders.
- A block uses only the capabilities in its `CAPS`. `Ctx` refuses the others by name.
- Blocks add to each other's pages through hooks (`core/hooks.py`): `today_top`, `today_next`, `today`, `today_end`, `concept_actions`,
  `concept_more`, `answer_tools`, `lesson_extra`, `nav_extra`, `page_extra`.
  A block never imports another block.
- `connect` registers every route in one place at its end, so one read shows the whole route surface.
- Shared style is in `core/base.css`. Block style is in the block's own `.css`. htmx, KaTeX and d3 are in
  `core/vendor`, and fonts in `core/fonts`, so the app works offline.

## Rules

- Before you write a helper, look for one in the dependencies with kosha (`kosha context "<what you need>"`,
  `kosha public-api <pkg>`). abhyasa stands on ramabana (agents, routing, PII guards), rishi (the model broker),
  fossick (fetch, search, clones, YouTube), shalya (agent tools), vishalakshi (the vault), gheasy (git), rupaka
  (demos), fastcore and FastHTML. Use their primitives. Write your own only when kosha shows none, and say so in the
  commit message.

- Never open the user's real vault (`~/.vishalakshi/vault.db`) in tests. Use `temp_learning()`.
- Browser checks use Playwright's bundled Chromium (`p.chromium.launch(headless=True)`, no `executable_path`), or `$FASTCDP_CHROME`
  for fastcdp. Never automate `/Applications/Google Chrome.app`, port 9223 or `~/.cache/fastcdp/cdp-chrome`: they are the
  user's own browsers. Run one browser at a time and close it in a `finally`.
- Prose (notebooks, docs, UI text, commit messages, release notes) is ASD-STE100 Simplified Technical English, US grade 9.
- Notebooks read as documents: an intro, short sections, a one-line lead before each code cell, small cells, tests in small
  steps with a line on what each checks.
- Commit messages are one plain line, with no AI credit.
- Release: write the CHANGELOG entry, `nbdev-prepare`, push, check that CI passes, then `nbdev-release-git` and `nbdev-pypi`.
  Never `nbdev-release-gh`.
