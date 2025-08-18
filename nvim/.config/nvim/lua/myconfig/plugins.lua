return {

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

