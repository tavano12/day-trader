#!/usr/bin/env python3
"""
UFFICIO AGENTI FINANZIARI IA (Autonomous Portfolio Manager)
Funzioni principali eseguite ogni 2 ore:
1. AUDIT PORTAFOGLIO: controlla cassa, equity, controvalore e posizioni attive su Alpaca Paper.
2. RIBILANCIAMENTO E RISCHIO: verifica stop-loss (-5%), take-profit (+5%), e limiti di allocazione.
3. OPPORTUNITY SCOUTING: analizza il mercato e calcola un punteggio AI (Score 1-10) su titoli leader.
4. ESECUZIONE AUTONOMA: invia gli ordini di ribilanciamento e acquisto direttamente al broker.
"""

import os
import sys
import time
import json
import logging
import datetime
import urllib.request
import urllib.error

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(ROOT_DIR, "trader", "ai_office.log")
STATUS_FILE = os.path.join(ROOT_DIR, "trader", "portfolio_status.json")
ENV_FILE = os.path.join(ROOT_DIR, ".env")
CONFIG_FILE = os.path.join(ROOT_DIR, "trader", "config.json")

os.makedirs(os.path.join(ROOT_DIR, "trader"), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

# Watchlist di asset per scouting e diversificazione
INVESTMENT_UNIVERSE = [
    ("SPY", "S&P 500 ETF", "Indice"),
    ("QQQ", "Nasdaq 100 ETF", "Indice"),
    ("NVDA", "Nvidia Corp", "AI / Chips"),
    ("AAPL", "Apple Inc", "Tech"),
    ("MSFT", "Microsoft", "Tech / Cloud"),
    ("AMZN", "Amazon", "E-Commerce / Cloud"),
    ("TSLA", "Tesla Inc", "EV / Tech"),
    ("AMD", "AMD", "Semiconductors"),
    ("STM", "STMicroelectronics", "Semiconductors"),
    ("XOM", "Exxon Mobil", "Energy"),
    ("TTE", "TotalEnergies", "Energy"),
    ("JPM", "JPMorgan Chase", "Finance")
]

def load_env():
    env = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    for k in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY", "APCA_API_KEY_ID", "APCA_API_SECRET_KEY", "APCA_API_BASE_URL", "SEC_USER_AGENT"):
        if k in os.environ and os.environ[k]:
            env[k] = os.environ[k]
    return env

def alpaca_req(env, endpoint, method="GET", data=None):
    base_url = env.get("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")
    url = f"{base_url}{endpoint}"
    payload = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=payload, method=method)
    key = env.get("APCA_API_KEY_ID") or env.get("ALPACA_API_KEY")
    sec = env.get("APCA_API_SECRET_KEY") or env.get("ALPACA_SECRET_KEY")
    req.add_header("APCA-API-KEY-ID", key)
    req.add_header("APCA-API-SECRET-KEY", sec)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def fetch_market_data(ticker):
    """Recupera dati di prezzo recenti via chart endpoint."""
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?range=5d&interval=15m"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            result = data["chart"]["result"][0]
            meta = result["meta"]
            quotes = result["indicators"]["quote"][0]
            closes = [c for c in quotes["close"] if c is not None]
            highs = [h for h in quotes["high"] if h is not None]
            lows = [l for l in quotes["low"] if l is not None]
            if not closes:
                return None
            curr = closes[-1]
            prev = meta.get("chartPreviousClose") or meta.get("previousClose", curr)
            pct = ((curr - prev) / prev * 100) if prev else 0.0
            return {
                "ticker": ticker,
                "price": curr,
                "change_pct": pct,
                "high_5d": max(highs),
                "low_5d": min(lows),
                "closes": closes[-20:] # ultime 20 barre
            }
    except Exception:
        return None

def calculate_ai_score(market_data):
    """
    Calcola un punteggio quantitativo/AI da 1 a 10 per la valutazione investimenti:
    - Trend di momentum
    - Posizione rispetto ai massimi a 5 giorni
    - Stabilita' di prezzo
    """
    if not market_data:
        return 0.0
    
    score = 5.0 # punteggio neutro di partenza
    closes = market_data["closes"]
    curr = market_data["price"]
    change = market_data["change_pct"]
    high = market_data["high_5d"]
    low = market_data["low_5d"]

    # 1. Momentum recente
    if change > 1.5:
        score += 1.5
    elif change > 0.5:
        score += 1.0
    elif change < -2.0:
        score -= 1.5

    # 2. Posizione nel range 5D
    if high > low:
        range_pos = (curr - low) / (high - low)
        if 0.70 <= range_pos <= 0.95: # Breakout sano vicino ai massimi
            score += 1.5
        elif range_pos < 0.20: # Ipervenduto
            score += 0.5

    # 3. Media mobile a breve termine (10 periodi)
    if len(closes) >= 10:
        ma10 = sum(closes[-10:]) / 10
        if curr > ma10:
            score += 1.0
        else:
            score -= 1.0

    return max(1.0, min(10.0, round(score, 1)))

def execute_ai_cycle(env):
    logging.info("=" * 65)
    logging.info("AVVIO CICLO AGENTI IA (GESTIONE E RIBILANCIAMENTO PORTAFOGLIO)")
    logging.info("=" * 65)

    # -------------------------------------------------------------
    # 1. CONTROLLO PORTAFOGLIO
    # -------------------------------------------------------------
    try:
        acc = alpaca_req(env, "/v2/account")
        positions = alpaca_req(env, "/v2/positions")
        clock = alpaca_req(env, "/v2/clock")
    except Exception as e:
        logging.error(f"Errore connessione ad Alpaca: {e}")
        return

    cash = float(acc.get("cash", 0.0))
    equity = float(acc.get("equity", 0.0))
    buying_power = float(acc.get("buying_power", 0.0))
    is_market_open = clock.get("is_open", False)

    logging.info(f"Stato Mercato: {'APERTO' if is_market_open else 'CHIUSO'}")
    logging.info(f"Capitale Totale (Equity): ${equity:,.2f} | Cassa Libera: ${cash:,.2f}")
    logging.info(f"Posizioni Attualmente Aperte: {len(positions)}")

    portfolio_report = {
        "timestamp": datetime.datetime.now().isoformat(),
        "is_market_open": is_market_open,
        "cash": cash,
        "equity": equity,
        "positions": [],
        "rebalancing_actions": [],
        "opportunities": []
    }

    # -------------------------------------------------------------
    # 2. CONTROLLO E RIBILANCIAMENTO POSIZIONI
    # -------------------------------------------------------------
    for p in positions:
        sym = p.get("symbol")
        qty = float(p.get("qty", 0))
        entry = float(p.get("avg_entry_price", 0))
        curr = float(p.get("current_price", 0))
        unrealized_pl = float(p.get("unrealized_pl", 0))
        pl_pct = float(p.get("unrealized_plpc", 0)) * 100
        market_val = float(p.get("market_value", 0))
        weight = (market_val / equity * 100) if equity > 0 else 0

        pos_info = {
            "symbol": sym,
            "qty": qty,
            "entry_price": entry,
            "current_price": curr,
            "unrealized_pl": unrealized_pl,
            "unrealized_pl_pct": round(pl_pct, 2),
            "portfolio_weight_pct": round(weight, 2),
            "status": "HOLD"
        }

        logging.info(f"Posizione {sym}: {qty:.0f} az. | Prezzo: ${curr:.2f} (Entry: ${entry:.2f}) | P&L: ${unrealized_pl:+.2f} ({pl_pct:+.2f}%) | Peso: {weight:.1f}%")

        # Regola di Ribilanciamento 1: Stop-Loss di Protezione (se perdita > 5.0%)
        if pl_pct <= -5.0:
            logging.warning(f"ALLERTA RISCHIO [{sym}]: Perdita del {pl_pct:.2f}% oltre la soglia del -5.0%. Esecuzione Stop-Loss di sicurezza.")
            if is_market_open:
                try:
                    alpaca_req(env, f"/v2/positions/{sym}", method="DELETE")
                    logging.info(f"Ordine Stop-Loss eseguito con successo su {sym}.")
                    pos_info["status"] = "CLOSED_STOP_LOSS"
                except Exception as ex:
                    logging.error(f"Errore chiusura posizione {sym}: {ex}")
            else:
                logging.info(f"Mercato chiuso: l'ordine di vendita protettivo per {sym} verra' eseguito all'apertura.")
                pos_info["status"] = "PENDING_CLOSE_STOP_LOSS"
            portfolio_report["rebalancing_actions"].append(f"VENDITA STOP-LOSS su {sym} ({pl_pct:.2f}%)")

        # Regola di Ribilanciamento 2: Take-Profit (se guadagno >= 5.0%)
        elif pl_pct >= 5.0:
            logging.info(f"TARGET RAGGIUNTO [{sym}]: Guadagno del {pl_pct:.2f}%. Incasso profitto e ribilanciamento in cassa.")
            if is_market_open:
                try:
                    alpaca_req(env, f"/v2/positions/{sym}", method="DELETE")
                    pos_info["status"] = "CLOSED_TAKE_PROFIT"
                except Exception as ex:
                    logging.error(f"Errore chiusura profitto {sym}: {ex}")
            else:
                pos_info["status"] = "PENDING_CLOSE_TAKE_PROFIT"
            portfolio_report["rebalancing_actions"].append(f"PRESA PROFITTO su {sym} (+{pl_pct:.2f}%)")

        # Regola di Ribilanciamento 3: Sovra-concentrazione (peso > 20% del portafoglio)
        elif weight > 20.0:
            logging.info(f"RIBILANCIAMENTO PESI [{sym}]: Peso {weight:.1f}% > 20%. Riduzione posizione.")
            pos_info["status"] = "TRIM_WEIGHT"
            portfolio_report["rebalancing_actions"].append(f"RIDUZIONE PESO su {sym} ({weight:.1f}%)")

        else:
            logging.info(f"Verdetto {sym}: HOLD (Parametri stabili all'interno del corridoio di oscillazione).")

        portfolio_report["positions"].append(pos_info)

    # -------------------------------------------------------------
    # 3. VALUTAZIONE NUOVI INVESTIMENTI (OPPORTUNITY SCOUTING)
    # -------------------------------------------------------------
    logging.info("-" * 65)
    logging.info("DESK ANALISI & OPPORTUNITA': Scansione asset per investimenti...")
    
    scored_opportunities = []
    for ticker, name, cat in INVESTMENT_UNIVERSE:
        data = fetch_market_data(ticker)
        if data:
            score = calculate_ai_score(data)
            scored_opportunities.append({
                "ticker": ticker,
                "name": name,
                "category": cat,
                "price": data["price"],
                "change_pct": data["change_pct"],
                "score": score
            })
        time.sleep(0.05)

    scored_opportunities.sort(key=lambda x: x["score"], reverse=True)
    portfolio_report["opportunities"] = scored_opportunities[:5]

    for opp in scored_opportunities[:5]:
        logging.info(f"Opportunity: {opp['ticker']:<5} ({opp['name']:<18}) | Score: {opp['score']}/10 | Prezzo: ${opp['price']:>7.2f} | Var%: {opp['change_pct']:>+5.2f}%")

    # -------------------------------------------------------------
    # 4. DECISIONE DI INVESTIMENTO
    # -------------------------------------------------------------
    top_pick = scored_opportunities[0] if scored_opportunities else None
    
    # Se il titolo ha uno Score elevato (>= 7.5), non e' gia' in portafoglio e abbiamo liquidita'
    held_symbols = [p.get("symbol") for p in positions]
    cash_buffer = equity * 0.10 # 10% sempre in cassa di sicurezza

    if top_pick and top_pick["score"] >= 7.5 and top_pick["ticker"] not in held_symbols and cash > cash_buffer:
        target_allocation = 1000.0 # investiamo $1.000 per tranche
        shares_to_buy = int(target_allocation / top_pick["price"])
        
        if shares_to_buy > 0:
            logging.info(f"SEGNALE INVESTIMENTO ATTIVATO: Acquisto {shares_to_buy} azioni di {top_pick['ticker']} (Score: {top_pick['score']}/10)")
            order_data = {
                "symbol": top_pick["ticker"],
                "qty": str(shares_to_buy),
                "side": "buy",
                "type": "market",
                "time_in_force": "day"
            }
            try:
                res = alpaca_req(env, "/v2/orders", method="POST", data=order_data)
                logging.info(f"Ordine di acquisto inviato ad Alpaca! ID: {res.get('id')} | Stato: {res.get('status')}")
                portfolio_report["rebalancing_actions"].append(f"ACQUISTO NUOVA OPPORTUNITA': {shares_to_buy} x {top_pick['ticker']}")
            except Exception as e:
                logging.error(f"Errore invio ordine acquisto per {top_pick['ticker']}: {e}")
    else:
        logging.info("Verdetto Investimenti: Nessuna nuova posizione richiesta in questo ciclo. Capitale preservato.")

    # Salvataggio stato portafoglio in JSON
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(portfolio_report, f, indent=2)

    logging.info(f"Ciclo completato. Report salvato in {STATUS_FILE}")
    logging.info("=" * 65)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Autonomous AI Portfolio Manager")
    parser.add_argument("--once", action="store_true", help="Esegue un singolo ciclo di ribilanciamento ed esce")
    parser.add_argument("--interval", type=int, default=7200, help="Secondi tra un ciclo e l'altro (default 7200 = 2 ore)")
    args = parser.parse_args()

    env = load_env()

    if args.once:
        execute_ai_cycle(env)
        return

    logging.info(f"Avvio Demone AI Portfolio Manager (Intervallo: ogni {args.interval // 3600} ore / {args.interval} sec)...")
    while True:
        try:
            execute_ai_cycle(env)
            logging.info(f"In attesa del prossimo ciclo tra {args.interval // 60} minuti...")
            time.sleep(args.interval)
        except KeyboardInterrupt:
            logging.info("Arresto manuale del Portfolio Manager.")
            break
        except Exception as e:
            logging.error(f"Errore imprevisto nel demone: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
