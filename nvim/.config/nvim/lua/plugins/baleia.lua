-- baleia.nvim: render ANSI color codes in nvim buffers
-- Manual: :BaleiaColorize to apply to the current buffer
return {
  "m00qek/baleia.nvim",
  commit = "710537ff5cd669c5a76c5f5b6a9169fd9b913d18",
  submodules = false, -- test deps only; avoids broken submodule checkout on sync
  config = function()
    local baleia = require("baleia").setup()

    local function colorize_buffer(bufnr)
      if vim.bo[bufnr].buftype ~= "" or not vim.bo[bufnr].modifiable then
        return false
      end
      baleia.once(bufnr)
      return true
    end

    -- Automatically render ANSI files after they are read.
    vim.api.nvim_create_autocmd("BufReadPost", {
      pattern = "*.ansi",
      callback = function(args)
        colorize_buffer(args.buf)
      end,
    })

    -- Manual command remains available for any modifiable file.
    vim.api.nvim_create_user_command("BaleiaColorize", function()
      if not colorize_buffer(vim.api.nvim_get_current_buf()) then
        vim.notify("Baleia: current buffer is not modifiable", vim.log.levels.WARN)
      end
    end, {})
  end,
}
