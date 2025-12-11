import math
import sys

def calculate_aspect_ratio(width=None, height=None):
    """Calculate the aspect ratio for given width and height."""
    if width is None:
        width = int(input("Enter width: "))
    if height is None:
        height = int(input("Enter height: "))
    
    gcd_val = math.gcd(width, height)
    ratio_w = width // gcd_val
    ratio_h = height // gcd_val
    
    decimal_ratio = width / height
    
    print(f"{ratio_w}:{ratio_h}")
    print(f"{decimal_ratio}")
    
    return ratio_w, ratio_h, decimal_ratio

if __name__ == "__main__":
    width, height = None, None
    
    if len(sys.argv) == 2:
        # Format: python script.py 1920x1080
        if 'x' in sys.argv[1] or 'X' in sys.argv[1]:
            parts = sys.argv[1].replace('X', 'x').split('x')
            width, height = int(parts[0]), int(parts[1])
    elif len(sys.argv) == 3:
        # Format: python script.py 1920 1080
        width, height = int(sys.argv[1]), int(sys.argv[2])
    
    calculate_aspect_ratio(width, height)