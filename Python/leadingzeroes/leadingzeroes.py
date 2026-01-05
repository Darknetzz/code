import hashlib
import time
import multiprocessing
import threading
import signal
import sys
import secrets
import os
from pathlib import Path
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

def find_longest_recurring(hash_str: str, min_length: int = 3, find_any: bool = False) -> tuple:
    """
    Find recurring patterns in a hash string.
    
    Args:
        min_length: Minimum length of pattern to find
        find_any: If True, finds ANY recurring character (even 2 chars), ignoring min_length
    
    Returns:
        (pattern_length, pattern_type, pattern) where:
        - pattern_length: Length of the recurring pattern
        - pattern_type: 'same_char' for all same character, 'repeating' for repeating sequence
        - pattern: The actual pattern found
    """
    if find_any:
        min_length = 2  # Override to find any repetition
        # Ultra-fast path: just check for any 2 consecutive identical characters
        for i in range(len(hash_str) - 1):
            if hash_str[i] == hash_str[i + 1]:
                # Found 2 consecutive, now find how many
                char = hash_str[i]
                length = 2
                j = i + 2
                while j < len(hash_str) and hash_str[j] == char:
                    length += 1
                    j += 1
                return (length, 'same_char', char * length)
        return (0, None, None)
    
    if len(hash_str) < min_length:
        return (0, None, None)
    
    max_len = 0
    max_pattern = None
    max_type = None
    
    # Check for same character sequences (e.g., "aaaa", "0000")
    i = 0
    while i < len(hash_str):
        char = hash_str[i]
        j = i + 1
        while j < len(hash_str) and hash_str[j] == char:
            j += 1
        length = j - i
        if length >= min_length and length > max_len:
            max_len = length
            max_pattern = char * length
            max_type = 'same_char'
        i = j
    
    # For find_any mode, we already returned above, so skip expensive repeating check
    if find_any:
        return (max_len, max_type, max_pattern)
    
    # Check for repeating sequences (e.g., "ababab", "123123")
    for seq_len in range(1, len(hash_str) // 2 + 1):
        for start in range(len(hash_str) - seq_len * 2 + 1):
            pattern = hash_str[start:start + seq_len]
            # Check if pattern repeats
            repeats = 1
            pos = start + seq_len
            while pos + seq_len <= len(hash_str) and hash_str[pos:pos + seq_len] == pattern:
                repeats += 1
                pos += seq_len
            
            total_length = repeats * seq_len
            if repeats >= 2 and total_length >= min_length and total_length > max_len:
                max_len = total_length
                max_pattern = pattern * repeats
                max_type = 'repeating'
    
    return (max_len, max_type, max_pattern)


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


# Embedded OpenCL SHA-256 kernel source
# This is embedded directly so it works with PyInstaller executables
SHA256_KERNEL_SOURCE = """// sha256.cl
// Optimized for AMD RDNA3 (7800 XT)
// Limitation: Input strings must be < 55 bytes.

typedef unsigned int uint;
typedef unsigned char uchar;

// SHA-256 Constants
__constant uint K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

// Rotations and bitwise helpers
#define ROTRIGHT(a,b) (((a) >> (b)) | ((a) << (32-(b))))
#define CH(x,y,z) (((x) & (y)) ^ (~(x) & (z)))
#define MAJ(x,y,z) (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define EP0(x) (ROTRIGHT(x,2) ^ ROTRIGHT(x,13) ^ ROTRIGHT(x,22))
#define EP1(x) (ROTRIGHT(x,6) ^ ROTRIGHT(x,11) ^ ROTRIGHT(x,25))
#define SIG0(x) (ROTRIGHT(x,7) ^ ROTRIGHT(x,18) ^ ((x) >> 3))
#define SIG1(x) (ROTRIGHT(x,17) ^ ROTRIGHT(x,19) ^ ((x) >> 10))

// Function to swap endianness (GPU is Little Endian, SHA is Big Endian)
uint swap_endian(uint val) {
    return ((val >> 24) & 0xff) | ((val << 8) & 0xff0000) |
           ((val >> 8) & 0xff00) | ((val << 24) & 0xff000000);
}

__kernel void sha256_kernel(
    __global const uchar *input_buffer, // All inputs flattened
    __global uchar *output_hashes,      // Output buffer
    const int stride                    // Fixed length of each input slot (e.g., 64)
) {
    int gid = get_global_id(0);
    
    // Locate my specific input string
    __global const uchar *my_input = &input_buffer[gid * stride];
    
    // 1. Prepare Message Schedule (W)
    uint W[64];
    
    // Initialize W buffer to 0
    for(int i=0; i<64; i++) W[i] = 0;

    // --- PADDING & LOADING ---
    // We manually copy bytes into W integers, swapping endianness as we go
    // This effectively pads the message into the W array
    
    int len = 0;
    // Calculate length (up to stride)
    for(int i=0; i<stride; i++) {
        if(my_input[i] == 0) break;
        len++;
    }
    
    // Load bytes into W
    for(int i=0; i<len; i++) {
        int w_idx = i / 4;
        int shift = (3 - (i % 4)) * 8; // Big Endian packing
        W[w_idx] |= ((uint)my_input[i]) << shift;
    }
    
    // Append the "1" bit (0x80 byte)
    int w_idx = len / 4;
    int shift = (3 - (len % 4)) * 8;
    W[w_idx] |= ((uint)0x80) << shift;
    
    // Append Length in bits at the very end (W[15])
    // SHA256 uses 64-bit length, but we only support lengths < 55 bytes, 
    // so we only need the lower 32 bits of the length.
    W[15] = len * 8;

    // --- MESSAGE SCHEDULE EXPANSION ---
    for (int i = 16; i < 64; ++i) {
        W[i] = SIG1(W[i - 2]) + W[i - 7] + SIG0(W[i - 15]) + W[i - 16];
    }

    // --- INITIAL HASH STATE ---
    uint a = 0x6a09e667;
    uint b = 0xbb67ae85;
    uint c = 0x3c6ef372;
    uint d = 0xa54ff53a;
    uint e = 0x510e527f;
    uint f = 0x9b05688c;
    uint g = 0x1f83d9ab;
    uint h = 0x5be0cd19;

    // --- COMPRESSION LOOP ---
    for (int i = 0; i < 64; ++i) {
        uint t1 = h + EP1(e) + CH(e, f, g) + K[i] + W[i];
        uint t2 = EP0(a) + MAJ(a, b, c);
        h = g;
        g = f;
        f = e;
        e = d + t1;
        d = c;
        c = b;
        b = a;
        a = t1 + t2;
    }

    // --- ADD STATE TO INITIAL ---
    uint h0 = 0x6a09e667 + a;
    uint h1 = 0xbb67ae85 + b;
    uint h2 = 0x3c6ef372 + c;
    uint h3 = 0xa54ff53a + d;
    uint h4 = 0x510e527f + e;
    uint h5 = 0x9b05688c + f;
    uint h6 = 0x1f83d9ab + g;
    uint h7 = 0x5be0cd19 + h;

    // --- WRITE OUTPUT (Big Endian) ---
    __global uint* res_ptr = (__global uint*)&output_hashes[gid * 32];
    
    // We must swap back to Big Endian for the final hash string to look correct
    res_ptr[0] = swap_endian(h0);
    res_ptr[1] = swap_endian(h1);
    res_ptr[2] = swap_endian(h2);
    res_ptr[3] = swap_endian(h3);
    res_ptr[4] = swap_endian(h4);
    res_ptr[5] = swap_endian(h5);
    res_ptr[6] = swap_endian(h6);
    res_ptr[7] = swap_endian(h7);
}
"""


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


def load_opencl_kernel(device_idx=0):
    """Load and compile the OpenCL SHA-256 kernel."""
    if not GPU_AVAILABLE:
        return None, None, None
    
    try:
        devices = get_gpu_devices()
        if not devices or device_idx >= len(devices):
            return None, None, None
        
        platform, device = devices[device_idx]
        
        # Create context and queue
        ctx = cl.Context([device])
        queue = cl.CommandQueue(ctx)
        
        # Use embedded kernel source (works in both script and PyInstaller executable)
        kernel_source = SHA256_KERNEL_SOURCE
        
        # Compile program
        program = cl.Program(ctx, kernel_source).build()
        kernel = program.sha256_kernel
        
        return ctx, queue, kernel
    except Exception as e:
        # Kernel loading failed, return None
        # In debug mode, you could log the error here
        return None, None, None


def worker_gpu(worker_id, prefix, target_zeroes, check_leading, check_trailing, 
               num_workers, total_attempts, counter_lock, found_solution, 
               start_time, console_output_queue, device_idx=0, batch_size=50000,
               random_seed=0, random_length=0, check_recurring=False, recurring_min_length=3, recurring_find_any=False):
    """
    GPU-accelerated worker using OpenCL SHA-256 kernel.
    
    Args:
        random_seed: Seed for deterministic randomness (0 = no randomness)
        random_length: Number of random hex characters to append (0 = no randomness)
        check_recurring: Check for recurring character patterns
        recurring_min_length: Minimum length of recurring pattern to match
    """
    if not GPU_AVAILABLE:
        # Fallback to CPU if GPU not available
        return
    
    # Load OpenCL kernel
    try:
        ctx, queue, kernel = load_opencl_kernel(device_idx)
        if ctx is None or queue is None or kernel is None:
            # Kernel loading failed, fallback to CPU
            return
    except Exception as e:
        # Kernel loading failed, exit worker gracefully
        return
    
    target_leading = '0' * target_zeroes
    target_trailing = '0' * target_zeroes
    
    nonce = worker_id
    local_attempts = 0
    
    # Input stride: 64 bytes per input (kernel limitation: inputs must be < 55 bytes)
    stride = 64
    max_input_length = 54  # Stay under 55 bytes for kernel compatibility
    
    while True:
        if found_solution['found']:
            return
        
        # Prepare batch
        batch_nonces = [nonce + i * num_workers for i in range(batch_size)]
        
        # Build input buffer
        input_buffer = np.zeros(batch_size * stride, dtype=np.uint8)
        
        input_strings = []
        for i, nonce_val in enumerate(batch_nonces):
            # Create input string (must be < 55 bytes)
            if random_length > 0 and random_seed != 0:
                random_part = generate_deterministic_random(nonce_val, random_seed, random_length)
                input_str = f"{prefix}{nonce_val}{random_part}"
            else:
                input_str = f"{prefix}{nonce_val}"
            
            # Check length limit
            input_bytes = input_str.encode('utf-8')
            if len(input_bytes) > max_input_length:
                # Truncate if too long (shouldn't happen in normal use)
                input_bytes = input_bytes[:max_input_length]
            
            input_strings.append(input_str)
            
            # Copy bytes into buffer
            offset = i * stride
            input_buffer[offset:offset + len(input_bytes)] = np.array(list(input_bytes), dtype=np.uint8)
        
        try:
            # Allocate GPU buffers
            input_buf = cl.Buffer(ctx, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR, hostbuf=input_buffer)
            output_buf = cl.Buffer(ctx, cl.mem_flags.WRITE_ONLY, batch_size * 32)  # 32 bytes per hash
            
            # Execute kernel
            kernel.set_arg(0, input_buf)
            kernel.set_arg(1, output_buf)
            kernel.set_arg(2, np.int32(stride))
            
            cl.enqueue_nd_range_kernel(queue, kernel, (batch_size,), None)
            queue.finish()
            
            # Read results
            output_array = np.empty(batch_size * 32, dtype=np.uint8)
            cl.enqueue_copy(queue, output_array, output_buf)
            queue.finish()
        except Exception as e:
            # OpenCL error occurred, exit worker gracefully
            # The process will terminate and main process will handle it
            return
        
        # Process results
        for i in range(batch_size):
            # Extract hash (32 bytes)
            hash_bytes = bytes(output_array[i * 32:(i + 1) * 32])
            hash_hex = hash_bytes.hex()
            
            input_str = input_strings[i]
            
            # Check for matches
            found = None
            zero_type = None
            pattern = None
            pattern_length = None
            
            if check_leading and hash_hex.startswith(target_leading):
                found = True
                zero_type = 'leading'
            elif check_trailing and hash_hex.endswith(target_trailing):
                found = True
                zero_type = 'trailing'
            elif check_recurring:
                effective_min = 2 if recurring_find_any else recurring_min_length
                pattern_len, pattern_type, pattern_found = find_longest_recurring(hash_hex, effective_min, recurring_find_any)
                if pattern_len >= effective_min:
                    found = True
                    zero_type = f'recurring_{pattern_type}'
                    pattern = pattern_found
                    pattern_length = pattern_len
            
            if found:
                with counter_lock:
                    total_attempts.value += local_attempts + (i + 1)
                    if not found_solution['found']:
                        found_solution['found'] = True
                        found_solution['hash'] = hash_hex
                        found_solution['input'] = input_str
                        found_solution['zero_type'] = zero_type
                        elapsed = time.time() - start_time.value
                        current_total = total_attempts.value
                        found_data = {
                            'type': zero_type,
                            'target': target_zeroes if 'recurring' not in zero_type else pattern_length,
                            'hash': hash_hex,
                            'input': input_str,
                            'elapsed': elapsed,
                            'worker': worker_id + 1,
                            'attempts': current_total
                        }
                        if pattern:
                            found_data['pattern'] = pattern
                            found_data['pattern_length'] = pattern_length
                        console_output_queue.put(('found', found_data))
                        return
        
        local_attempts += batch_size
        nonce += batch_size * num_workers
        
        # Update counter periodically
        if local_attempts % 10000 == 0:
            with counter_lock:
                total_attempts.value += local_attempts
                current_total = total_attempts.value
                if current_total % 1000000 == 0 and current_total > 0:
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
           random_seed=0, random_length=0, check_recurring=False, recurring_min_length=3, recurring_find_any=False):
    """
    Worker function that increments nonces and checks for target zeroes.
    Each worker starts from a different nonce range to avoid collisions.
    
    Args:
        random_seed: Seed for deterministic randomness (0 = no randomness)
        random_length: Number of random hex characters to append (0 = no randomness)
        check_recurring: Check for recurring character patterns
        recurring_min_length: Minimum length of recurring pattern to match
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
                # Add local attempts to global counter before reporting
                total_attempts.value += local_attempts
                if not found_solution['found']:
                    found_solution['found'] = True
                    found_solution['hash'] = hash_result
                    found_solution['input'] = input_str
                    found_solution['zero_type'] = 'leading'
                    elapsed = time.time() - start_time.value
                    current_total = total_attempts.value
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
                    local_attempts = 0  # Reset after reporting
            return
        
        # Check trailing zeroes
        if check_trailing and hash_result.endswith(target_trailing):
            with counter_lock:
                # Add local attempts to global counter before reporting
                total_attempts.value += local_attempts
                if not found_solution['found']:
                    found_solution['found'] = True
                    found_solution['hash'] = hash_result
                    found_solution['input'] = input_str
                    found_solution['zero_type'] = 'trailing'
                    elapsed = time.time() - start_time.value
                    current_total = total_attempts.value
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
                    local_attempts = 0  # Reset after reporting
            return
        
        # Check for recurring patterns
        if check_recurring:
            effective_min = 2 if recurring_find_any else recurring_min_length
            pattern_len, pattern_type, pattern = find_longest_recurring(hash_result, effective_min, recurring_find_any)
            if pattern_len >= effective_min:
                with counter_lock:
                    # Add local attempts to global counter before reporting
                    total_attempts.value += local_attempts
                    if not found_solution['found']:
                        found_solution['found'] = True
                        found_solution['hash'] = hash_result
                        found_solution['input'] = input_str
                        found_solution['zero_type'] = f'recurring_{pattern_type}'
                        elapsed = time.time() - start_time.value
                        current_total = total_attempts.value
                        # Send formatted output to queue for main process to display
                        console_output_queue.put(('found', {
                            'type': f'recurring_{pattern_type}',
                            'target': pattern_len,
                            'hash': hash_result,
                            'input': input_str,
                            'elapsed': elapsed,
                            'worker': worker_id + 1,
                            'attempts': current_total,
                            'pattern': pattern,
                            'pattern_length': pattern_len
                        }))
                        local_attempts = 0  # Reset after reporting
                return
        
        nonce += num_workers  # Stride by num_workers to maintain separation
        
        # Update global counter periodically (every 10k iterations for better progress updates)
        if local_attempts % 10000 == 0:
            with counter_lock:
                total_attempts.value += local_attempts
                
                # Send progress updates every 1M attempts (more frequent updates)
                current_total = total_attempts.value
                if current_total % 1000000 == 0 and current_total > 0:
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
        console.print()



@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    target_zeroes: Optional[int] = typer.Option(None, "--target", "-t", help="Target number of zeroes to find"),
    prefix: Optional[str] = typer.Option(None, "--prefix", "-p", help="Prefix string to use before nonce"),
    check_leading: Optional[bool] = typer.Option(None, "--leading/--no-leading", help="Check for leading zeroes"),
    check_trailing: Optional[bool] = typer.Option(None, "--trailing/--no-trailing", help="Check for trailing zeroes"),
    check_recurring: bool = typer.Option(False, "--recurring", help="Check for recurring character patterns"),
    recurring_min_length: int = typer.Option(3, "--recurring-min", help="Minimum length of recurring pattern to match"),
    recurring_find_any: bool = typer.Option(False, "--recurring-any", help="Find ANY recurring characters (minimum 2, ignores --recurring-min)"),
    workers: Optional[int] = typer.Option(None, "--workers", "-w", help="Number of worker processes (default: CPU count)"),
    use_defaults: bool = typer.Option(False, "--default", help="Use default values without prompting"),
    use_gpu: bool = typer.Option(False, "--gpu", help="Force GPU acceleration (overrides auto-detection)"),
    force_cpu: bool = typer.Option(False, "--cpu", help="Force CPU mode (disable GPU acceleration)"),
    random_seed: Optional[int] = typer.Option(None, "--random-seed", "-r", help="Seed for deterministic randomness (0 = disabled, default: auto-generate)"),
    random_length: Optional[int] = typer.Option(None, "--random-length", "-l", help="Enable randomness and append N hex characters to input (disabled by default)")
):
    """
    Find a hash with leading or trailing zeroes using parallel processing.
    
    Prompts for any settings not provided via command-line arguments unless --default is used.
    
    GPU acceleration is auto-detected and enabled by default if available. Use --cpu to force
    CPU mode or --gpu to force GPU mode. GPU mode uses real OpenCL kernel acceleration.
    """
    # If a subcommand was invoked, don't run the main search
    if ctx.invoked_subcommand is not None:
        return
    
    # Otherwise, run the search
    run_search(target_zeroes, prefix, check_leading, check_trailing, check_recurring,
               recurring_min_length, recurring_find_any, workers, use_defaults, use_gpu,
               force_cpu, random_seed, random_length)


def run_search(
    target_zeroes: Optional[int],
    prefix: Optional[str],
    check_leading: Optional[bool],
    check_trailing: Optional[bool],
    check_recurring: bool,
    recurring_min_length: int,
    recurring_find_any: bool,
    workers: Optional[int],
    use_defaults: bool,
    use_gpu: bool,
    force_cpu: bool,
    random_seed: Optional[int],
    random_length: Optional[int]
):
    # Auto-enable recurring if --recurring-any is provided
    if recurring_find_any:
        check_recurring = True
    
    # Prompt for settings if not provided (unless --default is used)
    if not use_defaults:
        if target_zeroes is None and not check_recurring:
            target_zeroes_input = typer.prompt("Target number of zeroes", default=6, type=int)
            target_zeroes = target_zeroes_input
        
        if prefix is None:
            prefix_input = typer.prompt("Prefix string", default="my_homelab_challenge_", type=str)
            prefix = prefix_input
        
        if check_leading is None and check_trailing is None and not check_recurring:
            check_type = typer.prompt("Check for (l)eading, (t)railing, or (b)oth zeroes?", default="t", type=str).lower()
            if 'l' in check_type:
                check_leading = True
            if 't' in check_type:
                check_trailing = True
            if 'b' in check_type:
                check_leading = True
                check_trailing = True
        
        if check_leading is None:
            check_leading = False
        if check_trailing is None:
            check_trailing = False
    else:
        # Use defaults
        if target_zeroes is None:
            target_zeroes = 6
        if prefix is None:
            prefix = "my_homelab_challenge_"
        if check_leading is None:
            check_leading = False
        if check_trailing is None:
            check_trailing = True
    
    # Validate that at least one check type is enabled
    if not check_leading and not check_trailing and not check_recurring:
        console.print("[bold red]Error:[/bold red] Must specify at least one check type (--leading, --trailing, or --recurring)")
        raise typer.Exit(1)
    
    # Handle randomness options
    use_randomness = False
    final_random_seed = 0
    final_random_length = 0
    
    if random_length is not None:
        if random_length > 0:
            use_randomness = True
            final_random_length = random_length
            if random_seed is None or random_seed == 0:
                # Auto-generate seed
                final_random_seed = secrets.randbits(64)
            else:
                final_random_seed = random_seed
        else:
            use_randomness = False
            final_random_seed = 0
            final_random_length = 0
    
    # Determine GPU/CPU mode
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
                mode_info = f"[green]GPU (OpenCL, {len(gpu_devices)} device(s))[/green]"
    else:
        # Auto-detect GPU
        if GPU_AVAILABLE:
            gpu_devices = get_gpu_devices()
            if gpu_devices:
                gpu_enabled = True
                mode_info = f"[green]GPU (OpenCL, {len(gpu_devices)} device(s))[/green]"
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
    
    # For GPU mode, check input length compatibility
    # GPU kernel has a 54-byte limit, so check if inputs would be too long
    if gpu_enabled:
        # Estimate max input length: prefix + max nonce digits + random_length
        max_nonce_digits = 20  # Reasonable estimate for large nonces
        estimated_max_length = len(prefix.encode('utf-8')) + max_nonce_digits + final_random_length
        
        if estimated_max_length > 54:
            console.print(f"[yellow]Warning:[/yellow] Input strings would exceed GPU kernel limit (54 bytes).")
            console.print(f"  Estimated length: {estimated_max_length} bytes (prefix: {len(prefix.encode('utf-8'))}, random: {final_random_length})")
            console.print(f"  Falling back to CPU mode for compatibility.\n")
            gpu_enabled = False
            mode_info = "[dim]CPU (input too long for GPU kernel)[/dim]"
        else:
            num_workers = min(num_workers, 2)  # GPU workers are more efficient with fewer processes
    
    # Initialize shared state (must be done in main process)
    manager = Manager()
    total_attempts_shared = Value('q', 0)  # Use 64-bit integer to avoid overflow
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
    if check_recurring:
        if recurring_find_any:
            check_types.append("[cyan]recurring[/cyan] (any: min 2 chars)")
        else:
            check_types.append(f"[cyan]recurring[/cyan] (min: {recurring_min_length})")
    
    config_table = Table(show_header=False, box=box.ROUNDED, padding=(0, 1))
    config_table.add_row("[bold]Mode:[/bold]", mode_info)
    config_table.add_row("[bold]Workers:[/bold]", f"[green]{num_workers}[/green]")
    config_table.add_row("[bold]Prefix:[/bold]", f"[yellow]{prefix}[/yellow]")
    if use_randomness:
        config_table.add_row("[bold]Randomness:[/bold]", f"[cyan]Enabled (seed: {final_random_seed}, length: {final_random_length})[/cyan]")
    else:
        config_table.add_row("[bold]Randomness:[/bold]", "[dim]Disabled[/dim]")
    
    target_text = f"[magenta]{target_zeroes}[/magenta] {' or '.join(check_types)}"
    if check_recurring and (check_leading or check_trailing):
        target_text += f" zeroes / recurring patterns"
    elif check_leading or check_trailing:
        target_text += " zeroes"
    else:
        target_text += " patterns"
    
    config_table.add_row("[bold]Target:[/bold]", target_text)
    
    if check_leading or check_trailing:
        config_table.add_row("[bold]Expected:[/bold]", f"~[dim]{16**target_zeroes:,}[/dim] attempts (1 in {16**target_zeroes:,})")
    else:
        config_table.add_row("[bold]Expected:[/bold]", "[dim]Varies based on pattern[/dim]")
    
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
        BarColumn(),
        TextColumn("[progress.description]{task.description}"),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console
    )
    
    # Start output monitor thread
    def output_monitor():
        with progress:
            task = progress.add_task("[cyan]Searching for hash...", total=None)
            
            last_update = time.time()
            update_interval = 0.2  # Update progress bar every 200ms
            
            while True:
                try:
                    # Check if solution found (with error handling for broken pipes)
                    try:
                        if found_solution_shared['found']:
                            break
                    except (BrokenPipeError, OSError, ConnectionError):
                        # Worker processes crashed, exit monitor
                        break
                    
                    message_type, data = console_output_queue.get(timeout=0.1)
                    
                    if message_type == 'found':
                        progress.update(task, description="[green]✓ Solution found![/green]")
                        # Display found solution
                        console.print("\n")
                        if data['type'].startswith('recurring_'):
                            pattern_type = data['type'].replace('recurring_', '')
                            found_table = Table(show_header=False, box=box.ROUNDED, padding=(0, 1))
                            found_table.add_row("[bold]Type:[/bold]", f"[green]{pattern_type} pattern[/green]")
                            found_table.add_row("[bold]Pattern:[/bold]", f"[cyan]{data.get('pattern', 'N/A')}[/cyan]")
                            found_table.add_row("[bold]Length:[/bold]", f"[magenta]{data.get('pattern_length', data['target'])}[/magenta]")
                            found_table.add_row("[bold]Hash:[/bold]", f"[yellow]{data['hash']}[/yellow]")
                            found_table.add_row("[bold]Input:[/bold]", f"[dim]{data['input']}[/dim]")
                            found_table.add_row("[bold]Worker:[/bold]", f"[cyan]{data['worker']}[/cyan]")
                            found_table.add_row("[bold]Attempts:[/bold]", f"[dim]{data['attempts']:,}[/dim]")
                            found_table.add_row("[bold]Time:[/bold]", f"[dim]{data['elapsed']:.2f}s[/dim]")
                            console.print(Panel(found_table, title="[bold green]Solution Found![/bold green]", border_style="green"))
                        else:
                            found_table = Table(show_header=False, box=box.ROUNDED, padding=(0, 1))
                            found_table.add_row("[bold]Type:[/bold]", f"[green]{data['type']} zeroes[/green]")
                            found_table.add_row("[bold]Target:[/bold]", f"[magenta]{data['target']}[/magenta]")
                            found_table.add_row("[bold]Hash:[/bold]", f"[yellow]{data['hash']}[/yellow]")
                            found_table.add_row("[bold]Input:[/bold]", f"[dim]{data['input']}[/dim]")
                            found_table.add_row("[bold]Worker:[/bold]", f"[cyan]{data['worker']}[/cyan]")
                            found_table.add_row("[bold]Attempts:[/bold]", f"[dim]{data['attempts']:,}[/dim]")
                            found_table.add_row("[bold]Time:[/bold]", f"[dim]{data['elapsed']:.2f}s[/dim]")
                            console.print(Panel(found_table, title="[bold green]Solution Found![/bold green]", border_style="green"))
                        break
                    elif message_type == 'progress':
                        current_time = time.time()
                        if current_time - last_update >= update_interval:
                            rate = data['rate']
                            progress.update(
                                task,
                                description=f"[cyan]Searching for hash...[/cyan] • [dim]{data['attempts']:,}[/dim] attempts • [dim]{rate:,.0f}[/dim] hashes/sec • [dim]{data['elapsed']:.0f}s[/dim]"
                            )
                            last_update = current_time
                except (BrokenPipeError, OSError, ConnectionError):
                    # Worker processes crashed, exit monitor
                    break
                except:
                    # Timeout or queue empty, continue
                    pass
            
            # Final summary
            if found_solution_shared['found']:
                elapsed = time.time() - start_time_shared.value
                final_total = total_attempts_shared.value
                rate = final_total / elapsed if elapsed > 0 else 0
                
                console.print("\n")
                summary_table = Table(show_header=False, box=box.ROUNDED, padding=(0, 1))
                summary_table.add_row("[bold]Total Attempts:[/bold]", f"[cyan]{final_total:,}[/cyan]")
                summary_table.add_row("[bold]Total Time:[/bold]", f"[cyan]{elapsed:.2f}s[/cyan]")
                summary_table.add_row("[bold]Average Rate:[/bold]", f"[cyan]{rate:,.0f} hashes/sec[/cyan]")
                console.print(Panel(summary_table, title="[bold blue]Summary[/bold blue]", border_style="blue"))
    
    monitor_thread = threading.Thread(target=output_monitor, daemon=True)
    monitor_thread.start()
    
    # Start worker processes
    processes = []
    try:
        for i in range(num_workers):
            if gpu_enabled:
                p = multiprocessing.Process(
                    target=worker_gpu,
                    args=(i, prefix, target_zeroes, check_leading, check_trailing, num_workers,
                          total_attempts_shared, counter_lock_shared, found_solution_shared,
                          start_time_shared, console_output_queue, i % len(get_gpu_devices()) if GPU_AVAILABLE else 0, 50000,
                          final_random_seed, final_random_length, check_recurring, recurring_min_length, recurring_find_any)
                )
            else:
                p = multiprocessing.Process(
                    target=worker,
                    args=(i, prefix, target_zeroes, check_leading, check_trailing, num_workers,
                          total_attempts_shared, counter_lock_shared, found_solution_shared,
                          start_time_shared, console_output_queue,
                          final_random_seed, final_random_length, check_recurring, recurring_min_length, recurring_find_any)
                )
            p.start()
            processes.append(p)
        
        # Wait for all processes to complete
        for p in processes:
            p.join()
    
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        found_solution_shared['found'] = True
        for p in processes:
            p.terminate()
            p.join(timeout=1)
            if p.is_alive():
                p.kill()


if __name__ == "__main__":
    # Required for PyInstaller/frozen executables with multiprocessing
    multiprocessing.freeze_support()
    
    # Filter out PyInstaller's injected multiprocessing option if present
    # (PyInstaller may inject --multiprocessing-fork which Typer doesn't recognize)
    if '--multiprocessing-fork' in sys.argv:
        sys.argv.remove('--multiprocessing-fork')
    
    # Set multiprocessing start method (spawn is default on Windows, required for PyInstaller)
    if sys.platform == 'win32':
        try:
            multiprocessing.set_start_method('spawn', force=True)
        except RuntimeError:
            # Start method already set, ignore
            pass
    
    app()
