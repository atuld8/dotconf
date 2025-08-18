-- LSP + Autocomplete setup

-- Safely import dependencies
local lspconfig = require("lspconfig")
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

-- Lua (for Neovim config)
lspconfig.lua_ls.setup({
  on_attach = on_attach,
  capabilities = capabilities,
  settings = {
    Lua = {
      diagnostics = { globals = { "vim" }, disable = { "large-file-warning" }, },
      workspace = {
        library = vim.api.nvim_get_runtime_file("", true),
      },
      telemetry = { enable = false },
    },
  },
})

-- C/C++ (clangd)
lspconfig.clangd.setup({
  on_attach = on_attach,
  capabilities = capabilities,
})

-- Python (pyright)
lspconfig.pyright.setup({
  on_attach = on_attach,
  capabilities = capabilities,
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

