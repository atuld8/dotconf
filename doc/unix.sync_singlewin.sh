#!/bin/bash
if [ ! -f $1/VI\ shortcuts\ info.txt ]; then
    echo "correct path not mentioned."
    exit 0
fi

diff -b <(vim -Nesc 'let &key=$VIMPASS | e ~/.vim/doc/vi.shortcuts.info_enc.txt | %p | q!') <(cat $1/VI\ shortcuts\ info.txt)
if [ $? -ne 0 ]; then
    vimdiff -n --cmd "let &key=\$VIMPASS" ~/.vim/doc/vi.shortcuts.info_enc.txt $1/VI\ shortcuts\ info.txt
fi

diff -b <(vim -Nesc 'let &key=$VIMPASS | e ~/.vim/doc/Bash.KB.shrtcuts.txt | %p | q!') <(cat $1/Bash\ KB\ shrtcuts.txt )
if [ $? -ne 0 ]; then
    vimdiff -n --cmd "let &key=\$VIMPASS" ~/.vim/doc/Bash.KB.shrtcuts.txt $1/Bash\ KB\ shrtcuts.txt
fi

diff -b <(vim -Nesc 'let &key=$VIMPASS | e ~/.vim/doc/CmdScriptsCollection.txt | %p | q!') <(cat $1/CmdScriptsCollection.txt )
if [ $? -ne 0 ]; then
    vimdiff -n --cmd "let &key=\$VIMPASS" ~/.vim/doc/CmdScriptsCollection.txt $1/CmdScriptsCollection.txt
fi

diff -b <(vim -Nesc 'let &key=$VIMPASS | e ~/.vim/doc/MAC.notes.txt | %p | q!') <(cat $1/MAC\ notes.txt )
if [ $? -ne 0 ]; then
    vimdiff -n --cmd "let &key=\$VIMPASS" ~/.vim/doc/MAC.notes.txt $1/MAC\ notes.txt
fi

diff -b <(vim -Nesc 'let &key=$VIMPASS | e ~/.vim/doc/NanoKeyShortcuts.txt | %p | q!') <(cat $1/NanoKeyShortcuts.txt )
if [ $? -ne 0 ]; then
    vimdiff -n --cmd "let &key=\$VIMPASS" ~/.vim/doc/NanoKeyShortcuts.txt $1/NanoKeyShortcuts.txt
fi

diff -b <(vim -Nesc 'let &key=$VIMPASS | e ~/.vim/doc/Tmux.txt | %p | q!') <(cat $1/Tmux.txt )
if [ $? -ne 0 ]; then
    vimdiff -n --cmd "let &key=\$VIMPASS" ~/.vim/doc/Tmux.txt $1/Tmux.txt
fi

diff -b <(vim -Nesc 'let &key=$VIMPASS | e ~/.vim/doc/UnixInGeneral.txt | %p | q!') <(cat $1/UnixInGeneral.txt )
if [ $? -ne 0 ]; then
    vimdiff -n --cmd "let &key=\$VIMPASS" ~/.vim/doc/UnixInGeneral.txt $1/UnixInGeneral.txt
fi

diff -b <(vim -Nesc 'let &key=$VIMPASS | e ~/.vim/doc/WindowsInGeneral.txt | %p | q!') <(cat $1/WindowsInGeneral.txt )
if [ $? -ne 0 ]; then
    vimdiff -n --cmd "let &key=\$VIMPASS" ~/.vim/doc/WindowsInGeneral.txt $1/WindowsInGeneral.txt
fi

diff -b <(vim -Nesc 'let &key=$VIMPASS | e ~/.vim/doc/android_mobile_app_noets.txt | %p | q!') <(cat $1/android_mobile_app_noets.txt )
if [ $? -ne 0 ]; then
    vimdiff -n --cmd "let &key=\$VIMPASS" ~/.vim/doc/android_mobile_app_noets.txt $1/android_mobile_app_noets.txt
fi

diff -b <(vim -Nesc 'let &key=$VIMPASS | e ~/.vim/doc/ctag-cscope.txt | %p | q!') <(cat $1/ctag-cscope.txt )
if [ $? -ne 0 ]; then
    vimdiff -n --cmd "let &key=\$VIMPASS" ~/.vim/doc/ctag-cscope.txt $1/ctag-cscope.txt
fi

diff -b <(vim -Nesc 'let &key=$VIMPASS | e ~/.vim/doc/eclipse_notes.txt | %p | q!') <(cat $1/eclipse_notes.txt )
if [ $? -ne 0 ]; then
    vimdiff -n --cmd "let &key=\$VIMPASS" ~/.vim/doc/eclipse_notes.txt $1/eclipse_notes.txt
fi

diff -b <(vim -Nesc 'let &key=$VIMPASS | e ~/.vim/doc/screen.txt | %p | q!') <(cat $1/screen.txt )
if [ $? -ne 0 ]; then
    vimdiff -n --cmd "let &key=\$VIMPASS" ~/.vim/doc/screen.txt $1/screen.txt
fi

diff -b <(vim -Nesc 'let &key=$VIMPASS | e ~/.vim/doc/screenrc.txt | %p | q!') <(cat $1/screenrc.txt )
if [ $? -ne 0 ]; then
    vimdiff -n --cmd "let &key=\$VIMPASS" ~/.vim/doc/screenrc.txt $1/screenrc.txt
fi

diff -b <(vim -Nesc 'let &key=$VIMPASS | e ~/.vim/doc/LearningNotes.txt | %p | q!') <(cat $1/LearningNotes.txt )
if [ $? -ne 0 ]; then
    vimdiff -n --cmd "let &key=\$VIMPASS" ~/.vim/doc/LearningNotes.txt $1/LearningNotes.txt
fi
