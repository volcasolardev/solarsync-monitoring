#!/usr/bin/env python3
"""
Utilitaires pour SolarSync Monitoring
Fonctions helper pour le traitement et la validation des données

Auteur: Équipe DevOps VolcaSolar
Contact: devops@volcasolar.fr
Version: 2.3.1
Dernière MAJ: 2024-11-18
"""

import hashlib
import hmac
import json
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
import logging

logger = logging.getLogger('SolarSync-Utils')


def verify_webhook_signature(payload: str, signature: str, secret: str) -> bool:
    """
    Vérifie la signature HMAC d'un webhook SolarSync
    
    Args:
        payload: Corps de la requête (string)
        signature: Signature reçue dans le header X-SolarSync-Signature
        secret: Secret partagé webhook
        
    Returns:
        True si signature valide, False sinon
        
    Example:
        >>> payload = '{"event": "alert", "site_id": "VS-PDD-001"}'
        >>> signature = "sha256=abc123..."
        >>> verify_webhook_signature(payload, signature, "mon_secret")
        True
    """
    if not secret:
        logger.warning("Secret webhook non configuré")
        return False
    
    try:
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Extraction du hash si format "sha256=..."
        if signature.startswith('sha256='):
            signature = signature[7:]
        
        return hmac.compare_digest(signature, expected_signature)
    
    except Exception as e:
        logger.error(f"Erreur vérification signature webhook: {str(e)}")
        return False


def format_site_id(raw_id: str) -> str:
    """
    Formate un ID de site au format standard VolcaSolar
    
    Format standard: VS-[REGION]-[NUM]
    Ex: pdd001 -> VS-PDD-001
        lyontest -> VS-LYO-001
        VS-PDD-001 -> VS-PDD-001 (inchangé)
    
    Args:
        raw_id: ID brut à formater
        
    Returns:
        ID formaté au standard VolcaSolar
    """
    if not raw_id:
        return ""
    
    raw_id = raw_id.strip()
    
    # Déjà au bon format
    if re.match(r'^VS-[A-Z]{3}-\d{3}$', raw_id):
        return raw_id
    
    # Format: pdd001, cdf042, etc.
    match = re.match(r'^([a-zA-Z]{3})(\d+)$', raw_id)
    if match:
        region = match.group(1).upper()
        number = match.group(2).zfill(3)
        return f"VS-{region}-{number}"
    
    # Format: pdd-001, cdf-42
    match = re.match(r'^([a-zA-Z]{3})-(\d+)$', raw_id)
    if match:
        region = match.group(1).upper()
        number = match.group(2).zfill(3)
        return f"VS-{region}-{number}"
    
    # Impossible à formater
    logger.warning(f"Format d'ID de site non reconnu: {raw_id}")
    return raw_id.upper()


def calculate_efficiency(
    power_output: float, 
    irradiance: float, 
    panel_area: float = 1.6,
    panel_count: int = 1
) -> float:
    """
    Calcule l'efficacité d'un système solaire
    
    Formule: Efficacité (%) = (Puissance sortie / Puissance théorique max) × 100
    
    Args:
        power_output: Puissance réelle en kW
        irradiance: Irradiance solaire en W/m²
        panel_area: Surface d'un panneau en m² (défaut: 1.6 m²)
        panel_count: Nombre de panneaux (défaut: 1)
        
    Returns:
        Efficacité en pourcentage (0-100)
        
    Example:
        >>> calculate_efficiency(power_output=3.2, irradiance=800, panel_count=20)
        12.5
    """
    if irradiance <= 0:
        return 0.0
    
    if power_output < 0:
        logger.warning(f"Puissance négative détectée: {power_output} kW")
        return 0.0
    
    # Puissance théorique maximale
    total_area = panel_area * panel_count
    max_power_w = irradiance * total_area  # en Watts
    max_power_kw = max_power_w / 1000  # en kW
    
    if max_power_kw == 0:
        return 0.0
    
    efficiency = (power_output / max_power_kw) * 100
    
    # Limitation réaliste (jamais > 25% pour photovoltaïque standard)
    if efficiency > 25.0:
        logger.warning(f"Efficacité anormalement élevée: {efficiency:.2f}%")
    
    return round(efficiency, 2)


def validate_site_data(data: Dict) -> Tuple[bool, List[str]]:
    """
    Valide la structure et les valeurs des données d'un site
    
    Args:
        data: Dictionnaire contenant les données du site
        
    Returns:
        Tuple (is_valid, errors_list)
        
    Example:
        >>> data = {"site_id": "VS-PDD-001", "power_output_kw": 45.2}
        >>> is_valid, errors = validate_site_data(data)
        >>> print(is_valid)
        True
    """
    errors = []
    
    # Champs obligatoires
    required_fields = ['site_id', 'power_output_kw', 'status']
    for field in required_fields:
        if field not in data:
            errors.append(f"Champ obligatoire manquant: {field}")
    
    # Validation du site_id
    if 'site_id' in data:
        site_id = data['site_id']
        if not re.match(r'^VS-[A-Z]{3}-\d{3}$', site_id):
            errors.append(f"Format site_id invalide: {site_id}")
    
    # Validation power_output
    if 'power_output_kw' in data:
        power = data['power_output_kw']
        if not isinstance(power, (int, float)):
            errors.append(f"power_output_kw doit être numérique: {power}")
        elif power < 0:
            errors.append(f"power_output_kw ne peut pas être négatif: {power}")
        elif power > 10000:  # Limite réaliste
            errors.append(f"power_output_kw anormalement élevé: {power} kW")
    
    # Validation status
    if 'status' in data:
        valid_statuses = ['online', 'offline', 'maintenance', 'warning', 'error']
        if data['status'] not in valid_statuses:
            errors.append(f"Status invalide: {data['status']}")
    
    # Validation température si présente
    if 'panel_temperature_c' in data:
        temp = data['panel_temperature_c']
        if not isinstance(temp, (int, float)):
            errors.append(f"panel_temperature_c doit être numérique: {temp}")
        elif temp < -40 or temp > 90:
            errors.append(f"Température hors limites réalistes: {temp}°C")
    
    # Validation irradiance si présente
    if 'irradiance_w_m2' in data:
        irr = data['irradiance_w_m2']
        if not isinstance(irr, (int, float)):
            errors.append(f"irradiance_w_m2 doit être numérique: {irr}")
        elif irr < 0 or irr > 1400:
            errors.append(f"Irradiance hors limites réalistes: {irr} W/m²")
    
    is_valid = len(errors) == 0
    return is_valid, errors


def parse_timestamp(timestamp_str: str) -> Optional[datetime]:
    """
    Parse un timestamp au format ISO 8601
    
    Args:
        timestamp_str: String représentant un timestamp
        
    Returns:
        Objet datetime ou None si parsing échoue
        
    Example:
        >>> parse_timestamp("2024-11-18T14:30:00Z")
        datetime.datetime(2024, 11, 18, 14, 30, tzinfo=timezone.utc)
    """
    if not timestamp_str:
        return None
    
    # Formats supportés
    formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z"
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(timestamp_str, fmt)
            # Ajout timezone UTC si absent
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    
    logger.warning(f"Impossible de parser le timestamp: {timestamp_str}")
    return None


def calculate_performance_ratio(
    actual_production: float,
    theoretical_production: float
) -> float:
    """
    Calcule le ratio de performance (PR) d'une installation
    
    Le PR indique la qualité de fonctionnement réelle vs théorique
    
    Args:
        actual_production: Production réelle en kWh
        theoretical_production: Production théorique en kWh
        
    Returns:
        Performance Ratio en pourcentage (0-100)
        
    Example:
        >>> calculate_performance_ratio(actual=850, theoretical=1000)
        85.0
    """
    if theoretical_production <= 0:
        logger.warning("Production théorique nulle ou négative")
        return 0.0
    
    pr = (actual_production / theoretical_production) * 100
    
    # Limitation réaliste (PR typique entre 70% et 90%)
    if pr > 100:
        logger.warning(f"PR > 100% détecté: {pr:.2f}% (données incohérentes)")
    
    return round(pr, 2)


def categorize_alert_severity(
    power_drop_percent: float,
    temperature: float,
    offline_duration_minutes: int
) -> str:
    """
    Détermine la sévérité d'une alerte basée sur plusieurs critères
    
    Args:
        power_drop_percent: Chute de production en %
        temperature: Température du panneau en °C
        offline_duration_minutes: Durée hors ligne en minutes
        
    Returns:
        Niveau de sévérité: 'low', 'medium', 'high', ou 'critical'
    """
    severity_score = 0
    
    # Score basé sur la chute de production
    if power_drop_percent > 80:
        severity_score += 4
    elif power_drop_percent > 50:
        severity_score += 3
    elif power_drop_percent > 25:
        severity_score += 2
    elif power_drop_percent > 10:
        severity_score += 1
    
    # Score basé sur la température
    if temperature > 80:
        severity_score += 3
    elif temperature > 70:
        severity_score += 2
    elif temperature > 60:
        severity_score += 1
    
    # Score basé sur la durée hors ligne
    if offline_duration_minutes > 240:  # > 4h
        severity_score += 3
    elif offline_duration_minutes > 60:  # > 1h
        severity_score += 2
    elif offline_duration_minutes > 15:
        severity_score += 1
    
    # Détermination de la sévérité
    if severity_score >= 8:
        return 'critical'
    elif severity_score >= 5:
        return 'high'
    elif severity_score >= 3:
        return 'medium'
    else:
        return 'low'


def format_api_error(status_code: int, error_message: str = "") -> Dict:
    """
    Formate un message d'erreur API de manière standardisée
    
    Args:
        status_code: Code HTTP de l'erreur
        error_message: Message d'erreur détaillé (optionnel)
        
    Returns:
        Dict formaté avec les détails de l'erreur
    """
    error_mapping = {
        400: "Requête invalide",
        401: "Non authentifié - Vérifier la clé API",
        403: "Accès refusé - Permissions insuffisantes",
        404: "Ressource non trouvée",
        429: "Trop de requêtes - Limite de taux atteinte",
        500: "Erreur interne du serveur",
        503: "Service temporairement indisponible"
    }
    
    default_message = error_mapping.get(status_code, "Erreur inconnue")
    
    return {
        'error': True,
        'status_code': status_code,
        'message': error_message or default_message,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }


def sanitize_site_name(name: str) -> str:
    """
    Nettoie et normalise un nom de site
    
    Args:
        name: Nom brut du site
        
    Returns:
        Nom nettoyé et normalisé
    """
    if not name:
        return "Site Sans Nom"
    
    # Suppression des caractères spéciaux
    sanitized = re.sub(r'[^\w\s-]', '', name)
    
    # Normalisation des espaces
    sanitized = ' '.join(sanitized.split())
    
    # Capitalisation
    sanitized = sanitized.title()
    
    return sanitized


def estimate_daily_production(
    panel_count: int,
    panel_wattage: int = 400,
    avg_sun_hours: float = 5.0,
    efficiency: float = 0.85
) -> float:
    """
    Estime la production journalière d'une installation
    
    Args:
        panel_count: Nombre de panneaux
        panel_wattage: Puissance crête d'un panneau en W (défaut: 400W)
        avg_sun_hours: Heures d'ensoleillement moyen (défaut: 5h)
        efficiency: Facteur d'efficacité global (défaut: 0.85)
        
    Returns:
        Production estimée en kWh/jour
    """
    if panel_count <= 0 or avg_sun_hours <= 0:
        return 0.0
    
    total_power_kw = (panel_count * panel_wattage) / 1000
    daily_production = total_power_kw * avg_sun_hours * efficiency
    
    return round(daily_production, 2)


def convert_coordinates_to_region(latitude: float, longitude: float) -> str:
    """
    Détermine la région VolcaSolar basée sur les coordonnées GPS
    
    Args:
        latitude: Latitude GPS
        longitude: Longitude GPS
        
    Returns:
        Code région (PDD, CDF, LYO, etc.)
    """
    # Coordonnées approximatives des principales régions
    regions = {
        'PDD': (45.7772, 3.0870),   # Puy-de-Dôme (Clermont-Ferrand)
        'CDF': (45.7833, 4.8333),   # Cantal (Aurillac)
        'LYO': (45.7640, 4.8357),   # Lyon
        'GRE': (45.1885, 5.7245),   # Grenoble
        'MRS': (43.2965, 5.3698),   # Marseille
    }
    
    # Calcul de la distance minimale
    min_distance = float('inf')
    closest_region = 'UNK'  # Unknown
    
    for region_code, (lat, lon) in regions.items():
        distance = ((latitude - lat) ** 2 + (longitude - lon) ** 2) ** 0.5
        if distance < min_distance:
            min_distance = distance
            closest_region = region_code
    
    return closest_region


def generate_maintenance_report(site_data: Dict, alerts: List[Dict]) -> str:
    """
    Génère un rapport de maintenance textuel
    
    Args:
        site_data: Données du site
        alerts: Liste des alertes
        
    Returns:
        Rapport formaté en texte
    """
    report_lines = [
        "=" * 60,
        f"RAPPORT DE MAINTENANCE - {site_data.get('site_id', 'N/A')}",
        f"Site: {site_data.get('name', 'N/A')}",
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 60,
        "",
        "ÉTAT ACTUEL:",
        f"  • Statut: {site_data.get('status', 'N/A')}",
        f"  • Production: {site_data.get('power_output_kw', 0)} kW",
        f"  • Efficacité: {site_data.get('efficiency_percent', 0)}%",
        f"  • Température: {site_data.get('panel_temperature_c', 0)}°C",
        "",
        f"ALERTES ACTIVES: {len(alerts)}",
    ]
    
    if alerts:
        for i, alert in enumerate(alerts, 1):
            report_lines.append(f"  {i}. [{alert.get('severity', 'N/A').upper()}] {alert.get('message', 'N/A')}")
    else:
        report_lines.append("  Aucune alerte active")
    
    report_lines.extend([
        "",
        "=" * 60
    ])
    
    return "\n".join(report_lines)


# Constantes utiles
REGION_CODES = {
    'PDD': 'Puy-de-Dôme',
    'CDF': 'Cantal',
    'LYO': 'Lyon',
    'GRE': 'Grenoble',
    'MRS': 'Marseille',
    'BOR': 'Bordeaux',
    'TLS': 'Toulouse'
}

ALERT_SEVERITIES = ['low', 'medium', 'high', 'critical']
SITE_STATUSES = ['online', 'offline', 'maintenance', 'warning', 'error']
MAINTENANCE_TYPES = ['cleaning', 'inspection', 'repair', 'upgrade', 'emergency']


if __name__ == "__main__":
    # Tests unitaires basiques
    print("Tests des fonctions utilitaires SolarSync\n")
    
    # Test format_site_id
    test_ids = ['pdd001', 'cdf-42', 'VS-LYO-003']
    print("Test format_site_id:")
    for test_id in test_ids:
        print(f"  {test_id} -> {format_site_id(test_id)}")
    
    # Test calculate_efficiency
    print("\nTest calculate_efficiency:")
    eff = calculate_efficiency(power_output=3.2, irradiance=800, panel_count=20)
    print(f"  Efficacité: {eff}%")
    
    # Test validation
    print("\nTest validate_site_data:")
    test_data = {
        'site_id': 'VS-PDD-001',
        'power_output_kw': 45.2,
        'status': 'online',
        'panel_temperature_c': 55.3
    }
    is_valid, errors = validate_site_data(test_data)
    print(f"  Valide: {is_valid}")
    if errors:
        print(f"  Erreurs: {errors}")
    
    print("\n✓ Tests terminés")
