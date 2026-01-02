return {
  "VundleVim/Vundle.vim",
  "tpope/vim-fugitive",
  "vim-scripts/perl-support.vim",
  "vim-scripts/ZoomWin",
  { "ascenator/L9", name = "L9", lazy = true, },
  {
      "nvim-telescope/telescope.nvim",
      dependencies = { "nvim-lua/plenary.nvim" },
      cmd = { "Telescope" },
      opts = {},
  },

  "vim-scripts/TaskList.vim",
  "sjl/gundo.vim",
  "ervandew/supertab",
  "MattesGroeger/vim-bookmarks",
  "derekwyatt/vim-protodef",
  "mileszs/ack.vim",
  "haya14busa/incsearch.vim",
  "majutsushi/tagbar",
  "vim-scripts/AutoComplPop",
  "vim-scripts/mru.vim",
  "kshenoy/vim-signature",
  "scrooloose/nerdtree",
  "Xuyuanp/nerdtree-git-plugin",
  "tpope/vim-surround",
  "vim-scripts/BufOnly.vim",
  "Lokaltog/vim-powerline",
  "wincent/command-t",
  "vim-scripts/Conque-Shell",
  "kien/ctrlp.vim",
  "Shougo/neocomplcache.vim",
  "vim-scripts/taglist.vim",
  "vim-scripts/Word-Fuzzy-Completion",
  "tpope/vim-pathogen",
  "easymotion/vim-easymotion",
  "xolox/vim-misc",
  "vim-airline/vim-airline",
  "ntpeters/vim-better-whitespace",
  "jez/vim-superman",
  "vim-utils/vim-man",
  "christoomey/vim-tmux-navigator",
  "vim-scripts/a.vim",
  "airblade/vim-gitgutter",
  "elzr/vim-json",
  "othree/html5.vim",
  "godlygeek/tabular",
  "junegunn/vim-easy-align",
  "scrooloose/nerdcommenter",
  "tomtom/tcomment_vim",
  "mbbill/undotree",
  "vim-scripts/YankRing.vim",
  "terryma/vim-multiple-cursors",
  "adinapoli/vim-markmultiple",
  "michaeljsmith/vim-indent-object",
  "gabrielelana/vim-markdown",
  "shime/vim-livedown",
  "vim-scripts/c.vim",
  "Shougo/neocomplete.vim",
  "tpope/vim-eunuch",
  "gregsexton/gitv",
  "mhinz/vim-signify",
  "dhruvasagar/vim-table-mode",
  {
  "xolox/vim-misc",
  lazy = true,
  },
  { "xolox/vim-notes",
   dependencies = { "xolox/vim-misc" },
  },
  "derekwyatt/vim-fswitch",
  "othree/xml.vim",
  "mtth/scratch.vim",
  "Shougo/unite.vim",
  "shougo/vimfiler.vim",
  "andrewradev/linediff.vim",
  "vitalk/vim-simple-todo",
  "tyru/transbuffer.vim",
  "vim-scripts/Lynx-Offline-Documentation-Browser",
  "vim-scripts/bufexplorer.zip",
  "rking/ag.vim",
  "motemen/git-vim",
  "taq/vim-git-branch-info",
  "int3/vim-extradite",
  "junegunn/gv.vim",
  "vim-scripts/git-log",
  "aquach/vim-http-client",
  "chrisbra/vim-diff-enhanced",
  "joonty/vim-do",
  "davidhalter/jedi-vim",
  "junegunn/fzf.vim",
  "mattn/emmet-vim",
  "tibabit/vim-templates",
  "lacombar/vim-mpage",
  "will133/vim-dirdiff",
  "LucHermitte/lh-vim-lib",
  "LucHermitte/lh-vim-lib",
  --{ "LucHermitte/local_vimrc",
  -- dependencies = { "LucHermitte/lh-vim-lib" },
  --},
  "prettier/vim-prettier",
  "bogado/file-line",
  "tpope/vim-abolish",
  "AndrewRadev/tagalong.vim",
  "wavded/vim-stylus",
  "skammer/vim-css-color",
  "digitaltoad/vim-pug",
  "adelarsq/vim-matchit",
  "jelera/vim-javascript-syntax",
  "pangloss/vim-javascript",
  "vim-pandoc/vim-pandoc",
  "thinca/vim-prettyprint",
  "maksimr/vim-jsbeautify",
  {
      "David-Kunz/gen.nvim",
      opts = {
          model = "mistral", -- The default model to use.
          host = "localhost", -- The host running the Ollama service.
          port = "11434", -- The port on which the Ollama service is listening.
          input = function()
              local start_line = vim.fn.getpos("'<")[2] - 1
              local end_line = vim.fn.getpos("'>")[2]

              if start_line >= 0 and end_line >= start_line then
                  local lines = vim.api.nvim_buf_get_lines(0, start_line, end_line, false)
                  if #lines > 0 then
                      return table.concat(lines, "\n")
                  end
              end

              return table.concat(
                  vim.api.nvim_buf_get_lines(0, 0, -1, false),
                  "\n"
              )
          end,
          quit_map = "q", -- set keymap to close the response window
          retry_map = "<c-r>", -- set keymap to re-send the current prompt
          accept_map = "<c-cr>", -- set keymap to replace the previous selection with the last result
          display_mode = "float", -- The display mode. Can be "float" or "split" or "horizontal-split" or "vertical-split".
          show_prompt = false, -- Shows the prompt submitted to Ollama. Can be true (3 lines) or "full".
          show_model = false, -- Displays which model you are using at the beginning of your chat session.
          no_auto_close = false, -- Never closes the window automatically.
          file = false, -- Write the payload to a temporary file to keep the command short.
          hidden = false, -- Hide the generation window (if true, will implicitly set `prompt.replace = true`), requires Neovim >= 0.10
          init = function(options) pcall(io.popen, "ollama serve > /dev/null 2>&1 &") end,
          -- Function to initialize Ollama
          command = function(options)
              local body = {model = options.model, stream = true}
              return "curl --silent --no-buffer -X POST http://" .. options.host .. ":" .. options.port .. "/api/chat -d $body"
          end,
          -- The command for the Ollama service. You can use placeholders $prompt, $model and $body (shellescaped).
          -- This can also be a command string.
          -- The executed command must return a JSON object with { response, context }
          -- (context property is optional).
          -- list_models = '<omitted lua function>', -- Retrieves a list of model names
          result_filetype = "markdown", -- Configure filetype of the result buffer
          debug = false -- Prints errors and the command which is run.
      }
  }
}
