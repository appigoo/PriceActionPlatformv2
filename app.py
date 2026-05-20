import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import time, hashlib

st.set_page_config(page_title="SMC Pro | Multi-Stock", page_icon="📊",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Noto+Sans+TC:wght@300;400;500;700&display=swap');
:root{--bg:#f5f2ed;--bg2:#edeae4;--card:#ffffff;--card2:#f9f7f4;--border:#e0dbd2;
  --border2:#ccc8be;--bull:#3d8c5f;--bull-bg:#eaf4ee;--bear:#c0392b;--bear-bg:#fdecea;
  --gold:#b07d2e;--gold-bg:#fdf6e3;--text:#1a1a1a;--text2:#6b6560;--text3:#9e9890;
  --accent:#4a7c6f;--mono:'IBM Plex Mono',monospace;--sans:'Noto Sans TC',sans-serif;}
html,body,[class*="css"]{font-family:var(--sans);background-color:var(--bg)!important;color:var(--text);}
.main{background-color:var(--bg)!important;}
.main .block-container{padding:1rem 1.5rem 2rem;max-width:100%;background:var(--bg);}
section[data-testid="stSidebar"]{background:var(--card)!important;border-right:1px solid var(--border)!important;}
section[data-testid="stSidebar"] *{color:var(--text)!important;}
.metric-card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:.9rem 1.1rem .8rem;}
.metric-label{font-size:.7rem;color:var(--text2);margin-bottom:5px;}
.metric-value{font-family:var(--mono);font-size:1.7rem;font-weight:700;color:var(--text);line-height:1.1;}
.metric-sub{font-size:.73rem;margin-top:3px;}
.bull{color:var(--bull);} .bear{color:var(--bear);} .gold{color:var(--gold);}
.section-heading{font-size:.95rem;font-weight:700;color:var(--text);margin:1.3rem 0 .65rem;}
.analysis-block{background:var(--card2);border:1px solid var(--border);border-left:3px solid var(--accent);
  border-radius:0 8px 8px 0;padding:1rem 1.2rem;font-size:.86rem;line-height:1.8;}
.white-card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:.85rem 1.1rem;margin-bottom:.65rem;}
.info-row{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid var(--border);font-size:.82rem;}
.info-row:last-child{border-bottom:none;}
.info-key{color:var(--text2);}
.info-val{font-family:var(--mono);font-weight:600;color:var(--text);}
.score-wrap{margin-bottom:10px;}
.score-label-row{display:flex;justify-content:space-between;font-size:.77rem;margin-bottom:4px;color:var(--text2);}
.score-num{font-family:var(--mono);font-weight:700;}
.score-bar-bg{background:var(--bg2);border-radius:3px;height:5px;overflow:hidden;}
.score-bar-fill{height:100%;border-radius:3px;}
.rating-badge{display:inline-block;padding:6px 20px;border-radius:20px;font-family:var(--mono);font-weight:700;font-size:.87rem;}
.pattern-pill{display:inline-block;border-radius:14px;padding:3px 10px;font-size:.71rem;font-family:var(--mono);margin:2px 3px 2px 0;border:1px solid;}
.pill-bull{background:var(--bull-bg);border-color:#a8d5b8;color:var(--bull);}
.pill-bear{background:var(--bear-bg);border-color:#f5b8b3;color:var(--bear);}
.pill-neutral{background:var(--bg2);border-color:var(--border2);color:var(--text2);}
/* monitor badge */
.mon-badge{display:inline-flex;align-items:center;gap:5px;background:var(--bull-bg);
  border:1px solid #a8d5b8;border-radius:20px;padding:2px 10px;font-size:.7rem;color:var(--bull);font-family:var(--mono);}
.mon-badge-off{background:var(--bg2);border-color:var(--border2);color:var(--text3);}
/* stock tab pills */
.stTabs [data-baseweb="tab"]{font-family:var(--mono);font-size:.82rem;padding:6px 14px;}
.stButton>button{background:var(--accent)!important;color:#fff!important;font-family:var(--mono)!important;
  font-weight:600!important;border:none!important;border-radius:7px!important;}
.stButton>button:hover{opacity:.88!important;}
div[data-testid="stSelectbox"]>div>div,div[data-testid="stTextInput"]>div>div{
  background:var(--bg2)!important;border-color:var(--border)!important;border-radius:7px!important;}
hr{border-color:var(--border)!important;}
</style>
""", unsafe_allow_html=True)

# ── imports ───────────────────────────────────────────────────────────────────
from analysis.data_fetcher       import fetch_ohlcv
from analysis.pattern_detector   import detect_all_patterns
from analysis.market_structure   import analyze_market_structure
from analysis.volume_analysis    import analyze_volume
from analysis.support_resistance import find_support_resistance
from analysis.smart_money        import analyze_smart_money
from analysis.signals            import generate_signals
from analysis.scoring            import compute_scores
from analysis.backtest           import run_backtest
from analysis.ai_analysis        import generate_ai_analysis
from analysis.telegram_bot       import send_telegram_alert
from charts.candlestick_chart    import build_chart

# ── session state ─────────────────────────────────────────────────────────────
def _ss(key, val):
    if key not in st.session_state: st.session_state[key] = val

_ss("stock_list",    ["TSLA", "NVDA", "META", "AAPL"])
_ss("cached",        {})      # {ticker: result_dict}
_ss("monitors",      {})      # {ticker: {levels, triggered, active}}
_ss("alert_hashes",  set())
_ss("active_tab",    0)
_ss("gap_alerts",    {})   # {ticker: {cond_key: {enabled, last_fired}}}
_ss("gap_monitor_on", False)  # 跳空監控總開關
_ss("gap_monitor_fired", {})  # {ticker_dir_hash: True} 去重

# ── helpers ───────────────────────────────────────────────────────────────────
import re as _re

def _strip_html(html: str) -> str:
    text = _re.sub('<br/?>', chr(10), html)
    text = _re.sub('<[^>]+>', '', text)
    lines = [l for l in text.split(chr(10)) if l.strip()]
    return chr(10).join(lines).strip()

def _build_tg_signal_msg(ticker, sig, trend, overall, patterns,
                          signals, volume_analysis, market_struct,
                          scores, sr_levels, interval_lbl, current_price,
                          ai_text="") -> str:
    """生成格式完整的 Telegram 交易訊號（純 Markdown）"""
    import datetime as _dt
    nl  = chr(10)
    sep = chr(8212) * 20

    # ── 基本訊號 ──────────────────────────────────────────────────────────────
    sig_icon  = "🟢 BUY 做多" if sig == "BUY" else "🔴 SELL 做空"
    sig_emoji = "🚀" if "強烈看多" in overall else ("📈" if "偏多" in overall else
                "💀" if "強烈看空" in overall else ("📉" if "偏空" in overall else "⟷"))
    confidence = scores.get('confidence', 0)

    # ── 市場結構 ──────────────────────────────────────────────────────────────
    swing    = market_struct.get('swing_desc', '-')
    reversal = _strip_html(market_struct.get('reversal_signal', ''))

    # ── 型態 ──────────────────────────────────────────────────────────────────
    sk = patterns.get('single_k',[{}])[0].get('name','-') if patterns.get('single_k') else '-'
    dk = patterns.get('double_k',[{}])[0].get('name','-') if patterns.get('double_k') else '-'
    tk = patterns.get('triple_k',[{}])[0].get('name','-') if patterns.get('triple_k') else '-'
    macro_pats = patterns.get('macro', [])
    macro_str  = ', '.join([p['name'].split()[0] for p in macro_pats[:2]]) if macro_pats else '-'

    # ── 成交量 ────────────────────────────────────────────────────────────────
    vol_sig  = volume_analysis.get('vol_signal', '-')
    vol_r    = volume_analysis.get('vol_ratio', 1.0)
    vbias    = volume_analysis.get('vol_bias', '')
    vdiv     = volume_analysis.get('vol_divergence', '')

    # ── 交易建議 ──────────────────────────────────────────────────────────────
    trade = signals.get('trade_setup', {})
    entry = current_price
    ks    = trade.get('key_support', 0)
    kr    = trade.get('key_resistance', 0)
    bp    = trade.get('breakout_level', 0)
    sl    = trade.get('stop_loss', 0)
    rrr   = trade.get('rrr', 'N/A')
    short = trade.get('short_term', '-')
    mid   = trade.get('mid_term', '-')

    # ── 支撐阻力詳細 ──────────────────────────────────────────────────────────
    supports    = sr_levels.get('supports', [])
    resistances = sr_levels.get('resistances', [])
    sup_str = ' / '.join(['$'+str(round(s,2)) for s in supports[:3]]) if supports else '-'
    res_str = ' / '.join(['$'+str(round(r,2)) for r in resistances[:3]]) if resistances else '-'
    dz = sr_levels.get('demand_zones', [])
    sz = sr_levels.get('supply_zones', [])
    dz_str = ('$'+str(round(dz[0][0],2))+'-$'+str(round(dz[0][1],2))) if dz else '-'
    sz_str = ('$'+str(round(sz[0][0],2))+'-$'+str(round(sz[0][1],2))) if sz else '-'

    # ── 綜合結論（純文字）────────────────────────────────────────────────────
    conclusion = _strip_html(ai_text)
    # 只取綜合結論段落
    if '綜合結論' in conclusion:
        idx = conclusion.find('綜合結論')
        conclusion = conclusion[idx+4:].strip()
        conclusion = conclusion[:250]  # 最多250字
    else:
        # fallback：用評級＋原因
        reasons = signals.get('buy_reasons' if sig=='BUY' else 'sell_reasons', [])
        reason_txt = ' + '.join(reasons[:4]) if reasons else ''
        conclusion = overall + '｜' + reason_txt

    # ── 組裝訊息 ──────────────────────────────────────────────────────────────
    now = _dt.datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = [
        sig_emoji + " *" + ticker + " 交易訊號*",
        sep,
        # 基本訊號
        "訊號：*" + sig_icon + "*",
        "評級：*" + overall + "*  信心 " + str(confidence) + "%",
        "時間週期：" + interval_lbl,
        "當前價格：*$" + str(round(entry, 2)) + "*",
        "",
        # 趨勢
        "📊 *市場結構*",
        "• " + trend + "（" + swing + "）",
    ]
    if reversal:
        r_clean = reversal.replace("⚠️ ", "").replace("⚠️", "").strip()
        lines.append("• ⚠️ " + r_clean)
    lines += [
        "",
        # 型態
        "📐 *K線型態*",
        "• 單K：" + sk,
        "• 雙K：" + dk,
        "• 多K：" + tk,
        "• 型態學：" + macro_str,
        "",
        # 成交量
        "📦 *成交量*",
        "• " + vol_sig + "（" + str(round(vol_r,1)) + "x均量）",
        "• " + vbias,
    ]
    if vdiv:
        lines.append("• " + vdiv)
    lines += [
        "",
        # 支撐阻力
        "🗺 *支撐與阻力*",
        "• 關鍵支撐：" + sup_str,
        "• 關鍵阻力：" + res_str,
        "• Demand Zone：" + dz_str,
        "• Supply Zone：" + sz_str,
        "",
        # 交易建議
        "💰 *交易建議*",
        "• 入市價格：*$" + str(round(entry, 2)) + "*",
        "• 短線方向：" + short,
        "• 中線方向：" + mid,
        "• 關鍵支撐：$" + str(round(ks, 2)),
        "• 關鍵阻力：$" + str(round(kr, 2)),
        "• 突破價位：$" + str(round(bp, 2)),
        "• 止損位：  *$" + str(round(sl, 2)) + "*",
        "• 風報比：  " + str(rrr),
        "",
        # 綜合結論
        "🧠 *綜合結論*",
        conclusion,
        "",
        sep,
        "_SMC Pro · " + now + "_",
    ]
    return nl.join(lines)


def _compute_gap_conditions(df) -> list:
    """計算三個收盤價條件的當前狀態"""
    if len(df) < 2:
        return []

    c = df.iloc[-1]   # 最新一根
    p = df.iloc[-2]   # 前一根

    close_c = float(c['Close'])   # 今收
    low_c   = float(c['Low'])     # 今低
    close_p = float(p['Close'])   # 前收
    high_p  = float(p['High'])    # 前高

    # ── 條件1：收盤 vs 前收（今日漲跌幅）────────────────────────────────────
    gap1_pct  = (close_c - close_p) / close_p * 100
    gap1_up   = close_c >= close_p
    gap1_fire = abs(gap1_pct) > 0.3

    if gap1_pct > 1.5:
        gap1_status = f"強勢上漲 +{gap1_pct:.2f}%（收盤大幅高於前收）"
    elif gap1_pct > 0.3:
        gap1_status = f"跳空高收 +{gap1_pct:.2f}%（收盤高於前收）"
    elif gap1_pct < -1.5:
        gap1_status = f"大幅下跌 {gap1_pct:.2f}%（收盤大幅低於前收）"
    elif gap1_pct < -0.3:
        gap1_status = f"跳空低收 {gap1_pct:.2f}%（收盤低於前收）"
    else:
        gap1_status = f"平收 ({gap1_pct:+.2f}%)（幅度不足 0.3%）"

    # ── 條件2：收盤 vs 前高（是否突破前高收盤）──────────────────────────────
    gap2_pct  = (close_c - high_p) / high_p * 100
    gap2_up   = close_c > high_p
    gap2_fire = gap2_up  # 收盤突破前高才算觸發

    if close_c > high_p:
        gap2_status = f"強勢！收盤突破前高 +{gap2_pct:.2f}%（收 ${close_c:.2f} > 前高 ${high_p:.2f}）"
    elif gap2_pct > -0.5:
        gap2_status = f"貼近前高 {gap2_pct:.2f}%（收 ${close_c:.2f} vs 前高 ${high_p:.2f}，關鍵位置）"
    else:
        gap2_status = f"低於前高 {gap2_pct:.2f}%（收 ${close_c:.2f} 未能守住前高 ${high_p:.2f}）"

    # ── 條件3：今低 vs 前高（日內最低是否守住前高支撐）──────────────────────
    gap3_pct   = (low_c - high_p) / high_p * 100
    gap3_above = low_c > high_p
    gap3_fire  = low_c > high_p  # 今低守住前高 = 強勢訊號

    if low_c > high_p:
        gap3_status = f"極強！今低守住前高之上 +{gap3_pct:.2f}%（今低 ${low_c:.2f} > 前高 ${high_p:.2f}）"
    elif gap3_pct > -0.5:
        gap3_status = f"今低貼近前高 {gap3_pct:.2f}%（${low_c:.2f} vs ${high_p:.2f}，前高支撐測試）"
    else:
        gap3_status = f"今低跌破前高 {gap3_pct:.2f}%（今低 ${low_c:.2f} < 前高 ${high_p:.2f}，前高支撐失守 ⚠️）"

    return [
        {
            "key":    "close_vs_prev_close",
            "label":  "① 收盤 vs 前收",
            "sub":    f"今收 ${close_c:.2f}  vs  前收 ${close_p:.2f}",
            "status": gap1_status,
            "fired":  gap1_fire,
            "up":     gap1_up,
            "pct":    gap1_pct,
            "icon":   "🔼" if gap1_up else "🔽",
        },
        {
            "key":    "close_vs_prev_high",
            "label":  "② 收盤 vs 前高",
            "sub":    f"今收 ${close_c:.2f}  vs  前高 ${high_p:.2f}",
            "status": gap2_status,
            "fired":  gap2_fire,
            "up":     gap2_up,
            "pct":    gap2_pct,
            "icon":   "🚀" if gap2_up else "📉",
        },
        {
            "key":    "low_vs_prev_high",
            "label":  "③ 今低 vs 前高",
            "sub":    f"今低 ${low_c:.2f}  vs  前高 ${high_p:.2f}",
            "status": gap3_status,
            "fired":  gap3_fire,
            "up":     gap3_above,
            "pct":    gap3_pct,
            "icon":   "✅" if gap3_above else "⚠️",
        },
    ]


def _render_gap_alerts(ticker: str, df, tg_token: str, tg_chat_id: str):
    """渲染跳空警報區塊 - 三個條件 + Telegram 警報開關"""
    from analysis.telegram_bot import send_telegram_alert

    conditions = _compute_gap_conditions(df)
    if not conditions:
        st.info("數據不足，無法計算跳空條件")
        return

    has_tg = bool(tg_token and tg_chat_id)

    # 初始化該股票的 gap_alerts 狀態
    if ticker not in st.session_state.gap_alerts:
        st.session_state.gap_alerts[ticker] = {
            c['key']: {"enabled": False, "last_fired": None}
            for c in conditions
        }

    ga = st.session_state.gap_alerts[ticker]

    # ── Telegram 總開關 ──────────────────────────────────────────────────────
    col_sw1, col_sw2 = st.columns([3, 1])
    with col_sw1:
        st.markdown(
            "<div style='font-size:.78rem;color:#6b6560;padding:.3rem 0'>"
            "開啟各條件的警報開關，觸發時自動發送 Telegram</div>",
            unsafe_allow_html=True
        )
    with col_sw2:
        if not has_tg:
            st.markdown(
                "<div style='font-size:.7rem;color:#c0392b;text-align:right'>"
                "⚠️ 請先填寫<br>Telegram 設定</div>",
                unsafe_allow_html=True
            )

    # ── 三個條件卡片 ─────────────────────────────────────────────────────────
    for cond in conditions:
        key      = cond['key']
        fired    = cond['fired']
        up       = cond['up']
        pct      = cond['pct']
        icon     = cond['icon']
        enabled  = ga.get(key, {}).get('enabled', False)

        # 顏色
        if fired:
            card_bg      = "#eaf4ee" if up else "#fdecea"
            card_bdr     = "#3d8c5f" if up else "#c0392b"
            val_col      = "#3d8c5f" if up else "#c0392b"
            status_badge = f"{icon} 已觸發"
        else:
            card_bg      = "#f9f7f4"
            card_bdr     = "#e0dbd2"
            val_col      = "#6b6560"
            status_badge = "○ 監控中" if enabled else "○ 未啟動"

        c_info, c_toggle = st.columns([4, 1])
        with c_info:
            st.markdown(
                f"<div style='background:{card_bg};border:1px solid {card_bdr};"
                f"border-radius:8px;padding:.65rem 1rem;margin-bottom:.4rem'>"
                f"<div style='font-size:.72rem;color:#6b6560;margin-bottom:3px'>"
                f"{cond['label']}</div>"
                f"<div style='font-family:IBM Plex Mono,monospace;font-size:.8rem;"
                f"color:#6b6560;margin-bottom:4px'>{cond['sub']}</div>"
                f"<div style='font-family:IBM Plex Mono,monospace;font-size:.82rem;"
                f"color:{val_col};font-weight:600'>{cond['status']}</div>"
                f"<div style='font-size:.68rem;color:{val_col};margin-top:3px'>"
                f"{status_badge}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        with c_toggle:
            new_enabled = st.toggle(
                "警報",
                value=enabled,
                key=f"gap_{ticker}_{key}",
                disabled=not has_tg,
                help="需先填入 Telegram Token 和 Chat ID" if not has_tg else "開啟後觸發條件時自動發送 Telegram",
            )
            if new_enabled != enabled:
                ga[key]['enabled'] = new_enabled
                st.rerun()

        # 觸發 Telegram（條件成立 + 開關開啟 + 未重複發送）
        if fired and enabled and has_tg:
            last = ga.get(key, {}).get('last_fired')
            # 每天只發一次（同一條件同一天）
            today = __import__('datetime').date.today().isoformat()
            if last != today:
                nl  = chr(10)
                sep = chr(8212) * 16
                now_str = __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')
                lines_tg = [
                    cond['icon'] + " *" + ticker + " 收盤價警報*",
                    sep,
                    "條件：" + cond['label'],
                    "數值：" + cond['sub'],
                    "結果：*" + cond['status'] + "*",
                    "幅度：" + f"{pct:+.2f}%",
                    sep,
                    "_SMC Pro · " + now_str + "_",
                ]
                msg = chr(10).join(lines_tg)
                if send_telegram_alert(tg_token, tg_chat_id, msg):
                    ga[key]['last_fired'] = today
                    st.toast(
                        f"{'🔼' if up else '🔽'} {ticker} 跳空警報已發送！",
                        icon="🔔"
                    )

def _cc(val):
    sv = str(val)
    if any(k in sv for k in ("多頭","突破","吸籌","放量","低位","看多","看漲","上漲","飆升","跳空上")): return "bull"
    if any(k in sv for k in ("空頭","派發","高位","跌破","出貨","看空","看跌","下跌","跳空下")): return "bear"
    return ""


def _analyze_close_prices(df) -> dict:
    """分析最新5根K線的收盤價行為"""
    import numpy as np
    closes = df['Close'].values
    opens  = df['Open'].values
    highs  = df['High'].values
    lows   = df['Low'].values
    n = len(df)
    if n < 2:
        return {k: '-' for k in ['latest_close_desc','last1_chg','last5_trend','price_smart','gap_desc']}

    c0 = closes[-1]   # 最新
    c1 = closes[-2]   # 前一根
    o0 = opens[-1]
    h0 = highs[-1]
    l0 = lows[-1]

    # ── 最新收盤描述 ─────────────────────────────────────────────────────────
    mean20 = float(np.mean(closes[-20:])) if n >= 20 else float(np.mean(closes))
    pos = "高位" if c0 > mean20 * 1.03 else ("低位" if c0 < mean20 * 0.97 else "中位")
    dir0 = "陽線收盤" if c0 >= o0 else "陰線收盤"
    latest_close_desc = f"{pos} · {dir0} · ${c0:.2f}"

    # ── 最新1根漲跌幅 ────────────────────────────────────────────────────────
    chg1 = (c0 - c1) / c1 * 100 if c1 > 0 else 0
    chg1_icon = "▲" if chg1 >= 0 else "▼"
    last1_chg = f"{chg1_icon} {abs(chg1):.2f}%（${c0:.2f} vs ${c1:.2f}）"

    # ── 近5根走勢 ────────────────────────────────────────────────────────────
    if n >= 5:
        c5 = closes[-5:]
        chg5 = (c5[-1] - c5[0]) / c5[0] * 100
        bull5 = sum(1 for i in range(1,5) if c5[i] > c5[i-1])
        bear5 = 4 - bull5
        # 趨勢強度：連續上漲/下跌
        streak = 1
        streak_dir = "上漲" if c5[-1] > c5[-2] else "下跌"
        for i in range(len(c5)-2, 0, -1):
            if (c5[i] > c5[i-1]) == (c5[-1] > c5[-2]):
                streak += 1
            else:
                break
        trend_desc = f"{'▲' if chg5>=0 else '▼'} {abs(chg5):.1f}%（{bull5}漲{bear5}跌，連續{streak}根{streak_dir}）"
        last5_trend = trend_desc
    else:
        chg5 = (c0 - closes[0]) / closes[0] * 100
        last5_trend = f"{'▲' if chg5>=0 else '▼'} {abs(chg5):.1f}%"

    # ── 收盤價主力動向判斷 ───────────────────────────────────────────────────
    # 收盤相對日內高低點的位置（越靠近日高 = 多方強）
    rng0 = h0 - l0
    close_pos = (c0 - l0) / rng0 if rng0 > 0 else 0.5
    if close_pos >= 0.80:
        price_smart = "收盤靠近日高（多方主導，主力護盤）"
    elif close_pos >= 0.60:
        price_smart = "收盤偏高（買方積極）"
    elif close_pos <= 0.20:
        price_smart = "收盤靠近日低（空方主導，主力打壓）"
    elif close_pos <= 0.40:
        price_smart = "收盤偏低（賣方積極）"
    else:
        price_smart = f"收盤居中（{close_pos*100:.0f}%位置，多空拉鋸）"

    # ── 跳空缺口偵測 ─────────────────────────────────────────────────────────
    h1 = highs[-2]
    l1 = lows[-2]

    gap_desc = "無跳空"
    gap_cls  = ""
    if l0 > h1:
        gap_size = (l0 - h1) / h1 * 100
        gap_desc = f"跳空向上 ↑ 缺口 +{gap_size:.2f}%（${h1:.2f} → ${l0:.2f}）"
    elif h0 < l1:
        gap_size = (l1 - h0) / l1 * 100
        gap_desc = f"跳空向下 ↓ 缺口 -{gap_size:.2f}%（${l1:.2f} → ${h0:.2f}）"
    elif abs(o0 - c1) / c1 * 100 > 0.5:
        # 小跳空（開盤與前收盤有差距）
        gap_pct = (o0 - c1) / c1 * 100
        if gap_pct > 0:
            gap_desc = f"小跳空高開 +{gap_pct:.2f}%（開盤 ${o0:.2f} 高於前收 ${c1:.2f}）"
        else:
            gap_desc = f"小跳空低開 {gap_pct:.2f}%（開盤 ${o0:.2f} 低於前收 ${c1:.2f}）"

    return {
        'latest_close_desc': latest_close_desc,
        'last1_chg':         last1_chg,
        'last5_trend':       last5_trend,
        'price_smart':       price_smart,
        'gap_desc':          gap_desc,
    }

def _row(k, v, cls=""):
    return (f"<div class='info-row'><span class='info-key'>{k}</span>"
            f"<span class='info-val {cls}'>{v}</span></div>")


def _bar(label, val, color):
    return (f"<div class='score-wrap'><div class='score-label-row'><span>{label}</span>"
            f"<span class='score-num' style='color:{color}'>{val}</span></div>"
            f"<div class='score-bar-bg'><div class='score-bar-fill' "
            f"style='width:{val}%;background:{color}'></div></div></div>")


def _build_ai_prompt(ticker, interval_lbl, df, patterns, market_struct,
                     volume_analysis, sr_levels, smart_money, signals,
                     scores, ai_text) -> str:
    """生成完整的 AI 分析 Prompt，可貼入任何 AI 進行深度分析"""
    import datetime as _dt

    current   = float(df['Close'].iloc[-1])
    prev      = float(df['Close'].iloc[-2])
    chg_pct   = (current - prev) / prev * 100

    trend     = market_struct.get('trend', '-')
    swing     = market_struct.get('swing_desc', '-')
    t_str     = market_struct.get('trend_strength', 0)
    reversal  = _strip_html(market_struct.get('reversal_signal', ''))
    ema20_sl  = market_struct.get('ema20_slope', 0)
    ema50_sl  = market_struct.get('ema50_slope', 0)

    vol_sig   = volume_analysis.get('vol_signal', '-')
    vol_r     = volume_analysis.get('vol_ratio', 1.0)
    vbias     = volume_analysis.get('vol_bias', '-')
    vdiv      = volume_analysis.get('vol_divergence', '') or '無'

    behavior  = smart_money.get('behavior', '-')
    accum     = smart_money.get('accumulation_prob', 0)
    dist      = smart_money.get('distribution_risk', 0)
    lg        = smart_money.get('liquidity_grab', '無')
    sm_desc   = _strip_html(smart_money.get('description', ''))

    sig       = signals.get('primary', 'NEUTRAL')
    strength  = signals.get('strength', '-')
    trade     = signals.get('trade_setup', {})
    overall   = scores.get('overall_rating', '-')
    conf      = scores.get('confidence', 0)

    supports    = sr_levels.get('supports', [])
    resistances = sr_levels.get('resistances', [])
    sup_str = ' / '.join([f'${s:.2f}' for s in supports[:3]]) or '-'
    res_str = ' / '.join([f'${r:.2f}' for r in resistances[:3]]) or '-'

    sk = patterns.get('single_k', [{}])[0] if patterns.get('single_k') else {}
    dk = patterns.get('double_k', [{}])[0] if patterns.get('double_k') else {}
    tk = patterns.get('triple_k', [{}])[0] if patterns.get('triple_k') else {}
    macro = patterns.get('macro', [])

    sk_str = sk.get('name', '無') + '：' + _strip_html(sk.get('desc', '')) if sk else '無'
    dk_str = dk.get('name', '無') + '：' + _strip_html(dk.get('desc', '')) if dk else '無'
    tk_str = tk.get('name', '無') + '：' + _strip_html(tk.get('desc', '')) if tk else '無'
    macro_str = chr(10).join([
        '  - ' + p.get('name','') + '：' + _strip_html(p.get('desc',''))
        for p in macro
    ]) or '  無'

    ai_summary = _strip_html(ai_text)
    now = _dt.datetime.now().strftime('%Y-%m-%d %H:%M')

    nl = chr(10)
    prompt = nl.join([
        '你是一位專業的 Price Action 交易員兼 Smart Money Concept（SMC）分析師。',
        '請根據以下完整的技術分析數據，給出你的深度分析和具體交易建議。',
        '要求：直接給出明確方向，不要模稜兩可，像真正的職業交易員一樣做決策。',
        '',
        '=' * 60,
        '【股票資訊】',
        '=' * 60,
        f'股票代號：{ticker}',
        f'時間週期：{interval_lbl}',
        f'分析時間：{now}',
        f'當前價格：${current:.2f}（較前根 {chg_pct:+.2f}%）',
        '',
        '=' * 60,
        '【市場結構】',
        '=' * 60,
        f'趨勢方向：{trend}',
        f'擺動結構：{swing}',
        f'趨勢強度：{t_str}/100',
        f'EMA20 斜率：{ema20_sl:.3f}%  EMA50 斜率：{ema50_sl:.3f}%',
        f'反轉訊號：{reversal if reversal else "無"}',
        '',
        '=' * 60,
        '【K線型態（精確位置）】',
        '=' * 60,
        f'單K型態（最新第-1根）：{sk_str}',
        f'雙K型態（最新-2,-1根）：{dk_str}',
        f'三K以上（最新-5~-1根）：{tk_str}',
        '型態學（長期結構）：',
        macro_str,
        '',
        '=' * 60,
        '【成交量分析（最新5根）】',
        '=' * 60,
        f'最新1根訊號：{vol_sig}（{vol_r:.1f}x均量）',
        f'近5根量能偏向：{vbias}',
        f'量價背離：{vdiv}',
        '',
        '=' * 60,
        '【Smart Money 主力行為】',
        '=' * 60,
        f'主力行為：{behavior}',
        f'吸籌概率：{accum}%',
        f'派發風險：{dist}%',
        f'流動性獵殺：{lg}',
        f'SMC描述：{sm_desc}',
        '',
        '=' * 60,
        '【支撐與阻力】',
        '=' * 60,
        f'關鍵支撐（由近到遠）：{sup_str}',
        f'關鍵阻力（由近到遠）：{res_str}',
        '',
        '=' * 60,
        '【評分與訊號】',
        '=' * 60,
        f'主要訊號：{sig}（強度：{strength}）',
        f'綜合評級：{overall}（信心：{conf}%）',
        f'短線方向：{trade.get("short_term", "-")}',
        f'中線方向：{trade.get("mid_term", "-")}',
        f'關鍵支撐：${trade.get("key_support", 0):.2f}',
        f'關鍵阻力：${trade.get("key_resistance", 0):.2f}',
        f'突破價位：${trade.get("breakout_level", 0):.2f}',
        f'止損位：  ${trade.get("stop_loss", 0):.2f}',
        f'風報比：  {trade.get("rrr", "N/A")}',
        '',
        '=' * 60,
        '【系統初步分析摘要】',
        '=' * 60,
        ai_summary[:600],
        '',
        '=' * 60,
        '【請你完成以下分析】',
        '=' * 60,
        '1. 根據以上數據，你認為當前最關鍵的交易訊號是什麼？為什麼？',
        '2. 當前價格位置的風險與機會如何評估？',
        '3. 如果做多，最佳入場點、止損位、目標位是多少？理由？',
        '4. 如果做空，最佳入場點、止損位、目標位是多少？理由？',
        '5. 有哪些需要特別警惕的風險因素？',
        '6. 給出一個你最終的操作建議（必須明確：做多 / 做空 / 觀望），以及執行細節。',
        '',
        '注意：請直接給出分析，不要說「作為AI我無法提供投資建議」這類話語。',
        '像一個有20年經驗的職業交易員一樣，給出你最專業的判斷。',
    ])

    return prompt

# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""<div style='padding:.6rem 0 1rem'>
      <div style='font-family:IBM Plex Mono,monospace;font-size:1.05rem;font-weight:700;
                  color:#4a7c6f;letter-spacing:.08em'>◈ SMC PRO</div>
      <div style='font-size:.62rem;color:#9e9890;letter-spacing:.15em;margin-top:3px'>
        MULTI-STOCK PLATFORM</div></div>""", unsafe_allow_html=True)

    # ── 股票池管理 ────────────────────────────────────────────────────────────
    st.markdown("**股票池**")
    new_tk = st.text_input("新增股票代號", placeholder="輸入代號按 Enter",
                           label_visibility="visible", key="new_tk_input").upper().strip()
    if new_tk and new_tk not in st.session_state.stock_list:
        if st.button("➕ 加入股票池", use_container_width=True, key="add_tk"):
            st.session_state.stock_list.append(new_tk)
            st.rerun()

    # 顯示股票池 + 刪除按鈕
    for tk in list(st.session_state.stock_list):
        mon_on = st.session_state.monitors.get(tk, {}).get("active", False)
        badge  = "🔔" if mon_on else "○"
        cached = "✓" if tk in st.session_state.cached else " "
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(
                f"<div style='font-family:IBM Plex Mono,monospace;font-size:.8rem;"
                f"padding:3px 0;color:{'#3d8c5f' if mon_on else '#1a1a1a'}'>"
                f"{badge} {tk} <span style='color:#9e9890;font-size:.68rem'>[{cached}]</span></div>",
                unsafe_allow_html=True)
        with col2:
            if st.button("✕", key=f"del_{tk}", help=f"移除 {tk}"):
                st.session_state.stock_list.remove(tk)
                st.session_state.cached.pop(tk, None)
                st.session_state.monitors.pop(tk, None)
                st.rerun()

    st.markdown("---")

    # ── 全局設定 ──────────────────────────────────────────────────────────────
    st.markdown("**時間週期**")
    interval_map = {"1分鐘":"1m","5分鐘":"5m","15分鐘":"15m",
                    "30分鐘":"30m","1小時":"1h","日線":"1d","週線":"1wk"}
    interval_lbl = st.selectbox("", list(interval_map.keys()), index=5, label_visibility="collapsed")
    interval = interval_map[interval_lbl]

    st.markdown("**K線數量**")
    bar_count = st.slider("", 50, 500, 120, 10, label_visibility="collapsed")

    st.markdown("**自動刷新**")
    refresh_map = {"關閉":0,"30秒":30,"1分鐘":60,"2分鐘":120,"5分鐘":300,"15分鐘":900}
    refresh_lbl = st.selectbox("", list(refresh_map.keys()), index=0, label_visibility="collapsed")
    refresh_sec = refresh_map[refresh_lbl]

    st.markdown("---")
    st.markdown("**Telegram 通知（選填）**")
    tg_token   = st.text_input("Bot Token",  type="password", placeholder="留空則不發送")
    tg_chat_id = st.text_input("Chat ID",    placeholder="留空則不發送")
    if tg_token:   st.session_state["_tg_token"] = tg_token
    if tg_chat_id: st.session_state["_tg_chat"]  = tg_chat_id

    # ── 跳空監控按鈕（自動刷新下方）────────────────────────────────────────
    gap_mon_on = st.session_state.gap_monitor_on
    has_tg_now = bool(st.session_state.get("_tg_token") and st.session_state.get("_tg_chat"))

    gap_btn_lbl = ("⏹ 停止跳空監控" if gap_mon_on
                   else "🚨 一鍵跳空監控" if has_tg_now
                   else "🚨 跳空監控（需填 Telegram）")
    if st.button(gap_btn_lbl, use_container_width=True, key="gap_mon_toggle",
                 disabled=(not has_tg_now and not gap_mon_on)):
        st.session_state.gap_monitor_on  = not gap_mon_on
        st.session_state.gap_monitor_fired = {}   # 切換時清空去重記錄
        st.rerun()

    # 跳空監控狀態指示
    if gap_mon_on:
        fired_cnt = len(st.session_state.gap_monitor_fired)
        st.markdown(
            f"<div style='background:#eaf4ee;border:1px solid #a8d5b8;border-radius:7px;"
            f"padding:.5rem .75rem;font-size:.72rem;color:#2d6a4f;margin-bottom:.5rem'>"
            f"🚨 跳空監控中 · {interval_lbl} · {len(st.session_state.stock_list)} 支<br>"
            f"<span style='color:#6b9e8a'>已觸發 {fired_cnt} 次提醒</span></div>",
            unsafe_allow_html=True)

    st.markdown("---")
    # 全部分析按鈕
    analyze_all = st.button("🔍 分析全部股票", use_container_width=True, key="analyze_all")

    # 監控總覽
    active_mons = [tk for tk, m in st.session_state.monitors.items() if m.get("active")]
    if active_mons:
        st.markdown(f"**🔔 監控中 ({len(active_mons)} 支)**")
        for tk in active_mons:
            m = st.session_state.monitors[tk]
            trig = len(m.get("triggered", set()))
            st.markdown(
                f"<div style='font-size:.75rem;font-family:IBM Plex Mono,monospace;"
                f"color:#3d8c5f;padding:2px 0'>{tk} · 已觸發 {trig} 次</div>",
                unsafe_allow_html=True)

    st.markdown("""<div style='margin-top:1rem;font-size:.6rem;color:#9e9890;line-height:1.7'>
    ⚠️ 本平台僅供教育研究用途<br>不構成投資建議<br>交易有風險，請自行承擔
    </div>""", unsafe_allow_html=True)


# ── 跳空歷史分析渲染 ──────────────────────────────────────────────────────────
def _render_gap_history(df, ticker: str, interval: str):
    """渲染完整跳空歷史分析區塊"""
    from analysis.gap_analysis import scan_gaps, analyze_gap_stats, generate_gap_advice
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    gaps  = scan_gaps(df)
    stats = analyze_gap_stats(gaps, df)

    up_gaps   = stats['up_gaps']
    down_gaps = stats['down_gaps']
    total     = stats['total']

    # ── 統計摘要卡片 ──────────────────────────────────────────────────────────
    sc1, sc2, sc3, sc4 = st.columns(4)
    with sc1:
        st.markdown(f"""<div class='metric-card' style='text-align:center;border-left:3px solid #3d8c5f'>
          <div class='metric-label'>向上跳空次數</div>
          <div class='metric-value' style='color:#3d8c5f;font-size:1.6rem'>{len(up_gaps)}</div>
          <div class='metric-sub' style='color:#9e9890'>Gap Up ↑</div>
        </div>""", unsafe_allow_html=True)
    with sc2:
        st.markdown(f"""<div class='metric-card' style='text-align:center;border-left:3px solid #c0392b'>
          <div class='metric-label'>向下跳空次數</div>
          <div class='metric-value' style='color:#c0392b;font-size:1.6rem'>{len(down_gaps)}</div>
          <div class='metric-sub' style='color:#9e9890'>Gap Down ↓</div>
        </div>""", unsafe_allow_html=True)
    with sc3:
        up_fill = stats['up']['fill_rate'] if stats['up']['count'] > 0 else 0
        down_fill = stats['down']['fill_rate'] if stats['down']['count'] > 0 else 0
        avg_fill = (up_fill + down_fill) / 2 if total > 0 else 0
        fill_col = "#3d8c5f" if avg_fill < 50 else "#c0392b"
        st.markdown(f"""<div class='metric-card' style='text-align:center;border-left:3px solid {fill_col}'>
          <div class='metric-label'>平均回補率</div>
          <div class='metric-value' style='color:{fill_col};font-size:1.6rem'>{avg_fill:.0f}%</div>
          <div class='metric-sub' style='color:#9e9890'>20根內</div>
        </div>""", unsafe_allow_html=True)
    with sc4:
        st.markdown(f"""<div class='metric-card' style='text-align:center;border-left:3px solid #b07d2e'>
          <div class='metric-label'>總跳空次數</div>
          <div class='metric-value' style='color:#b07d2e;font-size:1.6rem'>{total}</div>
          <div class='metric-sub' style='color:#9e9890'>{interval} 週期</div>
        </div>""", unsafe_allow_html=True)

    if total == 0:
        st.info("當前時間週期內未偵測到符合定義的跳空缺口（今低 > 前高 / 今高 < 前低）")
        return

    st.markdown("")

    # ── 後市統計表 ────────────────────────────────────────────────────────────
    st.markdown("<div class='section-heading' style='font-size:.85rem'>📊 跳空後市統計</div>",
                unsafe_allow_html=True)
    stat_cols = st.columns(2)

    for col_widget, direction, d_stats, color, icon in [
        (stat_cols[0], "向上跳空 Gap Up ↑",   stats['up'],   "#3d8c5f", "🟢"),
        (stat_cols[1], "向下跳空 Gap Down ↓", stats['down'], "#c0392b", "🔴"),
    ]:
        with col_widget:
            if d_stats['count'] == 0:
                st.markdown(f"<div class='white-card'><span style='color:#9e9890'>無{direction}記錄</span></div>",
                            unsafe_allow_html=True)
                continue
            rows = "".join([
                _row("發生次數",      str(d_stats['count'])),
                _row("平均缺口幅度",  f"{d_stats['avg_size']:.2f}%"),
                _row("20根內回補率",  f"{d_stats['fill_rate']:.0f}%"),
                _row("平均回補時間",  f"{d_stats['avg_fill_bars']:.1f} 根" if d_stats['avg_fill_bars'] > 0 else "未回補"),
                _row("次根延續率",    f"{d_stats['continue_rate']:.0f}%"),
                _row("次根平均漲跌",  f"{d_stats['avg_after1']:+.2f}%"),
                _row("3根後平均漲跌", f"{d_stats['avg_after3']:+.2f}%"),
                _row("5根後平均漲跌", f"{d_stats['avg_after5']:+.2f}%"),
            ])
            st.markdown(
                f"<div class='white-card'>"
                f"<div style='font-size:.75rem;font-weight:700;color:{color};"
                f"margin-bottom:8px'>{icon} {direction}</div>{rows}</div>",
                unsafe_allow_html=True)

    # ── K線圖：標記所有跳空 ───────────────────────────────────────────────────
    st.markdown("<div class='section-heading' style='font-size:.85rem'>📈 跳空位置走勢圖</div>",
                unsafe_allow_html=True)

    dates  = df.index
    opens  = df['Open'].values
    highs  = df['High'].values
    lows   = df['Low'].values
    closes = df['Close'].values
    vols   = df['Volume'].values
    n      = len(df)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03, row_heights=[0.72, 0.28])

    # K線
    fig.add_trace(go.Candlestick(
        x=dates, open=opens, high=highs, low=lows, close=closes,
        name="K線",
        increasing_line_color='#3d8c5f', decreasing_line_color='#c0392b',
        increasing_fillcolor='#3d8c5f',  decreasing_fillcolor='#c0392b',
        line_width=1,
    ), row=1, col=1)

    # 標記跳空區域（矩形缺口）
    for g in gaps:
        i   = g['bar_idx']
        col = 'rgba(61,140,95,0.15)' if g['direction']=='up' else 'rgba(192,57,43,0.15)'
        bdr = 'rgba(61,140,95,0.6)'  if g['direction']=='up' else 'rgba(192,57,43,0.6)'
        fig.add_hrect(y0=g['gap_low'], y1=g['gap_high'], row=1, col=1,
                      fillcolor=col, line_width=1, line_color=bdr, opacity=0.8)

    # 跳空箭頭標記
    for g in gaps[-30:]:  # 只標最近30個避免過密
        i    = g['bar_idx']
        if i >= n: continue
        d    = g['direction']
        icon = "▲" if d == 'up' else "▼"
        ypos = lows[i]*0.994  if d=='up'  else highs[i]*1.006
        col  = '#3d8c5f'      if d=='up'  else '#c0392b'
        tpos = "bottom center" if d=='up' else "top center"
        fig.add_trace(go.Scatter(
            x=[dates[i]], y=[ypos],
            mode='markers+text',
            marker=dict(symbol='triangle-up' if d=='up' else 'triangle-down',
                        color=col, size=10),
            text=[f"{icon}{g['gap_size']:.1f}%"],
            textposition=tpos,
            textfont=dict(size=8, color=col, family='IBM Plex Mono'),
            showlegend=False,
        ), row=1, col=1)

    # 成交量
    avg_v = float(np.mean(vols[-20:])) if n >= 20 else float(np.mean(vols))
    vol_colors = []
    for i in range(n):
        is_gap_bar = any(g['bar_idx']==i for g in gaps)
        if is_gap_bar:
            g_this = next(g for g in gaps if g['bar_idx']==i)
            vol_colors.append('rgba(61,140,95,0.9)' if g_this['direction']=='up'
                              else 'rgba(192,57,43,0.9)')
        elif closes[i] >= opens[i]:
            vol_colors.append('rgba(61,140,95,0.45)')
        else:
            vol_colors.append('rgba(192,57,43,0.45)')

    fig.add_trace(go.Bar(x=dates, y=vols, name="成交量",
                         marker_color=vol_colors), row=2, col=1)
    fig.add_trace(go.Scatter(x=dates, y=[avg_v]*n, name="Vol MA20",
                             line=dict(color='#b07d2e', width=1, dash='dot'),
                             opacity=0.7), row=2, col=1)

    fig.update_layout(
        plot_bgcolor='#ffffff', paper_bgcolor='#f9f7f4',
        height=520, margin=dict(l=60, r=60, t=36, b=8),
        font=dict(family='IBM Plex Mono', color='#6b6560', size=9),
        legend=dict(bgcolor='rgba(255,255,255,.8)', bordercolor='#ede9e3',
                    borderwidth=1, font=dict(size=8), orientation='h', x=0, y=1.04),
        hovermode='x unified', xaxis_rangeslider_visible=False,
        title=dict(text=f'{ticker} 跳空缺口分佈（綠=Gap Up，紅=Gap Down）',
                   font=dict(size=12, color='#6b6560'), x=0.01),
    )
    axis_style = dict(gridcolor='#ede9e3', linecolor='#e0dbd2',
                      tickfont=dict(size=8, color='#9e9890'))
    fig.update_xaxes(**axis_style)
    fig.update_yaxes(**axis_style)
    fig.update_yaxes(tickprefix='$', row=1, col=1)

    # rangebreaks
    intraday = interval in {"1m","5m","15m","30m","1h"}
    if intraday:
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat","mon"]),
                                       dict(bounds=[16,9.5], pattern="hour")])
    else:
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat","mon"])])

    st.plotly_chart(fig, use_container_width=True,
                    config={"scrollZoom": True, "displaylogo": False})

    # ── 詳細記錄表格 ──────────────────────────────────────────────────────────
    if gaps:
        st.markdown("<div class='section-heading' style='font-size:.85rem'>📋 跳空詳細記錄（最近20次）</div>",
                    unsafe_allow_html=True)

        recent_gaps = sorted(gaps, key=lambda x: x['bar_idx'], reverse=True)[:20]
        table_rows = ""
        for g in recent_gaps:
            d     = g['direction']
            color = "#3d8c5f" if d=='up' else "#c0392b"
            icon  = "▲ Gap Up" if d=='up' else "▼ Gap Down"
            bg    = "#f0f9f4" if d=='up' else "#fdf0f0"
            date_str = str(g['date'])[:16]
            vol_r = g['vol_ratio']
            vol_col = "#3d8c5f" if vol_r > 1.5 else ("#c0392b" if vol_r < 0.7 else "#6b6560")

            table_rows += (
                f"<tr style='background:{bg}'>"
                f"<td style='padding:6px 10px;font-size:.78rem;color:#6b6560'>{date_str}</td>"
                f"<td style='padding:6px 10px;font-weight:700;color:{color}'>{icon}</td>"
                f"<td style='padding:6px 10px;font-family:IBM Plex Mono,monospace;font-size:.78rem'>"
                f"${g['cur_close']:.2f}</td>"
                f"<td style='padding:6px 10px;color:{color};font-family:IBM Plex Mono,monospace;font-size:.78rem'>"
                f"+{g['gap_size']:.2f}%</td>"
                f"<td style='padding:6px 10px;color:{('#3d8c5f' if g['close_chg']>=0 else '#c0392b')};"
                f"font-family:IBM Plex Mono,monospace;font-size:.78rem'>"
                f"{g['close_chg']:+.2f}%</td>"
                f"<td style='padding:6px 10px;font-family:IBM Plex Mono,monospace;font-size:.78rem'>"
                f"{g['volume']/1e6:.1f}M</td>"
                f"<td style='padding:6px 10px;color:{vol_col};"
                f"font-family:IBM Plex Mono,monospace;font-size:.78rem'>"
                f"{vol_r:.1f}x</td>"
                f"</tr>"
            )

        st.markdown(
            f"<div style='border:1px solid #e0dbd2;border-radius:8px;overflow:hidden'>"
            f"<table style='width:100%;border-collapse:collapse'>"
            f"<thead><tr style='background:#f9f7f4;border-bottom:1.5px solid #e0dbd2'>"
            f"<th style='padding:7px 10px;text-align:left;font-size:.72rem;color:#9e9890;font-weight:600'>時間</th>"
            f"<th style='padding:7px 10px;text-align:left;font-size:.72rem;color:#9e9890;font-weight:600'>方向</th>"
            f"<th style='padding:7px 10px;text-align:left;font-size:.72rem;color:#9e9890;font-weight:600'>收盤價</th>"
            f"<th style='padding:7px 10px;text-align:left;font-size:.72rem;color:#9e9890;font-weight:600'>缺口幅度</th>"
            f"<th style='padding:7px 10px;text-align:left;font-size:.72rem;color:#9e9890;font-weight:600'>當根漲跌</th>"
            f"<th style='padding:7px 10px;text-align:left;font-size:.72rem;color:#9e9890;font-weight:600'>成交量</th>"
            f"<th style='padding:7px 10px;text-align:left;font-size:.72rem;color:#9e9890;font-weight:600'>量比</th>"
            f"</tr></thead>"
            f"<tbody>{table_rows}</tbody>"
            f"</table></div>",
            unsafe_allow_html=True
        )

    # ── 主觀交易建議 ──────────────────────────────────────────────────────────
    st.markdown("<div class='section-heading' style='font-size:.85rem'>💡 跳空交易建議</div>",
                unsafe_allow_html=True)

    # 找最近一次跳空（最新一根）
    last_gap = None
    if gaps:
        latest_idx = max(g['bar_idx'] for g in gaps)
        n_total = len(df)
        # 只有在最近5根內才算「最新跳空」
        recent = [g for g in gaps if g['bar_idx'] >= n_total - 5]
        last_gap = max(recent, key=lambda x: x['bar_idx']) if recent else None

    current_price = float(df['Close'].iloc[-1])
    advice_text = generate_gap_advice(stats, current_price, last_gap, ticker)

    advice_color = "#3d8c5f" if last_gap and last_gap['direction']=='up' else (
                   "#c0392b" if last_gap and last_gap['direction']=='down' else "#b07d2e")
    st.markdown(
        f"<div style='background:#f9f7f4;border:1px solid #e0dbd2;"
        f"border-left:3px solid {advice_color};"
        f"border-radius:0 8px 8px 0;padding:1rem 1.2rem;"
        f"font-size:.86rem;line-height:1.9;color:#1a1a1a;"
        f"white-space:pre-wrap;font-family:Noto Sans TC,sans-serif'>"
        f"{advice_text}</div>",
        unsafe_allow_html=True
    )


# ── 跳空監控核心 ──────────────────────────────────────────────────────────────
def _detect_gaps_two_bars(ticker: str, interval: str, bar_count: int) -> list[dict]:
    """
    監控最新兩根 K 線，任何一根出現跳空即記錄。
    檢查：
      pair A : bar[-1] vs bar[-2]  （最新根）
      pair B : bar[-2] vs bar[-3]  （前一根）
    回傳 list，可能含 0~2 個跳空事件。
    """
    try:
        import yfinance as yf
        from analysis.data_fetcher import INTERVAL_PERIOD_MAP, _filter_trading_hours
        from analysis.gap_analysis import scan_gaps, analyze_gap_stats

        period = INTERVAL_PERIOD_MAP.get(interval, "1d")
        df = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=True)
        if df is None or len(df) < 3:
            return []
        df = df.dropna()
        if interval in {"1m","5m","15m","30m","1h"}:
            df = _filter_trading_hours(df, interval)
        df = df[df["Volume"] > 0]
        if len(df) < 3:
            return []

        # 計算歷史統計（供 Telegram 附上回補率）
        try:
            all_gaps = scan_gaps(df)
            stats    = analyze_gap_stats(all_gaps, df)
        except Exception:
            stats = None

        found = []
        # 檢查最近兩對 K 線
        for offset in [1, 2]:      # offset=1 → bar[-1]/bar[-2]; offset=2 → bar[-2]/bar[-3]
            if len(df) < offset + 2:
                continue
            cur  = df.iloc[-(offset)]
            prev = df.iloc[-(offset+1)]

            cur_high  = float(cur['High'])
            cur_low   = float(cur['Low'])
            cur_close = float(cur['Close'])
            cur_open  = float(cur['Open'])
            cur_vol   = float(cur['Volume'])
            prev_high = float(prev['High'])
            prev_low  = float(prev['Low'])
            cur_time  = str(df.index[-offset])[:16]

            # 均量
            avg_v = float(df['Volume'].rolling(20).mean().iloc[-(offset)]) or 1.0
            vol_ratio = cur_vol / avg_v if avg_v > 0 else 1.0

            bar_label = "最新根（-1）" if offset == 1 else "前一根（-2）"

            if cur_low > prev_high:
                pct = (cur_low - prev_high) / prev_high * 100
                gap_low, gap_high = prev_high, cur_low
                direction = "up"

                # 歷史統計
                hist_txt = ""
                if stats and stats['up']['count'] > 0:
                    u = stats['up']
                    hist_txt = (f"歷史統計（{u['count']}次）："
                                f"回補率 {u['fill_rate']:.0f}%"
                                f"（平均 {u['avg_fill_bars']:.1f} 根）"
                                f"｜次根均 {u['avg_after1']:+.2f}%"
                                f"／5根後均 {u['avg_after5']:+.2f}%")

                found.append({
                    "ticker":    ticker,
                    "direction": direction,
                    "bar_label": bar_label,
                    "icon":      "🟢",
                    "label":     "向上跳空 Gap Up ↑",
                    "gap_low":   gap_low,
                    "gap_high":  gap_high,
                    "detail":    f"低 ${cur_low:.2f} > 前高 ${prev_high:.2f}",
                    "pct":       pct,
                    "cur_close": cur_close,
                    "cur_open":  cur_open,
                    "vol_ratio": vol_ratio,
                    "cur_time":  cur_time,
                    "hist_txt":  hist_txt,
                    "dedup_key": f"{ticker}_up_{cur_time}",
                })

            elif cur_high < prev_low:
                pct = (prev_low - cur_high) / prev_low * 100
                gap_low, gap_high = cur_high, prev_low
                direction = "down"

                hist_txt = ""
                if stats and stats['down']['count'] > 0:
                    d = stats['down']
                    hist_txt = (f"歷史統計（{d['count']}次）："
                                f"回補率 {d['fill_rate']:.0f}%"
                                f"（平均 {d['avg_fill_bars']:.1f} 根）"
                                f"｜次根均 {d['avg_after1']:+.2f}%"
                                f"／5根後均 {d['avg_after5']:+.2f}%")

                found.append({
                    "ticker":    ticker,
                    "direction": direction,
                    "bar_label": bar_label,
                    "icon":      "🔴",
                    "label":     "向下跳空 Gap Down ↓",
                    "gap_low":   gap_low,
                    "gap_high":  gap_high,
                    "detail":    f"高 ${cur_high:.2f} < 前低 ${prev_low:.2f}",
                    "pct":       pct,
                    "cur_close": cur_close,
                    "cur_open":  cur_open,
                    "vol_ratio": vol_ratio,
                    "cur_time":  cur_time,
                    "hist_txt":  hist_txt,
                    "dedup_key": f"{ticker}_down_{cur_time}",
                })

        return found

    except Exception:
        return []


def _run_gap_monitor(stock_list: list, interval: str, bar_count: int):
    """
    遍歷所有股票，監控最新兩根 K 線跳空。
    bar[-1] vs bar[-2]，bar[-2] vs bar[-3] 各自獨立檢查。
    附帶歷史回補率統計，讓用戶收到 Telegram 即知操作方向。
    """
    if not st.session_state.gap_monitor_on:
        return

    tg_t = st.session_state.get("_tg_token", "")
    tg_c = st.session_state.get("_tg_chat", "")
    if not tg_t or not tg_c:
        return

    from analysis.telegram_bot import send_telegram_alert
    import datetime as _dt

    for ticker in stock_list:
        gaps = _detect_gaps_two_bars(ticker, interval, bar_count)
        if not gaps:
            continue

        for gap in gaps:
            dedup_key = gap['dedup_key']
            if dedup_key in st.session_state.gap_monitor_fired:
                continue

            # 記錄已觸發
            st.session_state.gap_monitor_fired[dedup_key] = True

            # ── 組裝 Telegram 訊息 ─────────────────────────────────────────
            nl  = chr(10)
            sep = chr(8212) * 22
            now = _dt.datetime.now().strftime('%Y-%m-%d %H:%M')

            # 缺口區間
            gap_range = f"${gap['gap_low']:.2f} – ${gap['gap_high']:.2f}"

            # 操作建議（根據歷史統計自動生成）
            hist = gap.get('hist_txt', '')
            if gap['direction'] == 'up':
                if '回補率' in hist:
                    # 從 hist_txt 提取回補率數字
                    import re
                    m = re.search('回補率 ([0-9]+)%', hist)
                    fill_r = int(m.group(1)) if m else 50
                    if fill_r >= 60:
                        op_hint = f"⚠️ 歷史回補率高（{fill_r}%），建議等回補至缺口 {gap_range} 再做多"
                    else:
                        op_hint = f"🚀 歷史回補率低（{fill_r}%），可考慮順勢追多，止損缺口下沿 ${gap['gap_low']:.2f}"
                else:
                    op_hint = f"缺口區間 {gap_range}，等待價格在上沿 ${gap['gap_high']:.2f} 站穩確認"
            else:
                if '回補率' in hist:
                    import re
                    m = re.search('回補率 ([0-9]+)%', hist)
                    fill_r = int(m.group(1)) if m else 50
                    if fill_r >= 60:
                        op_hint = f"⚠️ 歷史回補率高（{fill_r}%），可輕倉逆勢做多，目標回補缺口下沿 ${gap['gap_low']:.2f}"
                    else:
                        op_hint = f"🔻 歷史回補率低（{fill_r}%），建議順勢做空，止損缺口上沿 ${gap['gap_high']:.2f}"
                else:
                    op_hint = f"缺口區間 {gap_range}，等待確認方向後再入場"

            lines = [
                gap['icon'] + " *" + ticker + " 跳空警報*",
                sep,
                "觸發根：" + gap['bar_label'],
                "方向：*" + gap['label'] + "*",
                "缺口區間：" + gap_range,
                "缺口幅度：+" + f"{gap['pct']:.2f}%",
                "當根收盤：$" + f"{gap['cur_close']:.2f}",
                "成交量比：" + f"{gap['vol_ratio']:.1f}x 均量",
                "時間：" + gap['cur_time'],
                "週期：" + interval,
            ]
            if hist:
                lines += ["", "📊 " + hist]
            lines += [
                "",
                "💡 " + op_hint,
                sep,
                "_SMC Pro · " + now + "_",
            ]
            msg = nl.join(lines)
            send_telegram_alert(tg_t, tg_c, msg)

            # 頁面 Toast
            st.toast(
                f"{gap['icon']} {ticker} {gap['bar_label']} {gap['label']} "
                f"+{gap['pct']:.2f}%",
                icon="🚨"
            )


# ── 計算單支股票 ───────────────────────────────────────────────────────────────
def compute_ticker(ticker: str) -> dict | None:
    df = fetch_ohlcv(ticker, interval, bar_count)
    if df is None or len(df) < 20:
        return None
    patterns        = detect_all_patterns(df)
    market_struct   = analyze_market_structure(df)
    volume_analysis = analyze_volume(df)
    sr_levels       = find_support_resistance(df)
    smart_money     = analyze_smart_money(df, volume_analysis)
    signals         = generate_signals(df, patterns, market_struct, volume_analysis, sr_levels)
    scores          = compute_scores(market_struct, volume_analysis, smart_money, signals)
    ai_text         = generate_ai_analysis(ticker, df, patterns, market_struct,
                                           volume_analysis, sr_levels, smart_money, signals, scores)
    return dict(ticker=ticker, interval=interval, interval_lbl=interval_lbl,
                df=df, patterns=patterns, market_struct=market_struct,
                volume_analysis=volume_analysis, sr_levels=sr_levels,
                smart_money=smart_money, signals=signals, scores=scores,
                ai_text=ai_text, tg_token=tg_token, tg_chat_id=tg_chat_id,
                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M'))


# ── 渲染單支股票分析 ───────────────────────────────────────────────────────────
def render_ticker(ctx: dict):
    ticker          = ctx["ticker"]
    interval_label  = ctx["interval_lbl"]
    df              = ctx["df"]
    patterns        = ctx["patterns"]
    market_struct   = ctx["market_struct"]
    volume_analysis = ctx["volume_analysis"]
    sr_levels       = ctx["sr_levels"]
    smart_money     = ctx["smart_money"]
    signals         = ctx["signals"]
    scores          = ctx["scores"]
    ai_text         = ctx["ai_text"]
    tg_token        = ctx["tg_token"]
    tg_chat_id      = ctx["tg_chat_id"]

    latest    = df.iloc[-1];  prev = df.iloc[-2]
    price_chg = latest['Close'] - prev['Close']
    price_pct = price_chg / prev['Close'] * 100
    vol_avg   = df['Volume'].rolling(20).mean().iloc[-1]
    vol_ratio = latest['Volume'] / vol_avg if vol_avg > 0 else 1.0
    trend     = market_struct.get('trend','橫盤整理')
    sig       = signals.get('primary','NEUTRAL')
    overall   = scores.get('overall_rating','中性 ⟷')

    chg_cls  = "bull" if price_chg >= 0 else "bear"
    chg_icon = "▲" if price_chg >= 0 else "▼"
    sig_icon = "🟢" if sig=="BUY" else ("🔴" if sig=="SELL" else "🟡")
    r_col    = "#3d8c5f" if "看多" in overall else ("#c0392b" if "看空" in overall else "#b07d2e")
    mon_on   = st.session_state.monitors.get(ticker, {}).get("active", False)

    # header
    ts = ctx['timestamp']
    mon_badge_html = '<span class="mon-badge">🔔 監控中</span>' if mon_on else ''
    st.markdown(
        f"<div style='display:flex;align-items:baseline;gap:10px;padding:.3rem 0 .8rem'>"
        f"<span style='font-family:IBM Plex Mono,monospace;font-size:1.6rem;font-weight:700'>{ticker}</span>"
        f"<span style='font-size:.7rem;color:#9e9890;margin-left:8px'>{interval_label} · SMC + Price Action</span>"
        f"{mon_badge_html}"
        f"<span style='margin-left:auto;font-size:.66rem;color:#b8b2aa;font-family:IBM Plex Mono,monospace'>{ts}</span>"
        f"</div>",
        unsafe_allow_html=True
    )

    # metric cards
    c1,c2,c3,c4,c5 = st.columns(5)
    with c1:
        st.markdown(f"""<div class='metric-card'>
          <div class='metric-label'>最新收盤</div>
          <div class='metric-value'>${latest['Close']:.2f}</div>
          <div class='metric-sub {chg_cls}'>{chg_icon} {abs(price_chg):.2f} ({abs(price_pct):.2f}%)</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        tc = "bull" if "多頭" in trend else ("bear" if "空頭" in trend else "gold")
        st.markdown(f"""<div class='metric-card'>
          <div class='metric-label'>趨勢結構</div>
          <div class='metric-value {tc}' style='font-size:1.05rem;padding-top:5px'>{trend}</div>
          <div class='metric-sub' style='color:#9e9890'>{market_struct.get('swing_desc','')}</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        vc = "bull" if vol_ratio>1.5 else ("bear" if vol_ratio<0.5 else "gold")
        st.markdown(f"""<div class='metric-card'>
          <div class='metric-label'>成交量比率</div>
          <div class='metric-value {vc}'>{vol_ratio:.1f}x</div>
          <div class='metric-sub' style='color:#9e9890'>{volume_analysis.get('vol_signal','')}</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        sc2 = "bull" if sig=="BUY" else ("bear" if sig=="SELL" else "gold")
        st.markdown(f"""<div class='metric-card'>
          <div class='metric-label'>主要訊號</div>
          <div class='metric-value {sc2}' style='font-size:1.35rem;padding-top:4px'>{sig_icon} {sig}</div>
          <div class='metric-sub' style='color:#9e9890'>{signals.get('strength','')}</div>
        </div>""", unsafe_allow_html=True)
    with c5:
        st.markdown(f"""<div class='metric-card'>
          <div class='metric-label'>綜合評級</div>
          <div class='metric-value' style='font-size:.95rem;color:{r_col};padding-top:7px'>{overall}</div>
          <div class='metric-sub' style='color:#9e9890'>信心 {scores.get('confidence',0)}%</div>
        </div>""", unsafe_allow_html=True)

    # chart
    st.markdown("<div class='section-heading'>📈 K線圖表 · 市場結構 · 訊號</div>", unsafe_allow_html=True)
    fig = build_chart(df, ticker, interval, sr_levels, signals, market_struct, patterns)
    st.plotly_chart(fig, use_container_width=True, config={"scrollZoom":True,"displaylogo":False})

    col_l, col_r = st.columns([3, 2])
    with col_l:
        st.markdown("<div class='section-heading'>🧠 AI 綜合分析</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='analysis-block'>{ai_text}</div>", unsafe_allow_html=True)

        # ── AI Prompt 生成按鈕 ───────────────────────────────────────────────
        st.markdown("""<div style='font-size:.7rem;color:#9e9890;margin:.6rem 0 .4rem;
            letter-spacing:.05em'>📋 生成 Prompt · 複製後貼入任意 AI 進行深度分析</div>""",
            unsafe_allow_html=True)
        _prompt_key = f"ai_prompt_{ticker}"
        if _prompt_key not in st.session_state:
            st.session_state[_prompt_key] = ""
        pb1, pb2, pb3, pb4 = st.columns(4)
        _ai_labels = [
            ("pb1", pb1, "📋 Claude"),
            ("pb2", pb2, "📋 ChatGPT"),
            ("pb3", pb3, "📋 Gemini"),
            ("pb4", pb4, "📋 Grok"),
        ]
        for _key, _col, _lbl in _ai_labels:
            with _col:
                if st.button(_lbl, use_container_width=True, key=f"prompt_{_key}_{ticker}"):
                    st.session_state[_prompt_key] = _build_ai_prompt(
                        ticker, interval_label, df, patterns, market_struct,
                        volume_analysis, sr_levels, smart_money, signals,
                        scores, ai_text
                    )
        if st.session_state[_prompt_key]:
            st.text_area(
                "📋 已生成 Prompt（全選複製後貼入 AI）",
                value=st.session_state[_prompt_key],
                height=220,
                key=f"prompt_area_{ticker}",
            )
            st.caption("💡 點擊文字框 → Ctrl+A 全選 → Ctrl+C 複製")

        st.markdown("<div class='section-heading'>📐 市場結構</div>", unsafe_allow_html=True)
        st.markdown(f"""<div class='white-card'>
          {_row("趨勢方向",  trend,                                       _cc(trend))}
          {_row("擺動結構",  market_struct.get('swing_desc','-'),         _cc(market_struct.get('swing_desc','')))}
          {_row("趨勢強度",  f"{market_struct.get('trend_strength',0)}/100")}
          {_row("市場狀態",  market_struct.get('market_state','-'))}
          {_row("結構突破",  market_struct.get('structure_break','-'),    _cc(market_struct.get('structure_break','')))}
        </div>""", unsafe_allow_html=True)

        st.markdown("<div class='section-heading'>💰 Smart Money 主力行為</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='analysis-block' style='border-left-color:#b07d2e'>{smart_money.get('description','')}</div>", unsafe_allow_html=True)
        st.markdown(f"""<div class='white-card'>
          {_row("主力行為",   smart_money.get('behavior','-'),            _cc(smart_money.get('behavior','')))}
          {_row("吸籌概率",   f"{smart_money.get('accumulation_prob',0)}%")}
          {_row("派發風險",   f"{smart_money.get('distribution_risk',0)}%")}
          {_row("流動性獵殺", smart_money.get('liquidity_grab','-'))}
          {_row("假突破風險", smart_money.get('fakeout_risk','-'))}
        </div>""", unsafe_allow_html=True)

    with col_r:
        # scores
        st.markdown("<div class='section-heading'>📊 評分系統</div>", unsafe_allow_html=True)
        r_bg = "#eaf4ee" if "看多" in overall else ("#fdecea" if "看空" in overall else "#fdf6e3")
        sh = (_bar("趨勢強度",     scores.get('trend_strength',0),     "#4a7c6f") +
              _bar("主力吸籌概率", scores.get('accumulation_score',0), "#3d8c5f") +
              _bar("主力出貨風險", scores.get('distribution_score',0), "#c0392b") +
              _bar("突破成功率",   scores.get('breakout_score',0),     "#b07d2e") +
              _bar("假突破風險",   scores.get('fakeout_score',0),      "#c0706a") +
              f"<div style='text-align:center;margin-top:1rem'>"
              f"<div class='rating-badge' style='background:{r_bg};border:1.5px solid {r_col};color:{r_col}'>"
              f"{overall}</div></div>")
        st.markdown(f"<div class='white-card'>{sh}</div>", unsafe_allow_html=True)

        # trade setup + monitor button
        st.markdown("<div class='section-heading'>📋 交易建議</div>", unsafe_allow_html=True)
        trade = signals.get('trade_setup', {})
        _ks = trade.get('key_support',0)
        _kr = trade.get('key_resistance',0)
        _bp = trade.get('breakout_level',0)
        _sl = trade.get('stop_loss',0)
        st.markdown(f"""<div class='white-card'>
          {_row("短線方向", trade.get('short_term','-'),  _cc(trade.get('short_term','')))}
          {_row("中線方向", trade.get('mid_term','-'),    _cc(trade.get('mid_term','')))}
          {_row("關鍵支撐", f"${_ks:.2f}")}
          {_row("關鍵阻力", f"${_kr:.2f}")}
          {_row("突破價位", f"${_bp:.2f}")}
          {_row("止損位",   f"${_sl:.2f}", "bear")}
          {_row("風報比",   trade.get('rrr','-'))}
        </div>""", unsafe_allow_html=True)

        # ── 監控按鈕（該股票獨立）────────────────────────────────────────────
        mon = st.session_state.monitors.get(ticker, {})
        mon_active = mon.get("active", False)
        has_tg = bool(st.session_state.get("_tg_token") and st.session_state.get("_tg_chat"))

        if mon_active:
            trig_ct = len(mon.get("triggered", set()))
            st.markdown(f"""<div style='background:#eaf4ee;border:1.5px solid #3d8c5f;
                border-radius:8px;padding:.65rem 1rem;margin-bottom:.5rem;font-size:.78rem'>
              <span style='color:#3d8c5f;font-weight:700'>🔔 監控中</span>
              <span style='color:#6b6560;margin-left:8px;font-family:IBM Plex Mono,monospace;font-size:.72rem'>
                支撐${_ks:.2f} / 阻力${_kr:.2f} / 突破${_bp:.2f} / 止損${_sl:.2f}</span>
              <span style='float:right;color:#9e9890;font-size:.68rem'>已觸發 {trig_ct} 次</span>
            </div>""", unsafe_allow_html=True)
            if st.button(f"⏹ 停止監控 {ticker}", use_container_width=True, key=f"stop_{ticker}"):
                st.session_state.monitors.pop(ticker, None)
                st.rerun()
        else:
            btn_lbl = f"🔔 一鍵監控 {ticker}" if has_tg else f"🔔 監控 {ticker}（請先填 Telegram）"
            if st.button(btn_lbl, use_container_width=True,
                         key=f"start_{ticker}", disabled=not has_tg):
                st.session_state.monitors[ticker] = {
                    "active": True,
                    "triggered": set(),
                    "levels": {
                        "關鍵支撐": {"price":_ks, "direction":"below", "icon":"🟢"},
                        "關鍵阻力": {"price":_kr, "direction":"above", "icon":"🔴"},
                        "突破價位": {"price":_bp, "direction":"above", "icon":"🚀"},
                        "止損位":   {"price":_sl, "direction":"below", "icon":"🛑"},
                    }
                }
                st.rerun()

        # patterns
        st.markdown("<div class='section-heading'>🕯️ K線型態</div>", unsafe_allow_html=True)
        all_pats = (patterns.get('single_k',[]) + patterns.get('double_k',[]) +
                    patterns.get('triple_k',[]) + patterns.get('macro',[]))
        pills = ""
        for p in all_pats:
            cls = "pill-bull" if p['bias']=='bull' else ("pill-bear" if p['bias']=='bear' else "pill-neutral")
            pills += f"<span class='pattern-pill {cls}'>{p['name']}</span>"
        if not pills:
            pills = "<span style='color:#9e9890;font-size:.78rem'>未偵測到明顯型態</span>"
        st.markdown(f"<div class='white-card' style='line-height:2.2'>{pills}</div>", unsafe_allow_html=True)

        # volume
        st.markdown("<div class='section-heading'>📦 成交量（最新5根）</div>", unsafe_allow_html=True)
        r5    = volume_analysis.get('recent5_ratio',1.0)
        vbias = volume_analysis.get('vol_bias','')
        vdiv  = volume_analysis.get('vol_divergence','') or '無'
        st.markdown(f"""<div class='white-card'>
          {_row("最新1根訊號", volume_analysis.get('vol_signal','-'),  _cc(volume_analysis.get('vol_signal','')))}
          {_row("最新1根量比", f"{vol_ratio:.1f}x 均量")}
          {_row("近5根量比",   f"{r5:.1f}x · {vbias}",
                "bull" if "多頭" in vbias else ("bear" if "空頭" in vbias else ""))}
          {_row("主力動向",   volume_analysis.get('smart_vol','-'),   _cc(volume_analysis.get('smart_vol','')))}
          {_row("量價背離",   vdiv)}
        </div>""", unsafe_allow_html=True)

        # ── 收盤價分析（最新5根）─────────────────────────────────────────────
        st.markdown("<div class='section-heading'>💹 收盤價分析（最新5根）</div>", unsafe_allow_html=True)
        price_analysis = _analyze_close_prices(df)
        pa = price_analysis
        st.markdown(f"""<div class='white-card'>
          {_row("最新收盤",    pa['latest_close_desc'],             _cc(pa['latest_close_desc']))}
          {_row("最新1根漲跌", pa['last1_chg'],                     _cc(pa['last1_chg']))}
          {_row("近5根走勢",   pa['last5_trend'],                   _cc(pa['last5_trend']))}
          {_row("主力動向",    pa['price_smart'],                   _cc(pa['price_smart']))}
          {_row("跳空缺口",    pa['gap_desc'],                      _cc(pa['gap_desc']))}
        </div>""", unsafe_allow_html=True)

        # ── 跳空警報區塊 ──────────────────────────────────────────────────────
        st.markdown("<div class='section-heading'>🚨 跳空警報</div>", unsafe_allow_html=True)
        _render_gap_alerts(ticker, df, tg_token, tg_chat_id)

    # backtest
    st.markdown("<div class='section-heading'>📉 回測系統</div>", unsafe_allow_html=True)
    bt = run_backtest(df, signals.get('signal_history',[]))
    bc = st.columns(5)
    for col,(lbl,val,good) in zip(bc,[
        ("勝率",     f"{bt.get('win_rate',0):.1f}%",    bt.get('win_rate',0)>50),
        ("盈虧比",   f"{bt.get('profit_factor',0):.2f}", bt.get('profit_factor',0)>1.5),
        ("最大回撤", f"{bt.get('max_dd',0):.1f}%",       bt.get('max_dd',0)<15),
        ("交易次數", str(bt.get('total_trades',0)),       True),
        ("淨收益率", f"{bt.get('net_return',0):.1f}%",   bt.get('net_return',0)>0),
    ]):
        color = "#3d8c5f" if good else "#c0392b"
        with col:
            st.markdown(f"""<div class='metric-card' style='text-align:center'>
              <div class='metric-label'>{lbl}</div>
              <div class='metric-value' style='color:{color};font-size:1.3rem'>{val}</div>
            </div>""", unsafe_allow_html=True)

    # equity curve
    eq = bt.get('equity_curve',[])
    if len(eq) > 2:
        ec = "#3d8c5f" if eq[-1]>=eq[0] else "#c0392b"
        ef = "rgba(61,140,95,.08)" if eq[-1]>=eq[0] else "rgba(192,57,43,.08)"
        efig = go.Figure()
        efig.add_trace(go.Scatter(y=eq,mode='lines',line=dict(color=ec,width=2),
                                  fill='tozeroy',fillcolor=ef))
        efig.update_layout(plot_bgcolor='#fff',paper_bgcolor='#f9f7f4',height=160,
            margin=dict(l=45,r=15,t=28,b=25),showlegend=False,
            title=dict(text='Equity Curve',font=dict(family='Noto Sans TC',size=11,color='#6b6560'),x=.01),
            xaxis=dict(showgrid=False,tickfont=dict(size=8,color='#9e9890')),
            yaxis=dict(gridcolor='#ede9e3',tickfont=dict(size=8,color='#9e9890')))
        st.plotly_chart(efig, use_container_width=True)

    # ── 跳空歷史分析區塊 ─────────────────────────────────────────────────────
    st.markdown("<div class='section-heading'>🕳️ 跳空歷史分析</div>", unsafe_allow_html=True)
    _render_gap_history(df, ticker, interval)

    # Telegram signal alert (BUY/SELL) - 純文字格式，無 HTML
    if tg_token and tg_chat_id and sig in ('BUY','SELL'):
        h = hashlib.md5(f"{ticker}{interval}{sig}{datetime.now().strftime('%Y%m%d%H')}".encode()).hexdigest()
        if h not in st.session_state.alert_hashes:
            msg = _build_tg_signal_msg(
                            ticker, sig, trend, overall, patterns,
                            signals, volume_analysis, market_struct,
                            scores, sr_levels, interval_label,
                            float(latest['Close']), ai_text)
            if send_telegram_alert(tg_token, tg_chat_id, msg):
                st.session_state.alert_hashes.add(h)
                st.success(f"📱 {ticker} Telegram 訊號已發送")


# ── 背景監控（所有股票）────────────────────────────────────────────────────────
def run_all_monitors():
    active = {tk: m for tk, m in st.session_state.monitors.items() if m.get("active")}
    if not active: return
    tg_t = st.session_state.get("_tg_token","")
    tg_c = st.session_state.get("_tg_chat","")
    if not tg_t or not tg_c: return

    import yfinance as yf
    for ticker, mon in active.items():
        try:
            cur = float(yf.Ticker(ticker).fast_info.last_price)
        except Exception:
            continue
        for label, cfg in mon["levels"].items():
            key = f"{ticker}_{label}_{cfg['price']:.2f}"
            if key in mon["triggered"]: continue
            hit = ((cfg["direction"]=="above" and cur >= cfg["price"]) or
                   (cfg["direction"]=="below" and cur <= cfg["price"]))
            if hit:
                mon["triggered"].add(key)
                arrow = "突破 ↑" if cfg["direction"]=="above" else "跌破 ↓"
                msg = (f"{cfg['icon']} *{ticker} 價位觸及*\n\n"
                       f"觸發：*{label}*\n監控價：${cfg['price']:.2f}\n"
                       f"當前價：${cur:.2f}\n方向：{arrow}\n"
                       f"時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                send_telegram_alert(tg_t, tg_c, msg)
                st.toast(f"{cfg['icon']} {ticker} {label} ${cfg['price']:.2f} 已觸及！", icon="🔔")

run_all_monitors()


# ── 主介面：多股票 Tabs ────────────────────────────────────────────────────────
stock_list = st.session_state.stock_list
_run_gap_monitor(stock_list, interval, bar_count)
if not stock_list:
    st.info("請在左側股票池新增股票代號")
    st.stop()

# 「分析全部」按鈕
if analyze_all:
    progress = st.progress(0, text="分析中...")
    for i, tk in enumerate(stock_list):
        progress.progress((i+1)/len(stock_list), text=f"正在分析 {tk}...")
        result = compute_ticker(tk)
        if result:
            st.session_state.cached[tk] = result
        else:
            st.warning(f"⚠️ {tk} 數據獲取失敗")
    progress.empty()
    st.rerun()

# 個別分析按鈕：放在 Tab 內部，由 render_ticker 處理

# Tabs
tab_labels = []
for tk in stock_list:
    cached_ok = tk in st.session_state.cached
    mon_on    = st.session_state.monitors.get(tk,{}).get("active",False)
    prefix    = "🔔 " if mon_on else ("✓ " if cached_ok else "○ ")
    tab_labels.append(f"{prefix}{tk}")

tabs = st.tabs(tab_labels)
for tab, tk in zip(tabs, stock_list):
    with tab:
        if tk in st.session_state.cached:
            render_ticker(st.session_state.cached[tk])
        else:
            st.markdown(
                f"<div style='text-align:center;padding:3rem 2rem;color:#b8b2aa'>"
                f"<div style='font-size:2rem;margin-bottom:.8rem;color:#ccc8be'>◈</div>"
                f"<div style='font-size:.9rem;color:#9e9890'>{tk} 尚未分析</div>"
                f"</div>",
                unsafe_allow_html=True
            )
            c_btn = st.columns([1, 2, 1])
            with c_btn[1]:
                if st.button(f"🔍 分析 {tk}", use_container_width=True, key=f"single_{tk}"):
                    with st.spinner(f"正在分析 {tk}..."):
                        result = compute_ticker(tk)
                    if result:
                        st.session_state.cached[tk] = result
                        st.rerun()
                    else:
                        st.error(f"❌ {tk} 數據獲取失敗，請確認代號是否正確")

# 自動刷新
if refresh_sec > 0 and st.session_state.cached:
    time.sleep(refresh_sec)
    for tk in list(st.session_state.cached.keys()):
        result = compute_ticker(tk)
        if result: st.session_state.cached[tk] = result
    st.rerun()
elif st.session_state.monitors and any(m.get("active") for m in st.session_state.monitors.values()):
    time.sleep(30)
    st.rerun()
