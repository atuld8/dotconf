-- lua/plugins/init.lua

return {
  -- Plugin manager can manage itself
  { "folke/lazy.nvim" },

  -- UI
  { "vim-airline/vim-airline" },
  { "altercation/vim-colors-solarized" },
  { "flazz/vim-colorschemes" },

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
  { "w0rp/ale" },

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
  { "junegunn/vim-easy-align" },

  -- Markdown
  { "gabrielelana/vim-markdown" },
  { "shime/vim-livedown" },

  -- Misc
  { "tpope/vim-eunuch" },
  { "tyru/transbuffer.vim" },
  { "xolox/vim-session" },
  { "ntpeters/vim-better-whitespace" },
  { "christoomey/vim-tmux-navigator" },
  { "MattesGroeger/vim-bookmarks" },
  { "andrewradev/linediff.vim" },
}

