# 技術棧 (Tech Stack)

## 後端
- **框架**: Flask (Python)
- **資料庫**: SQLite (`mailtask.db`)
- **認證**: Session-based (Flask sessions)
- **檔案結構**: 
  - `app.py` - 主應用程式（目前約 4000 行，**需要模組化**）

## 前端
- **框架**: 原生 JavaScript (無框架)
- **模板引擎**: Jinja2 (Flask templates)
- **主要檔案**: 
  - `templates/index.html` - 單一 HTML 檔案（目前約 11000+ 行，**需要模組化**）
- **樣式**: 內嵌 CSS（**需要分離**）

## 資料儲存
- **設定檔**: localStorage (emailProfiles, 使用者偏好)
- **資料庫表**:
  - `emails` - 郵件資料
  - `customers` - 客戶資料
  - `tasks` - 任務資料
  - `users` - 使用者資料
  - `oauth_tokens` - OAuth token

## 現有問題
⚠️ **技術債**：
- `app.py` 是單一巨型檔案（需要拆分成 routes/, models/, utils/ 等）
- `templates/index.html` 是單一巨型檔案（需要拆分成多個組件或模組）
- CSS 和 JavaScript 都內嵌在 HTML 中（需要分離）

## 建議的模組化方向
- 後端：拆分成 `routes/`, `models/`, `utils/`, `config.py`
- 前端：拆分成多個 `.js` 檔案和 `.css` 檔案
- 或者：使用 Flask Blueprints 組織路由




