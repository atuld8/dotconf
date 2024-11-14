#!/bin/sh
set -x

export ROOT_SRC=$PWD;
export ROOT_NAME=${1:-src}


while [ "`basename $ROOT_SRC`" != "$ROOT_NAME" ] ;
do
   ROOT_SRC=`dirname $ROOT_SRC`;
   if [ "$ROOT_SRC" == "/" ]; 
   then
      break;
   fi;
done;

if [ "`basename $ROOT_SRC`" == "$ROOT_NAME" ] ; then
   export VTAG_PATH=$ROOT_SRC"/vtags";
   export CSCOPE_PATH=$ROOT_SRC;
else
    echo "execute this command from $ROOT_NAME"
    exit 1
fi

echo "" > ${CSCOPE_PATH}/cscope.files

find $CSCOPE_PATH -iname "*.c" -o -iname "*.cpp" -o -iname "*.h" -o -iname "*.hpp" > ${CSCOPE_PATH}/cscope.files 2>/dev/null

find $CSCOPE_PATH -name "*.c" -o -name "*.cpp" -o -name "*.h" -o -name "*.hpp" >> ${CSCOPE_PATH}/cscope.files 2>/dev/null

awk '{ print "\""$0"\""; }' ${CSCOPE_PATH}/cscope.files > ${CSCOPE_PATH}/cscope.files.tmp

mv ${CSCOPE_PATH}/cscope.files.tmp ${CSCOPE_PATH}/cscope.files

sort -u -o ${CSCOPE_PATH}/cscope.files ${CSCOPE_PATH}/cscope.files

CSCOPE_CMD='cscope'
if [ -f /usr/bin/cscope ]; then
    CSCOPE_CMD='/usr/bin/cscope'
fi
$CSCOPE_CMD -q -R -b -v -C -i ${CSCOPE_PATH}/cscope.files -f ${CSCOPE_PATH}/cscope.out &

#ctags -R -a -f $VTAG_PATH --c++-kinds=+p --fields=+iaS --extra=+q -L ${CSCOPE_PATH}/cscope.files
cd $CSCOPE_PATH
ctags -R -a -f $VTAG_PATH --c++-kinds=+p --fields=+iaS --extra=+q .

wait
