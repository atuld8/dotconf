-- Cursor CLI (agent) integration for Neovim
-- https://github.com/suiramdev/cursorcli.nvim

local function git_root()
  local root = vim.fn.systemlist("git rev-parse --show-toplevel 2>/dev/null")
  if vim.v.shell_error == 0 and root[1] and root[1] ~= "" then
    return root[1]
  end
  return vim.loop.cwd()
end

local function open_in_cursor(path, line, col)
  local cmd = { "cursor" }
  if line and line > 0 then
    local loc = string.format("%s:%d", path, line)
    if col and col > 0 then
      loc = loc .. ":" .. col
    end
    table.insert(cmd, "--goto")
    table.insert(cmd, loc)
  else
    table.insert(cmd, path)
  end
  vim.fn.jobstart(cmd, { detach = true })
end

-- vim-tmux-navigator maps <C-h/j/k/l> to TmuxNavigate* in n/t mode when $TMUX
-- is set. That steals keys from the Cursor agent terminal (e.g. <C-h> backspace).
local function disable_tmux_nav_for_cursor_terminal(bufnr)
  if not vim.api.nvim_buf_is_valid(bufnr) then
    return
  end

  local ok = pcall(vim.api.nvim_buf_get_var, bufnr, "cursorcli_chat_id")
  if not ok then
    return
  end

  for _, key in ipairs({ "<C-h>", "<C-j>", "<C-k>", "<C-l>", "<C-\\>" }) do
    vim.keymap.set("t", key, key, {
      buffer = bufnr,
      silent = true,
      desc = "Pass key to Cursor agent terminal",
    })
    vim.keymap.set("n", key, "<Nop>", {
      buffer = bufnr,
      silent = true,
      desc = "Disable tmux-navigator in Cursor agent window",
    })
  end
end

local cursor_tmux_fix = vim.api.nvim_create_augroup("cursor_cli_tmux_fix", { clear = true })

vim.api.nvim_create_autocmd({ "TermOpen", "BufWinEnter" }, {
  group = cursor_tmux_fix,
  callback = function(event)
    if vim.bo[event.buf].buftype == "terminal" then
      disable_tmux_nav_for_cursor_terminal(event.buf)
    end
  end,
})

vim.api.nvim_create_user_command("CursorOpen", function(opts)
  local path = vim.fn.expand(opts.fargs[1] or "%:p")
  local line = opts.fargs[2] and tonumber(opts.fargs[2]) or nil
  open_in_cursor(path, line)
end, { nargs = "?", complete = "file" })

vim.api.nvim_create_user_command("CursorProject", function()
  open_in_cursor(git_root())
end, {})

vim.keymap.set("n", "<leader>co", function()
  open_in_cursor(vim.fn.expand("%:p"), vim.fn.line("."), vim.fn.col("."))
end, { desc = "Open file in Cursor IDE" })

vim.keymap.set("n", "<leader>cp", function()
  open_in_cursor(git_root())
end, { desc = "Open project in Cursor IDE" })

return {
  {
    "suiramdev/cursorcli.nvim",
    event = "VeryLazy",
    opts = {
      command = { "agent" },
      auto_insert = true,
      notify = true,
      path = { relative_to_cwd = true },
      position = "float",
      float = {
        width = 0.9,
        height = 0.85,
        border = "rounded",
      },
    },
    config = function(_, opts)
      require("cursorcli").setup(opts)
    end,
    keys = {
      { "<leader>caf", "<Cmd>CursorCliOpenWithLayout float<CR>", desc = "Cursor agent (float)", mode = "n" },
      { "<leader>cav", "<Cmd>CursorCliOpenWithLayout vsplit<CR>", desc = "Cursor agent (vsplit)", mode = "n" },
      { "<leader>cah", "<Cmd>CursorCliOpenWithLayout hsplit<CR>", desc = "Cursor agent (hsplit)", mode = "n" },
      { "<leader>cac", function() require("cursorcli").close() end, desc = "Close Cursor agent", mode = "n" },
      { "<leader>can", function() require("cursorcli").new_chat() end, desc = "New Cursor chat", mode = "n" },
      { "<leader>cas", function() require("cursorcli").select_chat() end, desc = "Select Cursor chat", mode = "n" },
      { "<leader>car", function() require("cursorcli").rename_chat() end, desc = "Rename Cursor chat", mode = "n" },
      { "<leader>caR", function() require("cursorcli").resume() end, desc = "Resume Cursor chat", mode = "n" },
      { "<leader>cax", function() require("cursorcli").restart() end, desc = "Restart Cursor agent", mode = "n" },
      { "<leader>cal", function() require("cursorcli").list_sessions() end, desc = "List Cursor sessions", mode = "n" },
      { "<leader>cae", function() require("cursorcli").request_fix_error_at_cursor() end, desc = "Cursor: fix error at cursor", mode = "n" },
      { "<leader>caa", function() require("cursorcli").add_visual_selection() end, desc = "Send selection to Cursor", mode = "x" },
      { "<leader>caA", function() require("cursorcli").request_fix_error_at_cursor_in_new_session() end, desc = "Cursor: fix error (new session)", mode = "n" },
      { "<leader>caA", function() require("cursorcli").add_visual_selection_to_new_session() end, desc = "Cursor: send selection (new session)", mode = "x" },
    },
  },
}
