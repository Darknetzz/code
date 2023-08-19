<!-- ─────────────────────────────────────────────────────────────────────── -->
<!--                                 README                                  -->
<!-- ─────────────────────────────────────────────────────────────────────── -->

***DISCLAIMER***
This code is probably not well written or secure in any way.
I use some of this code personally in my projects.

<!-- ─────────────────────────────────────────────────────────────────────── -->

## USAGE EXAMPLES

<!-- ─────────────────────────────────────────────────────────────────────── -->

### GENERAL

```
import utils as UTILS

importer = UTILS.importer
crypto   = UTILS.crypto.darkCrypt()
rand     = UTILS.rand
style    = UTILS.textStyle

importer     = importer.importer_import_new('git', 'gitpython')
encryptPass  = crypto.secret_encrypt('secret', 'password')
randomString = rand.genStr()
coolText     = style.style('This text will look super cool, I promise!', 'primary')
```

<!-- ─────────────────────────────────────────────────────────────────────── -->

### CRYPTO
`import utils as UTILS
crypto = UTILS.crypto.darkCrypt()`

`secret = crypto.secret_decrypt(cfg["secretFile"], cfg["keyFile"])`

OR

`secret = crypto.secret_decrypt('encryptedSecret', cfg["keyFile"])`

OR

`secret = crypto.secret_decrypt('encryptedSecret', 'unencryptedKey')` # <-- This method is UNSAFE, obviously

<!-- ─────────────────────────────────────────────────────────────────────── -->

### IMPORTER

USAGE: Define a variable and call this function with package you want to install


EXAMPLE: `ff = importer_import_new('ffmpeg')`

IS EQUAL TO: `import ffmpeg as ff`


EXAMPLE: `importer.importer_import_new('git', 'gitpython')`

IS EQUAL TO: `import git` (and pip install the required gitpython if it isn't installed)


Or you can add it to the global scope, for example in a for loop:

`import utils.importer as imp
packages = ["os", "time", "random"]
for p in packages:
    globals()[p] = imp.importer_import(p):
tk = imp.importer_import("tkinter")`

<!-- ─────────────────────────────────────────────────────────────────────── -->
