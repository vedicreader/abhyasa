import AppKit
import SwiftUI
import Observation

/// The state of the strip: one line of state with its where chip, a second line, the box for the question, the mic level,
/// Stop and Voice off, the countdown of the board's end, a saved thing with Undo, and a first-use sheet when one is due.
@MainActor @Observable
public final class StripModel {
    public struct Sheet: Equatable {
        public struct Button: Equatable {
            public var id: String
            public var title: String
            public var main = false
        }
        public var id: String
        public var title: String
        public var body: [String]
        public var buttons: [Button]
    }
    public var line = ""
    /// the where chip after the line: "on this Mac" (quiet) or "hosted · Anthropic" (outlined)
    public var chip = ""
    public var chipHosted = false
    public var detail = ""
    public var text = ""
    public var typing = false
    /// the pointer trail is on: the strip says so
    public var trail = false
    /// the mic level from 0 to 1 while the mic is on, else nil
    public var level: Float?
    /// Stop shows while the guide asks or a board shows; Voice off while a board shows
    public var stoppable = false
    public var board = false
    public var muted = false
    /// the countdown of the board's end: when it started and how long it is
    public var countdown: (start: Date, seconds: Double)?
    public var saved: GuideEvent.Saved?
    public var sheet: Sheet?
    @ObservationIgnored public var onSend: ((String) -> Void)?
    @ObservationIgnored public var onClose: (() -> Void)?
    @ObservationIgnored public var onSheet: ((String, String) -> Void)?
    @ObservationIgnored public var onStop: (() -> Void)?
    @ObservationIgnored public var onVoice: (() -> Void)?
    @ObservationIgnored public var onUndo: ((GuideEvent.Saved) -> Void)?

    /// one line of state with its chip; the second line, the level and the saved line stay as they are
    public func set(_ line: String, chip: String = "", hosted: Bool = false, detail: String = "") {
        self.line = line; self.chip = chip; chipHosted = hosted; self.detail = detail
    }

    /// back to an empty strip, with no buttons
    public func clear() {
        set("")
        level = nil; stoppable = false; board = false; countdown = nil; saved = nil; trail = false
    }
}

/// Muted and legible (as in Sanketa): a plain material, the system font, no boxes inside boxes.
struct StripView: View {
    @Bindable var m: StripModel
    @FocusState private var focus: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let s = m.sheet {
                Text(s.title).font(.headline)
                ForEach(Array(s.body.enumerated()), id: \.offset) { _, p in
                    Text(p).font(.callout).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                }
                HStack {
                    Spacer()
                    ForEach(s.buttons, id: \.id) { b in
                        if b.main { Button(b.title) { m.onSheet?(s.id, b.id) }.keyboardShortcut(.defaultAction) }
                        else { Button(b.title) { m.onSheet?(s.id, b.id) } }
                    }
                }
            }
            if m.typing {
                TextField(GuideText.ask, text: $m.text, prompt: Text("I don't get …"))
                    .textFieldStyle(.plain).font(.title3).focused($focus)
                    .onSubmit { m.onSend?(m.text) }
                    .onExitCommand { m.onClose?() }
                    .onAppear { focus = true }
            }
            if !m.line.isEmpty || m.stoppable {
                HStack(spacing: 8) {
                    if let l = m.level { Level(value: l) }
                    Text(m.line).font(.callout).foregroundStyle(.secondary).lineLimit(2)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    if !m.chip.isEmpty { Chip(text: m.chip, hosted: m.chipHosted) }
                    if m.board { Button(m.muted ? GuideText.voiceOn : GuideText.voiceOff) { m.onVoice?() }.controlSize(.small) }
                    if m.stoppable { Button(GuideText.stop) { m.onStop?() }.controlSize(.small) }
                }
            }
            if !m.detail.isEmpty {
                Text(m.detail).font(.caption).foregroundStyle(.secondary).lineLimit(2)
            }
            if let s = m.saved {
                HStack(spacing: 8) {
                    Text(GuideText.saved(s.title)).font(.callout).foregroundStyle(.secondary).lineLimit(1)
                    if !s.undo.isEmpty { Button(GuideText.undo) { m.onUndo?(s) }.buttonStyle(.link).controlSize(.small) }
                }
            }
            if m.trail { Text(GuideText.trail).font(.caption).foregroundStyle(.tertiary) }
            if let c = m.countdown { Countdown(start: c.start, seconds: c.seconds) }
        }
        .padding(.horizontal, 18).padding(.vertical, 14)
        .frame(width: StripPanel.size.width, alignment: .leading)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
    }
}

/// The where chip: quiet text on this Mac, a thin accent outline when the text leaves the Mac.
struct Chip: View {
    let text: String
    let hosted: Bool
    var body: some View {
        Text(text).font(.caption.weight(.medium)).lineLimit(1).fixedSize()
            .padding(.horizontal, 7).padding(.vertical, 3)
            .foregroundStyle(hosted ? AnyShapeStyle(.tint) : AnyShapeStyle(.secondary))
            .background(Capsule().fill(hosted ? Color.clear : Color.primary.opacity(0.06)))
            .overlay(Capsule().strokeBorder(hosted ? Color.accentColor.opacity(0.7) : .clear, lineWidth: 1))
    }
}

/// Four bars that follow the mic level; flat at silence.
struct Level: View {
    let value: Float
    var body: some View {
        HStack(alignment: .center, spacing: 2) {
            ForEach(0..<4, id: \.self) { k in
                let w: [Float] = [0.6, 1, 0.8, 0.45]
                Capsule().fill(.secondary).frame(width: 3, height: CGFloat(3 + 12 * min(1, value * w[k] * 1.4)))
            }
        }.frame(height: 16).accessibilityLabel(GuideText.menuListening)
    }
}

/// A thin, quiet line that gets shorter until the board goes, and its one plain line.
struct Countdown: View {
    let start: Date
    let seconds: Double
    var body: some View {
        TimelineView(.periodic(from: start, by: 0.25)) { t in
            let left = max(0, seconds - t.date.timeIntervalSince(start))
            VStack(alignment: .leading, spacing: 4) {
                Text(GuideText.closesIn(Int(left.rounded(.up)))).font(.caption).foregroundStyle(.tertiary)
                GeometryReader { g in
                    Rectangle().fill(.tertiary).frame(width: g.size.width * left / seconds, height: 1)
                }.frame(height: 1)
            }
        }
    }
}

/// A hosting view that takes the first click: the strip is not the key window, and a click on Stop must work at once.
final class FirstClickHost<V: View>: NSHostingView<V> {
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
}

/// The strip panel and its model.
@MainActor
public final class Strip {
    public let model = StripModel()
    var panel: StripPanel?
    var hideTask: Task<Void, Never>?

    public init() {}

    func make() -> StripPanel {
        if let panel { return panel }
        let p = StripPanel()
        let host = FirstClickHost(rootView: StripView(m: model))
        host.sizingOptions = [.preferredContentSize]
        p.contentView = host
        panel = p
        return p
    }

    public var isVisible: Bool { panel?.isVisible ?? false }

    /// shows the strip on the display with `visible` frame; `typing` opens the box and takes the key window, with no app switch
    public func show(line: String, typing: Bool, in visible: CGRect) {
        hideTask?.cancel()
        let p = make()
        model.line = line
        model.typing = typing
        if typing { model.text = "" }
        p.typing = typing
        let h = p.contentView?.fittingSize.height ?? StripPanel.size.height
        p.setFrame(StripPanel.frame(in: visible, height: max(48, h)), display: true)
        if typing { p.makeKeyAndOrderFront(nil) } else { p.orderFrontRegardless() }
    }

    /// one line of state; the strip shows it, and goes after `after` seconds when that is set
    public func say(_ line: String, chip: String = "", hosted: Bool = false, detail: String = "", after: Double? = nil) {
        model.set(line, chip: chip, hosted: hosted, detail: detail)
        resize()
        guard let after else { return }
        hideLater(after)
    }

    public func hideLater(_ after: Double) {
        hideTask?.cancel()
        hideTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(after))
            if !Task.isCancelled { self?.hide() }
        }
    }

    public func sheet(_ s: StripModel.Sheet?) { model.sheet = s; resize() }

    /// changes the model, then fits the panel to it
    public func update(_ change: (StripModel) -> Void) { change(model); resize() }

    func resize() {
        guard let p = panel, p.isVisible, let h = p.contentView?.fittingSize.height else { return }
        var f = p.frame
        f.origin.y += f.height - h
        f.size.height = h
        p.setFrame(f, display: true)
    }

    public func hide() {
        hideTask?.cancel()
        model.typing = false
        model.sheet = nil
        model.clear()
        panel?.typing = false
        panel?.orderOut(nil)
    }

    public var isTyping: Bool { model.typing }

    /// closes the box and gives the key window back to the app in front; the line of state stays on the screen
    public func release() {
        model.typing = false
        guard let p = panel, p.typing else { return }
        p.typing = false
        p.orderOut(nil)
        p.orderFrontRegardless()
        resize()
    }
}
