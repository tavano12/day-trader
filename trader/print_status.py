import os
import json
import urllib.request

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS_FILE = os.path.join(ROOT_DIR, "trader", "portfolio_status.json")
ENV_FILE = os.path.join(ROOT_DIR, ".env")

def get_live_data():
    env = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    env[k.strip()] = v.strip()
    
    headers = {
        "APCA-API-KEY-ID": env.get("APCA_API_KEY_ID") or env.get("ALPACA_API_KEY"),
        "APCA-API-SECRET-KEY": env.get("APCA_API_SECRET_KEY") or env.get("ALPACA_SECRET_KEY")
    }
    base_url = env.get("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")

    acc = {}
    positions = []
    clock = {}

    try:
        req = urllib.request.Request(f"{base_url}/v2/account", headers=headers)
        with urllib.request.urlopen(req, timeout=5) as r:
            acc = json.loads(r.read().decode())
        
        req = urllib.request.Request(f"{base_url}/v2/positions", headers=headers)
        with urllib.request.urlopen(req, timeout=5) as r:
            positions = json.loads(r.read().decode())

        req = urllib.request.Request(f"{base_url}/v2/clock", headers=headers)
        with urllib.request.urlopen(req, timeout=5) as r:
            clock = json.loads(r.read().decode())
    except Exception as e:
        pass

    return acc, positions, clock

def main():
    print("=" * 68)
    print("       REPORT UFFICIO AGENTI IA - STATO PORTAFOGLIO E RISCHIO")
    print("=" * 68)

    acc, positions, clock = get_live_data()

    if acc:
        cash = float(acc.get("cash", 0))
        equity = float(acc.get("equity", 0))
        bp = float(acc.get("buying_power", 0))
        is_open = clock.get("is_open", False)

        print(f"Stato Mercato : {'APERTO' if is_open else 'CHIUSO (in attesa della campana)'}")
        print(f"Capitale Netto: ${equity:,.2f}")
        print(f"Cassa Libera  : ${cash:,.2f}")
        print(f"Potere Acquisto: ${bp:,.2f}")
        print("-" * 68)
        print("POSIZIONI ATTIVE IN PORTAFOGLIO:")
        if positions:
            for p in positions:
                sym = p.get("symbol")
                qty = float(p.get("qty", 0))
                entry = float(p.get("avg_entry_price", 0))
                curr = float(p.get("current_price", 0))
                pnl = float(p.get("unrealized_pl", 0))
                pnl_pct = float(p.get("unrealized_plpc", 0)) * 100
                print(f"  -> {sym:<5} | {qty:.0f} azioni | Prezzo: ${curr:.2f} (Carico: ${entry:.2f}) | P&L: ${pnl:+.2f} ({pnl_pct:+.2f}%)")
        else:
            print("  Nessuna posizione aperta (100% in liquidita').")
    else:
        print("Impossibile contattare direttamente il broker. Lettura file locale...")

    print("-" * 68)
    print("ULTIMO MONITORAGGIO IA E OPPORTUNITA' RILEVATE:")
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                st = json.load(f)
                opps = st.get("opportunities", [])
                for o in opps[:4]:
                    print(f"  * {o['ticker']:<5} ({o['name']:<18}) | AI Score: {o['score']}/10 | Prezzo: ${o['price']:>7.2f} | Var%: {o['change_pct']:>+5.2f}%")
        except Exception:
            pass
    print("=" * 68)

if __name__ == "__main__":
    main()
