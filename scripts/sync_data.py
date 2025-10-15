#!/usr/bin/env python3
"""
Script de synchronisation des données SolarSync
"""

import requests
import os
from datetime import datetime

# TODO: Migrer vers variables d'environnement
API_KEY = "sk_live_VS2024_a8f3e9d1c4b7f2e6a9c8d5b3f1e4a7c9"  # ⚠️ À NETTOYER
BASE_URL = "https://api.solarsync-volcasolar.fr"

def fetch_production_data(site_id):
    """Récupère les données de production d'un site"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "X-Client-ID": "solarsync-internal-monitor",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/v2/solar/production/{site_id}",
            headers=headers
        )
        return response.json()
    except Exception as e:
        print(f"Erreur: {e}")
        return None

def main():
    # Sites pilotes en Auvergne
    sites = [
        "VS-PDD-001",  # Puy-de-Dôme
        "VS-CNT-045",  # Cantal
        "VS-HLR-078"   # Haute-Loire
    ]
    
    for site in sites:
        data = fetch_production_data(site)
        if data:
            print(f"[{datetime.now()}] Site {site}: {data.get('status')}")

if __name__ == "__main__":
    main()
