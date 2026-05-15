use std::sync::{Mutex, OnceLock};

pub static CHILD_PID: Mutex<Option<u32>> = Mutex::new(None);

pub fn install_sigint_handler() {
    static ONCE: OnceLock<()> = OnceLock::new();
    ONCE.get_or_init(|| {
        let _ = ctrlc::set_handler(|| {
            #[cfg(unix)]
            {
                if let Ok(guard) = CHILD_PID.lock() {
                    if let Some(pid) = *guard {
                        unsafe {
                            libc::kill(pid as libc::pid_t, libc::SIGINT);
                        }
                    }
                }
            }
        });
    });
}

pub fn set_child(pid: Option<u32>) {
    if let Ok(mut g) = CHILD_PID.lock() {
        *g = pid;
    }
}
