import random

# 1. The Utilities to "Undo" the Tempering
# ----------------------------------------
def undo_right_shift_xor(value, shift):
    """Reverses the operation: y = x ^ (x >> shift)"""
    result = value
    for _ in range(32 // shift):
        result = value ^ (result >> shift)
    return result

def undo_left_shift_xor_and(value, shift, mask):
    """Reverses the operation: y = x ^ ((x << shift) & mask)"""
    result = value
    for _ in range(32 // shift):
        result = value ^ ((result << shift) & mask)
    return result

def untemper(y):
    """
    Reverses the standard MT19937 tempering steps to get the raw state value.
    The constants (18, 15, 7, 11) and masks are standard for MT19937.
    """
    # Step 4: y = y ^ (y >> 18)
    y = undo_right_shift_xor(y, 18)

    # Step 3: y = y ^ ((y << 15) & 0xefc60000)
    y = undo_left_shift_xor_and(y, 15, 0xefc60000)

    # Step 2: y = y ^ ((y << 7) & 0x9d2c5680)
    y = undo_left_shift_xor_and(y, 7, 0x9d2c5680)

    # Step 1: y = y ^ (y >> 11)
    y = undo_right_shift_xor(y, 11)
    
    return y

# 2. The Attack
# ----------------------------------------
print("Collecting 624 outputs from the target...")

# The "Target" (Simulating a server giving out tokens)
target_rng = random.Random()
# We don't know the seed, we just see the outputs
observed_outputs = [target_rng.getrandbits(32) for _ in range(624)]

print("Recovering internal state...")
# Recover the internal state by untempering the outputs
recovered_state = [untemper(out) for out in observed_outputs]

# We also need the index. After 624 outputs, the index wraps to 624 (which triggers a twist)
# Python's state tuple format is (3, (state_array + [index]), None)
# The '3' indicates the version of the algorithm.
state_tuple = (3, tuple(recovered_state + [624]), None)

# Create our "Cracker" RNG and force the recovered state into it
cracker_rng = random.Random()
cracker_rng.setstate(state_tuple)

# 3. The Verification
# ----------------------------------------
print("\n--- PREDICTION TIME ---")
target_next = target_rng.getrandbits(32)
cracker_next = cracker_rng.getrandbits(32)

print(f"Target's next number:  {target_next}")
print(f"Cracker's prediction:  {cracker_next}")

if target_next == cracker_next:
    print("\n[SUCCESS] The RNG is fully cloned. We can predict all future values.")
else:
    print("\n[FAIL] Prediction failed.")