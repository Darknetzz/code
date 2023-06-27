import random
import string
from time import sleep


winningChance = 50
enableBlackJack = False
timeBetweenBets = 0

startingMoney = 1_000_000_000
startingBet = 1_000_000

currentMoney = startingMoney
currentBet = startingBet

highestMoney = startingMoney
highestBet = startingBet

wins = 0
loss = 0

wstreak = 0
lstreak = 0

lastBetLost = 0
lastBetWon = 0

while (currentMoney >= currentBet):
    # Place the bet
    currentMoney = currentMoney - currentBet
    print("Betting $"+str(currentBet))

    # Update highestBet if higher
    if (currentBet > highestBet):
        highestBet = currentBet

    # No need to do complex stuff here, just take chance of winning and roll a dice
    roll = random.randint(0,100)
    if (roll <= winningChance):
        # You win 😊
        print("You win $"+str(currentBet*2)+"! 😁 You now have $"+str(currentMoney)+".")
        wins += 1
        if (lastBetWon == 1):
            wstreak += 1
            lstreak = 0
        lastBetWon = 1
        lastBetLost = 0
        currentMoney = currentMoney + currentBet*2
        if (currentMoney > highestMoney):
            highestMoney = currentMoney # Update highest amount of money
        # Reset bet
        currentBet = startingBet
    else:
        # You lost 😞
        print("Bet lost! 😞 You now have $"+str(currentMoney)+" remaining.")
        loss += 1
        if (lastBetLost == 1):
            lstreak += 1
            wstreak = 0
        lastBetLost = 1
        lastBetWon = 0
        # Double up for next bet
        currentBet = currentBet*2
    sleep(timeBetweenBets)

print("-----------------\n")
print("You lost too much money to continue you absolute gambler!\n")
print("Starting Money: $"+str("{:,}".format(startingMoney)))
print("Remaining money: $"+str("{:,}".format(currentMoney)+"\n"))
print("Highest bet: $"+str("{:,}".format(highestBet)))
print("Highest money: $"+str("{:,}".format(highestMoney)+"\n"))
print(f"Win streak: {wstreak} | Loss streak: {lstreak}")
print(str("{:,}".format(wins))+" wins | "+str("{:,}".format(loss)+" losses."))