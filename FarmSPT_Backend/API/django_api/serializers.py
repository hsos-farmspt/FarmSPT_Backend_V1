from django.contrib.auth.models import User,Group
from rest_framework import serializers
from .models import FieldBoundary, ABTrace, Role

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



    
