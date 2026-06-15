// Atlas desktop shell (Owner idea #30 + epic #210): a native Tauri 2 window over Atlas.
//
// When a bundled `atlas-server` binary is present (#210e), the shell launches it on startup —
// it auto-starts its own Postgres and serves Atlas locally — waits for it to answer, then
// opens the window at it, and stops it when the app quits. With no bundled server (dev), it
// falls back to ATLAS_URL / a server you run yourself.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod localfs;
mod server;
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

/// Find the frozen server binary + the bundled Postgres bin dir: an env override (dev/CI),
/// else the bundled resources. Returns None when there's nothing to launch (dev with an
/// externally-run server).
fn resolve_server(app: &tauri::App) -> Option<(PathBuf, Option<PathBuf>)> {
    if let Ok(bin) = std::env::var("ATLAS_SERVER_BIN") {
        let pg = std::env::var("ATLAS_PG_BIN").ok().map(PathBuf::from);
        return Some((PathBuf::from(bin), pg));
    }
    let res = app.path().resource_dir().ok()?;
    let exe = if cfg!(windows) { "atlas-server.exe" } else { "atlas-server" };
    let bin = res.join("atlas-server").join(exe);
    if !bin.exists() {
        return None;
    }
    // pass the pg root; the server's _pg_bin resolves either <pg> or <pg>/bin, with .exe
    let pg = res.join("pg");
    Some((bin, pg.exists().then_some(pg)))
}

fn main() {
    let app = tauri::Builder::default()
        // Single instance (must be the FIRST plugin): a second launch focuses the existing
        // window and exits — critical here, since each instance would start its own Postgres
        // on the same data dir and corrupt it.
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
            localfs::open_local_file,
            updater::check_for_updates,
            updater::restart_app
        ])
        .setup(|app| {
            let port: u16 = std::env::var("ATLAS_PORT")
                .ok()
                .and_then(|p| p.parse().ok())
                .unwrap_or(8000);

            // launch the bundled server unless an external one was specified via ATLAS_URL
            let mut launched_bundled = false;
            let url = if std::env::var("ATLAS_URL").is_ok() {
                atlas_url()
            } else if let Some((bin, pg)) = resolve_server(app) {
                let data_dir = app
                    .path()
                    .app_data_dir()
                    .unwrap_or_else(|_| std::env::temp_dir());
                let _ = std::fs::create_dir_all(&data_dir);
                match server::spawn(&bin, &data_dir, pg.as_deref(), port) {
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
            // Atlas origin, so a compromised page can't steer the window off-origin.
            let allowed_host = parsed.host_str().unwrap_or("localhost").to_string();
            let window =
                WebviewWindowBuilder::new(app, "main", WebviewUrl::External(parsed.clone()))
                    .title("Atlas")
                    .inner_size(1400.0, 900.0)
                    .min_inner_size(900.0, 600.0)
                    .on_navigation(move |target| {
                        matches!(target.host_str(), Some(h) if h == allowed_host)
                    })
                    .build()?;
            let _ = window.set_focus();

            // The bundled server's FIRST launch runs initdb + migrate + collectstatic and can
            // take a while on a slow machine, so the window may open before the server answers
            // and show a "can't reach this page". Poll in the background and reload the window
            // the moment the server is up — the user never has to refresh by hand.
            if launched_bundled {
                let win = window.clone();
                std::thread::spawn(move || {
                    if server::wait_for_port(port, Duration::from_secs(600)) {
                        // a beat for waitress to begin serving HTTP after the port opens
                        std::thread::sleep(Duration::from_millis(750));
                        let _ = win.navigate(parsed);
                    }
                });
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("failed to launch the Atlas desktop shell");

    app.run(|handle, event| {
        if let RunEvent::Exit = event {
            // stop the bundled server (its atexit/self-heal handles Postgres) on quit
            if let Some(mut child) = handle.state::<ServerProc>().0.lock().unwrap().take() {
                let _ = child.kill();
            }
        }
    });
}
