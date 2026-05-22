from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
import requests
from django.contrib.auth import get_user_model
from django.conf import settings
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
import jwt
import logging
from rest_framework.permissions import BasePermission

User = get_user_model()
logger = logging.getLogger(__name__)

class KeycloakAuthentication(BaseAuthentication):
    """Einfache Keycloak Token Validierung"""
    
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '').split()
        
        if len(auth_header) != 2 or auth_header[0] != 'Bearer':
            return None
        
        token = auth_header[1]
        
        try:
            # Validiere Token gegen Keycloak UserInfo Endpoint
            userinfo_url = settings.OIDC_OP_USER_ENDPOINT
            response = requests.get(
                userinfo_url,
                headers={'Authorization': f'Bearer {token}'},
                verify=False
            )
            
            if response.status_code != 200:
                raise AuthenticationFailed('Token ungültig')
            
            user_info = response.json()
            
            # User in Django erstellen/aktualisieren
            user, created = User.objects.get_or_create(
                username=user_info.get('preferred_username'),
                defaults={
                    'first_name': user_info.get('given_name', ''),
                    'last_name': user_info.get('family_name', ''),
                    'email': user_info.get('email', '')
                }
            )
            
            return (user, None)
            
        except Exception as e:
            raise AuthenticationFailed(f'Token Validierung fehlgeschlagen: {str(e)}')


class KeycloakOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    """Custom OIDC Backend mit Group/Role Blocking"""
    
    def get_userinfo(self, access_token, id_token, payload):
        """
        Überschreibe get_userinfo um Gruppen/Rollen zu prüfen
        Dies wird NACH der Token-Validierung aufgerufen
        """
        # Erst die Standard UserInfo holen
        user_info = super().get_userinfo(access_token, id_token, payload)
        
        # Hier können wir auf die User Info (die auch Groups enthält) zugreifen
        logger.info(f"OIDC UserInfo für {user_info.get('preferred_username')}: {user_info}")
        
        # Gruppen und Rollen prüfen (aus UserInfo oder aus payload)
        groups = user_info.get('groups', [])
        realm_access = user_info.get('realm_access', {})
        roles = realm_access.get('roles', [])
        
        logger.info(f"Groups: {groups}, Roles: {roles}")
        
        # Access-Check: Ist User in /Manufacturers Gruppe oder hat default-deny Rolle?
        is_manufacturer = '/Manufacturers' in groups
        has_default_deny = 'default-deny' in roles
        
        if is_manufacturer or has_default_deny:
            logger.warning(f"OIDC Access denied for {user_info.get('preferred_username')}: manufacturer={is_manufacturer}, default-deny={has_default_deny}")
            raise AuthenticationFailed("Access denied: insufficient permissions")
        
        return user_info

