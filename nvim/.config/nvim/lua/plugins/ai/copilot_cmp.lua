-- ==================================================================================================
-- Title: Copilot CMP Integration
-- About: Configuration for integrating GitHub Copilot with nvim-cmp
-- ==================================================================================================

return {
  {
    "zbirenbaum/copilot-cmp",
    commit = "15fc12af3d0109fa76b60b5cffa1373697e261d1",
    dependencies = { "zbirenbaum/copilot.lua" },
    event = "InsertEnter",
    config = function()
      local source = require("copilot_cmp.source")
      local orig_is_available = source.is_available
      source.is_available = function(self)
        local client = self.client
        -- Neovim 0.10+ LSP clients expose :is_stopped(); upstream calls .is_stopped().
        if client and type(client.is_stopped) ~= "function" then
          client.is_stopped = function()
            return client:is_stopped()
          end
        end
        return orig_is_available(self)
      end

      require("copilot_cmp").setup({
        fix_pairs = true,
      })
    end,
  },
}
