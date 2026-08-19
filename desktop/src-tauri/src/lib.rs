use serde_json::{json, Value};
use std::env;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

#[cfg(windows)]
use std::os::windows::process::CommandExt;

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

fn source_root() -> Result<PathBuf, String> {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .map_err(|error| format!("failed to locate the RigManifest source root: {error}"))
}

fn python_executable(root: &Path) -> PathBuf {
    if let Some(configured) = env::var_os("RIGMANIFEST_PYTHON") {
        return PathBuf::from(configured);
    }

    #[cfg(windows)]
    return root.join(".venv").join("Scripts").join("python.exe");

    #[cfg(not(windows))]
    return root.join(".venv").join("bin").join("python");
}

fn parse_sidecar_response(stdout: &[u8]) -> Result<Value, String> {
    let response: Value = serde_json::from_slice(stdout)
        .map_err(|error| format!("Python returned invalid JSON: {error}"))?;

    if let Some(error) = response.get("error") {
        let message = error
            .get("message")
            .and_then(Value::as_str)
            .unwrap_or("unknown Python sidecar error");
        return Err(message.to_owned());
    }

    response
        .get("result")
        .cloned()
        .ok_or_else(|| "Python response did not contain a result".to_owned())
}

fn invoke_python(profile: &str, target: &str, output_path: Option<&str>) -> Result<Value, String> {
    let root = source_root()?;
    let python = python_executable(&root);
    if !python.is_file() {
        return Err(format!(
            "Python environment not found at {}. Run the repository setup steps or set RIGMANIFEST_PYTHON.",
            python.display()
        ));
    }

    let request = json!({
        "id": "desktop",
        "method": "compile",
        "params": {
            "profile": profile,
            "target": target,
            "output_path": output_path,
        }
    });

    let mut command = Command::new(&python);
    command
        .args(["-m", "rigmanifest.sidecar"])
        .current_dir(&root)
        .env("PYTHONPATH", root.join("src"))
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    #[cfg(windows)]
    command.creation_flags(CREATE_NO_WINDOW);

    let mut child = command
        .spawn()
        .map_err(|error| format!("failed to start Python at {}: {error}", python.display()))?;

    let mut stdin = child
        .stdin
        .take()
        .ok_or_else(|| "failed to open Python stdin".to_owned())?;
    writeln!(stdin, "{request}")
        .map_err(|error| format!("failed to send request to Python: {error}"))?;
    drop(stdin);

    let output = child
        .wait_with_output()
        .map_err(|error| format!("failed while waiting for Python: {error}"))?;
    if !output.status.success() {
        return Err(format!(
            "Python sidecar exited with {}: {}",
            output.status,
            String::from_utf8_lossy(&output.stderr).trim()
        ));
    }

    parse_sidecar_response(&output.stdout)
}

#[tauri::command]
fn compile_profile(
    profile: String,
    target: String,
    output_path: Option<String>,
) -> Result<Value, String> {
    invoke_python(&profile, &target, output_path.as_deref())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![compile_profile])
        .run(tauri::generate_context!())
        .expect("error while running RigManifest");
}

#[cfg(test)]
mod tests {
    use super::parse_sidecar_response;

    #[test]
    fn extracts_result_from_sidecar_response() {
        let result = parse_sidecar_response(br#"{"id":"test","result":{"schema_version":1}}"#)
            .expect("response should parse");

        assert_eq!(result["schema_version"], 1);
    }

    #[test]
    fn surfaces_sidecar_error_message() {
        let error = parse_sidecar_response(
            br#"{"id":"test","error":{"code":"INVALID_REQUEST","message":"bad target"}}"#,
        )
        .expect_err("error response should fail");

        assert_eq!(error, "bad target");
    }
}
