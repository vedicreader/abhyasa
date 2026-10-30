import Carbon.HIToolbox
import Foundation

/// The guide's keys as Carbon hot keys (`RegisterEventHotKey`): they give a press and a release, and they need no permission
/// (no event tap, no Input Monitoring). ⌥` is always held while the guide is on. `Esc` is held only while a board shows.
@MainActor
public final class HotKeys {
    public struct Key: Equatable, Sendable {
        public var code: UInt32
        public var mods: UInt32
        public static let guide = Key(code: UInt32(kVK_ANSI_Grave), mods: UInt32(optionKey))
        public static let escape = Key(code: UInt32(kVK_Escape), mods: 0)
    }
    enum ID: UInt32 { case guide = 1, escape = 2 }

    public var onDown: (() -> Void)?
    public var onUp: (() -> Void)?
    public var onEscape: (() -> Void)?

    var refs: [ID: EventHotKeyRef] = [:]
    var handler: EventHandlerRef?
    static weak var shared: HotKeys?

    public init() {}

    public var isOn: Bool { refs[.guide] != nil }

    public func register() {
        installHandler()
        add(.guide, .guide)
    }

    public func unregister() {
        for id in refs.keys { remove(id) }
    }

    /// holds `Esc` only while `on` is true, so the app in front gets it at other times
    public func escape(_ on: Bool) {
        if on, isOn { add(.escape, .escape) } else { remove(.escape) }
    }

    func add(_ id: ID, _ k: Key) {
        guard refs[id] == nil else { return }
        var ref: EventHotKeyRef?
        let hid = EventHotKeyID(signature: OSType(0x4162_6879), id: id.rawValue)   // 'Abhy'
        if RegisterEventHotKey(k.code, k.mods, hid, GetApplicationEventTarget(), 0, &ref) == noErr, let ref { refs[id] = ref }
    }

    func remove(_ id: ID) {
        if let r = refs.removeValue(forKey: id) { UnregisterEventHotKey(r) }
    }

    func installHandler() {
        guard handler == nil else { return }
        Self.shared = self
        var types = [EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed)),
                     EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyReleased))]
        InstallEventHandler(GetApplicationEventTarget(), { _, event, _ -> OSStatus in
            var hid = EventHotKeyID()
            guard let event, GetEventParameter(event, EventParamName(kEventParamDirectObject), EventParamType(typeEventHotKeyID), nil,
                                               MemoryLayout<EventHotKeyID>.size, nil, &hid) == noErr else { return OSStatus(eventNotHandledErr) }
            let pressed = GetEventKind(event) == UInt32(kEventHotKeyPressed)
            MainActor.assumeIsolated {
                guard let me = HotKeys.shared else { return }
                switch (ID(rawValue: hid.id), pressed) {
                case (.guide, true): me.onDown?()
                case (.guide, false): me.onUp?()
                case (.escape, true): me.onEscape?()
                default: break
                }
            }
            return noErr
        }, types.count, &types, nil, &handler)
    }
}
