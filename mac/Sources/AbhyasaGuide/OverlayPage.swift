import Foundation
import CoreGraphics

/// The page in each overlay panel. It loads board.js and its styles from the abhyasa server (`/assets/<name>` and `/vendor/`),
/// so the overlay draws with the same code as the pages. Swift puts one empty box for each anchor on the page, at the anchor's
/// place in the panel's points, so board.js finds each anchor with its default `resolve`. The voice goes to Swift
/// (AVSpeechSynthesizer, with word marks). The page shows no text from the model except through board.js, which uses
/// textContent only.
public enum OverlayPage {
    /// one anchor box on the page, in CSS pixels of the panel (top left origin)
    public struct Box: Equatable, Encodable, Sendable {
        public var id: String
        public var x, y, w, h: Double
        public init(id: String, rect: CGRect) {
            self.id = id
            x = Double(rect.minX); y = Double(rect.minY); w = Double(rect.width); h = Double(rect.height)
        }
    }

    /// the boxes of `anchors` (CG global frames) in the panel of `display`
    public static func boxes(_ anchors: [Anchor], display: Display, mainHeight: CGFloat) -> [Box] {
        anchors.map { Box(id: $0.id, rect: Geometry.panel(fromCG: $0.frame, display: display, mainHeight: mainHeight)) }
    }

    /// a JSON value as JavaScript source text; nil when it cannot be encoded
    public static func js<T: Encodable>(_ v: T) -> String? {
        let e = JSONEncoder()
        e.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        guard let d = try? e.encode(v) else { return nil }
        // U+2028 and U+2029 end a line in older JavaScript; JSON allows them in strings
        return String(decoding: d, as: UTF8.self).replacingOccurrences(of: "\u{2028}", with: "\\u2028")
            .replacingOccurrences(of: "\u{2029}", with: "\\u2029")
    }

    /// seconds that a board stays on the screen after its last line, then it goes
    public static let linger = 8.0

    public static let html = """
    <!doctype html>
    <html><head><meta charset="utf-8">
    <link rel="stylesheet" href="/assets/base.css"><link rel="stylesheet" href="/assets/themes.css">
    <link rel="stylesheet" href="/assets/board.css">
    <style>
    html, body { background: transparent !important; margin: 0; padding: 0; width: 100vw; height: 100vh; overflow: hidden; }
    body { color-scheme: light dark; }
    #anchors > div { position: absolute; pointer-events: none; }
    #guide-strip { left: 50%; right: auto; bottom: 48px; transform: translateX(-50%); width: min(640px, 90vw); border-radius: 12px;
                   border: 1px solid color-mix(in srgb, var(--fg, #222) 12%, transparent); }
    #guide-strip .board-keys { display: none; }
    #guide-strip:not([hidden])::after { content: "\(GuideText.keys)"; display: block; font-size: var(--t-meta, 14px); color: var(--mute, #777); }
    </style>
    <script src="/assets/board.js"></script>
    </head><body><div id="anchors"></div><script>
    (() => {
      const post = m => { try { webkit.messageHandlers.guide.postMessage(m); } catch (e) {} };
      const voices = {};
      let nv = 0, live = null, gen = 0, linger = null;
      const calm = () => { if (linger) { clearTimeout(linger); linger = null; } };
      const host = {
        speak(text, onWord, done) {
          calm();
          const id = ++nv;
          voices[id] = {onWord, done: () => {
            done();
            const s = window.abhyasaBoard && abhyasaBoard.state;   // the last line of a whole board: it goes after a short time
            if (s && !s.streaming && s.i === s.steps - 1) {   // Swift shows a quiet countdown; a key or a move keeps the board
              linger = setTimeout(() => abhyasaBoard.stop(), \(Int(linger * 1000)));
              post({op: 'linger', ms: \(Int(linger * 1000))});
            }
          }};
          post({op: 'speak', id, text: String(text)});
          return () => { delete voices[id]; post({op: 'hush', id}); };
        },
        demo() {},   // no demo in another app
        assets: '/vendor/'
      };
      let point;   // the look of a point mark: the setting guide.point, from the step and board events of the server
      const opts = () => ({host, labels: {}, point});
      window.overlay = {
        anchors(list) {
          document.getElementById('anchors').replaceChildren(...list.map(a => {
            const d = document.createElement('div');
            d.dataset.guideId = a.id;
            Object.assign(d.style, {left: a.x + 'px', top: a.y + 'px', width: a.w + 'px', height: a.h + 'px'});
            return d;
          }));
        },
        move(dx, dy) {   // the window moved: each anchor moves with it, and board.js draws again
          for (const d of document.querySelectorAll('#anchors > div')) {
            d.style.left = (parseFloat(d.style.left) + dx) + 'px'; d.style.top = (parseFloat(d.style.top) + dy) + 'px';
          }
          dispatchEvent(new Event('resize'));
        },
        // show while you talk: a faint trail of the pointer and a soft ring on a gesture, in the board.css styles of the page guide
        trail(pts) {   // a canvas, in the ink of board.css; with reduced motion only the rings show
          let t = document.getElementById('board-trail');
          if (!t) {
            t = Object.assign(document.createElement('div'), {id: 'board-trail'});
            const c = document.createElement('canvas');
            Object.assign(c.style, {position: 'absolute', left: 0, top: 0, color: 'var(--board-ink)'});
            t.append(c); document.body.append(t);
          }
          const c = t.querySelector('canvas'), k = devicePixelRatio || 1, w = innerWidth, h = innerHeight;
          if (c.width !== Math.round(w * k)) { c.width = Math.round(w * k); c.height = Math.round(h * k); c.style.width = w + 'px'; c.style.height = h + 'px'; }
          const g = c.getContext('2d');
          g.setTransform(k, 0, 0, k, 0, 0); g.clearRect(0, 0, w, h);
          if (pts.length < 2 || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
          Object.assign(g, {strokeStyle: getComputedStyle(c).color, globalAlpha: .35, lineWidth: 2.5, lineCap: 'round', lineJoin: 'round'});
          g.beginPath(); pts.forEach((p, i) => i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1])); g.stroke();
        },
        ring(b, point) {
          if (!document.getElementById('board-trail')) overlay.trail([]);
          const r = Object.assign(document.createElement('div'), {className: 'board-trail-ring' + (point ? ' point' : '')}), pad = point ? 6 : 8;
          Object.assign(r.style, {left: b[0] - pad + 'px', top: b[1] - pad + 'px', width: b[2] - b[0] + 2 * pad + 'px', height: b[3] - b[1] + 2 * pad + 'px'});
          document.getElementById('board-trail').append(r);
          setTimeout(() => r.remove(), \(Int(Gestures.fadeMs)));
        },
        endTrail() { const t = document.getElementById('board-trail'); if (t) t.remove(); },
        word(id, k) { const v = voices[id]; if (v) v.onWord(k); },
        done(id) { const v = voices[id]; delete voices[id]; if (v) v.done(); },
        begin() { gen++; live = null; calm(); },
        note(t) { if (window.abhyasaBoard) abhyasaBoard.note(t); },
        again() { calm(); if (window.abhyasaBoard) abhyasaBoard.again(); },
        keep() { calm(); },   // the learner moved or pushed a key in the countdown: the board stays until Stop
        stop() { calm(); if (window.abhyasaBoard) abhyasaBoard.stop(); },
        // one event of the ask route, as guide.js plays it: the first step starts a streaming board, each next step is added,
        // and the board at the end finishes the streaming board, or plays as it is when no step came
        async event(m) {
          const n = gen;
          if (typeof m.point === 'string') point = m.point;
          if (m.wait) return abhyasaBoard.note(m.wait);
          if (m.error) return abhyasaBoard.note(m.error);
          if (m.step && !live) live = abhyasaBoard.play({steps: [m.step], tier: m.tier || 'tutor', sources: [], streaming: true}, opts());
          else if (m.step) live = live.then(() => n === gen && abhyasaBoard.add(m.step));
          if (m.board) {
            if (!live) return abhyasaBoard.play(m.board, opts());
            await live;
            const b = abhyasaBoard.state;
            if (n === gen && b && b.streaming && !abhyasaBoard.finish(m.board)) await abhyasaBoard.play(m.board, opts());
          }
        }
      };
      document.addEventListener('board:stop', () => { calm(); post({op: 'stop'}); });
      document.addEventListener('board:first', () => post({op: 'first'}));
      post({op: 'ready', board: !!window.abhyasaBoard});
    })();
    </script></body></html>
    """
}
