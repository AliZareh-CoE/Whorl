// Bundled-server lifecycle (Owner epic #210e, #266): the desktop shell spawns the frozen
// atlas-server (Django on a per-user SQLite file, served by waitress), waits for it to
// answer, then loads the window at it — and kills it when the app quits.
use std::net::{TcpListener, TcpStream};
use std::path::Path;
use std::process::{Child, Command};
use std::time::{Duration, Instant};

/// Spawn the frozen atlas-server with the per-user data dir, the port it should listen on,
/// and (when bundled) the path of the frozen `atlas-mcp` so the app can show the user the
/// exact `claude mcp add` line for this install.
pub fn spawn(
    server_bin: &Path,
    data_dir: &Path,
    port: u16,
    mcp_bin: Option<&Path>,
) -> std::io::Result<Child> {
    let mut cmd = Command::new(server_bin);
    cmd.env("ATLAS_DATA_DIR", data_dir)
        .env("ATLAS_PORT", port.to_string())
        // the app version (CI stamps Cargo.toml) lets the server skip re-collecting static on
        // repeat launches of the same build, but re-collect after an update (#241).
        .env("ATLAS_VERSION", env!("CARGO_PKG_VERSION"))
        .env("DJANGO_SETTINGS_MODULE", "config.settings.desktop");
    if let Some(mcp) = mcp_bin {
        cmd.env("ATLAS_MCP_BIN", mcp);
    }
    cmd.spawn()
}

/// Pick the port the bundled server should listen on: `preferred` when it is free, otherwise
/// an OS-assigned free port. A developer's own `runserver` on 8000 (or any other app holding
/// the port) used to make the bundled server fail to bind and the launch fail — now the two
/// simply coexist. `None` only if the OS refuses to hand out any loopback port at all.
pub fn choose_port(preferred: u16) -> Option<u16> {
    for candidate in [preferred, 0] {
        if let Ok(listener) = TcpListener::bind(("127.0.0.1", candidate)) {
            if let Ok(addr) = listener.local_addr() {
                // the listener is dropped here, freeing the port for the server to bind
                return Some(addr.port());
            }
        }
    }
    None
}

/// Block until something is listening on 127.0.0.1:`port` (the server is up), or give up.
pub fn wait_for_port(port: u16, timeout: Duration) -> bool {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if TcpStream::connect(("127.0.0.1", port)).is_ok() {
            return true;
        }
        std::thread::sleep(Duration::from_millis(300));
    }
    false
}

/// Last `max_bytes` of a UTF-8 text file, or a short note when it's missing/empty. Used to
/// surface the server log in the in-app diagnostic page when startup fails, so a failure
/// reports *why* instead of leaving a blank "can't reach this page" (#263).
pub fn tail_file(path: &Path, max_bytes: usize) -> String {
    match std::fs::read(path) {
        Ok(bytes) if !bytes.is_empty() => {
            let start = bytes.len().saturating_sub(max_bytes);
            String::from_utf8_lossy(&bytes[start..]).into_owned()
        }
        Ok(_) => "(empty)".to_string(),
        Err(_) => "(not created — the step that writes it never ran)".to_string(),
    }
}

/// Minimal HTML escaping so log text can be dropped into the diagnostic page safely.
pub fn escape_html(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::TcpListener;

    #[test]
    fn wait_for_port_detects_a_listener() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        assert!(wait_for_port(port, Duration::from_secs(2)));
    }

    #[test]
    fn choose_port_prefers_the_requested_port_when_free() {
        // grab an ephemeral port, release it, and ask for it back: it should be honoured
        let free = TcpListener::bind("127.0.0.1:0")
            .unwrap()
            .local_addr()
            .unwrap()
            .port();
        assert_eq!(choose_port(free), Some(free));
    }

    #[test]
    fn choose_port_falls_back_when_the_requested_port_is_taken() {
        let taken = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = taken.local_addr().unwrap().port();
        let chosen = choose_port(port).expect("some loopback port must be free");
        assert_ne!(chosen, port);
        assert!(TcpListener::bind(("127.0.0.1", chosen)).is_ok());
    }

    #[test]
    fn tail_file_reports_missing_and_truncates() {
        let dir = std::env::temp_dir().join(format!("atlas-tail-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("x.log");
        assert!(tail_file(&path, 10).contains("not created"));
        std::fs::write(&path, "abcdefghijklmnop").unwrap();
        assert_eq!(tail_file(&path, 4), "mnop");
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn escape_html_neutralises_markup() {
        assert_eq!(escape_html("<b>&"), "&lt;b&gt;&amp;");
    }

    #[test]
    fn wait_for_port_times_out_when_closed() {
        // an unbound high port should never answer within the short window
        assert!(!wait_for_port(59_999, Duration::from_millis(600)));
    }
}
