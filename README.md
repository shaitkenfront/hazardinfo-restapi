# Hazard Info REST API

## 概要

このプロジェクトは、日本のハザード情報を提供するREST APIです。住所や緯度経度を入力すると、その地点の様々なハザード情報（地震発生確率、浸水深、土砂災害警戒区域など）を取得できます。LINE Bot機能とREST API機能の両方を提供します。

## 機能

- **REST API**: HTTP GET/POSTリクエストでハザード情報を取得
- **選択的情報取得**: 必要なハザード情報のみを指定して取得可能（v2.0新機能）
- **パフォーマンス選択**: 高速モード（~7秒）と高精度モード（~11-14秒）を選択可能
- **位置情報に基づくハザード情報取得**: 住所または緯度経度から、以下のハザード情報を取得・表示
  - J-SHIS（地震ハザードステーション）による地震発生確率（震度5強以上、震度6強以上）
  - 国土地理院のハザードマップタイルデータからの情報
    - 想定最大浸水深（洪水、津波、高潮）
    - 土砂災害警戒区域（土石流、急傾斜地、地すべり）
  - 大規模盛土造成地情報
- **座標系対応**: WGS84（世界測地系）と日本測地系の両方に対応
- **LINE Bot連携**: LINE Messaging API を介してユーザーからのメッセージを受け取り、ハザード情報を返信

## 使用技術

- Python
- `requests`: 外部APIとの連携
- `Pillow`: 画像処理（ハザードマップタイル解析）
- `boto3`: AWS S3との連携
- `shapely`: ジオメトリ操作（GeoJSONデータ解析）
- `concurrent.futures`: 並列処理による高速化
- `pytest`: 自動テストフレームワーク

## セットアップ

プロジェクトをローカルで実行するための手順です。

1.  **リポジトリのクローン**

    ```bash
    git clone https://github.com/your-username/hazardinfo-restapi.git
    cd hazardinfo-restapi
    ```

2.  **仮想環境の構築と有効化**

    ```bash
    python -m venv .venv
    # Windowsの場合
    .venv\Scripts\activate
    # macOS/Linuxの場合
    # source .venv/bin/activate
    ```

3.  **依存関係のインストール**

    ```bash
    pip install -r requirements.txt
    ```

4.  **環境変数の設定**

    以下の環境変数を設定する必要があります。これらは、LINE Messaging API や Google Geocoding API との連携に必要です。

    -   `LINE_CHANNEL_ACCESS_TOKEN`: LINE Developers で取得したチャネルアクセストークン
    -   `LINE_CHANNEL_SECRET`: LINE Developers で取得したチャネルシークレット
    -   `GOOGLE_API_KEY`: Google Cloud Platform で取得した Geocoding API のAPIキー

    例（Windows PowerShell）:
    ```powershell
    $env:LINE_CHANNEL_ACCESS_TOKEN="your_access_token"
    $env:LINE_CHANNEL_SECRET="your_channel_secret"
    $env:GOOGLE_API_KEY="your_google_api_key"
    ```

    例（macOS/Linux Bash）:
    ```bash
    export LINE_CHANNEL_ACCESS_TOKEN="your_access_token"
    export LINE_CHANNEL_SECRET="your_channel_secret"
    export GOOGLE_API_KEY="your_google_api_key"
    ```

## AWS S3 設定

### 大規模盛土造成地情報の格納

このAPIは大規模盛土造成地情報をAWS S3から取得します。以下の形式でGeoJSONファイルを格納する必要があります。

#### S3バケット構造
```
your-s3-bucket/
├── A54-23_GEOJSON/
│   ├── A54-23_01.geojson  # 北海道
│   ├── A54-23_02.geojson  # 青森県
│   ├── A54-23_03.geojson  # 岩手県
│   ├── ...
│   └── A54-23_47.geojson  # 沖縄県
```

#### ファイル命名規則
- フォルダ名: `A54-23_GEOJSON`
- ファイル名: `A54-23_{都道府県コード}.geojson`
- 都道府県コードは01-47（例：北海道=01, 東京都=13, 大阪府=27, 沖縄県=47）

<details>
<summary>都道府県コード一覧表</summary>

| コード | 都道府県 | コード | 都道府県 | コード | 都道府県 |
|--------|----------|--------|----------|--------|----------|
| 01 | 北海道 | 17 | 石川県 | 33 | 岡山県 |
| 02 | 青森県 | 18 | 福井県 | 34 | 広島県 |
| 03 | 岩手県 | 19 | 山梨県 | 35 | 山口県 |
| 04 | 宮城県 | 20 | 長野県 | 36 | 徳島県 |
| 05 | 秋田県 | 21 | 岐阜県 | 37 | 香川県 |
| 06 | 山形県 | 22 | 静岡県 | 38 | 愛媛県 |
| 07 | 福島県 | 23 | 愛知県 | 39 | 高知県 |
| 08 | 茨城県 | 24 | 三重県 | 40 | 福岡県 |
| 09 | 栃木県 | 25 | 滋賀県 | 41 | 佐賀県 |
| 10 | 群馬県 | 26 | 京都府 | 42 | 長崎県 |
| 11 | 埼玉県 | 27 | 大阪府 | 43 | 熊本県 |
| 12 | 千葉県 | 28 | 兵庫県 | 44 | 大分県 |
| 13 | 東京都 | 29 | 奈良県 | 45 | 宮崎県 |
| 14 | 神奈川県 | 30 | 和歌山県 | 46 | 鹿児島県 |
| 15 | 新潟県 | 31 | 鳥取県 | 47 | 沖縄県 |
| 16 | 富山県 | 32 | 島根県 |  |  |

</details>

#### GeoJSONファイル形式
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[lon1, lat1], [lon2, lat2], ...]]
      },
      "properties": {
        "name": "大規模盛土造成地名",
        "area": "面積情報（オプション）"
      }
    }
  ]
}
```

#### 設定変更方法
`app/hazard_info.py`でS3バケット名を変更できます：
```python
S3_LARGE_FILL_LAND_BUCKET = "your-bucket-name"
S3_LARGE_FILL_LAND_FOLDER = "A54-23_GEOJSON"
S3_LARGE_FILL_LAND_FILE_PREFIX = "A54-23_"
```

#### データソース
大規模盛土造成地の情報は以下から取得できます：
- **国土数値情報**: [大規模盛土造成地データ](https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-A54-v1_0.html)
- **国土地理院**: 各都道府県の盛土造成地マップ

#### 必要なAWS権限
Lambda実行ロールに以下のS3アクセス権限が必要です：
- `s3:GetObject` - 指定バケットのGeoJSONファイル読み取り権限

## API使用方法

### REST API エンドポイント

このプロジェクトはAWS Lambda関数としてデプロイされることを想定しています。`lambda_function.py` がエントリポイントです。

### パラメータ

#### 必須パラメータ（以下のいずれかが必要）
- `lat`, `lon`: 緯度・経度（数値）
- `input`: 住所または緯度経度の文字列

#### オプションパラメータ
- `datum`: 座標系（`wgs84` または `tokyo`）デフォルト: `wgs84`
- `hazard_types`: 取得するハザード情報のタイプ（カンマ区切りまたは配列）
- `search_points`: 検索精度（`4`: 高速モード, `8`: 高精度モード）デフォルト: `4`

#### 利用可能なハザードタイプ
- `earthquake`: 地震発生確率
- `flood`: 想定最大浸水深
- `tsunami`: 津波浸水想定
- `high_tide`: 高潮浸水想定
- `large_fill_land`: 大規模盛土造成地
- `landslide`: 土砂災害警戒区域

#### 検索精度とパフォーマンス
- `search_points=4` (高速モード): 約7秒の応答時間、4方向検索で基本的な精度を提供
- `search_points=8` (高精度モード): 約11-14秒の応答時間、8方向検索で詳細な精度を提供

### 使用例

#### 全ハザード情報を取得（高速モード）
```bash
# GET リクエスト
curl "https://your-api-endpoint.com?lat=35.6586&lon=139.7454&datum=wgs84&search_points=4"

# POST リクエスト
curl -X POST https://your-api-endpoint.com \
  -H "Content-Type: application/json" \
  -d '{"lat": 35.6586, "lon": 139.7454, "datum": "wgs84", "search_points": 4}'
```

#### 特定のハザード情報のみ取得
```bash
# GET リクエスト - 地震と洪水情報のみ
curl "https://your-api-endpoint.com?lat=35.6586&lon=139.7454&hazard_types=earthquake,flood&search_points=4"

# POST リクエスト - 津波と土砂災害情報のみ
curl -X POST https://your-api-endpoint.com \
  -H "Content-Type: application/json" \
  -d '{"lat": 35.6586, "lon": 139.7454, "hazard_types": ["tsunami", "landslide"], "search_points": 4}'
```

#### 住所による検索
```bash
# GET リクエスト
curl "https://your-api-endpoint.com?input=東京都千代田区&hazard_types=earthquake&search_points=4"

# POST リクエスト
curl -X POST https://your-api-endpoint.com \
  -H "Content-Type: application/json" \
  -d '{"input": "東京都千代田区", "hazard_types": ["earthquake", "flood"], "search_points": 4}'
```

#### 高精度モードでの検索
```bash
# GET リクエスト - 高精度で全ハザード情報を取得
curl "https://your-api-endpoint.com?lat=35.6586&lon=139.7454&search_points=8"

# POST リクエスト - 高精度で特定ハザード情報を取得
curl -X POST https://your-api-endpoint.com \
  -H "Content-Type: application/json" \
  -d '{"lat": 35.6586, "lon": 139.7454, "hazard_types": ["earthquake", "landslide"], "search_points": 8}'
```

### レスポンス例

```json
{
  "coordinates": {
    "latitude": 35.6586,
    "longitude": 139.7454
  },
  "source": "座標: 35.6586, 139.7454 (入力座標系: wgs84)",
  "input_type": "latlon",
  "datum": "wgs84",
  "requested_hazard_types": ["earthquake", "flood"],
  "hazard_info": {
    "jshis_prob_50": {
      "max_prob": 0.05,
      "center_prob": 0.03
    },
    "jshis_prob_60": {
      "max_prob": 0.02,
      "center_prob": 0.01
    },
    "inundation_depth": {
      "max_info": "3m以上5m未満",
      "center_info": "0.5m未満"
    }
  },
  "status": "success"
}
```

### 使用例（進捗表示対応）

```javascript
// フロントエンド例：複数のハザード情報を順次取得
const hazardTypes = ['earthquake', 'flood', 'tsunami', 'landslide'];
const results = {};

for (let i = 0; i < hazardTypes.length; i++) {
  console.log(`取得中... ${i + 1}/${hazardTypes.length}`);
  const response = await fetch(`/api?lat=35.6586&lon=139.7454&hazard_types=${hazardTypes[i]}`);
  const data = await response.json();
  results[hazardTypes[i]] = data.hazard_info;
}
console.log('完了');
```

## 後方互換性

- 既存のAPIコール（`hazard_types` パラメータなし）は引き続き動作
- レスポンス形式は変更なし（`requested_hazard_types` フィールドのみ追加）
- 既存のクライアントコードは変更不要

## テストの実行

`pytest` を使用して、プロジェクトの自動テストを実行できます。仮想環境を有効化した状態で、以下のコマンドを実行してください。

```bash
pytest
```

または、仮想環境のPythonを直接指定して実行することもできます。

```bash
.venv\Scripts\pytest.exe # Windowsの場合
# ./.venv/bin/pytest # macOS/Linuxの場合
```

特定のテストファイルのみ実行：

```bash
pytest tests/test_lambda_function.py tests/test_hazard_info.py -v
```

## 変更履歴

### v2.1 (2025-08-02)
- **パフォーマンス大幅改善**: 並列処理により応答時間を約50%短縮（11-14秒→7秒）
- **検索精度選択機能**: `search_points`パラメータで高速モード（4点）と高精度モード（8点）を選択可能
- **並列タイル取得**: ThreadPoolExecutorによるタイル画像の並列取得
- **並列API呼び出し**: J-SHIS APIの複数地点同時取得
- **タイムアウト最適化**: 10秒→3秒に短縮し、障害時の早期切り上げを実現

### v2.0 (2025-08-01)
- 選択的ハザード情報取得機能を追加
- `hazard_types` パラメータによる情報指定機能
- 処理時間短縮とタイムアウト対策
- 完全な後方互換性を維持
- 包括的なテストスイートを追加

### v1.0
- 基本的なハザード情報取得機能
- LINE Bot機能
- 座標系変換対応

## ライセンス

[MIT License](LICENSE)
