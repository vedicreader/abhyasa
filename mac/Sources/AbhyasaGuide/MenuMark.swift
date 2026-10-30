import AppKit

/// The menu bar mark of the screen guide (P0 item 5): a small template glyph that follows the state, with no animation. Its
/// menu has the state line, Stop, Voice off, Turn off (or on) the guide, and Settings.
@MainActor
public final class MenuMark: NSObject, NSMenuDelegate {
    var item: NSStatusItem?
    public private(set) var state: GuideState = .off
    public var muted = false
    public var onStop: (() -> Void)?
    public var onVoice: (() -> Void)?
    /// true: turn on (the first-use sheet when it is due); false: turn off
    public var onTurn: ((Bool) -> Void)?
    public var onSettings: (() -> Void)?

    /// the items of the menu for `state`, as (title, enabled, checked); a pure part, for the tests
    nonisolated public static func items(_ state: GuideState, muted: Bool) -> [(title: String, enabled: Bool, checked: Bool)] {
        [(state.line, false, false),
         (GuideText.stop, state.busy, false),
         (GuideText.voiceOff, state != .off, muted),
         (state == .off ? GuideText.turnOn : GuideText.turnOff, true, false),
         (GuideText.settings, true, false)]
    }

    public func install() {
        guard item == nil else { return }
        let i = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        let m = NSMenu()
        m.delegate = self
        i.menu = m
        item = i
        show(state)
    }

    public func show(_ s: GuideState) {
        state = s
        guard let b = item?.button else { return }
        let img = NSImage(systemSymbolName: s.symbol, accessibilityDescription: s.line)
        img?.isTemplate = true
        b.image = img
        b.toolTip = s.line
        b.appearsDisabled = s == .off
    }

    // the menu is made each time it opens, so it always says the state of now
    public func menuNeedsUpdate(_ menu: NSMenu) {
        menu.removeAllItems()
        let acts: [Selector?] = [nil, #selector(stop), #selector(voice), #selector(turn), #selector(settings)]
        for (k, e) in Self.items(state, muted: muted).enumerated() {
            let mi = NSMenuItem(title: e.title, action: e.enabled ? acts[k] : nil, keyEquivalent: "")
            mi.target = self
            mi.isEnabled = e.enabled
            mi.state = e.checked ? .on : .off
            menu.addItem(mi)
            if k == 0 || k == 2 { menu.addItem(.separator()) }
        }
    }

    @objc func stop() { onStop?() }
    @objc func voice() { onVoice?() }
    @objc func turn() { onTurn?(state == .off) }
    @objc func settings() { onSettings?() }
}
