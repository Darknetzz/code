net use * /delete /yes;

net use z: "\\10.0.1.23\Share" /persistent:yes /yes; # nas3
net use y: "\\10.0.2.56\data" /persistent:yes /yes;  # ubuntu02

net use;
pause;