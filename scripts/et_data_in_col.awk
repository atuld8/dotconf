BEGIN {
    Columns=split(cols,out,",")

    ColumnWidth["ABSTRACT"]=60
    ColumnWidth["CATEGORY"]=20
    ColumnWidth["CHANGED_BY"]=20
    ColumnWidth["COMPONENT"]=30
    ColumnWidth["DATE_CLOSED"]=11
    ColumnWidth["DATE_FIXED"]=11
    ColumnWidth["DATE_OPENED"]=14
    ColumnWidth["DEFAULT"]=12
    ColumnWidth["INCIDENT"]=8
    ColumnWidth["KEYWORD"]=20
    ColumnWidth["LAST_CHANGED"]=11
    ColumnWidth["PLATFORM"]=13
    ColumnWidth["PRIORITY"]=3
    ColumnWidth["PRODUCT"]=10
    ColumnWidth["PROGRESS_STATUS"]=40
    ColumnWidth["REPORTER"]=20
    ColumnWidth["SEVERITY"]=3
    ColumnWidth["STATE"]=10
    ColumnWidth["SUBSCRIBE"]=40
    ColumnWidth["TYPE"]=17
    ColumnWidth["TARGET_BUILD"]=13
    ColumnWidth["TARGET_VERSION"]=10
    ColumnWidth["USER_DEFINED"]=20
    ColumnWidth["USER_DEFINED2"]=30
    ColumnWidth["VERSION"]=8
}

function print_seperator(width) {
    for(i=0;i<=width;i++)
        printf("-");
    printf("\n");
}

NR==1 {

    if ( cols == "*") {
        for (i=1; i<=NF; i++)
          out[i] = $i
        Columns = NF
    }

    for (i=1; i<=NF; i++)
        ix[$i] = i

    TotalWidth=0
    for (i in out) {
        if ( ColumnWidth[out[i]] == "" )
            ColumnWidth[out[i]] = ColumnWidth["DEFAULT"]

        TotalWidth = TotalWidth + ColumnWidth[out[i]] + 3
    }

    print_seperator(TotalWidth)

    printf "|"
    for (i=1; i <= Columns; i++)
        printf " %-*s%s|", ColumnWidth[out[i]], substr($ix[out[i]],1,ColumnWidth[out[i]]), OFS
    print ""
    print_seperator(TotalWidth)
}
NR>1 {
    printf "|"
    for (i=1; i <= Columns; i++)
        printf " %-*s%s|", ColumnWidth[out[i]], substr($ix[out[i]],1,ColumnWidth[out[i]]), OFS
    print ""
}



END {
    print_seperator(TotalWidth)
    printf "\nTotal number of records: %d\n", (NR-1)
}


# Example to use this
#/usr/local/bin/eq ESC_TRP_Closed | grep -v "^Query:" | sed '/^s*$/d' | awk -F "\t" -f ~/scripts/et_data_in_col.awk -v cols=INCIDENT,STATE

#/usr/local/bin/eq ETs_with_ESC_NEED_SPT_ACT | grep -v "^Query:" | sed '/^s*$/d' | awk -F "\t" -f ~/scripts/et_data_in_col.awk -v cols=INCIDENT,STATE | /home/atuld/scripts/html/aha-master/aha |  /home/atuld/scripts/sendmail_html.pl -s "ETs_with_ESC_NEED_SPT_ACT query output" -t email.id

#eq queryname | grep -e "^INCIDENT\|^[0-9]\{7\}"

