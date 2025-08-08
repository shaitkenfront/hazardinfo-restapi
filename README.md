# Hazard Info REST API

## 概要

このプロジェクトは、日本のハザード情報を提供するREST APIです。住所や緯度経度を入力すると、その地点の様々なハザード情報（地震発生確率、浸水深、土砂災害警戒区域など）を取得できます。

## 機能

- **REST API**: HTTP GET/POSTリクエストでハザード情報を取得
- **選択的情報取得**: 必要なハザード情報のみを指定して取得可能
- **パフォーマンス選択**: 高速モード（低精度、~3-5秒）と高精度モード（~7-10秒）を選択可能
- **位置情報に基づくハザード情報取得**: 住所または緯度経度から、以下のハザード情報を取得・表示
  - J-SHIS（地震ハザードステーション）による地震発生確率（震度5強以上、震度6強以上）
  - 国土地理院のハザードマップタイルデータからの情報
    - 想定最大浸水深（洪水、津波、高潮）
    - 浸水継続時間
    - 家屋倒壊等氾濫想定区域（氾濫流）
    - 家屋倒壊等氾濫想定区域（河岸侵食）
    - 土砂災害警戒区域（土石流、急傾斜地、地すべり）
  - 大規模盛土造成地情報
- **座標系対応**: WGS84（世界測地系）と日本測地系の両方に対応

## アーキテクチャ

### モジュール構成（2024年リファクタリング後）

プロジェクトは保守性と拡張性を向上させるため、機能別にモジュールが分離された構造になっています：

```
app/
├── hazard_info.py          # メイン API（大幅に簡素化）
├── lambda_function.py      # AWS Lambda エントリポイント
├── geocoding.py           # 住所・座標変換処理
├── input_parser.py        # 入力解析・検証
├── geojsonhelper.py       # GeoJSON処理ユーティリティ
├── config/
│   └── constants.py       # 定数定義（URL、設定値等）
└── utils/
    ├── color_mapping.py   # 色マップ定義と判定機能
    ├── tile_utils.py      # タイル座標計算・取得機能
    └── spatial_search.py  # 空間検索ユーティリティ
```

### 使用技術

- **Python 3.13+**: メイン開発言語
- **外部API連携**:
  - `requests`: HTTP通信（J-SHIS API、国土地理院API等）
- **画像・地理空間処理**:
  - `Pillow`: ハザードマップタイル画像解析
  - `shapely`: ジオメトリ操作（GeoJSONデータ解析）
  - `rtree`: R-tree空間インデックスによる高速地理空間検索
- **AWS連携**:
  - `boto3`: AWS S3との連携（大規模盛土造成地データ）
- **パフォーマンス最適化**:
  - `concurrent.futures`: 並列処理によるタイル取得の高速化
- **テスト・開発**:
  - `pytest`: 自動テストフレームワーク（44テストケース）

### 設計原則

- **モジュラー設計**: 機能別に分離されたモジュール構成で保守性を向上
- **単一責任原則**: 各モジュールが特定の責任のみを持つ
- **定数の集約管理**: 設定値やマジックナンバーを `constants.py` に集約
- **後方互換性**: 既存APIインターフェースを完全に維持
- **テスト駆動**: 全44テストケースによる品質保証

### パフォーマンス最適化

#### 2024年リファクタリングによる改善点

- **関数分割による可読性向上**: 長大な関数を小さな関数に分割することで、コードの理解とメンテナンスが容易に
- **定数管理の効率化**: マジックナンバーの排除により、設定変更時の影響範囲を最小化
- **メモリ使用量の削減**: 重複した色マップの統合により、メモリ効率を改善
- **モジュール間の疎結合**: 各モジュールが独立性を保ち、変更の影響を局所化

#### 実行時パフォーマンス特性

- **高速モード** (`precision=low`): 約3-5秒
  - 中心点と8方位ピクセルを調査
  - 基本的な精度で高速レスポンス
- **高精度モード** (`precision=high`): 約7-10秒  
  - 周辺100m範囲内の密度の高いサンプリング
  - より詳細で包括的な結果を提供
- **大規模盛土造成地検索**: R-tree空間インデックスと早期終了最適化により大幅な高速化

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

    以下の環境変数を設定する必要があります。これは、Google Geocoding API との連携に必要です。

    -   `GOOGLE_API_KEY`: Google Cloud Platform で取得した Geocoding API のAPIキー
    -   `ENABLE_LARGE_FILL_LAND`: (オプション)大規模盛土造成地機能の有効/無効を切り替えるフラグ。`true`で有効、`false`で無効。デフォルトは`false`。
    -   `S3_LARGE_FILL_LAND_BUCKET`: (オプション)大規模盛土造成地geojsonファイルを保存しているS3バケット名
    -   `ENABLE_LARGE_FILL_LAND` 環境変数を `true` に設定すると、大規模盛土造成地に関する情報の取得・表示が有効になります。デフォルトは `false` (無効)  です。
    
    例（Windows PowerShell）:
    ```powershell
    $env:GOOGLE_API_KEY="your_google_api_key"
    ```

    例（macOS/Linux Bash）:
    ```bash
    export GOOGLE_API_KEY="your_google_api_key"
    ```

## 機能の有効化/無効化

一部の機能は環境変数で有効/無効を切り替えることができます。

- **大規模盛土造成地**: `ENABLE_LARGE_FILL_LAND` 環境変数を `true` に設定すると、大規模盛土造成地に関する情報の取得・表示が有効になります。デフォルトは `false` (無効) です。

例（Windows PowerShell）:
```powershell
$env:ENABLE_LARGE_FILL_LAND="true"
```

例（macOS/Linux Bash）:
```bash
export ENABLE_LARGE_FILL_LAND="true"
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

#### データソース
大規模盛土造成地の情報は以下から取得できます：
- **国土数値情報**: [大規模盛土造成地データ](https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-A54-v1_0.html)

#### 必要なAWS権限
Lambda実行ロールに以下のS3アクセス権限が必要です：
- `s3:GetObject` - 指定バケットのGeoJSONファイル読み取り権限

### 大規模盛土造成地の高速化技術

大規模盛土造成地の検索には以下の高速化技術を採用しています：

#### R-tree空間インデックス
- **空間インデックス**: GeoJSONのフィーチャーをR-treeインデックスに登録し、空間検索を高速化
- **対数時間検索**: 線形検索（O(n)）から対数検索（O(log n)）への大幅な性能向上
- **候補絞り込み**: 全フィーチャーを調べる代わりに、空間的に近いフィーチャーのみを検索

#### インテリジェントキャッシュ
- **都道府県別キャッシュ**: 一度構築したR-treeインデックスを都道府県別にメモリキャッシュ
- **再利用効果**: 同じ都道府県への2回目以降のアクセスで大幅な時間短縮
- **メモリ効率**: 必要な都道府県のデータのみをキャッシュ

#### 早期終了最適化
- **2値判定の活用**: 大規模盛土造成地は"あり"/"なし"の2値なので、"あり"が見つかり次第即座に処理終了
- **中心点優先処理**: 中心点を最初に検索し、"あり"が見つかれば他の座標の探索をキャンセル
- **都道府県跨ぎ最適化**: 中心点を含む都道府県を優先処理し、"あり"が見つかれば他都道府県の処理をスキップ

#### パフォーマンス向上効果
- **最良ケース（中心点で"あり"）**: 約80-90%の処理時間短縮
- **一般ケース（2-3点目で"あり"）**: 約40-60%の処理時間短縮
- **キャッシュヒット時**: 2回目以降のアクセスで大幅な高速化

#### デバッグ出力
開発・運用時には以下の詳細なデバッグ情報が出力されます：
```
[DEBUG] get_large_scale_filled_land_info_from_geojson 開始: lat=35.6762, lon=139.6503
[DEBUG] 都道府県 13: GeoJSON読み込み時間 = 0.123秒
[DEBUG] 都道府県 13: R-treeインデックス構築完了 (features数=1234)
[DEBUG] Point 1/5: 大規模盛土造成地'あり'を発見！
[DEBUG] 早期終了: 大規模盛土造成地'あり'が見つかったため処理を終了
[DEBUG] get_large_scale_filled_land_info_from_geojson 完了: 総処理時間 = 0.234秒 (早期終了により一部処理をスキップ)
```

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
- `precision`: 検索精度（`low`: 高速モード, `high`: 高精度モード）デフォルト: `low`

#### 利用可能なハザードタイプ
- `earthquake`: 地震発生確率
- `flood`: 想定最大浸水深
- `flood_keizoku`: 浸水継続時間
- `kaokutoukai_hanran`: 家屋倒壊等氾濫想定区域（氾濫流）
- `kaokutoukai_kagan`: 家屋倒壊等氾濫想定区域（河岸侵食）
- `tsunami`: 津波浸水想定
- `high_tide`: 高潮浸水想定
- `large_fill_land`: 大規模盛土造成地
- `landslide`: 土砂災害警戒区域

#### 検索精度とパフォーマンス
- `precision=low` (高速モード): 約3-5秒の応答時間、中心点と8方位ピクセル調査で基本的な精度を提供
- `precision=high` (高精度モード): 約7-10秒の応答時間、周辺100m範囲内の密度の高いサンプリングで詳細な精度を提供

#### 洪水浸水想定区域の対象河川数（2025年8月現在）
本APIで取得可能な洪水浸水想定区域の対象河川数は以下の通りです：

**想定最大規模（L2タイル）**
- 国管理河川: 448河川
- 都道府県管理河川: 1,631河川  
- その他河川: 6,597河川
- **合計: 8,676河川**

**計画規模（L1タイル）**
- 国管理河川: 446河川
- 都道府県管理河川: 1,534河川
- その他河川: 3,198河川  
- **合計: 5,178河川**

高精度モード（`precision=high`）では、L2タイルで浸水情報が見つからない場合に自動的にL1タイルからも検索を行い、より包括的な浸水情報を提供します。

### 使用例

#### 全ハザード情報を取得（高速モード）
```bash
# GET リクエスト
curl "https://your-api-endpoint.com?lat=35.6586&lon=139.7454&datum=wgs84&precision=low"

# POST リクエスト
curl -X POST https://your-api-endpoint.com \
  -H "Content-Type: application/json" \
  -d '{"lat": 35.6586, "lon": 139.7454, "datum": "wgs84", "precision": "low"}'
```

#### 特定のハザード情報のみ取得
```bash
# GET リクエスト - 地震と洪水情報のみ
curl "https://your-api-endpoint.com?lat=35.6586&lon=139.7454&hazard_types=earthquake,flood&precision=low"

# POST リクエスト - 津波と土砂災害情報のみ
curl -X POST https://your-api-endpoint.com \
  -H "Content-Type: application/json" \
  -d '{"lat": 35.6586, "lon": 139.7454, "hazard_types": ["tsunami", "landslide"], "precision": "low"}'
```

#### 住所による検索
```bash
# GET リクエスト
curl "https://your-api-endpoint.com?input=東京都千代田区&hazard_types=earthquake&precision=low"

# POST リクエスト
curl -X POST https://your-api-endpoint.com \
  -H "Content-Type: application/json" \
  -d '{"input": "東京都千代田区", "hazard_types": ["earthquake", "flood"], "precision": "low"}'
```

#### 高精度モードでの検索
```bash
# GET リクエスト - 高精度で全ハザード情報を取得
curl "https://your-api-endpoint.com?lat=35.6586&lon=139.7454&precision=high"

# POST リクエスト - 高精度で特定ハザード情報を取得
curl -X POST https://your-api-endpoint.com \
  -H "Content-Type: application/json" \
  -d '{"lat": 35.6586, "lon": 139.7454, "hazard_types": ["earthquake", "landslide"], "precision": "high"}'
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

## 開発・保守

### コード品質

- **リファクタリング済み**: 2024年に大規模リファクタリングを実施し、保守性を大幅向上
- **モジュラー設計**: 機能別に分離されたアーキテクチャで変更影響を局所化
- **テストカバレッジ**: 44の自動テストケースで品質を保証
- **ドキュメント化**: 各モジュール・関数に詳細なdocstringを完備

### 拡張方法

新しいハザード情報を追加する際の推奨手順：

1. **`app/config/constants.py`**: 新しいタイルURL・色マップを定義
2. **`app/utils/color_mapping.py`**: 必要に応じて色マップを追加
3. **`app/hazard_info.py`**: 取得関数を追加
4. **テスト**: 新機能のテストケースを`tests/`に追加
5. **API更新**: `get_selective_hazard_info`にハザードタイプを追加

### トラブルシューティング

- **API応答が遅い場合**: `precision=low`モードを使用してパフォーマンスを優先
- **メモリ不足**: 大規模盛土造成地のR-treeキャッシュがメモリを消費する場合があります
- **テスト失敗**: リファクタリング後は後方互換性を保持していますが、新機能追加時は全テスト実行を推奨

## 変更履歴

### v1.2 (2025年)
- **新ハザード情報追加**: 家屋倒壊等氾濫想定区域（河岸侵食）を追加
  - 新しいAPIパラメータ: `kaokutoukai_kagan`
  - 国土地理院タイル: `01_flood_l2_kaokutoukai_kagan_data` からの色検出方式
  - 判定結果: 色の有無による二値判定（該当あり/該当なし）
  - 包括的テストスイート: 新機能の完全なテストカバレッジを提供

### v1.1 (2024年リファクタリング)
- **大規模リファクタリング実施**: コードの保守性と拡張性を大幅に向上
- **モジュール分割**: `hazard_info.py`（1356行）を機能別モジュールに分離
  - `app/config/constants.py`: 全定数を集約管理
  - `app/utils/color_mapping.py`: 色マップ定義とユーティリティ
  - `app/utils/tile_utils.py`: タイル処理関連機能
- **関数の細分化**: 長大な関数を複数の小さな関数に分割
  - `get_large_scale_filled_land_info_from_geojson`: 200行超 → 3関数に分割
  - `get_inundation_depth_from_gsi_tile`: 138行 → 3関数に分割
- **定数の体系化**: マジックナンバーを意味のある定数名に置き換え
- **色マップの統合**: 重複していた浸水深色マップを統合し、メモリ使用量を削減
- **テスト品質向上**: 全44テストケースで品質保証を維持
- **後方互換性**: 既存のAPIインターフェースは完全に保持

### v1.0
- 初期リリース

## ライセンス

[MIT License](LICENSE)
