<!-- SEO メタ情報と構造化データ -->
<div itemscope itemtype="https://schema.org/SoftwareApplication" align="center" xmlns="http://www.w3.org/1999/html">
  <meta itemprop="name" content="Dingo: AI データ品質評価ツール">
  <meta itemprop="description" content="機械学習データセット、LLM学習データ検証、幻覚検出、RAGシステム評価のための包括的なAI駆動データ品質評価プラットフォーム">
  <meta itemprop="applicationCategory" content="データ品質ソフトウェア">
  <meta itemprop="operatingSystem" content="クロスプラットフォーム">
  <meta itemprop="programmingLanguage" content="Python">
  <meta itemprop="url" content="https://github.com/MigoXLab/dingo">
  <meta itemprop="downloadUrl" content="https://pypi.org/project/dingo-python/">
  <meta itemprop="softwareVersion" content="latest">
  <meta itemprop="license" content="Apache-2.0">

<!-- logo -->
<p align="center">
  <img src="docs/assets/dingo-logo.png" width="300px" style="vertical-align:middle;" alt="Dingo AI データ品質評価ツール ロゴ">
</p>

<!-- badges -->
<p align="center">
  <a href="https://github.com/pre-commit/pre-commit"><img src="https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white" alt="pre-commit"></a>
  <a href="https://pypi.org/project/dingo-python/"><img src="https://img.shields.io/pypi/v/dingo-python.svg" alt="PyPI version"></a>
  <a href="https://pypi.org/project/dingo-python/"><img src="https://img.shields.io/pypi/pyversions/dingo-python.svg" alt="Python versions"></a>
  <a href="https://github.com/DataEval/dingo/blob/main/LICENSE"><img src="https://img.shields.io/github/license/DataEval/dingo" alt="License"></a>
  <a href="https://github.com/DataEval/dingo/stargazers"><img src="https://img.shields.io/github/stars/DataEval/dingo" alt="GitHub stars"></a>
  <a href="https://github.com/DataEval/dingo/network/members"><img src="https://img.shields.io/github/forks/DataEval/dingo" alt="GitHub forks"></a>
  <a href="https://github.com/DataEval/dingo/issues"><img src="https://img.shields.io/github/issues/DataEval/dingo" alt="GitHub issues"></a>
  <a href="https://mseep.ai/app/dataeval-dingo"><img src="https://mseep.net/pr/dataeval-dingo-badge.png" alt="MseeP.ai Security Assessment Badge" height="20"></a>
  <a href="https://deepwiki.com/MigoXLab/dingo"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki"></a>
  <a href="https://archestra.ai/mcp-catalog/dataeval__dingo"><img src="https://archestra.ai/mcp-catalog/api/badge/quality/DataEval/dingo" alt="Trust Score"></a>
</p>

</div>


<div align="center">

[English](README.md) · [简体中文](README_zh-CN.md) · [日本語](README_ja.md)

</div>


<!-- join us -->

<p align="center">
    👋 <a href="https://discord.gg/Jhgb2eKWh8" target="_blank">Discord</a>と<a href="./docs/assets/wechat.jpg" target="_blank">WeChat</a>でご参加ください
</p>

<p align="center">
  このプロジェクトが役に立ったら、GitHubで⭐を付けてください！
  <br/>
  <a href="https://github.com/DataEval/dingo/stargazers" target="_blank">
    <img src="docs/assets/clickstar_2.gif" alt="Star をクリック" width="480">
  </a>
</p>


# はじめに

Dingoは、データセット内のデータ品質問題を自動的に検出するデータ品質評価ツールです。Dingoは様々な組み込みルールとモデル評価手法を提供し、カスタム評価手法もサポートしています。Dingoは一般的に使用されるテキストデータセットとマルチモーダルデータセット（事前学習データセット、ファインチューニングデータセット、評価データセットを含む）をサポートしています。さらに、DingoはローカルCLIやSDKなど複数の使用方法をサポートし、[OpenCompass](https://github.com/open-compass/opencompass)などの様々な評価プラットフォームに簡単に統合できます。

## アーキテクチャ図

![Architecture of dingo](./docs/assets/architeture.png)

# クイックスタート

## インストール

```shell
pip install dingo-python
```

## 使用例

### 1. LLMチャットデータの評価

```python
from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io.input import Data
from dingo.model.llm.text_quality.llm_text_quality_v4 import LLMTextQualityV4
from dingo.model.rule.rule_common import RuleEnterAndSpace

data = Data(
    data_id='123',
    prompt="hello, introduce the world",
    content="Hello! The world is a vast and diverse place, full of wonders, cultures, and incredible natural beauty."
)


def llm():
    LLMTextQualityV4.dynamic_config = EvaluatorLLMArgs(
        key='YOUR_API_KEY',
        api_url='https://api.openai.com/v1/chat/completions',
        model='gpt-4o',
    )
    res = LLMTextQualityV4.eval(data)
    print(res)


def rule():
    res = RuleEnterAndSpace().eval(data)
    print(res)
```

### 2. データセットの評価

```python
from dingo.config import InputArgs
from dingo.exec import Executor

# Hugging Faceからデータセットを評価
input_data = {
    "input_path": "tatsu-lab/alpaca",  # Hugging Faceからのデータセット
    "dataset": {
        "source": "hugging_face",
        "format": "plaintext"  # フォーマット: plaintext
    },
    "executor": {
        "result_save": {
            "bad": True  # 評価結果を保存
        }
    },
    "evaluator": [
        {
            "evals": [
                {"name": "RuleColonEnd"},
                {"name": "RuleSpecialCharacter"}
            ]
        }
    ]
}

input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
result = executor.execute()
print(result)
```

## コマンドラインインターフェース

### ルールセットでの評価

```shell
python -m dingo.run.cli --input test/env/local_plaintext.json
```

### LLM（例：GPT-4o）での評価

```shell
python -m dingo.run.cli --input test/env/local_json.json
```

## GUI可視化

評価後（`result_save.bad=True`で）、フロントエンドページが自動的に生成されます。手動でフロントエンドを開始するには：

```shell
python -m dingo.run.vsl --input output_directory
```

ここで`output_directory`は`summary.json`ファイルを含む評価結果が格納されているディレクトリです。

![GUI output](docs/assets/dingo_gui.png)

## オンラインデモ
オンラインデモでDingoをお試しください: [(Hugging Face)🤗](https://huggingface.co/spaces/DataEval/dingo)

## ローカルデモ
地元でDingoを試してみましょう：

```shell
cd app_gradio
python app.py
```

![Gradio demo](docs/assets/gradio_demo.png)

## Google Colabデモ
Google ColabノートブックでDingoをインタラクティブに体験してください：[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/DataEval/dingo/blob/dev/examples/colab/dingo_colab_demo.ipynb)


# MCPサーバー

Dingoには実験的なModel Context Protocol（MCP）サーバーが含まれています。サーバーの実行とCursorなどのクライアントとの統合の詳細については、専用のドキュメントをご覧ください：

[English](README_mcp.md) · [简体中文](README_mcp_zh-CN.md) · [日本語](README_mcp_ja.md)

## ビデオデモンストレーション

Dingo MCPを素早く始められるよう、ビデオウォークスルーを作成しました：

https://github.com/user-attachments/assets/aca26f4c-3f2e-445e-9ef9-9331c4d7a37b

このビデオでは、Dingo MCPサーバーをCursorと一緒に使用する方法をステップバイステップで説明しています。


# データ品質メトリクス

Dingoはルールベースおよびプロンプトベースの評価メトリクスを通じて包括的なデータ品質評価を提供します。これらのメトリクスは、効果性、完全性、類似性、セキュリティなどの複数の品質次元をカバーしています。

📊 **[完全なメトリクス文書を表示 →](docs/metrics.md)**

評価システムには以下が含まれます：
- **テキスト品質評価メトリクス**: DataMan手法と拡張された多次元評価を使用した事前学習データの品質評価
- **SFTデータ評価メトリクス**: 教師ありファインチューニングデータの正直、有用、無害評価
- **分類メトリクス**: トピック分類とコンテンツ分類
- **マルチモーダル評価メトリクス**: 画像分類と関連性評価
- **ルールベース品質メトリクス**: ヒューリスティックルールによる効果性と類似性検出を用いた自動品質チェック
- **事実性評価メトリクス**: GPT-5 System Cardに基づく二段階事実性評価
- など

大部分のメトリクスは学術的なソースによって支持されており、客観性と科学的厳密性を保証しています。

### 評価でのLLM評価の使用

これらの評価プロンプトを評価で使用するには、設定で指定します：

```python
llm_config = {
    "model": "gpt-4o",
    "key": "YOUR_API_KEY",
    "api_url": "https://api.openai.com/v1/chat/completions"
}
input_data = {
    # Other parameters...
    "evaluator": [
        {
            "fields": {"content": "content"},
            "evals": [
                {"name": "LLMTextRepeat", "config": llm_config}
            ],
        }
    ]
}
```

これらのプロンプトは、特定の品質次元に焦点を当てたり、特定のドメイン要件に適応させるためにカスタマイズできます。適切なLLMモデルと組み合わせることで、これらのプロンプトは複数の次元にわたる包括的なデータ品質評価を可能にします。

### 幻覚検出とRAGシステム評価

HHEM-2.1-Openローカル推論とLLMベース評価を含む、Dingoの幻覚検出機能の使用に関する詳細なガイダンス：

📖 **[幻覚検出ガイドを見る →](docs/hallucination_guide.md)**

### 事実性評価

Dingoの二段階事実性評価システムの使用に関する詳細なガイダンス：

📖 **[事実性評価ガイドを見る →](docs/factcheck_guide.md)**


# 機能ハイライト

## マルチソース・マルチモーダルサポート

- **データソース**: ローカルファイル、Hugging Faceデータセット、S3ストレージ
- **データタイプ**: 事前学習、ファインチューニング、評価データセット
- **データモダリティ**: テキストと画像

## ルールベース・モデルベース評価

- **内蔵ルール**: 20以上の一般的なヒューリスティック評価ルール
- **LLM統合**: OpenAI、Kimi、ローカルモデル（例：Llama3）
- **幻覚検出**: HHEM-2.1-OpenローカルモデルとGPTベースの評価
- **RAGシステム評価**: 応答一貫性とコンテキスト整合性評価
- **カスタムルール**: 独自のルールとモデルで簡単に拡張
- **セキュリティ評価**: Perspective API統合

## 柔軟な使用方法

- **インターフェース**: CLIとSDKオプション
- **統合**: 他のプラットフォームとの簡単な統合
- **実行エンジン**: ローカルとSpark

## 包括的なレポート

- **品質メトリクス**: 7次元品質評価
- **トレーサビリティ**: 異常追跡のための詳細レポート

# ユーザーガイド

## カスタムルール、プロンプト、モデル

組み込みルールが要件を満たさない場合、カスタムルールを作成できます：

### カスタムルール例

```python
from dingo.model import Model
from dingo.model.rule.base import BaseRule
from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io import Data
from dingo.model.modelres import ModelRes

@Model.rule_register('QUALITY_BAD_RELEVANCE', ['default'])
class MyCustomRule(BaseRule):
    """テキスト内のカスタムパターンをチェック"""

    dynamic_config = EvaluatorRuleArgs(pattern=r'your_pattern_here')

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        # ここにルール実装
        return res
```

### カスタムLLM統合

```python
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI

@Model.llm_register('my_custom_model')
class MyCustomModel(BaseOpenAI):
    # ここにカスタム実装
    pass
```

詳細な例については以下をご覧ください：
- [ルール登録](examples/register/sdk_register_rule.py)
- [プロンプト登録](examples/register/sdk_register_prompt.py)
- [モデル登録](examples/register/sdk_register_llm.py)

## 実行エンジン

### ローカル実行

```python
from dingo.config import InputArgs
from dingo.exec import Executor

input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
result = executor.execute()

# 結果を取得
summary = executor.get_summary()        # 全体的な評価サマリー
bad_data = executor.get_bad_info_list() # 問題のあるデータのリスト
good_data = executor.get_good_info_list() # 高品質データのリスト
```

### Spark実行

```python
from dingo.config import InputArgs
from dingo.exec import Executor
from pyspark.sql import SparkSession

# Sparkを初期化
spark = SparkSession.builder.appName("Dingo").getOrCreate()
spark_rdd = spark.sparkContext.parallelize([...])  # Dataオブジェクトとしてのデータ

input_data = {
    "executor": {
        "result_save": {"bad": True}
    },
    "evaluator": [
        {
            "fields": {"content": "content"},
            "evals": [
                {"name": "RuleColonEnd"},
                {"name": "RuleSpecialCharacter"}
            ]
        }
    ]
}
input_args = InputArgs(**input_data)
executor = Executor.exec_map["spark"](input_args, spark_session=spark, spark_rdd=spark_rdd)
result = executor.execute()
```

## 評価レポート

評価後、Dingoは以下を生成します：

1. **サマリーレポート** (`summary.json`): 全体的なメトリクスとスコア
2. **詳細レポート**: 各ルール違反の具体的な問題

レポートの説明：
1. **score**: `num_good` / `total`
2. **type_ratio**: タイプの数 / 総数, 例: `QUALITY_BAD_COMPLETENESS` / `total`
3. **name_ratio**: 名前の数 / 総数, 例: `QUALITY_BAD_COMPLETENESS-RuleColonEnd` / `total`

サマリー例：
```json
{
    "task_id": "d6c922ec-981c-11ef-b723-7c10c9512fac",
    "task_name": "dingo",
    "eval_group": "default",
    "input_path": "test/data/test_local_jsonl.jsonl",
    "output_path": "outputs/d6c921ac-981c-11ef-b723-7c10c9512fac",
    "create_time": "20241101_144510",
    "score": 50.0,
    "num_good": 1,
    "num_bad": 1,
    "total": 2,
    "type_ratio": {
        "content": {
            "QUALITY_BAD_COMPLETENESS.RuleColonEnd": 0.5,
            "QUALITY_BAD_RELEVANCE.RuleSpecialCharacter": 0.5
        }
    }
}
```

# 今後の計画

- [ ] より豊富なグラフィックとテキスト評価指標
- [ ] 音声・動画データモダリティ評価
- [ ] 小規模モデル評価（fasttext、Qurating）
- [ ] データ多様性評価

# 制限事項

現在の組み込み検出ルールとモデル手法は、一般的なデータ品質問題に焦点を当てています。専門的な評価ニーズについては、検出ルールのカスタマイズを推奨します。

# 謝辞

- [RedPajama-Data](https://github.com/togethercomputer/RedPajama-Data)
- [mlflow](https://github.com/mlflow/mlflow)
- [deepeval](https://github.com/confident-ai/deepeval)
- [ragas](https://github.com/explodinggradients/ragas)

# 貢献

`Dingo`の改善と強化に努力してくださったすべての貢献者に感謝いたします。プロジェクトへの貢献に関するガイダンスについては、[貢献ガイド](docs/en/CONTRIBUTING.md)をご参照ください。

# ライセンス

このプロジェクトは[Apache 2.0オープンソースライセンス](LICENSE)を使用しています。

このプロジェクトは言語検出を含む一部の機能でfasttextを使用しています。fasttextはMITライセンスの下でライセンスされており、これは当社のApache 2.0ライセンスと互換性があり、様々な使用シナリオに柔軟性を提供します。

# 引用

このプロジェクトが有用だと思われる場合は、当社のツールの引用をご検討ください：

```
@misc{dingo,
  title={Dingo: A Comprehensive Data Quality Evaluation Tool for Large Models},
  author={Dingo Contributors},
  howpublished={\url{https://github.com/DataEval/dingo}},
  year={2024}
}
```
