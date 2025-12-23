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
    # Initialize the input string with the random starting string
    input_string = rand_str
    hash_obj = hashlib.sha256(input_string.encode())
    hash_hex = hash_obj.hexdigest()
    
    print(f"Worker {worker_id + 1} starting with: {hash_hex}")
    
    while True:
        # Instead of replacing, accumulate: append the hash to the input string
        # This creates a growing input string that gets hashed each iteration
        input_string += hash_hex
        hash_obj = hashlib.sha256(input_string.encode())
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
                    print(f"  Hash length: {len(hash_hex)} characters")
                    print(f"  Input length: {len(input_string)} characters")
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
                    print(f"  Hash length: {len(hash_hex)} characters")
                    print(f"  Input length: {len(input_string)} characters")
                    print(f"  Worker iteration: {worker_total_iterations:,}")
                    print(f"  Global total attempts: {current_total:,}\n")
                    
                    if trailing >= target_zeroes:
                        return
        
        # Update global counter periodically (every 100k iterations)
        if local_attempts % 100000 == 0:
            with counter_lock:
                # Update the global counter with this worker's contributions
                total_attempts.value += local_attempts
                
                # Only print progress at 100M milestones (100M, 200M, 300M, etc.)
                # Check if we've crossed a 100M boundary
                current_total = total_attempts.value
                current_milestone = current_total // 100000000
                
                # Only print if:
                # 1. We've reached a new milestone (current_milestone > last printed)
                # 2. We're actually at or past the milestone threshold (current_total >= milestone * 100M)
                # 3. The milestone is at least 1 (don't print at 100k, only at 100M+)
                if (current_milestone > last_progress_milestone.value and 
                    current_milestone >= 1 and 
                    current_total >= (current_milestone * 100000000)):
                    # Update the milestone counter FIRST to prevent other workers from printing
                    last_progress_milestone.value = current_milestone
                    
                    # Calculate elapsed time and rate
                    current_time = time.time()
                    elapsed = current_time - start_time.value
                    
                    # Only print if we have valid timing data
                    if elapsed > 0.001 and start_time.value > 0:
                        rate = current_total / elapsed
                        # Format rate appropriately
                        if rate >= 1000:
                            print(f"[{elapsed:.2f}s] Progress: {current_total:,} attempts ({rate:,.0f} hashes/sec)")
                        else:
                            print(f"[{elapsed:.2f}s] Progress: {current_total:,} attempts ({rate:,.2f} hashes/sec)")
                
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
    
    elapsed = time.time() - start_time.value
    print(f"\nSearch completed in {elapsed:.2f} seconds")
    print(f"Total attempts: {total_attempts.value:,}")
    print(f"Max leading zeroes found: {max_leading.value}")
    print(f"Max trailing zeroes found: {max_trailing.value}")

if __name__ == '__main__':
    multiprocessing.freeze_support()  # Required for Windows
    main()