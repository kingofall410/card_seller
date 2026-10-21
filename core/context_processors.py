import os
import logging

logger = logging.getLogger(__name__)

def environment_banner(request):
    """
    Injects navbar styling and debug info based on the active environment/port.
    """
    # Check if an environment variable or setting explicitly defines this as Env 2
    is_secondary = os.getenv('DJANGO_ENV_SECONDARY', 'False').lower() == 'true'
    
    # Alternatively, you can check the active database port or name from settings
    from django.conf import settings
    db_port = settings.DATABASES['default'].get('PORT', '5432')
    
    if db_port == '5433' or is_secondary:
        navbar_color = "#15C018"  # Dark Red for Clone / Env 2
        env_label = "DEV (Port 5433)"
    else:
        navbar_color = "#FC3E3E"  # Charcoal / Black for Primary / Env 1
        env_label = "PROD (Port 5432)"
        
    # Debug log to verify environment state
    logger.debug(f"[DEBUG_LOG] Active Environment Loaded: {env_label} | Navbar Color: {navbar_color}")

    return {
        'navbar_color': navbar_color,
        'current_env_label': env_label,
    }