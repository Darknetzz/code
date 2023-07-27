import string, random

def genStr(
        length: int = 24, 
        charset: string = string.ascii_letters+string.digits
        ) -> str:
    """Generate a string. Usage: genStr(length = 36, charset = "charACTERS123")"""
    str = ""
    for i in range(0, length):
        str += charset[random.randint(0, len(charset)-1)]
    return str

def pick_random(input: any) -> any:
    """Given an input of (almost) any type, pick one random element"""
    return input[random.randint(0,len(input)-1)]

def roll_percentage(percentage: int) -> bool:
    """Returns true if roll < percentage - else false"""
    return random.randint(0,100) <= percentage