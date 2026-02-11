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
本リポジトリでは `uv` を使用します。事前に以下を実行して `uv` を導入してください。

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

セットアップ手順は `Setup.cmd` が自動で実行します。

```powershell
.\Setup.cmd
```

## 実行
起動手順は `Run.cmd` が自動で実行します。

```powershell
.\Run.cmd
```

キャラクターを指定して起動する場合は `--character` オプションを利用します。

```powershell
.\Run.cmd --character kanya_kibuni
```

LM Studio でモデルをロードし、Local Server(OpenAI互換API)を有効化しておいてください。


デフォルトキャラクター: 下賀茂トキナ（shimogamo_tokina）

## Style-Bert-VITS2 のセットアップについて
Style-Bert-VITS2 (ver.2.7.0) は本リポジトリに同梱されています。`Setup.cmd` では、
`Style-Bert-VITS2-2.7.0` 内で `uv` を用いて依存関係とモデルを準備します。

本アプリケーションにおいて TTS は推論と音声出力のみに使用されます。
マージや新規モデルの作成には対応していません。

## VTube Studio 連携（Live2Dモーション）
LLMの `actions` / `emotion` をアバター制御コマンドへ変換し、バックエンド経由で送信できます。
実装は `app/avatar_control` に分離されており、将来は VTube Studio 以外のバックエンドへ差し替え可能です。

- `avatar.enabled`: 有効化
- `avatar.backend`: `none` または `vtube_studio`
- `avatar.action_to_hotkey`: `actions` 名からVTSホットキーへの対応表
- `avatar.emotion_to_hotkey`: `actions` が空の時に使う感情→ホットキー対応表
- `avatar.vtube_studio.*`: WebSocket接続・プラグイン認証設定

初回接続時はVTube Studio側でプラグイン認証を許可してください。
認証トークンは `avatar.vtube_studio.auth_token_path` に保存されます。
