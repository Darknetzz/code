-- io_and_file.lua
-- Basic file I/O: write then read a file in the current working directory
local fname = "example_output.txt"
local f = io.open(fname, "w")
if f then
  f:write("Line 1\nLine 2\n")
  f:close()
  print("Wrote to", fname)
else
  print("Failed to open file for writing")
end

local fr = io.open(fname, "r")
if fr then
  local content = fr:read("*a")
  fr:close()
  print("File content:\n" .. content)
else
  print("Failed to open file for reading")
end
