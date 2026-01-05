Option Explicit

' Function to make a request to the Jira API using Personal Access Token (Mac Excel compatible)
Function JiraRequest(jiraID As String, token As String) As String
    Dim URL As String
    Dim command As String
    Dim responseText As String

    ' Set the Jira API URL (modify as needed)
    URL = "https://jira.company.com/rest/api/2/issue/" & jiraID

    ' Construct the curl command with authorization header
    command = "curl -s -H 'Authorization: Bearer " & token & "' " & URL

    ' Execute the curl command and capture the response using MacScript
    responseText = MacScript("do shell script """ & command & """")

    ' Return API response
    JiraRequest = responseText
End Function

' Function to make a request to the Jira API using Personal Access Token (Mac Excel compatible)
Function JiraUrlRequest(jiraUrl As String, token As String) As String
    Dim URL As String
    Dim command As String
    Dim responseText As String

    ' Construct the curl command with authorization header
    command = "curl -s -H 'Authorization: Bearer " & token & "' " & jiraUrl

    ' Execute the curl command and capture the response using MacScript
    responseText = MacScript("do shell script """ & command & """")

    ' Return API response
    JiraUrlRequest = responseText
End Function


' Function to extract JSON values without using ActiveX (compatible with Mac)
Function ExtractJSONValue(json As String, key As String) As String
    Dim keyPos As Long
    Dim valuePos As Long
    Dim valueEnd As Long
    Dim keyLength As Long
    Dim tempValue As String

    keyLength = Len(key)
    keyPos = InStrRev(json, """" & key & """")

    If keyPos > 0 Then
        valuePos = InStr(keyPos + keyLength, json, ":") + 1
        tempValue = Mid(json, valuePos)

        ' Determine if the value is a string or a number
        If Mid(tempValue, 1, 1) = """" Then
            valuePos = InStr(1, tempValue, """") + 1
            valueEnd = InStr(valuePos + 1, tempValue, """")
            ExtractJSONValue = Mid(tempValue, valuePos, valueEnd - valuePos)
        Else
            valueEnd = InStr(1, tempValue, ",")
            If valueEnd = 0 Then
                valueEnd = InStr(1, tempValue, "}")
            End If
            ExtractJSONValue = Trim(Mid(tempValue, 1, valueEnd - 1))
        End If
    Else
        ExtractJSONValue = ""
    End If
End Function



' Function to make a request to the Jira API using Personal Access Token (Mac Excel compatible)
Function JiraRequestForField(apiEndpoint As String, token As String) As String
    Dim command As String
    Dim response As String

    ' Construct the curl command with authorization header
    command = "curl -s -H 'Authorization: Bearer " & token & "' 'https://jira.company.com/rest/api/2/" & apiEndpoint & "'"

    ' Execute the curl command and capture the response
    response = MacScript("do shell script """ & command & """")

    ' Return the API response
    JiraRequestForField = response
End Function


' Function to find the custom field ID by display name
Function GetCustomFieldIDByDisplayName(displayName As String, token As String) As String
    Dim fieldsResponse As String
    Dim fields() As String
    Dim i As Integer
    Dim fieldID As String

    ' Get the fields metadata from Jira
    fieldsResponse = JiraRequestForField("field", token)

    ' Testing purpose
    'ActiveSheet.Cells(42, 1).Value = fieldsResponse

    ' Split the JSON response by field entries
    fields = Split(fieldsResponse, "},")

    GetCustomFieldIDByDisplayName = ""

    ' Loop through each field to find the matching display name
    For i = LBound(fields) To UBound(fields)
        If InStr(fields(i), """" & displayName & """") > 0 Then
            fieldID = ExtractJSONValueForField(fields(i), "id")
            If fieldID <> "" Then
                GetCustomFieldIDByDisplayName = fieldID
                'Exit Function
            End If
        End If
    Next i

    ' If no match found
    'GetCustomFieldIDByDisplayName = ""
End Function


Sub TestGetCustomFieldIDByDisplayName()
    Dim token As String
    Dim displayName As String
    Dim fieldID As String

    ' Prompt user for Personal Access Token
    token = InputBox("Please enter your Jira Personal Access Token:", "Jira PAT")

    ' Set the display name of the custom field
    displayName = "Summary" ' Change this to the actual display name

    ' Get the custom field ID
    fieldID = GetCustomFieldIDByDisplayName(displayName, token)

    ' Display the custom field ID
    MsgBox "The custom field ID for '" & displayName & "' is: " & fieldID
End Sub


' Function to extract JSON values without using ActiveX (compatible with Mac)
Function ExtractJSONValueForField(json As String, key As String) As String
    Dim keyPos As Long
    Dim valuePos As Long
    Dim valueEnd As Long
    Dim keyLength As Long
    Dim tempValue As String

    keyLength = Len(key)
    keyPos = InStr(json, """" & key & """")

    If keyPos > 0 Then
        valuePos = InStr(keyPos + keyLength, json, ":") + 1
        tempValue = Mid(json, valuePos)

        ' Determine if the value is a string or a number
        If Mid(tempValue, 1, 1) = """" Then
            valuePos = InStr(1, tempValue, """") + 1
            valueEnd = InStr(valuePos + 1, tempValue, """")
            ExtractJSONValueForField = Mid(tempValue, valuePos, valueEnd - valuePos)
        Else
            valueEnd = InStr(1, tempValue, ",")
            If valueEnd = 0 Then
                valueEnd = InStr(1, tempValue, "}")
            End If
            ExtractJSONValueForField = Trim(Mid(tempValue, 1, valueEnd - 1))
        End If
    Else
        ExtractJSONValueForField = ""
    End If
End Function


Sub UpdateJiraDataForMulipleSelectedCell()
    Dim ws As Worksheet
    Dim selectedRange As Range
    Dim selectedCell As Range
    Dim jiraID As String
    Dim token As String
    Dim jiraResponse As String
    Dim jiraNestedResponse As String
    Dim row As Long
    Dim URLFromHeaderFieldValue As String
    Dim HeaderDisplayName As String
    Dim HeaderFieldId As String
    Dim HeaderFieldValue As String
    Dim HeaderNestedFieldValue As String
    Dim col As Long

    ' Set the worksheet
    Set ws = ActiveSheet ' Update sheet name as needed

    ' Prompt user for Personal Access Token
    token = "-token-" 'InputBox("Please enter your Jira Personal Access Token:", "Jira PAT")

    If TypeName(Selection) = "Range" Then
        ' Set the selected range
        Set selectedRange = Selection

        ' Loop through each cell in the selected range
        For Each selectedCell In selectedRange

            ' Check if the selected cell is in column A and not empty
            If Not selectedCell Is Nothing And Not selectedCell.EntireRow.Hidden Then
                If selectedCell.Column = 2 And selectedCell.Value <> "" Then
                    jiraID = selectedCell.Value
                    row = selectedCell.row

                    ' Check if Jira ID matches the pattern JIR-<Number>
                    If Left(jiraID, 7) = "ROSTER-" And IsNumeric(Mid(jiraID, 8)) Then
                        ' Make the Jira API request
                        jiraResponse = JiraRequest(jiraID, token)

                        ' Testing purpose
                        'ActiveSheet.Cells(41, 1).Value = jiraResponse

                        ' Process JSON response (you may need to adjust based on your JSON structure)
                        If jiraResponse <> "" Then
                            For col = 3 To 20
                                HeaderDisplayName = ws.Cells(2, col).Value
                                HeaderFieldId = GetCustomFieldIDByDisplayName(HeaderDisplayName, token)
                                HeaderFieldValue = ExtractJSONValue(jiraResponse, HeaderFieldId)

                                URLFromHeaderFieldValue = ExtractJSONValue(HeaderFieldValue, "self")

                                If URLFromHeaderFieldValue <> "" Then
                                    jiraNestedResponse = JiraUrlRequest(URLFromHeaderFieldValue, token)
                                    HeaderNestedFieldValue = ExtractJSONValue(jiraNestedResponse, "name")

                                    If HeaderNestedFieldValue = "" Then
                                        HeaderNestedFieldValue = ExtractJSONValue(jiraNestedResponse, "dislayName")
                                    End If

                                    If HeaderNestedFieldValue = "" Then
                                        HeaderNestedFieldValue = ExtractJSONValue(jiraNestedResponse, "value")
                                    End If

                                    HeaderFieldValue = HeaderNestedFieldValue
                                End If

                                ' Update Excel with retrieved data (adjust column numbers as needed)
                                ws.Cells(row, col).Value = HeaderFieldValue ' Update column C

                             Next col
                             MsgBox "Done!"
                        Else
                            MsgBox "Failed to retrieve data for Jira ID: " & jiraID
                        End If
                    Else
                        MsgBox "Selected cell does not contain a valid Jira ID (PVM-<Number>)"
                    End If
                Else
                    MsgBox "Please select a cell in column A that contains a Jira ID"
                End If
            End If

        Next selectedCell
    Else
        MsgBox "Please select a range of cells."
    End If
End Sub
