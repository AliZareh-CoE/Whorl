// Built-in terminal (Owner idea #30, slice 5; multi-tab dock 2026-09-06): real PTYs in the
// Rust desktop shell, driven from an xterm.js dock over Tauri IPC. This is arbitrary local
// code execution by design — acceptable in the single-user desktop trust model (same as
// VS Code) — and it lives ONLY here in the desktop binary. It is never exposed through the
// Django web API or the MCP server (guarded by a build-failing grep test).
//
// Several terminals can be open at once (one per dock tab): every PTY gets an id, output
// events carry that id, and the frontend routes them to the right xterm instance.
use std::collections::HashMap;
use std::io::{Read, Write};
use std::sync::atomic::{AtomicU32, Ordering};
use std::sync::Mutex;

use portable_pty::{native_pty_system, CommandBuilder, MasterPty, PtySize};
use serde::Serialize;
use tauri::{Emitter, State};

#[derive(Default)]
pub struct TerminalState {
    inner: Mutex<HashMap<u32, Pty>>,
    next_id: AtomicU32,
}

struct Pty {
    master: Box<dyn MasterPty + Send>,
    writer: Box<dyn Write + Send>,
}

#[derive(Clone, Serialize)]
struct Output {
    id: u32,
    data: String,
}

#[derive(Clone, Serialize)]
struct Exit {
    id: u32,
}

/// The shell to run and its startup arguments. Windows prefers PowerShell 7 (`pwsh`) when
/// installed, else Windows PowerShell, both without the copyright banner so a new tab is a
/// prompt, not a paragraph. `ATLAS_SHELL` overrides everything.
fn default_shell() -> (String, Vec<String>) {
    if let Ok(custom) = std::env::var("ATLAS_SHELL") {
        return (custom, vec![]);
    }
    if cfg!(windows) {
        let pwsh = std::env::var("ProgramFiles")
            .map(|pf| std::path::PathBuf::from(pf).join("PowerShell").join("7").join("pwsh.exe"))
            .ok()
            .filter(|p| p.exists());
        return match pwsh {
            Some(p) => (p.to_string_lossy().into_owned(), vec!["-NoLogo".into()]),
            None => ("powershell.exe".into(), vec!["-NoLogo".into()]),
        };
    }
    (std::env::var("SHELL").unwrap_or_else(|_| "/bin/bash".into()), vec![])
}

/// Spawn a shell in a fresh PTY and return its id.
#[tauri::command]
pub fn terminal_spawn(
    app: tauri::AppHandle,
    state: State<'_, TerminalState>,
    cwd: Option<String>,
    rows: u16,
    cols: u16,
) -> Result<u32, String> {
    let pair = native_pty_system()
        .openpty(PtySize {
            rows,
            cols,
            pixel_width: 0,
            pixel_height: 0,
        })
        .map_err(|e| e.to_string())?;

    let (shell, args) = default_shell();
    let mut cmd = CommandBuilder::new(shell);
    cmd.args(args);
    cmd.env("TERM", "xterm-256color");
    cmd.env("ATLAS_DESKTOP", "1");
    if let Some(dir) = cwd.filter(|d| !d.is_empty() && std::path::Path::new(d).is_dir()) {
        cmd.cwd(dir);
    }
    let mut child = pair.slave.spawn_command(cmd).map_err(|e| e.to_string())?;
    drop(pair.slave);

    let id = state.next_id.fetch_add(1, Ordering::SeqCst) + 1;
    let mut reader = pair.master.try_clone_reader().map_err(|e| e.to_string())?;
    let writer = pair.master.take_writer().map_err(|e| e.to_string())?;

    // pump PTY output to the frontend, tagged with the terminal id
    let emit_app = app.clone();
    std::thread::spawn(move || {
        let mut buf = [0u8; 8192];
        loop {
            match reader.read(&mut buf) {
                Ok(0) | Err(_) => break,
                Ok(n) => {
                    let data = String::from_utf8_lossy(&buf[..n]).to_string();
                    let _ = emit_app.emit("terminal-output", Output { id, data });
                }
            }
        }
        let _ = child.wait();
        let _ = emit_app.emit("terminal-exit", Exit { id });
    });

    state.inner.lock().unwrap().insert(
        id,
        Pty {
            master: pair.master,
            writer,
        },
    );
    Ok(id)
}

#[tauri::command]
pub fn terminal_write(
    state: State<'_, TerminalState>,
    id: u32,
    data: String,
) -> Result<(), String> {
    if let Some(pty) = state.inner.lock().unwrap().get_mut(&id) {
        pty.writer
            .write_all(data.as_bytes())
            .map_err(|e| e.to_string())?;
        pty.writer.flush().map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
pub fn terminal_resize(
    state: State<'_, TerminalState>,
    id: u32,
    rows: u16,
    cols: u16,
) -> Result<(), String> {
    if let Some(pty) = state.inner.lock().unwrap().get(&id) {
        pty.master
            .resize(PtySize {
                rows,
                cols,
                pixel_width: 0,
                pixel_height: 0,
            })
            .map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// Close a terminal: dropping the master ends the session and the reader thread exits.
#[tauri::command]
pub fn terminal_kill(state: State<'_, TerminalState>, id: u32) -> Result<(), String> {
    state.inner.lock().unwrap().remove(&id);
    Ok(())
}
