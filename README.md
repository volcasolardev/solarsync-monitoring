# SolarSync Monitoring Tools

Suite d'outils internes développés par l'équipe DevOps de VolcaSolar pour le monitoring temps réel de nos installations photovoltaïques connectées à la plateforme SolarSync.

Fonctionnalités principales :

    Collecte automatisée des données de production
    Alertes en temps réel sur anomalies de performance
    Synchronisation avec les bases de données internes
    Génération de rapports de maintenance
    Dashboard de supervision centralisé

<img src="https://img.shields.io/badge/python-3.9%2B-blue.svg" alt="Python Version" />
<img src="https://img.shields.io/badge/license-Proprietary-red.svg" alt="License" />
<img src="https://img.shields.io/badge/status-Production-green.svg" alt="Status" />

## Installation

Prérequis

    Python 3.9 ou supérieur
    Accès VPN VolcaSolar (pour API interne)
    Credentials SolarSync valides

Configuration

```git clone https://github.com/volcasolar/solarsync-monitoring.git
cd solarsync-monitoring

# Installer les dépendances
pip install -r requirements.txt```

## Utilisation

```python scripts/sync_data.py```
