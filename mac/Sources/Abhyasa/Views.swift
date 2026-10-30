import SwiftUI
import AppKit
import WebKit
import AbhyasaCore
import AbhyasaGuide

struct WebView: NSViewRepresentable {
    let web: WebController
    func makeNSView(context: Context) -> WKWebView { web.view }
    func updateNSView(_ v: WKWebView, context: Context) {}
}

struct MainView: View {
    let model: AppModel
    @Environment(\.openSettings) private var openSettings

    var body: some View {
        phase.onAppear {
            // the guide's menu bar mark and its first-use sheet open Settings with this
            Guide.shared.openSettings = { [openSettings] in NSApp.activate(); openSettings() }
        }
    }

    @ViewBuilder var phase: some View {
        switch model.supervisor.phase {
        case .ready:
            WebView(web: model.web)
        case .syncing(let line):
            FirstRunView(line: line)
        case .needsUV:
            NeedsUVView { model.start() }
        case .starting, .idle:
            VStack(spacing: 12) {
                ProgressView()
                Text("Starting abhyasa").foregroundStyle(.secondary)
            }.frame(maxWidth: .infinity, maxHeight: .infinity)
        case .failed(let message):
            FailedView(message: message) { model.start() }
        }
    }
}

/// The first launch: uv gets Python and the packages one time.
struct FirstRunView: View {
    let line: String

    var body: some View {
        VStack(spacing: 16) {
            Text("Setting up abhyasa").font(.title2)
            Text("The app gets Python and the abhyasa packages one time. This step needs the internet. It can take some minutes.")
                .multilineTextAlignment(.center).foregroundStyle(.secondary).frame(maxWidth: 420)
            ProgressView().progressViewStyle(.linear).frame(width: 320)
            Text(line).font(.callout.monospaced()).foregroundStyle(.secondary).lineLimit(1).truncationMode(.middle)
                .frame(maxWidth: 480)
        }.padding(40).frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

/// No uv on this Mac. The cask installs it; this is for a copy of the app from the zip.
struct NeedsUVView: View {
    let retry: () -> Void

    var body: some View {
        VStack(spacing: 16) {
            Text("abhyasa needs uv").font(.title2)
            Text("The app uses uv to get Python and the abhyasa packages. Install uv in Terminal. Then click Retry.")
                .multilineTextAlignment(.center).foregroundStyle(.secondary).frame(maxWidth: 420)
            HStack {
                Text(ChildEnv.uvInstall).font(.body.monospaced()).textSelection(.enabled)
                Button("Copy") {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(ChildEnv.uvInstall, forType: .string)
                }
            }
            Button("Retry", action: retry).keyboardShortcut(.defaultAction)
        }.padding(40).frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct FailedView: View {
    let message: String
    let again: () -> Void

    var body: some View {
        VStack(spacing: 16) {
            Text("abhyasa stopped").font(.title2)
            ScrollView {
                Text(message).font(.callout.monospaced()).textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading)
            }.frame(maxWidth: 560, maxHeight: 220)
            Button("Start Again", action: again).keyboardShortcut(.defaultAction)
        }.padding(40).frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

/// Model, speech engine and vault. Apply saves them and starts the server again.
struct SettingsView: View {
    let model: AppModel
    @State private var s = Prefs.load()
    @State private var typing = false
    private let guide = Guide.shared.status
    private static let other = "\u{1}other"

    /// the list item: the model, or "Type another model id" for an id that the list does not have
    private var pick: Binding<String> {
        Binding(get: { typing || !ServerSettings.isListed(s.model) ? Self.other : s.model },
                set: { v in typing = v == Self.other; if !typing { s.model = v } })
    }

    var body: some View {
        Form {
            Picker("Model", selection: pick) {
                Text("Default: Claude Sonnet").tag("")
                ForEach(ServerSettings.models, id: \.id) { Text($0.name).tag($0.id) }
                Divider()
                Text("Type another model id…").tag(Self.other)
            }
            if pick.wrappedValue == Self.other {
                TextField("Model id", text: $s.model, prompt: Text(ServerSettings.defaultModel))
            }
            Text("The default model for the tutor. The Claude models use the claude command. The Settings page in the app can set a model for each task.")
                .font(.caption).foregroundStyle(.secondary)
            Picker("Speech engine", selection: $s.stt) {
                Text("From the Settings page").tag("")
                ForEach(ServerSettings.engines, id: \.self) { Text($0) }
            }
            Text("Choose the speech model on the Settings page in the app. An engine here takes its place.").font(.caption).foregroundStyle(.secondary)
            HStack {
                TextField("Vault", text: $s.vault)
                Button("Choose…") { choose() }
            }
            // off until the learner pushes Start in the first-use sheet; turning it on shows that sheet the first time
            Toggle("Screen guide over other apps", isOn: Binding(get: { guide.on }, set: { Guide.shared.setEnabled($0) }))
            Text("Tap \(GuideText.key) to type a question about the window in front. Hold \(GuideText.key) to say it. The tutor draws the answer over the window. Esc stops it. The guide is off until you turn it on.")
                .font(.caption).foregroundStyle(.secondary)
            HStack {
                Spacer()
                Button("Default Values") { s = ServerSettings(); typing = false }
                Button("Apply") { model.apply(s) }.keyboardShortcut(.defaultAction).disabled(s == model.supervisor.settings)
            }
        }
        .padding(20).frame(width: 520)
    }

    private func choose() {
        let p = NSOpenPanel()
        p.canChooseFiles = true
        p.canChooseDirectories = false
        p.allowsMultipleSelection = false
        let home = NSHomeDirectory()
        p.directoryURL = URL(fileURLWithPath: ChildEnv.expand(s.vault, home: home)).deletingLastPathComponent()
        guard p.runModal() == .OK, let u = p.url else { return }
        s.vault = u.path.hasPrefix(home + "/") ? "~" + u.path.dropFirst(home.count) : u.path
    }
}
