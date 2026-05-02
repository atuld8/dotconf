-- Cscope + Ctags integration

local ok, _ = pcall(require, "cscope_maps")
if not ok then
    return
end

-- Tags configuration
vim.opt.tags = { "./tags", "tags", "tags;/" }

local function add_cscope_if_found()
  local db = vim.fn.getcwd() .. "/cscope.out"
  if vim.fn.filereadable(db) == 1 then
    vim.cmd("silent! cscope kill -1")
    vim.cmd("silent! cscope add " .. vim.fn.fnameescape(db))
  end
end

local function F_ctag_cscope_add_wrt_git()
  local ok2, rootpath = pcall(function()
    return vim.fn.system("git rev-parse --show-toplevel 2>/dev/null"):gsub("\n$", "")
  end)

  if not ok2 or rootpath == "" or vim.v.shell_error ~= 0 then
    return
  end

  local cscope_out = rootpath .. "/cscope.out"
  local ctags_file = rootpath .. "/tags"

  if vim.fn.filereadable(cscope_out) == 1 then
    vim.cmd("silent! cscope add " .. vim.fn.fnameescape(cscope_out))
  end

  if vim.fn.filereadable(ctags_file) == 1 then
    vim.opt.tags:append(ctags_file)
  end
end

vim.api.nvim_create_autocmd({ "VimEnter", "DirChanged" }, {
  callback = function()
    add_cscope_if_found()
    F_ctag_cscope_add_wrt_git()
  end,
})

