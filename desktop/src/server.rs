// Bundled-server lifecycle (Owner epic #210e): the desktop shell spawns the frozen
// atlas-server (which auto-starts its own Postgres and serves Atlas), waits for it to
// answer, then loads the window at it — and kills it when the app quits.
use std::net::TcpStream;
use std::path::Path;
use std::process::{Child, Command};
use std::time::{Duration, Instant};

/// Spawn the frozen atlas-server with the per-user data dir, the bundled Postgres bin dir,
/// and the port it should listen on. `pg_bin` is the directory holding initdb/postgres/etc.
pub fn spawn(
    server_bin: &Path,
    data_dir: &Path,
    pg_bin: Option<&Path>,
    port: u16,
) -> std::io::Result<Child> {
    let mut cmd = Command::new(server_bin);
    cmd.env("ATLAS_DATA_DIR", data_dir)
        .env("ATLAS_PORT", port.to_string())
        // the app version (CI stamps Cargo.toml) lets the server skip re-collecting static on
        // repeat launches of the same build, but re-collect after an update (#241).
        .env("ATLAS_VERSION", env!("CARGO_PKG_VERSION"))
        .env("DJANGO_SETTINGS_MODULE", "config.settings.desktop");
    if let Some(bin) = pg_bin {
        cmd.env("ATLAS_PG_BIN", bin);
    }
    cmd.spawn()
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
/// surface the server + Postgres logs in the in-app diagnostic page when startup fails, so a
/// failure reports *why* instead of leaving a blank "can't reach this page" (#263).
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
    fn wait_for_port_times_out_when_closed() {
        // an unbound high port should never answer within the short window
        assert!(!wait_for_port(59_999, Duration::from_millis(600)));
    }
}
