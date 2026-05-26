import json
import xml.etree.ElementTree as ET

def xml_to_geojson(xml_file, output_file='data.geojson'):
    """Konvertiert TASKDATA XML zu GeoJSON"""
    tree = ET.parse(xml_file)
    root = tree.getroot()
    
    features = []
    
    # Feldgrenzen
    for pfd in root.findall('PFD'):
        field_name = pfd.get('C')
        for lsg in pfd.findall('.//PLN/LSG'):
            coords = []
            for pnt in lsg.findall('PNT'):
                lat = float(pnt.get('C'))
                lon = float(pnt.get('D'))
                coords.append([lon, lat])
            
            if coords:
                coords.append(coords[0])  # Polygon schließen
                features.append({
                    "type": "Feature",
                    "properties": {"name": f"Feldgrenze: {field_name}", "type": "boundary"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [coords]
                    }
                })
    
    # Fahrtspuren
    for pfd in root.findall('PFD'):
        field_name = pfd.get('C')
        for ggp in pfd.findall('GGP'):
            spur_name = ggp.get('B')
            for lsg in ggp.findall('.//LSG'):
                coords = []
                for pnt in lsg.findall('PNT'):
                    lat = float(pnt.get('C'))
                    lon = float(pnt.get('D'))
                    coords.append([lon, lat])
                
                if coords:
                    features.append({
                        "type": "Feature",
                        "properties": {
                            "name": f"{field_name} - {spur_name}",
                            "type": "trace",
                            "points": len(coords)
                        },
                        "geometry": {
                            "type": "LineString",
                            "coordinates": coords
                        }
                    })
    
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    with open(output_file, 'w') as f:
        json.dump(geojson, f, indent=2)
    
    print(f"✅ Generiert: {output_file}")

if __name__ == '__main__':
    xml_to_geojson('TASKDATA_12felder.XML')