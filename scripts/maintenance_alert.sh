#!/bin/bash

################################################################################
# SolarSync Maintenance Alert Script
# 
# Description: Vérifie les alertes critiques et notifie l'équipe de maintenance
#
# Usage: 
#   ./scripts/maintenance_alert.sh [options]
#
# Options:
#   -e, --env       Environnement (dev|staging|production) [défaut: production]
#   -s, --site      ID site spécifique (ex: VS-PDD-001)
#   -v, --verbose   Mode verbeux
#   -h, --help      Affiche l'aide
#
################################################################################

set -euo pipefail

# Couleurs pour output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration par défaut
ENVIRONMENT="production"
SITE_ID=""
VERBOSE=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${PROJECT_ROOT}/logs/maintenance_$(date +%Y%m%d).log"

# Créer le répertoire logs si inexistant
mkdir -p "${PROJECT_ROOT}/logs"

################################################################################
# Fonctions utilitaires
################################################################################

log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${level}] ${message}" | tee -a "$LOG_FILE"
}

log_info() {
    echo -e "${BLUE}ℹ${NC} $*"
    log "INFO" "$*"
}

log_success() {
    echo -e "${GREEN}✓${NC} $*"
    log "SUCCESS" "$*"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $*"
    log "WARNING" "$*"
}

log_error() {
    echo -e "${RED}✗${NC} $*" >&2
    log "ERROR" "$*"
}

show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Vérifie les alertes critiques SolarSync et notifie l'équipe de maintenance.

OPTIONS:
    -e, --env ENV          Environnement cible (dev|staging|production)
                          Défaut: production
    
    -s, --site SITE_ID    ID du site à vérifier (ex: VS-PDD-001)
                          Si non spécifié, vérifie tous les sites
    
    -v, --verbose         Active le mode verbeux
    
    -h, --help            Affiche ce message d'aide

EXEMPLES:
    # Vérifier tous les sites en production
    $(basename "$0")
    
    # Vérifier un site spécifique
    $(basename "$0") --site VS-PDD-001
    
    # Vérifier en environnement staging
    $(basename "$0") --env staging --verbose

VARIABLES D'ENVIRONNEMENT:
    SOLARSYNC_API_KEY           Clé API SolarSync (requis)
    SLACK_WEBHOOK_URL           URL webhook Slack pour notifications
    EMAIL_RECIPIENTS            Emails séparés par des virgules

CONTACT:
    Email: devops@volcasolar.fr
    Astreinte: +33 6 12 34 56 78

EOF
}

################################################################################
# Vérification des prérequis
################################################################################

check_requirements() {
    log_info "Vérification des prérequis..."
    
    # Vérifier Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 n'est pas installé"
        exit 1
    fi
    
    # Vérifier jq pour parsing JSON
    if ! command -v jq &> /dev/null; then
        log_warning "jq n'est pas installé (recommandé pour parsing JSON)"
        log_info "Installation: apt-get install jq (Debian/Ubuntu) ou brew install jq (macOS)"
    fi
    
    # Vérifier fichier .env
    if [[ ! -f "${PROJECT_ROOT}/.env" ]]; then
        log_error "Fichier .env non trouvé à ${PROJECT_ROOT}/.env"
        log_info "Copier .env.example et le configurer: cp .env.example .env"
        exit 1
    fi
    
    # Charger variables d'environnement
    set -a
    source "${PROJECT_ROOT}/.env"
    set +a
    
    # Vérifier clé API
    if [[ -z "${SOLARSYNC_API_KEY:-}" ]]; then
        log_error "SOLARSYNC_API_KEY non définie dans .env"
        exit 1
    fi
    
    log_success "Prérequis OK"
}

################################################################################
# Récupération des alertes
################################################################################

fetch_alerts() {
    local site_filter="$1"
    local api_url="${SOLARSYNC_BASE_URL:-https://api.solarsync-volcasolar.fr}"
    local endpoint="/v2/alerts"
    
    if [[ -n "$site_filter" ]]; then
        endpoint="${endpoint}?site_id=${site_filter}"
    fi
    
    log_info "Récupération des alertes depuis ${api_url}${endpoint}..."
    
    # Requête API
    local response
    response=$(curl -s -w "\n%{http_code}" \
        -H "Authorization: Bearer ${SOLARSYNC_API_KEY}" \
        -H "Content-Type: application/json" \
        "${api_url}${endpoint}")
    
    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | sed '$d')
    
    if [[ "$http_code" != "200" ]]; then
        log_error "Erreur API (HTTP ${http_code})"
        [[ "$VERBOSE" == true ]] && echo "$body"
        return 1
    fi
    
    echo "$body"
}

################################################################################
# Analyse des alertes
################################################################################

analyze_alerts() {
    local alerts_json="$1"
    
    if ! command -v jq &> /dev/null; then
        # Parsing manuel simple si jq non disponible
        local alert_count=$(echo "$alerts_json" | grep -o '"id"' | wc -l)
        echo "$alert_count"
        return 0
    fi
    
    # Comptage avec jq
    local total=$(echo "$alerts_json" | jq '. | length')
    local critical=$(echo "$alerts_json" | jq '[.[] | select(.severity == "critical")] | length')
    local high=$(echo "$alerts_json" | jq '[.[] | select(.severity == "high")] | length')
    local medium=$(echo "$alerts_json" | jq '[.[] | select(.severity == "medium")] | length')
    
    echo "${total}:${critical}:${high}:${medium}"
}

################################################################################
# Notification
################################################################################

send_notification() {
    local severity="$1"
    local message="$2"
    local site_id="${3:-N/A}"
    
    log_info "Envoi notification: [${severity}] ${message}"
    
    # Notification Slack
    if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
        local emoji
        case "$severity" in
            critical) emoji=":rotating_light:" ;;
            high) emoji=":warning:" ;;
            medium) emoji=":information_source:" ;;
            *) emoji=":bell:" ;;
        esac
        
        local payload=$(cat <<EOF
{
    "text": "${emoji} *SolarSync Alert - ${severity^^}*",
    "attachments": [{
        "color": "$([ "$severity" = "critical" ] && echo "danger" || echo "warning")",
        "fields": [
            {"title": "Site", "value": "${site_id}", "short": true},
            {"title": "Severité", "value": "${severity}", "short": true},
            {"title": "Message", "value": "${message}", "short": false},
            {"title": "Timestamp", "value": "$(date '+%Y-%m-%d %H:%M:%S')", "short": true}
        ]
    }]
}
EOF
)
        
        curl -s -X POST "${SLACK_WEBHOOK_URL}" \
            -H "Content-Type: application/json" \
            -d "$payload" > /dev/null
        
        [[ "$VERBOSE" == true ]] && log_info "Notification Slack envoyée"
    fi
    
    # Notification Email (si configuré)
    if [[ -n "${EMAIL_RECIPIENTS:-}" ]] && command -v mail &> /dev/null; then
        echo -e "Alerte SolarSync\n\nSite: ${site_id}\nSeverité: ${severity}\n\n${message}" | \
            mail -s "[SolarSync] Alerte ${severity} - ${site_id}" "${EMAIL_RECIPIENTS}"
        
        [[ "$VERBOSE" == true ]] && log_info "Email envoyé à ${EMAIL_RECIPIENTS}"
    fi
}

################################################################################
# Génération rapport
################################################################################

generate_report() {
    local alerts_json="$1"
    local stats="$2"
    
    IFS=':' read -r total critical high medium <<< "$stats"
    
    cat << EOF

╔════════════════════════════════════════════════════════════════╗
║           RAPPORT ALERTES SOLARSYNC - MAINTENANCE              ║
╚════════════════════════════════════════════════════════════════╝

📅 Date: $(date '+%Y-%m-%d %H:%M:%S')
🌍 Environnement: ${ENVIRONMENT}
$([ -n "$SITE_ID" ] && echo "🏭 Site: ${SITE_ID}" || echo "🏭 Sites: Tous")

─────────────────────────────────────────────────────────────────

📊 STATISTIQUES:
   Total alertes actives: ${total}
   
   🔴 Critiques: ${critical}
   🟠 Élevées: ${high}
   🟡 Moyennes: ${medium}

─────────────────────────────────────────────────────────────────

EOF

    if command -v jq &> /dev/null && [[ "$total" -gt 0 ]]; then
        echo "📋 DÉTAILS DES ALERTES:"
        echo ""
        echo "$alerts_json" | jq -r '.[] | "  [\(.severity | ascii_upcase)] \(.site_id) - \(.message)\n    ⏰ Depuis: \(.created_at)"'
        echo ""
    fi
    
    cat << EOF
─────────────────────────────────────────────────────────────────

📞 CONTACTS URGENCE:
   DevOps: +33 6 12 34 56 78
   Email: devops@volcasolar.fr
   Slack: #solarsync-alerts

═════════════════════════════════════════════════════════════════

EOF
}

################################################################################
# Fonction principale
################################################################################

main() {
    log_info "=== Démarrage vérification alertes SolarSync ==="
    log_info "Environnement: ${ENVIRONMENT}"
    [[ -n "$SITE_ID" ]] && log_info "Site: ${SITE_ID}"
    
    # Vérifications
    check_requirements
    
    # Récupération alertes
    local alerts_json
    if ! alerts_json=$(fetch_alerts "$SITE_ID"); then
        log_error "Impossible de récupérer les alertes"
        exit 1
    fi
    
    # Analyse
    local stats
    stats=$(analyze_alerts "$alerts_json")
    IFS=':' read -r total critical high medium <<< "$stats"
    
    # Rapport
    generate_report "$alerts_json" "$stats"
    
    # Notifications si alertes critiques
    if [[ "$critical" -gt 0 ]]; then
        log_error "${critical} alerte(s) critique(s) détectée(s)!"
        send_notification "critical" "${critical} alerte(s) critique(s) nécessitent une intervention immédiate" "$SITE_ID"
        exit 2
    elif [[ "$high" -gt 0 ]]; then
        log_warning "${high} alerte(s) de haute priorité détectée(s)"
        send_notification "high" "${high} alerte(s) de haute priorité à traiter" "$SITE_ID"
        exit 1
    else
        log_success "Aucune alerte critique (${total} alerte(s) au total)"
        exit 0
    fi
}

################################################################################
# Parsing des arguments
################################################################################

while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -s|--site)
            SITE_ID="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            log_error "Option inconnue: $1"
            show_help
            exit 1
            ;;
    esac
done

# Lancement
main
