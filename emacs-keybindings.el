;;;; global


(global-set-key [f1] 'magit-status)
(global-set-key [f6] 'my-clear-all-caches)
(global-set-key [escape] 'keyboard-quit)
(global-set-key (kbd "M-a") 'mark-whole-buffer)
(global-set-key (kbd "C-\\") 'highlight-symbol-at-point)
(global-set-key (kbd "<M-up>") 'er/expand-region) ;
(global-set-key (kbd "<M-down>") 'er/contract-region)
(global-set-key (kbd "C-<backspace>") 'my-delete-backwards)
(global-set-key (kbd "RET") 'newline-and-indent)
;;(global-set-key (kbd "M-]") 'textmate-shift-right)
;;(global-set-key (kbd "M-[") 'textmate-shift-left)
(global-set-key (kbd "M-j") 'other-window)
(global-set-key (kbd "M-k") 'yas-expand-from-trigger-key)
(global-set-key (kbd "M-.") 'my-find-tag)
(global-set-key (kbd "M-b") 'ibuffer)
(global-set-key (kbd "M-RET") 'newline-anywhere)
(global-set-key (kbd "M-S-RET") 'newline-on-previous-line-anywhere)

(global-set-key (kbd "M-s") 'save-buffer)
(global-set-key (kbd "M-w") 'quit-window)
(global-set-key (kbd "M-W") 'projectile-kill-buffers)

;;; iedit

;; (global-set-key (kbd "M-L") 'iedit-mode)
;; (global-set-key (kbd "M-l") 'iedit-dwim)

;;; cursors

(global-set-key (kbd "M-L") 'skip-current-mark-and-mark-next)
(global-set-key (kbd "M-l") 'mc/mark-next-like-this)
;;; drop some keymaps

(require 'auto-complete)
;;(define-key *textmate-mode-map* [(meta return)] nil)
;;(define-key *textmate-mode-map* [(meta up)] nil)
;;(define-key *textmate-mode-map* [(meta down)] nil)
;;(define-key org-mode-map [(meta return)] nil)
(define-key ac-completing-map "\r" nil)
(define-key ac-completing-map [return] nil)
;;(define-key ruby-mode-map "{" nil)
;;(define-key ruby-mode-map "}" nil)
(define-key compilation-mode-map "g" nil)
(define-key compilation-mode-map "G" nil)


;;; esc quits

(define-key minibuffer-local-map [escape] 'minibuffer-keyboard-quit)
(define-key minibuffer-local-ns-map [escape] 'minibuffer-keyboard-quit)
(define-key minibuffer-local-completion-map [escape] 'minibuffer-keyboard-quit)
(define-key minibuffer-local-must-match-map [escape] 'minibuffer-keyboard-quit)
(define-key minibuffer-local-isearch-map [escape] 'minibuffer-keyboard-quit)

;;; helm

;; (define-key helm-map (kbd "M-n") 'helm-next-line)
;; (define-key helm-map (kbd "M-p") 'helm-previous-line)

;;; deft

;(define-key deft-mode-map (kbd "M-n") 'next-line)
;(define-key deft-mode-map (kbd "M-p") 'previous-line)
;(define-key deft-mode-map (kbd "M-k") 'deft-delete-file)
;(define-key deft-mode-map (kbd "M-r") 'deft-rename-file)

;;; javascript

;; isearch

(global-set-key (kbd "M-f") 'isearch-forward)
(global-set-key (kbd "M-r") 'isearch-backward)
(define-key isearch-mode-map [escape] 'isearch-cancel)
(define-key isearch-mode-map (kbd "M-f") 'isearch-repeat-forward)
(define-key isearch-mode-map (kbd "M-r") 'isearch-repeat-backward)

;;; comint

(defun kill-comint ()
  (interactive)
  (comint-interrupt-subjob)
  (popwin:close-popup-window))


;;; magit

;;; zencoding

;;(define-key zencoding-mode-keymap (kbd "M-e") 'zencoding-expand-line)

;;; ruby

;;; org

;; ;;; fuzzy find

;; (fuzzy-find-initialize)
;; (define-key fuzzy-find-keymap "\M-n" 'fuzzy-find-next-completion)
;; (define-key fuzzy-find-keymap "\M-p" 'fuzzy-find-previous-completion)

;;; Magit


;;; Stuff I had some trouble defining normally

(add-hook 'ido-minibuffer-setup-hook
          (lambda ()
            (define-key ido-completion-map (kbd "M-n") 'ido-next-match)
            (define-key ido-completion-map (kbd "C-n") 'ido-next-match)
            (define-key ido-completion-map (kbd "M-p") 'ido-prev-match)
            (define-key ido-completion-map (kbd "C-p") 'ido-prev-match)))

(add-hook 'ruby-mode-hook
          (lambda ()
            (local-set-key (kbd "RET") 'newline-and-indent)))

(add-hook 'change-major-mode-hook
          (lambda ()
            (global-set-key (kbd "C-/") 'comment-or-uncomment-region-or-line)))


(add-hook 'dired-mode-hook (lambda ()
  (define-key dired-mode-map "U" 'dired-up-directory)
  (define-key dired-mode-map "/" 'dired-isearch-filenames)))

(add-hook 'railway-minor-mode-hook 'evil-normalize-keymaps)

(provide 'emacs-keybings)
(custom-set-variables
 ;; custom-set-variables was added by Custom.
 ;; If you edit it by hand, you could mess it up, so be careful.
 ;; Your init file should contain only one such instance.
 ;; If there is more than one, they won't work right.
 '(ansi-color-names-vector
   ["#212526" "#ff4b4b" "#b4fa70" "#fce94f" "#729fcf" "#e090d7" "#8cc4ff" "#eeeeec"])
 '(custom-enabled-themes (quote (tango-dark)))
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
 ;; '(default ((t (:inherit nil :stipple nil :background "White" :foreground "Black" :inverse-video nil :box nil :strike-through nil :overline nil :underline nil :slant normal :weight normal :height 120 :width condensed :foundry "nil" :family "Courier")))))
(custom-set-faces
 ;; custom-set-faces was added by Custom.
 ;; If you edit it by hand, you could mess it up, so be careful.
 ;; Your init file should contain only one such instance.
 ;; If there is more than one, they won't work right.
 '(default ((t (:family "fixed613" :foundry "raster" :slant normal :weight normal :height 98 :width normal)))))
