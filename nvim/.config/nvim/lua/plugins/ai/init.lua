-- Auto-forward all AI plugin specs
local specs = {}
for _, mod in ipairs({ "plugins.ai.copilot", "plugins.ai.copilot-cmp" }) do
  local ok, spec = pcall(require, mod)
  if ok then
    vim.list_extend(specs, spec)
  end
end
return specs
