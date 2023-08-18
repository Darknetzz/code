import sys, pygame, random
pygame.init()

size = width, height = 1200, 960
speed = [1, 1]
black = 0, 0, 0

screen = pygame.display.set_mode(size)
background = pygame.Surface(size)

ball = pygame.draw.circle(background, "pink", [10,10], 10)
ballrect = ball

def rerollColor():
    x = random.randint(0,255)
    y = random.randint(0,255)
    z = random.randint(0,255)
    ball = pygame.draw.circle(background, [x,y,z], [10,10], 10)


while 1:
    for event in pygame.event.get():
        if event.type == pygame.QUIT: sys.exit()
        if event.type == pygame.KEYDOWN: speed = [random.randint(1,5), random.randint(1,5)]

    ballrect = ballrect.move(speed)
    if ballrect.left < 0 or ballrect.right > width:
        speed[0] = -speed[0]
        rerollColor()
    if ballrect.top < 0 or ballrect.bottom > height:
        speed[1] = -speed[1]
        rerollColor()

    screen.fill(black)
    screen.blit(background, ballrect)
    pygame.display.flip()