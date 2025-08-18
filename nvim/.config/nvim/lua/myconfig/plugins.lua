return {
  -- LSP
  { "neovim/nvim-lspconfig" },

  -- Autocompletion
  {
    "hrsh7th/nvim-cmp",
    dependencies = {
      "hrsh7th/cmp-nvim-lsp",
      "hrsh7th/cmp-buffer",
      "hrsh7th/cmp-path",
      "L3MON4D3/LuaSnip",
    },
  },

  -- Optional helper
  { "nvim-lua/plenary.nvim" },

  { "dhananjaylatkar/cscope_maps.nvim",
  dependencies = { "nvim-telescope/telescope.nvim" } },
   config = function()
    require("cscope_maps").setup({
      cscope = {
        db_file = "./cscope.out",
        exec = "cscope", -- or "gtags-cscope"
        picker = "telescope", -- "quickfix" or "fzf-lua" also possible
      },
    })
  end,
}

