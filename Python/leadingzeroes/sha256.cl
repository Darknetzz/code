// sha256.cl
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