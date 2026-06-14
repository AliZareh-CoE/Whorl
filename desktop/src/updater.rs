// In-app auto-update (Owner epic D2, 2026-06-14): "I want a button for updating the app".
//
// `check_for_updates` is invoked from the web UI's desktop-only "Check for updates" control.
// It asks the updater (configured against the GitHub Releases feed in tauri.conf.json)
// whether a newer signed build exists; if so it downloads + installs it and reports the new
// version so the UI can offer a restart. No update → Ok(None), so the UI can say "up to date".
use serde::Serialize;
use tauri::AppHandle;
use tauri_plugin_updater::UpdaterExt;

#[derive(Serialize)]
pub struct UpdateOutcome {
    /// Some(version) when a newer build was downloaded + installed; None when already current.
    pub installed_version: Option<String>,
}

#[tauri::command]
pub async fn check_for_updates(app: AppHandle) -> Result<UpdateOutcome, String> {
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
