# ---------------------------------------------------------------------------- #
#                               Short decription                               #
# ---------------------------------------------------------------------------- #
# This script is meant to generate a rainbowtable of sorts. It takes all       #
# combinations of n characters and hashes them. It will then insert into a DB  #
# ---------------------------------------------------------------------------- #


import string, mysql.connector, string, itertools, hashlib, sys

def hashStr(type, str):
    m = eval(f"hashlib.{type}()")
    m.update(str.encode())
    hex = m.hexdigest()
    return hex

defaultLength = int(sys.argv[1]) or 4
chars = string.ascii_lowercase

print("Please enter your database details")
host=input("Host: ")
user=input("Username: ")
password = input("Password: ")
database=input("Database: ")


cnx = mysql.connector.connect(user=user, password=password,
                              host=host, database=database)

cursor = cnx.cursor()

# keywords = [''.join(i) for i in itertools.product(chars, repeat = 4)]

combinations = list(itertools.product(chars, repeat=defaultLength))
combinationsCount = sum(1 for _ in combinations)

c = 0

for i in combinations:
    # Join array of chars into string
    cleartext = ''.join(i)
    # Hash the generated string
    hashtext  = hashStr('md5', cleartext)
    # Add the hash and cleartext to database
    addHash   = f"""INSERT INTO md5 (hash, cleartext) VALUES (%s, %s)"""
    data      = (hashtext, cleartext)

    cursor.execute(addHash, data)
    c += 1
    if c % 100 == 0:
        percentage = round((c / combinationsCount) * 100, 1)
        print(f"[{percentage}%] Iteration {c}: {hashtext} = {cleartext}")

cnx.commit()
cursor.close()
cnx.close()