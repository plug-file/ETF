#!/usr/bin/env python3
"""
ETF比較ダッシュボード生成スクリプト
yfinanceからETFデータを自動取得し、HTMLファイルを生成する。
GitHub Pagesでの公開を想定。
"""

import yfinance as yf
import json
import datetime
import sys

# ====== 設定 ======
TICKERS = [
    "VT",    # 全世界株式
    "VTI",   # 米国株式トータル
    "SPY",   # S&P 500
    "VGK",   # ヨーロッパ
    "EWG",   # ドイツ
    "EPOL",  # ポーランド
    "TUR",   # トルコ
    "EWZ",   # ブラジル
    "EWW",   # メキシコ
    "EPI",   # インド
    "VNM",   # ベトナム
    "EIDO",  # インドネシア
    "EWM",   # マレーシア
    "THD",   # タイ
    "EPHE",  # フィリピン
    "GLD",   # 金
    "GDX",   # 金鉱株
    "IBB",   # バイオテック
]

OUTPUT_FILE = "docs/index.html"


def safe_get(info: dict, key: str, default=None):
    val = info.get(key, default)
    return default if val is None else val


def fmt_pct(val, show_sign=True):
    if val is None or val == "-":
        return "-"
    try:
        v = float(val) * 100
        if show_sign:
            return f"{'+' if v > 0 else ''}{v:.2f}%"
        else:
            return f"{v:.2f}%"
    except (ValueError, TypeError):
        return "-"


def fmt_num(val, decimals=2):
    if val is None or val == "-":
        return "-"
    try:
        return f"{float(val):,.{decimals}f}"
    except (ValueError, TypeError):
        return "-"


def fmt_market_cap(val):
    if val is None or val == "-":
        return "-"
    try:
        v = float(val)
        if v >= 1e12:
            return f"${v/1e12:.1f}T"
        elif v >= 1e9:
            return f"${v/1e9:.1f}B"
        elif v >= 1e6:
            return f"${v/1e6:.0f}M"
        else:
            return f"${v:,.0f}"
    except (ValueError, TypeError):
        return "-"


def calc_returns(ticker_str):
    try:
        tk = yf.Ticker(ticker_str)
        hist = tk.history(period="5y")
        if hist.empty:
            return {}
        today_price = hist["Close"].iloc[-1]
        returns = {}
        now = hist.index[-1]

        year_start = hist.index[hist.index >= f"{now.year}-01-01"]
        if len(year_start) > 0:
            returns["ytd"] = (today_price - hist["Close"].loc[year_start[0]]) / hist["Close"].loc[year_start[0]]

        for key, days in [("1y", 365), ("3y", 365*3), ("5y", 365*5)]:
            ago = now - datetime.timedelta(days=days)
            cands = hist.index[hist.index >= ago]
            if len(cands) > 0:
                p = hist["Close"].loc[cands[0]]
                returns[key] = (today_price - p) / p

        return returns
    except Exception as e:
        print(f"  リターン計算エラー ({ticker_str}): {e}")
        return {}


def fetch_etf_data():
    etf_data = []
    for ticker_str in TICKERS:
        print(f"取得中: {ticker_str}...")
        try:
            tk = yf.Ticker(ticker_str)
            info = tk.info
            returns = calc_returns(ticker_str)
            row = {
                "ticker": ticker_str,
                "name": safe_get(info, "shortName", ticker_str),
                "per": safe_get(info, "trailingPE"),
                "pbr": safe_get(info, "priceToBook"),
                "expense_ratio": safe_get(info, "annualReportExpenseRatio"),
                "market_cap": safe_get(info, "totalAssets"),
                "dividend_yield": safe_get(info, "yield"),
                "ytd": returns.get("ytd"),
                "return_1y": returns.get("1y"),
                "return_3y": returns.get("3y"),
                "return_5y": returns.get("5y"),
                "price": safe_get(info, "previousClose"),
                "currency": safe_get(info, "currency", "USD"),
                "category": safe_get(info, "category", "-"),
            }
            etf_data.append(row)
            print(f"  完了: {row['name']}")
        except Exception as e:
            print(f"  エラー ({ticker_str}): {e}")
            etf_data.append({
                "ticker": ticker_str, "name": ticker_str,
                "per": None, "pbr": None, "expense_ratio": None,
                "market_cap": None, "dividend_yield": None,
                "ytd": None, "return_1y": None,
                "return_3y": None, "return_5y": None,
                "price": None, "currency": "USD", "category": "-",
            })
    return etf_data


def color_cell(val):
    if val is None or val == "-":
        return ""
    try:
        v = float(val)
        return "positive" if v > 0 else ("negative" if v < 0 else "")
    except (ValueError, TypeError):
        return ""


def generate_html(etf_data):
    """HTMLファイルを生成"""
    now = datetime.datetime.now().strftime("%Y年%m月%d日 %H:%M")

    mc_values = [float(d["market_cap"]) for d in etf_data if d["market_cap"] is not None]
    max_mc = max(mc_values) if mc_values else 1

    rows_html = ""
    for i, d in enumerate(etf_data):
        mc_val = float(d["market_cap"]) if d["market_cap"] is not None else 0
        mc_pct = (mc_val / max_mc * 100) if max_mc > 0 else 0

        rows_html += f"""
        <tr data-idx="{i}" onclick="selectRow(this, {i})" title="{d.get('name','')}">
            <td class="ticker-cell sticky-col"><strong>{d['ticker']}</strong></td>
            <td>{fmt_num(d['price'], 2)}</td>
            <td>{fmt_num(d['per'], 1)}</td>
            <td>{fmt_num(d['pbr'], 2)}</td>
            <td>{fmt_pct(d['expense_ratio'], show_sign=False)}</td>
            <td class="mc-cell"><div class="mc-bar" style="width:{mc_pct:.1f}%"></div><span class="mc-label">{fmt_market_cap(d['market_cap'])}</span></td>
            <td>{fmt_pct(d['dividend_yield'], show_sign=False)}</td>
            <td class="{color_cell(d['ytd'])}">{fmt_pct(d['ytd'])}</td>
            <td class="{color_cell(d['return_1y'])}">{fmt_pct(d['return_1y'])}</td>
            <td class="{color_cell(d['return_3y'])}">{fmt_pct(d['return_3y'])}</td>
            <td class="{color_cell(d['return_5y'])}">{fmt_pct(d['return_5y'])}</td>
        </tr>"""

    chart_data_list = []
    for d in etf_data:
        chart_data_list.append({
            "ticker": d["ticker"],
            "name": d.get("name", d["ticker"]),
            "ytd": round(float(d["ytd"]) * 100, 2) if d["ytd"] is not None else None,
            "r1y": round(float(d["return_1y"]) * 100, 2) if d["return_1y"] is not None else None,
            "r3y": round(float(d["return_3y"]) * 100, 2) if d["return_3y"] is not None else None,
            "r5y": round(float(d["return_5y"]) * 100, 2) if d["return_5y"] is not None else None,
        })
    chart_data_json = json.dumps(chart_data_list, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ETF比較ダッシュボード</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: "Noto Sans JP", "Hiragino Kaku Gothic Pro", "Meiryo", sans-serif;
    background: #FAFAFA;
    color: #1a1a1a;
    font-size: 16px;
    font-weight: 600;
    line-height: 1.3;
}}
.container {{
    max-width: 1400px;
    margin: 0 auto;
    padding: 8px 12px;
}}
h1 {{
    font-size: 1.6rem;
    font-weight: 900;
    color: #0d1b2a;
    margin: 4px 0;
    text-align: center;
}}
.update-time {{
    text-align: center;
    font-size: 0.75rem;
    color: #666;
    margin-bottom: 6px;
    font-weight: 500;
}}

/* テーブル: ティッカー列固定 + 横スクロール */
.table-wrapper {{
    overflow-x: auto;
    border-radius: 8px;
    box-shadow: 0 1px 6px rgba(0,0,0,0.08);
    margin-bottom: 10px;
    background: #fff;
    position: relative;
}}
table {{
    width: max-content;
    min-width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
    font-weight: 700;
}}
thead th {{
    background: #0d1b2a;
    color: #fff;
    padding: 6px 10px;
    text-align: center;
    font-size: 0.78rem;
    font-weight: 800;
    white-space: nowrap;
    position: sticky;
    top: 0;
    z-index: 10;
}}
thead th:first-child {{
    position: sticky;
    left: 0;
    z-index: 20;
    background: #0d1b2a;
}}
tbody td {{
    padding: 5px 10px;
    text-align: center;
    border-bottom: 1px solid #e8e8e8;
    white-space: nowrap;
}}
.sticky-col {{
    position: sticky;
    left: 0;
    z-index: 5;
    background: #fff;
    border-right: 2px solid #e0e0e0;
}}
tbody tr:nth-child(even) .sticky-col {{ background: #fafbfd; }}
tbody tr:hover .sticky-col {{ background: #f0f4ff; }}
tbody tr:nth-child(even):hover .sticky-col {{ background: #e8eeff; }}
tbody tr.selected .sticky-col {{ background: #dce6ff; }}
tbody tr {{
    cursor: pointer;
    transition: background 0.15s;
}}
tbody tr:hover {{ background: #f0f4ff; }}
tbody tr:nth-child(even) {{ background: #fafbfd; }}
tbody tr:nth-child(even):hover {{ background: #e8eeff; }}
tbody tr.selected {{
    background: #dce6ff !important;
    box-shadow: inset 3px 0 0 #0d47a1;
}}
.ticker-cell {{ color: #0d47a1; font-weight: 900; font-size: 0.9rem; }}
.positive {{ color: #d32f2f; font-weight: 900; }}
.negative {{ color: #1565c0; font-weight: 900; }}

/* 時価総額セル内バー */
.mc-cell {{
    position: relative;
    padding: 5px 10px;
    min-width: 110px;
}}
.mc-bar {{
    position: absolute;
    left: 0; top: 0; bottom: 0;
    background: linear-gradient(90deg, rgba(54,162,235,0.22), rgba(54,162,235,0.06));
    border-right: 2px solid rgba(54,162,235,0.45);
    pointer-events: none;
}}
.mc-label {{
    position: relative;
    z-index: 1;
    font-weight: 800;
}}

/* チャート（全幅1カラム） */
.chart-section {{
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 1px 6px rgba(0,0,0,0.08);
    padding: 10px;
    margin-bottom: 10px;
}}
.chart-section h3 {{
    font-size: 0.9rem;
    font-weight: 800;
    color: #1b263b;
    margin-bottom: 6px;
    text-align: center;
    min-height: 1.2em;
}}
canvas {{ max-width: 100%; }}
.detail-chart-container {{
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 300px;
    position: relative;
}}
.detail-placeholder {{
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: #aaa;
    font-weight: 700;
    font-size: 0.9rem;
    gap: 8px;
    min-height: 300px;
}}
.detail-placeholder svg {{ opacity: 0.3; }}

footer {{
    text-align: center;
    font-size: 0.65rem;
    color: #999;
    padding: 6px 0;
    font-weight: 500;
}}
@media (max-width: 768px) {{
    h1 {{ font-size: 1.2rem; }}
    table {{ font-size: 0.75rem; }}
}}
</style>
</head>
<body>
<div class="container">

<h1>ETF比較ダッシュボード</h1>
<p class="update-time">最終更新: {now}</p>

<div class="table-wrapper">
<table>
<thead>
<tr>
    <th>ティッカー</th>
    <th>価格(USD)</th>
    <th>PER</th>
    <th>PBR</th>
    <th>経費率</th>
    <th>時価総額</th>
    <th>配当利回り</th>
    <th>YTD</th>
    <th>1年</th>
    <th>3年</th>
    <th>5年</th>
</tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>
</div>

<div class="chart-section">
    <h3 id="detailTitle"></h3>
    <div class="detail-chart-container">
        <div class="detail-placeholder" id="detailPlaceholder">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 3v18h18"/><path d="M7 16l4-8 4 4 5-9"/></svg>
            テーブルの行をクリックするとチャートを表示
        </div>
        <canvas id="detailChart" style="display:none;"></canvas>
    </div>
</div>

<footer>データ出典: Yahoo Finance (yfinance) ｜ 自動生成ツール</footer>
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<script>
const etfData = {chart_data_json};
let detailChartInstance = null;

function selectRow(tr, idx) {{
    document.querySelectorAll('tbody tr').forEach(r => r.classList.remove('selected'));
    tr.classList.add('selected');
    const d = etfData[idx];
    document.getElementById('detailPlaceholder').style.display = 'none';
    const canvas = document.getElementById('detailChart');
    canvas.style.display = 'block';
    document.getElementById('detailTitle').textContent = d.ticker + '　' + d.name;
    if (detailChartInstance) detailChartInstance.destroy();

    const labels = ['YTD', '1年', '3年', '5年'];
    const values = [d.ytd, d.r1y, d.r3y, d.r5y];
    const bgColors = values.map(v => v === null ? '#ddd' : v >= 0 ? 'rgba(211,47,47,0.65)' : 'rgba(21,101,192,0.65)');
    const borderColors = values.map(v => v === null ? '#ccc' : v >= 0 ? '#d32f2f' : '#1565c0');

    detailChartInstance = new Chart(canvas, {{
        type: 'bar',
        data: {{ labels, datasets: [{{ label: 'リターン (%)', data: values.map(v => v ?? 0), backgroundColor: bgColors, borderColor: borderColors, borderWidth: 2, borderRadius: 4 }}] }},
        options: {{
            responsive: true, maintainAspectRatio: false, indexAxis: 'y',
            scales: {{
                x: {{ ticks: {{ callback: v => v + '%', font: {{ weight: 'bold', size: 12 }} }}, grid: {{ color: '#f0f0f0' }} }},
                y: {{ ticks: {{ font: {{ weight: 'bold', size: 14 }} }}, grid: {{ display: false }} }}
            }},
            plugins: {{
                legend: {{ display: false }},
                tooltip: {{ callbacks: {{ label: ctx => (ctx.raw > 0 ? '+' : '') + ctx.raw.toFixed(2) + '%' }}, titleFont: {{ weight: 'bold', size: 13 }}, bodyFont: {{ weight: 'bold', size: 13 }} }},
            }},
            animation: {{ duration: 400, easing: 'easeOutQuart' }}
        }},
        plugins: [{{
            afterDraw(chart) {{
                const ctx = chart.ctx;
                chart.data.datasets[0].data.forEach((val, i) => {{
                    const bar = chart.getDatasetMeta(0).data[i];
                    const text = (val > 0 ? '+' : '') + val.toFixed(2) + '%';
                    ctx.save();
                    ctx.font = 'bold 14px sans-serif';
                    ctx.fillStyle = val >= 0 ? '#d32f2f' : '#1565c0';
                    ctx.textAlign = val >= 0 ? 'left' : 'right';
                    ctx.textBaseline = 'middle';
                    ctx.fillText(text, val >= 0 ? bar.x + 8 : bar.x - 8, bar.y);
                    ctx.restore();
                }});
            }}
        }}]
    }});
}}
</script>
</body>
</html>"""

    return html


def main():
    print("=" * 50)
    print("ETF比較ダッシュボード 生成スクリプト")
    print("=" * 50)
    etf_data = fetch_etf_data()
    html = generate_html(etf_data)
    import os
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n✅ 生成完了: {OUTPUT_FILE}")
    print(f"   ETF数: {len(etf_data)}")


if __name__ == "__main__":
    main()
