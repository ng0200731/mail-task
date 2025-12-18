# 🔒 Always 生效的規則 (Always Rules)

這些規則在**每次**寫 code 前都必須遵守，無論什麼情況都不能違反。

## 核心規則

### ① 寫任何 code 前必須做的事
- ✅ 先讀 `memory-bank/PRD.md` 了解需求
- ✅ 先讀 `memory-bank/architecture.md` 了解現有結構（含 DB schema）
- ✅ 先讀 `memory-bank/progress.md` 了解做到哪裡了
- ✅ 先讀 `memory-bank/implementation-plan.md` 了解下一步要做什麼

### ② 檔案結構規則
- ✅ **永遠保持模組化，禁止單一巨型檔案**
- ✅ 每個功能模組應該有獨立的檔案
- ✅ CSS 樣式應該分離到獨立檔案或區塊
- ✅ JavaScript 邏輯應該分離到獨立函數或模組
- ✅ 如果一個檔案超過 500 行，必須拆分成多個檔案

### ③ 開發流程規則
- ✅ **一步一驗收**：每次只做一個小步驟，完成後驗收，通過才能繼續
- ✅ **不准自己擴大 scope**：只做 PRD 和 implementation-plan 裡寫的，不要自己加功能
- ✅ **我沒說 OK 不准進下一步**：完成一步後等確認，不要自動繼續

### ④ 文件更新規則
- ✅ 完成大功能／里程碑後**必須**更新 `architecture.md`
- ✅ 完成每個步驟後**必須**更新 `progress.md`
- ✅ 如果改了資料庫結構，**必須**更新 `architecture.md` 的 DB schema 部分
- ✅ 如果新增了檔案，**必須**在 `architecture.md` 記錄用途

### ⑤ 程式碼品質規則
- ✅ 記住所有 CSS 樣式的位置和用途
- ✅ 記住所有 JavaScript 邏輯的位置和用途
- ✅ 不要重複寫已經存在的功能
- ✅ 修改現有功能前，先找到對應的檔案和函數

## 違反規則的後果

如果違反以上任何規則：
- 🚨 立即停止
- 🚨 回報違反了哪條規則
- 🚨 等待指示後再繼續

## 檢查清單 (每次寫 code 前)

在開始寫任何 code 之前，確認：

- [ ] 我已經讀完 `memory-bank/PRD.md`
- [ ] 我已經讀完 `memory-bank/architecture.md`
- [ ] 我已經讀完 `memory-bank/progress.md`
- [ ] 我已經讀完 `memory-bank/implementation-plan.md`
- [ ] 我知道這次只做哪一步（不會擴大 scope）
- [ ] 我知道要修改/新增哪些檔案（不會產生巨型檔案）
- [ ] 我知道完成後要更新哪些文件




