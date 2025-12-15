# HealthmateUI

HealthmateUIは、ユーザがHealthCoachAIと対話するためのWebベースのチャットインターフェースです。htmxを使用したレスポンシブなフロントエンドと、Python FastAPIを使用したBFF（Backend for Frontend）で構成されます。

## 🌟 特徴

- 🔐 **Cognito認証**: 既存のHealthManagerMCPのCognito User Poolを利用
- 🤖 **AI連携**: HealthCoachAIとのリアルタイムストリーミングチャット
- 📱 **レスポンシブUI**: htmxを使用したモダンなWebインターフェース
- ⚡ **高速配信**: S3 + CloudFrontによる静的コンテンツ配信
- 🚀 **サーバーレス**: AWS Lambda上でのFastAPI実行

## 🏗️ アーキテクチャ

```
ユーザー → CloudFront → S3 (静的コンテンツ)
         ↓
         Lambda Function URL → FastAPI BFF
         ↓
         HealthCoachAI (AgentCore Runtime)
         ↓
         HealthManagerMCP (健康データ)
```

## 🛠️ 技術スタック

### フロントエンド
- **UI Framework**: htmx + HTML/CSS/JavaScript
- **Static Hosting**: Amazon S3 + CloudFront

### バックエンド
- **Runtime**: AWS Lambda (Python 3.12)
- **Web Framework**: FastAPI
- **Container**: Docker + Amazon ECR
- **Function URL**: ストリーミング対応

### 既存システム連携
- **認証**: Amazon Cognito User Pool (us-west-2_H5DVWxi8O)
- **AI**: HealthCoachAI (health_coach_ai-87qw32GDCf)
- **データ**: HealthManagerMCP Gateway

## 🚀 開発環境セットアップ

### 前提条件

- Python 3.12+
- AWS CLI v2 (設定済み)
- 既存のHealthManagerMCPとHealthCoachAIがデプロイ済み

### インストール

```bash
# リポジトリをクローン
cd HealthmateUI

# Python仮想環境を作成
python3.12 -m venv .venv
source .venv/bin/activate  # macOS/Linux

# 依存関係をインストール
pip install -r requirements.txt

# 環境変数を設定（オプション）
cp .env.example .env
# 必要に応じて.envファイルを編集
```

### 🔧 自動設定機能

開発サーバーは必要な設定を自動的に取得します：

```bash
# 開発サーバーを起動（自動設定付き）
python run_dev.py
```

自動設定される項目：
- ✅ **AWS Account ID**: AWS STSから取得
- ✅ **Cognito User Pool ID**: CloudFormationスタックから取得
- ✅ **Cognito Client ID**: CloudFormationスタックから取得
- ✅ **Cognito Client Secret**: Cognito AWS APIから取得
- ✅ **HealthCoachAI Runtime ID**: AgentCore AWS APIから取得

### 手動設定（必要な場合のみ）

自動設定が失敗する場合は、`.env`ファイルで手動設定：

```bash
# .envファイルを編集
AWS_ACCOUNT_ID=123456789012
COGNITO_USER_POOL_ID=us-west-2_XXXXXXXXX
COGNITO_CLIENT_ID=your-client-id
COGNITO_CLIENT_SECRET=your-client-secret
HEALTH_COACH_AI_RUNTIME_ID=health_coach_ai-XXXXXXXXX
MCP_GATEWAY_ENDPOINT=https://your-gateway.agentcore.region.amazonaws.com
```

### 設定確認

```bash
# 設定が正しく読み込まれることを確認
python run_dev.py
# または
python -c "
import os
os.environ['AWS_ACCOUNT_ID'] = 'test'
os.environ['COGNITO_USER_POOL_ID'] = 'test'
os.environ['COGNITO_CLIENT_ID'] = 'test'
os.environ['COGNITO_CLIENT_SECRET'] = 'test'
os.environ['HEALTH_COACH_AI_RUNTIME_ID'] = 'test'
os.environ['MCP_GATEWAY_ENDPOINT'] = 'test'
from app.utils.config import get_config
config = get_config()
print(f'Environment: {config.__class__.__name__}')
print('✅ Configuration loaded successfully')
"
```

## 📁 プロジェクト構造

```
HealthmateUI/
├── app/                          # FastAPIアプリケーション
│   ├── auth/                    # 認証モジュール
│   │   ├── cognito.py          # Cognito認証クライアント
│   │   ├── session.py          # セッション管理
│   │   ├── middleware.py       # 認証ミドルウェア
│   │   └── routes.py           # 認証APIルート
│   ├── chat/                    # チャット機能
│   ├── models/                  # データモデル
│   │   └── auth.py             # 認証関連モデル
│   └── utils/                   # ユーティリティ
│       ├── config.py           # 設定管理
│       └── logger.py           # ログ設定
├── static/                      # 静的ファイル
│   ├── css/                    # スタイルシート
│   └── js/                     # JavaScript
├── templates/                   # HTMLテンプレート
├── tests/                       # テストスイート
├── cdk/                         # AWS CDKインフラ
├── requirements.txt             # Python依存関係
├── pytest.ini                  # テスト設定
└── .env                        # 環境変数
```

## 🔧 開発コマンド

### テスト実行

```bash
# 単体テスト
pytest tests/unit/ -v

# 統合テスト
pytest tests/integration/ -v

# カバレッジ付きテスト
pytest --cov=app --cov-report=html
```

### コード品質

```bash
# フォーマット
black app/ tests/

# リント
flake8 app/ tests/

# 型チェック
mypy app/
```

## 🌐 既存システム連携

### HealthManagerMCP
- **認証**: Cognito User Pool（CloudFormationから自動取得）
- **Gateway**: MCP Gateway Endpoint（CloudFormationから自動取得）

### HealthCoachAI
- **Runtime ID**: AgentCore CLIから自動取得
- **Region**: us-west-2
- **連携方法**: AgentCore CLI (`agentcore invoke`)

## 🔧 トラブルシューティング

### 設定エラー

```bash
❌ Configuration Error: Missing required environment variables
```

**解決方法**:
1. AWS認証を確認: `aws sts get-caller-identity`
2. CloudFormationスタックを確認: `aws cloudformation describe-stacks --stack-name healthmate-stack`
3. AgentCoreを確認: `agentcore list`
4. 手動で`.env`ファイルに設定を追加

### AWS認証エラー

```bash
⚠️ AWS credentials not configured
```

**解決方法**:
```bash
aws configure
# または
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_DEFAULT_REGION=us-west-2
```

### CloudFormationスタックが見つからない

```bash
⚠️ CloudFormation stack 'healthmate-stack' not found
```

**解決方法**:
```bash
# カスタムスタック名を指定
export HEALTH_STACK_NAME=your-actual-stack-name
python run_dev.py
```

### Cognito Client Secretが取得できない

```bash
⚠️ Could not get Cognito Client Secret
```

**解決方法**:
```bash
# Cognito権限を確認
aws cognito-idp describe-user-pool-client --user-pool-id us-west-2_XXXXXXXXX --client-id your-client-id

# 手動設定
export COGNITO_CLIENT_SECRET=your-client-secret
```

### AgentCoreランタイムが見つからない

```bash
⚠️ Could not get HealthCoachAI Runtime ID
```

**解決方法**:
```bash
# AgentCoreをインストール
pip install agentcore

# ランタイムを確認
agentcore list

# 手動設定
export HEALTH_COACH_AI_RUNTIME_ID=your-runtime-id
```

## 📊 開発状況

| フェーズ | 状況 | 説明 |
|---------|------|------|
| ✅ Phase 1 | 完了 | 開発環境セットアップ |
| ✅ Phase 2 | 完了 | FastAPIバックエンド基盤 |
| ✅ Phase 3 | 完了 | Cognito認証システム |
| 🔄 Phase 4 | 進行中 | HealthCoachAI連携 |
| ⏳ Phase 3 | 予定 | フロントエンド実装 |
| ⏳ Phase 4 | 予定 | AWS CDKインフラ |
| ⏳ Phase 5 | 予定 | デプロイと統合テスト |

## 🤝 コントリビューション

1. フィーチャーブランチを作成
2. 変更をコミット
3. テストを実行して通ることを確認
4. プルリクエストを作成

## 📄 ライセンス

このプロジェクトはMITライセンスの下で公開されています。

---

**HealthmateUI** - Empowering seamless health coaching conversations 💬✨