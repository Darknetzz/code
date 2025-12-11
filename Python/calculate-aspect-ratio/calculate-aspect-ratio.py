import math
import sys

def calculate_aspect_ratio(width=None, height=None):
    """Calculate the aspect ratio (exact and marketing) for given width and height."""
    
    # --- 1. Handle Inputs ---
    if width is None:
        width = int(input("Enter width: "))
    if height is None:
        height = int(input("Enter height: "))
    
    # --- 2. Calculate Exact Ratio (Math) ---
    gcd_val = math.gcd(width, height)
    exact_w = width // gcd_val
    exact_h = height // gcd_val
    
    decimal_ratio = width / height

    # --- 3. Determine Marketing/Standard Ratio ---
    # Dictionary of common standards: (Width, Height) -> Label
    standards = {
        (16, 9): "16:9 (Widescreen)",
        (21, 9): "21:9 (Ultrawide)",       # 3440/1440 falls here
        (32, 9): "32:9 (Super Ultrawide)",
        (4, 3):  "4:3 (Legacy/iPad)",
        (16, 10):"16:10 (Productivity)",
        (5, 4):  "5:4",
        (1, 1):  "1:1 (Square)",
        (9, 16): "9:16 (Vertical)",
        (9, 21): "9:21 (Vertical Ultrawide)"
    }

    marketing_str = "Custom/Non-Standard"
    closest_diff = float('inf')

    # Find the closest match within a reasonable tolerance
    for (sw, sh), name in standards.items():
        standard_decimal = sw / sh
        diff = abs(decimal_ratio - standard_decimal)
        
        if diff < closest_diff:
            closest_diff = diff
            # If it's very close (tolerance 0.06 covers 3440 vs 21:9), use the label
            if diff < 0.06:
                marketing_str = name

    # --- 4. Output ---
    print(f"Resolution:      {width}x{height}")
    print(f"Exact Ratio:     {exact_w}:{exact_h}")
    print(f"Marketing Ratio: {marketing_str}")
    print(f"Decimal:         {decimal_ratio:.4f}")
    
    return exact_w, exact_h, decimal_ratio

if __name__ == "__main__":
    width, height = None, None
    
    if len(sys.argv) == 2:
        # Format: python script.py 1920x1080
        if 'x' in sys.argv[1].lower():
            parts = sys.argv[1].lower().split('x')
            if len(parts) == 2 and parts[0] and parts[1]:
                width, height = int(parts[0]), int(parts[1])
    elif len(sys.argv) == 3:
        # Format: python script.py 1920 1080
        width, height = int(sys.argv[1]), int(sys.argv[2])
    
    calculate_aspect_ratio(width, height)