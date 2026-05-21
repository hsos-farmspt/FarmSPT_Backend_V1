from django.contrib import admin
from .models import FieldBoundary, ABTrace, Role, Farmer

@admin.register(Farmer)
class FarmerAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at', 'updated_at']

@admin.register(FieldBoundary)
class FieldBoundaryAdmin(admin.ModelAdmin):
    list_display = ['name', 'area_hectares', 'created_at']

@admin.register(ABTrace)
class ABTraceAdmin(admin.ModelAdmin):
    list_display = ['field', 'distance_km', 'created_at']

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']


