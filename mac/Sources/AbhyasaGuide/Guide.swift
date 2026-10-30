import AppKit
import Observation
import AbhyasaCore

/// What Settings and the menu show of the guide: on or off, and its state now.
@MainActor @Observable
public final class GuideStatus {
    public var on = false
    public var state: GuideState = .off
    public var muted = false
}

/// The screen guide over other apps (design phase 2). Caps+E (Hyper+E) reads the window in front, opens the strip, sends the
/// question with the anchors to the server's `/guide/ask`, and plays the board in the overlay over that window. The server is
/// the brain; this class only reads, asks and draws.
///
/// Never caught unaware (0.0.15): the guide is off until the learner pushes Start in its first-use sheet. Before Start it holds
/// no key and no mouse monitor. Each state has a line in the strip and a mark in the menu bar, and the strip says what leaves
/// the Mac, to which model, before the request goes.
@MainActor
public final class Guide {
    public static let shared = Guide()
    static let onKey = "guide.on", startedKey = "guide.started", askedAccessKey = "guide.askedAccess"
    static let askedVoiceKey = "guide.askedVoice", mutedKey = "guide.voiceOff"
    /// the store of the switches; the tests use their own
    static var defaults = UserDefaults.standard
    /// true when the key may be held: the learner pushed Start, and the switch is on
    public static var holdsKey: Bool { on && started }

    public let overlay = Overlay()
    public let strip = Strip()
    public let status = GuideStatus()
    let mark = MenuMark()
    let speaker = Speaker()
    let recorder = Recorder()
    let keys = HotKeys()
    let trail = PointerTrail()
    var machine = KeyMachine()
    var client: GuideClient?
    var reading: Task<Snapshot, Never>?
    var snapshot: Snapshot?
    var asking: Task<Void, Never>?
    var follow: Timer?
    var holdTimer: Timer?
    var levelTimer: Timer?
    /// the global monitor of keys and moves, only in the countdown of the board's end
    var activity: Any?
    var lingerAt = 0.0
    /// who gets this question; the server's events correct the guess
    var who = Who.guess("")
    /// the first mark of this board shows
    var drew = false
    var boardShows = false { didSet { keys.escape(KeyMachine.wantsEscape(boardShows: boardShows)) } }
    /// a press of the key while Abhyasa's own window is in front: the page has its own guide (Hyper+E), so it opens that
    public var ownApp: (() -> Void)?
    /// opens the Settings window of the app
    public var openSettings: (() -> Void)?
    /// the model id and the speech engine of the Mac Settings (empty: the server default and the Settings page)
    public var model = ""
    public var speechEngine = ""

    /// the learner's switch: off until they push Start in the first-use sheet
    public static var on: Bool {
        get { Self.defaults.bool(forKey: onKey) }
        set { Self.defaults.set(newValue, forKey: onKey) }
    }
    static var started: Bool {
        get { Self.defaults.bool(forKey: startedKey) }
        set { Self.defaults.set(newValue, forKey: startedKey) }
    }
    var muted: Bool { Self.defaults.bool(forKey: Self.mutedKey) }
    var speech: Speech { Speech.of(speechEngine) }

    init() {
        keys.onDown = { [weak self] in self?.down() }
        keys.onUp = { [weak self] in self?.up() }
        keys.onEscape = { [weak self] in self?.act(self?.machine.escape(boardShows: self?.boardShows ?? false) ?? []) }
        overlay.onSpeak = { [weak self] id, t in self?.speaker.speak(id, t) }
        overlay.onHush = { [weak self] id in self?.speaker.hush(id) }
        overlay.onStop = { [weak self] in self?.boardStopped() }
        overlay.onFirst = { [weak self] in self?.drawing() }
        overlay.onLinger = { [weak self] s in self?.linger(s) }
        speaker.onWord = { [weak self] id, k in self?.overlay.word(id, k) }
        speaker.onDone = { [weak self] id in self?.overlay.done(id) }
        speaker.fetch = { [weak self] t in await self?.client?.say(t) ?? .failed("no server") }
        strip.model.onSend = { [weak self] t in self?.send(t) }
        strip.model.onClose = { [weak self] in self?.closeStrip() }
        strip.model.onSheet = { [weak self] id, b in self?.answerSheet(id, b) }
        strip.model.onStop = { [weak self] in self?.stopQuestion() }
        strip.model.onVoice = { [weak self] in self?.toggleVoice() }
        strip.model.onUndo = { [weak self] s in self?.undo(s) }
        trail.text = { [weak self] in self?.strip.model.text ?? "" }
        trail.onTrail = { [weak self] pts in self?.overlay.trail(pts) }
        trail.onRing = { [weak self] g in self?.overlay.ring(g) }
        trail.onEnd = { [weak self] in self?.overlay.endTrail() }
        mark.onStop = { [weak self] in self?.stopQuestion() }
        mark.onVoice = { [weak self] in self?.toggleVoice() }
        mark.onTurn = { [weak self] on in self?.setEnabled(on) }
        mark.onSettings = { [weak self] in self?.openSettings?() }
    }

    /// the server is ready on `port`: the menu bar mark shows, and the key works from now on when the guide is on
    public func start(port: Int) {
        let base = Port.base(port)
        client = GuideClient(base: base)
        overlay.base = base
        speaker.muted = muted
        status.muted = muted
        mark.muted = muted
        mark.install()
        apply()
    }

    /// holds the key (or not) as the switch says
    func apply() {
        let on = Self.holdsKey
        status.on = on
        if on, client != nil { keys.register(); set(.ready) } else { stop(); set(.off) }
    }

    func set(_ s: GuideState) {
        status.state = s
        mark.show(s)
    }

    /// the switch of Settings and the menu: on shows the first-use sheet the first time; off lets go of the key at once
    public func setEnabled(_ on: Bool) {
        if on { requestStart() } else { Self.on = false; apply() }
    }

    /// the first-use sheet in the strip, never at launch: it shows only when the learner turns the guide on
    public func requestStart() {
        if Self.started { Self.on = true; apply(); return }
        strip.show(line: "", typing: false, in: visibleFrame())
        strip.sheet(Self.startSheet(who: Who.guess(model, names: names), vision: WindowPicture.enabled))
    }

    var names: [String: String] { Dictionary(ServerSettings.models.map { ($0.id, $0.name) }, uniquingKeysWith: { a, _ in a }) }

    /// lets go of everything: the key, Esc, the monitors, the mic, the request and the panels
    public func stop() {
        asking?.cancel()
        _ = recorder.stop()
        holdTimer?.invalidate(); levelTimer?.invalidate()
        machine = KeyMachine()
        trail.stop()
        endActivity()
        keys.unregister()
        overlay.stop()
        overlay.hide()
        strip.hide()
        boardShows = false
        drew = false
    }

    // --- the key -----------------------------------------------------------------------------------------------------------
    var clock: Double { ProcessInfo.processInfo.systemUptime }

    func down() {
        let acts = machine.down(clock)
        if !acts.isEmpty, !boardShows, !frontIsMe {
            // U11: the sign first, then the read of the window
            strip.model.clear()
            strip.show(line: GuideText.readsWindow, typing: false, in: visibleFrame())
            set(.reading)
            read()
        }
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
            case .again: endCountdown(); overlay.again()
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

    /// the parts of the window that go with a question, from the snapshot
    func context(_ snap: Snapshot) -> GuideContext { AnchorList.build(window: snap.window, items: snap.items, limit: snap.limit) }

    func open(talk: Bool) {
        if frontIsMe { ownApp?(); return }
        guard client != nil else { return }
        trail.start()   // show while you talk: the pointer path, until the question goes or the strip closes
        Task {
            if let r = reading { snapshot = await r.value }
            let snap = snapshot ?? Snapshot(window: nil, items: [], limit: .noAccess, ms: 0)
            let limit = limitLine()
            let readLine = limit.isEmpty ? GuideText.reads(snap.window?.app ?? "this app", parts: Lines.parts(context(snap).anchors)) : limit
            strip.show(line: talk ? GuideText.micOn : readLine, typing: !talk, in: visibleFrame())
            strip.update {
                $0.trail = true
                if talk {
                    $0.chip = GuideText.speechChip(speech)
                    $0.chipHosted = speech.isHosted
                    $0.detail = readLine
                    $0.level = 0
                } else { $0.chip = GuideText.onThisMac }
            }
            set(talk ? .listening : .ready)
            strip.sheet(firstUseSheet() ?? (talk ? voiceSheet() : nil))
            if talk { await startTalk() }
        }
    }

    func closeStrip() {
        trail.stop()
        strip.hide()
        set(.ready)
    }

    // --- voice in ----------------------------------------------------------------------------------------------------------
    func startTalk() async {
        guard await Recorder.allowed() else { noMic(); return }
        guard machine.state == .talking else { return }   // the key came up while the app asked: no mic
        do { try recorder.start() } catch { noMic(); return }
        levelTimer?.invalidate()
        levelTimer = Timer.scheduledTimer(withTimeInterval: 0.08, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated { guard let self, self.recorder.on else { return }; self.strip.model.level = self.recorder.level }
        }
    }

    func noMic() {
        strip.update { $0.level = nil; $0.chip = "" }
        strip.show(line: GuideText.noMic, typing: true, in: visibleFrame())
        set(.ready)
    }

    func endTalk() {
        holdTimer?.invalidate()
        levelTimer?.invalidate()
        strip.update { $0.level = nil }
        if frontIsMe { return }
        guard let wav = recorder.stop() else {
            if !strip.isTyping { strip.show(line: GuideText.heardNothing, typing: true, in: visibleFrame()) }
            set(.ready)
            return
        }
        let s = speech
        strip.say(GuideText.writing, chip: GuideText.speechChip(s), hosted: s.isHosted)
        set(.writing)
        Task {
            let text = (try? await client?.stt(wav)) ?? ""
            if text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                strip.show(line: GuideText.heardNothing, typing: true, in: visibleFrame())
                set(.ready)
            } else { send(text) }
        }
    }

    // --- the question ------------------------------------------------------------------------------------------------------
    func send(_ said: String) {
        let said = AnchorList.cut(said, 300)
        guard !said.isEmpty, let client else { return }
        let shown = trail.stop()   // what the learner showed with the pointer while they asked
        strip.release()
        strip.update { $0.trail = false; $0.level = nil; $0.stoppable = true; $0.saved = nil }
        strip.say(GuideText.reading, chip: GuideText.onThisMac)
        set(.reading)
        drew = false
        asking?.cancel()
        asking = Task {
            if snapshot == nil, let r = reading { snapshot = await r.value }
            let snap = snapshot ?? Snapshot(window: nil, items: [], limit: .noAccess, ms: 0)
            var ctx = context(snap)
            let focus = PointerTrail.focus(shown, anchors: ctx.anchors)
            if !focus.isEmpty { ctx.focus = focus }
            let displays = Display.all, h = Geometry.mainHeight(displays)
            let win = snap.window.map { Geometry.appKit(fromCG: $0.frame, mainHeight: h) } ?? .zero
            guard let d = Geometry.display(for: win, in: displays), let body = try? AnchorList.body(said: said, ctx: ctx) else { return }
            // U12: before the request, what leaves the Mac and to whom
            let parts = Lines.parts(ctx.anchors)
            who = Who.guess(model, names: names)
            strip.say(GuideText.sends(parts: parts, to: who.model, local: who.local), chip: who.chip, hosted: !who.local,
                      detail: GuideText.reads(snap.window?.app ?? "this app", parts: parts))
            set(.asking(who))
            overlay.show(on: d, boxes: OverlayPage.boxes(ctx.anchors, display: d, mainHeight: h))
            do {
                for try await e in client.ask(body) {
                    if Task.isCancelled { return }
                    if let st = e.status { who = who.with(st) }
                    switch e.kind {
                    case .wait(let t):
                        guard !drew else { break }   // the board strip stays while the board draws
                        let l = Lines.wait(t, e.status, who: who)
                        strip.say(l.text, chip: l.chip, hosted: l.hosted, detail: l.detail)
                        if let s = GuideState.server(e.status?.state, who: who) { set(s) }
                        else if e.status?.model != nil || e.status?.place != nil { set(.asking(who)) }
                    case .error(let t):
                        strip.update { $0.stoppable = false; $0.board = false }
                        strip.say(t, after: 6)
                        overlay.hide()
                        set(.ready)
                    case .saved(let s):
                        strip.update { $0.saved = s }
                    case .step, .board:
                        if !boardShows { boardShows = true; followWindow(snap.window) }
                        overlay.event(e.raw)
                    case .other: break
                    }
                }
            } catch GuideClient.Failure.status(_, let text) {
                failed(text.isEmpty ? GuideText.failed : AnchorList.cut(text, 200))
            } catch {
                if !Task.isCancelled { failed(GuideText.failed) }
            }
        }
    }

    func failed(_ line: String) {
        strip.update { $0.stoppable = false; $0.board = false }
        strip.say(line, after: 6)
        if !boardShows { overlay.hide(); set(.ready) }
    }

    /// Stop, from the strip or the menu: the request ends (the stream closes), the mic and the board stop
    func stopQuestion() {
        let wasAsking = !boardShows && (status.state.busy)
        asking?.cancel()
        holdTimer?.invalidate(); levelTimer?.invalidate()
        _ = recorder.stop()
        machine = KeyMachine()
        trail.stop()
        if boardShows { overlay.stop(); return }   // board.js stops, and boardStopped takes the rest away
        overlay.hide()
        if wasAsking {
            strip.update { $0.stoppable = false; $0.level = nil; $0.trail = false }
            strip.say(GuideText.stopped, after: 5)
        } else { strip.hide() }
        set(status.on ? .ready : .off)
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
    /// U15 and U13: the first mark shows, so the strip becomes the board strip: the model and where, Stop and Voice off
    func drawing() {
        guard boardShows, !drew else { return }
        drew = true
        set(.drawing)
        strip.update {
            $0.set(muted ? GuideText.drawingQuiet : GuideText.drawing, chip: Lines.boardChip(who), hosted: !who.local, detail: GuideText.keys)
            $0.board = true; $0.stoppable = true; $0.muted = muted; $0.level = nil; $0.trail = false
        }
        if !strip.isVisible { strip.show(line: strip.model.line, typing: false, in: visibleFrame()) }
    }

    /// U14: the board goes in `s` seconds; the strip counts them, and a key or a move keeps the board
    func linger(_ s: Double) {
        strip.update { $0.countdown = (Date(), s) }
        endActivity()
        lingerAt = clock
        activity = NSEvent.addGlobalMonitorForEvents(matching: [.mouseMoved, .keyDown, .leftMouseDown, .scrollWheel]) { [weak self] _ in
            MainActor.assumeIsolated {
                guard let self, self.clock - self.lingerAt > 0.4 else { return }   // a small shake as the line ends is not a keep
                self.keepBoard()
            }
        }
    }

    func keepBoard() {
        guard strip.model.countdown != nil else { return }
        overlay.keep()
        strip.update { $0.countdown = nil; $0.detail = GuideText.kept }
        endActivity()
    }

    func endCountdown() {
        endActivity()
        strip.update { $0.countdown = nil; $0.detail = GuideText.keys }
    }

    func endActivity() {
        if let a = activity { NSEvent.removeMonitor(a) }
        activity = nil
    }

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
            endActivity()
            boardShows = false
            drew = false
            overlay.hide()
            set(status.on ? .ready : .off)
            if strip.model.saved != nil {   // a thing that stays after the board shows at the end, with Undo
                strip.update { $0.set(""); $0.board = false; $0.stoppable = false; $0.countdown = nil }
                strip.hideLater(10)
            } else { strip.hide() }
        }
    }

    func toggleVoice() {
        let m = !muted
        Self.defaults.set(m, forKey: Self.mutedKey)
        speaker.muted = m
        mark.muted = m
        status.muted = m
        strip.update {
            $0.muted = m
            if self.drew { $0.line = m ? GuideText.drawingQuiet : GuideText.drawing }
        }
    }

    func undo(_ s: GuideEvent.Saved) {
        guard let client else { return }
        Task {
            let ok = await client.post(s.undo)
            strip.update { $0.saved = nil; $0.detail = ok ? GuideText.undone : GuideText.undoFailed }
        }
    }

    // --- first-use sheets -------------------------------------------------------------------------------------------------
    /// the sheet of the guide (U10, review 1.4): what it reads, what leaves the Mac and to whom, the key, and how to turn it off
    nonisolated public static func startSheet(who: Who, vision: Bool) -> StripModel.Sheet {
        var buttons = [StripModel.Sheet.Button(id: "off", title: GuideText.turnOff)]
        if !who.local { buttons.append(.init(id: "local", title: GuideText.useLocal)) }
        buttons.append(.init(id: "start", title: GuideText.start, main: true))
        return StripModel.Sheet(id: "guide", title: GuideText.guideTitle,
                                body: [GuideText.guideKey, GuideText.guideSends(model: who.model, local: who.local, who: who.company),
                                       GuideText.guideKeeps(vision: vision), GuideText.guideDraws, GuideText.guideOff],
                                buttons: buttons)
    }

    /// the sheet of the voice, once, at the first hold of the key
    nonisolated public static func voiceSheet(_ s: Speech) -> StripModel.Sheet {
        StripModel.Sheet(id: "voice", title: GuideText.voiceTitle, body: [GuideText.voiceHold, GuideText.voiceWhere(s), GuideText.voiceSpeaks],
                         buttons: [.init(id: "ok", title: GuideText.ok, main: true)])
    }

    func voiceSheet() -> StripModel.Sheet? {
        Self.defaults.bool(forKey: Self.askedVoiceKey) ? nil : Self.voiceSheet(speech)
    }

    /// the Accessibility sheet, once, at the first question over another app with no permission
    func firstUseSheet() -> StripModel.Sheet? {
        guard snapshot?.limit == .noAccess, !Self.defaults.bool(forKey: Self.askedAccessKey) else { return nil }
        let app = snapshot?.window?.app ?? "this app"
        return StripModel.Sheet(id: "access", title: GuideText.accessTitle(app), body: [GuideText.accessBody(app)],
                                buttons: [.init(id: "later", title: GuideText.notNow), .init(id: "open", title: GuideText.openSettings, main: true)])
    }

    func answerSheet(_ id: String, _ button: String) {
        strip.sheet(nil)
        switch (id, button) {
        case ("guide", "start"):
            Self.started = true
            Self.on = true
            apply()
            strip.say(GuideText.menuReady, after: 4)
        case ("guide", "local"):
            strip.hide()
            openSettings?()
        case ("guide", _):
            Self.on = false
            apply()
        case ("voice", _):
            Self.defaults.set(true, forKey: Self.askedVoiceKey)
        case ("access", let b):
            Self.defaults.set(true, forKey: Self.askedAccessKey)
            guard b == "open" else { return }
            AXReader.askTrust()
            if let u = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility") { NSWorkspace.shared.open(u) }
        default: break
        }
    }
}
