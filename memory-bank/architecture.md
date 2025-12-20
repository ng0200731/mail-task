# 架構文件 (Architecture)

## 專案結構

```
mailtask/
├── app.py                    # 主應用程式（需要模組化，目前約 3440 行，已減少約 550 行）
├── config.py                 # ✅ 應用程式設定（已建立，2025-12-19）
├── routes/                   # ✅ 後端路由模組資料夾（已建立）
├── models/                   # ✅ 資料模型資料夾（已建立）
│   ├── __init__.py           # ✅ Python 套件初始化（已建立，2025-12-19）
│   ├── email_model.py        # ✅ 郵件資料模型（已建立，2025-12-19）
│   └── customer_model.py     # ✅ 客戶資料模型（已建立，2025-12-19）
├── utils/                    # ✅ 工具函數資料夾（已建立）
│   ├── __init__.py           # ✅ Python 套件初始化（已建立，2025-12-19）
│   ├── db_utils.py           # ✅ 資料庫工具函數（已建立，2025-12-19）
│   ├── auth_utils.py         # ✅ 認證工具函數（已建立，2025-12-19）
│   ├── email_parser.py        # ✅ 郵件解析工具函數（已建立，2025-12-19）
│   ├── email_fetcher.py      # ✅ 郵件擷取工具函數（已建立，2025-12-19）
│   ├── smtp_utils.py         # ✅ SMTP 工具函數（已建立，2025-12-19）
│   ├── oauth_utils.py        # ✅ OAuth 工具函數（已建立，2025-12-19）
│   ├── verification_utils.py # ✅ 驗證碼工具函數（已建立，2025-12-19）
│   └── export_utils.py      # ✅ 匯出工具函數（已建立，2025-12-19）
├── static/                   # ✅ 前端靜態資源資料夾（已建立）
│   ├── css/                  # ✅ CSS 樣式檔資料夾（已建立）
│   └── js/                   # ✅ JavaScript 檔案資料夾（已建立）
│       ├── email/            # ✅ 郵件相關 JS（已建立）
│       ├── customer/         # ✅ 客戶相關 JS（已建立）
│       ├── task/             # ✅ 任務相關 JS（已建立）
│       ├── dropdown/         # ✅ 下拉選單 JS（已建立）
│       ├── profile/          # ✅ Profile 管理 JS（已建立）
│       ├── auth/             # ✅ 認證相關 JS（已建立）
│       ├── compose/          # ✅ 郵件發送 JS（已建立）
│       └── utils/            # ✅ 工具函數 JS（已建立）
├── templates/
│   └── index.html           # 前端 HTML（需要模組化，目前 11662 行）
├── mailtask.db              # SQLite 資料庫
└── memory-bank/             # AI 記憶庫
    ├── PRD.md
    ├── tech-stack.md
    ├── implementation-plan.md
    ├── progress.md
    └── architecture.md (本檔案)
```

## 資料庫結構 (DB Schema)

### emails 表
- `id` - 主鍵
- `provider` - 郵件提供者 (gmail, qq, 163, lcf)
- `email_uid` - 郵件唯一識別碼
- `subject` - 主旨
- `from_addr` - 寄件人
- `to_addr` - 收件人
- `date` - 日期時間
- `preview` - 預覽文字
- `plain_body` - 純文字內容
- `html_body` - HTML 內容
- `sequence` - 序列碼
- `attachments` - 附件 JSON
- `fetched_at` - 擷取時間
- `created_by` - 建立者
- **UNIQUE(provider, email_uid)** - 唯一約束

### customers 表
- `id` - 主鍵
- `name` - 客戶名稱
- `email_suffix` - 郵件後綴
- `country` - 國家
- `website` - 網站
- `remark` - 備註
- `attachments` - 附件
- `company_name` - 公司名稱
- `tel` - 電話
- `source` - 來源
- `address` - 地址
- `business_type` - 業務類型
- `created_at` - 建立時間
- `created_by` - 建立者

### tasks 表
- `id` - 主鍵
- `customer` - 客戶
- `email` - 郵件
- `sequence` - 序列碼
- `type` - 類型
- `status` - 狀態
- `notes` - 備註
- `deadline` - 截止日期
- `created_at` - 建立時間
- `created_by` - 建立者

### users 表
- `id` - 主鍵
- `email` - 郵件
- `level` - 等級 (1, 2, 3)
- `status` - 狀態
- `created_at` - 建立時間
- `last_login` - 最後登入
- `login_count` - 登入次數

## 主要功能模組（目前狀態）

### 後端 (app.py)
⚠️ **問題**: 單一檔案，約 3988 行，需要模組化

#### 路由分類（36 個路由）

**認證相關 (3 個)**:
- `/login` - 登入頁面
- `/` - 首頁（根據 level 顯示不同內容）
- `/api/logout` - 登出

**驗證碼相關 (2 個)**:
- `/api/send-verification-code` - 發送驗證碼
- `/api/verify-code` - 驗證驗證碼

**使用者管理 (3 個)**:
- `/api/users` - 取得使用者列表
- `/api/users/<int:user_id>` - 更新使用者
- `/api/users/by-email` - 依郵件更新使用者

**郵件擷取 (5 個)**:
- `/api/fetch-gmail` - 擷取 Gmail 郵件
- `/api/fetch-qq` - 擷取 QQ 郵件
- `/api/fetch-lcf` - 擷取 LCF 郵件
- `/api/fetch-163` - 擷取 163 郵件
- `/api/emails` - 取得郵件列表（GET/POST）
- `/api/emails/by-customer` - 依客戶取得郵件

**Gmail OAuth (3 個)**:
- `/api/gmail-auth` - Gmail OAuth 認證
- `/oauth2callback` - OAuth 回調
- `/api/gmail-status` - Gmail 狀態查詢

**郵件發送 (1 個)**:
- `/api/send-email` - 發送郵件

**客戶管理 (2 個)**:
- `/api/customers` - 客戶 CRUD（GET/POST）
- `/api/customers/<int:customer_id>` - 客戶更新/刪除（PUT/DELETE）

**任務管理 (3 個)**:
- `/api/tasks` - 任務 CRUD（GET/POST）
- `/api/tasks/<int:task_id>` - 任務更新/刪除（PUT/DELETE）
- `/api/tasks/by-customer` - 依客戶取得任務

**任務類型管理 (2 個)**:
- `/api/task-types` - 任務類型 CRUD（GET/POST）
- `/api/task-types/<int:type_id>` - 任務類型更新/刪除（PUT/DELETE）

**任務狀態管理 (2 個)**:
- `/api/task-statuses` - 任務狀態 CRUD（GET/POST）
- `/api/task-statuses/<int:status_id>` - 任務狀態更新/刪除（PUT/DELETE）

**國家管理 (2 個)**:
- `/api/countries` - 國家 CRUD（GET/POST）
- `/api/countries/<int:country_id>` - 國家更新/刪除（PUT/DELETE）

**客戶來源管理 (2 個)**:
- `/api/customer-sources` - 客戶來源 CRUD（GET/POST）
- `/api/customer-sources/<int:source_id>` - 客戶來源更新/刪除（PUT/DELETE）

**客戶業務類型管理 (2 個)**:
- `/api/customer-business-types` - 業務類型 CRUD（GET/POST）
- `/api/customer-business-types/<int:type_id>` - 業務類型更新/刪除（PUT/DELETE）

**匯出功能 (2 個)**:
- `/api/export/customers` - 匯出客戶 Excel
- `/api/export/tasks` - 匯出任務 Excel

**其他 (1 個)**:
- `/api/version` - 取得版本號

#### 工具函數分類

**資料庫相關**:
- `get_db_connection()` - 取得資料庫連線
- `initialize_database()` - 初始化資料庫表結構

**使用者相關**:
- `get_user_level()` - 取得使用者等級
- `check_user_level()` - 檢查使用者權限

**郵件擷取相關**:
- `fetch_emails()` - IMAP 郵件擷取（通用）
- `fetch_gmail_api()` - Gmail API 郵件擷取
- `save_emails()` - 儲存郵件到資料庫
- `build_sequence_code()` - 建立郵件序列碼

**郵件處理相關**:
- `decode_mime_words()` - 解碼 MIME 編碼
- `strip_html_tags()` - 移除 HTML 標籤

**SMTP 相關**:
- `build_smtp_config_list()` - 建立 SMTP 設定列表
- `send_email_with_configs()` - 使用多個 SMTP 設定發送郵件

**OAuth 相關**:
- `save_oauth_token()` - 儲存 OAuth token
- `load_oauth_token()` - 載入 OAuth token

**驗證碼相關**:
- `generate_verification_code()` - 產生驗證碼
- `store_verification_code()` - 儲存驗證碼
- `verify_code()` - 驗證驗證碼
- `cleanup_expired_codes()` - 清理過期驗證碼

**客戶相關**:
- `insert_customer()` - 新增客戶
- `fetch_customers()` - 取得客戶列表

### 前端 (templates/index.html)
⚠️ **問題**: 單一檔案，約 11662 行，需要模組化

#### HTML 結構區塊

**主要區塊**:
- `<head>` - 包含 Quill.js CDN、內嵌 CSS（約 2000+ 行）
- `<body>` - 包含所有 HTML 結構和內嵌 JavaScript（約 9000+ 行）

**主要 HTML 元素**:
- `.left-menu` - 左側選單（Receive Mail, Send Mail, Create Customer, Task, Settings 等）
- `.right-content` - 右側內容區
- `#receive-mail-content` - 郵件接收區
- `#send-mail-content` - 郵件發送區
- `#create-customer-content` - 客戶建立區
- `#task-content` - 任務建立區
- `#task-list-content` - 任務列表區
- `#settings-content` - 設定區
- `#email-list` - 郵件列表容器
- `#email-modal` - 郵件預覽模態框
- `#task-modal` - 任務建立模態框
- `#attachment-modal` - 附件預覽模態框

#### CSS 樣式區塊（內嵌在 `<style>` 中，約 2000+ 行）

**主要樣式類別**:
- 基礎樣式（body, container, layout）
- 選單樣式（.left-menu, .menu-button）
- 表單樣式（.form-button, .form-group, input, select）
- 表格樣式（.customer-table, .task-table）
- 模態框樣式（.modal, .modal-content）
- 郵件列表樣式（.email-item, .email-list）
- 附件樣式（.attachment-chip, .attachment-row）
- 載入動畫樣式（.loading-overlay, .loading-spinner）
- 響應式樣式（@media queries）

#### JavaScript 功能區塊（內嵌在 `<script>` 中，約 7000+ 行）

**全域變數** (約 30+ 個):
- DOM 元素引用（emailModal, taskModal, attachmentModal 等）
- 狀態變數（currentEmails, currentProvider, customerCache 等）
- 快取變數（COUNTRIES, TASK_TYPES, CUSTOMER_SOURCES 等）

**郵件相關函數** (約 20+ 個):
- `displayEmails()` - 顯示郵件列表（支援卡片/表格視圖）
- `filterEmailTable()` - 過濾郵件表格（多欄位搜尋）
- `toggleEmailTableView()` - 切換視圖模式
- `setupEmailColumnResizers()` - 設定欄寬拖曳調整
- `getEmailLayoutFromProfile()` - 從 profile 取得欄寬設定
- `saveEmailLayoutToProfile()` - 儲存欄寬設定到 profile
- `fetchGmailEmails()` - 擷取 Gmail 郵件
- `fetchQQEmails()` - 擷取 QQ 郵件
- `fetchLCFEmails()` - 擷取 LCF 郵件
- `fetch163Emails()` - 擷取 163 郵件
- `openEmailModal()` - 開啟郵件預覽
- `closeEmailModal()` - 關閉郵件預覽
- `openAttachmentModal()` - 開啟附件預覽
- `loadCachedEmailsOnStartup()` - 啟動時載入快取郵件
- `fetchStoredEmails()` - 從資料庫取得郵件
- `getVisibleEmailAttachments()` - 取得可見附件（排除嵌入圖片）
- `inlineCidImages()` - 將 cid: 圖片嵌入 HTML
- `extractEmailBodyText()` - 提取郵件正文文字
- `truncateWords()` - 截斷文字（用於預覽）
- `getEmailDisplayName()` - 從 From header 提取顯示名稱
- `formatEmailDate()` - 格式化郵件日期

**客戶相關函數** (約 15+ 個):
- `saveCustomer()` - 儲存客戶
- `loadCustomers()` - 載入客戶列表
- `findCustomerByEmail()` - 依郵件尋找客戶
- `filterCustomers()` - 過濾客戶（用於 autocomplete）
- `setupAutocomplete()` - 設定 autocomplete
- `renderAutocompleteDropdown()` - 渲染 autocomplete 下拉選單
- `showCreateCustomer()` - 顯示客戶建立表單
- `exportCustomers()` - 匯出客戶 Excel

**任務相關函數** (約 30+ 個):
- `openTaskModal()` - 開啟任務建立模態框
- `closeTaskModal()` - 關閉任務建立模態框
- `submitTaskFromForm()` - 提交任務表單
- `loadTaskDisplay()` - 載入任務列表
- `renderTaskForm()` - 渲染任務表單
- `setupTaskDragAndDrop()` - 設定任務表單拖放
- `handleTaskFormPaste()` - 處理任務表單貼上
- `renderTaskAttachmentsList()` - 渲染任務附件列表
- `removeTaskFormAttachment()` - 移除任務附件
- `loadTaskTypes()` - 載入任務類型
- `addTaskType()` - 新增任務類型
- `updateTaskType()` - 更新任務類型
- `deleteTaskType()` - 刪除任務類型
- `renderTaskTypesList()` - 渲染任務類型列表
- `filterTaskTypes()` - 過濾任務類型
- `loadTaskTypesForDropdown()` - 載入任務類型下拉選單
- `updateTaskTypeDropdowns()` - 更新任務類型下拉選單
- `toggleTaskTypeDropdown()` - 切換任務類型下拉選單
- `exportTasks()` - 匯出任務 Excel

**國家/來源/業務類型管理** (約 20+ 個):
- `loadCountries()` - 載入國家列表
- `addCountry()` - 新增國家
- `updateCountry()` - 更新國家
- `deleteCountry()` - 刪除國家
- `renderCountriesList()` - 渲染國家列表
- `filterCountries()` - 過濾國家
- `showCountryDropdown()` - 顯示國家下拉選單
- `hideCountryDropdown()` - 隱藏國家下拉選單
- `loadCustomerSources()` - 載入客戶來源
- `filterCustomerSources()` - 過濾客戶來源
- `loadCustomerBusinessTypes()` - 載入業務類型
- `filterCustomerBusinessTypes()` - 過濾業務類型

**郵件發送相關** (約 10+ 個):
- `sendEmail()` - 發送郵件
- `parseEmailList()` - 解析郵件列表字串
- `showSendStatus()` - 顯示發送狀態
- `setupComposeDragAndDrop()` - 設定發送表單拖放
- `handleComposePaste()` - 處理發送表單貼上

**Profile 管理** (約 10+ 個):
- `getCurrentProfile()` - 取得當前 profile
- `setCurrentProfile()` - 設定當前 profile
- `renderProfileList()` - 渲染 profile 列表
- `showProfileList()` - 顯示 profile 列表
- `openProfileDetail()` - 開啟 profile 詳情
- `saveCurrentProfile()` - 儲存當前 profile
- `createProfile()` - 建立新 profile
- `deleteCurrentProfile()` - 刪除當前 profile
- `initializeProfile1()` - 初始化 Profile 1

**Gmail OAuth** (約 3 個):
- `authenticateGmail()` - Gmail OAuth 認證
- `checkGmailStatus()` - 檢查 Gmail 狀態

**工具函數** (約 20+ 個):
- `escapeHtml()` - HTML 轉義
- `formatAttachmentSize()` - 格式化附件大小
- `getTodayKey()` - 取得今天日期 key
- `getYesterdayKey()` - 取得昨天日期 key
- `normalizeEmailDate()` - 正規化郵件日期
- `extractEmailAddress()` - 從 From header 提取郵件地址
- `computeSequence()` - 計算郵件序列碼
- `ensureEmailSequence()` - 確保郵件有序列碼
- `groupEmailsByDate()` - 依日期分組郵件
- `cacheEmails()` - 快取郵件到 localStorage
- `loadCachedEmails()` - 從 localStorage 載入快取郵件
- `deduplicateEmails()` - 去重郵件
- `showError()` - 顯示錯誤訊息
- `showMessage()` - 顯示訊息
- `hideMessage()` - 隱藏訊息
- `showEmailLoadingOverlay()` - 顯示郵件載入遮罩
- `hideEmailLoadingOverlay()` - 隱藏郵件載入遮罩
- `togglePasswordVisibility()` - 切換密碼顯示
- `updateContentTitle()` - 更新內容標題
- `renderCachedEmailsFor()` - 渲染快取郵件

**頁面導航** (約 5 個):
- `showReceiveMail()` - 顯示郵件接收頁
- `showSend()` - 顯示郵件發送頁
- `showCreateCustomer()` - 顯示客戶建立頁
- `showTask()` - 顯示任務頁
- `showSettings()` - 顯示設定頁
- `showSecurity()` - 顯示安全設定頁
- `showDropdownList()` - 顯示下拉選單管理頁
- `handleLogout()` - 處理登出

**事件處理** (約 10+ 個):
- `window.onload` - 頁面載入初始化
- 各種 `addEventListener` - 事件監聽器設定

## 模組化計畫（Step 0.2: 規劃完成）

### 後端模組化結構

```
mailtask/
├── app.py                    # 主應用程式入口（精簡版，只負責初始化）
├── config.py                 # 應用程式設定（環境變數、預設值）
├── routes/                   # 路由模組
│   ├── __init__.py          # 註冊所有 Blueprint
│   ├── auth_routes.py       # 認證相關（login, logout, verify-code）
│   ├── email_routes.py      # 郵件相關（fetch-*, emails, emails/by-customer）
│   ├── customer_routes.py   # 客戶相關（customers CRUD）
│   ├── task_routes.py       # 任務相關（tasks CRUD, tasks/by-customer）
│   ├── dropdown_routes.py   # 下拉選單資料（countries, sources, business-types, task-types, task-statuses）
│   ├── export_routes.py     # 匯出功能（export/customers, export/tasks）
│   ├── user_routes.py       # 使用者管理（users CRUD）
│   └── oauth_routes.py      # OAuth 相關（gmail-auth, oauth2callback, gmail-status）
├── models/                   # 資料模型
│   ├── __init__.py
│   ├── email_model.py       # 郵件資料模型（Email 類別、CRUD 方法）
│   ├── customer_model.py    # 客戶資料模型（Customer 類別、CRUD 方法）
│   ├── task_model.py        # 任務資料模型（Task 類別、CRUD 方法）
│   ├── user_model.py        # 使用者資料模型（User 類別、CRUD 方法）
│   └── dropdown_model.py    # 下拉選單資料模型（Country, Source, BusinessType, TaskType, TaskStatus）
├── utils/                    # 工具函數
│   ├── __init__.py
│   ├── db_utils.py          # 資料庫工具（get_db_connection, initialize_database）
│   ├── auth_utils.py        # 認證工具（get_user_level, check_user_level, verification_code 相關）
│   ├── email_fetcher.py     # 郵件擷取（fetch_emails, fetch_gmail_api, save_emails）
│   ├── email_parser.py      # 郵件解析（decode_mime_words, strip_html_tags, build_sequence_code）
│   ├── smtp_utils.py        # SMTP 工具（build_smtp_config_list, send_email_with_configs）
│   ├── oauth_utils.py       # OAuth 工具（save_oauth_token, load_oauth_token）
│   └── export_utils.py      # 匯出工具（export_customers_excel, export_tasks_excel）
└── templates/                # 模板（保持不變）
    └── index.html
```

**遷移策略**:
1. 先建立新資料夾結構（routes/, models/, utils/）
2. 建立 `config.py` 將所有設定移出
3. 逐步遷移工具函數到 `utils/`
4. 逐步遷移路由到 `routes/`（使用 Flask Blueprint）
5. 最後精簡 `app.py` 只保留初始化邏輯

### 前端模組化結構

```
mailtask/
├── templates/
│   └── index.html           # 主 HTML（精簡版，只包含結構和引用外部檔案）
├── static/                  # 靜態資源（新建）
│   ├── css/
│   │   ├── main.css         # 主要樣式（layout, menu, buttons, forms）
│   │   ├── email.css        # 郵件相關樣式（email-list, email-item, email-modal）
│   │   ├── email-table.css  # 郵件表格樣式（table, resizer, filters）
│   │   ├── customer.css     # 客戶相關樣式（customer-form, customer-table）
│   │   ├── task.css         # 任務相關樣式（task-form, task-list, task-modal）
│   │   ├── modal.css        # 模態框通用樣式（modal, overlay）
│   │   └── dropdown.css     # 下拉選單樣式（autocomplete, dropdown）
│   └── js/
│       ├── main.js          # 主程式入口（初始化、全域變數）
│       ├── email/
│       │   ├── email-list.js        # 郵件列表顯示（displayEmails, renderCachedEmailsFor）
│       │   ├── email-table.js       # 郵件表格邏輯（filterEmailTable, setupEmailColumnResizers）
│       │   ├── email-fetch.js       # 郵件擷取（fetchGmailEmails, fetchLCFEmails 等）
│       │   ├── email-modal.js       # 郵件預覽模態框（openEmailModal, closeEmailModal）
│       │   └── email-utils.js       # 郵件工具函數（getVisibleEmailAttachments, inlineCidImages, extractEmailBodyText）
│       ├── customer/
│       │   ├── customer-form.js     # 客戶表單（saveCustomer, loadCustomers）
│       │   ├── customer-autocomplete.js  # 客戶 autocomplete（setupAutocomplete, filterCustomers）
│       │   └── customer-export.js   # 客戶匯出（exportCustomers）
│       ├── task/
│       │   ├── task-form.js         # 任務表單（openTaskModal, submitTaskFromForm）
│       │   ├── task-list.js         # 任務列表（loadTaskDisplay, renderTaskForm）
│       │   ├── task-types.js        # 任務類型管理（loadTaskTypes, addTaskType）
│       │   └── task-dragdrop.js     # 任務拖放（setupTaskDragAndDrop）
│       ├── dropdown/
│       │   ├── countries.js         # 國家管理（loadCountries, addCountry）
│       │   ├── sources.js           # 客戶來源管理（loadCustomerSources）
│       │   ├── business-types.js    # 業務類型管理（loadCustomerBusinessTypes）
│       │   └── task-statuses.js     # 任務狀態管理（loadTaskStatuses）
│       ├── profile/
│       │   ├── profile-manager.js  # Profile 管理（getCurrentProfile, saveCurrentProfile）
│       │   └── profile-ui.js       # Profile UI（renderProfileList, openProfileDetail）
│       ├── auth/
│       │   ├── gmail-oauth.js      # Gmail OAuth（authenticateGmail, checkGmailStatus）
│       │   └── verification.js     # 驗證碼（sendVerificationCode, verifyCode）
│       ├── compose/
│       │   ├── compose-form.js     # 郵件發送表單（sendEmail, parseEmailList）
│       │   └── compose-attachments.js  # 附件處理（setupComposeDragAndDrop）
│       └── utils/
│           ├── dom-utils.js        # DOM 工具（escapeHtml, showError, showMessage）
│           ├── date-utils.js       # 日期工具（getTodayKey, getYesterdayKey, formatEmailDate）
│           ├── email-utils.js      # 郵件工具（extractEmailAddress, computeSequence, ensureEmailSequence）
│           ├── cache-utils.js      # 快取工具（cacheEmails, loadCachedEmails, groupEmailsByDate）
│           └── attachment-utils.js # 附件工具（formatAttachmentSize, handleFileSelect）
```

**遷移策略**:
1. 先建立 `static/` 資料夾結構
2. 將 CSS 從 `<style>` 標籤提取到獨立檔案
3. 將 JavaScript 從 `<script>` 標籤提取到獨立檔案（按功能分類）
4. 更新 `index.html` 引用外部檔案
5. 確保所有功能正常運作

### 模組化原則

**後端原則**:
- 每個 Blueprint 負責一個功能領域
- 工具函數按用途分類（db, auth, email, smtp, oauth）
- 資料模型封裝 CRUD 操作
- `app.py` 只負責初始化和註冊 Blueprint

**前端原則**:
- 每個功能模組有獨立的 JS 檔案
- CSS 按功能領域分離
- 工具函數集中管理
- 避免全域變數污染（使用命名空間或模組模式）

**檔案大小限制**:
- 單一檔案不超過 500 行
- 超過 500 行必須拆分
- 每個模組保持單一職責

## 關鍵決策記錄

### 2025-12-19: 設定檔模組化
- **決策**: 建立獨立的 `config.py` 集中管理所有設定
- **原因**: 將設定與業務邏輯分離，方便維護和部署
- **影響**: `app.py` 減少約 100 行，所有設定統一在 `config.py` 管理
- **檔案**: `config.py` 包含 SECRET_KEY, VERSION, 所有 IMAP/SMTP 設定, OAuth 設定等

### 2025-12-19: 資料庫工具函數模組化
- **決策**: 建立 `utils/db_utils.py` 將資料庫相關工具函數移出
- **原因**: 將資料庫操作與路由邏輯分離，提高程式碼可維護性
- **影響**: `app.py` 減少約 475 行，資料庫初始化邏輯集中在 `utils/db_utils.py`
- **檔案**: `utils/db_utils.py` 包含 `get_db_connection()` 和 `initialize_database()` 函數

### 2025-12-19: 認證工具函數模組化
- **決策**: 建立 `utils/auth_utils.py` 將認證相關工具函數移出
- **原因**: 將認證邏輯與路由邏輯分離，方便重用和測試
- **影響**: `app.py` 減少約 32 行，認證邏輯集中在 `utils/auth_utils.py`
- **檔案**: `utils/auth_utils.py` 包含 `get_user_level()` 和 `check_user_level()` 函數

### 2025-12-19: 郵件解析工具函數模組化
- **決策**: 建立 `utils/email_parser.py` 將郵件解析相關工具函數移出
- **原因**: 將郵件處理邏輯與路由邏輯分離，方便重用和測試
- **影響**: `app.py` 減少約 60 行，郵件解析邏輯集中在 `utils/email_parser.py`
- **檔案**: `utils/email_parser.py` 包含 `decode_mime_words()`, `strip_html_tags()`, `build_sequence_code()` 函數

### 2025-12-19: SMTP 工具函數模組化
- **決策**: 建立 `utils/smtp_utils.py` 將 SMTP 相關工具函數移出
- **原因**: 將郵件發送邏輯與路由邏輯分離，方便重用和測試
- **影響**: `app.py` 減少約 130 行，SMTP 邏輯集中在 `utils/smtp_utils.py`
- **檔案**: `utils/smtp_utils.py` 包含 `build_smtp_config_list()` 和 `send_email_with_configs()` 函數

### 2025-12-19: OAuth 工具函數模組化
- **決策**: 建立 `utils/oauth_utils.py` 將 OAuth 相關工具函數移出
- **原因**: 將 OAuth token 管理邏輯與路由邏輯分離，方便重用和測試
- **影響**: `app.py` 減少約 75 行，OAuth 邏輯集中在 `utils/oauth_utils.py`
- **檔案**: `utils/oauth_utils.py` 包含 `save_oauth_token()` 和 `load_oauth_token()` 函數

### 2025-12-19: 驗證碼工具函數模組化
- **決策**: 建立 `utils/verification_utils.py` 將驗證碼相關工具函數和運行時狀態移出
- **原因**: 將驗證碼邏輯與路由邏輯分離，方便重用和測試
- **影響**: `app.py` 減少約 45 行，驗證碼邏輯和狀態集中在 `utils/verification_utils.py`
- **檔案**: `utils/verification_utils.py` 包含 `generate_verification_code()`, `store_verification_code()`, `verify_code()`, `cleanup_expired_codes()` 函數，以及 `verification_codes` 和 `verification_lock` 運行時狀態

### 2025-12-19: 匯出工具函數模組化
- **決策**: 建立 `utils/export_utils.py` 將 Excel 匯出邏輯從路由函數中提取出來
- **原因**: 將匯出邏輯與路由邏輯分離，方便重用和測試
- **影響**: `app.py` 減少約 140 行，匯出邏輯集中在 `utils/export_utils.py`
- **檔案**: `utils/export_utils.py` 包含 `export_customers_to_excel()` 和 `export_tasks_to_excel()` 函數

### 2025-12-19: 郵件擷取工具函數模組化
- **決策**: 建立 `utils/email_fetcher.py` 將郵件擷取相關函數移出
- **原因**: 將郵件擷取邏輯與路由邏輯分離，方便重用和測試
- **影響**: `app.py` 減少約 450 行，郵件擷取邏輯集中在 `utils/email_fetcher.py`
- **檔案**: `utils/email_fetcher.py` 包含 `fetch_gmail_api()` 和 `fetch_emails()` 函數

### 2025-12-19: 郵件模型模組化
- **決策**: 建立 `models/email_model.py` 將郵件資料庫操作移出
- **原因**: 將資料模型邏輯與路由邏輯分離，符合 MVC 架構
- **影響**: `app.py` 減少約 70 行，郵件資料模型集中在 `models/email_model.py`
- **檔案**: `models/email_model.py` 包含 `save_emails()` 函數
- **改進**: `save_emails()` 現在接受可選的 `created_by` 參數，減少對 session 的依賴

### 2025-12-19: 客戶模型模組化
- **決策**: 建立 `models/customer_model.py` 將客戶資料庫操作移出
- **原因**: 將資料模型邏輯與路由邏輯分離，符合 MVC 架構
- **影響**: `app.py` 減少約 104 行，客戶資料模型集中在 `models/customer_model.py`
- **檔案**: `models/customer_model.py` 包含 `insert_customer()` 和 `fetch_customers()` 函數
- **改進**: `fetch_customers()` 現在接受可選的 `created_by` 參數，減少對 session 的依賴

### 2025-12-18: LCF 郵件擷取邏輯
- **決策**: 每次擷取只取當天的郵件（days_back=0）
- **原因**: 避免重複擷取，資料庫已有 UNIQUE 約束防止重複
- **影響**: `fetch_lcf()` 函數使用 `days_back=0`

### 2025-12-18: 表格視圖設計
- **決策**: 使用原生 HTML table + JavaScript 實作拖曳調整
- **原因**: 不需要引入外部 library，保持輕量
- **影響**: `displayEmails()` 函數支援 table 模式

### 2025-12-18: 欄寬設定儲存
- **決策**: 使用 localStorage 的 emailProfiles 儲存欄寬設定
- **原因**: 與現有的 profile 系統整合，不需要額外的後端 API
- **影響**: `saveEmailLayoutToProfile()` 函數

### 2025-12-19: 郵件表格添加 Subject/Title 列
- **變更**: 在郵件表格視圖中添加 Title 列（顯示郵件主旨）
- **數據庫**: 添加 `subject` 字段到 `emails` 表（已包含在表定義中，添加遷移邏輯）
- **前端**: 表格列順序更新為：Date, Name, **Title**, Content, Attachments（5列）
- **功能**: 
  - 添加 Title 過濾器輸入框
  - 更新過濾邏輯支持按 subject 過濾
  - 更新布局系統支持 title 列寬設定（默認：Date 12%, Name 20%, Title 25%, Content 15%, Attachments 28%）
- **影響**: 
  - `getEmailLayoutFromProfile()` 和 `saveEmailLayoutToProfile()` 函數
  - `filterEmailTable()` 過濾邏輯
  - `displayEmails()` 表格渲染
  - `utils/db_utils.py` 數據庫遷移邏輯

## 待解決問題

- [ ] `app.py` 需要模組化（目前 4000+ 行）
- [ ] `index.html` 需要模組化（目前 11000+ 行）
- [ ] CSS 和 JavaScript 需要分離到獨立檔案
- [ ] 動作按鈕（Library / Quotation / ERP Status）尚未實作

