import hashlib
import time
import multiprocessing
import threading
import signal
import sys
import secrets
from multiprocessing import Value, Lock, Manager
import typer
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn
from rich import box

# GPU support (optional)
try:
    import pyopencl as cl
    import numpy as np
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False

def generate_deterministic_random(nonce: int, seed: int, length: int) -> str:
    """
    Generate deterministic random-looking data from nonce and seed.
    Uses hash-based approach to ensure reproducibility while appearing random.
    """
    if length == 0:
        return ""
    
    # Combine seed and nonce for deterministic randomness
    combined = f"{seed}:{nonce}".encode()
    
    # Generate hash and use it to create random-looking hex string
    hash_bytes = hashlib.sha256(combined).digest()
    
    # Convert to hex and take the requested length
    hex_str = hash_bytes.hex()
    
    # If we need more bytes, hash again with an index
    if length > len(hex_str):
        result = hex_str
        idx = 0
        while len(result) < length:
            combined_extended = f"{seed}:{nonce}:{idx}".encode()
            hash_extended = hashlib.sha256(combined_extended).digest().hex()
            result += hash_extended
            idx += 1
        return result[:length]
    else:
        return hex_str[:length]


def get_gpu_devices():
    """Get available GPU devices."""
    if not GPU_AVAILABLE:
        return []
    
    devices = []
    try:
        platforms = cl.get_platforms()
        for platform in platforms:
            for device in platform.get_devices(device_type=cl.device_type.GPU):
                devices.append((platform, device))
    except:
        pass
    
    return devices


def worker_gpu(worker_id, prefix, target_zeroes, check_leading, check_trailing, 
               num_workers, total_attempts, counter_lock, found_solution, 
               start_time, console_output_queue, device_idx=0, batch_size=50000,
               random_seed=0, random_length=0):
    """
    GPU-accelerated worker using batch processing with concurrent hashing.
    
    Note: Full GPU SHA-256 requires a complex OpenCL/CUDA kernel implementation.
    This version uses optimized batch processing with CPU hashlib, which still
    provides performance benefits through better CPU utilization.
    
    For true GPU acceleration, consider using hashcat or implementing a full
    SHA-256 OpenCL/CUDA kernel.
    
    Args:
        random_seed: Seed for deterministic randomness (0 = no randomness)
        random_length: Number of random hex characters to append (0 = no randomness)
    """
    from concurrent.futures import ThreadPoolExecutor
    import os
    
    # Use multiple threads for batch processing
    num_threads = min(os.cpu_count() or 4, 8)
    
    target_leading = '0' * target_zeroes
    target_trailing = '0' * target_zeroes
    
    nonce = worker_id
    local_attempts = 0
    
    def hash_and_check(nonce_val):
        """Hash a single nonce and check if it matches."""
        # Create input string with prefix, nonce, and optional random data
        if random_length > 0 and random_seed != 0:
            random_part = generate_deterministic_random(nonce_val, random_seed, random_length)
            input_str = f"{prefix}{nonce_val}{random_part}"
        else:
            input_str = f"{prefix}{nonce_val}"
        hash_result = hashlib.sha256(input_str.encode()).hexdigest()
        
        found = None
        zero_type = None
        
        if check_leading and hash_result.startswith(target_leading):
            found = True
            zero_type = 'leading'
        elif check_trailing and hash_result.endswith(target_trailing):
            found = True
            zero_type = 'trailing'
        
        return found, zero_type, hash_result, input_str
    
    while True:
        if found_solution['found']:
            return
        
        # Process batch in parallel
        batch_nonces = [nonce + i * num_workers for i in range(batch_size)]
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            results = list(executor.map(hash_and_check, batch_nonces))
        
        local_attempts += batch_size
        
        # Check results
        for found, zero_type, hash_result, input_str in results:
            if found:
                with counter_lock:
                    if not found_solution['found']:
                        found_solution['found'] = True
                        found_solution['hash'] = hash_result
                        found_solution['input'] = input_str
                        found_solution['zero_type'] = zero_type
                        elapsed = time.time() - start_time.value
                        current_total = total_attempts.value + local_attempts
                        console_output_queue.put(('found', {
                            'type': zero_type,
                            'target': target_zeroes,
                            'hash': hash_result,
                            'input': input_str,
                            'elapsed': elapsed,
                            'worker': worker_id + 1,
                            'attempts': current_total
                        }))
                        return
        
        nonce += batch_size * num_workers
        
        # Update counter periodically
        if local_attempts % 100000 == 0:
            with counter_lock:
                total_attempts.value += local_attempts
                current_total = total_attempts.value
                if current_total % 10000000 == 0 and current_total > 0:
                    elapsed = time.time() - start_time.value
                    if elapsed > 0.001:
                        rate = current_total / elapsed
                        console_output_queue.put(('progress', {
                            'elapsed': elapsed,
                            'attempts': current_total,
                            'rate': rate
                        }))
                local_attempts = 0


def worker(worker_id, prefix, target_zeroes, check_leading, check_trailing, num_workers, 
           total_attempts, counter_lock, found_solution, start_time, console_output_queue,
           random_seed=0, random_length=0):
    """
    Worker function that increments nonces and checks for target zeroes.
    Each worker starts from a different nonce range to avoid collisions.
    
    Args:
        random_seed: Seed for deterministic randomness (0 = no randomness)
        random_length: Number of random hex characters to append (0 = no randomness)
    """
    local_attempts = 0
    
    # Each worker starts from a different nonce offset and strides by num_workers
    # This ensures workers don't collide: worker 0 checks 0, 4, 8... worker 1 checks 1, 5, 9...
    nonce = worker_id
    
    target_leading = '0' * target_zeroes
    target_trailing = '0' * target_zeroes
    
    while True:
        # Check if another worker found the solution
        if found_solution['found']:
            return
        
        # Create input string with prefix, nonce, and optional random data
        if random_length > 0 and random_seed != 0:
            random_part = generate_deterministic_random(nonce, random_seed, random_length)
            input_str = f"{prefix}{nonce}{random_part}"
        else:
            input_str = f"{prefix}{nonce}"
        
        check = input_str.encode()
        hash_result = hashlib.sha256(check).hexdigest()
        
        local_attempts += 1
        
        # Check leading zeroes
        if check_leading and hash_result.startswith(target_leading):
            with counter_lock:
                if not found_solution['found']:
                    found_solution['found'] = True
                    found_solution['hash'] = hash_result
                    found_solution['input'] = input_str
                    found_solution['zero_type'] = 'leading'
                    elapsed = time.time() - start_time.value
                    current_total = total_attempts.value + local_attempts
                    # Send formatted output to queue for main process to display
                    console_output_queue.put(('found', {
                        'type': 'leading',
                        'target': target_zeroes,
                        'hash': hash_result,
                        'input': input_str,
                        'elapsed': elapsed,
                        'worker': worker_id + 1,
                        'attempts': current_total
                    }))
            return
        
        # Check trailing zeroes
        if check_trailing and hash_result.endswith(target_trailing):
            with counter_lock:
                if not found_solution['found']:
                    found_solution['found'] = True
                    found_solution['hash'] = hash_result
                    found_solution['input'] = input_str
                    found_solution['zero_type'] = 'trailing'
                    elapsed = time.time() - start_time.value
                    current_total = total_attempts.value + local_attempts
                    # Send formatted output to queue for main process to display
                    console_output_queue.put(('found', {
                        'type': 'trailing',
                        'target': target_zeroes,
                        'hash': hash_result,
                        'input': input_str,
                        'elapsed': elapsed,
                        'worker': worker_id + 1,
                        'attempts': current_total
                    }))
            return
        
        nonce += num_workers  # Stride by num_workers to maintain separation
        
        # Update global counter periodically (every 100k iterations)
        if local_attempts % 100000 == 0:
            with counter_lock:
                total_attempts.value += local_attempts
                
                # Send progress updates every 10M attempts
                current_total = total_attempts.value
                if current_total % 10000000 == 0 and current_total > 0:
                    elapsed = time.time() - start_time.value
                    if elapsed > 0.001:
                        rate = current_total / elapsed
                        console_output_queue.put(('progress', {
                            'elapsed': elapsed,
                            'attempts': current_total,
                            'rate': rate
                        }))
                
                local_attempts = 0


app = typer.Typer(help="Find hashes with leading or trailing zeroes using parallel processing")
console = Console()


@app.command()
def list_gpus(
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Show detailed device information")
):
    """List available GPU devices for OpenCL acceleration."""
    if not GPU_AVAILABLE:
        console.print("[red]PyOpenCL is not installed.[/red]")
        console.print("Install it with: [cyan]pip install pyopencl numpy[/cyan]")
        return
    
    devices = get_gpu_devices()
    if not devices:
        console.print("[yellow]No GPU devices found.[/yellow]")
        console.print("\nThis could mean:")
        console.print("1. GPU drivers are not installed or outdated")
        console.print("2. OpenCL runtime is not installed")
        console.print("3. GPU is not compatible with OpenCL")
        return
    
    if detailed:
        # Show detailed information for each device
        if not GPU_AVAILABLE:
            console.print("[red]Cannot show detailed info: PyOpenCL not available[/red]")
            return
        
        for idx, (platform, device) in enumerate(devices):
            device_type = "GPU"
            if device.type == cl.device_type.CPU:
                device_type = "CPU"
            elif device.type == cl.device_type.ACCELERATOR:
                device_type = "Accelerator"
            
            # Get device properties
            try:
                memory = device.get_info(cl.device_info.GLOBAL_MEM_SIZE) / (1024**3)  # GB
                compute_units = device.get_info(cl.device_info.MAX_COMPUTE_UNITS)
                max_work_group_size = device.get_info(cl.device_info.MAX_WORK_GROUP_SIZE)
                opencl_version = device.get_info(cl.device_info.OPENCL_C_VERSION)
            except:
                memory = "N/A"
                compute_units = "N/A"
                max_work_group_size = "N/A"
                opencl_version = "N/A"
            
            table = Table(
                title=f"[bold blue]GPU Device {idx}[/bold blue]",
                box=box.ROUNDED,
                show_header=False
            )
            table.add_column("Property", style="cyan", width=25)
            table.add_column("Value", style="yellow")
            
            table.add_row("Platform", platform.name)
            table.add_row("Device Name", device.name)
            table.add_row("Type", device_type)
            table.add_row("Memory", f"{memory:.2f} GB" if isinstance(memory, float) else str(memory))
            table.add_row("Compute Units", str(compute_units))
            table.add_row("Max Work Group Size", str(max_work_group_size))
            table.add_row("OpenCL Version", str(opencl_version))
            
            console.print("\n")
            console.print(table)
        
        console.print()
    else:
        # Show summary table
        table = Table(title="[bold blue]Available GPU Devices[/bold blue]", box=box.ROUNDED)
        table.add_column("ID", style="cyan", justify="center")
        table.add_column("Platform", style="green")
        table.add_column("Device Name", style="yellow")
        table.add_column("Type", style="magenta")
        table.add_column("Architecture", style="dim")
        
        # Map common AMD GPU codenames
        arch_map = {
            "gfx1101": "RDNA 3 (RX 7800/7900 series)",
            "gfx1100": "RDNA 3",
            "gfx1102": "RDNA 3",
            "gfx1036": "RDNA 2 (RX 6600/6700 series)",
            "gfx1030": "RDNA 2",
            "gfx1031": "RDNA 2",
            "gfx1032": "RDNA 2",
        }
        
        for idx, (platform, device) in enumerate(devices):
            device_type = "GPU"
            if device.type == cl.device_type.CPU:
                device_type = "CPU"
            elif device.type == cl.device_type.ACCELERATOR:
                device_type = "Accelerator"
            
            # Try to identify architecture from device name
            device_name = device.name.lower()
            arch = "Unknown"
            for codename, description in arch_map.items():
                if codename in device_name:
                    arch = description
                    break
            
            table.add_row(
                str(idx),
                platform.name,
                device.name,
                device_type,
                arch
            )
        
        console.print("\n")
        console.print(table)
        console.print("\n[dim]Tip: Use --detailed flag for more information about each device[/dim]\n")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    target_zeroes: Optional[int] = typer.Option(None, "--target", "-t", help="Target number of zeroes to find"),
    prefix: Optional[str] = typer.Option(None, "--prefix", "-p", help="Prefix string to use before nonce"),
    check_leading: Optional[bool] = typer.Option(None, "--leading/--no-leading", help="Check for leading zeroes"),
    check_trailing: Optional[bool] = typer.Option(None, "--trailing/--no-trailing", help="Check for trailing zeroes"),
    workers: Optional[int] = typer.Option(None, "--workers", "-w", help="Number of worker processes (default: CPU count)"),
    use_defaults: bool = typer.Option(False, "--default", help="Use default values without prompting"),
    use_gpu: bool = typer.Option(False, "--gpu", help="Force GPU acceleration (overrides auto-detection)"),
    force_cpu: bool = typer.Option(False, "--cpu", help="Force CPU mode (disable GPU acceleration)"),
    random_seed: Optional[int] = typer.Option(None, "--random-seed", "-r", help="Seed for deterministic randomness (0 = disabled, default: auto-generate)"),
    random_length: Optional[int] = typer.Option(None, "--random-length", "-l", help="Number of random hex characters to append to input (default: 16)")
):
    """
    Find a hash with leading or trailing zeroes using parallel processing.
    
    Prompts for any settings not provided via command-line arguments unless --default is used.
    
    GPU acceleration is auto-detected and enabled by default if available. Use --cpu to force
    CPU mode or --gpu to force GPU mode. GPU mode uses optimized batch processing with concurrent
    hashing for better performance.
    
    For true GPU SHA-256 acceleration, full OpenCL/CUDA kernel implementation would be required.
    """
    # If a subcommand was invoked, don't run the main search
    if ctx.invoked_subcommand is not None:
        return
    
    # Otherwise, run the search
    run_search(target_zeroes, prefix, check_leading, check_trailing, workers, use_defaults, use_gpu, force_cpu, random_seed, random_length)


def run_search(
    target_zeroes: Optional[int],
    prefix: Optional[str],
    check_leading: Optional[bool],
    check_trailing: Optional[bool],
    workers: Optional[int],
    use_defaults: bool,
    use_gpu: bool,
    force_cpu: bool,
    random_seed: Optional[int],
    random_length: Optional[int]
):
    # Use defaults if flag is set
    if use_defaults:
        target_zeroes = target_zeroes or 6
        prefix = prefix or "my_homelab_challenge_"
        if check_leading is None and check_trailing is None:
            check_leading = False
            check_trailing = True
    else:
        # Prompt for target_zeroes if not provided
        if target_zeroes is None:
            target_zeroes = typer.prompt("Target number of zeroes", default=6, type=int)
        
        # Prompt for prefix if not provided
        if prefix is None:
            prefix = typer.prompt("Prefix string", default="my_homelab_challenge_")
        
        # Prompt for check type if neither is provided
        if check_leading is None and check_trailing is None:
            while True:
                check_type = typer.prompt(
                    "Check for (l)eading, (t)railing, or (b)oth zeroes?",
                    default="t"
                ).lower().strip()
                if check_type in ["l", "t", "b"]:
                    break
                console.print("[yellow]Please enter 'l', 't', or 'b'[/yellow]")
            check_leading = check_type in ["l", "b"]
            check_trailing = check_type in ["t", "b"]
    
    # If only one is provided via CLI, default the other to False
    if check_leading is None:
        check_leading = False
    if check_trailing is None:
        check_trailing = False
    
    # Handle randomness parameters
    use_randomness = False
    final_random_seed = 0
    final_random_length = 0
    
    # If random_length is set, enable randomness
    if random_length is not None and random_length > 0:
        use_randomness = True
        final_random_length = random_length
        
        # Generate seed if not provided
        if random_seed is None:
            # Use a timestamp-based seed for reproducibility if desired, or use secrets for true randomness
            final_random_seed = secrets.randbits(64)  # 64-bit random seed
            console.print(f"[dim]Generated random seed: {final_random_seed}[/dim]")
        else:
            final_random_seed = random_seed
    elif random_seed is not None:
        # Seed provided but no length - ignore seed
        console.print("[yellow]Warning: random-seed provided but random-length not set. Randomness disabled.[/yellow]")
    
    # Validate configuration
    if not check_leading and not check_trailing:
        console.print("[bold red]Error:[/bold red] At least one of --leading or --trailing must be enabled")
        raise typer.Exit(1)
    
    # GPU auto-detection
    gpu_devices = []
    gpu_enabled = False
    
    if force_cpu:
        # Force CPU mode
        gpu_enabled = False
        mode_info = "[dim]CPU (forced)[/dim]"
    elif use_gpu:
        # Force GPU mode (user requested)
        if not GPU_AVAILABLE:
            console.print("[yellow]Warning:[/yellow] GPU support requested but PyOpenCL/numpy not available.")
            console.print("Install with: [cyan]pip install pyopencl numpy[/cyan]")
            console.print("Falling back to CPU mode.\n")
            gpu_enabled = False
            mode_info = "[dim]CPU (GPU unavailable)[/dim]"
        else:
            gpu_devices = get_gpu_devices()
            if not gpu_devices:
                console.print("[yellow]Warning:[/yellow] GPU support requested but no GPU devices detected.")
                console.print("For AMD GPUs:")
                console.print("  - Install latest AMD Adrenalin drivers (includes OpenCL runtime)")
                console.print("  - Download from: [cyan]https://www.amd.com/en/support[/cyan]")
                console.print("  - Run [cyan]leadingzeroes list-gpus[/cyan] to verify detection")
                console.print("Falling back to CPU mode.\n")
                gpu_enabled = False
                mode_info = "[dim]CPU (no GPU detected)[/dim]"
            else:
                gpu_enabled = True
                mode_info = f"[green]GPU (forced, {len(gpu_devices)} device(s))[/green]"
    else:
        # Auto-detect GPU
        if GPU_AVAILABLE:
            gpu_devices = get_gpu_devices()
            if gpu_devices:
                gpu_enabled = True
                mode_info = f"[green]GPU (auto-detected, {len(gpu_devices)} device(s))[/green]"
                # Show which GPU was detected
                if len(gpu_devices) == 1:
                    _, device = gpu_devices[0]
                    console.print(f"[green]✓ GPU detected:[/green] [cyan]{device.name}[/cyan]\n")
                else:
                    console.print(f"[green]✓ {len(gpu_devices)} GPU devices detected[/green]\n")
            else:
                gpu_enabled = False
                mode_info = "[dim]CPU (no GPU detected)[/dim]"
        else:
            gpu_enabled = False
            mode_info = "[dim]CPU (PyOpenCL not installed)[/dim]"
    
    # Determine number of workers (use all CPU cores by default)
    if workers is None:
        num_workers = multiprocessing.cpu_count()
    else:
        num_workers = workers
        if num_workers < 1:
            console.print("[bold red]Error:[/bold red] Number of workers must be at least 1")
            raise typer.Exit(1)
    
    # For GPU mode, use fewer workers (GPU handles parallelism internally)
    if gpu_enabled:
        num_workers = min(num_workers, 2)  # GPU workers are more efficient with fewer processes
    
    # Initialize shared state (must be done in main process)
    manager = Manager()
    total_attempts_shared = Value('i', 0)
    counter_lock_shared = Lock()
    found_solution_shared = manager.dict()
    found_solution_shared['found'] = False
    found_solution_shared['hash'] = ''
    found_solution_shared['input'] = ''
    found_solution_shared['zero_type'] = ''
    start_time_shared = Value('d', 0.0)
    console_output_queue = manager.Queue()
    
    # Build configuration display with Rich
    check_types = []
    if check_leading:
        check_types.append("[cyan]leading[/cyan]")
    if check_trailing:
        check_types.append("[cyan]trailing[/cyan]")
    
    config_table = Table(show_header=False, box=box.ROUNDED, padding=(0, 1))
    config_table.add_row("[bold]Mode:[/bold]", mode_info)
    config_table.add_row("[bold]Workers:[/bold]", f"[green]{num_workers}[/green]")
    config_table.add_row("[bold]Prefix:[/bold]", f"[yellow]{prefix}[/yellow]")
    if use_randomness:
        config_table.add_row("[bold]Randomness:[/bold]", f"[cyan]Enabled (seed: {final_random_seed}, length: {final_random_length})[/cyan]")
    else:
        config_table.add_row("[bold]Randomness:[/bold]", "[dim]Disabled[/dim]")
    config_table.add_row("[bold]Target:[/bold]", f"[magenta]{target_zeroes}[/magenta] {' or '.join(check_types)} zeroes")
    config_table.add_row("[bold]Expected:[/bold]", f"~[dim]{16**target_zeroes:,}[/dim] attempts (1 in {16**target_zeroes:,})")
    
    console.print("\n")
    console.print(Panel(config_table, title="[bold blue]Hash Search Configuration[/bold blue]", border_style="blue"))
    console.print()
    
    # Set start time
    start_time_shared.value = time.time()
    
    # Add shutdown flag for graceful exit
    shutdown_flag = Value('i', 0)
    
    # Signal handler for graceful shutdown
    def signal_handler(signum, frame):
        if shutdown_flag.value == 0:  # Only print once
            shutdown_flag.value = 1
            # Signal all workers to stop
            found_solution_shared['found'] = True
    
    # Register signal handlers
    try:
        signal.signal(signal.SIGINT, signal_handler)
        if sys.platform != 'win32':
            signal.signal(signal.SIGTERM, signal_handler)
    except (ValueError, OSError):
        # Signal handling may fail in some contexts (e.g., in threads)
        pass
    
    # Create progress bar
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("•"),
        TextColumn("[cyan]{task.completed:,}[/cyan] attempts"),
        TextColumn("•"),
        TextColumn("[green]{task.fields[rate]:,.0f}[/green] hashes/sec"),
        TextColumn("•"),
        TimeElapsedColumn(),
        console=console,
        transient=False
    )
    
    task_id = progress.add_task("[cyan]Searching for hash...", total=None, rate=0)
    
    # Start progress bar
    progress.start()
    
    solution_found = False
    
    def update_progress():
        """Update progress bar from queue messages."""
        import queue
        nonlocal solution_found
        last_update = 0
        while not solution_found and shutdown_flag.value == 0:
            try:
                msg_type, data = console_output_queue.get(timeout=0.1)
                if msg_type == 'found':
                    solution_found = True
                    progress.stop()
                    table = Table(show_header=False, box=box.DOUBLE, padding=(0, 1), border_style="green")
                    table.add_row("[bold green]FOUND![/bold green]", f"{data['target']} {data['type'].upper()} zeroes")
                    table.add_row("[bold]Hash:[/bold]", f"[yellow]{data['hash']}[/yellow]")
                    table.add_row("[bold]Input:[/bold]", f"[cyan]{data['input']}[/cyan]")
                    table.add_row("[bold]Time:[/bold]", f"{data['elapsed']:.2f} seconds")
                    table.add_row("[bold]Worker:[/bold]", f"{data['worker']}")
                    table.add_row("[bold]Total attempts:[/bold]", f"{data['attempts']:,}")
                    console.print("\n")
                    console.print(Panel(table, title="[bold green]🎉 Solution Found![/bold green]", border_style="green"))
                    console.print()
                elif msg_type == 'progress':
                    # Update progress bar
                    progress.update(
                        task_id,
                        completed=data['attempts'],
                        rate=data['rate'],
                        description="[cyan]Searching for hash..."
                    )
                    last_update = time.time()
                elif msg_type == 'error':
                    console.print(f"[yellow]Warning:[/yellow] {data}")
            except queue.Empty:
                # Update progress with current stats periodically even without new message
                current_time = time.time()
                if current_time - last_update > 0.5:  # Update every 500ms
                    if total_attempts_shared.value > 0:
                        elapsed = time.time() - start_time_shared.value
                        if elapsed > 0:
                            rate = total_attempts_shared.value / elapsed
                            progress.update(
                                task_id,
                                completed=total_attempts_shared.value,
                                rate=rate,
                                description="[cyan]Searching for hash..."
                            )
                            last_update = current_time
                continue
            except Exception:
                pass
    
    # Start progress update thread
    progress_thread = threading.Thread(target=update_progress, daemon=True)
    progress_thread.start()
    
    # Create worker processes
    processes = []
    # Use gpu_devices from detection above (already set)
    for i in range(num_workers):
        if gpu_enabled:
            # Use GPU-accelerated worker
            device_idx = i % len(gpu_devices) if gpu_devices else 0
            p = multiprocessing.Process(
                target=worker_gpu,
                args=(i, prefix, target_zeroes, check_leading, check_trailing, num_workers,
                      total_attempts_shared, counter_lock_shared, found_solution_shared, 
                      start_time_shared, console_output_queue, device_idx, 50000,
                      final_random_seed, final_random_length)
            )
        else:
            # Use CPU worker
            p = multiprocessing.Process(
                target=worker,
                args=(i, prefix, target_zeroes, check_leading, check_trailing, num_workers,
                      total_attempts_shared, counter_lock_shared, found_solution_shared, 
                      start_time_shared, console_output_queue, final_random_seed, final_random_length)
            )
        p.start()
        processes.append(p)
    
    # Wait for processes with graceful shutdown handling
    try:
        # Monitor for shutdown or completion
        while any(p.is_alive() for p in processes) and not solution_found:
            time.sleep(0.1)
            # Check if we should shutdown
            if shutdown_flag.value == 1:
                console.print("\n[yellow]Interrupt received. Shutting down gracefully...[/yellow]")
                break
        
        # Give processes a moment to finish
        for p in processes:
            if p.is_alive():
                p.join(timeout=2)
        
        # Force terminate if still running (shouldn't happen with graceful shutdown)
        if shutdown_flag.value == 1:
            for p in processes:
                if p.is_alive():
                    p.terminate()
                    p.join(timeout=1)
                    if p.is_alive():
                        p.kill()
    except KeyboardInterrupt:
        # Handle keyboard interrupt during join
        console.print("\n[yellow]Interrupt received. Shutting down...[/yellow]")
        shutdown_flag.value = 1
        found_solution_shared['found'] = True
        for p in processes:
            if p.is_alive():
                p.terminate()
                p.join(timeout=1)
                if p.is_alive():
                    p.kill()
    
    # Stop progress bar if still running
    if not solution_found:
        progress.stop()
    
    # Print final summary with Rich
    elapsed = time.time() - start_time_shared.value
    was_interrupted = shutdown_flag.value == 1 and not found_solution_shared['found']
    
    summary_table = Table(show_header=False, box=box.ROUNDED, padding=(0, 1))
    
    if was_interrupted:
        summary_table.add_row("[bold]Status:[/bold]", "[yellow]Interrupted by user[/yellow]")
        summary_table.add_row("[bold]Time elapsed:[/bold]", f"[dim]{elapsed:.2f} seconds[/dim]")
    else:
        summary_table.add_row("[bold]Search completed in:[/bold]", f"[green]{elapsed:.2f} seconds[/green]")
    
    summary_table.add_row("[bold]Total attempts:[/bold]", f"[yellow]{total_attempts_shared.value:,}[/yellow]")
    
    if found_solution_shared['found'] and found_solution_shared['hash']:
        summary_table.add_row("[bold]Solution found:[/bold]", f"[green]{found_solution_shared['zero_type']} zeroes[/green]")
        summary_table.add_row("[bold]Input:[/bold]", f"[cyan]{found_solution_shared['input']}[/cyan]")
        summary_table.add_row("[bold]Hash:[/bold]", f"[yellow]{found_solution_shared['hash']}[/yellow]")
    elif was_interrupted:
        summary_table.add_row("[bold]Solution:[/bold]", "[dim]No solution found (search interrupted)[/dim]")
    else:
        summary_table.add_row("[bold]Solution:[/bold]", "[red]No solution found[/red]")
    
    title = "[bold yellow]Search Interrupted[/bold yellow]" if was_interrupted else "[bold blue]Final Summary[/bold blue]"
    border_color = "yellow" if was_interrupted else "blue"
    
    console.print("\n")
    console.print(Panel(summary_table, title=title, border_style=border_color))
    console.print()


if __name__ == '__main__':
    multiprocessing.freeze_support()  # Required for Windows
    app()
