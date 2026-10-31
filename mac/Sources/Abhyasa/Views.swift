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
                Text("Starting Abhyasa…").foregroundStyle(.secondary)
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
        VStack(spacing: 24) {
            Header(title: "Setting up Abhyasa",
                   text: "Abhyasa gets Python and its packages one time. This step needs the internet. It can take a few minutes.")
            VStack(spacing: 8) {
                ProgressView().progressViewStyle(.linear).frame(width: 320)
                Text(line).font(.callout.monospaced()).foregroundStyle(.secondary).lineLimit(1).truncationMode(.middle)
                    .frame(maxWidth: 480)
            }
        }.padding(40).frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

/// No uv on this Mac. The cask installs it; this is for a copy of the app from the zip.
struct NeedsUVView: View {
    let retry: () -> Void

    var body: some View {
        VStack(spacing: 24) {
            Header(title: "Abhyasa needs uv",
                   text: "Abhyasa uses uv to get Python and its packages. To install uv, run this command in Terminal. Then click Retry.")
            HStack(spacing: 12) {
                Text(ChildEnv.uvInstall).font(.body.monospaced()).textSelection(.enabled)
                Button("Copy") {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(ChildEnv.uvInstall, forType: .string)
                }.buttonStyle(.borderless)
            }
            Button("Retry", action: retry).buttonStyle(.borderedProminent).keyboardShortcut(.defaultAction)
        }.padding(40).frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct FailedView: View {
    let message: String
    let again: () -> Void

    var body: some View {
        VStack(spacing: 24) {
            Header(title: "Abhyasa stopped", text: "The last lines of the log:")
            ScrollView {
                Text(message).font(.callout.monospaced()).textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading)
            }.frame(maxWidth: 560, maxHeight: 220)
            Button("Start again", action: again).buttonStyle(.borderedProminent).keyboardShortcut(.defaultAction)
        }.padding(40).frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

/// The title and the one plain paragraph at the top of each window view.
struct Header: View {
    let title: String
    let text: String

    var body: some View {
        VStack(spacing: 8) {
            Text(title).font(.title.weight(.semibold))
            Text(text).font(.body).multilineTextAlignment(.center).foregroundStyle(.secondary).frame(maxWidth: 420)
        }
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
            Section("Tutor") {
                Picker("Model", selection: pick) {
                    Text("Default: Claude Sonnet").tag("")
                    ForEach(ServerSettings.models, id: \.id) { Text($0.name).tag($0.id) }
                    Divider()
                    Text("Type another model id…").tag(Self.other)
                }
                if pick.wrappedValue == Self.other {
                    TextField("Model id", text: $s.model, prompt: Text(ServerSettings.defaultModel))
                }
                Note("The model that the tutor uses. Claude models need the claude command. To set a model for each task, use the Settings page in the app.")
                Picker("Speech engine", selection: $s.stt) {
                    Text("From the Settings page").tag("")
                    ForEach(ServerSettings.engines, id: \.self) { Text($0) }
                }
                Note("The Settings page in the app sets the speech engine. An engine that you choose here replaces it.")
                HStack {
                    TextField("Vault", text: $s.vault)
                    Button("Choose…") { choose() }
                }
            }
            Section("Screen guide") {
                // off until the learner pushes Start in the first-use sheet; turning it on shows that sheet the first time
                Toggle("Screen guide over other apps", isOn: Binding(get: { guide.on }, set: { Guide.shared.setEnabled($0) }))
                Note("Tap \(GuideText.key) to type a question about the window in front. Hold \(GuideText.key) to say it. The tutor draws the answer over the window. Esc stops it. The guide is off until you turn it on.")
            }
            HStack(spacing: 12) {
                Spacer()
                Button("Use the defaults") { s = ServerSettings(); typing = false }.buttonStyle(.borderless)
                Button("Apply") { model.apply(s) }.buttonStyle(.borderedProminent).keyboardShortcut(.defaultAction)
                    .disabled(s == model.supervisor.settings)
            }.padding(.top, 8)
        }
        .padding(24).frame(width: 520)
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

/// A quiet line under a setting, at a size that stays legible.
struct Note: View {
    let text: String
    init(_ text: String) { self.text = text }
    var body: some View { Text(text).font(.callout).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true) }
}
