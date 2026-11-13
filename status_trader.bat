@echo off
cd /d "C:\Users\lanat\.gemini\antigravity\scratch\day-trader-skill"
echo ======================================================
echo ULTIME ATTIVITA' UFFICIO AGENTI FINANZIARI
echo ======================================================
powershell -Command "if (Test-Path 'trader\trader.log') { Get-Content 'trader\trader.log' -Tail 25 } else { Write-Host 'Nessun file di log trovato.' }"
echo ======================================================
pause
