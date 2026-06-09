from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
import requests
from django.contrib.auth import get_user_model
from django.conf import settings
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
import jwt
import logging
import xml.etree.ElementTree as ET
from math import radians, sin, cos, sqrt, atan2
import gzip
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import uuid
import base64
import json

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

class passkeyHelper:
    """Hilfsmethoden für Passkey-Verarbeitung"""

    @staticmethod
    def generate_key_secret(num_bytes = 16):
        key = {
        "kid":str(uuid.uuid4()),
        "secret":get_random_bytes(num_bytes)
        }
        return key 

    @staticmethod    
    def create_key(secret = None, nonce = None):
        if not secret:
            secret = passkeyHelper.generate_key_secret()
        cipher = AES.new(secret, AES.MODE_EAX, nonce=nonce)
        return cipher
        
    @staticmethod
    def encode_header(header):
        header = json.dumps(header ) 
        header = header.encode('ascii') 
        return header

    @staticmethod   
    def decode_header(header):
        header = base64.b64decode(header)
        header = header.decode('ascii')
        header = json.loads(header )  
        return header

    @staticmethod    
    def cipher_msg(msg, header, key):
        header = passkeyHelper.encode_header(header)
        #print("Header:", header)
        
        cipher = passkeyHelper.create_key(key)
        cipher.update(header)
        ciphertext, tag = cipher.encrypt_and_digest(msg)
        
        json_k = [ 'nonce', 'header', 'ciphertext', 'tag' ]
        json_v = [ base64.b64encode(x).decode('utf-8') for x in (cipher.nonce, header, ciphertext, tag) ]
        result = dict(zip(json_k, json_v))
        
        #result_json = json.dumps(result)
        #b64_old = base64.b64encode(result_json.encode('utf-8'))
        
        b64 = passkeyHelper.json_to_compressed_base64(result)
        
        #print(f"Compression: {100*len(b64)/len(b64_old):.2f}%")
        print(f"Result Length: {len(b64)}")
        
        return b64
        
    @staticmethod    
    def get_header_from_passkey(passkey):
        header = {"kid":passkey['kid'], "server_url":passkey['server_url'], "realm_name":passkey['realm_name'], "farm_realm":passkey['farm_realm'], "username":passkey['username']}
        return header

    @staticmethod    
    def get_header_from_msg(msg):
        #msg_jsons = base64.b64decode(msg.decode('utf-8'))
        #msg_json = json.loads(msg_jsons)
        msg_json = passkeyHelper.compressed_base64_to_json(msg)
        
        header = passkeyHelper.decode_header(msg_json['header'])
        return header

    @staticmethod    
    def decode_msg(msg):
        msg = base64.b64decode(msg.decode('utf-8'))
        msg = json.loads(msg)
        #print(msg)
        
        header = passkeyHelper.decode_header(msg['header'])
        #print(header)
        
        return header, msg
            
    @staticmethod
    def decipher_msg(msg, key_secret):      
        try:
            #msg = base64.b64decode(msg.decode('utf-8'))
            #b64 = json.loads(msg)
            
            b64 = passkeyHelper.compressed_base64_to_json(msg)
            
            json_k = [ 'nonce', 'header', 'ciphertext', 'tag' ]
            jv = {k:base64.b64decode(b64[k]) for k in json_k}
            #print(jv)
            print(key)
            cipher = passkeyHelper.create_key(key_secret, nonce=jv['nonce'])
            cipher.update(jv['header'])
            plaintext = cipher.decrypt_and_verify(jv['ciphertext'], jv['tag'])
            
            return plaintext
        except (ValueError, KeyError):
            print("Incorrect decryption")

    @staticmethod     
    def encode_json_msg(json_msg):
        #json_str = json.dumps(json_msg)
        #msg = base64.b64encode(json_str.encode('utf-8'))
        
        msg = passkeyHelper.json_to_compressed_base64(json_msg)
        return msg
        
    @staticmethod
    def decode_json_msg(msg):
        #json_str = base64.b64decode(msg).decode('utf-8')
        #json_msg = json.loads(json_str)
        
        json_msg = passkeyHelper.compressed_base64_to_json(msg)
        return json_msg
        
    @staticmethod
    def json_to_compressed_base64(json_obj):
        """
        Konvertiert ein JSON-Objekt zu einem gezippten Base64-String
        
        Args:
            json_obj: JSON-Objekt (dict, list, etc.)
        
        Returns:
            Base64-kodierter String des gezippten JSON
        """
        # JSON zu String konvertieren
        json_string = json.dumps(json_obj)
        
        # String zu Bytes konvertieren
        json_bytes = json_string.encode('utf-8')
        
        # Mit gzip komprimieren
        compressed = gzip.compress(json_bytes)
        
        # Zu Base64 kodieren
        base64_string = base64.b64encode(compressed)#.decode('utf-8')
        
        return base64_string

    @staticmethod
    def compressed_base64_to_json(base64_string):
        """
        Dekodiert einen Base64-String zurück zu einem JSON-Objekt
        
        Args:
            base64_string: Base64-kodierter String
        
        Returns:
            JSON-Objekt
        """
        # Von Base64 dekodieren
        compressed = base64.b64decode(base64_string)#.encode('utf-8'))
        
        # Gzip dekomprimieren
        json_bytes = gzip.decompress(compressed)
        
        # Bytes zu String konvertieren
        json_string = json_bytes.decode('utf-8')
        
        # String zu JSON-Objekt konvertieren
        json_obj = json.loads(json_string)
        
        return json_obj
    

class helperMethods:
    """Hilfsmethoden für Authentifizierung und Datenverarbeitung"""
    
    @staticmethod
    def get_farmer_from_request(request):
        """
        Helper: Holt den Farmer basierend auf der Email des authentifizierten Users
        Nutzt die Email aus dem Keycloak-Token (via request.user.email)
        
        Returns: Farmer Objekt oder None
        """
        from API.django_api.models import Farmer
        
        user = request.user
        if not user or not user.email:
            return None
        
        try:
            farmer = Farmer.objects.get(email=user.email)
            return farmer
        except Farmer.DoesNotExist:
            return None
    
    @staticmethod
    def parse_points_from_lsg(lsg_element):
        """
        Parsed Punkte aus XML LSG-Element
        
        Args:
            lsg_element: XML Element vom Typ LSG
            
        Returns:
            List von [lat, lon] Koordinaten
        """
        points = []
        if lsg_element is None:
            return points

        for pnt in lsg_element.findall("PNT"):
            lat = pnt.get("C")
            lon = pnt.get("D")
            if lat is None or lon is None:
                continue
            points.append([float(lat), float(lon)])
        return points
    
    @staticmethod
    def distance_km(points):
        """
        Berechnet Haversine-Entfernung zwischen Punkten in km
        
        Args:
            points: List von [lat, lon] Koordinaten
            
        Returns:
            Gesamtdistanz in km (gerundet auf 4 Dezimalstellen)
        """
        if len(points) < 2:
            return 0.0

        r = 6371.0  # Erdradius in km
        total = 0.0
        for i in range(1, len(points)):
            lat1, lon1 = points[i - 1]
            lat2, lon2 = points[i]

            dlat = radians(lat2 - lat1)
            dlon = radians(lon2 - lon1)

            a = (
                sin(dlat / 2) ** 2
                + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
            )
            c = 2 * atan2(sqrt(a), sqrt(1 - a))
            total += r * c

        return round(total, 4)
    
    @staticmethod
    def add_user_to_manufacturers_group(user_id):
        """
        Helper-Methode: Fügt einen User zur 'Manufacturers' Gruppe hinzu
        
        Args:
            user_id: Die Keycloak User ID
            
        Returns:
            (bool, str) - (success, message)
        """
        try:
            # Erst einen Admin-Token holen
            token_url = f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token"
            
            token_response = requests.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.KEYCLOAK_CLIENT_ID,
                    "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
                },
                verify=False,
            )
            
            if token_response.status_code != 200:
                return False, "Keycloak admin token konnte nicht geholt werden"
            
            access_token = token_response.json()["access_token"]
            
            # Alle Gruppen abrufen
            groups_url = f"{settings.KEYCLOAK_URL}/admin/realms/{settings.KEYCLOAK_REALM}/groups"
            groups_response = requests.get(
                groups_url,
                headers={"Authorization": f"Bearer {access_token}"},
                verify=False
            )
            
            manufacturers_group = None
            for group in groups_response.json():
                if group['name'] == 'Manufacturers':
                    manufacturers_group = group
                    break
            
            if not manufacturers_group:
                return False, "Manufacturers Gruppe existiert nicht in Keycloak"
            
            # User zur Gruppe hinzufügen
            group_id = manufacturers_group['id']
            add_url = f"{settings.KEYCLOAK_URL}/admin/realms/{settings.KEYCLOAK_REALM}/users/{user_id}/groups/{group_id}"
            
            add_response = requests.put(
                add_url,
                headers={"Authorization": f"Bearer {access_token}"},
                verify=False
            )
            
            if add_response.status_code not in [201, 204, 200]:
                return False, f"User zu Gruppe hinzufügen fehlgeschlagen: {add_response.text}"
            
            return True, "User zu Manufacturers Gruppe hinzugefügt"
            
        except Exception as e:
            logger.error(f"Fehler beim Hinzufügen zur Gruppe: {e}")
            return False, str(e)
    
    @staticmethod
    def check_user_access_allowed_from_jwt(decoded_token):
        """
        Überprüft Zugriff direkt aus dem JWT heraus
        
        Zugriff wird VERWEIGERT wenn:
        - User in '/Manufacturers' Gruppe ist (beachte Leading Slash!)
        - ODER User hat 'default-deny' Rolle
        
        Args:
            decoded_token: Dekodierter JWT Token (dict)
            
        Returns:
            (bool, str) - (is_allowed, error_message)
        """
        # Gruppen aus JWT (mit Leading Slash!)
        groups = decoded_token.get('groups', [])
        
        # Rollen aus JWT (realm_access)
        realm_access = decoded_token.get('realm_access', {})
        roles = realm_access.get('roles', [])
        
        # Debug: Ausgeben für Testing
        logger.debug(f"Groups: {groups}")
        logger.debug(f"Roles: {roles}")
        
        # Überprüfung: User in Manufacturers Gruppe? (mit Slash!)
        is_manufacturer = '/Manufacturers' in groups
        
        # Überprüfung: User hat 'default-deny' Rolle?
        has_default_deny = 'default-deny' in roles
        
        # Zugriff verweigern wenn eine Bedingung zutrifft
        if is_manufacturer or has_default_deny:
            logger.warning(f"Access denied: manufacturer={is_manufacturer}, default-deny={has_default_deny}")
            return False, "not allowed (missing access-code)"
        
        return True, None

    @staticmethod
    def authenticate_user_from_credentials(username, password):
        """
        Authentifiziert einen User mit Credentials gegen Keycloak
        
        Args:
            username: Username oder Email
            password: Passwort
            
        Returns:
            (dict, str) - (decoded_token, error_message)
            Bei Erfolg: (decoded_token_dict, None)
            Bei Fehler: (None, error_message)
        """
        try:
            token_url = f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token"
            
            payload = {
                'grant_type': 'password',
                'client_id': settings.OIDC_RP_CLIENT_ID,
                'client_secret': settings.OIDC_RP_CLIENT_SECRET,
                'username': username,
                'password': password,
                'scope': 'openid profile email'
            }
            
            response = requests.post(token_url, data=payload, verify=False)
            
            if response.status_code != 200:
                return None, "Invalid credentials"
            
            token_data = response.json()
            access_token = token_data.get('access_token')
            
            # JWT dekodieren
            decoded_token = jwt.decode(access_token, options={"verify_signature": False})
            
            # Zugriff überprüfen
            is_allowed, error_msg = helperMethods.check_user_access_allowed_from_jwt(decoded_token)
            if not is_allowed:
                return None, error_msg
            
            return decoded_token, None
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None, str(e)

