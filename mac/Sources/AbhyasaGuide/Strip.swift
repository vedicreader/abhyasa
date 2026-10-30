import AppKit
import SwiftUI
import Observation

/// The state of the strip: one line of state, the box for the question, and a first-use sheet when one is due.
@MainActor @Observable
public final class StripModel {
    public struct Sheet: Equatable {
        public var title: String
        public var body: String
    }
    public var line = ""
    public var text = ""
    public var typing = false
    public var sheet: Sheet?
    @ObservationIgnored public var onSend: ((String) -> Void)?
    @ObservationIgnored public var onClose: (() -> Void)?
    @ObservationIgnored public var onSheet: ((Bool) -> Void)?
}

/// Muted and legible (as in Sanketa): a plain material, the system font, no boxes inside boxes.
struct StripView: View {
    @Bindable var m: StripModel
    @FocusState private var focus: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let s = m.sheet {
                Text(s.title).font(.headline)
                Text(s.body).font(.callout).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                HStack {
                    Spacer()
                    Button(GuideText.notNow) { m.onSheet?(false) }
                    Button(GuideText.openSettings) { m.onSheet?(true) }.keyboardShortcut(.defaultAction)
                }
            }
            if m.typing {
                TextField(GuideText.ask, text: $m.text, prompt: Text("I don't get …"))
                    .textFieldStyle(.plain).font(.title3).focused($focus)
                    .onSubmit { m.onSend?(m.text) }
                    .onExitCommand { m.onClose?() }
                    .onAppear { focus = true }
            }
            if !m.line.isEmpty {
                Text(m.line).font(.callout).foregroundStyle(.secondary).lineLimit(2)
            }
        }
        .padding(.horizontal, 18).padding(.vertical, 14)
        .frame(width: StripPanel.size.width, alignment: .leading)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
    }
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
        let host = NSHostingView(rootView: StripView(m: model))
        host.sizingOptions = [.preferredContentSize]
        p.contentView = host
        panel = p
        return p
    }

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
    public func say(_ line: String, after: Double? = nil) {
        model.line = line
        resize()
        guard let after else { return }
        hideTask?.cancel()
        hideTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(after))
            if !Task.isCancelled { self?.hide() }
        }
    }

    public func sheet(_ s: StripModel.Sheet?) { model.sheet = s; resize() }

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
