from django.contrib.auth.models import Group, User
from rest_framework import permissions, viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAdminUser, AllowAny
from API.django_api.serializers import ABTraceXMLUploadSerializer, FieldBoundaryXMLUploadSerializer, GroupSerializer, UserSerializer, FieldBoundarySerializer, ABTraceSerializer
from API.django_api.models import FieldBoundary, ABTrace
import xml.etree.ElementTree as ET
from .models import MQTTMessage, Role, SyncPartner
from .serializers import MQTTMessageSerializer, RoleSerializer, SyncPartnerSerializer
from keycloak import KeycloakAdmin
from keycloak.exceptions import KeycloakGetError
import requests
from django.conf import settings
import jwt
from .authentication import helperMethods
from django.http import HttpResponse
from django.views.generic import TemplateView

class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = User.objects.all().order_by("-date_joined")
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]


class GroupViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    queryset = Group.objects.all().order_by("name")
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated]


class FieldBoundaryViewSet(viewsets.ModelViewSet):
    """
    API endpoint für Feldgrenzen mit XML-Upload
    """
    queryset = FieldBoundary.objects.all()
    serializer_class = FieldBoundarySerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def get_queryset(self):
        """Filtert Feldgrenzen nach dem aktuellen Farmer"""
        farmer = helperMethods.get_farmer_from_request(self.request)
        if farmer:
            return FieldBoundary.objects.filter(farmer=farmer)
        return FieldBoundary.objects.none()

    @action(
        detail=False,
        methods=["get", "post"],
        parser_classes=[MultiPartParser, FormParser],
        serializer_class=FieldBoundaryXMLUploadSerializer,
        url_path="upload_xml",
    )
    def upload_xml(self, request):
        if request.method == "GET":
            return Response({"detail": "XML hochladen mit POST und Form-Feld file."})

        upload_serializer = FieldBoundaryXMLUploadSerializer(data=request.data)
        upload_serializer.is_valid(raise_exception=True)
        xml_file = upload_serializer.validated_data["file"]

        farmer = helperMethods.get_farmer_from_request(request)
        if not farmer:
            return Response(
                {"error": "Kein Farmer für deine Email gefunden"},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            root = ET.parse(xml_file).getroot()
        except ET.ParseError as e:
            return Response({"error": f"XML Parse Error: {e}"}, status=status.HTTP_400_BAD_REQUEST)

        pfd = root.find(".//PFD")
        if pfd is None:
            return Response({"error": "Kein PFD-Element gefunden."}, status=status.HTTP_400_BAD_REQUEST)

        field_name = pfd.get("C", "Unbenanntes Feld")
        area_raw = pfd.get("D")
        area_hectares = round(float(area_raw) / 10000.0, 4) if area_raw else 0.0

        boundary_lsg = pfd.find("./PLN/LSG")
        if boundary_lsg is None:
            boundary_lsg = pfd.find("./LSG[@A='1']")

        coordinates = helperMethods.parse_points_from_lsg(boundary_lsg)

        field = FieldBoundary.objects.create(
            name=field_name,
            coordinates=coordinates,
            area_hectares=area_hectares,
            farmer=farmer,  # ← Farmer gesetzt
        )

        # ZUSÄTZLICH: AB-Spuren importieren
        traces_imported = 0
        try:
            for ggp in pfd.findall(".//GGP"):
                ggp_name = (ggp.get("B") or "").strip()
                for gpn in ggp.findall("./GPN"):
                    gpn_type = gpn.get("B", "")
                    if gpn_type.lower() != "singletrack":
                        continue
                    for lsg in gpn.findall("./LSG"):
                        points = helperMethods.parse_points_from_lsg(lsg)
                        if points:  # Nur speichern wenn Punkte vorhanden
                            ABTrace.objects.create(
                                field=field,
                                trace_data={"name": ggp_name, "points": points},
                                distance_km=helperMethods.distance_km(points),
                            )
                            traces_imported += 1
        except Exception as e:
            # Fehler bei Spurenimport loggen, aber nicht Feldimport abbrechen
            print(f"Fehler beim Spurenimport: {e}")

        return Response(
            {
                "status": "success",
                "field_id": str(field.id),
                "name": field.name,
                "points": len(coordinates),
                "area_hectares": field.area_hectares,
                "traces_imported": traces_imported,  
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get'], url_path='edc-metadata')
    def edc_metadata(self, request, pk=None):
        """
        Gibt das Feld mit EDC-Katalog-Formattierung zurück
        GET /fieldboundaries/{id}/edc-metadata/
        """
        field = self.get_object()
        traces = ABTrace.objects.filter(field=field)
        
        data = {
            'asset_id': str(field.id),
            'asset_name': field.name,
            'description': f'Feld: {field.name}',
            'area_hectares': field.area_hectares,
            'coordinate_count': len(field.coordinates),
            'coordinates': field.coordinates,
            'created_at': field.created_at.isoformat(),
            'updated_at': field.updated_at.isoformat(),
            'traces_count': traces.count(),
            'traces': [
                {
                    'trace_id': str(t.id),
                    'name': t.trace_data.get('name', 'Unknown'),
                    'distance_km': t.distance_km,
                    'created_at': t.created_at.isoformat(),
                }
                for t in traces
            ]
        }
        return Response(data)


class ABTraceViewSet(viewsets.ModelViewSet):
    """
    API endpoint für AB-Spuren mit XML-Upload
    """
    queryset = ABTrace.objects.all()
    serializer_class = ABTraceSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def get_queryset(self):
        """Filtert AB-Spuren nach dem aktuellen Farmer"""
        farmer = helperMethods.get_farmer_from_request(self.request)
        if farmer:
            return ABTrace.objects.filter(farmer=farmer)
        return ABTrace.objects.none()

    @action(
        detail=False,
        methods=["get", "post"],
        parser_classes=[MultiPartParser, FormParser],
        serializer_class=ABTraceXMLUploadSerializer,
        url_path="upload_xml",
    )
    def upload_xml(self, request):
        if request.method == "GET":
            return Response({"detail": "XML hochladen mit POST und Feldern file + field_id."})

        upload_serializer = ABTraceXMLUploadSerializer(data=request.data)
        upload_serializer.is_valid(raise_exception=True)

        xml_file = upload_serializer.validated_data["file"]
        field_id = upload_serializer.validated_data["field_id"]

        farmer = helperMethods.get_farmer_from_request(request)
        if not farmer:
            return Response(
                {"error": "Kein Farmer für deine Email gefunden"},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            field = FieldBoundary.objects.get(id=field_id)
            # Prüfung: gehört das Feld auch zu diesem Farmer?
            if field.farmer != farmer:
                return Response(
                    {"error": "Du darfst nur in deinen eigenen Feldern Spuren hochladen"},
                    status=status.HTTP_403_FORBIDDEN
                )
        except FieldBoundary.DoesNotExist:
            return Response({"error": "Feldgrenze nicht gefunden."}, status=status.HTTP_404_NOT_FOUND)

        # Alte Spuren löschen
        ABTrace.objects.filter(field=field).delete()

        try:
            root = ET.parse(xml_file).getroot()
        except ET.ParseError as e:
            return Response({"error": f"XML Parse Error: {e}"}, status=status.HTTP_400_BAD_REQUEST)

        pfd = root.find(".//PFD")
        if pfd is None:
            return Response({"error": "Kein PFD-Element gefunden."}, status=status.HTTP_400_BAD_REQUEST)

        imported = 0
        for ggp in pfd.findall(".//GGP"):
            ggp_name = (ggp.get("B") or "").strip()
            for gpn in ggp.findall("./GPN"):
                gpn_type = gpn.get("B", "")
                if gpn_type.lower() != "singletrack":
                    continue
                for lsg in gpn.findall("./LSG"):
                    points = helperMethods.parse_points_from_lsg(lsg)
                    if points:
                        ABTrace.objects.create(
                            field=field,
                            trace_data={"name": ggp_name, "points": points},
                            distance_km=helperMethods.distance_km(points),
                            farmer=farmer,  # ← Farmer gesetzt
                        )
                        imported += 1

        return Response({"status": "success", "imported": imported}, status=status.HTTP_201_CREATED)
    
class RoleViewSet(viewsets.ModelViewSet):
        queryset = Role.objects.all()
        serializer_class = RoleSerializer
        permission_classes = [IsAdminUser]

# API/django_api/views.py - neuer Endpoint
@api_view(['POST'])
@permission_classes([AllowAny])
def keycloak_create_initialUserWithRealm(request):
    """
    Erstellt einen neuen Manufacturer(User) in Keycloak
    mit einer Hierarchie: Realm_{username} -> manufacturer (Subgroup)
    
    POST /api/keycloak/manufacturers/
    
    Erforderliche Parameter (JSON):
    {
        "username": "john.doe",
        "email": "john@example.com",
        "password": "SecurePassword123!",
        "first_name": "John",
        "last_name": "Doe"
    }
    """
    username = request.data.get("username")
    email = request.data.get("email")
    password = request.data.get("password")
    first_name = request.data.get("first_name", "")
    last_name = request.data.get("last_name", "")
    
    if not username or not email or not password:
        return Response(
            {"error": "username, email and password are required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try: #TODO: not safe for production!!! -> sub admin erstellen
        keycloak_admin = KeycloakAdmin(
            server_url=settings.KEYCLOAK_URL,
            client_id=settings.KEYCLOAK_CLIENT_ID,
            client_secret_key=settings.KEYCLOAK_CLIENT_SECRET,  
            realm_name=settings.KEYCLOAK_REALM,
            verify=False
        )
        
        # User erstellen
        user_data = {
            "username": username,
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "enabled": True,
            "credentials": [
                {
                    "type": "password",
                    "value": password,
                    "temporary": False
                }
            ],
        }
        
        user_id = keycloak_admin.create_user(user_data)
        
        # Parent Group erstellen: Realm_{username}
        parent_group_id = keycloak_admin.create_group({"name": f"Realm_{username}"})
        
        # Subgroup "manufacturer" unter Parent Group erstellen
        subgroup_url = f"{settings.KEYCLOAK_URL}/admin/realms/{settings.KEYCLOAK_REALM}/groups/{parent_group_id}/children"

        response = requests.post(
            subgroup_url,
            json={"name": "Manufacturer"},
            headers={"Authorization": f"Bearer {keycloak_admin.connection.token['access_token']}"},
            verify=False
        )

        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to create subgroup: {response.text}")

        # Die neue Gruppe-ID wird im Location Header zurückgegeben
        manufacturer_subgroup_id = response.headers.get('Location', '').split('/')[-1]

        if not manufacturer_subgroup_id:
            # Fallback: versuchen aus dem Response Body zu extrahieren
            try:
                manufacturer_subgroup_id = response.json().get('id')
            except:
                raise Exception("Could not extract subgroup ID from response")

        # User zu den Gruppen hinzufügen
        keycloak_admin.group_user_add(user_id, parent_group_id)
        #keycloak_admin.group_user_add(user_id, manufacturer_subgroup_id)

        # User zur Manufacturers Gruppe hinzufügen (falls noch benötigt)
        success, message = helperMethods.add_user_to_manufacturers_group(user_id)
        
        if not success:
            return Response(
                {"error": f"User erstellt, aber Gruppenzuweisung fehlgeschlagen: {message}"},
                status=status.HTTP_201_CREATED
            )
        
        return Response(
            {
                "status": "created",
                "user_id": user_id,
                "parent_group": f"Realm_{username}",
                "subgroup": "manufacturer",
                "message": message
            },
            status=status.HTTP_201_CREATED
        )
        
    except KeycloakGetError as e:
        return Response(
            {"error": f"Keycloak user creation failed: {e}"},
            status=status.HTTP_502_BAD_GATEWAY
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
def token_login(request):
    """
    Login mit Keycloak Credentials
    
    POST /api/login/
    {
        "username": "user@example.com",
        "password": "password123"
    }
    """
    username = request.data.get('username')
    password = request.data.get('password')
    
    if not username or not password:
        return Response(
            {"error": "username and password required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    decoded_token, error_msg = helperMethods.authenticate_user_from_credentials(username, password)
    
    if error_msg:
        status_code = status.HTTP_401_UNAUTHORIZED if error_msg == "Invalid credentials" else status.HTTP_403_FORBIDDEN
        return Response({"error": error_msg}, status=status_code)


    #TODO: checken ob der Farmer in "Krone" gemappt ist und gibt den Manufacturertoken zurück um den Manufactuer login zu haben und nicht den farmer login  Childgroups undso?
    
    # Token-Daten zurückgeben
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
    token_data = response.json()
    
    return Response(token_data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def create_farmers_keycloakToDjango(request):
    """
    Erstellt einen Farmer in Django basierend auf Keycloak-Authentifizierung
    
    POST /api/keycloak/farmers/
    
    Erforderliche Parameter (JSON):
    {
        "username": "john@example.com",
        "password": "password123"
    }
    """
    from API.django_api.models import Farmer
    
    username = request.data.get('username')
    password = request.data.get('password')
    
    if not username or not password:
        return Response(
            {"error": "username and password required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    decoded_token, error_msg = helperMethods.authenticate_user_from_credentials(username, password)
    
    if error_msg:
        status_code = status.HTTP_401_UNAUTHORIZED if error_msg == "Invalid credentials" else status.HTTP_403_FORBIDDEN
        return Response({"error": error_msg}, status=status_code)
    
    # Farmer erstellen/aktualisieren
    email = decoded_token.get('email')
    preferred_username = decoded_token.get('preferred_username')
    given_name = decoded_token.get('given_name', '')
    
    farmer, created = Farmer.objects.get_or_create(
        email=email,
        defaults={
            'name': f"{given_name}" if given_name else preferred_username
        }
    )
    
    return Response(
        {
            "status": "created" if created else "updated",
            "farmer_id": str(farmer.id),
            "farmer_name": farmer.name,
            "email": farmer.email,
            "message": f"Farmer {'created' if created else 'already exists'}"
        },
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )

@api_view(['POST'])
@permission_classes([IsAdminUser])
def add_user_to_group(request):
    """
    Fügt einen User einer Keycloak-Gruppe hinzu
    
    POST /api/keycloak/add-user-to-group/
    
    Erforderliche Parameter (JSON):
    {
        "user_id": "user-uuid",
        "group_name": "groupname"
    }
    """
    user_id = request.data.get("user_id")
    group_name = request.data.get("group_name")
    
    if not user_id or not group_name:
        return Response(
            {"error": "user_id and group_name are required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        keycloak_admin = KeycloakAdmin(
            server_url=settings.KEYCLOAK_URL,
            client_id=settings.KEYCLOAK_CLIENT_ID,
            client_secret_key=settings.KEYCLOAK_CLIENT_SECRET,
            realm_name=settings.KEYCLOAK_REALM,
            verify=False
        )
        
        # Gruppe nach Name finden
        groups = keycloak_admin.get_groups()
        group_id = None
        
        for group in groups:
            if group['name'] == group_name:
                group_id = group['id']
                break
        
        if not group_id:
            return Response(
                {"error": f"Group '{group_name}' not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        keycloak_admin.group_user_add(user_id, group_id)
        
        return Response(
            {
                "status": "success",
                "message": f"User {user_id} added to group {group_name}"
            },
            status=status.HTTP_200_OK
        )
        
    except KeycloakGetError as e:
        return Response(
            {"error": f"Keycloak error: {e}"},
            status=status.HTTP_502_BAD_GATEWAY
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

class DashboardView(TemplateView):
    template_name = 'html/mqtt_dashboard.html'



@api_view(['POST'])
@permission_classes([AllowAny])
def mqtt_message(request):
    """
    Endpoint zum Empfang von MQTT-Nachrichten
    
    POST /api/mqtt/
    
    Erforderliche Parameter (JSON):
    {
        "topic": "mqtt/topic",
        "payload": "test-payload: nothing to see here. go away.", 
        "qos": 1,
        "timestamp": "--:--:--",
        "metadata": "data-type: testdata"  
    }
    """
    topic = request.data.get('topic')
    payload = request.data.get('payload')
    qos = request.data.get('qos', 1)
    metadata =request.data.get('metadata', {})
    timestamp = request.data.get('timestamp')  
    
    # Validierung
    if not topic or payload is None:
        return Response(
            {"error": "topic and payload are required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # MQTT-Nachricht speichern (timestamp wird automatisch gesetzt)
        message = MQTTMessage.objects.create(
            topic=topic,
            payload=payload,
            qos=qos,
            timestamp=timestamp,
            metadata=metadata
        )
        
        print(f"Received MQTT message - Topic: {topic}, Payload: {payload}, QoS: {qos}")
        
        return Response({
            "status": "success",
            "message_id": str(message.id),
            "timestamp": message.timestamp
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def mqtt_getMessages(request):
    try:
        messages = MQTTMessage.objects.order_by('-timestamp')[:100]
        data = []
        for m in messages:
            data.append({
                "id": str(m.id),
                "topic": m.topic,
                "payload": m.payload,
                "qos": m.qos,
                "timestamp": m.timestamp.isoformat() if hasattr(m.timestamp, "isoformat") else m.timestamp,
                "metadata": m.metadata or {}
            })
        return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def mqtt_latest_timestamp(request):
    latest = MQTTMessage.objects.latest('timestamp')
    return Response({
        "timestamp": latest.timestamp.isoformat() if latest else None
    })


@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def mqtt_delete_all_messages(request):
    """
    Löscht alle MQTT-Nachrichten
    DELETE /api/mqtt-messages/
    """
    try:
        count, _ = MQTTMessage.objects.all().delete()
        return Response({
            "status": "success",
            "deleted_count": count
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def mqtt_delete_message(request, message_id):
    """
    Löscht eine einzelne MQTT-Nachricht
    DELETE /api/mqtt-messages/{message_id}/
    """
    try:
        message = MQTTMessage.objects.get(id=message_id)
        message.delete()
        return Response({
            "status": "success",
            "message": f"Message {message_id} deleted"
        }, status=status.HTTP_200_OK)
    except MQTTMessage.DoesNotExist:
        return Response(
            {"error": "Message not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

class SyncPartnerViewSet(viewsets.ModelViewSet):
    """
    API endpoint für SyncPartner
    """
    queryset = SyncPartner.objects.all()
    serializer_class = SyncPartnerSerializer
    permission_classes = [permissions.IsAuthenticated]



@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_manufacturers(request):
    """
    Gibt eine Liste aller Hersteller (Manufacturers) zurück
    GET /api/manufacturers/
    """
    try:
        keycloak_admin = KeycloakAdmin(
            server_url=settings.KEYCLOAK_URL,
            client_id=settings.KEYCLOAK_CLIENT_ID,
            client_secret_key=settings.KEYCLOAK_CLIENT_SECRET,
            realm_name=settings.KEYCLOAK_REALM,
            verify=False
        )
        
        groups = keycloak_admin.get_groups()
        manufacturers = [g for g in groups if g['name'] == 'Manufacturers']
        
        if not manufacturers:
            return Response(
                {"error": "Manufacturers group not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        manufacturer_group = manufacturers[0]
        members = keycloak_admin.get_group_members(manufacturer_group['id'])
        
        return Response(members, status=status.HTTP_200_OK)
        
    except KeycloakGetError as e:
        return Response(
            {"error": f"Keycloak error: {e}"},
            status=status.HTTP_502_BAD_GATEWAY
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['Post'])
def define_sync_partners(request):
    """
    Definiert Sync-Partner für die Daten-Synchronisation
    POST /api/syncpartners/
    
    Erforderliche Parameter (JSON) - Variante 1 (mehrere Manufacturer):
    {
        "farmer": "klaus@farmer.de",
        "usernames": ["Manufacturer X", "Manufacturer Y", "Manufacturer Z"]
    }
    
    Oder Variante 2 (einzelner Manufacturer):
    {
        "farmer": "klaus@farmer.de",
        "username": "Manufacturer X"
    }
    """
    from API.django_api.models import Farmer, Manufacturer
    
    farmer_email = request.data.get("farmer")
    usernames = request.data.get("usernames")  # Liste
    single_username = request.data.get("username")  # Einzelner String

    # Fallback: wenn usernames nicht gesetzt, single_username in Liste konvertieren
    if not usernames and single_username:
        usernames = [single_username]
    
    if not farmer_email or not usernames:
        return Response(
            {"error": "farmer and usernames/username are required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # usernames muss eine Liste sein
    if not isinstance(usernames, list):
        usernames = [usernames]
    
    try:
        # Farmer-Instanz anhand der Email suchen
        farmer = Farmer.objects.get(email=farmer_email)
        
        # SyncPartner für alle Manufacturer erstellen
        created_partners = []
        for username in usernames:
            if not username:  # Leere Strings überspringen
                continue
            
            # Manufacturer anhand des Namens suchen oder erstellen
            manufacturer, _ = Manufacturer.objects.get_or_create(name=username)
            
            # SyncPartner erstellen
            partner = SyncPartner.objects.create(
                farmer=farmer,
                manufacturer=manufacturer
            )
            created_partners.append(partner)
        
        if not created_partners:
            return Response(
                {"error": "No valid manufacturers provided"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Alle erstellten Partner serialisieren
        serializer = SyncPartnerSerializer(created_partners, many=True)
        return Response({
            "status": "success",
            "count": len(created_partners),
            "partners": serializer.data
        }, status=status.HTTP_201_CREATED)
        
    except Farmer.DoesNotExist:
        return Response(
            {"error": f"Farmer with email '{farmer_email}' not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAdminUser])
def add_subgroup(request):
    """
    Fügt eine Subgroup unter einer Parent-Gruppe hinzu
    
    POST /api/keycloak/add-subgroup/
    
    Erforderliche Parameter (JSON):
    {
        "parent_group_id": "group-uuid",
        "subgroup_name": "SubgroupName"
    }
    
    Oder alternativ mit Gruppennamen:
    {
        "parent_group_name": "GroupName",
        "subgroup_name": "SubgroupName"
    }
    """
    parent_group_id = request.data.get("parent_group_id")
    parent_group_name = request.data.get("parent_group_name")
    subgroup_name = request.data.get("subgroup_name")
    
    if not subgroup_name or (not parent_group_id and not parent_group_name):
        return Response(
            {"error": "subgroup_name and either parent_group_id or parent_group_name are required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        keycloak_admin = KeycloakAdmin(
            server_url=settings.KEYCLOAK_URL,
            client_id=settings.KEYCLOAK_CLIENT_ID,
            client_secret_key=settings.KEYCLOAK_CLIENT_SECRET,
            realm_name=settings.KEYCLOAK_REALM,
            verify=False
        )
        
        # Falls parent_group_name statt ID gegeben, ID ermitteln
        if not parent_group_id:
            groups = keycloak_admin.get_groups()
            for group in groups:
                if group['name'] == parent_group_name:
                    parent_group_id = group['id']
                    break
        
        if not parent_group_id:
            return Response(
                {"error": "Parent group not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Subgroup erstellen
        subgroup_url = f"{settings.KEYCLOAK_URL}/admin/realms/{settings.KEYCLOAK_REALM}/groups/{parent_group_id}/children"
        
        response = requests.post(
            subgroup_url,
            json={"name": subgroup_name},
            headers={"Authorization": f"Bearer {keycloak_admin.connection.token['access_token']}"},
            verify=False
        )
        
        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to create subgroup: {response.text}")
        
        subgroup_id = response.headers.get('Location', '').split('/')[-1]
        if not subgroup_id:
            try:
                subgroup_id = response.json().get('id')
            except:
                pass
        
        return Response(
            {
                "status": "success",
                "subgroup_id": subgroup_id,
                "subgroup_name": subgroup_name,
                "parent_group_id": parent_group_id
            },
            status=status.HTTP_201_CREATED
        )
        
    except KeycloakGetError as e:
        return Response(
            {"error": f"Keycloak error: {e}"},
            status=status.HTTP_502_BAD_GATEWAY
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_group_hierarchy(request):
    """
    Gibt die komplette Gruppen-Hierarchie zurück
    GET /api/keycloak/group-hierarchy/
    
    Optional: nach bestimmter Gruppe filtern:
    GET /api/keycloak/group-hierarchy/?parent_name=Realm_john.doe&subgroup_name=Manufacturer
    """
    parent_name = request.query_params.get('parent_name')
    subgroup_name = request.query_params.get('subgroup_name')
    
    try:
        keycloak_admin = KeycloakAdmin(
            server_url=settings.KEYCLOAK_URL,
            client_id=settings.KEYCLOAK_CLIENT_ID,
            client_secret_key=settings.KEYCLOAK_CLIENT_SECRET,
            realm_name=settings.KEYCLOAK_REALM,
            verify=False
        )
        
        groups = keycloak_admin.get_groups()
        
        # Wenn Filter gegeben, gezielt suchen
        if parent_name:
            for parent_group in groups:
                if parent_group['name'] == parent_name:
                    # Subgroups der Parent-Gruppe abrufen
                    subgroups = keycloak_admin.get_group_children(parent_group['id'])
                    
                    if subgroup_name:
                        # Nach spezifischer Subgroup suchen
                        for subgroup in subgroups:
                            if subgroup['name'] == subgroup_name:
                                return Response({
                                    "parent_group": {
                                        "id": parent_group['id'],
                                        "name": parent_group['name']
                                    },
                                    "subgroup": {
                                        "id": subgroup['id'],
                                        "name": subgroup['name']
                                    }
                                }, status=status.HTTP_200_OK)
                        
                        return Response(
                            {"error": f"Subgroup '{subgroup_name}' not found under '{parent_name}'"},
                            status=status.HTTP_404_NOT_FOUND
                        )
                    else:
                        # Alle Subgroups zurückgeben
                        return Response({
                            "parent_group": {
                                "id": parent_group['id'],
                                "name": parent_group['name']
                            },
                            "subgroups": subgroups
                        }, status=status.HTTP_200_OK)
            
            return Response(
                {"error": f"Parent group '{parent_name}' not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Keine Filter: komplette Hierarchie zurückgeben
        hierarchy = []
        for group in groups:
            subgroups = keycloak_admin.get_group_children(group['id'])
            hierarchy.append({
                "id": group['id'],
                "name": group['name'],
                "subgroups": subgroups
            })
        
        return Response(hierarchy, status=status.HTTP_200_OK)
        
    except KeycloakGetError as e:
        return Response(
            {"error": f"Keycloak error: {e}"},
            status=status.HTTP_502_BAD_GATEWAY
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )




