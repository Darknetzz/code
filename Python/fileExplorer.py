import tkinter as tk
import os, pathlib, string

# Window initialize
window   = tk.Tk()
# window.resizable(False, False)
window.title("File explorer")
window.geometry('700x500')

# Config
currentFolder = os.getcwd()
lastFolder    = os.getcwd() # will change when changecwd is called

# ---------------------------------------------------------------------------- #
#                                   Functions                                  #
# ---------------------------------------------------------------------------- #
def get_drives():
    drives = []
    for drive in string.ascii_uppercase:
        if os.path.exists(f"{drive}:"):
            drives.append(drive + ":\\")
    return drives

def getFiles(folder):
    fileList = os.listdir(currentFolder)
    fileList.sort(key=lambda f: os.path.isfile(f))
    return fileList

def changecwd(folder):
    global currentFolder
    global fileList
    global fileListBox
    lastFolder = os.getcwd()
    os.chdir(folder)
    currentFolder = os.getcwd()

    header.config(text=currentFolder)
    fileList = getFiles(currentFolder)
    
    fileListBox.delete(0, tk.END)
    fileListBox.insert(tk.END, f"📂 ..")

    for file in fileList:
        if os.path.isdir(file):
            fileListBox.insert(tk.END, f"📂 {file}")
        elif os.path.isfile(file):
            fileListBox.insert(tk.END, f"📄 {file}")

def clickedFile():
    global currentFolder
    global fileListBox
    global fileList

    folder = fileListBox.curselection()
    folder = fileListBox.get(folder)[2:len(fileListBox.get(folder))]
    if os.path.isdir(folder):
        changecwd(folder)
    else:
        print(f"Opening {folder}")

def clickedFolderofInterest():
    folder = foldersOfInterestBox.curselection()
    folder = foldersOfInterestBox.get(folder)[2:len(foldersOfInterestBox.get(folder))]

    if os.path.isdir(folder):
        changecwd(folder)

# # ---------------------------------------------------------------------------- #
# #                               Frames/Containers                              #
# # ---------------------------------------------------------------------------- #
topFrame = tk.Frame(window)
topFrame.pack(side=tk.TOP)
leftFrame = tk.Frame(window)
leftFrame.pack(expand = True, fill = tk.BOTH, side=tk.LEFT)
rightFrame = tk.Frame(window)
rightFrame.pack(expand=True, fill=tk.BOTH, side=tk.LEFT)

header = tk.Label(text = currentFolder)
search = tk.Entry(window)
search.insert(0, "Search")
previousfolder = tk.Button(window, text="Back", command=lambda: changecwd(lastFolder))

# # ---------------------------------------------------------------------------- #
# #                                    Widgets                                   #
# # ---------------------------------------------------------------------------- #

# ---------------------------------- Stuff ---------------------------------- #
header.pack(in_=topFrame)
search.pack(in_=topFrame)
previousfolder.pack(in_=topFrame)

# ---------------------------- Folders of interest --------------------------- #
foldersOfInterestBox = tk.Listbox(leftFrame)
foldersOfInterest = get_drives()

for folder in foldersOfInterest:
    os.path.normpath(folder)
    foldersOfInterestBox.insert(tk.END, f"📂 {folder}")

foldersOfInterestBox.place(relheight=1, relwidth=1, relx=0.5, rely=0.5,anchor=tk.CENTER)
foldersOfInterestBox.bind("<<ListboxSelect>>", lambda event: clickedFolderofInterest())

# --------------------------------- File list -------------------------------- #
fileList = getFiles(currentFolder)

fileListBox = tk.Listbox(rightFrame)

fileListBox.insert(tk.END, f"📂 ..")
for file in fileList:
    if os.path.isdir(file):
        fileListBox.insert(tk.END, f"📂 {file}")
    elif os.path.isfile(file):
        fileListBox.insert(tk.END, f"📄 {file}")
fileListBox.place(relheight=1, relwidth=1, relx=0.5, rely=0.5,anchor=tk.CENTER)
fileListBox.bind("<<ListboxSelect>>", lambda event: clickedFile())


window.mainloop()