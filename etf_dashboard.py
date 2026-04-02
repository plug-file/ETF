#!/usr/bin/env python3
"""
ETF比較ダッシュボード生成スクリプト
Financial Modeling Prep (FMP) APIからETFデータを自動取得し、HTMLファイルを生成する。
GitHub Pagesでの公開を想定。
"""

import json
import datetime
import time
import sys
import os
import urllib.request
import urllib.error

# ====== 設定 ======
FMP_API_KEY = os.environ.get("FMP_API_KEY", "")
FMP_BASE = "https://financialmodelingprep.com"

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


# ====================================================================
#  API通信
# ====================================================================

def fmp_get(path: str, params: dict | None = None, label: str = ""):
    """
    FMP APIへGETリクエストを送り、JSONを返す。
    path は "/stable/profile" や "/api/v3/quote/SPY" のような形式。
    """
    if params is None:
        params = {}
    params["apikey"] = FMP_API_KEY

    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{FMP_BASE}{path}?{query}"

    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ETF-Dashboard/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
                data = json.loads(body)

                # FMPはエラー時に {"Error Message": "..."} を返すことがある
                if isinstance(data, dict) and "Error Message" in data:
                    print(f"    ⚠ API Error [{label}]: {data['Error Message']}")
                    return None

                return data

        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")[:300]
            except Exception:
                pass
            print(f"    HTTP {e.code} [{label}] (試行 {attempt+1}/3): {e.reason}")
            if body:
                print(f"      Body: {body}")
            if e.code == 429:
                time.sleep(5 * (attempt + 1))
            elif e.code == 403:
                print("    → APIキーまたはプランの問題の可能性があります")
                return None
            else:
                time.sleep(2)

        except Exception as e:
            print(f"    エラー [{label}] (試行 {attempt+1}/3): {e}")
            time.sleep(2)

    return None


# ====================================================================
#  ユーティリティ
# ====================================================================

def safe_float(val, default=None):
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def fmt_pct(val, show_sign=True):
    """0.05 → "5.00%" のように小数比率をパーセント表記"""
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


def fmt_pct_raw(val, show_sign=True):
    """既にパーセント値（例: 5.23）をそのまま表記"""
    if val is None or val == "-":
        return "-"
    try:
        v = float(val)
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


# ====================================================================
#  データ取得
# ====================================================================

def fetch_quote_batch(tickers: list[str]) -> dict:
    """
    /stable/quote でバッチ取得（カンマ区切り）。
    price, pe, priceToBook, marketCap, volume 等が取れる。
    """
    result = {}
    tickers_str = ",".join(tickers)
    data = fmp_get("/stable/quote", {"symbol": tickers_str}, label="quote-batch")
    if data and isinstance(data, list):
        for item in data:
            sym = item.get("symbol", "")
            if sym:
                result[sym] = item
    return result


def fetch_price_change_batch(tickers: list[str]) -> dict:
    """
    /stable/stock-price-change でバッチ取得。
    ytd, 1Y, 3Y, 5Y 等のパーセント変動が取れる。
    """
    result = {}
    tickers_str = ",".join(tickers)
    data = fmp_get("/stable/stock-price-change", {"symbol": tickers_str}, label="price-change-batch")
    if data and isinstance(data, list):
        for item in data:
            sym = item.get("symbol", "")
            if sym:
                result[sym] = item
    return result


def fetch_etf_info_single(ticker: str) -> dict:
    """
    ETF固有情報（経費率等）を取得。
    /stable/etf-info → v4レガシー の順で試行。
    """
    # 1) stable エンドポイント
    data = fmp_get("/stable/etf-info", {"symbol": ticker}, label=f"etf-info-stable-{ticker}")
    if data and isinstance(data, list) and len(data) > 0:
        return data[0]

    # 2) レガシー v4
    data = fmp_get("/api/v4/etf-info", {"symbol": ticker}, label=f"etf-info-v4-{ticker}")
    if data and isinstance(data, list) and len(data) > 0:
        return data[0]

    return {}


def fetch_etf_data():
    """FMP APIからETFデータを取得して統合"""
    if not FMP_API_KEY:
        print("❌ FMP_API_KEY が設定されていません。")
        print("   環境変数 FMP_API_KEY にAPIキーを設定してください。")
        sys.exit(1)

    print(f"🔑 APIキー: {FMP_API_KEY[:4]}...{FMP_API_KEY[-4:]}")

    # --- 1) quote（価格・PER等）バッチ取得 ---
    print(f"\n📡 [1/3] Quote取得中...")
    quotes = fetch_quote_batch(TICKERS)
    print(f"  → {len(quotes)}件取得")
    if quotes:
        sample_key = next(iter(quotes))
        sample = quotes[sample_key]
        print(f"  → サンプル ({sample_key}): price={sample.get('price')}, pe={sample.get('pe')}, marketCap={sample.get('marketCap')}")
    else:
        print("  ⚠ Quote取得失敗！APIキーやプランを確認してください。")
        # 個別取得を試行
        print("  → 個別取得を試行します...")
        for t in TICKERS[:2]:
            print(f"    テスト: {t}")
            data = fmp_get(f"/stable/quote", {"symbol": t}, label=f"quote-single-{t}")
            if data:
                print(f"      レスポンス型: {type(data).__name__}, 長さ: {len(data) if isinstance(data, list) else 'N/A'}")
                if isinstance(data, list) and len(data) > 0:
                    print(f"      キー: {list(data[0].keys())[:10]}")
                elif isinstance(data, dict):
                    print(f"      キー: {list(data.keys())[:10]}")
            else:
                print(f"      → None（取得失敗）")
            time.sleep(1)

    # --- 2) price-change（リターン）バッチ取得 ---
    print(f"\n📡 [2/3] 価格変動取得中...")
    price_changes = fetch_price_change_batch(TICKERS)
    print(f"  → {len(price_changes)}件取得")
    if price_changes:
        sample_key = next(iter(price_changes))
        sample = price_changes[sample_key]
        print(f"  → サンプル ({sample_key}): ytd={sample.get('ytd')}, 1Y={sample.get('1Y')}, 5Y={sample.get('5Y')}")

    # --- 3) ETF情報（経費率等）個別取得 ---
    print(f"\n📡 [3/3] ETF情報取得中...")
    etf_infos = {}
    for i, ticker_str in enumerate(TICKERS):
        ei = fetch_etf_info_single(ticker_str)
        if ei:
            etf_infos[ticker_str] = ei
        if i < len(TICKERS) - 1:
            time.sleep(0.4)
    print(f"  → {len(etf_infos)}件取得")
    if etf_infos:
        sample_key = next(iter(etf_infos))
        sample = etf_infos[sample_key]
        print(f"  → サンプル ({sample_key}): expenseRatio={sample.get('expenseRatio')}, aum={sample.get('aum')}")

    # --- 4) データ統合 ---
    print(f"\n📊 データ統合中...")
    etf_data = []
    for ticker_str in TICKERS:
        q = quotes.get(ticker_str, {})
        pc = price_changes.get(ticker_str, {})
        ei = etf_infos.get(ticker_str, {})

        # 経費率
        expense = safe_float(ei.get("expenseRatio"))

        # 配当利回り
        dividend_yield = None
        # quoteから取得を試みる
        if q.get("annualDividend") and q.get("price"):
            price_val = safe_float(q.get("price"))
            div_val = safe_float(q.get("annualDividend"))
            if price_val and div_val and price_val > 0:
                dividend_yield = div_val / price_val
        # ETF infoのdividendYieldをフォールバック
        if dividend_yield is None and ei.get("dividendYield"):
            dividend_yield = safe_float(ei.get("dividendYield"))

        # リターン（FMPは%値、例: 5.23 = +5.23%）
        ytd_pct = safe_float(pc.get("ytd"))
        r1y_pct = safe_float(pc.get("1Y"))
        r3y_pct = safe_float(pc.get("3Y"))
        r5y_pct = safe_float(pc.get("5Y"))

        # 時価総額
        market_cap = safe_float(q.get("marketCap")) or safe_float(ei.get("aum")) or safe_float(ei.get("totalAssets"))

        # PER・PBR
        per = safe_float(q.get("pe"))
        pbr = safe_float(q.get("priceToBook"))

        # 価格
        price = safe_float(q.get("price")) or safe_float(q.get("previousClose"))

        # 名前
        name = q.get("name") or ei.get("name") or ticker_str

        row = {
            "ticker": ticker_str,
            "name": name,
            "per": per,
            "pbr": pbr,
            "expense_ratio": expense,
            "market_cap": market_cap,
            "dividend_yield": dividend_yield,
            "ytd": ytd_pct,
            "return_1y": r1y_pct,
            "return_3y": r3y_pct,
            "return_5y": r5y_pct,
            "price": price,
            "currency": "USD",
            "category": ei.get("assetClass") or q.get("sector") or "-",
        }

        has_data = price is not None or ytd_pct is not None
        status = "✅" if has_data else "❌ データ無し"
        print(f"  {ticker_str}: {name} → price={price}, ytd={ytd_pct} {status}")
        etf_data.append(row)

    return etf_data


# ====================================================================
#  HTML生成
# ====================================================================

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

        expense_str = fmt_pct(d['expense_ratio'], show_sign=False) if d['expense_ratio'] is not None else '-'
        div_str = fmt_pct(d['dividend_yield'], show_sign=False) if d['dividend_yield'] is not None else '-'

        rows_html += f"""
        <tr data-idx="{i}" onclick="selectRow(this, {i})" title="{d.get('name','')}">
            <td class="ticker-cell sticky-col"><strong>{d['ticker']}</strong></td>
            <td>{fmt_num(d['price'], 2)}</td>
            <td>{fmt_num(d['per'], 1)}</td>
            <td>{fmt_num(d['pbr'], 2)}</td>
            <td>{expense_str}</td>
            <td class="mc-cell"><div class="mc-bar" style="width:{mc_pct:.1f}%"></div><span class="mc-label">{fmt_market_cap(d['market_cap'])}</span></td>
            <td>{div_str}</td>
            <td class="{color_cell(d['ytd'])}">{fmt_pct_raw(d['ytd'])}</td>
            <td class="{color_cell(d['return_1y'])}">{fmt_pct_raw(d['return_1y'])}</td>
            <td class="{color_cell(d['return_3y'])}">{fmt_pct_raw(d['return_3y'])}</td>
            <td class="{color_cell(d['return_5y'])}">{fmt_pct_raw(d['return_5y'])}</td>
        </tr>"""

    chart_data_list = []
    for d in etf_data:
        chart_data_list.append({
            "ticker": d["ticker"],
            "name": d.get("name", d["ticker"]),
            "ytd": round(d["ytd"], 2) if d["ytd"] is not None else None,
            "r1y": round(d["return_1y"], 2) if d["return_1y"] is not None else None,
            "r3y": round(d["return_3y"], 2) if d["return_3y"] is not None else None,
            "r5y": round(d["return_5y"], 2) if d["return_5y"] is not None else None,
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

<footer>データ出典: Financial Modeling Prep (FMP) ｜ 自動生成ツール</footer>
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


# ====================================================================
#  メイン
# ====================================================================

def main():
    print("=" * 60)
    print("  ETF比較ダッシュボード 生成スクリプト")
    print("  データソース: Financial Modeling Prep (FMP)")
    print("=" * 60)

    etf_data = fetch_etf_data()

    # 取得状況サマリー
    ok = sum(1 for d in etf_data if d["price"] is not None)
    print(f"\n📊 取得結果: {ok}/{len(etf_data)} 銘柄にデータあり")

    if ok == 0:
        print("\n⚠ 全銘柄のデータが取得できませんでした。")
        print("  考えられる原因:")
        print("  1. FMP_API_KEY が正しく設定されていない")
        print("  2. FMPの無料プランでは一部シンボルのみ対応（AAPL, TSLA等の約100銘柄）")
        print("  3. APIのレート制限に達した")
        print("  → FMPダッシュボードでAPIキーとプランを確認してください")
        print("  → https://financialmodelingprep.com/developer/docs/dashboard")

    html = generate_html(etf_data)
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n✅ 生成完了: {OUTPUT_FILE}")
    print(f"   ETF数: {len(etf_data)}, データあり: {ok}")


if __name__ == "__main__":
    main()
