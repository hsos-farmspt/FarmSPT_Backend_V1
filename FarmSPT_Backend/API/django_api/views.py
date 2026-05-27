from django.contrib.auth.models import Group, User
from rest_framework import permissions, viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAdminUser, AllowAny
from API.django_api.serializers import ABTraceXMLUploadSerializer, FieldBoundaryXMLUploadSerializer, GroupSerializer, UserSerializer, FieldBoundarySerializer, ABTraceSerializer
from API.django_api.models import FieldBoundary, ABTrace
import xml.etree.ElementTree as ET
from .models import Role
from .serializers import RoleSerializer
from keycloak import KeycloakAdmin
from keycloak.exceptions import KeycloakGetError
import requests
from django.conf import settings
import jwt
from .authentication import helperMethods

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
                "traces_imported": traces_imported,  # ✅ Neu
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
def keycloak_create_manufacturer(request):
    """
    Erstellt einen neuen Manufacturer(User) in Keycloak
    und fügt ihn automatisch zur 'Manufacturers' Gruppe hinzu
    
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
        
        #TODO: hilfmethode einfügen die mit subadmin Manufactuer_receiver und manufactuer_produce Gruppen dynamisch erstellt und zuweist
        
        #receiver group erstellen
        receiver_group_id = keycloak_admin.create_group({"name": f"{username}_receiver"})
        #producer group erstellen
        producer_group_id = keycloak_admin.create_group({"name": f"{username}_producer"})

        # User zu den Gruppen hinzufügen
        keycloak_admin.group_user_add(user_id, receiver_group_id)
        keycloak_admin.group_user_add(user_id, producer_group_id)

        # User zur Manufacturers Gruppe hinzufügen
        success, message = helperMethods.add_user_to_manufacturers_group(user_id)
        
        if not success:
            return Response(
                {"error": f"User erstellt, aber Gruppenzuweisung fehlgeschlagen: {message}"},
                status=status.HTTP_201_CREATED  # User wurde trotzdem erstellt
            )
        
        return Response(
            {
                "status": "created",
                "user_id": user_id,
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
    
    try:
        # Token vom Keycloak anfordern
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
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        token_data = response.json()
        access_token = token_data.get('access_token')
        
        # JWT dekodieren (ohne Signatur-Validierung für dev/local)
        decoded_token = jwt.decode(access_token, options={"verify_signature": False})
        
        # Zugriff überprüfen MIT JWT-Daten
        is_allowed, error_message = helperMethods.check_user_access_allowed_from_jwt(decoded_token)
        
        if not is_allowed:
            return Response(
                {"error": error_message},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return Response(token_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
