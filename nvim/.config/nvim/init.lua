-- init.lua

-- Load lazy.nvim plugin manager
local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not vim.loop.fs_stat(lazypath) then
  vim.fn.system({
    "git", "clone", "--filter=blob:none",
    "https://github.com/folke/lazy.nvim.git",
    lazypath
  })
end
vim.opt.rtp:prepend(lazypath)

require("lazy").setup("plugins")

-- Basic Neovim settings
vim.opt.number = true
vim.opt.relativenumber = true
vim.opt.termguicolors = true
vim.cmd("filetype plugin indent on")
