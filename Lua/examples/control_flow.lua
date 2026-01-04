-- control_flow.lua
-- if, for, while examples
local n = 5
if n > 3 then
  print("n is greater than 3")
else
  print("n is 3 or less")
end

for i = 1, 5 do
  print("for loop", i)
end

local i = 0
while i < 3 do
  print("while loop", i)
  i = i + 1
end
