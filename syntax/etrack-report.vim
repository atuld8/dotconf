" Syntax: eTrack hierarchy / deliverable report output
" Used by etrack_hierarchy_table.py, esql_formatter.py, etc.

if exists("b:current_syntax")
  finish
endif

syn match EtrackDelimiter     /^=\+$/
syn match EtrackDelimiter     /^[-+]\{3,}[-+|]\{3,}[-+]\{3,}$/
syn match EtrackReportTitle   /^EEB \(PACKAGE\|BUNDLE\|STANDARD EEB\) REPORT.*$/
syn match EtrackReportTitle   /^DELIVERABLE SUMMARY.*$/
syn match EtrackCommentMeta   /^Comment #\d\+ @ .*$/
syn match EtrackSection       /^\(SUMMARY:\|LINKS:\|HIERARCHY TREE:\|VERSION SUMMARY:\)$/
syn match EtrackSection       /^\(SR SHIPPING SUMMARY:\|ARTIFACTS SUMMARY:\|PLATFORM PACKAGES SUMMARY:\)$/
syn match EtrackSection       /^SR DETAILS (\|^SR SHIPPING (\|^PLATFORM PACKAGES (\|^ARTIFACTS (\|^SR SHIPPING DETAILS (\|^ARTIFACTS (\|^PLATFORM PACKAGES (\|^Total rows: \d\+/
syn match EtrackHint          /^(Full listing: .*; use --full-deliverable-details to show all)$/

syn match EtrackTableBorder   /^[+|][-+|]\+[+|]$/
syn match EtrackTableHeader   /^| .* |$/
syn match EtrackTableRow      /^| [^|]\+ |$/

syn match EtrackTreeLine      /^  \++-- /

syn match EtrackStatus        /\<\(CURRENT\|STALE\|UNKNOWN\|NEWER\)\>/
syn match EtrackStatus        /\<\(CLOSED\|REOPEN\|WORKING\|OPEN\)\>/
syn match EtrackStatus        /\<\(SOURCE_CHANGE\|FIXED\|DUPLICATE\)\>/

syn match EtrackKind          /\<\(EEB PACKAGE\|EEB BUNDLE\|STANDARD EEB\|SERVICE_REQUEST\|DEFECT\)\>/
syn match EtrackSource        /\<\(BUNDLE\|PKG\|README\*\)\>/

syn match EtrackET            /\<\(ET\|PKG\|BUNDLE\)\/\?\d\{6,8\}\>/
syn match EtrackET            /\<ET \d\{6,8\}\>/
syn match EtrackET            /| \d\{6,8\} \+| | \d\{6,8\}    |/

syn match EtrackPlatform      /\<\(AMD64\|linuxR_x86\|linuxS_x86\|all (3)\|linux×2\)\>/
syn match EtrackArtifactType  /\<\(eebinstaller\|install-script\|primary-set\|rpm\|index\|war\|jar\|exe\|other\)\(×\d\+\)\?\>/

syn match EtrackURL           /https\?:\/\/\S\+/

hi def link EtrackDelimiter     Delimiter
hi def link EtrackReportTitle   Title
hi def link EtrackCommentMeta   Comment
hi def link EtrackSection       Statement
hi def link EtrackHint          Comment
hi def link EtrackTableBorder   NonText
hi def link EtrackTableHeader   Identifier
hi def link EtrackTableRow      Normal
hi def link EtrackTreeLine      Structure
hi def link EtrackStatus        Special
hi def link EtrackKind          Type
hi def link EtrackSource        Tag
hi def link EtrackET            Number
hi def link EtrackPlatform      Constant
hi def link EtrackArtifactType  String
hi def link EtrackURL           Underlined

let b:current_syntax = "etrack-report"
