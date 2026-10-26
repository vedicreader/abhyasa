# Abhyasa for Mac

Abhyasa.app is a SwiftUI window with a web view on the abhyasa server. The app starts the server, and it stops the
server when you quit. It is for macOS 26 on Apple Silicon.

## How it works

The bundle holds a small pinned project (`Contents/Resources/Pin`). The only dependency of the project is
`abhyasa[whisper,tick]==0.0.2` from PyPI, and `uv.lock` locks all of its packages. The app does not hold a copy of uv.
It uses the uv from Homebrew: the cask has `depends_on formula: "uv"`. The app looks for uv in `/opt/homebrew/bin`,
then `/usr/local/bin`, then `~/.local/bin`, then the folders in `PATH`. If it finds no uv, it shows
`brew install uv`, a Copy button and a Retry button.

1. The app copies the pinned project to `~/Library/Application Support/abhyasa/project`.
2. When the hash of `pyproject.toml` and `uv.lock` is different from the hash of the last good sync, the app runs
   `uv sync --frozen`. uv gets Python 3.12 and the packages into `~/Library/Application Support/abhyasa/env`. This step
   needs the internet one time. The first-run screen shows the last line that uv writes.
3. The app gets a free port on 127.0.0.1 and starts `abhyasa --port <port> --vault <vault>`.
4. The app waits until `/health` is ok, then loads the page.
5. If the server stops by itself, the app shows the last lines of its log and a "Start Again" button.

A GUI app does not get the shell environment, so the app sets the environment of the server. `PATH` starts with the
environment's `bin`, then `~/.local/bin`, `/opt/homebrew/bin`, `/usr/local/bin` and the system folders. The default
model, `claude/sonnet`, uses the `claude` command, so `claude` must be in one of these folders.

The logs are `server.log` and `sync.log` in `~/Library/Application Support/abhyasa`.

## Settings

Open Abhyasa > Settings (Command-comma). Apply saves the values and starts the server again.

| setting | variable | default |
|---|---|---|
| Model | `ABHYASA_MODEL` | `claude/sonnet` (the server default) |
| Speech engine | `ABHYASA_STT` | `gemma` |
| Vault | `--vault` and `ABHYASA_VAULT` | `~/.vishalakshi/vault.db` |

The `whisper` extra installs `mlx-audio` for the whisper engine, and the `tick` extra installs `pobblebonk`.

## Native parts

- Microphone: `NSMicrophoneUsageDescription`, the `audio-input` entitlement, and a `WKUIDelegate` that gives the
  microphone only to `http://127.0.0.1:<the server port>`.
- Keys: no menu item uses Option and a letter, so Option-D, Option-S and Option-W go to the page.
- Menu: File > New Session (Command-N), and Go > Today, Graph, Search (Command-F) and Add a Source.
- Dock badge: the number of due reviews, from `/due.json`, each 5 minutes and after each page load. abhyasa 0.0.2 does
  not have `/due.json`, so the badge shows after the next release of the Python package.
- Links: `abhyasa://concept/<slug>` opens the page of that concept. `abhyasa://` and `abhyasa://today` open Today.
  Links to other sites open in your browser.

## Build

```sh
make test     # the Swift tests; they do not open a window
make build    # swift build
make app      # the bundle in build/Abhyasa.app, signed with SIGN_ID (default "Apple Development")
make verify   # checks the bundle and its signature, without opening it
make run      # opens the app
```

`make lock` uses `UV` (default `/opt/homebrew/bin/uv`). To build and run the app, install uv first: `brew install uv`.

To change the abhyasa version, edit the pin in `Resources/Pin/pyproject.toml`, run `make lock`, then bump
`CFBundleShortVersionString` in `Resources/Info.plist`.

## Release

The release targets are the same as Sanketa's. `make release` signs with the Developer ID, notarizes and staples.
`make publish` makes the GitHub release `mac-v<version>`. `make cask` copies `cask/abhyasa.rb` into `Casks/` in `TAP`
(default `../../homebrew-tap`) if it is not there, then writes the version and hash into it. It does not commit or
push. The cask depends on the `uv` formula. `make -n` and `make -i` do not run `release` or `publish`.
