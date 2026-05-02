-- ==================================================================================================
-- Title: Copilot configuration
-- About: Configuration for GitHub Copilot plugin for Neovim
-- ==================================================================================================

return {
  {
    "zbirenbaum/copilot.lua",
    cmd = "Copilot",
    build = ":Copilot auth",
    event = "InsertEnter",
    opts = {
      suggestion = {
        enabled = true,
        auto_trigger = true,    -- suggest as you type
        keymap = {
          accept = "<Tab>",     -- accept full suggestion
          accept_word = "<C-l>", -- accept one word
          next = "<M-]>",       -- next suggestion
          prev = "<M-[>",       -- previous suggestion
          dismiss = "<C-e>",    -- dismiss suggestion
        },
      },
      panel = { enabled = false },
      filetypes = {
        markdown = true,
        help = true,
      },
    },
  },
}
