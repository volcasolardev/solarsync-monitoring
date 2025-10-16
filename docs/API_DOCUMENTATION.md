# SolarSync API Documentation

**Base URL:** `https://api.solarsync-volcasolar.fr`  
**Version:** 2.3.1

---

## Authentification

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     https://api.solarsync-volcasolar.fr/v2/sites
```

Type de clés :

* sk_live_ - production (lecture/écriture)
* sk_test_ - staying (limité)
* sk_read_ - lecture seule

-----------------------------------------

## Endpoints principaux

GET /v2/sites

Liste tous les sites de production.

Paramètres:

* status - Filtrer par statut (online, offline, maintenance)
* region - Code région (PDD, CDF...)
* page - Pagination (défaut: 1)
* limit - Résultats/page (max: 200)

Réponse :

```
{
  "data": [
    {
      "site_id": "VS-PDD-001",
      "name": "Centrale Clermont-Ferrand Nord",
      "status": "online",
      "capacity_kwp": 250.5,
      "last_update": "2024-11-18T14:32:45Z"
    }
  ],
  "pagination": { "total": 127, "page": 1, "pages": 3 }
}
```

-----------------------------------------------

## GET /v2/sites/{site_id}

Détail d'un site spécifique

Réponse :

```
{
  "site_id": "VS-PDD-001",
  "name": "Centrale Clermont-Ferrand Nord",
  "status": "online",
  "current_metrics": {
    "power_output_kw": 187.3,
    "efficiency_percent": 18.7
  }
}
```

-------------------------------------------------

## GET /v2/sites/{site_id}/metrics

Métriques de production temps réel.

Paramètres :

* from - Date début (ISO 8601)
* to - Date fin
* interval - 5min, 15min, 1h, 1d

Réponse :

```
{
  "site_id": "VS-PDD-001",
  "data": [
    {
      "timestamp": "2024-11-18T14:00:00Z",
      "power_output_kw": 189.2,
      "energy_kwh": 47.3,
      "efficiency_percent": 18.9
    }
  ]
}
```

-----------------------------------------

## GET /v2/alerts

Alertes actives.

Paramètres :

* site_id - Filtrer par site
* severity - low, medium, high, critical
* status - active, acknowledged, resolved

Réponse:

```
[
  {
    "alert_id": "ALT-2024-11-18-001",
    "site_id": "VS-PDD-001",
    "severity": "high",
    "status": "active",
    "message": "Baisse de production détectée (-25%)",
    "created_at": "2024-11-18T13:45:22Z"
  }
]
```


