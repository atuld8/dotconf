-- baleia.nvim: render ANSI color codes in nvim buffers
-- Usage: open any *.ansi file and colors render automatically
-- Manual: :BaleiaColorize  to apply to current buffer
return {
  "m00qek/baleia.nvim",
  commit = "710537ff5cd669c5a76c5f5b6a9169fd9b913d18",
  submodules = false, -- test deps only; avoids broken submodule checkout on sync
  config = function()
    local baleia = require("baleia").setup()

    -- Auto-render ANSI codes in *.ansi files
    vim.api.nvim_create_autocmd("BufReadPost", {
      pattern = "*.ansi",
      callback = function()
        baleia.once(vim.api.nvim_get_current_buf())
      end,
    })

    -- Manual command for any buffer
    vim.api.nvim_create_user_command("BaleiaColorize", function()
      baleia.once(vim.api.nvim_get_current_buf())
    end, {})
  end,
}
