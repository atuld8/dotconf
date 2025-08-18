-- Cscope + Ctags integration

local ok, cscope_maps = pcall(require, "cscope_maps")
if not ok then
    return
end

require("cscope_maps").setup({
    disable_maps = false, -- keep default keymaps
    skip_input_prompt = true, -- auto-use cscope.out if found
})


vim.opt.tags = { "./tags", "tags", "tags;/" }
vim.opt.cscopetag = true
vim.opt.csto = 1
vim.opt.cscopeverbose = true
vim.opt.cscopequickfix = "s+,c+,d+,i+,t+,e+,f+,g+"

local function add_cscope_if_found()
  local db = vim.fn.getcwd() .. "/cscope.out"
  if vim.fn.filereadable(db) == 1 then
    vim.cmd("silent! cscope kill -1")
    vim.cmd("silent! cscope add " .. vim.fn.fnameescape(db))
  end
end

vim.api.nvim_create_autocmd({ "VimEnter", "DirChanged" }, {
  callback = add_cscope_if_found,
})

