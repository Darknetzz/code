use anyhow::{Context, Result};
use comfy_table::{presets::UTF8_FULL, Table};
use if_addrs::IfAddr;

fn main() -> Result<()> {
    let mut ifaces = if_addrs::get_if_addrs().context("failed to enumerate network interfaces")?;
    ifaces.sort_by(|a, b| a.name.cmp(&b.name).then_with(|| a.addr.ip().cmp(&b.addr.ip())));

    let mut table = Table::new();
    table.load_preset(UTF8_FULL);
    table.set_header(["Interface", "Family", "Address"]);

    for iface in ifaces {
        table.add_row([
            iface.name,
            family(&iface.addr).to_string(),
            iface.addr.ip().to_string(),
        ]);
    }

    println!("{table}");
    Ok(())
}

fn family(addr: &IfAddr) -> &'static str {
    match addr {
        IfAddr::V4(_) => "IPv4",
        IfAddr::V6(_) => "IPv6",
    }
}
