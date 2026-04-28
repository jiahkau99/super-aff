use std::sync::Mutex;

use tauri::{Manager, RunEvent, State};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

const BACKEND_PORT: u16 = 8765;

#[derive(Default)]
struct BackendChild(Mutex<Option<CommandChild>>);

fn spawn_backend(app: &tauri::AppHandle) -> Result<CommandChild, String> {
    let sidecar = app
        .shell()
        .sidecar("super-aff-backend")
        .map_err(|e| format!("could not resolve sidecar: {e}"))?;

    let (mut rx, child) = sidecar
        .args(["--port", &BACKEND_PORT.to_string(), "--host", "127.0.0.1"])
        .spawn()
        .map_err(|e| format!("failed to spawn backend: {e}"))?;

    // Drain stdout/stderr in the background so the child does not block.
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) | CommandEvent::Stderr(line) => {
                    log::info!("[backend] {}", String::from_utf8_lossy(&line));
                }
                CommandEvent::Error(err) => log::error!("[backend] error: {err}"),
                CommandEvent::Terminated(payload) => {
                    log::warn!(
                        "[backend] terminated code={:?} signal={:?}",
                        payload.code,
                        payload.signal
                    );
                    break;
                }
                _ => {}
            }
        }
    });

    Ok(child)
}

#[tauri::command]
fn backend_port() -> u16 {
    BACKEND_PORT
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_log::Builder::default().build())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_process::init())
        .manage(BackendChild::default())
        .invoke_handler(tauri::generate_handler![backend_port])
        .setup(|app| {
            let handle = app.handle().clone();
            let child = spawn_backend(&handle)?;
            let state: State<BackendChild> = app.state();
            *state.0.lock().unwrap() = Some(child);
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                let state: State<BackendChild> = app.state();
                if let Some(child) = state.0.lock().unwrap().take() {
                    let _ = child.kill();
                }
            }
        });
}
