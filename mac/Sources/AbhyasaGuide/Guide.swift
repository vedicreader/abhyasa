import AppKit
import AbhyasaCore

/// The screen guide over other apps (design phase 2). ⌥` reads the window in front, opens the strip, sends the question with
/// the anchors to the server's `/guide/ask`, and plays the board in the overlay over that window. The server is the brain;
/// this class only reads, asks and draws. It asks for no permission at launch.
@MainActor
public final class Guide {
    public static let shared = Guide()
    static let enabledKey = "guide", askedAccessKey = "guide.askedAccess"

    public let overlay = Overlay()
    public let strip = Strip()
    let speaker = Speaker()
    let recorder = Recorder()
    let keys = HotKeys()
    var machine = KeyMachine()
    var client: GuideClient?
    var reading: Task<Snapshot, Never>?
    var snapshot: Snapshot?
    var asking: Task<Void, Never>?
    var follow: Timer?
    var holdTimer: Timer?
    var boardShows = false { didSet { keys.escape(KeyMachine.wantsEscape(boardShows: boardShows)) } }
    /// a press of the key while Abhyasa's own window is in front: the page has its own guide (Hyper+E), so it opens that
    public var ownApp: (() -> Void)?

    /// the learner's switch in Settings; on by default
    public static var enabled: Bool {
        get { UserDefaults.standard.object(forKey: enabledKey) as? Bool ?? true }
        set { UserDefaults.standard.set(newValue, forKey: enabledKey) }
    }

    init() {
        keys.onDown = { [weak self] in self?.down() }
        keys.onUp = { [weak self] in self?.up() }
        keys.onEscape = { [weak self] in self?.act(self?.machine.escape(boardShows: self?.boardShows ?? false) ?? []) }
        overlay.onSpeak = { [weak self] id, t in self?.speaker.speak(id, t) }
        overlay.onHush = { [weak self] id in self?.speaker.hush(id) }
        overlay.onStop = { [weak self] in self?.boardStopped() }
        speaker.onWord = { [weak self] id, k in self?.overlay.word(id, k) }
        speaker.onDone = { [weak self] id in self?.overlay.done(id) }
        strip.model.onSend = { [weak self] t in self?.send(t) }
        strip.model.onClose = { [weak self] in self?.strip.hide() }
        strip.model.onSheet = { [weak self] yes in self?.answerSheet(yes) }
    }

    /// the server is ready on `port`: the key works from now on (when the guide is on)
    public func start(port: Int) {
        let base = Port.base(port)
        client = GuideClient(base: base)
        overlay.base = base
        if Self.enabled { keys.register() } else { keys.unregister() }
    }

    public func setEnabled(_ on: Bool) {
        Self.enabled = on
        if on, client != nil { keys.register() } else { stop() }
    }

    public func stop() {
        asking?.cancel()
        keys.unregister()
        overlay.stop()
        overlay.hide()
        strip.hide()
        boardShows = false
    }

    // --- the key -----------------------------------------------------------------------------------------------------------
    var clock: Double { ProcessInfo.processInfo.systemUptime }

    func down() {
        let acts = machine.down(clock)
        if !acts.isEmpty, !boardShows { read() }   // read the window now, before the strip can take the key window
        act(acts)
    }

    func up() { act(machine.up(clock, boardShows: boardShows)) }

    func act(_ acts: [KeyMachine.Action]) {
        for a in acts {
            switch a {
            case .armTimer(let s):
                holdTimer?.invalidate()
                holdTimer = Timer.scheduledTimer(withTimeInterval: s, repeats: false) { [weak self] _ in
                    MainActor.assumeIsolated { guard let self else { return }; self.act(self.machine.tick(self.clock)) }
                }
            case .open: open(talk: false)
            case .startTalk: open(talk: true)
            case .endTalk: endTalk()
            case .again: overlay.again()
            case .stop: overlay.stop()
            }
        }
    }

    var frontIsMe: Bool { NSWorkspace.shared.frontmostApplication?.processIdentifier == ProcessInfo.processInfo.processIdentifier }

    /// reads the front app on the AX queue; the question waits for it
    func read() {
        guard let app = NSWorkspace.shared.frontmostApplication, !frontIsMe else { reading = nil; return }
        let m = NSEvent.mouseLocation, h = Geometry.mainHeight(Display.all)
        let pointer = CGPoint(x: m.x, y: h - m.y)
        let pid = app.processIdentifier, name = app.localizedName ?? "this app", bundle = app.bundleIdentifier ?? ""
        snapshot = nil
        reading = Task { await AXReader.read(pid: pid, app: name, bundle: bundle, pointer: pointer) }
    }

    func visibleFrame() -> CGRect {
        let main = Display.all
        if let w = snapshot?.window, let d = Geometry.display(for: Geometry.appKit(fromCG: w.frame, mainHeight: Geometry.mainHeight(main)), in: main),
           let s = NSScreen.screens.first(where: { $0.frame == d.frame }) { return s.visibleFrame }
        return (NSScreen.main ?? NSScreen.screens.first)?.visibleFrame ?? .zero
    }

    func open(talk: Bool) {
        if frontIsMe { ownApp?(); return }
        guard client != nil else { return }
        Task {
            if let r = reading { snapshot = await r.value }
            let first = firstUseSheet()
            let line = talk ? GuideText.micOn : limitLine()
            strip.show(line: line, typing: !talk, in: visibleFrame())
            strip.sheet(first)
            if talk { await startTalk() }
        }
    }

    // --- voice in ----------------------------------------------------------------------------------------------------------
    func startTalk() async {
        guard await Recorder.allowed() else { strip.show(line: GuideText.noMic, typing: true, in: visibleFrame()); return }
        guard machine.state == .talking else { return }   // the key came up while the app asked: no mic
        do { try recorder.start() } catch { strip.show(line: GuideText.noMic, typing: true, in: visibleFrame()) }
    }

    func endTalk() {
        holdTimer?.invalidate()
        if frontIsMe { return }
        guard let wav = recorder.stop() else {
            if !strip.isTyping { strip.show(line: GuideText.heardNothing, typing: true, in: visibleFrame()) }
            return
        }
        strip.say(GuideText.writing)
        Task {
            let text = (try? await client?.stt(wav)) ?? ""
            if text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                strip.show(line: GuideText.heardNothing, typing: true, in: visibleFrame())
            } else { send(text) }
        }
    }

    // --- the question ------------------------------------------------------------------------------------------------------
    func send(_ said: String) {
        let said = AnchorList.cut(said, 300)
        guard !said.isEmpty, let client else { return }
        strip.release()
        strip.say(GuideText.reading)
        asking?.cancel()
        asking = Task {
            if snapshot == nil, let r = reading { snapshot = await r.value }
            let snap = snapshot ?? Snapshot(window: nil, items: [], limit: .noAccess, ms: 0)
            let ctx = AnchorList.build(window: snap.window, items: snap.items, limit: snap.limit)
            let displays = Display.all, h = Geometry.mainHeight(displays)
            let win = snap.window.map { Geometry.appKit(fromCG: $0.frame, mainHeight: h) } ?? .zero
            guard let d = Geometry.display(for: win, in: displays), let body = try? AnchorList.body(said: said, ctx: ctx) else { return }
            overlay.show(on: d, boxes: OverlayPage.boxes(ctx.anchors, display: d, mainHeight: h))
            do {
                for try await e in client.ask(body) {
                    if Task.isCancelled { return }
                    switch e.kind {
                    case .wait(let t): strip.say(t)
                    case .error(let t): strip.say(t, after: 6); overlay.hide()
                    case .step, .board:
                        if !boardShows { boardShows = true; strip.hide(); followWindow(snap.window) }
                        overlay.event(e.raw)
                    case .other: break
                    }
                }
            } catch GuideClient.Failure.status(_, let text) {
                strip.say(text.isEmpty ? GuideText.failed : AnchorList.cut(text, 200), after: 6)
                if !boardShows { overlay.hide() }
            } catch {
                strip.say(GuideText.failed, after: 6)
                if !boardShows { overlay.hide() }
            }
        }
    }

    /// the strip's line for what the guide could not read
    func limitLine() -> String {
        switch snapshot?.limit ?? .none {
        case .none: return ""
        case .noAccess: return GuideText.windowOnly(snapshot?.window?.app ?? "this app")
        case .neverLook(let a): return GuideText.neverLook(a)
        case .password: return GuideText.password
        }
    }

    // --- the board on the screen -------------------------------------------------------------------------------------------
    /// moves the marks with the window, ten times a second, while a board shows; the board stops when the window goes
    func followWindow(_ w: FrontWindow?) {
        follow?.invalidate()
        guard let w, w.windowID != 0 else { return }
        var last = w.frame.origin
        follow = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated {
                guard let self else { return }
                guard let now = AXReader.bounds(of: w.windowID) else { self.overlay.stop(); return }
                if now.origin != last {
                    self.overlay.move(dx: now.minX - last.x, dy: now.minY - last.y)
                    last = now.origin
                }
            }
        }
    }

    /// board.js stopped a board; a new board can start at the same time, so look again a little later
    func boardStopped() {
        Task {
            try? await Task.sleep(for: .milliseconds(300))
            if await overlay.showing() { return }
            follow?.invalidate()
            boardShows = false
            overlay.hide()
        }
    }

    // --- permissions ------------------------------------------------------------------------------------------------------
    /// the Accessibility sheet, once, at the first question over another app with no permission
    func firstUseSheet() -> StripModel.Sheet? {
        guard snapshot?.limit == .noAccess, !UserDefaults.standard.bool(forKey: Self.askedAccessKey) else { return nil }
        let app = snapshot?.window?.app ?? "this app"
        return StripModel.Sheet(title: GuideText.accessTitle(app), body: GuideText.accessBody(app))
    }

    func answerSheet(_ yes: Bool) {
        UserDefaults.standard.set(true, forKey: Self.askedAccessKey)
        strip.sheet(nil)
        guard yes else { return }
        AXReader.askTrust()
        if let u = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility") { NSWorkspace.shared.open(u) }
    }
}
