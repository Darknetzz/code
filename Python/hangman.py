from english_words import english_words_lower_alpha_set
import random, string, os

os.system('cls' if os.name == 'nt' else 'clear')

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

print(f"""
{bcolors.OKGREEN}
 _   _                                         
| | | |                                        
| |_| | __ _ _ __   __ _ _ __ ___   __ _ _ __  
|  _  |/ _` | '_ \ / _` | '_ ` _ \ / _` | '_ \ 
| | | | (_| | | | | (_| | | | | | | (_| | | | |
\_| |_/\__,_|_| |_|\__, |_| |_| |_|\__,_|_| |_|
                    __/ |                      
                   |___/                       
____________________________________________________
{bcolors.ENDC}
""")

dict = list(english_words_lower_alpha_set)

pref_len = input("Select length of word (blank for random): ")
try:
    pref_len = int(pref_len)
except ValueError:
    pref_len = 0


word_len = 0

if pref_len == 0:
    selected_word = random.choice(dict)
else:
    found = False
    print(f"Looking for word of length {pref_len} in dictionary...")
    for i in dict:
        word_len = len(i)
        if word_len == pref_len:
            selected_word = i
            found = True
    if found != True:
        print(f"No words of length {pref_len} in dictionary, picking random.")
        selected_word = random.choice(dict)
            

valid_chars = string.ascii_lowercase
guessed_chars = ""
lives = 10
all_guessed = False
status = "none"
word_len = len(selected_word)


while lives > 0 and all_guessed == False:
    os.system('cls' if os.name == 'nt' else 'clear')
    all_guessed = True # Just a placeholder, this gets overridden
    valid_chars_f = ""
    guessed_chars_f = ""

    # Format valid chars
    for c in valid_chars:
        if c in guessed_chars:
            if c in selected_word:
                valid_chars_f += f"{bcolors.OKGREEN}{c}{bcolors.ENDC}"
            else:
                valid_chars_f += f"{bcolors.FAIL}{c}{bcolors.ENDC}"

        else:
            valid_chars_f += c
    
    # Format guessed chars
    for c in guessed_chars:
        if c in selected_word:
            guessed_chars_f += f"{bcolors.OKGREEN}{c}{bcolors.ENDC}"
        else:
            guessed_chars_f += f"{bcolors.FAIL}{c}{bcolors.ENDC}"






    print(f"""
{bcolors.OKGREEN}
 _   _                                         
| | | |                                        
| |_| | __ _ _ __   __ _ _ __ ___   __ _ _ __  
|  _  |/ _` | '_ \ / _` | '_ ` _ \ / _` | '_ \ 
| | | | (_| | | | | (_| | | | | | | (_| | | | |
\_| |_/\__,_|_| |_|\__, |_| |_| |_|\__,_|_| |_|
                    __/ |                      
                   |___/                       
{bcolors.ENDC}
____________________________________________________

The word is {word_len} characters long, randomly picked from a dictionary with {len(dict)} words.

Valid characters: {valid_chars_f}
____________________________________________________
""")

    for i in range(word_len):
        if selected_word[i] in guessed_chars:
            print(f"{bcolors.OKGREEN}{selected_word[i]}{bcolors.ENDC}", end = " ")
        else:
            print(f"{bcolors.FAIL}_{bcolors.ENDC}", end = " ")
            all_guessed = False

    if all_guessed == True:
        break

    print(f"\n\nYou have guessed the following characters: {guessed_chars_f}")
    print(f"You have {lives} ❤️ left.\n\n\n\n")
    if status == "correct":
        print("Good job! You guessed correct.")
    elif status == "incorrect":
        print("No, that's not it.")
    elif status == "invalid":
        print("That character is not valid.")
    elif status == "alreadyguessed":
        print("You already guessed this character. Try again.")
    elif status == "help":
        # TODO: Would be nice to show only non guessed chars, not really sure how to implement atm
        randletter = selected_word[random.randint(0,len(selected_word)-1)]
        print(f"Maybe you should try the character {randletter}")
    guess = input("Guess a character: ")

    if guess == 'help' or guess == 'tips':
        status = "help"
    elif guess in valid_chars:
        if guess in guessed_chars:
            # print("You already guessed this character. Try again.")
            status = "alreadyguessed"
        else:
            guessed_chars += guess
            if guess in selected_word:
                # print(f"The character {guess} is in the word!")
                status = "correct"
            else:
                lives = lives-1
                # print(f"That character is unfortunately not in the word. {lives} lives left.")
                status = "incorrect"
    else:
        status = "invalid"

if all_guessed == True:
    print(f"Congratulations! You guessed the word {selected_word} with ease!")
else:
    print(f"You died. The word was {selected_word}, but I guess you were too stupid to figure that out.")