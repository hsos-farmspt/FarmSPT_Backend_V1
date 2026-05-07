# FarmSPT Code-Struktur & API-Dokumentation

##  Dateistruktur

### `FarmSPT_Backend/API/settings.py`
- Django Konfiguration
- Keycloak/OIDC Setup
- Datenbankverbindung PostgreSQL
- CORS, Security Headers via Traefik


### `FarmSPT_Backend/API/urls.py`
- REST API Routing
- Registrierte ViewSets
- Admin Interface
- OIDC Endpoints

### `FarmSPT_Backend/API/django_api/models.py`
**Datenbank-Schema:**

1. **FieldBoundary** - Feldgrenzen
   - id (UUID)
   - name: Name des Feldes
   - coordinates: JSON array mit [lat, lng] Punkte
   - area_hectares: Größe des Feldes
   - timestamps: created_at, updated_at
   
2. **ABTrace** - GPS-Fahrtspuren
   - id (UUID)
   - field: FK → FieldBoundary
   - trace_data: JSON mit GPS-Punkte
   - distance_km: Berechnete Distanz
   - created_at: Zeitstempel

3. **Role** - Rollen für RBAC
   - name: Rollenname
   - description: Beschreibung

4. **Policy** - Zugriffskontroll-Regeln (Casbin) ->unfinished
   - role: FK → Role
   - resource: z.B. 'fieldboundary', 'trace'
   - action: read, write, delete, admin, denied, custom, temporary
   - unique_together: Verhindert Duplikate

### `FarmSPT_Backend/API/django_api/views.py`
**API Viewsets (Endpunkte):**

1. **UserViewSet** (`/api/users/`) ->django standard und hier eigentlich nicht relevant ist zum testen
   - GET: Alle User
   - POST: User erstellen
   - Requires: IsAuthenticated

2. **GroupViewSet** (`/api/groups/`) >django standard und hier eigentlich nicht relevant ist zum testen
   - GET: Alle Groups
   - POST: Group erstellen

3. **FieldBoundaryViewSet** (`/api/fieldboundaries/`)
   - GET: Alle Felder
   - POST: Neues Feld
   - `POST /upload_xml`: XML-Datei importieren
   - **Funktion**: 
     - `_parse_points_from_lsg()`: Parst LSG-Element aus XML
     - `_distance_km()`: Berechnet Distanz mit Haversine-Formel (Großkreis)

4. **ABTraceViewSet** (`/api/traces/`)
   - GET: Alle Spuren
   - POST: Neue Spur
   - PATCH: Spur aktualisieren

### `FarmSPT_Backend/API/django_api/serializers.py`
[Beschreibung der DRF Serializers]

##  Authentifizierung

### Keycloak Integration (OIDC)
- Provider: Keycloak auf `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}`
- Client: farmspt_v1-api
- Authentifizierung: mozilla-django-oidc
- Token-Validierung: RS256

### Flow:
1. domain eingeben: api.farmspt.ai.edvsz.hs-osnabrueck.de/oidc/authenticate/
2. Redirect zu Keycloak (sign in)
3. Keycloak gibt JWT Token
4. Django validiert Token gegen JWKS Endpoint
5. User ist authentifiziert



##  Geplante Module

### FarmSPT_Dataspace
[ Platzhalter ]

### FarmSPT_StagingArea_MQTT
[ Platzhalter ]

### FarmSPT_SyncModule

### FarmSPT_Transferlayer
[ Platzhalter ]
