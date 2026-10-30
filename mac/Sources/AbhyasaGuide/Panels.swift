import AppKit

/// The panel that holds the board over one display. It never takes a click, the focus or the key window: the app in front
/// keeps them. It shows on all Spaces and over full-screen apps, and it does not move when the Space changes. The flags are
/// the known-good set from Clicky's OverlayWindow.swift (MIT), with the level from design section 12.2.
public final class OverlayPanel: NSPanel {
    public static let level = NSWindow.Level.statusBar
    public static let behavior: NSWindow.CollectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary, .ignoresCycle]
    public static let style: NSWindow.StyleMask = [.borderless, .nonactivatingPanel]

    public let displayID: UInt32

    /// a panel with the frame of `display`. It is not on the screen until the guide orders it front.
    public init(display: Display) {
        displayID = display.id
        super.init(contentRect: display.frame, styleMask: Self.style, backing: .buffered, defer: true)
        isOpaque = false
        backgroundColor = .clear
        hasShadow = false
        ignoresMouseEvents = true
        level = Self.level
        collectionBehavior = Self.behavior
        hidesOnDeactivate = false
        isReleasedWhenClosed = false
        animationBehavior = .none
        isMovable = false
        becomesKeyOnlyIfNeeded = true
        setFrame(display.frame, display: false)
    }

    public override var canBecomeKey: Bool { false }
    public override var canBecomeMain: Bool { false }
}

/// The small strip at the top centre of the display in front: the box for the question and one line of state. It does not make
/// Abhyasa the active app. It takes the key window only while the box is open, so you can type; then the focus goes back.
public final class StripPanel: NSPanel {
    public static let style: NSWindow.StyleMask = [.borderless, .nonactivatingPanel, .fullSizeContentView]
    public static let size = NSSize(width: 560, height: 96)
    /// true while the box is open for typing
    public var typing = false

    public init() {
        super.init(contentRect: NSRect(origin: .zero, size: Self.size), styleMask: Self.style, backing: .buffered, defer: true)
        isOpaque = false
        backgroundColor = .clear
        hasShadow = true
        level = NSWindow.Level(rawValue: OverlayPanel.level.rawValue + 1)
        collectionBehavior = OverlayPanel.behavior
        hidesOnDeactivate = false
        isReleasedWhenClosed = false
        animationBehavior = .none
        isMovableByWindowBackground = false
        becomesKeyOnlyIfNeeded = true
    }

    public override var canBecomeKey: Bool { typing }
    public override var canBecomeMain: Bool { false }

    /// the frame of the strip at the top centre of `visible` (a display's visible frame, AppKit global)
    public static func frame(in visible: CGRect, height: CGFloat = size.height) -> CGRect {
        CGRect(x: (visible.midX - size.width / 2).rounded(), y: visible.maxY - height - 12, width: size.width, height: height)
    }
}

public extension Display {
    /// the displays of this Mac, the main display (with the menu bar) first
    @MainActor static var all: [Display] {
        NSScreen.screens.map { s in
            let id = (s.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? NSNumber)?.uint32Value ?? 0
            return Display(id: id, frame: s.frame, scale: s.backingScaleFactor)
        }
    }
}
