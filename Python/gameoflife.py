# This is the game of life!

# Rules:
# Any live cell with fewer than two live neighbours dies, as if by underpopulation.
# Any live cell with two or three live neighbours lives on to the next generation.
# Any live cell with more than three live neighbours dies, as if by overpopulation.
# Any dead cell with exactly three live neighbours becomes a live cell, as if by reproduction.

def main():

    # ---------------------------------------------------------------------------- #
    #                                    Imports                                   #
    # ---------------------------------------------------------------------------- #
    import random, time, os

    aliveChance = int(input("chance (%) of any given cell being populated when generating board [default 10]: ") or 10)
    dead = str(input("Character for dead cells [default .]: ") or ".")
    alive = str(input("Character for live cells [default 0]: ") or "0")
    sleepTime = int(input("Time (ms) between each \"frame\" [default 300]: ") or 300)


    # ---------------------------------------------------------------------------- #
    #                                  Board setup                                 #
    # ---------------------------------------------------------------------------- #
    x, y = 75, 75
    board = []
    board.append([])

    # ---------------------------------------------------------------------------- #
    #                                   Functions                                  #
    # ---------------------------------------------------------------------------- #
    def doNothing():
        nothing = True

    def getLiveNeighbors(board,x,y):
        neighbors = 0
        coordinatesToCheck = [
            [x-1, y], # left
            [x+1, y], # right
            [x, y+1], # down
            [x, y-1], # up
            [x-1, y-1], # up left
            [x+1, y-1], # up right
            [x-1, y+1], # down left
            [x+1, y+1], # down right
        ]
        
        for coordinates in coordinatesToCheck:
            if 0 <= coordinates[0] < len(board) and 0 <= coordinates[1] < len(board[coordinates[0]]):
                if board[coordinates[0]][coordinates[1]] == alive:
                    neighbors += 1

        return neighbors
        

    # ---------------------------------------------------------------------------- #
    #                                 Create board                                 #
    # ---------------------------------------------------------------------------- #
    print(f"Generating {x}x{y} board")
    for row in range(0, x):
        print(f"Creating row: board[{row}]")
        board.append([])

        for col in range(0, y):
            cell = random.randint(0,100)
            if cell <= aliveChance:
                cell = alive
            else:
                cell = dead
            board[row].append(cell)
            # print(f"Creating col: board[{row}][{col}]: {board[row][col]}")

    # ---------------------------------------------------------------------------- #
    #                            Start the actual stuff                            #
    # ---------------------------------------------------------------------------- #
    while True:
        for row, rval in enumerate(board):
            for col, cval in enumerate(rval):
                neighbors = getLiveNeighbors(board,row,col)
                if board[row][col] == alive and neighbors < 2:
                    board[row][col] = dead
                    #print("Less than 2 neighbors")
                elif board[row][col] == alive and neighbors == 2 or neighbors == 3:
                    board[row][col] = alive
                    #print("Exactly 2 or 3 neighbors")
                elif board[row][col] == alive and neighbors > 3:
                    board[row][col] = dead
                    #print("More than 3 neighbors")
                elif board[row][col] == dead and neighbors == 3:
                    board[row][col] = alive
                    #print("Dead with 3 neighbors")

            print(''.join(board[row]))
        time.sleep(sleepTime/1000)
        os.system('cls')

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Exited.")