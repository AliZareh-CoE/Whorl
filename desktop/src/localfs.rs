// Local-disk file access (Owner idea #30, slice 6): the desktop shell can open a file
// the user explicitly PICKS from disk and read it into a preview — the "contain any file
// from disk" ask. Only the single user-chosen file is read (no directory traversal, no
// arbitrary path from the webview); size-capped. Like the terminal, this is a
// desktop-binary capability and never exposed through the web API/MCP.
//
// 2026-09-06 (owner: "open from disk not working"): the command is async. A blocking file
// dialog inside a synchronous command runs on the main thread, which is exactly where the
// dialog plugin says it must not run — the picker never appeared. The picked file now also
// comes back as base64 so the page can add it to the project (binary files included).
use tauri_plugin_dialog::DialogExt;

const MAX_BYTES: u64 = 25 * 1024 * 1024;

#[derive(serde::Serialize)]
pub struct LocalFile {
    path: String,
    name: String,
    size: u64,
    /// UTF-8 text when the file is text, else None (binary files preview as "no preview").
    content: Option<String>,
    /// The raw bytes, base64 — for "Add to this project".
    data_b64: String,
}

fn base64(bytes: &[u8]) -> String {
    const T: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = String::with_capacity((bytes.len() + 2) / 3 * 4);
    for chunk in bytes.chunks(3) {
        let b = [chunk[0], *chunk.get(1).unwrap_or(&0), *chunk.get(2).unwrap_or(&0)];
        let n = (u32::from(b[0]) << 16) | (u32::from(b[1]) << 8) | u32::from(b[2]);
        out.push(T[(n >> 18) as usize & 63] as char);
        out.push(T[(n >> 12) as usize & 63] as char);
        out.push(if chunk.len() > 1 { T[(n >> 6) as usize & 63] as char } else { '=' });
        out.push(if chunk.len() > 2 { T[n as usize & 63] as char } else { '=' });
    }
    out
}

#[tauri::command]
pub async fn open_local_file(app: tauri::AppHandle) -> Result<Option<LocalFile>, String> {
    let (tx, rx) = std::sync::mpsc::channel();
    app.dialog().file().pick_file(move |picked| {
        let _ = tx.send(picked);
    });
    let picked = tauri::async_runtime::spawn_blocking(move || rx.recv().ok().flatten())
        .await
        .map_err(|e| e.to_string())?;
    let Some(file_path) = picked else {
        return Ok(None);
    };
    let path = file_path.into_path().map_err(|e| e.to_string())?;
    let meta = std::fs::metadata(&path).map_err(|e| e.to_string())?;
    if meta.len() > MAX_BYTES {
        return Err(format!(
            "{} is {} MB — files over 25 MB can't be opened here; upload them on the Files page instead.",
            path.display(),
            meta.len() / (1024 * 1024)
        ));
    }
    let bytes = std::fs::read(&path).map_err(|e| format!("{}: {e}", path.display()))?;
    let name = path
        .file_name()
        .map(|n| n.to_string_lossy().to_string())
        .unwrap_or_default();
    Ok(Some(LocalFile {
        path: path.display().to_string(),
        name,
        size: meta.len(),
        content: String::from_utf8(bytes.clone()).ok(),
        data_b64: base64(&bytes),
    }))
}

#[cfg(test)]
mod tests {
    use super::base64;

    #[test]
    fn base64_matches_rfc4648() {
        assert_eq!(base64(b""), "");
        assert_eq!(base64(b"f"), "Zg==");
        assert_eq!(base64(b"fo"), "Zm8=");
        assert_eq!(base64(b"foo"), "Zm9v");
        assert_eq!(base64(b"foobar"), "Zm9vYmFy");
    }
}


/// Pick a folder (#406: the watched PDF folder). Same off-main-thread dance as the file picker.
#[tauri::command]
pub async fn pick_folder(app: tauri::AppHandle) -> Result<Option<String>, String> {
    let (tx, rx) = std::sync::mpsc::channel();
    app.dialog().file().pick_folder(move |picked| {
        let _ = tx.send(picked);
    });
    let picked = tauri::async_runtime::spawn_blocking(move || rx.recv().ok().flatten())
        .await
        .map_err(|e| e.to_string())?;
    let Some(folder) = picked else {
        return Ok(None);
    };
    let path = folder.into_path().map_err(|e| e.to_string())?;
    Ok(Some(path.display().to_string()))
}
