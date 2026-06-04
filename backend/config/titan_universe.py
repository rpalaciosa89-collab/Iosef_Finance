"""
config/titan_universe.py
Universo Titan 100: Las 100 empresas seleccionadas bajo filosofía
Musk (First Principles) + Gates (Engineering Scale) + Buffett (Economic Moats) + Jensen Huang (AI Infrastructure).
Sin redundancias, sin hueso. Solo carne premium.

Licencia: MIT (uso interno)
"""

# ── Bloque 1: Jensen Huang & Satya Nadella (Infraestructura, IA, Cloud) ────────
BLOCK_AI_INFRA = [
    "NVDA", "TSM",  "ASML", "MSFT", "AMZN", "GOOGL",
    "AMD",  "AVGO", "ARM",  "QCOM", "MU",   "ANET",
    "META", "ADBE", "CRM",  "ORCL", "SNPS", "CDNS",
    "CRWD", "PANW", "PLTR", "NOW",  "INTU", "SAP",  "IBM",
]

# ── Bloque 2: Warren Buffett (Fosos Económicos, Cashflow, Indestructibles) ─────
BLOCK_MOAT = [
    "AAPL", "BRK-B","V",   "MA",   "AXP",  "JPM",
    "BAC",  "KO",   "PEP", "PG",   "COST", "WMT",
    "JNJ",  "UNH",  "LLY", "NVO",  "MCD",  "HD",
    "LOW",  "SPGI", "MCO", "VRTX", "REGN", "ABBV", "MRK",
]

# ── Bloque 3: Elon Musk & Hard Tech (Física, Energía, Defensa, Disrupción) ─────
BLOCK_HARD_TECH = [
    "TSLA", "LMT",  "RTX",  "NOC",  "GD",   "GE",
    "HON",  "CAT",  "DE",   "XOM",  "CVX",  "FSLR",
    "ENPH", "NEE",  "LIN",  "SHW",  "APD",  "UBER",
    "ABNB", "SPOT", "ISRG", "BSX",  "SYK",  "TDG",  "HEI",
]

# ── Bloque 4: Titanes Globales (Lujo, Europa, Poder de Precio, Escasez) ────────
BLOCK_GLOBAL = [
    "LVMUY","RMS.PA","TTE",  "SIE.DE","AIR.PA","NFLX",
    "DIS",  "SBUX", "NKE",  "TM",   "SONY",  "RACE",
    "MAR",  "BKNG", "CMG",  "TMO",  "DHR",   "SAP",
    "ASML", "OR.PA","MC.PA","CDI.PA","ITX.MC","IBE.MC","SAN.MC",
]

# ── Universo unificado y deduplicado (Set → List para preservar orden) ──────────
TITAN_100: list[str] = list(dict.fromkeys(
    BLOCK_AI_INFRA + BLOCK_MOAT + BLOCK_HARD_TECH + BLOCK_GLOBAL
))

# Metadatos de sector para los "Sector Embeddings" del LSTM
SECTOR_MAP: dict[str, str] = {
    # Technology / AI Infrastructure
    **{t: "AI_INFRA"    for t in BLOCK_AI_INFRA},
    # Financials / Consumer Staples / Healthcare
    **{t: "MOAT"        for t in BLOCK_MOAT},
    # Industrials / Energy / Hard Tech
    **{t: "HARD_TECH"   for t in BLOCK_HARD_TECH},
    # Global / Luxury / Consumer Discretionary
    **{t: "GLOBAL_TITAN" for t in BLOCK_GLOBAL},
}

if __name__ == "__main__":
    print(f"Universo Titan 100: {len(TITAN_100)} empresas únicas")
    for i, t in enumerate(TITAN_100, 1):
        print(f"  {i:>3}. {t:<12} [{SECTOR_MAP.get(t,'?')}]")
