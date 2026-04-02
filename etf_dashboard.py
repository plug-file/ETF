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
    "GDX",   # 金鉱株
    "IBB",   # バイオテック
]

OUTPUT_FILE = "index.html"


def safe_get(info: dict, key: str, default=None):
    """辞書から安全に値を取得"""
    val = info.get(key, default)
    if val is None:
        return default
    return val


def fmt_pct(val):
    """パーセント表示用フォーマット"""
    if val is None or val == "-":
        return "-"
    try:
        v = float(val) * 100
        sign = "+" if v > 0 else ""
        return f"{sign}{v:.2f}%"
    except (ValueError, TypeError):
        return "-"


def fmt_num(val, decimals=2):
    """数値フォーマット"""
    if val is None or val == "-":
        return "-"
    try:
        return f"{float(val):,.{decimals}f}"
    except (ValueError, TypeError):
        return "-"


def fmt_market_cap(val):
    """時価総額を億ドル表示"""
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
    """期間別リターンを計算"""
    try:
        tk = yf.Ticker(ticker_str)
        hist = tk.history(period="5y")
        if hist.empty:
            return {}, {}

        today_price = hist["Close"].iloc[-1]

        # 各期間の計算
        returns = {}
        now = hist.index[-1]

        # YTD
        year_start = hist.index[hist.index >= f"{now.year}-01-01"]
        if len(year_start) > 0:
            ytd_start = hist["Close"].loc[year_start[0]]
            returns["ytd"] = (today_price - ytd_start) / ytd_start
        else:
            returns["ytd"] = None

        # 1年リターン
        one_year_ago = now - datetime.timedelta(days=365)
        candidates = hist.index[hist.index >= one_year_ago]
        if len(candidates) > 0:
            price_1y = hist["Close"].loc[candidates[0]]
            returns["1y"] = (today_price - price_1y) / price_1y
        else:
            returns["1y"] = None

        # 3年平均リターン（年率）
        three_year_ago = now - datetime.timedelta(days=365 * 3)
        candidates = hist.index[hist.index >= three_year_ago]
        if len(candidates) > 0:
            price_3y = hist["Close"].loc[candidates[0]]
            total_return = (today_price - price_3y) / price_3y
            years = (now - candidates[0]).days / 365.25
            if years > 0:
                returns["3y_ann"] = (1 + total_return) ** (1 / years) - 1
            else:
                returns["3y_ann"] = None
        else:
            returns["3y_ann"] = None

        # 5年平均リターン（年率）
        five_year_ago = now - datetime.timedelta(days=365 * 5)
        candidates = hist.index[hist.index >= five_year_ago]
        if len(candidates) > 0:
            price_5y = hist["Close"].loc[candidates[0]]
            total_return = (today_price - price_5y) / price_5y
            years = (now - candidates[0]).days / 365.25
            if years > 0:
                returns["5y_ann"] = (1 + total_return) ** (1 / years) - 1
            else:
                returns["5y_ann"] = None
        else:
            returns["5y_ann"] = None

        return returns, {}

    except Exception as e:
        print(f"  リターン計算エラー ({ticker_str}): {e}")
        return {}, {}


def fetch_etf_data():
    """全ETFのデータを取得"""
    etf_data = []

    for ticker_str in TICKERS:
        print(f"取得中: {ticker_str}...")
        try:
            tk = yf.Ticker(ticker_str)
            info = tk.info

            # リターン計算
            returns, _ = calc_returns(ticker_str)

            row = {
                "ticker": ticker_str,
                "name": safe_get(info, "shortName", ticker_str),
                "per": safe_get(info, "trailingPE"),
                "pbr": safe_get(info, "priceToBook"),
                "expense_ratio": safe_get(info, "annualReportExpenseRatio"),
                "market_cap": safe_get(info, "totalAssets"),
                "num_holdings": safe_get(info, "holdings"),  # ETF保有銘柄数は別途
                "dividend_yield": safe_get(info, "yield"),
                "dividend_freq": safe_get(info, "fundFamily", "-"),
                "ytd": returns.get("ytd"),
                "return_1y": returns.get("1y"),
                "return_3y": returns.get("3y_ann"),
                "return_5y": returns.get("5y_ann"),
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
                "market_cap": None, "num_holdings": None,
                "dividend_yield": None, "dividend_freq": "-",
                "ytd": None, "return_1y": None,
                "return_3y": None, "return_5y": None,
                "price": None, "currency": "USD", "category": "-",
            })

    return etf_data


def color_cell(val, reverse=False):
    """値に応じたセルの色クラスを返す"""
    if val is None or val == "-":
        return ""
    try:
        v = float(val)
        if reverse:
            v = -v
        if v > 0:
            return "positive"
        elif v < 0:
            return "negative"
    except (ValueError, TypeError):
        pass
    return ""


def generate_html(etf_data):
    """HTMLファイルを生成"""
    now = datetime.datetime.now().strftime("%Y年%m月%d日 %H:%M")

    # テーブル行を生成
    rows_html = ""
    for d in etf_data:
        ytd_cls = color_cell(d["ytd"])
        r1y_cls = color_cell(d["return_1y"])
        r3y_cls = color_cell(d["return_3y"])
        r5y_cls = color_cell(d["return_5y"])

        rows_html += f"""
        <tr>
            <td class="ticker-cell"><strong>{d['ticker']}</strong></td>
            <td class="name-cell" title="{d.get('name','')}">{d.get('name','')[:30]}</td>
            <td>{fmt_num(d['per'], 1)}</td>
            <td>{fmt_num(d['pbr'], 2)}</td>
            <td>{fmt_pct(d['expense_ratio'])}</td>
            <td>{fmt_market_cap(d['market_cap'])}</td>
            <td>{fmt_pct(d['dividend_yield'])}</td>
            <td class="{ytd_cls}">{fmt_pct(d['ytd'])}</td>
            <td class="{r1y_cls}">{fmt_pct(d['return_1y'])}</td>
            <td class="{r3y_cls}">{fmt_pct(d['return_3y'])}</td>
            <td class="{r5y_cls}">{fmt_pct(d['return_5y'])}</td>
            <td>{fmt_num(d['price'], 2)}</td>
        </tr>"""

    # 円グラフ用データ（時価総額ベースの構成比）
    pie_data = []
    colors = [
        "#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF",
        "#FF9F40", "#E7E9ED", "#7BC8A4", "#F67019", "#4DC9F6",
        "#ACC236", "#FF5A5E", "#C9CB3F",
    ]
    total_mc = sum(float(d["market_cap"]) for d in etf_data if d["market_cap"] is not None)
    for i, d in enumerate(etf_data):
        mc = float(d["market_cap"]) if d["market_cap"] is not None else 0
        pct = (mc / total_mc * 100) if total_mc > 0 else 0
        pie_data.append({
            "label": d["ticker"],
            "value": round(pct, 1),
            "color": colors[i % len(colors)],
        })

    # リターン比較バーチャート用データ
    bar_labels = json.dumps([d["ticker"] for d in etf_data])
    bar_ytd = json.dumps([round(float(d["ytd"]) * 100, 2) if d["ytd"] is not None else 0 for d in etf_data])
    bar_1y = json.dumps([round(float(d["return_1y"]) * 100, 2) if d["return_1y"] is not None else 0 for d in etf_data])

    pie_json = json.dumps(pie_data)

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
    letter-spacing: 0.03em;
}}
.update-time {{
    text-align: center;
    font-size: 0.75rem;
    color: #666;
    margin-bottom: 6px;
    font-weight: 500;
}}
.section-title {{
    font-size: 1.1rem;
    font-weight: 800;
    color: #1b263b;
    margin: 8px 0 4px 0;
    padding-left: 8px;
    border-left: 4px solid #FF6384;
}}

/* テーブル */
.table-wrapper {{
    overflow-x: auto;
    border-radius: 8px;
    box-shadow: 0 1px 6px rgba(0,0,0,0.08);
    margin-bottom: 10px;
    background: #fff;
}}
table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
    font-weight: 700;
}}
thead th {{
    background: #0d1b2a;
    color: #fff;
    padding: 6px 8px;
    text-align: center;
    font-size: 0.78rem;
    font-weight: 800;
    white-space: nowrap;
    position: sticky;
    top: 0;
    z-index: 10;
}}
tbody td {{
    padding: 5px 8px;
    text-align: center;
    border-bottom: 1px solid #e8e8e8;
    white-space: nowrap;
}}
tbody tr:hover {{
    background: #f0f4ff;
}}
tbody tr:nth-child(even) {{
    background: #fafbfd;
}}
tbody tr:nth-child(even):hover {{
    background: #e8eeff;
}}
.ticker-cell {{
    color: #0d47a1;
    font-weight: 900;
    font-size: 0.9rem;
}}
.name-cell {{
    text-align: left;
    font-weight: 600;
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    font-size: 0.72rem;
    color: #555;
}}
.positive {{ color: #d32f2f; font-weight: 900; }}
.negative {{ color: #1565c0; font-weight: 900; }}

/* チャートセクション */
.charts-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-bottom: 10px;
}}
.chart-box {{
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 1px 6px rgba(0,0,0,0.08);
    padding: 10px;
}}
.chart-box h3 {{
    font-size: 0.9rem;
    font-weight: 800;
    color: #1b263b;
    margin-bottom: 6px;
    text-align: center;
}}
canvas {{
    max-width: 100%;
}}

/* 円グラフ（大きく） */
.pie-container {{
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 400px;
}}
.pie-container canvas {{
    max-height: 400px;
}}

/* フッター */
footer {{
    text-align: center;
    font-size: 0.65rem;
    color: #999;
    padding: 6px 0;
    font-weight: 500;
}}
@media (max-width: 768px) {{
    .charts-grid {{ grid-template-columns: 1fr; }}
    h1 {{ font-size: 1.2rem; }}
    table {{ font-size: 0.75rem; }}
}}
</style>
</head>
<body>
<div class="container">

<h1>ETF比較ダッシュボード</h1>
<p class="update-time">最終更新: {now}</p>

<div class="section-title">データ一覧</div>
<div class="table-wrapper">
<table>
<thead>
<tr>
    <th>ティッカー</th>
    <th>名称</th>
    <th>PER</th>
    <th>PBR</th>
    <th>経費率</th>
    <th>時価総額</th>
    <th>配当利回り</th>
    <th>YTD</th>
    <th>1年</th>
    <th>3年(年率)</th>
    <th>5年(年率)</th>
    <th>価格(USD)</th>
</tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>
</div>

<div class="charts-grid">
    <div class="chart-box">
        <h3>時価総額 構成比</h3>
        <div class="pie-container">
            <canvas id="pieChart"></canvas>
        </div>
    </div>
    <div class="chart-box">
        <h3>リターン比較 (YTD vs 1年)</h3>
        <canvas id="barChart" height="400"></canvas>
    </div>
</div>

<footer>
    データ出典: Yahoo Finance (yfinance) ｜ 自動生成ツール
</footer>

</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<script>
// 円グラフ
const pieData = {pie_json};
new Chart(document.getElementById('pieChart'), {{
    type: 'pie',
    data: {{
        labels: pieData.map(d => d.label + ' (' + d.value + '%)'),
        datasets: [{{
            data: pieData.map(d => d.value),
            backgroundColor: pieData.map(d => d.color),
            borderWidth: 2,
            borderColor: '#fff',
        }}]
    }},
    options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
            legend: {{
                position: 'right',
                labels: {{
                    font: {{ size: 12, weight: 'bold' }},
                    padding: 8,
                    usePointStyle: true,
                    pointStyleWidth: 12,
                }}
            }}
        }}
    }}
}});

// バーチャート
new Chart(document.getElementById('barChart'), {{
    type: 'bar',
    data: {{
        labels: {bar_labels},
        datasets: [
            {{
                label: 'YTD (%)',
                data: {bar_ytd},
                backgroundColor: 'rgba(255, 99, 132, 0.7)',
                borderColor: '#FF6384',
                borderWidth: 1,
            }},
            {{
                label: '1年リターン (%)',
                data: {bar_1y},
                backgroundColor: 'rgba(54, 162, 235, 0.7)',
                borderColor: '#36A2EB',
                borderWidth: 1,
            }}
        ]
    }},
    options: {{
        responsive: true,
        maintainAspectRatio: false,
        scales: {{
            y: {{
                ticks: {{ callback: v => v + '%', font: {{ weight: 'bold' }} }},
                grid: {{ color: '#eee' }}
            }},
            x: {{
                ticks: {{ font: {{ weight: 'bold', size: 11 }} }},
                grid: {{ display: false }}
            }}
        }},
        plugins: {{
            legend: {{
                labels: {{ font: {{ size: 12, weight: 'bold' }}, padding: 10 }}
            }}
        }}
    }}
}});
</script>
</body>
</html>"""

    return html


def main():
    print("=" * 50)
    print("ETF比較ダッシュボード 生成スクリプト")
    print("=" * 50)

    # データ取得
    etf_data = fetch_etf_data()

    # HTML生成
    html = generate_html(etf_data)

    # ファイル出力
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ 生成完了: {OUTPUT_FILE}")
    print(f"   ETF数: {len(etf_data)}")
    print("   GitHub Pagesで公開するには:")
    print("   1. このファイルをGitHubリポジトリにpush")
    print("   2. Settings > Pages > Source を main ブランチに設定")


if __name__ == "__main__":
    main()
