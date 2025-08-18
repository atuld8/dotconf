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

local cscope_maps = require("cscope_maps")

-- Function to add cscope and ctags (relative to current script path)
local function F_ctag_cscope_add()
  local path = vim.fn.fnamemodify(vim.fn.resolve(vim.fn.expand("<sfile>:p")), ":h")
  local srcpath = string.gsub(path, "/src/.*$", "/src/")
  local cscope_out = string.gsub(srcpath, "/src/.*$", "/src/cscope.out")
  local ctags_file = string.gsub(srcpath, "/src/.*$", "/src/vtags")

  if vim.fn.filereadable(cscope_out) == 1 then
    cscope_maps.cscope.add(cscope_out)  -- ✅ instead of :cscope add
  end

  if vim.fn.filereadable(ctags_file) == 1 then
    vim.opt.tags:append(ctags_file)
  end
end

-- Function to add cscope/ctags relative to git root
local function F_ctag_cscope_add_wrt_git()
  local rootpath = vim.fn.system("git rev-parse --show-toplevel"):gsub("\n$", "")
  local cscope_out = rootpath .. "/cscope.out"
  local ctags_file = rootpath .. "/tags"

  if vim.fn.filereadable(cscope_out) == 1 then
    cscope_maps.cscope.add(cscope_out)
  end

  if vim.fn.filereadable(ctags_file) == 1 then
    vim.opt.tags:append(ctags_file)
  end
end

-- Run them at startup
F_ctag_cscope_add()
F_ctag_cscope_add_wrt_git()

