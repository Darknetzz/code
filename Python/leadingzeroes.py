import time
import random
import hashlib
import string
import multiprocessing
from multiprocessing import Value, Lock

# Shared counters for all processes
total_attempts = Value('i', 0)
max_leading = Value('i', 0)
max_trailing = Value('i', 0)
last_progress_milestone = Value('i', -1)  # Track last progress milestone printed (start at -1)
counter_lock = Lock()
start_time = Value('d', 0.0)  # Use shared Value so all processes see the same start time

def worker(worker_id, target_zeroes):
    """
    Worker function that creates a hash chain and checks for zeroes.
    
    Each worker maintains its own hash chain (iteratively hashing the previous hash)
    and tracks local maximums for leading/trailing zeroes. When new records are found,
    they're reported and checked against the global maximum.
    """
    local_attempts = 0
    worker_total_iterations = 0  # Track this worker's total iterations
    local_max_leading = 0
    local_max_trailing = 0
    
    # Start with a random string to ensure each worker has a different starting point
    rand_str = ''.join(random.choices(string.ascii_letters + string.digits, k=64))
    hash_obj = hashlib.sha256(rand_str.encode())
    hash_hex = hash_obj.hexdigest()
    
    print(f"Worker {worker_id + 1} starting with: {hash_hex}")
    
    while True:
        # Hash the previous hash (chain iteration)
        hash_obj = hashlib.sha256(hash_hex.encode())
        hash_hex = hash_obj.hexdigest()
        
        # Count leading zeroes (consecutive zeros from the start)
        leading = len(hash_hex) - len(hash_hex.lstrip('0'))
        
        # Count trailing zeroes (consecutive zeros at the end)
        trailing = len(hash_hex) - len(hash_hex.rstrip('0'))
        
        local_attempts += 1
        worker_total_iterations += 1
        
        # Check if we found a new record for leading zeroes
        if leading > local_max_leading:
            local_max_leading = leading
            with counter_lock:
                # Only report if it's a new global record
                if leading > max_leading.value:
                    max_leading.value = leading
                    # Calculate elapsed time and current total attempts across all workers
                    elapsed = time.time() - start_time.value
                    # Include this worker's pending attempts in the total
                    current_total = total_attempts.value + local_attempts
                    print(f"[{elapsed:.2f}s] Worker {worker_id + 1}: Found {leading} LEADING zeroes!")
                    print(f"  Hash:   {hash_hex}")
                    print(f"  Worker iteration: {worker_total_iterations:,}")
                    print(f"  Global total attempts: {current_total:,}\n")
                    
                    if leading >= target_zeroes:
                        return
        
        # Check if we found a new record for trailing zeroes
        if trailing > local_max_trailing:
            local_max_trailing = trailing
            with counter_lock:
                # Only report if it's a new global record
                if trailing > max_trailing.value:
                    max_trailing.value = trailing
                    # Calculate elapsed time and current total attempts across all workers
                    elapsed = time.time() - start_time.value
                    # Include this worker's pending attempts in the total
                    current_total = total_attempts.value + local_attempts
                    print(f"[{elapsed:.2f}s] Worker {worker_id + 1}: Found {trailing} TRAILING zeroes!")
                    print(f"  Hash:   {hash_hex}")
                    print(f"  Worker iteration: {worker_total_iterations:,}")
                    print(f"  Global total attempts: {current_total:,}\n")
                    
                    if trailing >= target_zeroes:
                        return
        
        # Update global counter periodically (every 100k iterations)
        if local_attempts % 100000 == 0:
            with counter_lock:
                # Update the global counter with this worker's contributions
                total_attempts.value += local_attempts
                
                # Calculate current milestone (which 100M we're at)
                current_milestone = total_attempts.value // 100000000
                
                # Only print progress when we hit a NEW milestone (strictly greater)
                # Check and update atomically to prevent multiple workers from printing
                if current_milestone > last_progress_milestone.value:
                    # Update the milestone counter FIRST to prevent other workers from printing
                    last_progress_milestone.value = current_milestone
                    
                    # Now calculate time and rate
                    elapsed = time.time() - start_time.value
                    if elapsed > 0.001:  # Avoid division by very small numbers
                        rate = total_attempts.value / elapsed
                        # Format rate with 2 decimal places for better readability
                        print(f"[{elapsed:.2f}s] Progress: {total_attempts.value:,} attempts ({rate:,.2f} hashes/sec)")
                
                # Reset local counter after adding to global
                local_attempts = 0

def main():
    target = 9  # Target number of zeroes
    num_workers = multiprocessing.cpu_count()
    
    print(f"Starting hash search with {num_workers} parallel workers")
    print(f"Target: {target} leading or trailing zeroes")
    print(f"Expected attempts: ~{16**target:,} (probability: 1 in {16**target:,})")
    print("=" * 70 + "\n")
    
    # Set the shared start time so all worker processes see the same value
    start_time.value = time.time()
    
    # Create worker processes
    processes = []
    for i in range(num_workers):
        p = multiprocessing.Process(target=worker, args=(i, target))
        p.start()
        processes.append(p)
    
    # Wait for all processes to complete
    for p in processes:
        p.join()
    
    elapsed = time.time() - start_time
    print(f"\nSearch completed in {elapsed:.2f} seconds")
    print(f"Total attempts: {total_attempts.value:,}")
    print(f"Max leading zeroes found: {max_leading.value}")
    print(f"Max trailing zeroes found: {max_trailing.value}")

if __name__ == '__main__':
    multiprocessing.freeze_support()  # Required for Windows
    main()