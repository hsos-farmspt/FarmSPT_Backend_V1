from django.contrib.auth.models import User,Group
from rest_framework import serializers
from .models import FieldBoundary, ABTrace, Role, Farmer, Manufacturer, SyncPartner, FieldData

class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ["url", "username", "email", "groups"]

class GroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Group
        fields = ["url", "name"]

class FieldBoundarySerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldBoundary
        fields = ['id', 'name', 'coordinates', 'area_hectares', 'created_at']

class FieldBoundaryXMLUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    

class ABTraceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ABTrace
        fields = ['id', 'field', 'trace_data', 'distance_km', 'created_at']


class ABTraceXMLUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    field_id = serializers.UUIDField()


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name', 'description']

class FarmerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Farmer
        fields = ['id', 'name', 'email', 'created_at', 'updated_at']

class ManufacturerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Manufacturer
        fields = ['id', 'name', 'created_at', 'updated_at']

class RoleSerializerForSyncPartner(serializers.ModelSerializer):
    """Nested Serializer für Role in SyncPartner"""
    class Meta:
        model = Role
        fields = ['id', 'name']

class SyncPartnerSerializer(serializers.ModelSerializer):
    role = RoleSerializerForSyncPartner(read_only=True)
    farmer = FarmerSerializer(read_only=True)
    manufacturer = ManufacturerSerializer(read_only=True)
    
    class Meta:
        model = SyncPartner
        fields = ['id', 'farmer', 'manufacturer', 'role', 'created_at', 'updated_at']

class FieldDataSerializer(serializers.ModelSerializer):
    farmer = FarmerSerializer(read_only=True)
    syncPartner = SyncPartnerSerializer(read_only=True)
    
    class Meta:
        model = FieldData
        fields = ['id', 'farmer', 'syncPartner']




