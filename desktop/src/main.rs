// Atlas desktop shell (Owner idea #30, slice 3): a thin Tauri 2 window over the local
// Atlas server. The web app stays the single source of truth — this just wraps it in a
// native window so Atlas feels like an app (and is the foundation the terminal sits on).
//
// Usage: start Atlas (docker compose up -d && manage.py runserver), then launch this.
// The ATLAS_URL env var overrides the default localhost address.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod terminal;

use tauri::{Manager, WebviewUrl, WebviewWindowBuilder};

fn atlas_url() -> String {
    std::env::var("ATLAS_URL").unwrap_or_else(|_| "http://localhost:8000/".to_string())
}

fn main() {
    tauri::Builder::default()
        .manage(terminal::TerminalState::default())
        .invoke_handler(tauri::generate_handler![
            terminal::terminal_spawn,
            terminal::terminal_write,
            terminal::terminal_resize
        ])
        .setup(|app| {
            let url = atlas_url();
            let parsed = url.parse().expect("ATLAS_URL is not a valid URL");
            WebviewWindowBuilder::new(app, "main", WebviewUrl::External(parsed))
                .title("Atlas")
                .inner_size(1400.0, 900.0)
                .min_inner_size(900.0, 600.0)
                .build()?;
            // bring the window to the front on launch
            if let Some(w) = app.get_webview_window("main") {
                let _ = w.set_focus();
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("failed to launch the Atlas desktop shell");
}
