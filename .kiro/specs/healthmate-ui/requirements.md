# 要件文書

## 概要

HealthmateUIは、ユーザがHealthCoachAIと対話するためのWebベースのチャットインターフェースです。Cognito認証を使用したセキュアなログイン機能と、Amazon Bedrock AgentCoreランタイムとのリアルタイムストリーミング連携を提供します。FastAPIバックエンド（BFF）とhtmxフロントエンドで構成され、AWS Lambda上で動作します。

## 用語集

- **HealthmateUI**: ユーザとHealthCoachAIの対話を可能にするWebアプリケーション
- **HealthCoachAI**: Amazon Bedrock AgentCoreで実行される健康コーチAIエージェント
- **Cognito_UserPool**: AWS Cognitoユーザープールによる認証システム
- **JWT_AccessToken**: Cognitoから発行されるJSONWebトークンアクセストークン
- **AgentCore_Memory**: Amazon Bedrock AgentCoreのメモリ機能によるチャット履歴管理
- **FastAPI_Backend**: Backend for Frontendとして動作するFastAPIサーバ
- **HTMX_Frontend**: htmxライブラリを使用したフロントエンド画面
- **Lambda_Function**: AWS Lambda上で動作するFastAPIアプリケーション
- **S3_StaticContent**: S3から配信される静的コンテンツ（htmxファイル等）

## 要件

### 要件 1

**ユーザストーリー:** ユーザとして、Cognito認証を使用してログインしたい。そうすることで、HealthCoach AIチャットインターフェースに安全にアクセスできる。

#### 受入基準

1. ユーザがアプリケーションにアクセスした時、HealthmateUIはCognitoログインインターフェースを表示する
2. ユーザが有効なCognito認証情報を提供した時、HealthmateUIはユーザを認証しJWTアクセストークンを取得する
3. 認証が成功した時、HealthmateUIはユーザをチャットインターフェースにリダイレクトする
4. 認証が失敗した時、HealthmateUIはエラーメッセージを表示しログイン状態を維持する
5. ユーザセッションが期限切れになった時、HealthmateUIはユーザをログインインターフェースにリダイレクトする

### 要件 2

**ユーザストーリー:** ログインしたユーザとして、HealthCoach AIとリアルタイムでチャットしたい。そうすることで、即座に健康コーチングのガイダンスを受けることができる。

#### 受入基準

1. ユーザがメッセージを送信した時、HealthmateUIはFastAPIバックエンド経由でHealthCoachAIにメッセージを送信する
2. HealthCoachAIが応答した時、HealthmateUIはストリーミングを使用してリアルタイムで応答を表示する
3. ストリーミングデータを受信した時、HealthmateUIはページリフレッシュなしでチャットインターフェースを段階的に更新する
4. メッセージが送信された時、HealthmateUIは入力フィールドをクリアし次のメッセージのためにフォーカスを維持する
5. チャットインターフェースが読み込まれた時、HealthmateUIはAgentCore Memoryを使用して以前の会話履歴を表示する

### 要件 3

**ユーザストーリー:** システム管理者として、JWTアクセストークンがHealthCoach AIに渡されることを望む。そうすることで、バックエンドMCPサーバがユーザリクエストを認可できる。

#### 受入基準

1. HealthCoachAIにリクエストを行う時、FastAPI_BackendはリクエストヘッダーにJWT_AccessTokenを含める
2. JWTトークンが無効または期限切れの時、FastAPI_Backendは認可エラーを適切に処理する
3. トークンリフレッシュが必要な時、FastAPI_BackendはCognitoを使用してトークンのリフレッシュを試行する
4. トークンリフレッシュが失敗した時、FastAPI_Backendはフロントエンドに認証エラーを返す

### 要件 4

**ユーザストーリー:** ユーザとして、チャット履歴を見たい。そうすることで、HealthCoach AIとの以前の会話を確認できる。

#### 受入基準

1. ユーザがログインした時、HealthmateUIはAgentCore_Memoryを使用して以前のチャット履歴を取得し表示する
2. チャット履歴を表示する時、HealthmateUIはタイムスタンプ付きで時系列順にメッセージを表示する
3. チャット履歴が読み込まれた時、HealthmateUIは最新のメッセージまでスクロールする
4. 新しいメッセージが追加された時、HealthmateUIは既存の履歴に追加する

### 要件 5

**ユーザストーリー:** 開発者として、アプリケーションがAWSインフラストラクチャにデプロイされることを望む。そうすることで、スケールし他のAWSサービスと統合できる。

#### 受入基準

1. FastAPIバックエンドがデプロイされた時、Lambda_FunctionはFunction URLを有効にしAuthをNONEに設定して実行する
2. ストリーミングが必要な時、Lambda_FunctionはAWS_LWA_INVOKE_MODE環境変数をresponse_streamに設定する
3. 静的コンテンツを配信する時、S3_StaticContentはhtmxファイルやその他のフロントエンドアセットを配信する
4. アプリケーションがコンテナ化された時、FastAPI_BackendはDockerイメージとしてパッケージ化されECRに保存される
5. Lambda関数が呼び出された時、FastAPI_BackendはFunction URL経由でHTTPリクエストを処理する

### 要件 6

**ユーザストーリー:** ユーザとして、htmxで構築されたレスポンシブなチャットインターフェースを使いたい。そうすることで、ページ全体のリロードなしでスムーズな会話体験ができる。

#### 受入基準

1. ユーザインタラクションが発生した時、HTMX_Frontendはページの必要な部分のみを更新する
2. メッセージが送信または受信された時、HTMX_Frontendは適切に現在のスクロール位置を維持する
3. インターフェースが更新された時、HTMX_Frontendはユーザアクションに対する視覚的フィードバックを提供する
4. エラーが発生した時、HTMX_Frontendはチャットフローを妨げることなくエラーメッセージを表示する
5. ページが読み込まれた時、HTMX_Frontendは適切なスタイリングとレイアウトでチャットインターフェースを初期化する