# Notes de déploiement SolarSync

## Historique

### 2024-11-15 - Migration API v2.3
- Nouvelle authentification Bearer
- Rotation des clés API
- ⚠️ Anciennes clés valides jusqu'au 2024-12-31 pour transition

### 2024-10-03 - Incident sécurité
- Détection accès non autorisé sur endpoint /api/admin
- Logs disponibles sur Splunk
- Actions: rotation partielle des secrets

## Accès

- **Production**: https://api.solarsync-volcasolar.fr
- **Staging**: https://staging-api.solarsync-volcasolar.fr
- **Doc API**: https://docs.solarsync-volcasolar.fr

## Credentials Manager

Les credentials sont stockés sur:
- AWS Secrets Manager (production)
- 1Password (équipe DevOps)
- ⚠️ Backup chiffré sur S3: s3://volcasolar-secrets-backup/

## Contact urgence

- DevOps: +33 6 12 34 56 78
- RSSI: security@volcasolar.fr
