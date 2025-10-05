import random
import string
from time import sleep
from rich.console import Console

con = Console()

def cprint(text, style="bold white"):
    con.print(text, style=style)

# ──────────────────────────────────────────────────────────────────────────── #
#                                   Defaults                                   #
# ──────────────────────────────────────────────────────────────────────────── #
winningChance   = 49.5
timeBetweenBets = 0.1
startingMoney   = 1000
startingBet     = 10
currentMoney    = startingMoney
currentBet      = startingBet
highestMoney    = startingMoney
highestBet      = startingBet
wins            = 0
loss            = 0
wstreak         = 0
lstreak         = 0
cwlstreak       = 0
# lastBetLost     = 0
# lastBetWon      = 0

defaults = input("Use default settings? (Y/n): ")
if (defaults.lower() == "n"):
        currentMoney    = startingMoney = input(f"Enter starting money (default ${startingMoney}): $")
        currentBet      = startingBet   = input(f"Enter starting bet (default ${startingBet}): $")
        winningChance   = input(f"Enter winning chance in percent (default {winningChance}%): ")
        timeBetweenBets = input(f"Enter seconds between each bet (default {timeBetweenBets}): ")

# Convert inputs to appropriate types
try:
    currentMoney = startingMoney = float(startingMoney)
except ValueError:
    currentMoney = startingMoney = 1000
try:
    currentBet = startingBet = float(startingBet)
except ValueError:
    currentBet = startingBet = 10
try:
    winningChance = float(winningChance)
except ValueError:
    winningChance = 49.5
try:
    timeBetweenBets = float(timeBetweenBets)
except ValueError:
    timeBetweenBets = 0.1


while (currentMoney >= currentBet):
    # Place the bet
    currentMoney = currentMoney - currentBet
    # cprint("Betting $"+str(currentBet))

    # Update highestBet if higher
    if (currentBet > highestBet):
        highestBet = currentBet

    # No need to do complex stuff here, just take chance of winning and roll a dice
    roll = random.randint(0,100)
    if (roll <= winningChance):
        # You win 😊
        cprint("You win $"+str(currentBet*2)+"! 😁 You now have $"+str(currentMoney)+".", "bold green")
        wins    += 1
        wstreak += 1
        lstreak = 0
        # if (lastBetWon == 1):
        #     wstreak += 1
        #     lstreak = 0
        # lastBetWon = 1
        # lastBetLost = 0
        currentMoney = currentMoney + currentBet*2
        if (currentMoney > highestMoney):
            highestMoney = currentMoney # Update highest amount of money
        # Reset bet
        currentBet = startingBet
    else:
        # You lost 😞
        cprint("Bet lost! 😞 You now have $"+str(currentMoney)+" remaining.", "bold red")
        loss    += 1
        lstreak += 1
        wstreak = 0
        # if (lastBetLost == 1):
        #     lstreak += 1
        #     wstreak = 0
        # lastBetLost = 1
        # lastBetWon = 0
        # Double up for next bet
        currentBet = currentBet*2
    sleep(timeBetweenBets)

cprint("-----------------\n")
cprint("You lost too much money to continue you absolute gambler!\n")
cprint("Starting Money: $"+str("{:,}".format(startingMoney)))
cprint("Remaining money: $"+str("{:,}".format(currentMoney)+"\n"))
cprint("Highest bet: $"+str("{:,}".format(highestBet)))
cprint("Highest money: $"+str("{:,}".format(highestMoney)+"\n"))
cprint(f"Win streak: {wstreak} | Loss streak: {lstreak}")
cprint(str("{:,}".format(wins))+" wins | "+str("{:,}".format(loss)+" losses."))