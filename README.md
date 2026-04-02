# ETF比較ダッシュボード

新興国・テーマ型ETFの主要データを自動取得し、HTMLダッシュボードとして表示するツール。

## 含まれるETF

| ティッカー | 対象 |
|-----------|------|
| EWG | ドイツ |
| EPOL | ポーランド |
| TUR | トルコ |
| EWZ | ブラジル |
| EWW | メキシコ |
| EPI | インド |
| VNM | ベトナム |
| EIDO | インドネシア |
| EWM | マレーシア |
| THD | タイ |
| EPHE | フィリピン |
| GDX | 金鉱株 |
| IBB | バイオテック |

## 表示データ

PER / PBR / 経費率 / 時価総額 / 配当利回り / YTD / 1年・3年・5年リターン（年率）

## 使い方

### ローカル実行

```bash
export FMP_API_KEY="あなたのFMP APIキー"
python etf_dashboard.py
# docs/index.html が生成される
```

外部ライブラリ不要（標準ライブラリのみ使用）。

### GitHub Pages で公開（自動更新付き）

1. このリポジトリをGitHubにpush
2. **Settings → Secrets and variables → Actions** で `FMP_API_KEY` を設定
3. **Settings → Pages → Source** を `main` ブランチの `/docs` に設定
4. GitHub Actionsが毎日自動でデータを更新

### ETFの追加・変更

`etf_dashboard.py` の `TICKERS` リストを編集するだけ。

## データ出典

[Financial Modeling Prep (FMP)](https://financialmodelingprep.com/) API
