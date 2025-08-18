-- init.lua
vim.g.python3_host_prog="/opt/homebrew/bin/python3.12"

-- Load lazy.nvim plugin manager
local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not vim.loop.fs_stat(lazypath) then
  vim.fn.system({
    "git", "clone", "--filter=blob:none",
    "https://github.com/folke/lazy.nvim.git",
    "--branch=stable", lazypath
  })
end
vim.opt.rtp:prepend(lazypath)

require("lazy").setup("plugins")
require("lazy").setup("myconfig.plugins")

-- Load basic configs
require("myconfig.options")
require("myconfig.keymaps")

-- Load plugins (using lazy.nvim)
require("myconfig.plugins")

-- Load extras
require("myconfig.lsp")
require("myconfig.cscope")

-- Basic Neovim settings
vim.opt.number = true
vim.opt.relativenumber = true
vim.opt.termguicolors = true
vim.cmd("filetype plugin indent on")

-- Encoding
vim.opt.encoding = "utf-8"

-- Filetype handling
vim.cmd("filetype plugin on")
vim.cmd("filetype indent on")

-- Line numbers
vim.opt.number = true
vim.opt.relativenumber = true


-- Enable relativenumber for normal buffers, except NERDTree
local function set_numbers()
    local bufname = vim.api.nvim_buf_get_name(0) or ""
    if not bufname:match("NERD_tree") then
        vim.opt_local.number = true
        vim.opt_local.relativenumber = true
    end
end

local function unset_numbers()
    local bufname = vim.api.nvim_buf_get_name(0) or ""
    if not bufname:match("NERD_tree") then
        vim.opt_local.number = true
        vim.opt_local.relativenumber = false
    end
end

-- Run when entering window/focus
vim.api.nvim_create_autocmd({ "WinEnter", "FocusGained", "BufReadPost", "VimEnter" }, {
    pattern = "*",
    callback = set_numbers,
})

-- Run when leaving window/focus
vim.api.nvim_create_autocmd({ "WinLeave", "FocusLost" }, {
    pattern = "*",
    callback = unset_numbers,
})

-- NERDTree config
vim.g.NERDTreeShowLineNumbers = 0

-- Tabs & indentation
vim.opt.tabstop = 4
vim.opt.shiftwidth = 4
vim.opt.expandtab = true
--vim.cmd("retab")

-- Show invisible characters
vim.opt.listchars = { eol = "$", trail = ".", extends = ">", precedes = "<", tab = "> " }
--vim.opt.list = true

-- Indentation & editing behavior
vim.opt.autoindent = true
vim.opt.cindent = true
vim.opt.ruler = true
vim.opt.backspace = { "indent", "eol", "start" }
vim.opt.history = 50
vim.opt.formatoptions = "tcql"

-- Searching
vim.opt.hlsearch = true
vim.opt.ignorecase = true
vim.opt.incsearch = true

-- Status line
vim.opt.laststatus = 2
vim.opt.statusline:append("%F")  -- full file path

-- Cursorline
vim.opt.cursorline = true
vim.api.nvim_create_autocmd("WinEnter", {
  pattern = "*",
  callback = function() vim.opt_local.cursorline = true end,
})
vim.api.nvim_create_autocmd("WinLeave", {
  pattern = "*",
  callback = function() vim.opt_local.cursorline = false end,
})

-- Search highlight
vim.cmd("hi Search cterm=NONE ctermfg=grey ctermbg=magenta")

-- CursorLine for light/dark background
local function CursorLineL()
  vim.cmd("hi CursorLine cterm=NONE ctermbg=lightgrey guibg=lightgrey")
end
local function CursorLineD()
  vim.cmd("hi CursorLine term=NONE cterm=NONE ctermbg=233 guibg=Grey20")
end

vim.api.nvim_create_user_command("CurL", CursorLineL, {})
vim.api.nvim_create_user_command("CurD", CursorLineD, {})

if vim.o.background == "dark" then
  CursorLineD()
else
  CursorLineL()
end

-- Open last file if no args
local function OpenLastFile()
  if vim.fn.argc() ~= 0 then return end
  local first = vim.v.oldfiles[1]
  if first and vim.fn.filereadable(first) == 1 then
    vim.cmd("edit " .. vim.fn.fnameescape(first))
  end
end

vim.api.nvim_create_autocmd("VimEnter", { callback = OpenLastFile })

-- Highlight column > 80 chars
local function OverLen()
  if vim.o.background == "dark" then
    vim.cmd("highlight OverLength ctermbg=red ctermfg=white guibg=#592929")
  end
  vim.fn.matchadd("OverLength", "\\%81v.\\+")
end
vim.api.nvim_create_user_command("OverLen", OverLen, {})

-- Quickfix helpers
local function ClearQuickfixList() vim.fn.setqflist({}) end
vim.api.nvim_create_user_command("ClearQuickfixList", ClearQuickfixList, {})

-- Grep helpers
vim.api.nvim_create_user_command("VimGrepCursorw",
  function() vim.cmd("vimgrep " .. vim.fn.expand("<cword>") .. " " .. vim.fn.fnameescape(vim.fn.expand("%:p")) .. " | copen | cc") end, {})

vim.api.nvim_create_user_command("VimGrepCursorW",
  function() vim.cmd("vimgrep " .. vim.fn.expand("<cWORD>") .. " " .. vim.fn.fnameescape(vim.fn.expand("%:p")) .. " | copen | cc") end, {})

vim.api.nvim_create_user_command("VimGrepYanked",
  function() vim.cmd("vimgrep /" .. vim.fn.getreg("0") .. "/ " .. vim.fn.fnameescape(vim.fn.expand("%:p")) .. " | copen | cc") end, {})

vim.api.nvim_create_user_command("VimGrepError",
  function() vim.cmd("vimgrep /\\<(FATAL|ERROR|ERRORS|FAIL|FAILED|FAILURE)\\>/ " .. vim.fn.fnameescape(vim.fn.expand("%:p")) .. " | copen | cc") end, {})

vim.api.nvim_create_user_command("VimGrepWarn",
  function() vim.cmd("vimgrep /\\<(WARNING|DELETE|DELETING|DELETED|RETRY|RETRYING|Diagnostic)\\>/ " .. vim.fn.fnameescape(vim.fn.expand("%:p")) .. " | copen | cc") end, {})

vim.api.nvim_create_user_command("VimGrepErrorAppend",
  function() vim.cmd("vimgrepadd /\\<(FATAL|ERROR|ERRORS|FAIL|FAILED|FAILURE)\\>/ " .. vim.fn.fnameescape(vim.fn.expand("%:p")) .. " | copen | cc") end, {})

vim.api.nvim_create_user_command("VimGrepWarnAppend",
  function() vim.cmd("vimgrepadd /\\<(WARNING|DELETE|DELETING|DELETED|RETRY|RETRYING|Diagnostic)\\>/ " .. vim.fn.fnameescape(vim.fn.expand("%:p")) .. " | copen | cc") end, {})

-- Source extra scripts
vim.api.nvim_create_user_command("Nblog", function()
  vim.cmd("source ~/.vim/syntax/nblog.vim")
end, {})

vim.api.nvim_create_user_command("Abb", function()
  vim.cmd("source ~/.vim/plugin/abbreviations.vim")
end, {})

-- Copy paths to clipboard
vim.api.nvim_create_user_command("CurrentFilePathCopy", function()
  vim.fn.setreg("+", vim.fn.expand("%:p"))
end, {})

vim.api.nvim_create_user_command("CurrentFileDirCopy", function()
  vim.fn.setreg("+", vim.fn.expand("%:p:h"))
end, {})

-- Commands to manage iskeyword and completeopt
vim.api.nvim_create_user_command("SetWORDcomplete", function()
    vim.opt.iskeyword:append({ "@", ".", "-", "_" })
    vim.opt.completeopt:append("menuone")
end, {})

vim.api.nvim_create_user_command("UnsetWORDcomplete", function()
    vim.opt.iskeyword:remove({ ".", "-" })
    vim.opt.completeopt:remove("menuone")
end, {})

vim.api.nvim_create_user_command("ShowKeywords", function()
    print(vim.o.iskeyword)
end, {})

-- Keymaps for copying paths
if vim.fn.has("win32") == 1 then
    vim.keymap.set("n", ",cs", [[:let @*=substitute(expand("%"), "/", "\\", "g")<CR>]])
    vim.keymap.set("n", ",cl", [[:let @*=substitute(expand("%:p"), "/", "\\", "g")<CR>]])
    vim.keymap.set("n", ",yf", [[:let @"=substitute(expand("%:p"), "/", "\\", "g")<CR>]])
    vim.keymap.set("n", ",yn", [[:let @"=substitute(expand("%"), "/", "\\", "g")<CR>]])
    vim.keymap.set("n", ",c8", [[:let @*=substitute(expand("%:p:8"), "/", "\\", "g")<CR>]])
else
    vim.keymap.set("n", ",cs", [[:let @*=expand("%")<CR>]])
    vim.keymap.set("n", ",cl", [[:let @*=expand("%:p")<CR>]])
    vim.keymap.set("n", ",cf", [[:let @*=expand("%:p")<CR>]], { desc = "Copy File path" })
    vim.keymap.set("n", ",yf", [[:let @"=expand("%:p")<CR>]], { desc = "Yank File path" })
    vim.keymap.set("n", ",fn", [[:let @"=expand("%")<CR>]], { desc = "Yank File Name" })
end

-- Terminal / GUI settings
if vim.fn.has("nvim") == 1 then
    vim.opt.ttyfast = true
else
    vim.opt.ttyfast = true
    vim.opt.ttyscroll = 3
    if vim.fn.has("unix") == 1 then
        vim.opt.term = "screen-256color"
    end
end

if vim.fn.has("win32") == 1 then
    vim.opt.guifont = "Consolas:h10"
    -- vim.cmd("call CursorLineL()") -- if you have this function defined somewhere
else
    if vim.fn.has("gui_running") == 1 then
        -- vim.opt.guifont = "monaco:h11"
        -- vim.opt.guifont = "menlo regular:h12"
        -- vim.opt.guifont = "Consolas:h12"
        vim.opt.guifont = "6x13:h13"
    end
end

-- Source external vimscript files (Neovim still supports :source)
-- vim.cmd("source ~/.vim/cscope_maps.vim")

vim.cmd("source ~/.vim/et.vim")



-- Quick copy current buffer to next window
vim.fn.setreg("c", "ggVGy<C-W><C-W>ggVGp")
-- Quick copy opposite buffer to current buffer
vim.fn.setreg("n", "<C-W><C-W>ggVGy<C-W><C-W>ggVGp")

-- Diff mode customizations
if vim.wo.diff then
    vim.keymap.set("n", "mo", "do]c", { desc = "Obtain diff hunk" })
    vim.keymap.set("n", "mp", "dp]c", { desc = "Put diff hunk" })

    vim.api.nvim_create_autocmd("VimResized", {
        pattern = "*",
        command = "wincmd =",
    })

    vim.cmd([[
        highlight DiffAdd    cterm=bold ctermfg=10 ctermbg=17 gui=none guifg=bg guibg=Red
        highlight DiffDelete cterm=bold ctermfg=10 ctermbg=17 gui=none guifg=bg guibg=Red
        highlight DiffChange cterm=bold ctermfg=10 ctermbg=17 gui=none guifg=bg guibg=Red
        highlight DiffText   cterm=bold ctermfg=10 ctermbg=88 gui=none guifg=bg guibg=Red
    ]])
elseif vim.fn.has("gui_running") == 1 then
    -- vim.cmd.colorscheme("torte")
    -- vim.cmd.colorscheme("zellner")
    vim.opt.scrolljump = 5
    vim.opt.scroll = math.floor(vim.o.lines / 3)
end

-- Keymaps
vim.keymap.set("n", "<F2>", ":help <C-R><C-W><CR>", { silent = false })
vim.keymap.set("v", "<", "<gv")
vim.keymap.set("v", ">", ">gv")

-- Pydiction plugin settings
vim.g.pydiction_location = "~/.vim/bundle/pydiction/complete-dict"
vim.g.pydiction_menu_height = 3

-- Open file in readonly mode if swap exists
vim.api.nvim_create_autocmd("SwapExists", {
    pattern = "*",
    callback = function()
        vim.v.swapchoice = "o"
    end,
})

-- Window and buffer mappings
vim.keymap.set("n", "<C-L>", "<C-W>|<C-W>_")
vim.keymap.set("n", "<leader>fb", ":FufBuffer<CR>", { silent = true })
vim.keymap.set("n", "<leader>ff", ":FufFile<CR>", { silent = true })

vim.keymap.set("n", "<leader>bl", ":buffers<CR>", { silent = true })
vim.keymap.set("n", "<leader>bd", ":bd<CR>", { silent = true })
vim.keymap.set("n", "<leader>bn", ":bnext<CR>", { silent = true })
vim.keymap.set("n", "<leader>bp", ":bprev<CR>", { silent = true })




-- Function to include project-specific .vimrc if exists
local function F_include_project_specific_vimrc()
  local rootpath = vim.fn.system("git rev-parse --show-toplevel")
  local rootpathtrim = string.gsub(rootpath, "\n$", "")
  local local_vimrc = string.gsub(rootpath, "\n$", "/.vimrc")

  if vim.fn.isdirectory(rootpathtrim) == 1 then
    vim.g.git_root_path = rootpathtrim
    vim.opt.path:append(rootpathtrim)
  else
    vim.g.git_root_path = "."
  end

  if vim.fn.filereadable(local_vimrc) == 1 then
    if vim.fn.has("win32") == 1 or vim.fn.has("win64") == 1 then
      vim.cmd("source " .. local_vimrc)
    else
      vim.cmd("source " .. local_vimrc)
    end
  end
end

F_include_project_specific_vimrc()



-- OpenSSL args
local opensslargs      = "x509 -text -noout -fingerprint -sha1 -in #"
local opensslchainarg1 = "crl2pkcs7 -nocrl -certfile #"
local opensslchainarg2 = "pkcs7 -print_certs -text -noout"

-- Auto-command: on BufReadPost or BufNewFile for *.0, run openssl
vim.api.nvim_create_autocmd({ "BufReadPost", "BufNewFile" }, {
  pattern = "*.0",
  callback = function()
    vim.cmd("vnew %.x509 | r!openssl " .. opensslargs)
  end,
})

-- Commands
vim.api.nvim_create_user_command("GenX509", function()
  vim.cmd("vnew | r!openssl " .. opensslargs)
end, {})

vim.api.nvim_create_user_command("GenX509chain", function()
  vim.cmd("vnew | r!openssl " .. opensslchainarg1 .. " | openssl " .. opensslchainarg2)
end, {})

if vim.fn.has("win32") == 1 or vim.fn.has("win64") == 1 then
  vim.api.nvim_create_user_command("GenX509Nb", function()
    vim.cmd("vnew | r!vxsslcmd.exe " .. opensslargs)
  end, {})

  vim.api.nvim_create_user_command("GenX509chainNb", function()
    vim.cmd("vnew | r!vxsslcmd.exe " .. opensslchainarg1 .. " | vxsslcmd.exe " .. opensslchainarg2)
  end, {})
else
  vim.api.nvim_create_user_command("GenX509Nb", function()
    vim.cmd("vnew | r!/usr/openv/netbackup/bin/goodies/vxsslcmd " .. opensslargs)
  end, {})

  vim.api.nvim_create_user_command("GenX509chainNb", function()
    vim.cmd("vnew | r!/usr/openv/netbackup/bin/goodies/vxsslcmd " .. opensslchainarg1 ..
            " | /usr/openv/netbackup/bin/goodies/vxsslcmd " .. opensslchainarg2)
  end, {})
end





-- Macros preloaded into registers
-- Usage: run with @o, @t, @p, @v, @w, @x

-- @o → Yank current line, open in horizontal split, maximize split height
vim.fn.setreg("o", [[:only
0v$"zy:sp z¬Äkb
:wincmd _
]])

-- @t → Yank current line, open in new tab
vim.fn.setreg("t", [[:only
0v$"zy:tabedit z¬Äkb
]])

-- @p → Yank current line, open in horizontal split, keep split height
vim.fn.setreg("p", [[0v$"zy:sp z¬Äkb
:wincmd _
]])

-- @v → Yank current line, open in vertical split, switch buffers,
--       move window right, go to next buffer, resize split
vim.fn.setreg("v", [[:BufOnly
0v$"zy:vsp z¬Äkb | bN
:wincmd r
:bn
:wincmd |
:vertical resize -70
]])

-- @w → Yank current line, move to next window, open in horizontal split
vim.fn.setreg("w", [[0v$"zy:wincmd w
:sp z¬Äkb
]])

-- @x → Yank current line, move to next window, open in vertical split, return to previous window
vim.fn.setreg("x", [[0v$"zy:wincmd w
:vsp z¬Äkb
:wincmd p
]])





-- Insert a new UUID in insert mode (Ctrl+j u)
vim.keymap.set("i", "<C-j>u", function()
  return string.upper(vim.fn.system("uuidgen"):gsub("\n", ""))
end, { expr = true, desc = "Insert uppercase UUID" })

-- Toggle paste mode with F2 (useful for copy-paste without autoindent messing up)
-- Toggle "paste mode" manually in Neovim
vim.keymap.set("n", "<F2>", function()
  vim.opt.paste = not vim.opt.paste:get()
  print("Paste mode: " .. tostring(vim.opt.paste:get()))
end, { desc = "Toggle paste mode" })


-- Better copy-paste: if not inside tmux, use system clipboard
if vim.env.TMUX == nil or vim.env.TMUX == "" then
  vim.opt.clipboard:append("unnamed")
end

-- Global variables to configure C toolchain integrations
vim.g.C_UseTool_cmake   = "yes"
vim.g.C_UseTool_doxygen = "yes"




-- EasyMotion: set leader key for EasyMotion to "\"
vim.g.EasyMotion_leader_key = "\\"

-- Better command-line completion (wildmenu)
if vim.fn.has("wildmenu") == 1 then
  vim.opt.wildmenu = true
  vim.opt.wildmode = { "longest:full", "full" }
end

-- Menu support when not in GUI (terminal mode)
if vim.fn.has("gui_running") == 0 then
  vim.cmd("runtime! menu.vim") -- load menu support
  -- wildcharm needs a keycode number, not a string
  vim.opt.wildcharm = vim.api.nvim_replace_termcodes("<C-]>", true, true, true):byte()

  -- Keymaps for accessing menu with <C-Z>
  vim.keymap.set("n", "<C-Z>", ":emenu <C-]>", { silent = true, desc = "Open menu" })
  vim.keymap.set("i", "<C-Z>", "<C-O>:emenu <C-]>", { silent = true, desc = "Open menu (insert)" })
end





-- Use netrw in tree style if NERDTree is not installed
vim.g.netrw_liststyle = 3

-- NERDTree and Tagbar settings
vim.g.NERDTreeWinPos = "right"     -- Open NERDTree on the right side
vim.g.tagbar_left = 1              -- Open Tagbar on the left side
vim.g.tagbar_width = 30            -- Set Tagbar window width
vim.g.tagbar_autofocus = 1         -- Auto focus Tagbar
vim.g.tagbar_autoclose = 0         -- Keep Tagbar open when switching buffers

-- Shortcut to toggle Tagbar with <Leader>st
vim.keymap.set("n", "<Leader>st", ":TagbarToggle<CR>", { silent = true })

-- Change local directory to current file's folder on buffer enter
vim.api.nvim_create_autocmd("BufEnter", {
  pattern = "*",
  command = "silent! lcd %:p:h",
})

-- Track NERDTree state (whether opened via toggle)
if vim.g.nerdtreefindexec == nil then
  vim.g.nerdtreefindexec = 0
end

-- Custom function to toggle NERDTree and return focus to previous window
function _G.F_toggle_nerdtree_settings()
  if vim.g.nerdtreefindexec == 1 then
    vim.g.nerdtreefindexec = 0
    vim.cmd("NERDTreeClose")
    vim.cmd("wincmd p")
  else
    vim.g.nerdtreefindexec = 1
    vim.cmd("NERDTreeToggle")
    vim.cmd("NERDTreeFind")
    vim.cmd("wincmd p")
  end
end






-- NERDTree is disabled by default
vim.g.nerdtreefindexec = 0

-- Toggle NERDTree with <Leader>sn
vim.keymap.set("n", "<Leader>sn", ":silent lua F_toggle_nerdtree_settings()<CR>", { silent = true })

-- Commands to enable/disable NERDTree auto-find mode
vim.api.nvim_create_user_command("NERDTreeFindExeOff", function()
  vim.g.nerdtreefindexec = 0
end, {})

vim.api.nvim_create_user_command("NERDTreeFindExeOn", function()
  vim.g.nerdtreefindexec = 1
end, {})

-- Apply autocmds only if not in diff mode and nerdtree auto-find is on
if not vim.wo.diff and vim.g.nerdtreefindexec == 1 then
  -- When leaving buffer, keep NERDTree in sync
  vim.api.nvim_create_autocmd("BufLeave", {
    callback = function()
      if vim.g.nerdtreefindexec == 1 and not string.match(vim.fn.expand("%"), "NERD_tree") then
        vim.cmd("silent! NERDTreeFind | wincmd p")
      end
    end,
  })

  -- On entering buffer, sync NERDTree with current file
  vim.api.nvim_create_autocmd("BufEnter", {
    callback = function()
      if vim.g.nerdtreefindexec == 1
          and not string.match(vim.fn.expand("%"), "NERD_tree")
          and not string.match(vim.fn.expand("#"), "NERD_tree")
          and vim.fn.filereadable(vim.fn.fnameescape(vim.fn.expand("%"))) == 1
      then
        vim.cmd("silent! NERDTreeFind | wincmd p")
      end
    end,
  })

  -- On VimEnter, open NERDTree and return focus to main window
  vim.api.nvim_create_autocmd("VimEnter", {
    callback = function()
      if vim.g.nerdtreefindexec == 1 and not string.match(vim.fn.expand("%"), "NERD_tree") then
        vim.cmd("NERDTree | wincmd p")
      end
    end,
  })

  -- Close Neovim if only NERDTree is left open
  vim.api.nvim_create_autocmd("BufEnter", {
    callback = function()
      if vim.fn.winnr("$") == 1 and vim.b.NERDTree and vim.b.NERDTree.isTabTree == 1 then
        vim.cmd("q")
      end
    end,
  })
end

-- Console compatibility for arrows
vim.g.nerdtree_tabs_open_on_console_startup = 0
vim.g.NERDTreeDirArrowExpandable = ">"
vim.g.NERDTreeDirArrowCollapsible = "v"
vim.g.NERDTreeIgnore = { [[\~$]], [[\.pyc$]], [[__pycache__]] }






-- Function: Insert a Python docstring snippet from ~/.vim/plugin/pydocstring
function InsertDocString()
  -- Save current cursor position
  local pos = vim.fn.getpos(".")

  -- Path to the template file
  local file = vim.fn.expand("$HOME/.vim/plugin/pydocstring")

  -- Echo the file path (for debugging)
  print("File path: " .. file)

  -- Read file content into the buffer at current cursor position
  vim.cmd("read " .. file)

  -- Restore cursor position
  vim.fn.setpos(".", pos)
end

-- Function: Define a text object for ${...} placeholders
function TextobjPlaceholder()
  -- Get current line content
  local line = vim.api.nvim_get_current_line()

  -- Find the first occurrence of "${" and "}"
  local start = { line:find("%${") }
  local finish = { line:find("}") }

  if start[1] and finish[1] and start[1] < finish[1] then
    -- Move cursor to start of placeholder
    vim.fn.cursor(0, start[1])
    vim.cmd("normal! v")
    -- Move cursor to end of placeholder
    vim.fn.cursor(0, finish[1])
  end
end

-- Map to text objects (like `i$`)
vim.keymap.set("x", "i$", ":<C-u>lua TextobjPlaceholder()<CR>", { silent = true })
vim.keymap.set("o", "i$", ":<C-u>lua TextobjPlaceholder()<CR>", { silent = true })

-- Optional: Command to insert docstring
vim.api.nvim_create_user_command("InsertDocString", InsertDocString, {})









-- ==============================
-- Python settings
-- ==============================
vim.api.nvim_create_augroup("python_ft", { clear = true })
vim.api.nvim_create_autocmd("FileType", {
  group = "python_ft",
  pattern = "python",
  callback = function()
    -- Use pylint as makeprg
    vim.opt.makeprg = "pylint --reports=n --output-format=parseable --rcfile=$(git rev-parse --show-toplevel)/.pylintrc %:p"

    -- Error format for quickfix parsing
    vim.opt.efm = "%A%f:%l: [%t%.%#] %m,%Z%p^^,%-C%.%#"

    -- Enable full syntax highlighting
    vim.g.python_highlight_all = 1

    -- Insert docstring with <C-d> in insert mode
    vim.keymap.set("i", "<C-d>", function()
      vim.cmd("stopinsert")   -- exit insert mode
      InsertDocString()       -- call our Lua function
      vim.cmd("startinsert")  -- re-enter insert mode
    end, { buffer = true })
  end,
})

-- Apply indentation rules to Python buffers
vim.api.nvim_create_autocmd({ "BufNewFile", "BufRead" }, {
  group = "python_ft",
  pattern = "*.py",
  callback = function()
    vim.opt.tabstop = 4
    vim.opt.softtabstop = 4
    vim.opt.shiftwidth = 4
    vim.opt.textwidth = 79
    vim.opt.expandtab = true
    vim.opt.autoindent = true
    vim.opt.fileformat = "unix"
  end,
})


-- ==============================
-- YAML settings
-- ==============================
vim.api.nvim_create_augroup("yaml_ft", { clear = true })
vim.api.nvim_create_autocmd("FileType", {
  group = "yaml_ft",
  pattern = "yaml",
  callback = function()
    vim.g.syntastic_yaml_checkers = { "yamllint" }
    vim.opt_local.tabstop = 2
    vim.opt_local.softtabstop = 2
    vim.opt_local.shiftwidth = 2
    vim.opt_local.expandtab = true
    vim.g.indentLine_char = "|"
  end,
})


-- ==============================
-- WiX files (*.wxs) → XML
-- ==============================
vim.api.nvim_create_augroup("wix_ft", { clear = true })
vim.api.nvim_create_autocmd({ "BufNewFile", "BufRead" }, {
  group = "wix_ft",
  pattern = "*.wxs",
  command = "setfiletype xml",
})


-- ==============================
-- Groovy files (*.gradle)
-- ==============================
vim.api.nvim_create_augroup("groovy_ft", { clear = true })
vim.api.nvim_create_autocmd({ "BufNewFile", "BufRead" }, {
  group = "groovy_ft",
  pattern = "*.gradle",
  command = "setfiletype groovy",
})


-- ==============================
-- Global syntax enable (legacy equivalent of :syntax on)
-- ==============================
vim.cmd("syntax enable")






-- Only needed if you're still using terryma/vim-multiple-cursors
vim.g.multicursor_quit = "<Esc>"
vim.g.multi_cursor_start_key = "<F4>"

vim.keymap.set("n", "<Leader><C-m>p", ":call MultiCursorPlaceCursor()<CR>", { silent = true })
vim.keymap.set("n", "<Leader><C-m>r", ":call MultiCursorRemoveCursors()<CR>", { silent = true })
vim.keymap.set("n", "<Leader><C-m>m", ":call MultiCursorManual()<CR>", { silent = true })
vim.keymap.set("n", "<Leader><C-m>v", ":call MultiCursorVisual()<CR>", { silent = true })
vim.keymap.set("x", "<Leader><C-m>s", ":call MultiCursorSearch('')<CR>", { silent = true })





-- Search all subdirectories when using :find
vim.opt.path:append("**")


-- ALE options
vim.g.ale_python_flake8_options =
  "--ignore=E501,E221,D100,D101,D102,D103"
vim.g.ale_python_pycodestyle_options =
  "--ignore=E221,E226,E302,E71,E501,W12,D100,D101,D102,D103"




-- Template plugin settings
vim.g.tmpl_auto_initialize = 0
vim.g.tmpl_author_name     = "atuld8"
vim.g.tmpl_author_email    = "atuld8@gmail.com"
vim.g.tmpl_company         = "<company private ltd.>"

-- Define :SilentCmd command (run shell command silently and redraw)
vim.api.nvim_create_user_command("SilentCmd", function(opts)
  vim.cmd("silent !" .. opts.args)
  vim.cmd("redraw!")
end, { nargs = 1 })

-- Example:
-- vim.api.nvim_create_user_command("Makeall", function()
--   vim.cmd("SilentCmd tmux send -t 2 'make ; make.suse' Enter")
-- end, {})

-- CtrlP plugin: open buffer list by default
vim.g.ctrlp_cmd = "CtrlPBuffer"

-- Load project-specific vimrc (must be last)
--- Call it once on startup
F_include_project_specific_vimrc()

vim.g.session_autoload = "no"
vim.g.session_autosave = "no"
