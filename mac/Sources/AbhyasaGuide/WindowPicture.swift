import AppKit
import CoreGraphics
import ScreenCaptureKit
import ImageIO
import UniformTypeIdentifiers

/// One picture of the window in front, for a later vision board (design 4.6). It is off by default (the `guide.vision`
/// setting). It never asks for Screen Recording: with no permission, it gives nothing. The picture stays in memory for one
/// call; it is never written to disk or a log. The guide's own panels are not in it, because the filter holds one window only.
public enum WindowPicture {
    public enum Failure: Error, Equatable { case off, noPermission, noWindow }

    /// the flag: true only after the learner turns on vision boards
    public static var enabled: Bool { UserDefaults.standard.bool(forKey: "guide.vision") }

    /// true when Screen Recording is on for this app. It never asks.
    public static var granted: Bool { CGPreflightScreenCaptureAccess() }

    /// a JPEG of window number `id`, made to fit 1280 by 800 points of the model
    public static func take(windowID id: UInt32, scale: CGFloat) async throws -> (jpeg: Data, size: CGSize) {
        guard enabled else { throw Failure.off }
        guard granted else { throw Failure.noPermission }   // SCShareableContent would ask, so check first
        let all = try await SCShareableContent.excludingDesktopWindows(true, onScreenWindowsOnly: true)
        guard let w = all.windows.first(where: { $0.windowID == id }) else { throw Failure.noWindow }
        let size = Geometry.captureSize(window: w.frame.size, scale: scale)
        let c = SCStreamConfiguration()
        c.width = Int(size.width)
        c.height = Int(size.height)
        c.showsCursor = false
        let img = try await SCScreenshotManager.captureImage(contentFilter: SCContentFilter(desktopIndependentWindow: w), configuration: c)
        return (jpeg(img) ?? Data(), size)
    }

    /// `img` as JPEG bytes in memory
    public static func jpeg(_ img: CGImage, quality: Double = 0.8) -> Data? {
        let d = NSMutableData()
        guard let dst = CGImageDestinationCreateWithData(d, UTType.jpeg.identifier as CFString, 1, nil) else { return nil }
        CGImageDestinationAddImage(dst, img, [kCGImageDestinationLossyCompressionQuality: quality] as CFDictionary)
        return CGImageDestinationFinalize(dst) ? d as Data : nil
    }
}
