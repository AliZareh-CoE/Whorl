// Local-disk file access (Owner idea #30, slice 6): the desktop shell can open a file
// the user explicitly PICKS from disk and read it into a preview — the "contain any file
// from disk" ask. Only the single user-chosen file is read (no directory traversal, no
// arbitrary path from the webview); text-only and size-capped. Like the terminal, this
// is a desktop-binary capability and never exposed through the web API/MCP.
use tauri_plugin_dialog::DialogExt;

const MAX_PREVIEW_BYTES: u64 = 5 * 1024 * 1024;

#[derive(serde::Serialize)]
pub struct LocalFile {
    path: String,
    name: String,
    content: String,
}

#[tauri::command]
pub fn open_local_file(app: tauri::AppHandle) -> Result<Option<LocalFile>, String> {
    let picked = app.dialog().file().blocking_pick_file();
    let Some(file_path) = picked else {
        return Ok(None);
    };
    let path = file_path.into_path().map_err(|e| e.to_string())?;
    let meta = std::fs::metadata(&path).map_err(|e| e.to_string())?;
    if meta.len() > MAX_PREVIEW_BYTES {
        return Err("File is too large to preview in-app.".into());
    }
    let content = std::fs::read_to_string(&path)
        .map_err(|_| "Not a UTF-8 text file (binary files can't be previewed here).")?;
    let name = path
        .file_name()
        .map(|n| n.to_string_lossy().to_string())
        .unwrap_or_default();
    Ok(Some(LocalFile {
        path: path.display().to_string(),
        name,
        content,
    }))
}
