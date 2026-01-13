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
