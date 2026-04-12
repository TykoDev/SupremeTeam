# Common Azure Deployment Mistakes

## Configuration Mistakes

### 1. Secret in Plain Text App Setting

Sensitive values such as API keys, connection strings, or signing secrets are
written directly into app settings instead of referenced from Key Vault.

### 2. Deployment-Only Variable in App Settings

Temporary deployment variables remain in production runtime configuration and
confuse operators or leak implementation detail.

### 3. Wrong Key Vault Reference URI

The app setting points to a secret name or vault URI that does not exist or does
not match the intended environment.

### 4. Missing RBAC Role Assignment

The managed identity exists but lacks the precise role needed for ACR, Key
Vault, Storage, or database access.

## Database Mistakes

### 5. Migration Applied Out of Order

Migrations run in the wrong sequence, producing schema drift or failed startup.

### 6. Checksum Mismatch

The migration tool or deployment process cannot prove that the applied schema
matches the expected migration history.

### 7. Application User Over-Privileged

The runtime DB principal gets admin-like grants when a narrower role would work.

### 8. Extension Not Enabled

The application depends on a PostgreSQL extension that was never provisioned or
verified.

## Security Mistakes

### 9. ACR Admin User Enabled

Shared registry credentials remain enabled even though managed identity or RBAC
pull should be used.

### 10. Key Vault Using Access Policies Instead of RBAC

Access policies are used without a strong reason, creating harder-to-audit auth
behavior than RBAC.

### 11. PostgreSQL Public Network Without Firewall Discipline

Public access is enabled with overly broad or stale firewall rules.

### 12. Deploy Runner IP Firewall Rule Left Behind

Temporary deployment access remains after the deployment window closes.

## Deployment Process Mistakes

### 13. State File Committed to Git

Deployment state or secret-bearing temp files are accidentally checked into the
repository.

### 14. Temporary Settings File Not Cleaned Up

Generated configuration files remain on disk after deployment and may contain
sensitive data.

### 15. `latest` Tag Used in Production

Mutable image tags make rollback and traceability unreliable.

### 16. Docker Build Context Too Large

Missing or weak `.dockerignore` causes secrets, VCS data, or unnecessary files
to be sent to the Docker daemon.
