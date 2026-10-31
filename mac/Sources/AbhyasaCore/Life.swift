import Foundation

/// How long the app runs: as Leela, until you quit it. Closing the window leaves the app, its menu bar mark and the server running.
public enum Life {
    /// the answer to `applicationShouldTerminateAfterLastWindowClosed`: never, so a closed window never stops the server or research
    public static let quitOnLastWindow = false

    /// whether a click on the Dock icon opens the main window again: only when no window shows
    public static func reopen(visibleWindows: Bool) -> Bool { !visibleWindows }
}
