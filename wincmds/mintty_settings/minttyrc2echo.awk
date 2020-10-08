# Run awk -f minttyrc2echo.awk minttyrc.darktheme
# This will not effect when we are running the script from the tmux
BEGIN {

    FS="="

    ColorNameToEchoTag["Black"]="\\e]4;0;"
    ColorNameToEchoTag["Red"]="\\e]4;1;"
    ColorNameToEchoTag["Green"]="\\e]4;2;"
    ColorNameToEchoTag["Yellow"]="\\e]4;3;"
    ColorNameToEchoTag["Blue"]="\\e]4;4;"
    ColorNameToEchoTag["Manenta"]="\\e]4;5;"
    ColorNameToEchoTag["Cyan"]="\\e]4;6;"
    ColorNameToEchoTag["White"]="\\e]4;7;"
    ColorNameToEchoTag["BoldBlack"]="\\e]4;8;"
    ColorNameToEchoTag["BoldRed"]="\\e]4;9;"
    ColorNameToEchoTag["BoldGreen"]="\\e]4;10;"
    ColorNameToEchoTag["BoldYellow"]="\\e]4;11;"
    ColorNameToEchoTag["BoldBlue"]="\\e]4;12;"
    ColorNameToEchoTag["BoldMagenta"]="\\e]4;13;"
    ColorNameToEchoTag["BoldCyan"]="\\e]4;14;"
    ColorNameToEchoTag["BoldWhite"]="\\e]4;15;"
    ColorNameToEchoTag["ForegroundColour"]="\\e]10;"
    ColorNameToEchoTag["BackgroundColour"]="\\e]11;"
    ColorNameToEchoTag["CursorColour"]="\\e]12;"
    ColorNameToEchoTag["End"]="\\a"
 }

{
    ColorName=$1
    ColorValue=$2
    if ( ColorNameToEchoTag[ColorName] != "" )
        printf ("echo -ne '%s%s%s'\n",ColorNameToEchoTag[ColorName],ColorValue, ColorNameToEchoTag["End"])
}

END {
}
