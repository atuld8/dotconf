return {
  {
    "dhananjaylatkar/cscope_maps.nvim",
    dependencies = { "nvim-telescope/telescope.nvim" },
    config = function()
      require("cscope_maps").setup({
        cscope = {
          db_file = "./cscope.out",
          exec = "cscope",
          picker = "telescope",
        },
      })
    end,
  },
}

