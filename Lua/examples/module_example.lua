-- module_example.lua
-- A tiny module that can be required
local M = {}

function M.greet(name)
  print("Hello, " .. (name or "there") .. "!")
end

return M
