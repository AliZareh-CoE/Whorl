// External links (owner report 2026-09-06: "the button to get it manually failed").
//
// The shell only lets the webview navigate inside the local Atlas origin (see
// `on_navigation` in main.rs), which is right for security but means every outbound link —
// DOIs, the releases page, API docs — silently did nothing. The frontend sends those here
// and we hand them to the operating system's default browser. Only http(s) and mailto are
// accepted, so a page can never launch an arbitrary program through this door.
use std::process::Command;

fn allowed(url: &str) -> bool {
    let lower = url.to_ascii_lowercase();
    lower.starts_with("https://") || lower.starts_with("http://") || lower.starts_with("mailto:")
}

#[tauri::command]
pub fn open_external(url: String) -> Result<(), String> {
    if !allowed(&url) || url.chars().any(|c| c.is_control() || c.is_whitespace()) {
        return Err("only http(s) and mailto links can be opened".into());
    }
    let result = if cfg!(target_os = "windows") {
        // `start` is a cmd builtin; the empty "" is the window title argument it expects
        Command::new("cmd").args(["/C", "start", "", &url]).spawn()
    } else if cfg!(target_os = "macos") {
        Command::new("open").arg(&url).spawn()
    } else {
        Command::new("xdg-open").arg(&url).spawn()
    };
    result.map(|_| ()).map_err(|e| e.to_string())
}

#[cfg(test)]
mod tests {
    use super::allowed;

    #[test]
    fn only_web_and_mail_links_pass() {
        assert!(allowed("https://github.com/x/y/releases"));
        assert!(allowed("HTTP://doi.org/10.1/abc"));
        assert!(allowed("mailto:someone@example.org"));
        assert!(!allowed("file:///etc/passwd"));
        assert!(!allowed("cmd:///C"));
        assert!(!allowed("javascript:alert(1)"));
    }
}

// Files on disk (CRUD sweep follow-up, 2026-09-06): the Files page can hand a document to
// the operating system — open it with the default app, or show it in the file manager. The
// server only reports local paths in desktop mode, and only for files it stores, so the
// webview never names arbitrary files; still, we refuse anything that is not an existing
// regular file.
fn existing_file(path: &str) -> Result<std::path::PathBuf, String> {
    let p = std::path::PathBuf::from(path);
    if path.chars().any(|c| c.is_control()) || !p.is_absolute() || !p.is_file() {
        return Err("not a file on this computer".into());
    }
    Ok(p)
}

#[tauri::command]
pub fn open_path(path: String) -> Result<(), String> {
    let p = existing_file(&path)?;
    let s = p.to_string_lossy().into_owned();
    let result = if cfg!(target_os = "windows") {
        Command::new("cmd").args(["/C", "start", "", &s]).spawn()
    } else if cfg!(target_os = "macos") {
        Command::new("open").arg(&s).spawn()
    } else {
        Command::new("xdg-open").arg(&s).spawn()
    };
    result.map(|_| ()).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn reveal_path(path: String) -> Result<(), String> {
    let p = existing_file(&path)?;
    let s = p.to_string_lossy().into_owned();
    let result = if cfg!(target_os = "windows") {
        Command::new("explorer").arg(format!("/select,{s}")).spawn()
    } else if cfg!(target_os = "macos") {
        Command::new("open").args(["-R", &s]).spawn()
    } else {
        let dir = p.parent().map(|d| d.to_string_lossy().into_owned()).unwrap_or(s);
        Command::new("xdg-open").arg(dir).spawn()
    };
    result.map(|_| ()).map_err(|e| e.to_string())
}

#[cfg(test)]
mod path_tests {
    use super::existing_file;

    #[test]
    fn only_existing_regular_files_pass() {
        let dir = std::env::temp_dir();
        let file = dir.join("atlas-existing-file-test.txt");
        std::fs::write(&file, b"x").unwrap();
        assert!(existing_file(&file.to_string_lossy()).is_ok());
        assert!(existing_file(&dir.to_string_lossy()).is_err()); // a directory
        assert!(existing_file("relative/file.txt").is_err());
        assert!(existing_file(&dir.join("does-not-exist.bin").to_string_lossy()).is_err());
        std::fs::remove_file(file).unwrap();
    }
}
