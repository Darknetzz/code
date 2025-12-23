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
counter_lock = Lock()
start_time: float = 0.0

def worker(worker_id, target_zeroes):
    """Worker function that generates random strings and checks for zeroes"""
    local_attempts = 0
    local_max_leading = 0
    local_max_trailing = 0
    
    while True:
        # Generate random string
        rand_str = ''.join(random.choices(string.ascii_letters + string.digits, k=64))
        
        # Hash it
        hash_obj = hashlib.sha256(rand_str.encode())
        hash_hex = hash_obj.hexdigest()
        
        # Count leading zeroes
        leading = len(hash_hex) - len(hash_hex.lstrip('0'))
        
        # Count trailing zeroes
        trailing = len(hash_hex) - len(hash_hex.rstrip('0'))
        
        local_attempts += 1
        
        # Check if we found new records
        if leading > local_max_leading:
            local_max_leading = leading
            elapsed = time.time() - start_time
            with counter_lock:
                if leading > max_leading.value:
                    max_leading.value = leading
                    print(f"[{elapsed:.2f}s] Worker {worker_id}: Found {leading} LEADING zeroes!")
                    print(f"  String: {rand_str}")
                    print(f"  Hash:   {hash_hex}")
                    print(f"  Total attempts: {total_attempts.value:,}\n")
                    
                    if leading >= target_zeroes:
                        return
        
        if trailing > local_max_trailing:
            local_max_trailing = trailing
            elapsed = time.time() - start_time
            with counter_lock:
                if trailing > max_trailing.value:
                    max_trailing.value = trailing
                    print(f"[{elapsed:.2f}s] Worker {worker_id}: Found {trailing} TRAILING zeroes!")
                    print(f"  String: {rand_str}")
                    print(f"  Hash:   {hash_hex}")
                    print(f"  Total attempts: {total_attempts.value:,}\n")
                    
                    if trailing >= target_zeroes:
                        return
        
        # Update global counter periodically
        if local_attempts % 100000 == 0:
            with counter_lock:
                total_attempts.value += local_attempts
                local_attempts = 0
                
                # Print progress every 100M attempts
                if total_attempts.value % 100000000 < 100000:
                    elapsed = time.time() - start_time
                    rate = total_attempts.value / elapsed
                    print(f"[{elapsed:.2f}s] Progress: {total_attempts.value:,} attempts ({rate:,.0f} hashes/sec)")

def main():
    global start_time
    
    target = 9  # Target number of zeroes
    num_workers = multiprocessing.cpu_count()
    
    print(f"Starting hash search with {num_workers} parallel workers")
    print(f"Target: {target} leading or trailing zeroes")
    print(f"Expected attempts: ~{16**target:,} (probability: 1 in {16**target:,})")
    print("=" * 70 + "\n")
    
    start_time = time.time()
    
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