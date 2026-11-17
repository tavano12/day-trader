@echo off
cd /d "C:\Users\lanat\.gemini\antigravity\scratch\day-trader-skill"
echo ==============================================================
echo       REPORT UFFICIO AGENTI IA - STATO E RIBILANCIAMENTO
echo ==============================================================
python -c "
import json
try:
    with open('trader/portfolio_status.json', encoding='utf-8') as f:
        d = json.load(f)
        print('Ultimo Controllo:', d.get('timestamp'))
        print('Mercato Aperto:', d.get('is_market_open'))
        print(f'Cassa Libera: ${d.get(\"cash\"):,.2f}')
        print(f'Valore Totale (Equity): ${d.get(\"equity\"):,.2f}')
        print('\n--- POSIZIONI ATTIVE ---')
        for p in d.get('positions', []):
            print(f'-> {p[\"symbol\"]}: {p[\"qty\"]} az. | Prezzo: ${p[\"current_price\"]:.2f} | P&L: ${p[\"unrealized_pl\"]:+.2f} ({p[\"unrealized_pl_pct\"]:+.2f}%) | Azione: {p[\"status\"]}')
        if not d.get('positions'):
            print('Nessuna posizione aperta.')
        print('\n--- TOP 3 OPPORTUNITA\' ANALIZZATE DALL\'IA ---')
        for o in d.get('opportunities', [])[:3]:
            print(f'-> {o[\"ticker\"]} ({o[\"name\"]}) | AI Score: {o[\"score\"]}/10 | Prezzo: ${o[\"price\"]:.2f} | Var%: {o[\"change_pct\"]:+.2f}%')
except Exception as e:
    print('Nessun report disponibile al momento:', e)
"
echo ==============================================================
echo [INFO] Per forzare un controllo immediato ora, premi un tasto...
pause
python trader/ai_portfolio_manager.py --once
pause
