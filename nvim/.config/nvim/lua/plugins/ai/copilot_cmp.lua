-- ==================================================================================================
-- Title: Copilot CMP Integration
-- About: Configuration for integrating GitHub Copilot with nvim-cmp
-- ==================================================================================================

return {
  {
    "zbirenbaum/copilot-cmp",
    dependencies = { "zbirenbaum/copilot.lua" },
    event = "InsertEnter",
    config = function()
      require("copilot_cmp").setup({
        fix_pairs = true,
      })
    end,
  },
}
