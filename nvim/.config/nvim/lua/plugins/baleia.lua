-- baleia.nvim: render ANSI color codes in nvim buffers
-- Manual: :BaleiaColorize to apply to the current buffer
return {
  "m00qek/baleia.nvim",
  commit = "710537ff5cd669c5a76c5f5b6a9169fd9b913d18",
  submodules = false, -- test deps only; avoids broken submodule checkout on sync
  config = function()
    local baleia = require("baleia").setup()

    -- Rendering is explicit so opening a file never changes its buffer.
    vim.api.nvim_create_user_command("BaleiaColorize", function()
      local bufnr = vim.api.nvim_get_current_buf()
      if vim.bo[bufnr].buftype ~= "" or not vim.bo[bufnr].modifiable then
        vim.notify("Baleia: current buffer is not modifiable", vim.log.levels.WARN)
        return
      end
      baleia.once(bufnr)
    end, {})
  end,
}
