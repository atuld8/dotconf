;;put this in your emacs

;; reflect .emacs changes without restart or reboot
;; M-x load-file ~/.emacs or .el file
;; M-x eval-buffer
;; C-x C-e  current line
;; M-x eval-region

(setq package-list '( 0blayout 0xc ace-jump-mode anaconda-mode auto-complete-c-headers auto-complete-chunk auto-complete-clang auto-complete-clang-async auto-complete-exuberant-ctags auto-complete buffer-move dired-launch eide avy embrace elscreen expand-region find-file-in-repository fiplr flx-isearch flx flymake-cppcheck flymake-google-cpplint flymake-easy fuzzy ggtags git-blamed git-gutter+ git-gutter google-c-style grizzl helm-cscope helm-fuzzier helm-fuzzy-find helm-git helm-git-grep helm-gitignore gitignore-mode helm-ls-git helm-smex helm-swoop helm helm-core importmagic epc ctable concurrent deferred indent-tools hydra let-alist git-commit material-theme meta-presenter multiple-cursors myterminal-controls neotree popup powerline projectile-codesearch projectile pkg-info epl codesearch py-import-check py-isort py-smart-operator pydoc pydoc-info pyenv-mode highlight-indentation find-file-in-project ivy pyimport pyimpsort python python-docstring pythonic pyvenv request seq shut-up smex solarized-theme switch-window theme-looper vimish-fold f s which-key with-editor dash async xcscope yafolding yasnippet ztree zygospore helm-gtags ws-butler volatile-highlights iedit dtrt-indent counsel-projectile clean-aindent-mode anzu ))

; start package.el with emacs
(require 'package)
; add MELPA to repository list
(add-to-list 'package-archives '("melpa" . "http://melpa.milkbox.net/packages/"))
; initialize package.el
(package-initialize)

; fetch the list of packages available
(unless package-archive-contents
  (package-refresh-contents))

; install the missing packages
(dolist (package package-list)
  (unless (package-installed-p package)
    (package-install package)))



;; power line related functions
(require 'powerline)
(powerline-default-theme)

;making git-gutter mode for showing git status of buffer
(require 'git-gutter)
(global-git-gutter-mode +1)
(git-gutter:linum-setup)
(global-set-key (kbd "C-x C-g") 'git-gutter:toggle)
(global-set-key (kbd "C-x v =") 'git-gutter:popup-hunk)

;; Jump to next/previous hunk
(global-set-key (kbd "C-x p") 'git-gutter:previous-hunk)
(global-set-key (kbd "C-x n") 'git-gutter:next-hunk)

;; Stage current hunk
(global-set-key (kbd "C-x v s") 'git-gutter:stage-hunk)

;; Revert current hunk
(global-set-key (kbd "C-x v r") 'git-gutter:revert-hunk)

;; Mark current hunk
(global-set-key (kbd "C-x v SPC") #'git-gutter:mark-hunk)

;; helm the compressed list
(require 'helm)
(require 'helm-config)

;; The default "C-x c" is quite close to "C-x C-c", which quits Emacs.
;; Changed to "C-c h". Note: We must set "C-c h" globally, because we
;; cannot change `helm-command-prefix-key' once `helm-config' is loaded.
(global-set-key (kbd "C-c h") 'helm-command-prefix)
(global-unset-key (kbd "C-x c"))

(define-key helm-map (kbd "<tab>") 'helm-execute-persistent-action) ; rebind tab to run persistent action
(define-key helm-map (kbd "C-i") 'helm-execute-persistent-action) ; make TAB work in terminal
(define-key helm-map (kbd "C-z")  'helm-select-action) ; list actions using C-z

(when (executable-find "curl")
  (setq helm-google-suggest-use-curl-p t))

(setq helm-split-window-in-side-p           t ; open helm buffer inside current window, not occupy whole other window
      helm-move-to-line-cycle-in-source     t ; move to end or beginning of source when reaching top or bottom of source.
      helm-ff-search-library-in-sexp        t ; search for library in `require' and `declare-function' sexp.
      helm-scroll-amount                    8 ; scroll 8 lines other window using M-<next>/M-<prior>
      helm-ff-file-name-history-use-recentf t)

(helm-mode 1)
(setq helm-semantic-fuzzy-match t
      helm-imenu-fuzzy-match    t)

(define-key helm-map (kbd "<tab>") 'helm-execute-persistent-action)

(global-set-key (kbd "C-x b") 'helm-buffers-list)
(global-set-key (kbd "M-y") 'helm-show-kill-ring)
(global-set-key (kbd "C-x C-f") 'helm-find-files)

(add-to-list 'semantic-default-submodes 'global-semanticdb-minor-mode)
(add-to-list 'semantic-default-submodes 'global-semantic-mru-bookmark-mode)
(add-to-list 'semantic-default-submodes 'global-semantic-idle-scheduler-mode)
(add-to-list 'semantic-default-submodes 'global-semantic-idle-summary-mode)
(add-to-list 'semantic-default-submodes 'global-semantic-stickyfunc-mode)

(semantic-mode 1)

; start auto-complete with emacs
(require 'auto-complete)
; do default config for auto-complete
(require 'auto-complete-config)
(ac-config-default)
; start yasnippet with emacs
(require 'yasnippet)
(yas-global-mode 1)
; let's define a function which initializes auto-complete-c-headers and gets called for c/c++ hooks
(defun my:ac-c-header-init ()
  (require 'auto-complete-c-headers)
  (add-to-list 'ac-sources 'ac-source-c-headers)
  (add-to-list 'achead:include-directories '"/Applications/Xcode.app/Contents/Developer/usr/llvm-gcc-4.2/lib/gcc/i686-apple-darwin11/4.2.1/include")
  )
; now let's call this function from c/c++ hooks
(add-hook 'c++-mode-hook 'my:ac-c-header-init)
(add-hook 'c-mode-hook 'my:ac-c-header-init)

; Fix iedit bug in Mac
(define-key global-map (kbd "C-c ;") 'iedit-mode)

; start flymake-google-cpplint-load
; let's define a function for flymake initialization
(defun my:flymake-google-init ()
  (require 'flymake-google-cpplint)
  (custom-set-variables
   '(flymake-google-cpplint-command "/opt/local/Library/Frameworks/Python.framework/Versions/2.7/bin/cpplint"))
  (flymake-google-cpplint-load)
  )
(add-hook 'c-mode-hook 'my:flymake-google-init)
(add-hook 'c++-mode-hook 'my:flymake-google-init)

; start google-c-style with emacs
(require 'google-c-style)
(add-hook 'c-mode-common-hook 'google-set-c-style)
(add-hook 'c-mode-common-hook 'google-make-newline-indent)

; turn on Semantic
(semantic-mode 1)
; let's define a function which adds semantic as a suggestion backend to auto complete
; and hook this function to c-mode-common-hook
(defun my:add-semantic-to-autocomplete()
  (add-to-list 'ac-sources 'ac-source-semantic)
  )
(add-hook 'c-mode-common-hook 'my:add-semantic-to-autocomplete)
; turn on ede mode
(global-ede-mode 1)

; create a project for our program.
;(ede-cpp-root-project "my project" :file "~/demos/my_program/src/main.cpp"
;		      :include-path '("/../my_inc"))

; you can use system-include-path for setting up the system header file locations.
; turn on automatic reparsing of open buffers in semantic
(global-semantic-idle-scheduler-mode 1)

;start which key mode
(which-key-mode)

;Set hooks for dired-launch-mode
(add-hook 'dired-mode-hook
	  'dired-launch-mode)

;Start undo tree
;(global-undo-tree-mode)


(setq custom-file "~/.vim/emacs-keybindings.el")
(load custom-file)


(global-set-key "\C-cl" 'org-store-link)
(global-set-key "\C-cc" 'org-capture)
(global-set-key "\C-ca" 'org-agenda)
(global-set-key "\C-cb" 'org-iswitchb)
(put 'upcase-region 'disabled nil)

;;(add-to-list 'load-path
;;"~/.emacs.d/plugins")
;;(require 'yasnippet-bundle)
;;(custom-set-variables
;; custom-set-variables was added by Custom.
;; If you edit it by hand, you could mess it up, so be careful.
;; Your init file should contain only one such instance.
;; If there is more than one, they won't work right.
;;'(send-mail-function nil))
;;(custom-set-faces
;; custom-set-faces was added by Custom.
;; If you edit it by hand, you could mess it up, so be careful.
;; Your init file should contain only one such instance.
;; If there is more than one, they won't work right.
;;'(default ((t (:inherit nil :stipple nil :background "White" :foreground "Black" :inverse-video nil :box nil :strike-through nil :overline nil :underline nil :slant normal :weight normal :height 100 :width normal :foundry "nil" :family "Menlo")))))

;;(add-to-list 'load-path "~/.emacs.d/")
;;(require 'auto-complete)
;;(require 'auto-complete-config)
(add-to-list 'ac-dictionary-directories "~/.emacs.d/ac-dict")
(ac-config-default)

;; Enable line number in file ( M-x linum-mode)
(global-linum-mode t)

;; Setting related to yasnippet
(require 'yasnippet)
(yas-global-mode 1)

;; Enable the clipboard
(setq x-select-enable-clipboard t) ;; M-x set-variable RET x-select-enable-clipboard RET t

(put 'scroll-left 'disabled nil)

;; Set C-^ to perform operation like C-u M-^ ( join current line with next line ) 
(defun top-join-line ()
"Join the current line with the line beneath it."
(interactive)
(delete-indentation 1))

(global-set-key (kbd "C-^") 'top-join-line)


;; Enable keybinds for windows movement [S-up/down/right/left]
(windmove-default-keybindings)

;; S-up is not working so fixing this issue
(defadvice terminal-init-xterm (after select-shift-up activate)
(define-key input-decode-map "\e[1;2A" [S-up]))

(if (equal "xterm" (tty-type))
 (define-key input-decode-map "\e[1;2A" [S-up]))

(if (equal "xterm-256color" (tty-type))
 (define-key input-decode-map "\e[1;2A" [S-up]))

(if (equal "screen" (tty-type))
 (define-key input-decode-map "\e[1;2A" [S-up]))

;; buffer switching mode style
;;(iswitchb-mode)

;; specified the buffers which we ignore while selection
;; (add-to-list 'iswitchb-buffer-ignore "^ ")
;; (add-to-list 'iswitchb-buffer-ignore "*Messages*")
;; (add-to-list 'iswitchb-buffer-ignore "*ECB")
;; (add-to-list 'iswitchb-buffer-ignore "*Buffer")
;; (add-to-list 'iswitchb-buffer-ignore "*Completions")
;; (add-to-list 'iswitchb-buffer-ignore "*ftp ")
;; (add-to-list 'iswitchb-buffer-ignore "*bsh")
;; (add-to-list 'iswitchb-buffer-ignore "*jde-log")
;; (add-to-list 'iswitchb-buffer-ignore "^[tT][aA][gG][sS]$")

;; Avoid backup file creation
(setq make-backup-files nil)

;; setup backup file location
;;(setq backup-directory-alist `(("." . "~/.saves")))

;; cscope enabled
(require 'xcscope)

(add-hook 'c-mode-common-hook 'helm-cscope-mode)
(add-hook 'helm-cscope-mode-hook
	  (lambda ()
	    (local-set-key (kbd "M-.") 'helm-cscope-find-global-definition)
	    (local-set-key (kbd "M-@") 'helm-cscope-find-calling-this-funtcion)
	    (local-set-key (kbd "M-s") 'helm-cscope-find-this-symbol)
	                (local-set-key (kbd "M-,") 'helm-cscope-pop-mark)))

(if (or (eq system-type 'windows-nt) (eq system-type 'cygwin) (eq system-type 'ms-dos))
(add-to-list 'default-frame-alist
              '(font . "Fixed613-8"))
(ding)
;;(set-default-font "Menlo")
(add-to-list 'default-frame-alist
              '(font . "Courier-10")))

;;(require 'relative-line-numbers)
;;(set-face-attribute 'relative-line-numbers-current-line nil
;;		    :background "gray30" :foreground "gold")
;;(setq relative-line-numbers-motion-function 'forward-visible-line)
;;(setq relative-line-numbers-format
;;      '(lambda (offset)
;;	          (concat " " (number-to-string (abs offset)) " ")))
;;(global-relative-line-numbers-mode)



(defun relative-abs-line-numbers-format (offset)
    "The default formatting function.
Return the absolute value of OFFSET, converted to string."
    (if (= 0 offset)
	(number-to-string (line-number-at-pos))
      (number-to-string (abs offset))))

(setq relative-line-numbers-format 'relative-abs-line-numbers-format)

;;(eide-start)
(custom-set-variables
 ;; custom-set-variables was added by Custom.
 ;; If you edit it by hand, you could mess it up, so be careful.
 ;; Your init file should contain only one such instance.
 ;; If there is more than one, they won't work right.
 '(custom-safe-themes
   (quote
    ("d677ef584c6dfc0697901a44b885cc18e206f05114c8a3b7fde674fce6180879" "a8245b7cc985a0610d71f9852e9f2767ad1b852c2bdea6f4aadc12cce9c4d6d0" default)))
 '(flymake-google-cpplint-command
   "/opt/local/Library/Frameworks/Python.framework/Versions/2.7/bin/cpplint")
 '(package-selected-packages
   (quote
    (2048-game imenu-list go-autocomplete org-ac org code-library dkdo which-key theme-looper textmate textmate-to-yas tern-auto-complete anaconda-mode importmagic indent-tools py-import-check py-isort py-smart-operator pydoc pydoc-info pyenv-mode pyimport pyimpsort python python-docstring 0xc 0blayout helm-gitignore helm-ls-git egg flymake-google-cpplint ztree yasnippet solarized-theme seq projectile-codesearch let-alist helm-swoop helm-smex helm-git-grep helm-git helm-fuzzy-find helm-fuzzier helm-cscope google-c-style git-gutter git-gutter+ ggtags fuzzy flymake-cppcheck flx-isearch fiplr find-file-in-repository eide auto-complete-exuberant-ctags auto-complete-clang-async auto-complete-clang auto-complete-chunk auto-complete-c-headers ace-jump-mode ac-etags ac-emacs-eclim ac-c-header))))

;;(custom-set-faces
 ;; custom-set-faces was added by Custom.
 ;; If you edit it by hand, you could mess it up, so be careful.
 ;; Your init file should contain only one such instance.
 ;; If there is more than one, they won't work right.
 ;;'(default ((t (:inherit nil :stipple nil :background "White" :foreground "Black" :inverse-video nil :box nil :strike-through nil :overline nil :underline nil :slant normal :weight normal :height 120 :width condensed :foundry "nil" :family "Courier")))))

;; Enable multiple cursor
(require 'multiple-cursors)

;; Open help file quickly
(global-set-key (kbd "<f5>") (lambda() (interactive)(find-file "/work/Tools/emacs.txt")))

;;

(put 'narrow-to-page 'disabled nil)
(put 'narrow-to-region 'disabled nil)


;; set c-x 1 to toggle the deletion 
(global-set-key (kbd "C-x 1") 'zygospore-toggle-delete-other-windows)


;;(require 'setup-helm-gtags)
;;(require 'setup-ggtags)
;;(require 'setup-general)
;;(require 'setup-cedet)
;;(require 'setup-editing)

;;(setq load-path (cons "/usr/local/Cellar/global/6.5.6/bin/" load-path))
;;(setq load-path (cons "/usr/local/Cellar/global/6.5.6/bin/" load-path))
;;(setq load-path (cons "/Users/atul.das1/.vim/gtags.el" load-path))
;;(require 'ggtags)
;;(autoload 'gtags-mode "gtags" "" t)

(add-to-list 'load-path "~/.emacs.d/custom")

(setq c-mode-hook
'(lambda ()
(gtags-mode 1)))
(setq c++-mode-hook
'(lambda ()
(gtags-mode 1)))

