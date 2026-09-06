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
