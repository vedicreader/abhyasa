# Abhyasa for Mac

Abhyasa.app is a SwiftUI window with a web view of the abhyasa server. The app starts the server. It stops the server
when you quit. It is for macOS 26 on Apple Silicon.

## How it works

The bundle holds a small pinned project (`Contents/Resources/Pin`). The only dependency of the project is
`abhyasa[whisper,tick]==0.0.2` from PyPI, and `uv.lock` locks all of its packages. The app does not hold a copy of uv.
It uses the uv from Homebrew: the cask has `depends_on formula: "uv"`. The app looks for uv in `/opt/homebrew/bin`,
then `/usr/local/bin`, then `~/.local/bin`, then the folders in `PATH`. If it finds no uv, it shows
`brew install uv`, a Copy button and a Retry button.

1. The app copies the pinned project to `~/Library/Application Support/abhyasa/project`.
2. The app compares the hash of `pyproject.toml` and `uv.lock` with the hash of the last good sync. When they are
   different, the app runs `uv sync --frozen`. uv puts Python 3.12 and the packages into
   `~/Library/Application Support/abhyasa/env`. This step needs the internet one time. The first-run screen shows the
   last line that uv writes.
3. The app gets a free port on 127.0.0.1 and starts `abhyasa --port <port> --vault <vault>`.
4. The app waits until `/health` is ok, then loads the page.
5. If the server stops by itself, the app shows the last lines of its log and a "Start Again" button.

A GUI app does not get the shell environment, so the app sets the environment of the server. `PATH` starts with the
environment's `bin`, then `~/.local/bin`, `/opt/homebrew/bin`, `/usr/local/bin` and the system folders. The default
model, Claude Sonnet (`claude/sonnet`), uses the `claude` command. Thus `claude` must be in one of these folders.

The logs are `server.log` and `sync.log` in `~/Library/Application Support/abhyasa`.

## Settings

Open Abhyasa > Settings (Command-comma). Apply saves the values and starts the server again. You choose the model
from a list of names. The last item, "Type another model id", shows a text box for an id that the list does not have.
The Settings page of the web app can set a different model for each tutor task.
It can also change the prompts of the tutor: the rules, the hint ladder and the text of each way to teach.
A change works on the next question. "Use the default" goes back to the text that comes with abhyasa.

| setting | variable | default |
|---|---|---|
| Model | `ABHYASA_MODEL` (the model id) | Claude Sonnet, `claude/sonnet` (the server default) |
| Speech engine | `ABHYASA_STT` | `gemma` |
| Vault | `--vault` and `ABHYASA_VAULT` | your vault, `~/.vishalakshi/vault.db` |

The `whisper` extra installs `mlx-audio` for the whisper engine, and the `tick` extra installs `pobblebonk`.

## Native parts

- Microphone: `NSMicrophoneUsageDescription`, the `audio-input` entitlement, and a `WKUIDelegate` that gives the
  microphone only to `http://127.0.0.1:<the server port>`.
- Keys: no menu item uses Option and a letter, so Option-D, Option-S and Option-W go to the page.
- Menu: File > New Session (Command-N), and Go > Today, Graph, Search (Command-F) and Add a Source.
- Dock badge: the number of due reviews, from `/due.json`. The app reads it each 5 minutes and after each page load.
  abhyasa 0.0.2 does not have `/due.json`. Thus the badge shows after the next release of the Python package.
- Links: `abhyasa://concept/<slug>` opens the page of that concept. `abhyasa://vault/<shelf>/<doc_id>` opens that
  document of your vault. `abhyasa://` and `abhyasa://today` open Today. Links to other sites open in your browser.
  A shelf or a document id has only letters, digits, `-`, `_` and `.`, and it is not only dots.

## The screen guide over other apps

The `AbhyasaGuide` target draws the guide's board over any app. The abhyasa server is the brain. The app only reads the
window, asks the server and draws.

- Off until Start: a fresh install holds no key and no mouse monitor. To turn on the guide, use the switch in Settings or the
  Abhyasa mark in the menu bar. The first time, a sheet shows in the strip. It says what the guide reads (the title and the
  visible text of the window in front, through Accessibility; a picture only when the vision setting is on), which model gets
  it (hosted or on this Mac), what the key does, and how to turn the guide off. The guide starts only when you push Start. The
  sheet never shows by itself at launch. The 0.0.14 switch (`guide`, on by default) is not used.
- Key: Caps+E. Caps Lock is Hyper (⌃⌥⇧⌘), so the hot key is ⌃⌥⇧⌘E, the same key as the page guide. A tap opens a small strip at
  the top of the screen, where you type your question. A hold opens the mic; the release sends what you said to `/voice/stt`.
  The words that come back stay in the strip's box: change them if you need to, then push Return to send them.
  While a board shows, a tap says the step again, and `Esc` stops the board. The app takes `Esc` only while a board shows. The
  key is a Carbon hot key, so it needs no permission. Over Abhyasa's own window, the key opens the page's own guide box.
- Follow-up questions: the guide keeps your last 3 questions over the window in front, with the lines of their boards, in memory
  only. It sends them with the next question, and the strip shows "Follows up on: <your last question>" with × (Start fresh).
  It forgets them when the window changes (the app or the window title), after 10 minutes with no question, or with ×.
- Signs: at key down, before the read, the strip says "The guide reads this window." Then it says what it read ("Reads Safari:
  the window title and 38 parts with text."). Before the request goes, it says what leaves the Mac and to which model, with a
  chip: `on this Mac`, or `hosted · Anthropic`. While the mic is on, a level moves, and a chip tells where speech to text runs
  (`speech: on this Mac` for Gemma and Whisper, `speech: hosted · OpenAI` for OpenAI). While the pointer trail is on, the strip
  says "The guide follows your pointer while you ask."
- The menu bar mark follows the state: off, ready, listening, writing what you said, reading, asking, searching, saving and
  drawing. It is a small template glyph with no animation. Its menu has the state line, Stop, Voice off, Turn off the guide
  (or Turn on the guide) and Settings.
- The server's state events: a `wait` event can have `state`, `model`, `where`, `who`, `query` and `sources`. The strip shows
  the line with its chip, and the web query word for word. A `saved` event shows "Saved to your vault: <title>." with Undo,
  which posts to the route of the event (a path on the server only). Each field is optional, so an older server works too.
- Anchors: the app reads the window in front with the Accessibility API: the window, the thing under the pointer, the
  selected text and up to 40 visible parts with text. Each read has a timeout of 0.5 s, and the whole read stops after
  0.35 s or 600 parts. It runs on its own queue, not on the main thread. Password fields and fields with a name like a key
  or a token are left out. The app does not read Keychain Access, 1Password, Bitwarden, Passwords, Messages, Mail, Signal,
  WhatsApp or System Settings.
- With no Accessibility permission, the guide uses the window frame only, and the strip says so. The first time, the strip
  asks if you want to open System Settings. The app never asks for a permission at launch.
- The question goes to `/guide/ask` as `{"said", "ctx"}`. `ctx.title` is the app name and the window title, and
  `ctx.anchors` is the anchor list. The app reads the server-sent events (`wait`, `step`, `board`, `error`).
- Show while you talk: while you hold the key, or while the strip is open, you can circle a part with the mouse or hold the
  pointer still on it. A global monitor of mouse moves keeps the path in memory only while the guide asks (30 points a
  second, the last 15 s). A faint trail and a soft ring show in the overlay panel. The question sends the gestures as
  `ctx.focus`, with the anchors under each one. The rules are in `Gestures.swift`, the same as the page guide, and both test
  against `tests/data/gesture_paths.json`. The monitor uses no new permission.
- The board plays in a clear, click-through panel over the display of the window. The panel never takes the focus. Its web
  view loads `board.js` from the server, and the app puts one empty box on the page for each anchor. The voice is
  `AVSpeechSynthesizer`, with a mark for each word. Voice off mutes it at once, and the board keeps its time. The marks move
  when the window moves. When the first mark shows, the strip becomes the board strip: the model and where it runs, Stop and
  Voice off. The board goes 8 s after its last line. A thin line counts the 8 s; a key or a move of the pointer in that time
  keeps the board until Stop or Esc. The app watches keys and moves only in these 8 s.
- A picture of the window (ScreenCaptureKit, one window only, in memory only) is in the code, behind the `guide.vision`
  setting, which is off. It never asks for Screen Recording. The server does not take a picture yet.
- Settings has a switch for the guide. It is off by default.

## Build

```sh
make test     # the Swift tests; they do not open a window
make build    # swift build
make app      # the bundle in build/Abhyasa.app, signed with SIGN_ID (default "Apple Development")
make verify   # checks the bundle and its signature, without opening it
make run      # opens the app
```

`make lock` uses `UV` (default `/opt/homebrew/bin/uv`). To build and run the app, first install uv with `brew install uv`.

To change the abhyasa version, do these steps:

1. Edit the pin in `Resources/Pin/pyproject.toml`.
2. Run `make lock`.
3. Increase `CFBundleShortVersionString` in `Resources/Info.plist`.

## Release

The release targets are the same as Sanketa's. `make release` signs with the Developer ID, notarizes and staples.
`make publish` makes the GitHub release `mac-v<version>`. `make cask` copies `cask/abhyasa.rb` into `Casks/` in `TAP`
(default `../../homebrew-tap`), if the file is not there. Then it writes the version and the hash into the file. It does
not commit or push. The cask depends on the `uv` formula. `make -n` and `make -i` do not run `release`, `publish` or `ship`.

`make ship V=<version>` does all of a release in one step. It sets the abhyasa pin and the app version to V, runs
`make lock`, `make publish` and `make cask`, commits the tap and abhyasa, and pushes both. It stops when V is empty, or when
abhyasa or the tap has changes that are not committed. Before it changes a file, it waits up to 10 minutes for abhyasa V on
PyPI, and stops if it does not come. The script is `scripts/ship.sh`. When a step fails before the commits, it puts
the files back as they were. A second run skips a release that is on GitHub already, so `make ship V=<version>` can always run again.
