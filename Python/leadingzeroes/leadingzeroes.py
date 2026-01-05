import hashlib
import time
import multiprocessing
import threading
from multiprocessing import Value, Lock, Manager
import typer
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

def worker(worker_id, prefix, target_zeroes, check_leading, check_trailing, num_workers, 
           total_attempts, counter_lock, found_solution, start_time, console_output_queue):
    """
    Worker function that increments nonces and checks for target zeroes.
    Each worker starts from a different nonce range to avoid collisions.
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
        
        # Create input string with prefix and nonce
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
def main(
    target_zeroes: Optional[int] = typer.Option(None, "--target", "-t", help="Target number of zeroes to find"),
    prefix: Optional[str] = typer.Option(None, "--prefix", "-p", help="Prefix string to use before nonce"),
    check_leading: Optional[bool] = typer.Option(None, "--leading/--no-leading", help="Check for leading zeroes"),
    check_trailing: Optional[bool] = typer.Option(None, "--trailing/--no-trailing", help="Check for trailing zeroes"),
    workers: Optional[int] = typer.Option(None, "--workers", "-w", help="Number of worker processes (default: CPU count)"),
    use_defaults: bool = typer.Option(False, "--default", help="Use default values without prompting")
):
    """
    Find a hash with leading or trailing zeroes using parallel processing.
    
    Prompts for any settings not provided via command-line arguments unless --default is used.
    """
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
            check_type = typer.prompt(
                "Check for (l)eading, (t)railing, or (b)oth zeroes?",
                default="t",
                type=typer.Choice(["l", "t", "b"], case_sensitive=False)
            )
            check_leading = check_type.lower() in ["l", "b"]
            check_trailing = check_type.lower() in ["t", "b"]
    
    # If only one is provided via CLI, default the other to False
    if check_leading is None:
        check_leading = False
    if check_trailing is None:
        check_trailing = False
    
    # Validate configuration
    if not check_leading and not check_trailing:
        console.print("[bold red]Error:[/bold red] At least one of --leading or --trailing must be enabled")
        raise typer.Exit(1)
    
    # Determine number of workers (use all CPU cores by default)
    if workers is None:
        num_workers = multiprocessing.cpu_count()
    else:
        num_workers = workers
        if num_workers < 1:
            console.print("[bold red]Error:[/bold red] Number of workers must be at least 1")
            raise typer.Exit(1)
    
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
    config_table.add_row("[bold]Workers:[/bold]", f"[green]{num_workers}[/green]")
    config_table.add_row("[bold]Prefix:[/bold]", f"[yellow]{prefix}[/yellow]")
    config_table.add_row("[bold]Target:[/bold]", f"[magenta]{target_zeroes}[/magenta] {' or '.join(check_types)} zeroes")
    config_table.add_row("[bold]Expected:[/bold]", f"~[dim]{16**target_zeroes:,}[/dim] attempts (1 in {16**target_zeroes:,})")
    
    console.print("\n")
    console.print(Panel(config_table, title="[bold blue]Hash Search Configuration[/bold blue]", border_style="blue"))
    console.print()
    
    # Set start time
    start_time_shared.value = time.time()
    
    # Start a thread to monitor console output queue
    output_thread_stop = threading.Event()
    
    def output_monitor():
        import queue
        while not output_thread_stop.is_set():
            try:
                msg_type, data = console_output_queue.get(timeout=0.5)
                if msg_type == 'found':
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
                    elapsed_text = f"[dim]{data['elapsed']:.2f}s[/dim]"
                    attempts_text = f"[bold]{data['attempts']:,}[/bold] attempts"
                    rate_text = f"[cyan]{data['rate']:,.0f}[/cyan] hashes/sec"
                    console.print(f"{elapsed_text} Progress: {attempts_text} ({rate_text})")
            except queue.Empty:
                # Expected timeout, continue polling
                continue
            except Exception:
                # Ignore other exceptions to prevent thread crash
                pass
    
    output_thread = threading.Thread(target=output_monitor, daemon=True)
    output_thread.start()
    
    # Create worker processes
    processes = []
    for i in range(num_workers):
        p = multiprocessing.Process(
            target=worker,
            args=(i, prefix, target_zeroes, check_leading, check_trailing, num_workers,
                  total_attempts_shared, counter_lock_shared, found_solution_shared, 
                  start_time_shared, console_output_queue)
        )
        p.start()
        processes.append(p)
    
    # Wait for all processes to complete
    for p in processes:
        p.join()
    
    # Stop output monitor
    output_thread_stop.set()
    output_thread.join(timeout=1)
    
    # Print final summary with Rich
    elapsed = time.time() - start_time_shared.value
    summary_table = Table(show_header=False, box=box.ROUNDED, padding=(0, 1))
    summary_table.add_row("[bold]Search completed in:[/bold]", f"[green]{elapsed:.2f} seconds[/green]")
    summary_table.add_row("[bold]Total attempts:[/bold]", f"[yellow]{total_attempts_shared.value:,}[/yellow]")
    
    if found_solution_shared['found']:
        summary_table.add_row("[bold]Solution found:[/bold]", f"[green]{found_solution_shared['zero_type']} zeroes[/green]")
        summary_table.add_row("[bold]Input:[/bold]", f"[cyan]{found_solution_shared['input']}[/cyan]")
        summary_table.add_row("[bold]Hash:[/bold]", f"[yellow]{found_solution_shared['hash']}[/yellow]")
    else:
        summary_table.add_row("[bold]Status:[/bold]", "[red]No solution found (shouldn't happen if we found one)[/red]")
    
    console.print("\n")
    console.print(Panel(summary_table, title="[bold blue]Final Summary[/bold blue]", border_style="blue"))
    console.print()


if __name__ == '__main__':
    multiprocessing.freeze_support()  # Required for Windows
    app()
