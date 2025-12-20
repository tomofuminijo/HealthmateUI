# Implementation Plan: Code Cleanup

## Overview

HealthmateUI サービスの実装を見直し、重複したコード、未使用のモジュール、過度に複雑な実装を排除します。統合されたチャット API、簡素化された設定管理、統一されたデータモデルを実装し、保守性と可読性を向上させます。

## Tasks

- [x] 1. データモデルの統合
- [x] 1.1 重複したモデル定義を特定し統合する
  - `models/chat.py` と `healthcoach/models.py` の `ChatMessage`, `MessageRole` を統合
  - 統一されたモデルを `app/models/` に配置
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [ ]* 1.2 モデル統合のプロパティテストを作成
  - **Property 5: Model Definition Consolidation**
  - **Validates: Requirements 5.1, 5.2, 5.3, 5.4**

- [x] 2. チャット API の統合
- [x] 2.1 重複したチャット機能を統合する
  - `/api/chat.py` と `/api/streaming.py` の機能を単一の API に統合
  - ストリーミング/非ストリーミングを `stream` パラメータで制御
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [ ]* 2.2 統合チャット API のプロパティテストを作成
  - **Property 1: Unified Chat API Implementation**
  - **Validates: Requirements 1.1, 1.2, 1.3, 1.4**

- [x] 3. 設定管理の簡素化
- [x] 3.1 複雑な自動設定ロジックを簡素化する
  - `run_dev.py` から AWS API 自動呼び出しを削除
  - 環境変数と `.env` ファイルからの設定読み込みのみに簡素化
  - 必須設定不足時の明確なエラーメッセージを実装
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [ ]* 3.2 設定管理のプロパティテストを作成
  - **Property 2: Simplified Configuration Management**
  - **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**

- [x] 4. 未使用コードとサービスの削除
- [x] 4.1 未使用のサービスモジュールを削除する
  - `streaming_service.py` が実際に使用されているかを確認し、未使用なら削除
  - 未使用のインポートと依存関係を削除
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 4.2 サービス層を簡素化する
  - `chat_service.py` の複雑な機能を簡素化
  - 開発用のシンプルなインメモリストレージに変更
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [ ]* 4.3 コード削除とサービス簡素化のプロパティテストを作成
  - **Property 3: Dead Code Elimination**
  - **Property 4: Service Layer Simplification**
  - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 4.4**

- [x] 5. Checkpoint - 基本機能の動作確認
- Ensure all tests pass, ask the user if questions arise.

- [ ] 6. 依存関係の最適化
- [ ] 6.1 未使用の依存関係を特定し削除する
  - `requirements.txt` の各依存関係が実際に使用されているかを確認
  - 重複機能を提供するライブラリを統一
  - 必要最小限の依存関係のみを維持
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [ ]* 6.2 依存関係最適化のプロパティテストを作成
  - **Property 6: Dependency Optimization**
  - **Validates: Requirements 6.1, 6.2, 6.3, 6.4**

- [ ] 7. エラーハンドリングの統一
- [ ] 7.1 一貫したエラーハンドリングを実装する
  - 統一されたエラーレスポンス形式を定義
  - ネストした try-catch ブロックを簡素化
  - 明確で実用的なエラーメッセージを実装
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [ ]* 7.2 エラーハンドリングのプロパティテストを作成
  - **Property 7: Consistent Error Handling**
  - **Validates: Requirements 7.1, 7.2, 7.3, 7.4**

- [ ] 8. テストファイルの整理
- [ ] 8.1 散らばったテストファイルを整理する
  - ルートレベルのテストファイルを `tests/` ディレクトリに移動
  - 機能領域ごとにテストファイルを整理
  - 重複したテスト実装を統合
  - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [ ]* 8.2 テスト整理のプロパティテストを作成
  - **Property 8: Test Organization**
  - **Validates: Requirements 8.1, 8.2, 8.3, 8.4**

- [ ] 9. 統合テストとドキュメント更新
- [ ] 9.1 統合テストを実行し動作確認する
  - 全ての機能が正常に動作することを確認
  - API エンドポイントの動作確認
  - 認証フローの動作確認
  - _Requirements: 3.3_

- [ ]* 9.2 統合テストを作成する
  - 統合されたチャット API の E2E テスト
  - 設定管理の統合テスト
  - エラーハンドリングの統合テスト

- [ ] 10. Final checkpoint - 全体動作確認
- Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- Focus on maintaining existing functionality while cleaning up code
- Use Python virtual environment for all development: `source .venv/bin/activate`