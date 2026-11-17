@echo off
cd /d "C:\Users\lanat\.gemini\antigravity\scratch\day-trader-skill"
echo Avvio dell'Ufficio Agenti IA (ciclo automatico ogni 2 ore)...
start "" "C:\Users\lanat\AppData\Local\Programs\Python\Python314\pythonw.exe" "trader\ai_portfolio_manager.py"
echo [OK] Ufficio Agenti IA attivo in background!
echo Monitora e ribilancia il portafoglio ogni 2 ore.
echo Puoi verificare lo stato in ogni momento aprendo 'check_portfolio_status.bat'.
pause
