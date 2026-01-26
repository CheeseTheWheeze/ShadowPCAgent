# Safety and approvals

## Sensitive change taxonomy

Changes are **sensitive** if they modify:

- Authentication/authorization logic
- Secrets, tokens, or environment credentials
- CI/CD pipelines or deployment infrastructure
- Production configuration or data migrations
- Access control policies or permissions
- Security libraries or cryptographic settings

## Draft/diff workflow

1. Detect sensitive files or operations.
2. Generate a draft patch/diff.
3. Provide a concise summary and explicit approval request.
4. Apply changes only after approval.

## Command safety

- Allowlist standard tooling (formatters, tests, builds).
- Require explicit approval for destructive operations.
- Log every command and its output.

## Recovery strategy

- Keep a backup of files before edits.
- Support clean revert to last known good state.
- Provide clear rollback instructions in outputs.
