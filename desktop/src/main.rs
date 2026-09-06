// Atlas desktop shell (Owner idea #30 + epic #210): a native Tauri 2 window over Atlas.
//
// When a bundled `atlas-server` binary is present (#210e), the shell launches it on startup —
// Django on a per-user SQLite file (#266), no database server, no Docker — waits for it to
// answer, then opens the window at it, and stops it when the app quits. With no bundled
// server (dev), it falls back to ATLAS_URL / a server you run yourself.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod localfs;
mod server;
mod external;
mod terminal;
mod updater;

use std::path::PathBuf;
use std::process::Child;
use std::sync::Mutex;
use std::time::Duration;

use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};

/// Holds the spawned server process so it can be stopped on exit.
struct ServerProc(Mutex<Option<Child>>);

fn atlas_url() -> String {
    std::env::var("ATLAS_URL").unwrap_or_else(|_| "http://localhost:8000/".to_string())
}

/// Write an HTML page into the data dir and return a `file://` URL the window can load.
/// We render the splash + the failure diagnostic as local files so the user always sees an
/// Atlas-owned page, never WebView2's blank "can't reach this page" (#263).
fn local_page_url(data_dir: &std::path::Path, name: &str, html: &str) -> Option<tauri::Url> {
    let path = data_dir.join(name);
    std::fs::write(&path, html).ok()?;
    tauri::Url::from_file_path(&path).ok()
}

/// The "starting up" splash shown while the bundled server boots (first launch runs migrate +
/// collectstatic, which can take a minute). Pure HTML/CSS — no script/network — so it always
/// renders.
fn splash_html() -> String {
    r#"<!doctype html><html><head><meta charset="utf-8"><title>Atlas</title>
<style>body{font-family:system-ui,sans-serif;background:#fafaf9;color:#1c1917;display:flex;
align-items:center;justify-content:center;height:100vh;margin:0}.box{text-align:center;max-width:30rem}
.dot{width:12px;height:12px;border-radius:50%;background:#4f46e5;display:inline-block;animation:p 1s infinite}
@keyframes p{0%,100%{opacity:.3}50%{opacity:1}}h1{font-weight:600;font-size:1.3rem}p{color:#78716c}</style>
</head><body><div class="box"><div class="dot"></div><h1>Starting Atlas…</h1>
<p>The first launch sets up its local database and assets — this can take up to a minute. The
window will open automatically when it's ready.</p></div></body></html>"#
        .to_string()
}

/// The failure page: the actual server log, the data-dir path, and the most common fixes.
/// Shown in-window when the server crashes or never binds, so a failure self-reports instead
/// of leaving us debugging blind.
fn diagnostic_html(data_dir: &std::path::Path, reason: &str, port: u16) -> String {
    let server_log = server::escape_html(&server::tail_file(
        &data_dir.join("atlas-server.log"),
        12000,
    ));
    let dir = server::escape_html(&data_dir.display().to_string());
    format!(
        r#"<!doctype html><html><head><meta charset="utf-8"><title>Atlas — startup problem</title>
<style>body{{font-family:system-ui,sans-serif;background:#fafaf9;color:#1c1917;margin:0;padding:2rem;
line-height:1.5}}h1{{font-size:1.4rem}}h2{{font-size:.95rem;text-transform:uppercase;letter-spacing:.04em;
color:#78716c;margin-top:1.5rem}}pre{{background:#1c1917;color:#e7e5e4;padding:1rem;border-radius:.4rem;
overflow:auto;font-size:.8rem;white-space:pre-wrap;word-break:break-word}}.fix{{background:#eef2ff;
border:1px solid #c7d2fe;border-radius:.4rem;padding:1rem;margin:1rem 0}}code{{background:#f5f5f4;
padding:.1rem .3rem;border-radius:.2rem}}li{{margin:.3rem 0}}</style></head><body>
<h1>Atlas couldn't start</h1>
<p>{reason}. The log below says where it stopped — please send this whole page (or the
<code>atlas-server.log</code> file in the folder named below) so we can fix it.</p>
<div class="fix"><strong>Things to check first:</strong><ul>
<li>The server should have listened on <code>127.0.0.1:{port}</code>. If the log ends in an
"address already in use" error, another program grabbed the port between the check and the
start — just relaunch Atlas.</li>
<li>On Windows, security software sometimes quarantines <code>atlas-server.exe</code> as an
unknown program. If the log is empty and the server never ran, allow it and relaunch.</li>
<li>The data folder must be writable. Atlas keeps its database (<code>atlas.sqlite3</code>),
uploaded files, and this log there.</li></ul></div>
<h2>Data folder</h2><pre>{dir}</pre>
<h2>atlas-server.log</h2><pre>{server_log}</pre>
</body></html>"#
    )
}

/// A bundled one-folder PyInstaller binary: `<resource dir>/<name>/<name>[.exe]`.
fn bundled_bin(app: &tauri::App, name: &str) -> Option<PathBuf> {
    let res = app.path().resource_dir().ok()?;
    let exe = if cfg!(windows) {
        format!("{name}.exe")
    } else {
        name.to_string()
    };
    let bin = res.join(name).join(exe);
    bin.exists().then_some(bin)
}

/// Find the frozen server binary: an env override (dev/CI), else the bundled resource.
/// Returns None when there's nothing to launch (dev with an externally-run server).
fn resolve_server(app: &tauri::App) -> Option<PathBuf> {
    if let Ok(bin) = std::env::var("ATLAS_SERVER_BIN") {
        return Some(PathBuf::from(bin));
    }
    bundled_bin(app, "atlas-server")
}

/// Find the frozen MCP server (`atlas-mcp`) that ships next to the app: an env override, else
/// the bundled resource. Handed to the server so the "Connect Claude Code" page can print the
/// exact `claude mcp add atlas -- <path>` line for this machine.
fn resolve_mcp(app: &tauri::App) -> Option<PathBuf> {
    if let Ok(bin) = std::env::var("ATLAS_MCP_BIN") {
        return Some(PathBuf::from(bin));
    }
    bundled_bin(app, "atlas-mcp")
}

fn main() {
    let app = tauri::Builder::default()
        // Single instance (must be the FIRST plugin): a second launch focuses the existing
        // window and exits — critical here, since each instance would start its own server
        // against the same SQLite file.
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(w) = app.get_webview_window("main") {
                let _ = w.unminimize();
                let _ = w.set_focus();
            }
        }))
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(terminal::TerminalState::default())
        .manage(ServerProc(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![
            terminal::terminal_spawn,
            terminal::terminal_write,
            terminal::terminal_resize,
            terminal::terminal_kill,
            external::open_external,
            localfs::open_local_file,
            updater::check_for_updates,
            updater::check_update,
            updater::install_update,
            updater::restart_app
        ])
        .setup(|app| {
            // ATLAS_PORT pins the port; otherwise prefer 8000 but step aside to a free port when
            // something else (a dev `runserver`, another app) already holds it.
            let port: u16 = match std::env::var("ATLAS_PORT")
                .ok()
                .and_then(|p| p.parse().ok())
            {
                Some(p) => p,
                None => server::choose_port(8000).unwrap_or(8000),
            };

            // per-user data dir holds the SQLite db, media, and the log the diagnostic page
            // surfaces (#263).
            let data_dir = app
                .path()
                .app_data_dir()
                .unwrap_or_else(|_| std::env::temp_dir());
            let _ = std::fs::create_dir_all(&data_dir);

            // launch the bundled server unless an external one was specified via ATLAS_URL
            let mut launched_bundled = false;
            let url = if std::env::var("ATLAS_URL").is_ok() {
                atlas_url()
            } else if let Some(bin) = resolve_server(app) {
                let mcp = resolve_mcp(app);
                match server::spawn(&bin, &data_dir, port, mcp.as_deref()) {
                    Ok(child) => {
                        app.state::<ServerProc>().0.lock().unwrap().replace(child);
                        launched_bundled = true;
                        format!("http://127.0.0.1:{port}/")
                    }
                    Err(_) => atlas_url(),
                }
            } else {
                atlas_url()
            };

            let parsed: tauri::Url = url.parse().expect("server URL is not valid");
            // security hardening (AUDIT #15, #160): the shell only navigates within the local
            // Atlas origin (or our own file:// splash/diagnostic pages), so a compromised page
            // can't steer the window off-origin.
            let allowed_host = parsed.host_str().unwrap_or("localhost").to_string();

            // Open on a local splash page while the bundled server boots, so the window never
            // shows WebView2's blank "can't reach this page" (#263). External/dev mode opens
            // straight at the server.
            let initial_url = if launched_bundled {
                local_page_url(&data_dir, "starting.html", &splash_html())
                    .unwrap_or_else(|| parsed.clone())
            } else {
                parsed.clone()
            };
            let window = WebviewWindowBuilder::new(app, "main", WebviewUrl::External(initial_url))
                .title("Atlas")
                .inner_size(1400.0, 900.0)
                .min_inner_size(900.0, 600.0)
                .on_navigation(move |target| {
                    target.scheme() == "file"
                        || matches!(target.host_str(), Some(h) if h == allowed_host)
                })
                .build()?;
            let _ = window.set_focus();

            // The bundled server's FIRST launch runs migrate + collectstatic and can take a
            // while, so we poll in the background: navigate to the app the moment the
            // server answers, OR — if the server process exits or never binds — navigate to a
            // diagnostic page showing the real logs, instead of leaving the user stuck (#263).
            if launched_bundled {
                let win = window.clone();
                let server_url = parsed.clone();
                let dd = data_dir.clone();
                let handle = app.handle().clone();
                std::thread::spawn(move || {
                    let deadline = std::time::Instant::now() + Duration::from_secs(600);
                    loop {
                        if server::wait_for_port(port, Duration::from_millis(800)) {
                            // a beat for waitress to begin serving HTTP after the port opens
                            std::thread::sleep(Duration::from_millis(750));
                            let _ = win.navigate(server_url);
                            return;
                        }
                        let exited = {
                            let state = handle.state::<ServerProc>();
                            let mut guard = state.0.lock().unwrap();
                            match guard.as_mut() {
                                Some(child) => matches!(child.try_wait(), Ok(Some(_))),
                                None => false,
                            }
                        };
                        let reason = if exited {
                            Some("the Atlas server process exited during startup")
                        } else if std::time::Instant::now() >= deadline {
                            Some("the Atlas server did not start within 10 minutes")
                        } else {
                            None
                        };
                        if let Some(reason) = reason {
                            if let Some(u) = local_page_url(
                                &dd,
                                "diagnostic.html",
                                &diagnostic_html(&dd, reason, port),
                            ) {
                                let _ = win.navigate(u);
                            }
                            return;
                        }
                    }
                });
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("failed to launch the Atlas desktop shell");

    app.run(|handle, event| {
        if let RunEvent::Exit = event {
            // stop the bundled server on quit (SQLite needs no further teardown)
            if let Some(mut child) = handle.state::<ServerProc>().0.lock().unwrap().take() {
                let _ = child.kill();
            }
        }
    });
}
