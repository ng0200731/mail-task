# Front-End Breakage Post-mortem – 4 Jan 2026

## What Happened
1. **Merge-conflict markers left in `templates/index.html`**  
   * During a rebase/merge we resolved most conflicts, but one block was committed with
   remaining `<<<<<<<`, `=======`, `>>>>>>>` markers and duplicate code.
   * The browser parsed these characters inside the `<script>` block, producing
   `Uncaught SyntaxError: Unexpected token '<<'`.

2. **Duplicate / half-deleted code block**  
   * The same merge introduced two overlapping versions of the e-mail-row click-handler.
   * Extra opening parentheses/braces were removed later, but in the meantime the file
   reached production with a `missing ) after argument list` error around line ≈ 7780.

3. **Global functions not exposed**  
   * After refactoring, `showCreateCustomer`, `showReceiveMail`, and
     `showTaskList` were defined inside the script but never attached to
     `window.*`.
   * The HTML still used inline `onclick="showCreateCustomer(event)"`, causing
     `ReferenceError: showCreateCustomer is not defined`.

## Root Causes
| Category | Details |
|----------|---------|
| Process  | Merge conflicts resolved hastily; lack of final conflict-marker scan. |
| Testing  | No automated lint/CI step to block committing HTML with conflict markers or JS syntax errors. |
| Design   | Reliance on inline `onclick="…"` attributes that require the function to be in global scope. |

## Fix Applied
* Removed all conflict markers and duplicate code blocks.
* Ensured only **one** well-formed click-handler block remains.
* Exposed the menu functions:  
  `window.showCreateCustomer = showCreateCustomer;` (etc.).
* Pushed clean code in commits `46ad704`, `01524be`.

## How To Prevent This Next Time
1. **Always complete the 3-step conflict checklist**
   ```bash
   rg "^<<<<<<<|^=======|^>>>>>>>" -n  # verify *zero* hits before commit
   npm run lint                         # or equivalent linter
   npm run test / manual browser smoke  # open the page once
   ```
2. **Enable a pre-commit hook** (e.g. Husky) that rejects commits containing
   conflict markers or JS syntax errors.
3. **Prefer `addEventListener` over inline `onclick`** so functions don’t have to
   live in global scope. If inline handlers are unavoidable, **always** attach
   them explicitly to `window.*` in the same commit.
4. **Run the app locally after merge/rebase**—open DevTools console and look for
   red errors before pushing.

---
*Document generated automatically after production issue on 4 Jan 2026.*
