import CoreGraphics

/// One display, as AppKit gives it: its frame in AppKit global points (origin at the bottom left of the main display) and its
/// scale factor. The first display in a list is the main display, the one with the menu bar.
public struct Display: Equatable, Sendable {
    public var id: UInt32
    public var frame: CGRect
    public var scale: CGFloat

    public init(id: UInt32, frame: CGRect, scale: CGFloat) {
        self.id = id
        self.frame = frame
        self.scale = scale
    }
}

/// The conversions between the spaces of design section 4.7. Accessibility and CGWindowList give frames in CG global points:
/// the origin is the top left of the main display and y goes down. AppKit uses the bottom left of the main display, and y goes
/// up. A web view in a panel uses the top left of the panel, and y goes down. The scale factor is never used for a position.
public enum Geometry {
    /// a CG global rect (AX, CGWindowList) in AppKit global points; `mainHeight` is the height of the main display
    public static func appKit(fromCG r: CGRect, mainHeight: CGFloat) -> CGRect {
        CGRect(x: r.minX, y: mainHeight - r.maxY, width: r.width, height: r.height)
    }

    /// an AppKit global rect in CG global points (the same flip, the other way)
    public static func cg(fromAppKit r: CGRect, mainHeight: CGFloat) -> CGRect {
        CGRect(x: r.minX, y: mainHeight - r.maxY, width: r.width, height: r.height)
    }

    /// an AppKit global rect in the CSS pixels of a web view that fills a panel with the frame `panel`
    public static func panel(fromAppKit r: CGRect, panel: CGRect) -> CGRect {
        CGRect(x: r.minX - panel.minX, y: panel.maxY - r.maxY, width: r.width, height: r.height)
    }

    /// a CG global rect in the CSS pixels of the panel on `display`
    public static func panel(fromCG r: CGRect, display: Display, mainHeight: CGFloat) -> CGRect {
        panel(fromAppKit: appKit(fromCG: r, mainHeight: mainHeight), panel: display.frame)
    }

    /// the height of the main display, which all flips use; 0 with no display
    public static func mainHeight(_ displays: [Display]) -> CGFloat { displays.first?.frame.height ?? 0 }

    /// the display that holds the centre of `r` (AppKit global), else the display with the largest part of it, else the main one
    public static func display(for r: CGRect, in displays: [Display]) -> Display? {
        let c = CGPoint(x: r.midX, y: r.midY)
        if let d = displays.first(where: { $0.frame.contains(c) }) { return d }
        let best = displays.max { area($0.frame.intersection(r)) < area($1.frame.intersection(r)) }
        if let best, area(best.frame.intersection(r)) > 0 { return best }
        return displays.first
    }

    /// the parts of `r` (AppKit global) on each display, for a mark that crosses two displays
    public static func split(_ r: CGRect, in displays: [Display]) -> [(Display, CGRect)] {
        displays.compactMap { d in
            let p = d.frame.intersection(r)
            return p.isNull || p.isEmpty ? nil : (d, p)
        }
    }

    /// the pixel size of a picture of a window: the window in backing pixels, made smaller to fit in `most` with the same
    /// shape (1280 by 800 is the size for 16:10 that the model reads best). It is never larger than the window's pixels.
    public static func captureSize(window: CGSize, scale: CGFloat, most: CGSize = CGSize(width: 1280, height: 800)) -> CGSize {
        let px = CGSize(width: window.width * scale, height: window.height * scale)
        guard px.width > 0, px.height > 0 else { return .zero }
        let k = min(1, most.width / px.width, most.height / px.height)
        return CGSize(width: (px.width * k).rounded(), height: (px.height * k).rounded())
    }

    /// a box in picture pixels in CG global points, for a picture of the window with the CG frame `window`
    public static func cg(fromPicture b: CGRect, picture: CGSize, window: CGRect) -> CGRect {
        guard picture.width > 0, picture.height > 0 else { return .null }
        let kx = window.width / picture.width, ky = window.height / picture.height
        return CGRect(x: window.minX + b.minX * kx, y: window.minY + b.minY * ky, width: b.width * kx, height: b.height * ky)
    }

    static func area(_ r: CGRect) -> CGFloat { r.isNull ? 0 : r.width * r.height }
}
