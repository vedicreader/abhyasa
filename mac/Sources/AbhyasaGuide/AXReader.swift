import AppKit
import ApplicationServices

/// What the guide read from the front app at the press of its key.
public struct Snapshot: Sendable {
    public var window: FrontWindow?
    public var items: [AXItem]
    public var limit: Limit
    public var ms: Int
}

/// Reads the front app with the Accessibility API: the focused window, the element under the pointer (the target), the selected
/// text and its box, and the visible elements with text. The pattern is Sanketa's AXReader (a timeout of 0.5 s for each read),
/// not its code. Each read is bounded: at most `nodes` elements and `budget` seconds, on a queue of its own, never on the main
/// thread. With no permission, it gives the window frame only (from CGWindowList, which needs no permission).
public enum AXReader {
    public static let nodes = 600, depth = 14
    public static let budget = 0.35
    static let q = DispatchQueue(label: "abhyasa.guide.ax", qos: .userInitiated)
    static let textRoles: Set<String> = ["AXStaticText", "AXTextField", "AXTextArea", "AXHeading", "AXLink", "AXButton", "AXCheckBox",
                                         "AXRadioButton", "AXPopUpButton", "AXMenuItem", "AXCell", "AXImage", "AXTab", "AXComboBox"]

    /// true when this app has Accessibility. It never asks.
    public static var trusted: Bool { AXIsProcessTrusted() }

    /// asks macOS to add Abhyasa to the Accessibility list; only after the learner clicks "Open System Settings"
    public static func askTrust() {
        _ = AXIsProcessTrustedWithOptions([kAXTrustedCheckOptionPrompt.takeUnretainedValue(): true] as CFDictionary)
    }

    /// reads the app with process id `pid`. `pointer` is the mouse in CG global points.
    public static func read(pid: pid_t, app: String, bundle: String, pointer: CGPoint) async -> Snapshot {
        await withCheckedContinuation { c in
            q.async { c.resume(returning: readNow(pid: pid, app: app, bundle: bundle, pointer: pointer)) }
        }
    }

    static func readNow(pid: pid_t, app: String, bundle: String, pointer: CGPoint) -> Snapshot {
        let t0 = Date()
        var window = cgWindow(pid: pid, app: app, bundle: bundle)
        let ms = { Int(Date().timeIntervalSince(t0) * 1000) }
        if AnchorList.neverLook.contains(app) { return Snapshot(window: window, items: [], limit: .neverLook(app), ms: ms()) }
        guard trusted else { return Snapshot(window: window, items: [], limit: .noAccess, ms: ms()) }
        let ax = AXUIElementCreateApplication(pid)
        AXUIElementSetMessagingTimeout(ax, 0.5)
        var items: [AXItem] = []
        if let w: AXUIElement = attr(ax, kAXFocusedWindowAttribute) {
            let f = frame(w)
            let title: String = attr(w, kAXTitleAttribute) ?? ""
            if window == nil, let f { window = FrontWindow(app: app, bundle: bundle, title: title, frame: f) }
            if let f { window?.frame = f }
            if !title.isEmpty { window?.title = title }
        }
        if let focus: AXUIElement = attr(ax, kAXFocusedUIElementAttribute) {
            let i = info(focus)
            if i.secure { return Snapshot(window: window, items: [], limit: .password, ms: ms()) }
            if let s = selection(focus) { items.append(s) }
        }
        if let win = window?.frame, win.contains(pointer), let t = target(at: pointer) { items.append(t) }
        if let w: AXUIElement = attr(ax, kAXFocusedWindowAttribute), let win = window?.frame {
            items += visible(w, in: win, until: t0.addingTimeInterval(budget))
        }
        return Snapshot(window: window, items: items, limit: .none, ms: ms())
    }

    /// the front window of `pid` from CGWindowList: its frame, number and (when macOS gives it) its title
    public static func cgWindow(pid: pid_t, app: String, bundle: String) -> FrontWindow? {
        guard let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]]
        else { return nil }
        for w in list where (w[kCGWindowOwnerPID as String] as? pid_t) == pid && (w[kCGWindowLayer as String] as? Int) == 0 {
            guard let b = w[kCGWindowBounds as String] as? NSDictionary, let r = CGRect(dictionaryRepresentation: b) else { continue }
            if r.width < 40 || r.height < 40 { continue }
            return FrontWindow(app: app, bundle: bundle, title: w[kCGWindowName as String] as? String ?? "", frame: r,
                               windowID: w[kCGWindowNumber as String] as? UInt32 ?? 0)
        }
        return nil
    }

    /// the CG frame of window number `id` now, or nil when it is not on the screen
    public static func bounds(of id: UInt32) -> CGRect? {
        guard id != 0, let list = CGWindowListCopyWindowInfo([.optionIncludingWindow], CGWindowID(id)) as? [[String: Any]],
              let w = list.first, (w[kCGWindowIsOnscreen as String] as? Bool) == true,
              let b = w[kCGWindowBounds as String] as? NSDictionary else { return nil }
        return CGRect(dictionaryRepresentation: b)
    }

    // --- the reads ---------------------------------------------------------------------------------------------------------
    static func attr<T>(_ e: AXUIElement, _ name: String) -> T? {
        var v: CFTypeRef?
        guard AXUIElementCopyAttributeValue(e, name as CFString, &v) == .success, let v else { return nil }
        if T.self == AXUIElement.self { return CFGetTypeID(v) == AXUIElementGetTypeID() ? (v as! T) : nil }
        return v as? T
    }

    static func frame(_ e: AXUIElement) -> CGRect? {
        var p = CGPoint.zero, s = CGSize.zero
        guard let pv: AXValue = axValue(e, kAXPositionAttribute), let sv: AXValue = axValue(e, kAXSizeAttribute),
              AXValueGetValue(pv, .cgPoint, &p), AXValueGetValue(sv, .cgSize, &s) else { return nil }
        return CGRect(origin: p, size: s)
    }

    static func axValue(_ e: AXUIElement, _ name: String) -> AXValue? {
        var v: CFTypeRef?
        guard AXUIElementCopyAttributeValue(e, name as CFString, &v) == .success, let v, CFGetTypeID(v) == AXValueGetTypeID() else { return nil }
        return (v as! AXValue)
    }

    struct Info { var role = "", subrole = "", text = "", frame: CGRect?, secure = false }

    /// role, subrole, text and frame in one call to the app
    static func info(_ e: AXUIElement) -> Info {
        let names = [kAXRoleAttribute, kAXSubroleAttribute, kAXTitleAttribute, kAXValueAttribute, kAXDescriptionAttribute,
                     kAXPositionAttribute, kAXSizeAttribute] as CFArray
        var out: CFArray?
        var i = Info()
        guard AXUIElementCopyMultipleAttributeValues(e, names, [], &out) == .success, let vals = out as? [AnyObject], vals.count == 7 else { return i }
        i.role = vals[0] as? String ?? ""
        i.subrole = vals[1] as? String ?? ""
        let title = vals[2] as? String ?? "", desc = vals[4] as? String ?? ""
        i.secure = AnchorList.isSecret(role: i.role, subrole: i.subrole, name: title + " " + desc)
        let value = i.secure ? "" : (vals[3] as? String).map { String($0.prefix(2000)) } ?? ""
        i.text = [title, value, desc].first { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty } ?? ""
        var p = CGPoint.zero, s = CGSize.zero
        if CFGetTypeID(vals[5]) == AXValueGetTypeID(), CFGetTypeID(vals[6]) == AXValueGetTypeID(),
           AXValueGetValue(vals[5] as! AXValue, .cgPoint, &p), AXValueGetValue(vals[6] as! AXValue, .cgSize, &s) {
            i.frame = CGRect(origin: p, size: s)
        }
        return i
    }

    /// the selected text of `e` and the box of the selection
    static func selection(_ e: AXUIElement) -> AXItem? {
        guard let rv: AXValue = axValue(e, kAXSelectedTextRangeAttribute) else { return nil }
        var r = CFRange()
        guard AXValueGetValue(rv, .cfRange, &r), r.length > 0 else { return nil }
        let text: String = attr(e, kAXSelectedTextAttribute) ?? ""
        var b: CFTypeRef?
        guard AXUIElementCopyParameterizedAttributeValue(e, kAXBoundsForRangeParameterizedAttribute as CFString, rv, &b) == .success,
              let b, CFGetTypeID(b) == AXValueGetTypeID() else { return nil }
        var box = CGRect.zero
        guard AXValueGetValue(b as! AXValue, .cgRect, &box), !box.isEmpty else { return nil }
        return AXItem(role: "AXStaticText", text: text, frame: box, near: .selection)
    }

    /// the smallest thing under the pointer that has text or is an image: the element there, or one of its two parents
    static func target(at p: CGPoint) -> AXItem? {
        let sys = AXUIElementCreateSystemWide()
        AXUIElementSetMessagingTimeout(sys, 0.5)
        var hit: AXUIElement?
        guard AXUIElementCopyElementAtPosition(sys, Float(p.x), Float(p.y), &hit) == .success, var e = hit else { return nil }
        for _ in 0..<3 {
            let i = info(e)
            if i.secure { return nil }
            if let f = i.frame, !i.text.isEmpty || i.role == "AXImage" {
                return AXItem(role: i.role, subrole: i.subrole, text: i.text, frame: f, near: .target)
            }
            guard let up: AXUIElement = attr(e, kAXParentAttribute) else { break }
            e = up
        }
        return nil
    }

    /// the elements with text inside the window, breadth first, bounded by count, depth and time
    static func visible(_ root: AXUIElement, in win: CGRect, until end: Date) -> [AXItem] {
        var out: [AXItem] = [], todo: [(AXUIElement, Int)] = [(root, 0)], seen = 0
        while !todo.isEmpty, seen < nodes, Date() < end {
            let (e, d) = todo.removeFirst()
            seen += 1
            let i = info(e)
            if d > 0, textRoles.contains(i.role), let f = i.frame, f.intersects(win), !f.isEmpty {
                out.append(AXItem(role: i.role, subrole: i.subrole, text: i.text, frame: f, secure: i.secure))
            }
            if let f = i.frame, d > 0, !f.intersects(win) { continue }   // a part out of the window: its children are too
            guard d < depth else { continue }
            let kids: [AXUIElement] = attr(e, kAXVisibleChildrenAttribute) ?? attr(e, kAXChildrenAttribute) ?? []
            todo += kids.prefix(80).map { ($0, d + 1) }
        }
        return out
    }
}
