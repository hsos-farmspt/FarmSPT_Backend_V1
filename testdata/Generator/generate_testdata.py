#!/usr/bin/env python3
"""
Generator für realistische TASKDATA XML Testdaten
- Feldgrenzen: Unregelmäßige Formen in verschiedenen Ausrichtungen
- Fahrtspuren: Enge parallele Linien + Randspuren
- Random Größe, Form UND Rotation
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
import uuid
import random
import math

def rotate_point(lat, lon, center_lat, center_lon, angle_deg):
    """Rotiert einen Punkt um ein Zentrum um einen Winkel (in Grad)"""
    angle_rad = math.radians(angle_deg)
    
    # Zu Meter konvertieren (vereinfacht)
    dlat = (lat - center_lat) * 111000
    dlon = (lon - center_lon) * 111000 * math.cos(math.radians(center_lat))
    
    # Rotieren
    rotated_dlat = dlat * math.cos(angle_rad) - dlon * math.sin(angle_rad)
    rotated_dlon = dlat * math.sin(angle_rad) + dlon * math.cos(angle_rad)
    
    # Zurück zu Grad
    new_lat = center_lat + rotated_dlat / 111000
    new_lon = center_lon + rotated_dlon / (111000 * math.cos(math.radians(center_lat)))
    
    return new_lat, new_lon

def generate_realistic_taskdata(filename, num_fields=12):
    """Generiert realistische TASKDATA mit Rotation und mehr Random"""
    
    # Seed nur für Reproduzierbarkeit - kann auch entfernt werden für echte Randomisierung
    random.seed()
    
    root = ET.Element('ISO11783_TaskData')
    root.set('VersionMajor', '4')
    root.set('VersionMinor', '1')
    root.set('ManagementSoftwareManufacturer', 'FarmSPT')
    root.set('ManagementSoftwareVersion', 'v1.0')
    root.set('TaskControllerManufacturer', '')
    root.set('TaskControllerVersion', '')
    root.set('DataTransferOrigin', '1')
    
    # Kontakte
    contacts = [
        ('CTR-1', 'Müller', 'Hans'),
        ('CTR-2', 'Schmidt', 'Klaus'),
        ('CTR-3', 'Weber', 'Johann'),
        ('CTR-4', 'Fischer', 'Otto'),
    ]
    
    for ctr_id, name, firstname in contacts:
        ctr = ET.SubElement(root, 'CTR')
        ctr.set('A', ctr_id)
        ctr.set('B', name)
        ctr.set('C', firstname)
    
    # Felder mit realistischen Spuren
    for field_idx in range(num_fields):
        field_id = f"PFD-{field_idx + 1}"
        field_name = f"Feld {field_idx + 1}"
        
        # Randomisierte Basis-Koordinaten - MEHR Variation
        base_lat = random.uniform(49, 53)  # Latitude: 40-60
        base_lon = random.uniform(6, 9)    # Longitude: 4-8
        
        # **VIEL mehr Random bei Feldgröße**
        lat_delta = random.uniform(0.002, 0.015)  
        lon_delta = random.uniform(0.002, 0.015)  
        
        # **Random Rotation: 0-360°**
        rotation_angle = random.uniform(0, 360)
        
        # **Random Anzahl Spuren**
        num_traces = random.randint(7, 16)
        
        # Feldmittelpunkt (für Rotation)
        field_center_lat = base_lat + lat_delta / 2
        field_center_lon = base_lon + lon_delta / 2
        
        # **Feldgrenze - unregelmäßiger**
        boundary_coords = [
            [base_lat, base_lon],
            [base_lat + lat_delta * 0.25, base_lon + random.uniform(-0.0005, 0.0005)],
            [base_lat + lat_delta * 0.5, base_lon + random.uniform(-0.0005, 0.0005)],
            [base_lat + lat_delta * 0.75, base_lon + random.uniform(-0.0005, 0.0005)],
            [base_lat + lat_delta, base_lon],
            [base_lat + lat_delta + random.uniform(-0.0005, 0.0005), base_lon + lon_delta * 0.25],
            [base_lat + lat_delta + random.uniform(-0.0005, 0.0005), base_lon + lon_delta * 0.5],
            [base_lat + lat_delta + random.uniform(-0.0005, 0.0005), base_lon + lon_delta * 0.75],
            [base_lat + lat_delta, base_lon + lon_delta],
            [base_lat + lat_delta * 0.75, base_lon + lon_delta + random.uniform(-0.0005, 0.0005)],
            [base_lat + lat_delta * 0.5, base_lon + lon_delta + random.uniform(-0.0005, 0.0005)],
            [base_lat + lat_delta * 0.25, base_lon + lon_delta + random.uniform(-0.0005, 0.0005)],
            [base_lat, base_lon + lon_delta],
            [base_lat + random.uniform(-0.0005, 0.0005), base_lon + lon_delta * 0.75],
            [base_lat + random.uniform(-0.0005, 0.0005), base_lon + lon_delta * 0.5],
            [base_lat + random.uniform(-0.0005, 0.0005), base_lon + lon_delta * 0.25],
            [base_lat, base_lon],
        ]
        
        # Feldgrenzen rotieren
        rotated_boundary = [
            rotate_point(lat, lon, field_center_lat, field_center_lon, rotation_angle)
            for lat, lon in boundary_coords
        ]
        
        field_area = int(lat_delta * 111000 * lon_delta * 111000)
        
        # PFD Element
        pfd = ET.SubElement(root, 'PFD')
        pfd.set('A', field_id)
        pfd.set('B', str(uuid.uuid4())[:32])
        pfd.set('C', field_name)
        pfd.set('D', str(field_area))
        pfd.set('E', f"CTR-{(field_idx % 4) + 1}")
        
        # Feldgrenzen
        pln = ET.SubElement(pfd, 'PLN')
        pln.set('A', '1')
        
        lsg = ET.SubElement(pln, 'LSG')
        lsg.set('A', '1')
        
        for lat, lon in rotated_boundary:
            pnt = ET.SubElement(lsg, 'PNT')
            pnt.set('A', '2')
            pnt.set('C', f"{lat:.9f}")
            pnt.set('D', f"{lon:.9f}")
        
        # **Fahrtspuren: Parallele Linien in Rotation**
        spacing = math.sqrt(lat_delta**2 + lon_delta**2) / (num_traces + 2)
        
        for trace_idx in range(num_traces + 1):
            ggp_id = f"GGP-{field_idx * (num_traces + 1) + trace_idx + 1}"
            gpn_id = f"GPN-{field_idx * (num_traces + 1) + trace_idx + 1}"
            
            if trace_idx == 0:
                label = "Rand"
            else:
                label = f"Spur_{trace_idx}"
            
            # Einfache Spurberechnung:
            # 1. Berechne Spur als gerade Linie entlang der Feldlänge
            # 2. Positioniere die Spur über die Feldbreite verteilt
            # 3. Rotiere dann
            
            trace_coords = []
            num_points = random.randint(40, 70)
            
            # Relative Position der Spur (0 = linker Rand, 1 = rechter Rand)
            trace_position = trace_idx / (num_traces + 1)
            
            for point_idx in range(num_points):
                # Entlang der Feldlänge (progress: 0 bis 1)
                progress = point_idx / (num_points - 1)
                
                # Unrotierte Koordinaten (rechteck-basiert)
                unrot_lat = base_lat + lat_delta * progress
                unrot_lon = base_lon + lon_delta * trace_position
                
                # Rotiere um Feldmittelpunkt
                rot_lat, rot_lon = rotate_point(
                    unrot_lat, unrot_lon,
                    field_center_lat, field_center_lon,
                    rotation_angle
                )
                
                # Rauschen hinzufügen
                noise_lat = random.uniform(-0.000005, 0.000005)
                noise_lon = random.uniform(-0.000005, 0.000005)
                
                trace_coords.append((rot_lat + noise_lat, rot_lon + noise_lon))
            
            ggp = ET.SubElement(pfd, 'GGP')
            ggp.set('A', ggp_id)
            ggp.set('B', label)
            
            gpn = ET.SubElement(ggp, 'GPN')
            gpn.set('A', gpn_id)
            gpn.set('B', 'SingleTrack')
            gpn.set('C', '3')
            gpn.set('E', '4')
            gpn.set('F', '4')
            
            lsg_trace = ET.SubElement(gpn, 'LSG')
            lsg_trace.set('A', '5')
            
            for idx, (lat, lon) in enumerate(trace_coords):
                pnt = ET.SubElement(lsg_trace, 'PNT')
                pnt.set('A', '6' if idx == 0 else '8')
                pnt.set('C', f"{lat:.13f}")
                pnt.set('D', f"{lon:.13f}")
    
    # XML formatieren
    xml_string = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(xml_string)
    
    print(f"✅ Generiert: {filename} ({num_fields} Felder mit variablen Spuren und Rotationen)")

if __name__ == '__main__':
    generate_realistic_taskdata('TASKDATA_12felder.XML', num_fields=12)