-- LSP + Autocomplete setup

-- Safely import dependencies
local cmp = require("cmp")
local cmp_lsp = require("cmp_nvim_lsp")

-- Capabilities (so LSP knows completion is available)
local capabilities = cmp_lsp.default_capabilities()

-- Common on_attach
local on_attach = function(_, bufnr)
  local map = function(mode, lhs, rhs)
    vim.keymap.set(mode, lhs, rhs, { buffer = bufnr })
  end
  map("n", "gd", vim.lsp.buf.definition)
  map("n", "K", vim.lsp.buf.hover)
  map("n", "gr", vim.lsp.buf.references)
end

-- Lua LSP
vim.lsp.config('lua_ls', {
  cmd = { "lua-language-server" },
  filetypes = { "lua" },
  settings = {
    Lua = {
      diagnostics = {
        globals = { "vim" },
        disable = { "large-file-warning" },
      },
      workspace = {
        library = vim.api.nvim_get_runtime_file("", true),
      },
      telemetry = { enable = false },
    },
  },
  on_attach = on_attach,
  capabilities = capabilities,
})

-- C/C++ LSP (clangd)
vim.lsp.config('clangd', {
  cmd = { "clangd" },
  filetypes = { "c", "cpp", "objc", "objcpp" },
  on_attach = on_attach,
  capabilities = capabilities,
})

-- Python LSP (pyright)
vim.lsp.config('pyright', {
  cmd = { "pyright-langserver", "--stdio" },
  filetypes = { "python" },
  on_attach = on_attach,
  capabilities = capabilities,
})

-- Enable LSP servers for configured filetypes
vim.api.nvim_create_autocmd("FileType", {
  pattern = { "lua", "c", "cpp", "objc", "objcpp", "python" },
  callback = function(args)
    local ft = args.match
    if ft == "lua" then
      vim.lsp.enable('lua_ls')
    elseif ft == "c" or ft == "cpp" or ft == "objc" or ft == "objcpp" then
      vim.lsp.enable('clangd')
    elseif ft == "python" then
      vim.lsp.enable('pyright')
    end
  end,
})


-- Autocomplete
cmp.setup({
  snippet = {
    expand = function(args)
      -- requires 'L3MON4D3/LuaSnip'
      require("luasnip").lsp_expand(args.body)
    end,
  },
  mapping = {
    ["<C-Space>"] = cmp.mapping.complete(),
    ["<CR>"] = cmp.mapping.confirm({ select = true }),
  },
  sources = {
    { name = "nvim_lsp" },
    { name = "luasnip" },
    { name = "buffer" },
    { name = "path" },
  },
})

