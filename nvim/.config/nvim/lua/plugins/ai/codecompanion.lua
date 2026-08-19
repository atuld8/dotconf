-- ==================================================================================================
-- Title: CodeCompanion.nvim configuration
-- About: Cursor-like AI assistant for Neovim (pure Lua, no build required)
-- ==================================================================================================

return {
  {
    "olimorris/codecompanion.nvim",
    dependencies = {
      "nvim-lua/plenary.nvim",
      "nvim-treesitter/nvim-treesitter",
      "zbirenbaum/copilot.lua", -- Use existing Copilot auth
    },
    opts = {
      strategies = {
        chat = {
          adapter = "copilot",
        },
        inline = {
          adapter = "copilot",
        },
        agent = {
          adapter = "copilot",
        },
      },
      adapters = {
        copilot = function()
          return require("codecompanion.adapters").extend("copilot", {
            schema = {
              model = {
                default = "gpt-4o",
              },
            },
          })
        end,
      },
      display = {
        chat = {
          window = {
            layout = "vertical", -- vertical|horizontal|float|buffer
            width = 0.3,
            height = 0.5,
          },
        },
        diff = {
          enabled = true,
          provider = "default", -- default|mini_diff
        },
      },
    },
    keys = {
      { "<leader>aa", "<cmd>CodeCompanionChat Toggle<cr>", mode = { "n", "v" }, desc = "Toggle AI Chat" },
      { "<leader>ae", "<cmd>CodeCompanionChat Add<cr>", mode = "v", desc = "Add to AI Chat" },
      { "<leader>ac", "<cmd>CodeCompanionActions<cr>", mode = { "n", "v" }, desc = "AI Actions" },
      { "<leader>ai", "<cmd>CodeCompanion<cr>", mode = { "n", "v" }, desc = "Inline AI" },
    },
    cmd = { "CodeCompanion", "CodeCompanionChat", "CodeCompanionActions" },
  },
}
