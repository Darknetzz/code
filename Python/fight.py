from contextlib import nullcontext
import random
import time

class Fighter:
    strength = 1 # can be anything really
    health = 100 # this too
    critChance = 20 # a value from 0 - 100 (should be higher than critChance)
    sCritChance = 1 # a value from 0 - 100 (should be lower than critChance)
    blockChance = 10

player1 = Fighter()
player1.health = 100
player1.strength = 10
player1.critChance = 10
player1.sCritChance = 1
player1.blockChance = 10


player2 = Fighter()
player2.health = 100
player2.strength = 10
player2.critChance = 10
player2.sCritChance = 1
player2.blockChance = 10

turn = random.randint(1,2)

# Attack function
def attack(attackerObject):
    damage = random.randint(1,attackerObject.strength)
    crit = random.randint(0,100)
    block = random.randint(0,100)
    attack.block = False
    attack.crit = False
    if (block <= attackerObject.blockChance):
        damage = 0
        attack.block = True
        return 0
    elif (crit <= attackerObject.sCritChance):
        attack.crit = True
        damage = damage+damage+damage
    elif (crit <= attackerObject.critChance):
        attack.crit = True
        damage = damage+damage
    else:
        attack.crit = False
    damage
    return round(damage)

def currentHealth(player1, player2):
    print("Player 1: "+str(player1)+"%"+" | Player 2: "+str(player2)+"%")

while (player1.health > 0 and player2.health > 0):
    # Fighter 1 attacks fighter 2
    if (turn == 1):
        damage = attack(player1)
        crit = attack.crit
        block = attack.block
        if (block == True):
            block = "ATTACK BLOCKED!"
        else:
            block = ""
        if (crit == True):
            crit = "CRITICAL HIT!"
        else:
            crit = ""
        print("Player 1 ⚔️ player 2 for "+str(damage)+" 🎯. "+str(crit)+str(block))
        player2.health -= damage
        turn = 0
    # Fighter 2 attacks fighter 1
    else:
        damage = attack(player2)
        crit = attack.crit
        block = attack.block
        if (block == True):
            block = "ATTACK BLOCKED!"
        else:
            block = ""
        if (crit == True):
            crit = "CRITICAL HIT!"
        else:
            crit = ""
        print("Player 2 ⚔️ player 1 for "+str(damage)+" 🎯. "+str(crit)+str(block))
        player1.health -= damage
        turn = 1
    currentHealth(player1.health, player2.health)
    time.sleep(1)
if (player1.health > player2.health):
    print("Player 1 wins the fight with "+str(player1.health)+" hp!")
else:
    print("Player 2 wins the fight with "+str(player2.health)+" hp!")