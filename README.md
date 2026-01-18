# キャラ演技LLM（CUI）実装 v1.01

## 概要
本アプリケーションは、LLMに特定のキャラクターを演じさせ、CUI上で対話するための
キャラクター会話エンジンです。

キャラクターの人格・話し方・過去エピソードはすべてYAMLで外部定義され、
それらをシステムプロンプトとして統合することで、一貫したキャラ性を保った会話を実現します。

会話はセッション単位で管理され、SQLiteに永続保存されるため、
アプリを再起動しても同じキャラクターとの会話を継続できます。

将来的なGUI化、ゲームエンジン連携、感情モデル導入を見据えた
拡張可能な対話コアとして設計されています。

## セットアップ
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## 実行
```powershell
python -m app
```

LM Studio でモデルをロードし、Local Server(OpenAI互換API)を有効化しておいてください。


デフォルトキャラクター: 下賀茂トキナ（shimogamo_tokina）


## 初回起動時のTTSセットアップ
初回起動時に `tts.bootstrap.enabled: true` の場合、`Style-Bert-VITS2` を `third_party/Style-Bert-VITS2` に取得し、依存関係を `pip install -r` で導入します（ネットワークと git が必要）。


### JP-Extra（モデルデータ）の自動取得
`tts.bootstrap.download_models: true` の場合、初回起動時に Style-Bert-VITS2 フォルダ内で `python initialize.py` を実行し、JP-Extraを含む事前学習モデル/デフォルトTTSモデルを自動取得します（大容量・ネットワーク必須）。


### git の自動準備
初回起動時、git が見つからない場合は Windows 環境では `winget` を用いて Git for Windows のインストールを試みます。失敗した場合は手動インストールを案内します。
