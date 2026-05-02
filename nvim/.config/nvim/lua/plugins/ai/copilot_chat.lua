return {
  {
    "CopilotC-Nvim/CopilotChat.nvim",
    dependencies = {
      "zbirenbaum/copilot.lua",
      "nvim-lua/plenary.nvim",
    },
    event = "VeryLazy",
    config = function()
      require("CopilotChat").setup({
        window = {
          layout = "vertical",
          width = 0.4,
        },
      })

      local map = vim.keymap.set
      map({ "n", "v" }, "<leader>cc", "<cmd>CopilotChat<CR>",                       { desc = "Copilot Chat" })
      map({ "n", "v" }, "<leader>ce", ":<C-u>CopilotChatExplain<CR>",               { desc = "Copilot Explain" })
      map({ "n", "v" }, "<leader>cf", ":<C-u>CopilotChatFix<CR>",                   { desc = "Copilot Fix" })
      map({ "n", "v" }, "<leader>co", ":<C-u>CopilotChatOptimize<CR>",              { desc = "Copilot Optimize" })
      map({ "n", "v" }, "<leader>ct", ":<C-u>CopilotChatTests<CR>",                 { desc = "Copilot Tests" })
      map({ "n", "v" }, "<leader>ca", ":<C-u>CopilotChatAsk ",                      { desc = "Copilot Ask" })
    end,
  },
}
