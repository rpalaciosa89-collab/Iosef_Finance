import json, urllib.request, time, math, statistics
import sys

BASE = "http://localhost:8002"

def get(path):
    url = f"{BASE}{path}&_t={int(time.time())}" if "?" in path else f"{BASE}{path}?_t={int(time.time())}"
    return json.loads(urllib.request.urlopen(url).read())

print("=" * 70)
print("DATOS BASE")
print("=" * 70)

# ---- SCAN ----
scan = get("/api/scan?market=titan100")
data = scan.get("data", [])
alerts = scan.get("alerts", [])

pwins  = [t["signal_strength_score"] for t in data]
scores = [t["composite_score"] for t in data]
rsis   = [t["rsi"] for t in data if t["rsi"] > 0]
changes = [t["change_pct"] for t in data]

active = [t for t in data if t.get("signal_status") in ("new","active")]
active.sort(key=lambda x: -x["signal_strength_score"])

longs  = [t for t in data if t.get("trade_plan",{}).get("direction")=="LONG" and t.get("signal_status") in ("new","active")]
shorts = [t for t in data if t.get("trade_plan",{}).get("direction")=="SHORT" and t.get("signal_status") in ("new","active")]

print(f"Tickers: {len(data)}")
print(f"Alertas activas: {len(alerts)}")
print(f"Señales activas (new/active): {len(active)}  LONG={len(longs)}  SHORT={len(shorts)}")
print()

# ---- SIGNAL LAB ----
lab = get("/api/signal-evaluation?market=titan100")
signals = lab.get("data", {}).get("signals", {})
print("SIGNAL LAB (Top 6 por ocurrencias):")
for name, s in sorted(signals.items(), key=lambda x: -x[1]["total_signals"])[:6]:
    wr = s["win_rate_5d"]
    ar = s["avg_return_5d"]
    mr = s["median_return_5d"]
    n  = s["total_signals"]
    # IC 95%
    se = math.sqrt(wr * (1 - wr) / n)
    ci_low = max(0, wr - 1.96 * se)
    ci_high = min(1, wr + 1.96 * se)
    print(f"  {name}: n={n} wr={wr:.1%} [{ci_low:.1%}-{ci_high:.1%}] ret_mean={ar}% ret_median={mr}%")
print()

# ---- ANALYTICS ----
anl = get("/api/analytics")
sa = anl.get("data", {}).get("signal_analytics", {})
total_closed = sum(s["total_trades"] for s in sa.values())
total_wr = sum(s["effective_win_rate"] * s["total_trades"] / 100 for s in sa.values())
eff_wr = (total_wr / total_closed * 100) if total_closed > 0 else 0
avg_pnl_all = sum(s["avg_pnl"] * s["total_trades"] for s in sa.values()) / total_closed if total_closed > 0 else 0

print("ANALYTICS:")
for name, s in sorted(sa.items(), key=lambda x: -x[1]["total_trades"])[:6]:
    print(f"  {name}: trades={s['total_trades']} eff_wr={s['effective_win_rate']:.1f}% pnl={s['avg_pnl']}% expiry={s['expiry_rate']}%")
print(f"  TOTAL CLOSED: {total_closed}, PnL medio global: {avg_pnl_all:+.2f}%")
print()

# ---- NEURAL ----
neural_samples = {}
for ticker in ["TSLA", "AAPL", "IBM", "LLY", "NVDA", "JNJ", "MSFT", "INTU", "COST", "META"]:
    try:
        ns = get(f"/api/neural-score/{ticker}")
        nd = ns.get("data", {})
        neural_samples[ticker] = {
            "xgb": nd.get("p_win_xgb", 50),
            "lstm": nd.get("p_win_lstm", 50),
            "ensemble": nd.get("p_win_composite", 50),
            "signal": nd.get("signal", "NEUTRAL"),
            "alignment": nd.get("alignment", "NEUTRAL"),
        }
    except:
        pass

print("NEURAL SCORE (10 tickers):")
for t, s in neural_samples.items():
    print(f"  {t}: xgb={s['xgb']:.1f}% lstm={s['lstm']:.1f}% ens={s['ensemble']:.1f}% → {s['signal']} ({s['alignment']})")

ensembles = [s["ensemble"] for s in neural_samples.values()]
lstms = [s["lstm"] for s in neural_samples.values() if s["lstm"] is not None]
xgbs = [s["xgb"] for s in neural_samples.values()]
print(f"  LSTM range: {min(lstms):.1f}% - {max(lstms):.1f}%  avg={sum(lstms)/len(lstms):.1f}%")
print(f"  XGB  range: {min(xgbs):.1f}% - {max(xgbs):.1f}%  avg={sum(xgbs)/len(xgbs):.1f}%")
print(f"  Ens  range: {min(ensembles):.1f}% - {max(ensembles):.1f}%  avg={sum(ensembles)/len(ensembles):.1f}%")

# Count how many are COMPRA / VENTA / NEUTRAL
signals_counts = {"COMPRA": 0, "VENTA": 0, "NEUTRAL": 0}
for s in neural_samples.values():
    signals_counts[s["signal"]] = signals_counts.get(s["signal"], 0) + 1
print(f"  Distribución: {signals_counts}")
print()

# ---- Top 5 activas con plan ----
print("TOP 5 SEÑALES ACTIVAS:")
for t in active[:5]:
    p = t.get("trade_plan", {})
    print(f"  {t['ticker']}: P(Win)={t['signal_strength_score']:.1f}% score={t['composite_score']} "
          f"dir={p.get('direction','?')} sit={t.get('situation')} clarity={t.get('decision_clarity')} "
          f"RSI={t['rsi']:.1f} Mom1M={t['momentum_1m']:+.1f}% chg={t['change_pct']:+.2f}%")
    print(f"    Entry=${p.get('entry_price',0):.2f} SL=${p.get('stop_loss',0):.2f} TP=${p.get('take_profit',0):.2f} R/R={p.get('risk_reward','?')}")

print()
print("=" * 70)
print("CÁLCULOS FINANCIEROS")
print("=" * 70)

# ---- A.1: Retorno esperado neto ----
# Usamos los datos del Signal Lab: 12 tipos de señal, 2 años de backtest
# Tomamos la señal promedio ponderada por ocurrencias
total_signals_lab = 0
weighted_ret = 0
weighted_wr = 0
for name, s in signals.items():
    n = s["total_signals"]
    total_signals_lab += n
    weighted_ret += n * s["avg_return_5d"]
    weighted_wr += n * s["win_rate_5d"]

avg_ret_per_signal = weighted_ret / total_signals_lab  # en %, por 5 días
avg_wr_lab = weighted_wr / total_signals_lab

print(f"\n--- A.1: Retorno esperado por operación ---")
print(f"Señales totales en backtest: {total_signals_lab}")
print(f"Win rate medio ponderado: {avg_wr_lab:.1%}")
print(f"Retorno medio ponderado (5d): {avg_ret_per_signal:+.2f}%")

# Asumiendo 1 operación por día (la mejor señal disponible)
# 252 días de mercado al año
# La señal dura 5 días → podemos tener ~50 operaciones/año si rotamos,
# o ~252 operaciones/año si tomamos 1 señal nueva cada día
ops_per_year = 252
cost_per_trade = 0.001  # 0.1% por operación (entrada + salida)
tax_rate = 0.20

# Retorno bruto esperado por operación (en %)
avg_loss_rate = 1 - avg_wr_lab
# Estimamos avg_gain y avg_loss a partir del retorno medio y win rate
# Retorno_medio = WR * avg_gain - (1-WR) * avg_loss
# Asumiendo R/R ~2 (del plan de trading), avg_gain ≈ 2 * avg_loss
# avg_loss ≈ avg_ret / (WR*2 - (1-WR))
rr_ratio = 2.0
avg_loss_est = avg_ret_per_signal / (avg_wr_lab * rr_ratio - avg_loss_rate)
avg_gain_est = avg_loss_est * rr_ratio

print(f"  avg_gain estimado: {avg_gain_est:+.2f}%")
print(f"  avg_loss estimado: {avg_loss_est:+.2f}%")

ret_bruto_por_op = avg_wr_lab * avg_gain_est - avg_loss_rate * avg_loss_est
ret_neto_por_op = ret_bruto_por_op - cost_per_trade * 100  # convertir a %
# Solo pagamos impuesto si el retorno neto es positivo
tax_per_op = max(0, ret_neto_por_op) * tax_rate
ret_final_por_op = ret_neto_por_op - tax_per_op

print(f"  Retorno bruto/op: {ret_bruto_por_op:+.3f}%")
print(f"  Costo transacción: -{cost_per_trade*100:.2f}%")
print(f"  Retorno neto/op: {ret_neto_por_op:+.3f}%")
print(f"  Impuesto (20%): -{tax_per_op:.3f}%")
print(f"  Retorno final/op: {ret_final_por_op:+.3f}%")

ret_anual = (1 + ret_final_por_op/100) ** ops_per_year - 1
print(f"  Retorno anualizado: {ret_anual:+.1%}")

# SPY benchmark
spy_return = 0.10
print(f"  SPY buy & hold: +10.0%")
print(f"  Diferencia: {ret_anual - spy_return:+.1%}")

# Sharpe aproximado
vol_diaria = 1.5  # volatilidad diaria típica del mercado ~1.5%
sharpe = (ret_anual - 0.04) / (vol_diaria * math.sqrt(252) / 100)
print(f"  Sharpe estimado: {sharpe:.2f}")

print(f"\n--- A.2: Intervalo de confianza high_volume ---")
hv = signals.get("high_volume", {})
if hv:
    n_hv = hv["total_signals"]
    wr_hv = hv["win_rate_5d"]
    se_hv = math.sqrt(wr_hv * (1 - wr_hv) / n_hv)
    ci = 1.96 * se_hv
    print(f"  n={n_hv} wr={wr_hv:.1%}")
    print(f"  IC 95%: [{wr_hv - ci:.1%}, {wr_hv + ci:.1%}]")
    print(f"  ¿Significativamente > 50%?: {'SÍ' if wr_hv - ci > 0.50 else 'NO'}")

print(f"\n--- A.3: Paradoja WR > 50% con PnL negativo ---")
# Win rate alto pero avg_pnl negativo = las pérdidas son más grandes que las ganancias
# Esto es clásico de distribuciones con fat tails negativas
momentum_down = sa.get("momentum_down", {})
if momentum_down:
    wr_md = momentum_down["effective_win_rate"] / 100
    pnl_md = momentum_down["avg_pnl"]
    trades_md = momentum_down["total_trades"]
    # avg_pnl = wr * avg_gain - (1-wr) * avg_loss
    # Si avg_pnl < 0 y wr > 0.5 → avg_loss > avg_gain * wr/(1-wr)
    ratio_min = wr_md / (1 - wr_md)
    print(f"  momentum_down: wr={wr_md:.1%} pnl={pnl_md:+.2f}% trades={trades_md}")
    print(f"  Para que PnL<0 con wr>{0.5:.1%}: avg_loss > {ratio_min:.2f}x avg_gain")
    print(f"  → Las pérdidas son al menos {ratio_min:.1f}x más grandes que las ganancias")
    print(f"  → Implica fat tails negativas o stops demasiado amplios vs. takes")

print(f"\n--- B.2: ¿El LSTM agrega valor? ---")
# Varianza del ensemble vs XGBoost puro
var_xgb = statistics.variance(xgbs) if len(xgbs) > 1 else 0
var_ens = statistics.variance(ensembles) if len(ensembles) > 1 else 0
print(f"  var(XGBoost) = {var_xgb:.1f}")
print(f"  var(Ensemble) = {var_ens:.1f}")
print(f"  El ensemble tiene {'MENOS' if var_ens < var_xgb else 'MÁS'} varianza que XGBoost puro")
print(f"  → El LSTM está {'COMPRIMIENDO' if var_ens < var_xgb else 'AMPLIFICANDO'} la señal")
print(f"  LSTM medio: {sum(lstms)/len(lstms):.1f}% (anclado en ~50%)")

# Si sacamos el LSTM y usamos solo XGB:
xgbs_only_signals = {"COMPRA": 0, "VENTA": 0, "NEUTRAL": 0}
for t, s in neural_samples.items():
    if s["xgb"] >= 55:
        xgbs_only_signals["COMPRA"] += 1
    elif s["xgb"] <= 45:
        xgbs_only_signals["VENTA"] += 1
    else:
        xgbs_only_signals["NEUTRAL"] += 1
print(f"  Con XGBoost puro: {xgbs_only_signals}")
print(f"  Con Ensemble:     {signals_counts}")

print(f"\n--- B.3: Poder predictivo real ---")
# Cuántos tickers tienen P(Win) significativamente diferente de 50%
# Si el modelo no discrimina, la distribución debería estar centrada en 50%
above_55 = sum(1 for p in pwins if p >= 55)
below_45 = sum(1 for p in pwins if p <= 45)
print(f"  P(Win) >= 55%: {above_55}/{len(pwins)} ({above_55/len(pwins):.0%})")
print(f"  P(Win) <= 45%: {below_45}/{len(pwins)} ({below_45/len(pwins):.0%})")
discrimina = above_55 + below_45
print(f"  Total que discrimina: {discrimina}/{len(pwins)} ({discrimina/len(pwins):.0%})")
print(f"  Si el modelo fuera aleatorio, esperaríamos ~{len(pwins)*0.32:.0f} fuera de [45,55]")
print(f"  ¿Discrimina más que el azar?: {'SÍ' if discrimina > len(pwins)*0.32 else 'NO'}")

print(f"\n--- D.1: Comparación con alternativas pasivas ---")
print(f"  Estrategia Iosef (mejor caso, 1 op/día): {ret_anual:+.1%}")
print(f"  SPY buy & hold:                          +10.0%")
print(f"  60/40 stocks/bonds:                      +7.0%")
print(f"  Cash (risk-free):                        +4.0%")
print(f"  Iosef supera SPY: {'SÍ' if ret_anual > 0.10 else 'NO'}")
print(f"  Iosef supera 60/40: {'SÍ' if ret_anual > 0.07 else 'NO'}")
print(f"  Iosef supera cash: {'SÍ' if ret_anual > 0.04 else 'NO'}")

# Break-even: ¿cuántas ops/año necesito para igualar SPY?
ops_for_spy = math.log(1.10) / math.log(1 + ret_final_por_op/100) if ret_final_por_op > 0 else float('inf')
print(f"  Operaciones/año para igualar SPY: {ops_for_spy:.0f} (imposible con 252 días)" if ops_for_spy > 252 else f"  Operaciones/año para igualar SPY: {ops_for_spy:.0f}")

print(f"\n--- E.1: Veredicto previo ---")
print(f"  Sharpe: {sharpe:.2f} (SPY ~0.5-0.7 en últimos 10 años)")
print(f"  Retorno anualizado: {ret_anual:+.1%}")
print(f"  Win rate medio: {avg_wr_lab:.1%}")
print(f"  El retorno por operación ({ret_final_por_op:+.3f}%) es marginal")
