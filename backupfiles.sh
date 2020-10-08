#!/bin/bash
for f in `git ls-tree -r master --name-only | grep -v "bundle/" | grep -v "autoload/" | grep -v "emacs.d/" | grep -v "doc/" `;
do
    echo "cheking for $f and ~/Dropbox/github/dotconfig/$f file..."
    if [ -f ~/Dropbox/github/dotconfig/$f ]; then
      diff -w --strip-trailing-cr $f ~/Dropbox/github/dotconfig/$f > /dev/null 2>&1
      if [ $? -ne 0 ]
      then
          echo Diff in: $f ~/Dropbox/github/dotconfig/$f
          vim -d -n -c "colorscheme torte | windo set wrap" -f $f ~/Dropbox/github/dotconfig/$f
      else
         echo In sync: $f ~/Dropbox/github/dotconfig/$f
      fi
    else
        base_dirname=`dirname $f`;
        if [ ! -d ~/Dropbox/github/dotconfig/$base_dirname ]; then
           mkdir -p ~/Dropbox/github/dotconfig/$base_dirname
        fi
        cp $f ~/Dropbox/github/dotconfig/$f;
    fi
done
