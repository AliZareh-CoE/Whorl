// Built-in terminal (Owner idea #30, slice 5): a real PTY in the Rust desktop shell,
// driven from an xterm.js panel over Tauri IPC. This is arbitrary local code execution
// by design — acceptable in the single-user desktop trust model (same as VS Code) — and
// it lives ONLY here in the desktop binary. It is never exposed through the Django web
// API or the MCP server (guarded by a build-failing grep test).
use std::io::{Read, Write};
use std::sync::Mutex;

use portable_pty::{CommandBuilder, MasterPty, PtySize, native_pty_system};
use tauri::{Emitter, State};

#[derive(Default)]
pub struct TerminalState {
    inner: Mutex<Option<Pty>>,
}

struct Pty {
    master: Box<dyn MasterPty + Send>,
    writer: Box<dyn Write + Send>,
}

fn default_shell() -> String {
    if cfg!(windows) {
        std::env::var("COMSPEC").unwrap_or_else(|_| "powershell.exe".into())
    } else {
        std::env::var("SHELL").unwrap_or_else(|_| "/bin/bash".into())
    }
}

#[tauri::command]
pub fn terminal_spawn(
    app: tauri::AppHandle,
    state: State<'_, TerminalState>,
    cwd: Option<String>,
    rows: u16,
    cols: u16,
) -> Result<(), String> {
    let pair = native_pty_system()
        .openpty(PtySize { rows, cols, pixel_width: 0, pixel_height: 0 })
        .map_err(|e| e.to_string())?;

    let mut cmd = CommandBuilder::new(default_shell());
    if let Some(dir) = cwd {
        cmd.cwd(dir);
    }
    let mut child = pair.slave.spawn_command(cmd).map_err(|e| e.to_string())?;
    drop(pair.slave);

    let mut reader = pair.master.try_clone_reader().map_err(|e| e.to_string())?;
    let writer = pair.master.take_writer().map_err(|e| e.to_string())?;

    // pump PTY output to the frontend
    let emit_app = app.clone();
    std::thread::spawn(move || {
        let mut buf = [0u8; 4096];
        loop {
            match reader.read(&mut buf) {
                Ok(0) | Err(_) => break,
                Ok(n) => {
                    let chunk = String::from_utf8_lossy(&buf[..n]).to_string();
                    let _ = emit_app.emit("terminal-output", chunk);
                }
            }
        }
        let _ = child.wait();
        let _ = emit_app.emit("terminal-exit", ());
    });

    *state.inner.lock().unwrap() = Some(Pty { master: pair.master, writer });
    Ok(())
}

#[tauri::command]
pub fn terminal_write(state: State<'_, TerminalState>, data: String) -> Result<(), String> {
    if let Some(pty) = state.inner.lock().unwrap().as_mut() {
        pty.writer.write_all(data.as_bytes()).map_err(|e| e.to_string())?;
        pty.writer.flush().map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
pub fn terminal_resize(
    state: State<'_, TerminalState>,
    rows: u16,
    cols: u16,
) -> Result<(), String> {
    if let Some(pty) = state.inner.lock().unwrap().as_ref() {
        pty.master
            .resize(PtySize { rows, cols, pixel_width: 0, pixel_height: 0 })
            .map_err(|e| e.to_string())?;
    }
    Ok(())
}
