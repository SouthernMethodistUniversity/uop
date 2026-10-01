import folium

# Lista de nodos EDC
edc_nodes = [
    {"id": "EDC_1_LCOL_TX", "name": "Las Colinas", "lat": 32.890918, "lon": -96.961279},
    {"id": "EDC_2_NPCR_TX", "name": "NorthPark Center", "lat": 32.871456, "lon": -96.774168},
    {"id": "EDC_3_DALL_TX", "name": "Dallas", "lat": 32.7767, "lon": -96.797},
    {"id": "EDC_4_TEPK_TX", "name": "Tietze Park", "lat": 32.82014275, "lon": -96.73361576},
    {"id": "EDC_5_IRVI_TX", "name": "Irving", "lat": 32.81583036, "lon": -96.95010695},
    {"id": "EDC_6_FAPK_TX", "name": "Fair Park", "lat": 32.778, "lon": -96.758},
    {"id": "EDC_7_OAKC_TX", "name": "Oak Cliff / Kiest", "lat": 32.723, "lon": -96.824},
    {"id": "EDC_8_LFLD_TX", "name": "Dallas Love Field", "lat": 32.843, "lon": -96.848},
    {"id": "EDC_9_WHRO_TX", "name": "White Rock Lake", "lat": 32.831, "lon": -96.715},
    {"id": "EDC_10_FBRN_TX", "name": "Farmers Branch", "lat": 32.924, "lon": -96.876}
]

# Crear mapa centrado en el área aproximada de DFW (OpenStreetMap por defecto)
m = folium.Map(location=[32.82, -96.83], zoom_start=11)

# Agregar marcadores
for node in edc_nodes:
    folium.Marker(
        location=[node['lat'], node['lon']],
        popup=f"<b>{node['name']}</b><br>{node['id']}",
        tooltip=node['name'],
        icon=folium.Icon(color="blue", icon="cloud")
    ).add_to(m)

# Guardar y visualizar
m.save("edc_topology_map.html")
print("Mapa guardado como 'edc_topology_map.html'. Ábrelo en tu navegador web.")
