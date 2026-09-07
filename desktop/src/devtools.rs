// The web inspector on demand (#389). The release build ships with Tauri's `devtools`
// feature so the owner can open a real console when a page misbehaves — the blank-window
// report of 2026-09-07 had no way to say what was thrown. Opened only on request: F12 or
// Ctrl+Shift+I in the app, the Diagnostics button, or the boot-failure panel.

#[tauri::command]
pub fn open_devtools(window: tauri::WebviewWindow) -> Result<(), String> {
    window.open_devtools();
    Ok(())
}
