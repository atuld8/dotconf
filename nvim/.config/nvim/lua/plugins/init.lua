-- lua/plugins/init.lua

return {
  -- Plugin manager can manage itself
  { "folke/lazy.nvim" },

  -- UI
  { "vim-airline/vim-airline" },

  -- File navigation
  { "preservim/nerdtree" },
  { "Xuyuanp/nerdtree-git-plugin" },
  { "kien/ctrlp.vim" },
  { "junegunn/fzf.vim" },
  { "Shougo/unite.vim" },

  -- Git
  { "tpope/vim-fugitive" },
  { "airblade/vim-gitgutter" },
  { "junegunn/gv.vim" },
  { "mhinz/vim-signify" },

  -- Editing Enhancements
  { "tpope/vim-surround" },
  { "scrooloose/nerdcommenter" },
  { "tomtom/tcomment_vim" },
  { "vim-scripts/ZoomWin" },
  { "vim-scripts/BufOnly.vim" },

  -- Fuzzy/Incremental Search
  { "haya14busa/incsearch.vim" },
  { "haya14busa/incsearch-fuzzy.vim" },

  -- Completion and Linting
  { "ervandew/supertab" },
  { "Shougo/neocomplcache.vim" },
  {
    "dense-analysis/ale",
    config = function()
      -- Disable ALE's integration with Neovim diagnostics to avoid conflicts with LSP
      vim.g.ale_use_neovim_diagnostics_api = 0
      
      -- Only lint on save and when text changes after leaving insert mode
      vim.g.ale_lint_on_text_changed = 'normal'
      vim.g.ale_lint_on_insert_leave = 1
      vim.g.ale_lint_on_enter = 0
      
      -- Linters
      vim.g.ale_linters = {
        python = { "flake8", "pycodestyle", "pylint" },
        cpp = { "gcc", "clang" },
        c   = { "gcc", "clang" },
      }

      -- Python options
      vim.g.ale_python_flake8_options =
        "--ignore=E501,E221,D100,D101,D102,D103"
      vim.g.ale_python_pycodestyle_options =
        "--ignore=E221,E226,E302,E71,E501,W12,D100,D101,D102,D103"

      -- Compiler flags
      vim.g.ale_cpp_gcc_options = "-Wall"
      vim.g.ale_c_gcc_options   = "-Wall"

      -- UI
      vim.g.ale_sign_error = "✘"
      vim.g.ale_sign_warning = "⚠"
      vim.g.ale_fix_on_save = 1
    end,
  },

  -- Undo Tree
  { "mbbill/undotree" },
  { "sjl/gundo.vim" },

  -- Language Support
  { "vim-scripts/perl-support.vim" },
  { "fatih/vim-go", ft = "go" },
  { "davidhalter/jedi-vim", ft = "python" },

  -- Syntax and Formatting
  { "elzr/vim-json" },
  { "godlygeek/tabular" },
  { "junegunn/vim-easy-align",
  keys = {
    { "ga", "<Plug>(EasyAlign)", mode = { "n", "x" } }
  } },

  -- Markdown
  { "gabrielelana/vim-markdown" },
  { "shime/vim-livedown" },
  { "dhruvasagar/vim-table-mode",
      ft = { "markdown", "text", "org" },
      keys = {
          { "<leader>tm", ":TableModeToggle<CR>", desc = "Toggle Table Mode" }
      }
  },

  -- Misc
  { "tpope/vim-eunuch" },
  { "tyru/transbuffer.vim" },
  {
      "xolox/vim-session",
      dependencies = { "xolox/vim-misc" },
  },
  {
      "xolox/vim-misc",  -- required by vim-session
      lazy = true,
  },
  { "ntpeters/vim-better-whitespace" },
  { "christoomey/vim-tmux-navigator" },
  { "MattesGroeger/vim-bookmarks" },
  { "andrewradev/linediff.vim" },
  { "preservim/tagbar" },

  -- Telescope fuzzy finder
  { "nvim-lua/plenary.nvim" },
  {
      "nvim-telescope/telescope.nvim",
      dependencies = { "nvim-lua/plenary.nvim" },
      cmd = { "Telescope" },
  },

  -- Cscope integration
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

    -- Autocompletion
  { "hrsh7th/nvim-cmp" },
  { "hrsh7th/cmp-nvim-lsp" },
  { "hrsh7th/cmp-buffer" },
  { "hrsh7th/cmp-path" },
  { "L3MON4D3/LuaSnip" },
  { "saadparwaiz1/cmp_luasnip" },

  -- AI Assistants
  { "github/copilot.vim", event = "VeryLazy" },
  {
      "David-Kunz/gen.nvim",
      cmd = { "Gen" },
      opts = {
          model = "mistral",
          host = "localhost",
          port = "11434",
          prompt = "$input",
          quit_map = "q",
          retry_map = "<c-r>",
          accept_map = "<c-cr>",
          display_mode = "float",
          show_prompt = false,
          show_model = false,
          no_auto_close = false,
          init = function() pcall(io.popen, "ollama serve > /dev/null 2>&1 &") end,
          command = function(options)
              local body = {model = options.model, stream = true}
              return "curl --silent --no-buffer -X POST http://" .. options.host .. ":" .. options.port .. "/api/chat -d $body"
          end,
          result_filetype = "markdown",
          debug = false
      },
  },
}

