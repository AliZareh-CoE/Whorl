// In-app updates (Owner epic D2, 2026-06-14; owner 2026-09-06: "auto update or an update
// button so I won't need to download and install again").
//
// Two commands, so the UI can check silently on launch and only download when asked:
//   check_update      → Some(version) when the GitHub Releases feed (latest.json) carries a
//                       newer signed build, None when current.
//   install_update    → downloads + installs that build; the UI then offers a restart.
//   check_for_updates → the original one-shot (check + install) kept for compatibility.
// Every download is verified against the public key in tauri.conf.json, so a tampered feed
// or file is rejected — this is why the release workflow signs the updater artifacts.
use serde::Serialize;
use tauri::AppHandle;
use tauri_plugin_updater::UpdaterExt;

#[derive(Serialize)]
pub struct UpdateOutcome {
    /// Some(version) when a newer build was downloaded + installed; None when already current.
    pub installed_version: Option<String>,
}

#[derive(Serialize)]
pub struct UpdateCheck {
    /// Some(version) when a newer signed build is available on the release feed.
    pub available_version: Option<String>,
    pub current_version: String,
    /// Release notes / body from the feed, if any.
    pub notes: Option<String>,
}

/// Relaunch the whole app after an update was installed. A webview reload is not enough: the
/// freshly-installed binary (and the bundled server it spawns) only take effect on a real
/// process restart, so the "Update ready — restart" button calls this. `restart()` diverges
/// (it exits and re-execs the new binary), so this never returns.
#[tauri::command]
pub fn restart_app(app: AppHandle) {
    app.restart();
}

/// Silent availability check (the UI runs it once on launch).
#[tauri::command]
pub async fn check_update(app: AppHandle) -> Result<UpdateCheck, String> {
    let current = app.package_info().version.to_string();
    let updater = app.updater().map_err(|e| e.to_string())?;
    match updater.check().await.map_err(|e| e.to_string())? {
        Some(update) => Ok(UpdateCheck {
            available_version: Some(update.version.clone()),
            current_version: current,
            notes: update.body.clone(),
        }),
        None => Ok(UpdateCheck {
            available_version: None,
            current_version: current,
            notes: None,
        }),
    }
}

/// Download + install the available build (verified against the bundled public key).
#[tauri::command]
pub async fn install_update(app: AppHandle) -> Result<UpdateOutcome, String> {
    let updater = app.updater().map_err(|e| e.to_string())?;
    match updater.check().await.map_err(|e| e.to_string())? {
        Some(update) => {
            let version = update.version.clone();
            update
                .download_and_install(|_chunk, _total| {}, || {})
                .await
                .map_err(|e| e.to_string())?;
            Ok(UpdateOutcome {
                installed_version: Some(version),
            })
        }
        None => Ok(UpdateOutcome {
            installed_version: None,
        }),
    }
}

/// One-shot check + install (kept for the existing "Check for updates" flow).
#[tauri::command]
pub async fn check_for_updates(app: AppHandle) -> Result<UpdateOutcome, String> {
    install_update(app).await
}
