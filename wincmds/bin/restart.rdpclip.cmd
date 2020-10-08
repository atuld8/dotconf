@taskkill /f /im rdpclip.exe

@start rdpclip.exe
@echo newly started rdpclip

@tasklist | findstr "rdpclip"