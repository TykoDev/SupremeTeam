# Azure Deployment Attack Surface Analysis

## Network Attack Surface

### App Service

- Public `*.azurewebsites.net` hostnames are internet-reachable by default
- Kudu / SCM endpoints expose administrative surfaces if not locked down
- App Service access restrictions can drift from intended allowlists
- Health endpoints may leak operational detail if left unauthenticated

### PostgreSQL Flexible Server

- Public network access exposes the server to internet-originated connection attempts
- Broad firewall rules create unnecessary reachability
- `AllowAzureServices` is wider than many teams assume
- TLS and auth mode must align with the application's real connection path

### Storage Account

- Blob containers may be accidentally public
- Shared Access Signatures can outlive their intended purpose
- CORS misconfiguration may expose data to unexpected origins
- Account keys are high-blast-radius secrets if widely distributed

### Container Registry

- Admin user enablement creates long-lived shared credentials
- Broad pull rights increase lateral movement potential
- Image provenance and tag discipline affect rollback and trust

### Key Vault

- Public network exposure and broad RBAC expand the secret access surface
- Soft-delete and purge-protection gaps increase destructive-risk exposure

## Identity Attack Surface

### Managed Identities

- RBAC overreach is a common privilege-escalation path
- Scope mistakes at the resource-group level create wider access than intended
- Identity references can drift between architecture, config, and runtime

### Service Principals

- Client secrets create rotation and leakage risk
- App registrations may retain stale permissions over time

## Secret Attack Surface

### Key Vault Secrets

- Secret naming mismatches break runtime resolution silently
- Missing references or stale versions cause confusing startup failures
- Secret sprawl makes auditing harder and increases blast radius

### App Settings

- Sensitive values may leak into plaintext app settings
- Deployment-only variables can remain in production runtime configuration by mistake

### Database Credentials

- Password-based auth paths expand the credential surface
- Shared or over-privileged DB identities worsen compromise impact

## Container Attack Surface

### Image Supply Chain

- Unpinned base images increase update unpredictability
- Secrets passed as build args may leak into image history
- Large build context can unintentionally ship sensitive files

### Container Runtime

- Wrong port or health-check config can masquerade as app failure
- Runtime settings may not match the image that was actually deployed

## Data Attack Surface

### PostgreSQL Data

- Over-privileged roles can expose schema mutation or data exfiltration paths
- Missing extensions or schema drift can break security assumptions

### Blob Storage Data

- Public access, weak SAS practices, or broad role grants can expose data
- Lifecycle and soft-delete settings affect recoverability after mistakes

## Deployment Process Attack Surface

### State File

- Concurrent writes or bad save semantics can corrupt deployment state
- Missing validation turns state drift into cascading deployment failures

### Deploy Scripts

- Redaction gaps can leak secrets into logs
- Non-idempotent steps create fragile reruns and unsafe recovery behavior
