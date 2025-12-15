# HealthmateUI サービス

## Service Overview

HealthmateUI サービスは、Healthmate プロダクトのWebフロントエンドを担当し、ユーザーが健康管理機能にアクセスするためのインターフェースを提供します。

### Primary Responsibilities

- **User Interface**: 健康データの入力・表示・管理のためのWebUI
- **Authentication Flow**: Cognito OAuth 2.0による認証フロー管理
- **MCP API Integration**: HealthManagerMCP サービスとの連携
- **AI Agent Integration**: HealthCoachAI サービスとのチャット機能
- **Multi-language Support**: 日本語・英語対応

### Service Architecture

- **Framework**: TBD (React/Vue.js/Angular等のモダンWebフレームワーク)
- **Authentication**: Amazon Cognito OAuth 2.0 integration
- **API Communication**: RESTful API calls to MCP Gateway
- **State Management**: TBD (Redux/Vuex/Pinia等)
- **Styling**: TBD (Tailwind CSS/Material-UI/Chakra UI等)

### Key Features

#### Health Data Management
- **User Profile**: ユーザー情報の表示・編集
- **Goal Setting**: 健康目標の作成・管理・進捗表示
- **Policy Management**: 健康ポリシーの設定・管理
- **Activity Logging**: 日々の活動記録（食事、運動、体重等）

#### AI Integration
- **Health Coach Chat**: HealthCoachAI サービスとのリアルタイムチャット
- **Personalized Advice**: AIからの健康アドバイス表示
- **Progress Analysis**: AIによる健康データ分析結果の可視化

### Authentication Patterns

#### Cognito OAuth 2.0 Flow
```javascript
// 認証設定例
const authConfig = {
  ClientId: process.env.REACT_APP_COGNITO_CLIENT_ID,
  AppWebDomain: 'healthmate.auth.us-west-2.amazoncognito.com',
  TokenScopesArray: ['openid', 'profile', 'email', 'phone'],
  RedirectUriSignIn: window.location.origin + '/callback',
  RedirectUriSignOut: window.location.origin + '/signout'
};
```

#### JWT Token Management
```javascript
// JWTトークンの管理と自動更新
const useAuth = () => {
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  
  // Token refresh logic
  // User session management
};
```

### API Integration Patterns

#### MCP API Calls
```javascript
// HealthManagerMCP サービスとの連携
const apiClient = {
  baseURL: process.env.REACT_APP_MCP_GATEWAY_URL,
  
  async callMCPTool(toolName, parameters) {
    const token = await getValidToken();
    return fetch(`${this.baseURL}/${toolName}`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(parameters)
    });
  }
};
```

#### Error Handling
```javascript
// 統一されたエラーハンドリング
const handleAPIError = (error) => {
  if (error.status === 401) {
    // Token expired - redirect to login
  } else if (error.status === 403) {
    // Insufficient permissions
  } else {
    // General error handling
  }
};
```

### UI/UX Patterns

#### Responsive Design
- **Mobile-First**: スマートフォンでの利用を優先
- **Progressive Web App**: PWA対応でネイティブアプリ体験
- **Accessibility**: WCAG 2.1 AA準拠のアクセシビリティ

#### Component Structure
```
src/
├── components/
│   ├── common/          # 共通コンポーネント
│   ├── auth/           # 認証関連
│   ├── health/         # 健康管理機能
│   └── chat/           # AIチャット機能
├── pages/              # ページコンポーネント
├── hooks/              # カスタムフック
├── services/           # API呼び出しロジック
└── utils/              # ユーティリティ関数
```

### State Management Patterns

#### Health Data State
```javascript
// 健康データの状態管理
const healthStore = {
  user: null,
  goals: [],
  policies: [],
  activities: {},
  
  // Actions
  fetchUserData: async () => {},
  updateGoal: async (goalId, updates) => {},
  addActivity: async (date, activity) => {}
};
```

#### Chat State
```javascript
// AIチャットの状態管理
const chatStore = {
  messages: [],
  isTyping: false,
  connectionStatus: 'connected',
  
  // Actions
  sendMessage: async (message) => {},
  receiveMessage: (message) => {}
};
```

### Development Patterns

#### Environment Configuration
```javascript
// 環境別設定
const config = {
  development: {
    MCP_GATEWAY_URL: 'https://dev-gateway.example.com',
    COGNITO_CLIENT_ID: 'dev-client-id'
  },
  production: {
    MCP_GATEWAY_URL: 'https://prod-gateway.example.com',
    COGNITO_CLIENT_ID: 'prod-client-id'
  }
};
```

#### Testing Strategy
- **Unit Tests**: コンポーネント単体テスト
- **Integration Tests**: API連携テスト
- **E2E Tests**: ユーザーフロー全体のテスト
- **Accessibility Tests**: アクセシビリティ自動テスト

### Integration Points

- **HealthManagerMCP サービス**: MCP Gateway経由でのデータCRUD操作
- **HealthCoachAI サービス**: WebSocket/Server-Sent Eventsでのリアルタイムチャット
- **Amazon Cognito**: ユーザー認証・認可・プロファイル管理

### Service-Specific Best Practices

- **Security**: JWTトークンの安全な保存（HttpOnly cookies推奨）
- **Performance**: 健康データの効率的なキャッシング
- **User Experience**: オフライン対応とデータ同期
- **Privacy**: 健康データの適切な暗号化と表示制御
- **Internationalization**: 多言語対応の実装パターン