from django.db import models
import uuid

class Farmer (models.Model):
    """Datenbankmodell für die Speicherung von Informationen zu Eigentümern"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
            return self.name



class Role(models.Model):
    """Rollen für Zugriffskontrolle der Datenbank aus keycloak"""
    name = models.CharField(max_length=255)
    description = models.TextField()

    def __str__(self):
        return self.name
    
class Manufacturer(models.Model):
    """Datenbankmodell für die Speicherung von Informationen zu Herstellern"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True) 

    def __str__(self):
            return self.name

class SyncPartner(models.Model):
    """Datenbankmodell für die Speicherung von Informationen zu Synchronisationspartnern"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, null=True, blank=True)
    manufacturer = models.ForeignKey(Manufacturer, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)    
    role = models.ForeignKey(Role, on_delete=models.CASCADE, null=True, blank=True)  

    def __str__(self):
            return str(self.farmer)
  


class FieldData (models.Model):
        """Datenbankmodell für die Speicherung von Metadaten zur auswertung und zuordnung von Feldern"""
        farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, null=True, blank=True)
        syncPartner = models.ForeignKey(SyncPartner, on_delete=models.CASCADE)

        def __str__(self):
            return str(self.farmer)

class FieldBoundary(models.Model):
    """XML-Import für Feldgrenzen"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=255)
    coordinates = models.JSONField()  # z.B. [[lat, lng], ...]
    area_hectares = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, null=True, blank=True)
    syncpartners = models.ManyToManyField(SyncPartner,null=True, blank=True)

    def __str__(self):
        return self.name

class ABTrace(models.Model):
    """XML-Import für AB-Spuren"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    field = models.ForeignKey(FieldBoundary, on_delete=models.CASCADE)
    trace_data = models.JSONField()  # GPS-Spurdaten
    distance_km = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, null=True, blank=True)
    syncpartners = models.ManyToManyField(SyncPartner,null=True, blank=True)

    def __str__(self):
        return f"Trace for {self.field.name}"




class MQTTMessage(models.Model):
    topic = models.CharField(max_length=255)
    payload = models.JSONField()
    qos = models.IntegerField(default=1)
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(null=True, blank=True)  # Optionales Feld für zusätzliche Metadaten
    
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.topic}"









