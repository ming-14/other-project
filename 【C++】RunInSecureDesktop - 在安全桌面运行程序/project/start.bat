@echo off
powershell -Command "Start-Process '%~dp0NSudoLC.exe' -ArgumentList '/U:T RunInSecureDesktop.exe """%~1"""' -Verb RunAs"