# FarmSPT Code-Struktur & API-Dokumentation

##  Dateistruktur

### `docker-compose.yml`
- **traefik** (v3): Reverse Proxy, SSL/TLS, ACME Zertifikate
- **keycloak**: Identity & Access Management (OIDC Provider) -> fliegt ggf noch raus (only dev)
- **postgres**: Datenbank (farmspt_db)
- **backend**: Django REST API

### `FarmSPT_Backend/API/settings.py`
- Django Konfiguration
- Keycloak/OIDC Setup (mozilla-django-oidc)
- Datenbankverbindung PostgreSQL
- CORS, Security Headers via Traefik
- env data


### `FarmSPT_Backend/API/urls.py`
- REST API Routing
- Registrierte ViewSets
- Admin Interface
- OIDC Endpoints (only dev)
- Token Endpoint
- User Creation Endpoint

### `FarmSPT_Backend/API/django_api/models.py`
**Datenbank-Schema:**

1. **Farmer** - Feldbesitzer/Eigentümer
   - id (UUID)
   - name: Name des Farmers
   - email: Email-Adresse
   - timestamps: created_at, updated_at

2. **Role** - Rollen für RBAC
   - name: Rollenname
   - description: Beschreibung

3. **Manufacturer** - Gerätehersteller
   - id (UUID)
   - name: Name des Herstellers
   - timestamps: created_at, updated_at

4. **SyncPartner** - Synchronisationspartner
   - id (UUID)
   - farmer: FK → Farmer (nullable)
   - manufacturer: FK → Manufacturer
   - role: FK → Role (nullable)
   - timestamps: created_at, updated_at

5. **FieldData** - Feldmetadaten für Auswertung & Zuordnung
   - farmer: FK → Farmer (nullable)
   - syncPartner: FK → SyncPartner

6. **FieldBoundary** - Feldgrenzen (aus XML)
   - id (UUID)
   - name: Name des Feldes
   - coordinates: JSON array mit [lat, lng] Punkte
   - area_hectares: Größe des Feldes
   - farmer: FK → Farmer (nullable) - 
   - timestamps: created_at, updated_at

7. **ABTrace** - GPS-Fahrtspuren (aus XML)
   - id (UUID)
   - field: FK → FieldBoundary
   - trace_data: JSON mit GPS-Punkte + Name
   - distance_km: Berechnete Distanz (Haversine)
   - farmer: FK → Farmer (nullable) - **NEU: Farmer-Zuordnung**
   - created_at: Zeitstempel

### `FarmSPT_Backend/API/django_api/serializers.py`
**DRF Serializers:**

1. **UserSerializer** - Django User Serialization
   - fields: url, username, email, groups

2. **GroupSerializer** - Django Group Serialization
   - fields: url, name

3. **FieldBoundarySerializer** - Feldgrenzen
   - fields: id, name, coordinates, area_hectares, created_at

4. **FieldBoundaryXMLUploadSerializer** - XML Upload
   - file: FileField

5. **ABTraceSerializer** - GPS-Spuren
   - fields: id, field, trace_data, distance_km, created_at

6. **ABTraceXMLUploadSerializer** - XML Upload mit Field-ID
   - file: FileField
   - field_id: UUIDField

7. **RoleSerializer** - Rollen
   - fields: id, name, description

8. **FarmerSerializer** - Farmer
   - fields: id, name, email, created_at, updated_at

9. **ManufacturerSerializer** - Hersteller
   - fields: id, name, created_at, updated_at

10. **RoleSerializerForSyncPartner** - Nested Role für SyncPartner
    - fields: id, name (read_only)

11. **SyncPartnerSerializer** - Sync Partner mit Nested Relations
    - fields: id, farmer (read_only), manufacturer (read_only), role (read_only), created_at, updated_at

12. **FieldDataSerializer** - Feldmetadaten
    - fields: id, farmer (read_only), syncPartner (read_only)

### `FarmSPT_Backend/API/django_api/views.py`
**API Viewsets (Endpunkte):**

1. **UserViewSet** (`/api/users/`)
   - GET: Alle User
   - POST: User erstellen
   - Requires: IsAuthenticated

2. **GroupViewSet** (`/api/groups/`)
   - GET: Alle Groups
   - POST: Group erstellen

3. **FieldBoundaryViewSet** (`/api/fieldboundaries/`)
   - GET: Alle Felder (gefiltert nach aktuellem Farmer)
   - POST: Neues Feld
   - `POST /upload_xml`: XML-Datei importieren
   - **Funktion**: 
     - `_parse_points_from_lsg()`: Parst LSG-Element aus XML
     - `_distance_km()`: Berechnet Distanz mit Haversine-Formel (Großkreis)

4. **ABTraceViewSet** (`/api/traces/`)
   - GET: Alle Spuren (gefiltert nach aktuellem Farmer)
   - POST: Neue Spur
   - PATCH: Spur aktualisieren
   - `POST /upload_xml`: XML-Upload mit field_id
   - **Helper-Funktionen**:
     - `get_queryset()`: Filtert nach Farmer

### `FarmSPT_Backend/API/django_api/authentication.py`
**Authentifizierung & Helper:**

1. **KeycloakAuthentication** - Bearer Token Validierung
   - Validiert Token gegen Keycloak UserInfo Endpoint
   - Erstellt/aktualisiert Django User automatisch

2. **KeycloakOIDCAuthenticationBackend** - Custom OIDC Backend
   - Überschreibt `get_userinfo()` für Group/Role Blocking
   - Prüft auf `/Manufacturers` Gruppe oder `default-deny` Rolle
   - Wirft `AuthenticationFailed` bei Access Denial

3. **helperMethods** - Utility Functions
   - `get_farmer_from_request()`: Holt Farmer basierend auf User-Email
   - `parse_points_from_lsg()`: Parst [lat, lon] Koordinaten aus XML LSG-Element
   - `distance_km()`: Berechnet Haversine-Distanz zwischen GPS-Punkten (km)
   - `add_user_to_manufacturers_group()`: Fügt User zu Keycloak Gruppe hinzu (Admin Token)

## Authentifizierung

### Keycloak Integration (OIDC)
- **Provider**: Keycloak auf `https://keycloak.${PROJECT_BASE_URL}/realms/${KEYCLOAK_REALM}`
- **Realm**: `FarmSPT_v1`
- **Client**: `farmspt_v1-api`
- **Authentifizierung**: mozilla-django-oidc
- **Token-Validierung**: RS256 (JWKS Endpoint)
- **Access Control**: Gruppen/Rollen Blocking

### Flow - OIDC Redirect:
1. User besucht: `api.farmspt.ai.edvsz.hs-osnabrueck.de/oidc/authenticate/`
2. Redirect zu Keycloak Login
3. User authentifiziert sich
4. Keycloak gibt JWT Token + Gruppen/Rollen
5. Django validiert Token gegen JWKS Endpoint
6. User ist authentifiziert (wird in Django User-DB erstellt/aktualisiert)

### Flow - Token per Credentials:
1. POST an Token Endpoint mit User Credentials
2. Keycloak gibt Access Token + Refresh Token
3. Access Token wird zur Authorization bei API-Endpoints im Header genutzt (`Authorization: Bearer <token>`)

## Geplante Module

### FarmSPT_Dataspace
[ Platzhalter ]

### FarmSPT_StagingArea_MQTT
[ Platzhalter ]

### FarmSPT_SyncModule
[ Platzhalter ]

### FarmSPT_Transferlayer
[ Platzhalter ]

### etc. ###
