-- functions.lua
-- Defining functions, return values, and varargs
local function add(x, y)
  return x + y
end
print("add(2,3)", add(2,3))

local function varargs(...)
  local t = { ... }
  for i, v in ipairs(t) do
    print(i, v)
  end
end
varargs("one", "two", "three")
