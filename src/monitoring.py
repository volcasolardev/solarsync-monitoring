#!/usr/bin/env python3
"""
SolarSync Monitoring System
Module de surveillance temps réel de la production solaire

Auteur: Équipe DevOps VolcaSolar
Contact: devops@volcasolar.fr
Version: 2.3.1
Dernière MAJ: 2024-11-18
"""

import requests
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sqlite3
import os

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/monitoring.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('SolarSync-Monitor')


class SolarSyncMonitor:
    """
    Classe principale de monitoring de la plateforme SolarSync
    """
    
    def __init__(self, api_key: str = None, base_url: str = None):
        """
        Initialisation du moniteur
        
        Args:
            api_key: Clé API SolarSync (doit être fournie via env)
            base_url: URL de base de l'API
        """
        # Chargement configuration depuis variables d'environnement
        self.api_key = api_key or os.getenv('SOLARSYNC_API_KEY')
        
        if not self.api_key:
            logger.error("ERREUR: Clé API non fournie. Définir SOLARSYNC_API_KEY")
            raise ValueError("API Key manquante")
        
        self.base_url = base_url or os.getenv('SOLARSYNC_BASE_URL',
            'https://api.solarsync-volcasolar.fr')
        
        self.webhook_secret = os.getenv('SOLARSYNC_WEBHOOK_SECRET', '')
        
        # Headers par défaut
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'X-Client-ID': 'solarsync-internal-monitor',
            'X-Client-Version': '2.3.1',
            'Content-Type': 'application/json',
            'User-Agent': 'VolcaSolar-Monitor/2.3.1'
        }
        
        # Base de données locale pour cache
        self.db_path = 'monitoring.db'
        self._init_database()
        
        logger.info("SolarSync Monitor initialisé")
        logger.debug(f"API Base URL: {self.base_url}")
    
    def _init_database(self):
        """Initialise la base de données SQLite locale"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS production_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                power_output REAL,
                efficiency REAL,
                status TEXT,
                temperature REAL,
                irradiance REAL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                resolved BOOLEAN DEFAULT 0
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.debug("Base de données locale initialisée")
    
    def get_site_production(self, site_id: str) -> Optional[Dict]:
        """
        Récupère les données de production d'un site
        
        Args:
            site_id: Identifiant du site (ex: VS-PDD-001)
            
        Returns:
            Dict avec les données de production ou None si erreur
        """
        endpoint = f"/api/v2/solar/production/{site_id}"
        
        try:
            response = requests.get(
                f"{self.base_url}{endpoint}",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Données récupérées pour {site_id}")
                
                # Sauvegarde en cache local
                self._save_production_data(site_id, data)
                
                return data
            
            elif response.status_code == 401:
                logger.error("Authentification échouée - Vérifier API key")
                return None
            
            elif response.status_code == 403:
                logger.error(f"Accès refusé au site {site_id}")
                return None
            
            elif response.status_code == 404:
                logger.warning(f"Site {site_id} non trouvé")
                return None
            
            else:
                logger.error(f"Erreur API: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"Timeout lors de la requête pour {site_id}")
            return None
        
        except requests.exceptions.ConnectionError:
            logger.error(f"Erreur de connexion à l'API SolarSync")
            return None
        
        except Exception as e:
            logger.error(f"Erreur inattendue: {str(e)}")
            return None
    
    def _save_production_data(self, site_id: str, data: Dict):
        """Sauvegarde les données de production en local"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO production_data 
                (site_id, power_output, efficiency, status, temperature, irradiance)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                site_id,
                data.get('power_output_kw', 0),
                data.get('efficiency_percent', 0),
                data.get('status', 'unknown'),
                data.get('panel_temperature_c', 0),
                data.get('irradiance_w_m2', 0)
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde DB: {str(e)}")
    
    def get_all_sites(self) -> List[Dict]:
        """
        Récupère la liste de tous les sites supervisés
        
        Returns:
            Liste des sites avec leurs informations
        """
        endpoint = "/api/v2/sites"
        
        try:
            response = requests.get(
                f"{self.base_url}{endpoint}",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                sites = response.json().get('sites', [])
                logger.info(f"{len(sites)} sites récupérés")
                return sites
            else:
                logger.error(f"Erreur récupération sites: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Erreur get_all_sites: {str(e)}")
            return []
    
    def get_alerts(self, site_id: str = None, severity: str = None) -> List[Dict]:
        """
        Récupère les alertes de sécurité/maintenance
        
        Args:
            site_id: Filtrer par site (optionnel)
            severity: Filtrer par sévérité (low/medium/high/critical)
            
        Returns:
            Liste des alertes
        """
        endpoint = "/api/v2/alerts"
        params = {}
        
        if site_id:
            params['site_id'] = site_id
        if severity:
            params['severity'] = severity
        
        try:
            response = requests.get(
                f"{self.base_url}{endpoint}",
                headers=self.headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                alerts = response.json().get('alerts', [])
                logger.info(f"{len(alerts)} alertes récupérées")
                
                # Sauvegarde des alertes critiques
                for alert in alerts:
                    if alert.get('severity') in ['high', 'critical']:
                        self._save_alert(alert)
                
                return alerts
            else:
                logger.error(f"Erreur récupération alertes: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Erreur get_alerts: {str(e)}")
            return []
    
    def _save_alert(self, alert: Dict):
        """Sauvegarde une alerte en base locale"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO alerts 
                (site_id, alert_type, severity, message)
                VALUES (?, ?, ?, ?)
            ''', (
                alert.get('site_id'),
                alert.get('type'),
                alert.get('severity'),
                alert.get('message')
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde alerte: {str(e)}")
    
    def schedule_maintenance(self, site_id: str, date: str, maintenance_type: str) -> bool:
        """
        Programme une maintenance sur un site
        
        Args:
            site_id: ID du site
            date: Date de maintenance (format ISO: YYYY-MM-DD)
            maintenance_type: Type (cleaning/inspection/repair/upgrade)
            
        Returns:
            True si succès, False sinon
        """
        endpoint = "/api/v2/maintenance/schedule"
        
        payload = {
            'site_id': site_id,
            'scheduled_date': date,
            'type': maintenance_type,
            'requested_by': 'monitoring_system',
            'priority': 'medium'
        }
        
        try:
            response = requests.post(
                f"{self.base_url}{endpoint}",
                headers=self.headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 201:
                logger.info(f"Maintenance programmée pour {site_id} le {date}")
                return True
            else:
                logger.error(f"Erreur programmation maintenance: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Erreur schedule_maintenance: {str(e)}")
            return False
    
    def get_production_stats(self, site_id: str, days: int = 7) -> Dict:
        """
        Récupère les statistiques de production sur une période
        
        Args:
            site_id: ID du site
            days: Nombre de jours à analyser
            
        Returns:
            Dict avec statistiques agrégées
        """
        endpoint = f"/api/v2/solar/stats/{site_id}"
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        params = {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'granularity': 'hourly'
        }
        
        try:
            response = requests.get(
                f"{self.base_url}{endpoint}",
                headers=self.headers,
                params=params,
                timeout=15
            )
            
            if response.status_code == 200:
                stats = response.json()
                logger.info(f"Stats récupérées pour {site_id} ({days} jours)")
                return stats
            else:
                logger.error(f"Erreur récupération stats: {response.status_code}")
                return {}
                
        except Exception as e:
            logger.error(f"Erreur get_production_stats: {str(e)}")
            return {}
    
    def check_anomalies(self, site_id: str) -> List[Dict]:
        """
        Détecte les anomalies de production via l'IA
        
        Args:
            site_id: ID du site à analyser
            
        Returns:
            Liste des anomalies détectées
        """
        endpoint = f"/api/v2/ai/anomaly-detection"
        
        payload = {
            'site_id': site_id,
            'analysis_window': '24h',
            'sensitivity': 'medium'
        }
        
        try:
            response = requests.post(
                f"{self.base_url}{endpoint}",
                headers=self.headers,
                json=payload,
                timeout=20
            )
            
            if response.status_code == 200:
                anomalies = response.json().get('anomalies', [])
                
                if anomalies:
                    logger.warning(f"⚠️ {len(anomalies)} anomalie(s) détectée(s) sur {site_id}")
                    for anomaly in anomalies:
                        logger.warning(f"  - {anomaly.get('type')}: {anomaly.get('description')}")
                else:
                    logger.info(f"✓ Aucune anomalie détectée sur {site_id}")
                
                return anomalies
            else:
                logger.error(f"Erreur analyse anomalies: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Erreur check_anomalies: {str(e)}")
            return []
    
    def monitor_all_sites(self, interval: int = 300):
        """
        Boucle de monitoring continue de tous les sites
        
        Args:
            interval: Intervalle entre chaque cycle (secondes)
        """
        logger.info(f"🚀 Démarrage monitoring continu (intervalle: {interval}s)")
        
        while True:
            try:
                sites = self.get_all_sites()
                
                for site in sites:
                    site_id = site.get('id')
                    logger.info(f"📊 Monitoring site: {site_id} - {site.get('name')}")
                    
                    # Production
                    production = self.get_site_production(site_id)
                    if production:
                        status = production.get('status')
                        power = production.get('power_output_kw', 0)
                        logger.info(f"  ⚡ Statut: {status} | Production: {power} kW")
                    
                    # Alertes
                    alerts = self.get_alerts(site_id=site_id, severity='high')
                    if alerts:
                        logger.warning(f"  ⚠️ {len(alerts)} alerte(s) haute priorité")
                    
                    # Anomalies (toutes les heures seulement)
                    if datetime.now().minute < 5:
                        self.check_anomalies(site_id)
                    
                    time.sleep(2)
                
                logger.info(f"✓ Cycle terminé. Pause de {interval}s...")
                time.sleep(interval)
                
            except KeyboardInterrupt:
                logger.info("🛑 Arrêt du monitoring (Ctrl+C)")
                break
            
            except Exception as e:
                logger.error(f"❌ Erreur dans la boucle de monitoring: {str(e)}")
                logger.info(f"Nouvelle tentative dans {interval}s...")
                time.sleep(interval)


def main():
    """Point d'entrée principal"""
    
    print("=" * 60)
    print("SolarSync Monitoring System v2.3.1")
    print("VolcaSolar - Plateforme de supervision")
    print("=" * 60)
    print()
    
    # Vérification des variables d'environnement
    if not os.getenv('SOLARSYNC_API_KEY'):
        print("❌ ERREUR: Variable d'environnement SOLARSYNC_API_KEY non définie")
        print()
        print("Configuration requise:")
        print("  export SOLARSYNC_API_KEY='votre_clé_api'")
        print("  export SOLARSYNC_BASE_URL='https://api.solarsync-volcasolar.fr'")
        print()
        return
    
    try:
        # Initialisation
        monitor = SolarSyncMonitor()
        
        # Test de connexion
        logger.info("Test de connexion à l'API SolarSync...")
        sites = monitor.get_all_sites()
        
        if sites:
            logger.info(f"✓ Connexion réussie - {len(sites)} site(s) trouvé(s)")
            
            # Affichage des sites
            print("\nSites supervisés:")
            for site in sites:
                print(f"  • {site.get('id')} - {site.get('name')} ({site.get('location')})")
            
            # Exemple: monitoring d'un site spécifique
            if sites:
                test_site = sites[0].get('id')
                logger.info(f"\n--- Test monitoring site {test_site} ---")
                
                production = monitor.get_site_production(test_site)
                if production:
                    print(json.dumps(production, indent=2))
                
                alerts = monitor.get_alerts(site_id=test_site)
                print(f"\nAlertes actives: {len(alerts)}")
            
            # Démarrer monitoring continu (décommenter si besoin)
            # monitor.monitor_all_sites(interval=300)
            
        else:
            logger.error("❌ Impossible de se connecter à l'API")
            logger.error("Vérifier:")
            logger.error("  1. La clé API")
            logger.error("  2. La connectivité réseau")
            logger.error("  3. L'URL de base de l'API")
    
    except ValueError as e:
        logger.error(str(e))
    except Exception as e:
        logger.error(f"Erreur d'initialisation: {str(e)}")


if __name__ == "__main__":
    main()
