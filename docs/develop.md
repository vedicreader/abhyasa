# Develop

This page tells you how to test and release abhyasa. The rules are in [CLAUDE.md](../CLAUDE.md). The decisions are in
[decisions.md](decisions.md).

## Tests

```sh
uv run --frozen nbdev-prepare          # export, test the notebooks, clean
uv run --frozen pytest -q              # the web app
uv run --frozen nbdev-proc-nbs --force # the cells that the Pages build runs
```

## A test server on a copy of your vault

Never open `~/.vishalakshi/vault.db`. The launcher `~/code/personal/orgs/abhyasa-designs/try.py` copies the vault, its
`.usearch` index files and your settings to `/tmp/abhyasa-try`, and changes the index paths in the copy. Then it starts
abhyasa on the copy, and a test Leela beside it.

```sh
uv run --project ~/code/personal/orgs/abhyasa python ~/code/personal/orgs/abhyasa-designs/try.py
```

- abhyasa is at <http://127.0.0.1:5110>, and the test Leela at <http://127.0.0.1:5111>. Ctrl+C stops both.
- `TRY_KEEP=1` keeps the copy from the last run. `TRY_SRC=<folder>` runs another checkout. `TRY_WITH=<folder>:<folder>` adds
  packages that are not released, such as a rupaka branch. `TRY_LEELA_SRC=<folder>` picks the Leela checkout.
- `TRY_DIR` and `TRY_PORT` change the folder and the port. Use them to run a second server.

## The eval of understanding

`tools/eval_understanding.py` scores the chain from idea to check to grade to feedback on 20 fixed steps. It calls real models
(about 125 calls), so CI never runs it. Run it on a vault copy before and after a change to a prompt of that chain, and
compare the two results:

```sh
uv run python tools/eval_understanding.py --vault /tmp/abhyasa-try/vault/vault.db --out /tmp/eval-before
uv run python tools/eval_understanding.py --table /tmp/eval-before.json /tmp/eval-after.json
```

The first run builds a book walk from `--book` (a Project Gutenberg text). `--only 3` makes a short smoke run.

## The crawl gate

Do this before each release, on a fresh copy from `try.py`:

1. GET each route of each block (`Routes` in each `cfg.py`) and of core, with real ids from the copy. Then GET the internal
   links on those pages. Each status must be 200, or a correct 400, 403, 404 or 405.
2. Open the main pages in Playwright's bundled Chromium. The console must show no errors and no failed requests.
3. Do the main actions: answer a check, ask the screen guide, change a walk from its box and Undo, Stop a job, open in Leela,
   and delete a walk on the copy.
4. Read the server log: no 500 and no traceback.
5. Check `mac/Resources/Pin/pyproject.toml`: the new version, and each extra that a feature needs (`voice`, `whisper`).

The small Playwright drivers in `~/code/personal/orgs/abhyasa-designs/tools/` help with steps 2 and 3.

## Release

1. Write the CHANGELOG entry by hand. Run `nbdev-prepare`, push, and check that CI and Pages pass.
2. Do the crawl gate.
3. `uv run nbdev-release-git`, then `uv run nbdev-pypi`. Mark the new release Latest on GitHub
   (`gh api -X PATCH repos/<owner>/abhyasa/releases/<id> -f make_latest=true`). Never `nbdev-release-gh`.
4. `uv run nbdev-bump-version`, and commit the start of the next version.

The order across repos: rupaka first, then abhyasa (after `uv lock --upgrade-package rupaka`), then Leela (it pins abhyasa
and rupaka), then the Mac app: set the pin, `make lock`, then `make ship V=<version>` in `mac/`.
