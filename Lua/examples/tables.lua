-- tables.lua
-- Tables as arrays and dictionaries
local arr = {10, 20, 30}
for i, v in ipairs(arr) do
  print("arr[" .. i .. "] =", v)
end

local person = { name = "Alice", age = 30 }
print("Name:", person.name)
print("Age:", person["age"]) 

-- mixing numeric and keyed entries
local mix = { "a", key = "value", 123 }
for k, v in pairs(mix) do
  print(k, v)
end
