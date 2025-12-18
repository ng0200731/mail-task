# Product Requirements Document (PRD)

## 問題定義 (Problem Statement)

需要建立一個郵件管理系統的前端介面，整合多個內部功能模組：
- 圖片庫 (Image Library)
- 報價單 (Quotation)
- 跟進 (Follow Up)
- ERP 系統連結 (Link to ERP)

## 使用者 (Users)

- **主要使用者**: Level 2+ 使用者（主管層級）
- **權限**: Level 2 以上才能使用 Receive Mail 功能

## 核心功能需求

### 1. LCF 郵件擷取與顯示
- 每日自動擷取 LCF 郵件（只擷取當天的郵件）
- 表格視圖顯示郵件列表
- 支援搜尋功能（每個欄位獨立搜尋）
- 欄寬可拖曳調整，設定會記住（存在 profile）

### 2. 動作按鈕
每個郵件需要以下動作按鈕：
- **Library** - 連結到圖片庫功能
- **Quotation** - 連結到報價單功能
- **ERP Status** - 連結到 ERP 狀態查詢

### 3. 其他內部功能整合
- 圖片庫模組
- 報價單模組
- 跟進模組
- ERP 連結模組

## 成功標準 (Success Criteria)

✅ LCF 郵件可以正常擷取並顯示在表格中  
✅ 表格支援多欄位搜尋  
✅ 欄寬可以拖曳調整，設定會自動保存到 profile  
✅ 每個郵件都有 Library / Quotation / ERP Status 按鈕  
✅ 所有功能模組化，沒有單一巨型檔案  

## 這次「不做」什麼 (Out of Scope)

❌ 不改動其他 provider（Gmail/QQ/163）的現有邏輯  
❌ 不建立新的後端 API（除非必要）  
❌ 不改變現有的資料庫結構（除非必要）  

## 技術約束 (Technical Constraints)

⚠️ **嚴格要求**：
- 模組化、多檔案
- 禁止單一巨型檔案
- 一步一驗收
- 不准自己擴大 scope
- 完成功能後必須更新文件




