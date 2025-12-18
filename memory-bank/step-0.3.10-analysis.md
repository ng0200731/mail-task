# Step 0.3.10: 剩餘工具函數分析報告

## 日期：2025-12-19

## 已完成模組化

### Utils 模組（已完成）
- ✅ `utils/db_utils.py` - 資料庫工具
- ✅ `utils/auth_utils.py` - 認證工具
- ✅ `utils/email_parser.py` - 郵件解析工具
- ✅ `utils/smtp_utils.py` - SMTP 工具
- ✅ `utils/oauth_utils.py` - OAuth 工具
- ✅ `utils/verification_utils.py` - 驗證碼工具
- ✅ `utils/export_utils.py` - 匯出工具

### Config 模組（已完成）
- ✅ `config.py` - 應用程式設定

## 剩餘需要模組化的函數

### 1. 資料模型相關函數（應移到 `models/`）

#### `models/customer_model.py`
- `insert_customer()` - 新增客戶（約 14 行）
- `fetch_customers()` - 取得客戶列表（約 90 行）
  - 包含資料轉換邏輯（處理舊資料庫欄位）

#### `models/email_model.py`
- `save_emails()` - 儲存郵件到資料庫（約 70 行）
  - 處理批量插入/更新
  - 使用 `ON CONFLICT` 處理重複郵件

### 2. 郵件擷取相關函數（應移到 `utils/email_fetcher.py`）

#### `utils/email_fetcher.py`
- `fetch_gmail_api()` - Gmail API 郵件擷取（約 200 行）
  - 使用 Gmail API
  - 處理附件、日期解析
  - 依賴 `load_oauth_token()`
  
- `fetch_emails()` - IMAP 郵件擷取（約 250 行）
  - 通用 IMAP 擷取函數
  - 處理多種郵件格式
  - 處理附件和內嵌圖片
  - 包含內部輔助函數 `_imap_date()` 和 `_clean_content_id()`

## 統計

### 當前狀態
- `app.py` 行數：約 2976 行
- 已減少：約 936 行（約 24%）
- 剩餘工具函數：約 624 行可提取

### 預期完成後
- `app.py` 預期行數：約 2352 行（主要是路由函數）
- 總減少：約 1560 行（約 40%）

## 下一步建議

### 優先順序 1：郵件擷取函數（`utils/email_fetcher.py`）
**理由**：
- 這些函數較大（約 450 行）
- 邏輯獨立，容易提取
- 不依賴 session（除了 `save_emails` 中的 `created_by`）

**步驟**：
1. 建立 `utils/email_fetcher.py`
2. 將 `fetch_gmail_api()` 和 `fetch_emails()` 移過去
3. 處理依賴關係（`load_oauth_token`, `save_emails`, `decode_mime_words`, `build_sequence_code`）
4. 更新 `app.py` 中的路由函數

### 優先順序 2：資料模型函數（`models/`）
**理由**：
- 這些函數較小但數量多
- 需要處理 session 依賴（`created_by`）
- 可以逐步遷移

**步驟**：
1. 建立 `models/__init__.py`
2. 建立 `models/customer_model.py`，移入 `insert_customer()` 和 `fetch_customers()`
3. 建立 `models/email_model.py`，移入 `save_emails()`
4. 處理 session 依賴（可能需要將 `created_by` 作為參數傳入）
5. 更新 `app.py` 中的路由函數

## 注意事項

1. **Session 依賴**：
   - `insert_customer()` 和 `save_emails()` 使用 `session.get('user_email')`
   - 建議改為將 `created_by` 作為參數傳入，而不是在模型層訪問 session

2. **函數依賴**：
   - `fetch_gmail_api()` 和 `fetch_emails()` 都調用 `save_emails()`
   - `save_emails()` 需要先移到 `models/email_model.py`
   - 或者先移到 `utils/email_fetcher.py`，之後再重構

3. **內部函數**：
   - `fetch_emails()` 包含內部輔助函數 `_imap_date()` 和 `_clean_content_id()`
   - 這些應該保留在 `fetch_emails()` 內部，或提取為模組級輔助函數

## 建議執行順序

1. **Step 0.3.11**: 建立 `utils/email_fetcher.py`（郵件擷取函數）
2. **Step 0.3.12**: 建立 `models/email_model.py`（郵件模型）
3. **Step 0.3.13**: 建立 `models/customer_model.py`（客戶模型）

這樣可以確保依賴關係正確，避免循環引用問題。

