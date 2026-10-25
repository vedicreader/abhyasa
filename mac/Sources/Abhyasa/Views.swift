import SwiftUI
import AppKit
import WebKit
import AbhyasaCore

struct WebView: NSViewRepresentable {
    let web: WebController
    func makeNSView(context: Context) -> WKWebView { web.view }
    func updateNSView(_ v: WKWebView, context: Context) {}
}

struct MainView: View {
    let model: AppModel

    var body: some View {
        switch model.supervisor.phase {
        case .ready:
            WebView(web: model.web)
        case .syncing(let line):
            FirstRunView(line: line)
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
            Text("The app gets Python and the abhyasa packages one time. This needs the internet and can take some minutes.")
                .multilineTextAlignment(.center).foregroundStyle(.secondary).frame(maxWidth: 420)
            ProgressView().progressViewStyle(.linear).frame(width: 320)
            Text(line).font(.callout.monospaced()).foregroundStyle(.secondary).lineLimit(1).truncationMode(.middle)
                .frame(maxWidth: 480)
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

    var body: some View {
        Form {
            TextField("Model", text: $s.model, prompt: Text(ServerSettings.defaultModel))
            Text("A rishi model name. The default, claude/sonnet, uses the claude command.").font(.caption).foregroundStyle(.secondary)
            Picker("Speech engine", selection: $s.stt) {
                ForEach(ServerSettings.engines, id: \.self) { Text($0) }
            }
            Text("whisper needs mlx-audio, which the app does not install.").font(.caption).foregroundStyle(.secondary)
            HStack {
                TextField("Vault", text: $s.vault)
                Button("Choose…") { choose() }
            }
            HStack {
                Spacer()
                Button("Default Values") { s = ServerSettings() }
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
