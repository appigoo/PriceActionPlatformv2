"""
跳空歷史分析模組
- 掃描全部歷史數據找出所有跳空事件
- 統計跳空後走勢（回補率、平均漲跌）
- 生成主觀交易建議
"""
import numpy as np
import pandas as pd


# ── 核心定義 ──────────────────────────────────────────────────────────────────
# Gap Up  : current_low  > prev_high  → 向上缺口
# Gap Down: current_high < prev_low   → 向下缺口


def scan_gaps(df: pd.DataFrame) -> list[dict]:
    """掃描所有跳空事件，返回詳細記錄列表"""
    gaps = []
    closes = df['Close'].values
    opens  = df['Open'].values
    highs  = df['High'].values
    lows   = df['Low'].values
    vols   = df['Volume'].values
    dates  = df.index
    n      = len(df)

    avg_vol20 = np.convolve(vols, np.ones(20)/20, mode='full')[:n]

    for i in range(1, n):
        cur_high  = float(highs[i])
        cur_low   = float(lows[i])
        cur_close = float(closes[i])
        cur_open  = float(opens[i])
        cur_vol   = float(vols[i])
        prev_high = float(highs[i-1])
        prev_low  = float(lows[i-1])
        prev_close= float(closes[i-1])

        avg_v = float(avg_vol20[i]) if avg_vol20[i] > 0 else 1.0
        vol_ratio = cur_vol / avg_v

        # 跳空幅度
        if cur_low > prev_high:
            direction = "up"
            gap_size  = (cur_low - prev_high) / prev_high * 100
            gap_low   = prev_high
            gap_high  = cur_low
        elif cur_high < prev_low:
            direction = "down"
            gap_size  = (prev_low - cur_high) / prev_low * 100
            gap_low   = cur_high
            gap_high  = prev_low
        else:
            continue

        # 收盤漲跌幅
        close_chg = (cur_close - prev_close) / prev_close * 100

        # 跳空後 N 根的走勢（後5根）
        future_closes = []
        for j in range(1, 6):
            if i + j < n:
                future_closes.append(float(closes[i + j]))

        gaps.append({
            "bar_idx":      i,
            "date":         dates[i],
            "direction":    direction,
            "gap_size":     gap_size,
            "gap_low":      gap_low,
            "gap_high":     gap_high,
            "cur_close":    cur_close,
            "cur_open":     cur_open,
            "cur_high":     cur_high,
            "cur_low":      cur_low,
            "prev_high":    prev_high,
            "prev_low":     prev_low,
            "close_chg":    close_chg,
            "volume":       cur_vol,
            "vol_ratio":    vol_ratio,
            "future_closes": future_closes,
        })

    return gaps


def analyze_gap_stats(gaps: list[dict], df: pd.DataFrame) -> dict:
    """統計跳空後行為：回補率、平均後市漲跌、平均回補時間"""
    closes = df['Close'].values
    highs  = df['High'].values
    lows   = df['Low'].values
    n      = len(df)

    up_gaps   = [g for g in gaps if g['direction'] == 'up']
    down_gaps = [g for g in gaps if g['direction'] == 'down']

    def calc_stats(gap_list, direction):
        if not gap_list:
            return {
                'count': 0, 'avg_size': 0,
                'fill_rate': 0, 'avg_fill_bars': 0,
                'avg_after1': 0, 'avg_after3': 0, 'avg_after5': 0,
                'continue_rate': 0,
            }

        fill_count = 0
        fill_bars_list = []
        after1_list, after3_list, after5_list = [], [], []
        continue_count = 0

        for g in gap_list:
            i  = g['bar_idx']
            c0 = g['cur_close']
            gl = g['gap_low']
            gh = g['gap_high']

            # 後市漲跌（相對跳空當根收盤）
            fc = g['future_closes']
            if len(fc) >= 1:
                after1_list.append((fc[0] - c0) / c0 * 100)
            if len(fc) >= 3:
                after3_list.append((fc[2] - c0) / c0 * 100)
            if len(fc) >= 5:
                after5_list.append((fc[4] - c0) / c0 * 100)

            # 順勢延續（跳空方向繼續）
            if len(fc) >= 1:
                if direction == 'up'   and fc[0] > c0: continue_count += 1
                if direction == 'down' and fc[0] < c0: continue_count += 1

            # 缺口回補：後續某根K線觸及缺口區間
            filled = False
            for j in range(i+1, min(i+21, n)):
                if direction == 'up':
                    # Gap Up 回補：後續低點 <= gap_low（前高）
                    if lows[j] <= gh:
                        fill_count += 1
                        fill_bars_list.append(j - i)
                        filled = True
                        break
                else:
                    # Gap Down 回補：後續高點 >= gap_high（前低）
                    if highs[j] >= gl:
                        fill_count += 1
                        fill_bars_list.append(j - i)
                        filled = True
                        break

        cnt = len(gap_list)
        return {
            'count':          cnt,
            'avg_size':       float(np.mean([g['gap_size'] for g in gap_list])),
            'fill_rate':      fill_count / cnt * 100,
            'avg_fill_bars':  float(np.mean(fill_bars_list)) if fill_bars_list else 0,
            'avg_after1':     float(np.mean(after1_list))    if after1_list  else 0,
            'avg_after3':     float(np.mean(after3_list))    if after3_list  else 0,
            'avg_after5':     float(np.mean(after5_list))    if after5_list  else 0,
            'continue_rate':  continue_count / cnt * 100,
        }

    up_stats   = calc_stats(up_gaps,   'up')
    down_stats = calc_stats(down_gaps, 'down')

    return {
        'up':   up_stats,
        'down': down_stats,
        'total': len(gaps),
        'up_gaps':   up_gaps,
        'down_gaps': down_gaps,
    }


def generate_gap_advice(stats: dict, current_price: float,
                         last_gap: dict | None, ticker: str) -> str:
    """根據統計數據生成主觀交易建議"""
    up   = stats['up']
    down = stats['down']

    lines = []

    # ── 整體跳空特性 ──────────────────────────────────────────────────────────
    if stats['total'] == 0:
        return f"{ticker} 在當前時間週期內未偵測到符合定義的跳空缺口，無法生成建議。"

    lines.append(f"【{ticker} 跳空行為規律分析】")
    lines.append("")

    # Gap Up 規律
    if up['count'] > 0:
        fill_char = "容易回補" if up['fill_rate'] > 60 else ("難以回補" if up['fill_rate'] < 35 else "回補率中等")
        cont_char = "傾向繼續上漲" if up['continue_rate'] > 55 else ("傾向回落" if up['continue_rate'] < 45 else "方向不確定")
        lines.append(f"▸ 向上跳空（{up['count']}次）：平均缺口 {up['avg_size']:.2f}%，"
                     f"20根內回補率 {up['fill_rate']:.0f}%（{fill_char}），"
                     f"次根{cont_char}（{up['continue_rate']:.0f}%）。")
        lines.append(f"  後市均表現：次根 {up['avg_after1']:+.2f}% / 3根後 {up['avg_after3']:+.2f}% / 5根後 {up['avg_after5']:+.2f}%")

    # Gap Down 規律
    if down['count'] > 0:
        fill_char = "容易回補" if down['fill_rate'] > 60 else ("難以回補" if down['fill_rate'] < 35 else "回補率中等")
        cont_char = "傾向繼續下跌" if down['continue_rate'] > 55 else ("傾向反彈" if down['continue_rate'] < 45 else "方向不確定")
        lines.append(f"▸ 向下跳空（{down['count']}次）：平均缺口 {down['avg_size']:.2f}%，"
                     f"20根內回補率 {down['fill_rate']:.0f}%（{fill_char}），"
                     f"次根{cont_char}（{down['continue_rate']:.0f}%）。")
        lines.append(f"  後市均表現：次根 {down['avg_after1']:+.2f}% / 3根後 {down['avg_after3']:+.2f}% / 5根後 {down['avg_after5']:+.2f}%")

    lines.append("")

    # ── 最新跳空的具體建議 ────────────────────────────────────────────────────
    if last_gap:
        d   = last_gap['direction']
        sz  = last_gap['gap_size']
        gl  = last_gap['gap_low']
        gh  = last_gap['gap_high']
        ref = stats[d]

        lines.append("【最新跳空交易建議】")

        if d == 'up':
            fill_r = ref['fill_rate']
            cont_r = ref['continue_rate']
            a1     = ref['avg_after1']

            if cont_r > 60 and fill_r < 40:
                advice = (f"🟢 強勢向上跳空，歷史上 {cont_r:.0f}% 機率繼續上漲，"
                          f"缺口回補率僅 {fill_r:.0f}%。"
                          f"建議：可順勢追多，以缺口上沿 ${gh:.2f} 為支撐，"
                          f"跌破缺口下沿 ${gl:.2f} 立即止損。")
            elif fill_r > 60:
                advice = (f"⚠️ 向上跳空但歷史回補率高達 {fill_r:.0f}%，"
                          f"缺口區間 ${gl:.2f}–${gh:.2f} 大概率會被回測。"
                          f"建議：不追高，等待回補缺口至 ${gl:.2f}–${gh:.2f} 附近再入場做多，"
                          f"止損設在缺口下沿 ${gl:.2f} 以下。")
            else:
                advice = (f"🟡 向上跳空，歷史數據顯示方向不確定（延續率 {cont_r:.0f}%，回補率 {fill_r:.0f}%）。"
                          f"建議：觀望，等待價格在缺口上沿 ${gh:.2f} 上方站穩後再做多，"
                          f"或等缺口回補至 ${gl:.2f} 後確認支撐再入場。")

        else:  # down
            fill_r = ref['fill_rate']
            cont_r = ref['continue_rate']

            if cont_r > 60 and fill_r < 40:
                advice = (f"🔴 強勢向下跳空，歷史上 {cont_r:.0f}% 機率繼續下跌，"
                          f"缺口回補率僅 {fill_r:.0f}%。"
                          f"建議：不要抄底，可考慮順勢做空，以缺口下沿 ${gl:.2f} 為阻力，"
                          f"收盤重新回補缺口 ${gh:.2f} 以上則止損離場。")
            elif fill_r > 60:
                advice = (f"⚠️ 向下跳空但歷史回補率高達 {fill_r:.0f}%，"
                          f"缺口區間 ${gl:.2f}–${gh:.2f} 大概率會被回測。"
                          f"建議：可輕倉逆勢做多（反彈交易），目標缺口下沿 ${gl:.2f}，"
                          f"若繼續跌破當根低點則立即止損。")
            else:
                advice = (f"🟡 向下跳空，歷史延續率 {cont_r:.0f}%，回補率 {fill_r:.0f}%，方向不明確。"
                          f"建議：觀望為主，待缺口 ${gl:.2f}–${gh:.2f} 方向確認後再行動。")

        lines.append(advice)
        lines.append("")
        lines.append(f"缺口關鍵位：下沿 ${gl:.2f} ／上沿 ${gh:.2f}（缺口幅度 {sz:.2f}%）")
    else:
        lines.append("【當前無最新跳空】")
        lines.append("基於歷史規律，當下無即時跳空交易機會，建議按正常 Price Action 框架操作。")

    return "\n".join(lines)
