from dataclasses import dataclass


@dataclass
class GuardrailConfig:
    max_tranches_per_ticker: int = 3
    max_stake_per_market_usd: float = 15.00
    max_stake_per_city_usd: float = 25.00
    cash_reserve_floor_usd: float = 0.00
    tranche_ev_bump_min: float = 0.05
    high_ev_floor_override: float = 0.35


def evaluate_candidate(cand, cfg, t_spend, t_cnt, t_tranches, t_cost_cents, t_last_ev, c_spend, spent_this_cycle, remaining_budget):
    mkt = cand['ticker']
    city = cand['city']
    stake_usd = float(cand['stake_usd'])
    ask_cents = int(cand['ask_cents'])
    ev = float(cand['ev'])
    tranche_num = t_tranches.get(mkt, 0)
    if tranche_num >= cfg.max_tranches_per_ticker:
        return False, f'BLOCKED_TRANCHE_CAP ({tranche_num}/{cfg.max_tranches_per_ticker})'
    if tranche_num > 0:
        prev_cnt = max(t_cnt.get(mkt, 0), 1)
        avg_cents = t_cost_cents.get(mkt, 0.0) / prev_cnt
        prev_ev = t_last_ev.get(mkt, 0.0)
        if not (ask_cents <= avg_cents or ev >= prev_ev + cfg.tranche_ev_bump_min):
            return False, f'BLOCKED_TRANCHE_PRICE (ask={ask_cents}c vs avg={avg_cents:.1f}c, ev={ev:+.3f} vs prev={prev_ev:+.3f})'
    proj_mkt_spend = t_spend.get(mkt, 0.0) + stake_usd
    if proj_mkt_spend > cfg.max_stake_per_market_usd:
        return False, f'BLOCKED_MARKET_CAP (${proj_mkt_spend:.2f} > ${cfg.max_stake_per_market_usd:.2f})'
    proj_city_spend = c_spend.get(city, 0.0) + stake_usd + spent_this_cycle
    if proj_city_spend > cfg.max_stake_per_city_usd:
        return False, f'BLOCKED_CITY_CAP (${proj_city_spend:.2f} > ${cfg.max_stake_per_city_usd:.2f})'
    if remaining_budget < stake_usd:
        return False, 'BLOCKED_INSUFFICIENT_BUDGET'
    if (remaining_budget - stake_usd) < cfg.cash_reserve_floor_usd and ev < cfg.high_ev_floor_override:
        return False, f'BLOCKED_CASH_FLOOR (rem=${remaining_budget:.2f}, ev={ev:+.3f})'
    return True, 'APPROVED'
