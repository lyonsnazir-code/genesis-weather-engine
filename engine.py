import os
import sqlite3
import uuid
from quant_engine.guardrails import GuardrailConfig, evaluate_candidate

DB_PATH = os.getenv('STATE_DB_PATH', 'weather_engine_state.db')
DRY_RUN = os.getenv('DRY_RUN', 'true').lower() in ('1', 'true', 'yes')


def init_db(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute(
        'CREATE TABLE IF NOT EXISTS cycle_audit ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp_utc TEXT, city TEXT, market_ticker TEXT, '
        'p_true REAL, p_implied REAL, ev_per_contract REAL, obi_top5 REAL, '
        'decision TEXT, contracts_sized INTEGER, stake_usd REAL, order_id TEXT)'
    )
    conn.commit()
    conn.close()


def load_sqlite_exposure(db_path=DB_PATH):
    t_spend, t_cnt, t_tranches, t_cost_cents, t_last_ev, c_spend = {}, {}, {}, {}, {}, {}
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT city, market_ticker, contracts_sized, stake_usd, p_implied, ev_per_contract "
        "FROM cycle_audit WHERE decision IN ('LIVE_EXECUTED', 'DRY_RUN_EXECUTE') ORDER BY id ASC"
    )
    for city, mkt, cnt, stk, p_imp, ev in cur.fetchall():
        cnt_i = int(cnt or 0)
        stk_f = float(stk or 0.0)
        c_cents = round(float(p_imp or 0.0) * 100.0, 2)
        t_spend[mkt] = t_spend.get(mkt, 0.0) + stk_f
        t_cnt[mkt] = t_cnt.get(mkt, 0) + cnt_i
        t_tranches[mkt] = t_tranches.get(mkt, 0) + 1
        t_cost_cents[mkt] = t_cost_cents.get(mkt, 0.0) + (cnt_i * c_cents)
        t_last_ev[mkt] = float(ev or 0.0)
        c_spend[city] = c_spend.get(city, 0.0) + stk_f
    conn.close()
    return t_spend, t_cnt, t_tranches, t_cost_cents, t_last_ev, c_spend


def run_demo_cycle(bankroll_usd=25.00):
    init_db()
    cfg = GuardrailConfig()
    t_spend, t_cnt, t_tranches, t_cost_cents, t_last_ev, c_spend = load_sqlite_exposure()
    cands = [
        {'city': 'SEA', 'ticker': 'KXWT-DEMO-B42.5', 'contracts': 10, 'stake_usd': 0.60, 'ask_cents': 6, 'ev': 0.31},
        {'city': 'SEA', 'ticker': 'KXWT-DEMO-B42.5', 'contracts': 10, 'stake_usd': 0.90, 'ask_cents': 9, 'ev': 0.25},
    ]
    cands.sort(key=lambda x: x['ev'], reverse=True)
    spent = 0.0
    for cand in cands:
        ok, reason = evaluate_candidate(
            cand, cfg, t_spend, t_cnt, t_tranches, t_cost_cents, t_last_ev, c_spend, spent, bankroll_usd - spent
        )
        if not ok:
            print(f"   -> [{cand['city']}] {cand['ticker']} | {reason}")
            continue
        oid = f"SIM-{uuid.uuid4().hex[:8]}" if DRY_RUN else 'LIVE-PLACEHOLDER'
        dec = 'DRY_RUN_EXECUTE' if DRY_RUN else 'LIVE_EXECUTED'
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            'INSERT INTO cycle_audit (timestamp_utc, city, market_ticker, p_true, p_implied, '
            'ev_per_contract, obi_top5, decision, contracts_sized, stake_usd, order_id) '
            "VALUES (datetime('now'), ?, ?, 0.37, ?, ?, 0.45, ?, ?, ?, ?)",
            (cand['city'], cand['ticker'], cand['ask_cents'] / 100.0, cand['ev'], dec, cand['contracts'], cand['stake_usd'], oid),
        )
        conn.commit()
        conn.close()
        spent += cand['stake_usd']
        t_spend[cand['ticker']] = t_spend.get(cand['ticker'], 0.0) + cand['stake_usd']
        t_cnt[cand['ticker']] = t_cnt.get(cand['ticker'], 0) + cand['contracts']
        t_tranches[cand['ticker']] = t_tranches.get(cand['ticker'], 0) + 1
        t_cost_cents[cand['ticker']] = t_cost_cents.get(cand['ticker'], 0.0) + (cand['contracts'] * cand['ask_cents'])
        t_last_ev[cand['ticker']] = cand['ev']
        c_spend[cand['city']] = c_spend.get(cand['city'], 0.0) + cand['stake_usd']
        print(f"   *** EXECUTED [{cand['city']}] {cand['ticker']} -> {dec} ({oid}) ***")


if __name__ == '__main__':
    run_demo_cycle()
