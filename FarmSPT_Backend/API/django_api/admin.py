from django.contrib import admin
from .models import FieldBoundary, ABTrace, MQTTMessage, Role, Farmer, SyncPartner, Manufacturer

@admin.register(Farmer)
class FarmerAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at', 'updated_at']

@admin.register(FieldBoundary)
class FieldBoundaryAdmin(admin.ModelAdmin):
    list_display = ['name', 'area_hectares', 'farmer', 'created_at']
    fieldsets = (
        ('Feld Informationen', {
            'fields': ('name', 'area_hectares', 'coordinates')
        }),
        ('Beziehungen', {
            'fields': ('farmer', 'syncpartners')
        }),
        ('Metadaten', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    filter_horizontal = ('syncpartners',)
    readonly_fields = ('created_at', 'updated_at')

@admin.register(ABTrace)
class ABTraceAdmin(admin.ModelAdmin):
    list_display = ['field', 'distance_km', 'farmer', 'created_at']
    fieldsets = (
        ('Spur Informationen', {
            'fields': ('field', 'trace_data', 'distance_km')
        }),
        ('Beziehungen', {
            'fields': ('farmer', 'syncpartners')
        }),
        ('Metadaten', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    filter_horizontal = ('syncpartners',)
    readonly_fields = ('created_at',)

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']

@admin.register(SyncPartner)
class SyncPartnerAdmin(admin.ModelAdmin):
    list_display = ['farmer', 'manufacturer', 'role', 'created_at']

@admin.register(Manufacturer)
class ManufacturerAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at', 'updated_at']

@admin.register(MQTTMessage)
class MQTTMessageAdmin(admin.ModelAdmin):
    list_display = ['topic', 'payload', 'timestamp']
    readonly_fields = ['topic', 'payload', 'timestamp']



