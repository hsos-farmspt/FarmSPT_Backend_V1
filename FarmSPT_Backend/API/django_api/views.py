from django.shortcuts import render
from django.contrib.auth.models import Group, User
from rest_framework import permissions, viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAdminUser
from API.django_api.serializers import ABTraceXMLUploadSerializer, FieldBoundaryXMLUploadSerializer, GroupSerializer, UserSerializer, FieldBoundarySerializer, ABTraceSerializer
from API.django_api.models import FieldBoundary, ABTrace
import xml.etree.ElementTree as ET
import json
from math import radians, sin, cos, sqrt, atan2
from .models import Role, Policy
from .serializers import RoleSerializer, PolicySerializer


#helper method (made with claude )
def _parse_points_from_lsg(lsg_element):
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

#helper method (made with claude)
def _distance_km(points):
    if len(points) < 2:
        return 0.0

    r = 6371.0
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
    permission_classes = [permissions.AllowAny] #TODO Set to IsAuthenticated for production
    parser_classes = (MultiPartParser, FormParser)

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

        coordinates = _parse_points_from_lsg(boundary_lsg)

        field = FieldBoundary.objects.create(
            name=field_name,
            coordinates=coordinates,
            area_hectares=area_hectares,
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
                        points = _parse_points_from_lsg(lsg)
                        if points:  # Nur speichern wenn Punkte vorhanden
                            ABTrace.objects.create(
                                field=field,
                                trace_data={"name": ggp_name, "points": points},
                                distance_km=_distance_km(points),
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
    permission_classes = [permissions.AllowAny]  # TODO: Set to IsAuthenticated for production
    parser_classes = (MultiPartParser, FormParser)

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

        try:
            field = FieldBoundary.objects.get(id=field_id)
        except FieldBoundary.DoesNotExist:
            return Response({"error": "Feldgrenze nicht gefunden."}, status=status.HTTP_404_NOT_FOUND)

        # Alte Spuren für das Feld löschen!
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
                    points = _parse_points_from_lsg(lsg)
                    if points:
                        ABTrace.objects.create(
                            field=field,
                            trace_data={"name": ggp_name, "points": points},
                            distance_km=_distance_km(points),
                        )
                        imported += 1

        return Response({"status": "success", "imported": imported}, status=status.HTTP_201_CREATED)
    




class RoleViewSet(viewsets.ModelViewSet):
        queryset = Role.objects.all()
        serializer_class = RoleSerializer
        permission_classes = [IsAdminUser]

class PolicyViewSet(viewsets.ModelViewSet):
        queryset = Policy.objects.all()
        serializer_class = PolicySerializer
        permission_classes = [IsAdminUser]    