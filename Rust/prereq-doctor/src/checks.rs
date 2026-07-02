use std::time::Duration;

use regex::Regex;
use tokio::process::Command;
use tokio::time::timeout;

use crate::config::CustomCheck;
use crate::models::CheckResult;

struct BuiltinCheck {
    id: &'static str,
    label: &'static str,
    required: bool,
    platform: Option<&'static str>,
}

const BUILTIN_CHECKS: &[BuiltinCheck] = &[
    BuiltinCheck {
        id: "git",
        label: "Git",
        required: true,
        platform: None,
    },
    BuiltinCheck {
        id: "rustc",
        label: "Rust compiler",
        required: true,
        platform: None,
    },
    BuiltinCheck {
        id: "cargo",
        label: "Cargo",
        required: true,
        platform: None,
    },
    BuiltinCheck {
        id: "python",
        label: "Python",
        required: true,
        platform: None,
    },
    BuiltinCheck {
        id: "gh",
        label: "GitHub CLI",
        required: false,
        platform: None,
    },
    BuiltinCheck {
        id: "node",
        label: "Node.js",
        required: false,
        platform: None,
    },
    BuiltinCheck {
        id: "ping",
        label: "Ping utility",
        required: true,
        platform: None,
    },
    BuiltinCheck {
        id: "powershell",
        label: "PowerShell",
        required: true,
        platform: Some("windows"),
    },
    BuiltinCheck {
        id: "rsat-ad",
        label: "RSAT Active Directory module",
        required: false,
        platform: Some("windows"),
    },
];

pub async fn run_builtin_checks(only: &[String]) -> Vec<CheckResult> {
    let mut results = Vec::new();

    for spec in BUILTIN_CHECKS {
        if !only.is_empty() && !only.iter().any(|id| id == spec.id) {
            continue;
        }
        if let Some(platform) = spec.platform {
            if !cfg_matches(platform) {
                continue;
            }
        }

        let result = match spec.id {
            "git" => check_command_version(
                spec.id,
                spec.label,
                spec.required,
                "git",
                &["--version"],
                "Install Git and ensure it is on PATH.",
            )
            .await,
            "rustc" => {
                check_command_version(
                    spec.id,
                    spec.label,
                    spec.required,
                    "rustc",
                    &["--version"],
                    "Install Rust from https://rustup.rs and ensure cargo bin dir is on PATH.",
                )
                .await
            }
            "cargo" => {
                check_command_version(
                    spec.id,
                    spec.label,
                    spec.required,
                    "cargo",
                    &["--version"],
                    "Install Rust from https://rustup.rs and ensure cargo bin dir is on PATH.",
                )
                .await
            }
            "python" => check_python(spec.required).await,
            "gh" => {
                check_command_version(
                    spec.id,
                    spec.label,
                    spec.required,
                    "gh",
                    &["--version"],
                    "Install the GitHub CLI from https://cli.github.com.",
                )
                .await
            }
            "node" => {
                check_command_version(
                    spec.id,
                    spec.label,
                    spec.required,
                    "node",
                    &["--version"],
                    "Install Node.js if you need JavaScript tooling.",
                )
                .await
            }
            "ping" => check_ping(spec.required).await,
            "powershell" => check_powershell(spec.required).await,
            "rsat-ad" => check_rsat_ad(spec.required).await,
            _ => continue,
        };

        results.push(result);
    }

    results
}

pub async fn run_custom_checks(checks: &[CustomCheck], only: &[String]) -> Vec<CheckResult> {
    let mut results = Vec::new();

    for check in checks {
        if !only.is_empty() && !only.iter().any(|id| id == &check.id) {
            continue;
        }

        let mut last_error = String::from("Command not found.");
        let mut found = false;

        for command in &check.commands {
            let args: Vec<&str> = check.args.iter().map(String::as_str).collect();
            match run_command(command, &args, Duration::from_secs(10)).await {
                Ok((0, output)) => {
                    found = true;
                    let version = extract_version(&output);
                    results.push(CheckResult::pass(
                        check.id.clone(),
                        check.id.clone(),
                        check.required,
                        version,
                        Some(output.trim().to_string()),
                    ));
                    break;
                }
                Ok((code, output)) => {
                    last_error = format!("Exit code {code}: {}", output.trim());
                }
                Err(error) => {
                    last_error = error;
                }
            }
        }

        if !found {
            let hint = check
                .hint
                .clone()
                .unwrap_or_else(|| "Install the tool and ensure it is on PATH.".into());
            if check.required {
                results.push(CheckResult::fail(
                    check.id.clone(),
                    check.id.clone(),
                    true,
                    last_error,
                    hint,
                ));
            } else {
                results.push(CheckResult::warn(
                    check.id.clone(),
                    check.id.clone(),
                    last_error,
                    hint,
                ));
            }
        }
    }

    results
}

async fn check_command_version(
    id: &str,
    label: &str,
    required: bool,
    command: &str,
    args: &[&str],
    hint: &str,
) -> CheckResult {
    match run_command(command, args, Duration::from_secs(10)).await {
        Ok((0, output)) => CheckResult::pass(
            id,
            label,
            required,
            extract_version(&output),
            Some(output.trim().to_string()),
        ),
        Ok((code, output)) => fail_or_warn(
            id,
            label,
            required,
            format!("Exit code {code}: {}", output.trim()),
            hint,
        ),
        Err(error) => fail_or_warn(id, label, required, error, hint),
    }
}

async fn check_python(required: bool) -> CheckResult {
    let candidates: &[(&str, &[&str])] = if cfg!(windows) {
        &[
            ("py", &["-3", "--version"]),
            ("python", &["--version"]),
            ("python3", &["--version"]),
        ]
    } else {
        &[
            ("python3", &["--version"]),
            ("python", &["--version"]),
        ]
    };

    let mut last_error = String::from("Python executable not found.");
    for (command, args) in candidates {
        match run_command(command, args, Duration::from_secs(10)).await {
            Ok((0, output)) => {
                return CheckResult::pass(
                    "python",
                    "Python",
                    required,
                    extract_version(&output),
                    Some(format!("{command} {}", output.trim())),
                );
            }
            Ok((code, output)) => {
                last_error = format!("Exit code {code}: {}", output.trim());
            }
            Err(error) => {
                last_error = error;
            }
        }
    }

    fail_or_warn(
        "python",
        "Python",
        required,
        last_error,
        "Install Python 3 and ensure python, python3, or py is on PATH.",
    )
}

async fn check_ping(required: bool) -> CheckResult {
    let args: &[&str] = if cfg!(windows) {
        &["-?"]
    } else {
        &["-V"]
    };

    match run_command("ping", args, Duration::from_secs(5)).await {
        Ok((0, output)) | Ok((1, output)) => CheckResult::pass(
            "ping",
            "Ping utility",
            required,
            None,
            Some(first_line(&output)),
        ),
        Ok((code, output)) => fail_or_warn(
            "ping",
            "Ping utility",
            required,
            format!("Exit code {code}: {}", first_line(&output)),
            "Ensure the system ping utility is available on PATH.",
        ),
        Err(error) => fail_or_warn(
            "ping",
            "Ping utility",
            required,
            error,
            "Ensure the system ping utility is available on PATH.",
        ),
    }
}

async fn check_powershell(required: bool) -> CheckResult {
    let script = "$PSVersionTable.PSVersion.ToString()";
    match run_command(
        "powershell",
        &["-NoProfile", "-Command", script],
        Duration::from_secs(10),
    )
    .await
    {
        Ok((0, output)) => CheckResult::pass(
            "powershell",
            "PowerShell",
            required,
            Some(output.trim().to_string()),
            Some(format!("powershell {output}")),
        ),
        Ok((code, output)) => fail_or_warn(
            "powershell",
            "PowerShell",
            required,
            format!("Exit code {code}: {}", output.trim()),
            "PowerShell should be available by default on Windows.",
        ),
        Err(error) => fail_or_warn(
            "powershell",
            "PowerShell",
            required,
            error,
            "PowerShell should be available by default on Windows.",
        ),
    }
}

async fn check_rsat_ad(required: bool) -> CheckResult {
    let script = "if (Get-Module -ListAvailable -Name ActiveDirectory) { 'installed' } else { exit 1 }";
    match run_command(
        "powershell",
        &["-NoProfile", "-Command", script],
        Duration::from_secs(15),
    )
    .await
    {
        Ok((0, output)) => CheckResult::pass(
            "rsat-ad",
            "RSAT Active Directory module",
            required,
            None,
            Some(output.trim().to_string()),
        ),
        Ok((code, output)) => fail_or_warn(
            "rsat-ad",
            "RSAT Active Directory module",
            required,
            format!("Exit code {code}: {}", output.trim()),
            "Install RSAT Active Directory tools (Settings > Optional features on Windows).",
        ),
        Err(error) => fail_or_warn(
            "rsat-ad",
            "RSAT Active Directory module",
            required,
            error,
            "Install RSAT Active Directory tools (Settings > Optional features on Windows).",
        ),
    }
}

async fn run_command(
    command: &str,
    args: &[&str],
    wait_for: Duration,
) -> Result<(i32, String), String> {
    let mut process = Command::new(command);
    process.args(args);
    process.kill_on_drop(true);

    let output = timeout(wait_for, process.output())
        .await
        .map_err(|_| format!("Timed out running {command}"))?
        .map_err(|error| format!("Failed to run {command}: {error}"))?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    let combined = if stdout.trim().is_empty() {
        stderr.to_string()
    } else if stderr.trim().is_empty() {
        stdout.to_string()
    } else {
        format!("{stdout}{stderr}")
    };

    Ok((output.status.code().unwrap_or(-1), combined))
}

fn extract_version(output: &str) -> Option<String> {
    static VERSION_RE: std::sync::OnceLock<Regex> = std::sync::OnceLock::new();
    let re = VERSION_RE.get_or_init(|| Regex::new(r"\d+\.\d+(?:\.\d+)?(?:[-+][\w.-]+)?").unwrap());
    re.find(output).map(|m| m.as_str().to_string())
}

fn first_line(text: &str) -> String {
    text.lines().next().unwrap_or("").trim().to_string()
}

fn fail_or_warn(
    id: &str,
    label: &str,
    required: bool,
    detail: String,
    hint: &str,
) -> CheckResult {
    if required {
        CheckResult::fail(id, label, true, detail, hint)
    } else {
        CheckResult::warn(id, label, detail, hint)
    }
}

fn cfg_matches(platform: &str) -> bool {
    match platform {
        "windows" => cfg!(windows),
        "unix" => cfg!(unix),
        _ => true,
    }
}
