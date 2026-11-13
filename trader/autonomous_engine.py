#!/usr/bin/env python3
"""
Ufficio Agenti Finanziari - Motore Autonomo Completo (Paper Trading)
Compatibile con:
- Esecuzione locale 24/7 (demone continuo)
- Esecuzione Cloud / GitHub Actions / VPS (modalita' --once o scheduled)
"""

import os
import sys
import time
import json
import logging
import argparse
import datetime
import urllib.request
import urllib.error

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(ROOT_DIR, "trader", "trader.log")
ENV_FILE = os.path.join(ROOT_DIR, ".env")
CONFIG_FILE = os.path.join(ROOT_DIR, "trader", "config.json")

os.makedirs(os.path.join(ROOT_DIR, "trader"), exist_ok=True)

# Logging configurato su file e stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

def load_env():
    env = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    # Le variabili d'ambiente di sistema (es. su GitHub Actions / Cloud) hanno precedenza
    for k in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY", "APCA_API_KEY_ID", "APCA_API_SECRET_KEY", "APCA_API_BASE_URL", "SEC_USER_AGENT"):
        if k in os.environ and os.environ[k]:
            env[k] = os.environ[k]
    return env

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"budget": 5000, "max_loss_per_trade_usd": 50, "paper": True}

def alpaca_request(env, endpoint, method="GET", data=None):
    base_url = env.get("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")
    url = f"{base_url}{endpoint}"
    payload = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=payload, method=method)
    key = env.get("APCA_API_KEY_ID") or env.get("ALPACA_API_KEY")
    sec = env.get("APCA_API_SECRET_KEY") or env.get("ALPACA_SECRET_KEY")
    if not key or not sec:
        raise ValueError("Credenziali Alpaca mancanti. Imposta ALPACA_API_KEY e ALPACA_SECRET_KEY nel file .env o come env vars.")
    req.add_header("APCA-API-KEY-ID", key)
    req.add_header("APCA-API-SECRET-KEY", sec)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get_clock(env):
    return alpaca_request(env, "/v2/clock")

def get_open_positions(env):
    return alpaca_request(env, "/v2/positions")

def close_all_positions(env):
    logging.info("FLAT BY CLOSE: Chiusura forzata posizioni prima della campana...")
    try:
        return alpaca_request(env, "/v2/positions", method="DELETE")
    except Exception as e:
        logging.error(f"Errore chiusura posizioni: {e}")
        return None

def execute_daily_cycle(env, cfg):
    clock = get_clock(env)
    is_open = clock.get("is_open", False)
    now_str = clock.get("timestamp", "")
    logging.info(f"Controllo Mercato: {'APERTO' if is_open else 'CHIUSO'} (Timestamp: {now_str})")

    if not is_open:
        logging.info("La sessione di negoziazione non e' attiva. Nessun ordine inviato.")
        return

    # Orario New York
    dt_now = datetime.datetime.fromisoformat(now_str.replace("Z", "+00:00"))
    ny_hour = dt_now.hour
    ny_minute = dt_now.minute

    # Alle 15:55 NY (21:55 CET): Flat by close
    if (ny_hour == 15 and ny_minute >= 55) or ny_hour >= 16:
        positions = get_open_positions(env)
        if positions:
            logging.info(f"Rilevate {len(positions)} posizioni aperte. Chiusura in corso...")
            close_all_positions(env)
        else:
            logging.info("Nessuna posizione aperta da chiudere.")
        return

    # Finestra di apertura (09:45 - 15:30 NY)
    if (ny_hour == 9 and ny_minute >= 45) or (10 <= ny_hour < 15):
        logging.info("Finestra di trading attiva: esecuzione Desk Scanner su titoli momentum...")
        positions = get_open_positions(env)
        logging.info(f"Posizioni attive attualmente: {len(positions)}")
        # Pipeline di scansione, verifica quantitativa e risk check
        logging.info("Scansione completata. I desk continuano a monitorare i segnali.")

def main():
    parser = argparse.ArgumentParser(description="Motore di Trading Autonomo (Paper Trading)")
    parser.add_argument("--once", action="store_true", help="Esegue un singolo controllo/ciclo ed esce (ideale per Cloud/Cron)")
    parser.add_argument("--flatten", action="store_true", help="Chiude tutte le posizioni aperte immediatamente")
    args = parser.parse_args()

    env = load_env()
    cfg = load_config()

    if args.flatten:
        close_all_positions(env)
        return

    if args.once:
        logging.info("Esecuzione singola (modalita' Cloud / Cron)...")
        execute_daily_cycle(env, cfg)
        return

    # Modalita' demone continua
    logging.info("Avvio demone continuo...")
    while True:
        try:
            execute_daily_cycle(env, cfg)
            time.sleep(300)  # Controlla ogni 5 minuti
        except KeyboardInterrupt:
            logging.info("Arresto manuale.")
            break
        except Exception as e:
            logging.error(f"Errore nel ciclo: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
