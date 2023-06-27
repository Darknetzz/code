import sys
import random
from english_words import english_words_set
from time import sleep
from essential_generators import DocumentGenerator

def typeWriter(words):
    for char in words:
        sleep(random.uniform(0,0.2))
        print(char, end='', flush=True)

def typeWriter_RandomSentence():
    # import documentgenerator
    main = DocumentGenerator().paragraph()
    for char in main:
        sleep(random.uniform(0,0.2))
        print(char, end='', flush=True)
    print(" ")

#typeWriter("Wake up, Neo...\n")
#sleep(2)
#typeWriter("Follow the white rabbit\n\n")

while True:
    # typeWriter(random.choice(list(english_words_set))+" ")
    typeWriter_RandomSentence()