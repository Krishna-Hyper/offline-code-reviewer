---
name: code-review
description: |
  Reviews code submitted by the user and returns structured, concise feedback
  in a fixed markdown format covering Summary, Bugs, Improvements, Security,
  and Complexity.

  Use this skill when:
    1. The user pastes code or a git diff and asks for a review.
    2. The user requests feedback on bugs, security, performance, or general
       code quality.
    3. The review focus is one of: general, bugs, security, or performance.

  Do NOT use this skill for:
    - Generating new code from scratch.
    - Refactoring or rewriting entire files.
    - Tasks unrelated to evaluating existing code.
license: Apache-2.0
metadata:
  version: v1
  publisher: Krishna-Hyper
---

# Code Review

Structured, concise code review following a fixed output format. Never rewrite
the whole file; focus on actionable, line-referenced feedback.

## Output Format

Always respond in exactly this markdown structure. Every section is mandatory.

```
## Summary
One or two sentences describing what the code does.

## Bugs
- Real bugs or crashes, with line references. Write "None found" if clean.

## Improvements
- Readability, naming, structure, performance suggestions.

## Security
- Injection risks, unsafe input handling, secrets in code. Write "None found" if clean.

## Complexity
Time and space complexity if the code is algorithmic; otherwise omit or write "N/A".
```

## Review Modes

The review focus is set by the caller. Adjust emphasis accordingly:

| Focus       | Emphasis                                              |
|-------------|-------------------------------------------------------|
| `general`   | Balanced review across all sections.                  |
| `bugs`      | Prioritise Bugs section; surface edge cases and crashes. |
| `security`  | Prioritise Security section; look for injection, auth flaws, exposed secrets. |
| `performance` | Prioritise Complexity section; evaluate time/space, hot paths, unnecessary allocations. |

All four sections must still appear regardless of focus mode.

## Constraints

- **Be concise.** Do not rewrite the whole file.
- **Reference lines.** When citing a bug or issue, include the line number or
  range (e.g. `line 14`, `lines 22-31`).
- **No think tokens.** Prepend system messages with `/no_think` to suppress
  chain-of-thought output when the underlying model supports it.
- **Temperature.** Use `temperature: 0.2` to keep reviews deterministic and
  factual.
- **Context window.** Truncate input code to 6 000 characters to stay within
  the model's context budget.

## Language Handling

- Accept any programming language or a raw `git diff`.
- If language is `auto-detect`, infer it from syntax and file structure.
- Apply language-specific idioms when suggesting improvements (e.g. Pythonic
  style, Go error handling conventions, Rust ownership patterns).

## Example Interaction

**User input**
```python
DB_PASSWORD = "supersecret123"

def get_user(username):
    query = f"SELECT * FROM users WHERE name = '{username}'"
    cursor.execute(query)
```

**Expected output**
```
## Summary
A SQLite helper that fetches a user by name and stores a hardcoded DB password.

## Bugs
- Line 5: `cursor.execute` is called without a connection being opened in this
  function; will raise `NameError` if `cursor` is not in scope.

## Improvements
- Use parameterised queries instead of f-strings for all SQL calls.
- Move DB connection setup into a context manager or dependency-inject `cursor`.

## Security
- Line 1: `DB_PASSWORD` is hardcoded in source; use an environment variable or
  a secrets manager.
- Line 4: SQL injection -- `username` is interpolated directly into the query
  string. Use `cursor.execute("... WHERE name = ?", (username,))` instead.

## Complexity
N/A -- no algorithmic logic present.
```
