@echo off
chcp 65001 >nul
cd /d "C:\Users\lanat\.gemini\antigravity\scratch\day-trader-skill"
"C:\Users\lanat\AppData\Local\Programs\Python\Python314\python.exe" "trader\print_status.py"
echo.
echo Premi un tasto per forzare un controllo e ribilanciamento IA immediato...
pause >nul
echo.
echo [Avvio ribilanciamento IA in corso...]
"C:\Users\lanat\AppData\Local\Programs\Python\Python314\python.exe" "trader\ai_portfolio_manager.py" --once
echo.
echo [Operazione completata con successo!]
pause
