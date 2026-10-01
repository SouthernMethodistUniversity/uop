"""
UPF Optimal Placer (UOP) - v2.0

File: services.py

Description:
Implements the core business logic, including network distance calculations, telemetry simulation, and multi-criteria ranking algorithms.

@authors: R. Rodriguez <raul.rodriguez@hcltech.com>, Y. Aldoori <yaseen.aldoori@windriver.com>, L. Popokh <leo.popokh@asato.ai>
@license: MIT
@copyright: Copyright (c) 2026 R. Rodriguez, Y. Aldoori, L. Popokh
"""

from __future__ import annotations

# Standard library imports
import os
import random
import math
from functools import lru_cache
from datetime import datetime
from typing import Dict, List, Optional, Union, Any

# Third-party libraries
import yaml
import folium
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from tabulate import tabulate
from loguru import logger
from openpyxl.styles import Font, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

# Local application imports
from database import execute_query, execute_single_query
from schemas import NodeBase, SiteBase, SiteDistanceResponse, PathCandidate

class ConfigManager:
    """
    Static manager to handle singleton-like access to the YAML configuration.
    """
    @staticmethod
    @lru_cache(maxsize=1)
    def get_config():
        with open("config.yaml", "r") as f:
            return yaml.safe_load(f)

class NetworkService:
    """
    Service layer for Network Devices using the full DDL mapping.
    """

    def get_enriched_nodes_for_visualization(self) -> List[dict]:
        """
        Fetches all nodes and enriches them with simulated telemetry data
        specifically formatted for map visualization.
        """
        raw_nodes = self.get_all_nodes()
        enriched = []
        for node in raw_nodes:
            n_data = node.model_dump()
            # Simulate and normalize telemetry
            sim = self.simulate_node_metrics(is_deployed=True)
            n_data['cpu'] = sim['cpu'] * 100.0 if sim['cpu'] < 1.0 else sim['cpu']
            n_data['ramava'] = sim['ram_ava'] * 100.0 if sim['ram_ava'] < 1.0 else sim['ram_ava']
            n_data['diskava'] = sim['disk_ava'] * 100.0 if sim['disk_ava'] < 1.0 else sim['disk_ava']
            n_data['iops'] = sim['iops']
            n_data['bw'] = sim['bw']
            # Normalize Role
            n_data['role'] = 'FEServer' if n_data.get('type') == 'FEDGE' else n_data.get('role')
            enriched.append(n_data)
        return enriched

    @staticmethod
    def calculate_haversine(lat1: float, lon1: float, lat2: float, lon2: float, unit: str = 'km') -> float:
        """
        Calculate the great-circle distance between two points on Earth.
        Supports both Kilometers and Miles.
        """
        # Earth radius constants
        R_KM = 6371.0
        R_MILES = 3958.8
        
        R = R_MILES if unit.lower() == 'miles' else R_KM
        
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        
        a = math.sin(dphi / 2)**2 + \
            math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
        
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c
        
        

# services.py

    @staticmethod
    def get_all_nodes() -> List[NodeBase]:
        """
        Retrieves nodes and formats telemetry to be EXACTLY like the original app.
        Example: 82.00, 19.00, and IOPS with commas.
        """
#        query = """
#            SELECT n.*, s.Location, s.ShortName, s.Latitude, s.Longitude
#            FROM Provisioned_Devices n
#            LEFT JOIN Sites s ON n.Site = s.ID
#        """

        query = """
            SELECT n.*, s.Location, s.ShortName, s.Latitude, s.Longitude
            FROM Provisioned_Devices n
            LEFT JOIN Sites s ON n.Site = s.ID
            WHERE 
                n.Region = 'DFW' 
                AND n.Status = 'Active' 
                AND (n.ID LIKE '%_UPF' OR n.ID LIKE '%_DU') 
                AND (n.Role = 'EdgeServer' OR n.Role = 'FEServer');
        """


        rows = execute_query(query)
        
        nodes = []
        for row in rows:
            node_data = {k.lower(): v for k, v in dict(row).items()}
            
            cnf_val = node_data.get('cnf')
            is_deployed = str(cnf_val) == '1' or str(cnf_val).lower() == 'yes'
            
            telemetry = NetworkService.simulate_node_metrics(is_deployed)
            
            # FORMATTING TO STRING WITH 2 DECIMALS
            # Example: 82 -> "82.00"
            node_data['cpu'] = "{:.2f}".format(float(telemetry['cpu']))
            node_data['ramava'] = "{:.2f}".format(float(telemetry['ram_ava']) * 100)
            node_data['diskava'] = "{:.2f}".format(float(telemetry['disk_ava']) * 100)
            
            # IOPS WITH THOUSANDS SEPARATOR
            # Example: 1226416 -> "1,226,416"
            node_data['iops'] = "{:,}".format(int(telemetry['iops']))
            
            # BANDWIDTH WITH 2 DECIMALS
            node_data['bw'] = "{:.2f}".format(float(telemetry['bw']))
            
            nodes.append(NodeBase(**node_data))
            
        return nodes

    @staticmethod
    def get_node_by_id(node_id: str) -> Optional[NodeBase]:
        """
        Fetch a specific device by its ID.
        """
        query = """
            SELECT 
                ID as id, Status as status, CNF as cnf, CPU as cpu, 
                RamAva as ram_ava, RamTot as ram_tot, DiskAva as disk_ava, 
                DiskTot as disk_tot, IOPS as iops, BW as bw, Site as site, 
                "Role" as role, Manufacturer as manufacturer, "Type" as type, 
                Cluster as cluster, Platform as platform, Description as description, 
                Region as region, LastRefresh as last_refresh
            FROM Provisioned_Devices 
            WHERE ID = ?
        """
        row = execute_single_query(query, (node_id,))
        return NodeBase(**dict(row)) if row else None
        

    @staticmethod
    def get_all_sites() -> List[SiteBase]:
        """
        Fetch all physical sites from the Sites table.
        """
        query = """
            SELECT 
                ID as id, "Type" as type, Status as status, Location as location, 
                ShortName as short_name, Region as region, Description as description, 
                Latitude as latitude, Longitude as longitude
            FROM Sites
        """
        rows = execute_query(query)
        return [SiteBase(**dict(row)) for row in rows]

    @staticmethod
    def get_site_by_id(site_id: str) -> Optional[SiteBase]:
        """
        Fetch a specific site by its ID.
        """
        query = 'SELECT * FROM Sites WHERE ID = ?'
        row = execute_single_query(query, (site_id,))
        # Quick manual mapping for column aliases if necessary
        if row:
            d = dict(row)
            return SiteBase(
                id=d["ID"], type=d["Type"], status=d["Status"],
                location=d["Location"], short_name=d["ShortName"],
                region=d["Region"], description=d["Description"],
                latitude=d["Latitude"], longitude=d["Longitude"]
            )
        return None        
        
        
    @staticmethod
    def get_nodes_by_site(site_id: str) -> List[NodeBase]:
        """
        Retrieve all devices located in a specific site.
        """
        query = """
            SELECT 
                ID as id, Status as status, CNF as cnf, CPU as cpu, 
                RamAva as ram_ava, RamTot as ram_tot, DiskAva as disk_ava, 
                DiskTot as disk_tot, IOPS as iops, BW as bw, Site as site, 
                "Role" as role, Manufacturer as manufacturer, "Type" as type, 
                Cluster as cluster, Platform as platform, Description as description, 
                Region as region, LastRefresh as last_refresh
            FROM Provisioned_Devices
            WHERE Site = ?
        """
        rows = execute_query(query, (site_id,))
        return [NodeBase(**dict(row)) for row in rows]
        


    @staticmethod
    def find_closest_sites(lat: float, lon: float, limit: int = 3) -> List[SiteDistanceResponse]:
        """
        Calculate distance from a given point to all sites and return the N closest.
        """
        all_sites = NetworkService.get_all_sites()
        sites_with_distance = []

        for site in all_sites:
            if site.latitude and site.longitude:
                dist = NetworkService.calculate_haversine(
                    lat, lon, site.latitude, site.longitude
                )
                
                # Create the response object with the distance
                site_data = site.model_dump()
                site_data["distance_km"] = round(dist, 2)
                sites_with_distance.append(SiteDistanceResponse(**site_data))

        # Sort by distance (ascending)
        sites_with_distance.sort(key=lambda x: x.distance_km)
        
        return sites_with_distance[:limit]



    @staticmethod
    def generate_network_map(top_path: dict = None, enriched_nodes: list = None, comparison_results: dict = None) -> str:
        """
        Generates an interactive HTML map with Sites, POIs, and dynamic telemetry overlays.
        Implements adaptive non-crossing Bezier path routing and embeds detailed hardware 
        performance indicators (CPU, RAM, Disk, IOPS, BW) within tooltips and popups.
        """
        config = ConfigManager.get_config()
        all_sites = NetworkService.get_all_sites()
        enriched_nodes = enriched_nodes or []
        
        # Index enriched metrics by site string identifier for O(1) cross-referencing lookups
        metrics_lookup = {node.get('site'): node for node in enriched_nodes if node.get('site')}
        
        # Initialize map with a fallback center
        m = folium.Map(location=[32.81, -96.81], zoom_start=12, control_scale=True)
        
        # Coords from central config
        smu_ref = config["smu_reference"]
        utsw_ref = config["network_anchors"]["utsw"]
        smu_coords = [smu_ref["lat"], smu_ref["lon"]]
        utsw_coords = [utsw_ref["latitude"], utsw_ref["longitude"]]
        
        fedge_winner_coords = None
        edge_winner_coords = None

        # Coords for comparison mode winners
        orig_fe_coords = None
        orig_ed_coords = None
        c3_fe_coords = None
        c3_ed_coords = None

        # Helper mathematical functions for Bezier and intersection checks
        def get_bezier_curve(p1, p2, curvature=0.15):
            mid_lat = (p1[0] + p2[0]) / 2
            mid_lon = (p1[1] + p2[1]) / 2
            delta_lat = p2[0] - p1[0]
            delta_lon = p2[1] - p1[1]
            control_lat = mid_lat - (delta_lon * curvature)
            control_lon = mid_lon + (delta_lat * curvature)
            
            curve_points = []
            for t in range(31):
                t_pct = t / 30.0
                one_minus_t = 1.0 - t_pct
                lat = (one_minus_t**2 * p1[0]) + (2 * one_minus_t * t_pct * control_lat) + (t_pct**2 * p2[0])
                lon = (one_minus_t**2 * p1[1]) + (2 * one_minus_t * t_pct * control_lon) + (t_pct**2 * p2[1])
                curve_points.append([lat, lon])
            return curve_points

        def segments_intersect(line1_p1, line1_p2, line2_p1, line2_p2):
            # Avoid detecting intersections at shared vertices/nodes (hop junctions or common sites)
            if line1_p1 == line2_p1 or line1_p1 == line2_p2 or \
               line1_p2 == line2_p1 or line1_p2 == line2_p2:
                return False
                
            def ccw(A, B, C):
                return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])
            
            return (ccw(line1_p1, line2_p1, line2_p2) != ccw(line1_p2, line2_p1, line2_p2) and
                    ccw(line1_p1, line1_p2, line2_p1) != ccw(line1_p1, line1_p2, line2_p2))

        def paths_cross(path1, path2):
            for i in range(len(path1) - 1):
                for j in range(len(path2) - 1):
                    if segments_intersect(path1[i], path1[i+1], path2[j], path2[j+1]):
                        return True
            return False

        # 1. RENDER INFRASTRUCTURE SITES WITH TELEMETRY METRICS
        for site in all_sites:
            if site.latitude and site.longitude:
                loc_name = site.location if site.location else "Unknown"
                node_type = site.type if site.type else "Unknown"
                
                # Fetch performance telemetry details for this specific hosting site location
                node_metrics = metrics_lookup.get(str(site.id))
                
                # Default strings if telemetry is missing
                cpu_str = f"{node_metrics['cpu']:.2f}%" if node_metrics else "N/A"
                ram_str = f"{node_metrics['ramava']:.2f}%" if node_metrics else "N/A"
                disk_str = f"{node_metrics['diskava']:.2f}%" if node_metrics else "N/A"
                iops_str = f"{node_metrics['iops']:,}" if node_metrics else "N/A"
                bw_str = f"{node_metrics['bw']:.2f} Gbps" if node_metrics else "N/A"
                
                # Build the enriched multi-line hover tooltip text
                custom_tooltip = (
                    f"Site: {site.id} ({loc_name} | {node_type})<br>"
                    f"---------------------------<br>"
                    f"CPU Usage: {cpu_str}<br>"
                    f"RAM Free: {ram_str}<br>"
                    f"Disk Free: {disk_str}<br>"
                    f"IOPS Performance: {iops_str}<br>"
                    f"Bandwidth Capacity: {bw_str}"
                )
                
                # Build the persistent interactive click Popup HTML window
                popup_text = (
                    f"<b>Site ID:</b> {site.id}<br>"
                    f"<b>Status:</b> {site.status}<br>"
                    f"<b>Type:</b> {node_type}<br>"
                    f"<hr style='margin: 8px 0;'>"
                    f"<b>📊 Node Telemetry Diagnostics:</b><br>"
                    f"• CPU Utilization: <span style='color:#2563EB;'>{cpu_str}</span><br>"
                    f"• Available Memory: <span style='color:#2563EB;'>{ram_str}</span><br>"
                    f"• Available Storage: <span style='color:#2563EB;'>{disk_str}</span><br>"
                    f"• Disk Throughput: <span style='color:#2563EB;'>{iops_str} IOPS</span><br>"
                    f"• Current Bandwidth: <span style='color:#2563EB;'>{bw_str}</span>"
                )

                # Check for winners in comparison mode
                if comparison_results:
                    orig_best = comparison_results.get("original_best", {})
                    c3_best = comparison_results.get("c3_best", {})
                    
                    is_orig_fe = str(site.id) == str(orig_best.get("fedge"))
                    is_orig_ed = str(site.id) == str(orig_best.get("edge"))
                    is_c3_fe = str(site.id) == str(c3_best.get("fedge"))
                    is_c3_ed = str(site.id) == str(c3_best.get("edge"))
                    
                    if is_orig_fe: orig_fe_coords = [site.latitude, site.longitude]
                    if is_orig_ed: orig_ed_coords = [site.latitude, site.longitude]
                    if is_c3_fe: c3_fe_coords = [site.latitude, site.longitude]
                    if is_c3_ed: c3_ed_coords = [site.latitude, site.longitude]
                    
                    if is_orig_fe or is_orig_ed:
                        popup_text += "<br><br><span style='color:#1D4ED8;'><b>🏆 [Original Algorithm Winner]</b></span>"
                    if is_c3_fe or is_c3_ed:
                        popup_text += "<br><br><span style='color:#DC2626;'><b>🏆 [C3-Pareto-TOPSIS Winner]</b></span>"
                    
                    if (is_orig_fe and is_c3_fe) or (is_orig_ed and is_c3_ed):
                        popup_text += "<br><span style='color:#10B981;'><b>(Shared Selection)</b></span>"
                
                if top_path:
                    if node_type == 'FEDGE':
                        if (str(site.id) == str(top_path.get("fedge_site")) or 
                            (top_path.get("path_id") and str(site.id) in top_path["path_id"])):
                            fedge_winner_coords = [site.latitude, site.longitude]
                            popup_text += "<br><br><span style='color:#EF4444;'><b>🏆 [Winning FEDGE Node Segment]</b></span>"
                    
                    if node_type == 'EDGE':
                        if (str(site.id) == str(top_path.get("edge_site")) or 
                            (top_path.get("path_id") and str(site.id) in top_path["path_id"])):
                            edge_winner_coords = [site.latitude, site.longitude]
                            popup_text += "<br><br><span style='color:#EF4444;'><b>🏆 [Winning EDGE Node Segment]</b></span>"

                if node_type == 'CORE':
                    icon = folium.Icon(icon='cubes', prefix='fa', color='darkblue')
                elif node_type == 'EDGE':
                    icon = folium.Icon(icon='cloud', prefix='fa', color='purple')
                elif node_type == 'FEDGE':
                    icon_file = 'images/logo.png'
                    icon = folium.features.CustomIcon(icon_image=icon_file, icon_size=(29, 37))
                else:
                    icon = folium.Icon(icon='signal', prefix='fa', color='orange')

                folium.Marker(
                    location=[site.latitude, site.longitude],
                    popup=folium.Popup(popup_text, max_width=320),
                    tooltip=folium.Tooltip(custom_tooltip, sticky=True),
                    icon=icon
                ).add_to(m)

        # 2. ADD KEY LANDMARK POIs
        folium.Marker(location=smu_coords, tooltip="SMU Dallas Campus", icon=folium.Icon(icon='mortar-board', prefix='fa', color='blue')).add_to(m)
        folium.Marker(location=utsw_coords, tooltip="UTSW Medical Center Dallas", icon=folium.Icon(icon='medkit', prefix='fa', color='green')).add_to(m)

        # Inject JavaScript to handle hierarchy logic in the LayerControl.
        # This allows algorithm (parent) selection to synchronize with its Hops (children).
        js_sync = """
        <script>
        function setupLayerHierarchy() {
            var overlays = document.querySelector('.leaflet-control-layers-overlays');
            if (!overlays) {
                setTimeout(setupLayerHierarchy, 500);
                return;
            }
            function bindHierarchy(masterName) {
                var labels = Array.from(overlays.querySelectorAll('label'));
                var masterLabel = labels.find(l => l.textContent.includes(masterName));
                if (!masterLabel) return;

                var masterCheck = masterLabel.querySelector('input');
                var slaves = [];
                var startIndex = labels.indexOf(masterLabel);

                for (var i = startIndex + 1; i < labels.length; i++) {
                    var txt = labels[i].textContent.trim();
                    # Children are identified by the hierarchy symbol '└─'
                    if (txt.includes('└─')) {
                        slaves.push(labels[i].querySelector('input'));
                    } else {
                        break;
                    }
                }

                masterCheck.addEventListener('change', function() {
                    var state = this.checked;
                    slaves.forEach(s => {
                        if (s.checked !== state) s.click();
                    });
                });
            }
            bindHierarchy('Original Algorithm');
            bindHierarchy('C3-Pareto-TOPSIS');
        }
        window.onload = setupLayerHierarchy;
        </script>
        """
        m.get_root().html.add_child(folium.Element(js_sync))

        def draw_full_path(parent_group, start, fe, edge, end, colors, label, curvature_offset=0, existing_curves=None, hop_names=None):
            """
            Draws a 3-hop trajectory iteratively resolving curvature collisions
            to prevent lines from crossing each other or existing paths.
            """
            # Deterministic RNG based on coordinates to ensure identical paths overlap perfectly
            seed_str = f"{start}{fe}{edge}{end}"
            local_rng = random.Random(seed_str)
            
            existing_curves = existing_curves or []
            opts = [0.12, 0.18, -0.12, 0.25, -0.25, 0.35, -0.35, 0.05, -0.05, 0.45, -0.45, 0.60, -0.60]
            
            c1, c2, c3 = 0.12 + curvature_offset, 0.18 + curvature_offset, -0.12 + curvature_offset
            
            h1 = get_bezier_curve(start, fe, curvature=c1)
            h2 = get_bezier_curve(fe, edge, curvature=c2)
            h3 = get_bezier_curve(edge, end, curvature=c3)
            
            # Resolution loop: Adapt curvatures until no crossings occur
            for _ in range(40): 
                current = [h1, h2, h3]
                # Verify internal and external crossings
                if (paths_cross(h1, h2) or paths_cross(h2, h3) or paths_cross(h1, h3) or
                    any(paths_cross(hc, ec) for hc in current for ec in existing_curves)):
                    c1, c2, c3 = [local_rng.choice(opts) + curvature_offset for _ in range(3)]
                    h1, h2, h3 = get_bezier_curve(start, fe, c1), get_bezier_curve(fe, edge, c2), get_bezier_curve(edge, end, c3)
                else:
                    break

            path_colors = [colors]*3 if isinstance(colors, str) else colors

            # If site names are provided, we create subgroups for each hop (individual checkboxes)
            # We use a visual prefix to indicate hierarchy in the menu
            if hop_names and len(hop_names) == 4:
                indent = "&nbsp;&nbsp;&nbsp;└─ "
                hops_meta = [
                    (h1, f"{indent}{hop_names[0]} → {hop_names[1]}", path_colors[0]),
                    (h2, f"{indent}{hop_names[1]} → {hop_names[2]}", path_colors[1]),
                    (h3, f"{indent}{hop_names[2]} → {hop_names[3]}", path_colors[2])
                ]
                for curve, h_label, h_color in hops_meta:
                    # We add a hidden span with the algorithm label to ensure the name is unique for Folium's LayerControl.
                    # This prevents segments with the same site names from being merged in the UI menu.
                    fg_hop = folium.FeatureGroup(name=f"{h_label}<span style='display:none;'>_{label}</span>", show=True)
                    folium.PolyLine(locations=curve, color=h_color, weight=6, opacity=0.9, dash_array='8, 8', tooltip=f"{label}: {h_label}").add_to(fg_hop)
                    # Add DIRECTLY to the base map so it is visible in the LayerControl
                    fg_hop.add_to(m)
            else:
                # Direct drawing to the parent group
                folium.PolyLine(locations=h1, color=path_colors[0], weight=6, opacity=0.9, dash_array='8, 8', tooltip=f"{label}: Hop 1").add_to(parent_group)
                folium.PolyLine(locations=h2, color=path_colors[1], weight=6, opacity=0.9, dash_array='8, 8', tooltip=f"{label}: Hop 2").add_to(parent_group)
                folium.PolyLine(locations=h3, color=path_colors[2], weight=6, opacity=0.9, dash_array='8, 8', tooltip=f"{label}: Hop 3").add_to(parent_group)

            return [h1, h2, h3]
        
        # 3. SOLVE AND DRAW ADAPTIVE NON-CROSSING OVERLAYS
        all_bounds = [smu_coords, utsw_coords]

        if comparison_results and orig_fe_coords and orig_ed_coords and c3_fe_coords and c3_ed_coords:
            orig_best = comparison_results.get("original_best", {})
            c3_best = comparison_results.get("c3_best", {})
            
            # Check if both algorithms chose the exact same path
            is_same_path = (str(orig_best.get("fedge")) == str(c3_best.get("fedge")) and 
                            str(orig_best.get("edge")) == str(c3_best.get("edge")))

            # Initialize groups with multi-line English labels and path info
            same_msg = "<br><span style='color:green; font-weight:bold;'>Same result both cases!</span>" if is_same_path else ""

            # 1. Create and add MASTER groups first so they appear at the top of the legend
            fg_orig = folium.FeatureGroup(name=f"Original Algorithm (Blue)<br>Path: {orig_best.get('fedge')} → {orig_best.get('edge')}{same_msg}", show=True)
            fg_orig.add_to(m)
            
            # 2. Draw the hops (they will be added to 'm' automatically inside draw_full_path)
            orig_hops = ["SMU", orig_best.get('fedge'), orig_best.get('edge'), "UTSW"]
            p1_coords = draw_full_path(fg_orig, smu_coords, orig_fe_coords, orig_ed_coords, utsw_coords, '#1D4ED8', 'Original', 0, hop_names=orig_hops)
            
            # 3. Perform the same logic for the C3 algorithm
            fg_c3 = folium.FeatureGroup(name=f"C3-Pareto-TOPSIS (Red)<br>Path: {c3_best.get('fedge')} → {c3_best.get('edge')}{same_msg}", show=True)
            fg_c3.add_to(m)
            
            c3_offset = 0 if is_same_path else 0.20
            c3_avoid = None if is_same_path else p1_coords
            c3_hops = ["SMU", c3_best.get('fedge'), c3_best.get('edge'), "UTSW"]
            
            draw_full_path(fg_c3, smu_coords, c3_fe_coords, c3_ed_coords, utsw_coords, '#DC2626', 'C3-TOPSIS', c3_offset, existing_curves=c3_avoid, hop_names=c3_hops)
            
            # Add layer control (checkbox menu)
            # 'collapsed=False' keeps the menu expanded by default
            folium.LayerControl(position='topright', collapsed=False).add_to(m)

            all_bounds.extend([smu_coords, orig_fe_coords, orig_ed_coords, c3_fe_coords, c3_ed_coords, utsw_coords])
            m.fit_bounds(all_bounds, padding=(30, 30))
            logger.info("Comparison map rendered with isolated trajectories for both algorithms.")

        elif top_path and fedge_winner_coords and edge_winner_coords:
            # Apply hierarchy to single algorithm mode for consistency
            fg_winner = folium.FeatureGroup(name=f"Winning Path<br>Path: {top_path.get('fedge_site')} → {top_path.get('edge_site')}", show=True)
            fg_winner.add_to(m)
            
            top_hops = ["SMU", top_path.get('fedge_site'), top_path.get('edge_site'), "UTSW"]
            draw_full_path(fg_winner, smu_coords, fedge_winner_coords, edge_winner_coords, utsw_coords,
                           ['#1D4ED8', '#E63946', '#10B981'], 'Path', 0, hop_names=top_hops)
            
            folium.LayerControl(position='topright', collapsed=False).add_to(m)
            
            # 4. DYNAMIC VIEWPORT BOUNDS ADJUSTMENT
            path_bounds = [smu_coords, fedge_winner_coords, edge_winner_coords, utsw_coords]
            m.fit_bounds(path_bounds, padding=(30, 30))
            
            #loguru.logger.info("Comprehensive triple-hop intersection validation completed. Trajectories are isolated.")
            logger.info("Comprehensive triple-hop intersection validation completed. Trajectories are isolated.")
        else:
            #loguru.logger.warning("Could not resolve coordinate maps for dynamic viewport bounding box adjustment.")
            logger.warning("Could not resolve coordinate maps for dynamic viewport bounding box adjustment.")

        map_path = config["paths"]["map_output"]
        m.save(map_path)
        return map_path
 
    @staticmethod
    def _load_config() -> Dict:
        """
        Loads simulation thresholds from the YAML config file.
        """
        return ConfigManager.get_config()


    @staticmethod
    def simulate_node_metrics(is_deployed: bool) -> Dict:
        """
        Generates random telemetry data with floating point precision.
        Uses random.uniform to ensure we get realistic decimal noise 
        instead of flat integers.
        """
        conf = NetworkService._load_config()["simulation"]
        state = "deployed" if is_deployed else "not_deployed"

        # random.uniform(a, b) returns a random floating point number N 
        # such that a <= N <= b.
        return {
            "cpu": random.uniform(conf["cpu"][state]["min"], conf["cpu"][state]["max"]),
            "ram_ava": random.uniform(conf["memory"][state]["min"], conf["memory"][state]["max"]),
            "disk_ava": random.uniform(conf["disk"][state]["min"], conf["disk"][state]["max"]),
            "iops": random.randint(conf["performance"]["iops"]["min"], conf["performance"]["iops"]["max"]),
            "bw": random.uniform(conf["performance"]["bw_gbps"]["min"], conf["performance"]["bw_gbps"]["max"])
        }


class PlacementService:
    
    @staticmethod
    def algorithm_original(nodes: List[Any],num_of_sim: int) -> tuple[List[Dict], List[List[Any]], List[str], str]:
        """
        Calculates end-to-end path scores (FEServer + EdgeServer) with full matrix debug tracing.
        Exports results to a stylized Excel sheet with 4 tabs, including deep latency hop audits.
        Roadmap: SMU Campus -> FEServer (Microwave) -> EdgeServer (Fiber) -> UTSW Medical Center
        """
        config = ConfigManager.get_config()
        w = config["scoring_weights"]
        
        # Fixed geo-coordinates from config
        smu_ref = config["smu_reference"]
        utsw_ref = config["network_anchors"]["utsw"]
        smu_coords = (smu_ref["lat"], smu_ref["lon"])
        utsw_coords = (utsw_ref["latitude"], utsw_ref["longitude"])
        
        # Latency factors from config
        lat_f_micro = config["latency_factors"]["fedge_microwave"]
        lat_f_fiber = config["latency_factors"]["edge_fiber"]
        
        # 1. Data Preparation
        nodes_dict = []
        for n in nodes:
            if hasattr(n, "model_dump"): nodes_dict.append(n.model_dump())
            elif hasattr(n, "dict"): nodes_dict.append(n.dict())
            else: nodes_dict.append(n)

        def fmt_iops(val):
            raw = str(val or '0').replace(',', '')
            try: return int(float(raw))
            except: return 0

        def fmt_dec(val):
            try: return f"{float(val):.2f}"
            except: return "0.00"

        # --- CLI INPUT DATA ---
        # --- CLI INPUT DATA LOGGING ---
        headers_in = ["Region", "Site", "Device UUID", "Status", "Role", "CNF", "CPU Usage %", "RAM free %", "Disk free %", "IOPS", "Bandwidth (Gbps)", "Manufacturer", "Platform", "Cluster", "Location", "ShortName", "Type", "Latitude", "Longitude"]
        table_in = []
        for n in nodes_dict:
            table_in.append([
                n.get('region', 'DFW'), n.get('site', 'N/A'), n.get('id', n.get('ID')),
                n.get('status', 'Active'), n.get('role', n.get('Role')), n.get('cnf', 1),
                fmt_dec(n.get('cpu')), fmt_dec(n.get('ramava')), fmt_dec(n.get('diskava')), f"{fmt_iops(n.get('iops')):,}",
                fmt_dec(n.get('bw')), n.get('manufacturer'), n.get('platform'), n.get('cluster'),
                n.get('location'), n.get('shortname'), n.get('type'), fmt_dec(n.get('latitude')), fmt_dec(n.get('longitude'))
            ])
        
        print("\n--- INPUT DATA ---")
        print(tabulate(table_in, headers=headers_in, tablefmt="fancy_grid"))
        print("-" * 50)

        fedge_candidates = [n for n in nodes_dict if str(n.get('role') or n.get('Role') or '').strip().lower() == 'feserver']
        edge_candidates = [n for n in nodes_dict if str(n.get('role') or n.get('Role') or '').strip() == 'EdgeServer']

        if not fedge_candidates or not edge_candidates:
            logger.warning("Missing required FEServer or EdgeServer nodes to compute combined paths.")
            return []

        # 2. Build Path Combinations & Apply Bottleneck Principles
        path_candidates = []
        node_site_lookup = {}

        for fedge in fedge_candidates:
            fe_id = fedge.get('id') or fedge.get('ID')
            fe_lat = float(fedge.get('latitude') or 0)
            fe_lon = float(fedge.get('longitude') or 0)
            node_site_lookup[fe_id] = fedge.get('site', 'N/A')
            
            for edge in edge_candidates:
                ed_id = edge.get('id') or edge.get('ID')
                ed_lat = float(edge.get('latitude') or 0)
                ed_lon = float(edge.get('longitude') or 0)
                node_site_lookup[ed_id] = edge.get('site', 'N/A')
                
                path_id = f"{fe_id} + {ed_id}"
                
                # Geodetic calculations per hop
                d1 = NetworkService.calculate_haversine(smu_coords[0], smu_coords[1], fe_lat, fe_lon, unit='miles')
                lat1 = d1 * lat_f_micro
                
                d2 = NetworkService.calculate_haversine(fe_lat, fe_lon, ed_lat, ed_lon, unit='miles')
                lat2 = d2 * lat_f_fiber
                
                d3 = NetworkService.calculate_haversine(ed_lat, ed_lon, utsw_coords[0], utsw_coords[1], unit='miles')
                lat3 = d3 * lat_f_fiber
                
                total_lat = round(lat1 + lat2 + lat3, 3)
                total_dist = round(d1 + d2 + d3, 3)
                
                # Raw node parameters for auditing
                fe_cpu, ed_cpu = float(fedge.get('cpu') or 0), float(edge.get('cpu') or 0)
                fe_ram, ed_ram = float(fedge.get('ramava') or 0), float(edge.get('ramava') or 0)
                fe_disk, ed_disk = float(fedge.get('diskava') or 0), float(edge.get('diskava') or 0)
                fe_iops, ed_iops = fmt_iops(fedge.get('iops')), fmt_iops(edge.get('iops'))
                fe_bw, ed_bw = float(fedge.get('bw') or 0), float(edge.get('bw') or 0)

                # Bottleneck consolidation
                path_cpu = max(fe_cpu, ed_cpu)
                path_ram = min(fe_ram, ed_ram)
                path_disk = min(fe_disk, ed_disk)
                path_iops = min(fe_iops, ed_iops)
                path_bw = min(fe_bw, ed_bw)
                
                path_candidates.append({
                    'path_id': path_id, 'fedge': fedge, 'edge': edge,
                    'fe_cpu': fe_cpu, 'ed_cpu': ed_cpu, 'cpu': path_cpu,
                    'fe_ram': fe_ram, 'ed_ram': ed_ram, 'ramava': path_ram,
                    'fe_disk': fe_disk, 'ed_disk': ed_disk, 'diskava': path_disk,
                    'fe_iops': fe_iops, 'ed_iops': ed_iops, 'iops': path_iops,
                    'fe_bw': fe_bw, 'ed_bw': ed_bw, 'bw': path_bw,
                    'd1': round(d1, 3), 'd2': round(d2, 3), 'd3': round(d3, 3),
                    'lat1': round(lat1, 3), 'lat2': round(lat2, 3), 'lat3': round(lat3, 3),
                    '_lat_val': total_lat, '_dist_mi': total_dist
                })

        # 3. Path Score Calculations and Matrix Tracing
        results_for_table = []
        results_details = []
        final_results = []

        for target in path_candidates:
            p_id = target['path_id']
            stats = {'cpu': [], 'ram': [], 'disk': [], 'iops': [], 'bw': [], 'lat': []}
            
            for comp in path_candidates:
                if p_id == comp['path_id']: continue
                
                stats['cpu'].append(1 if target['cpu'] < comp['cpu'] else -1)
                stats['ram'].append(1 if target['ramava'] > comp['ramava'] else -1)
                stats['disk'].append(1 if target['diskava'] > comp['diskava'] else -1)
                stats['bw'].append(1 if target['bw'] > comp['bw'] else -1)
                stats['lat'].append(1 if target['_lat_val'] < comp['_lat_val'] else -1)
                stats['iops'].append(1 if target['iops'] > comp['iops'] else -1)

            # --- RESTORED LOGS ---
            # --- SCORING LOGS ---
            logger.debug(f"Calculating score for device {p_id} with cpu_usage {target['cpu']}")
            sum_cpu = sum(stats['cpu'])
            logger.debug(f"Device {p_id} - Corrected: {' + '.join(map(str, stats['cpu']))} = {sum_cpu}")
            logger.debug(f"    Weight value for CPU: {w['cpu']}")
            s_cpu = round(sum_cpu * w['cpu'], 3)
            logger.debug(f"    {sum_cpu} * {w['cpu']} = {s_cpu}")
            logger.debug(f"Device {p_id} - cpu_score calculated: {s_cpu}")

            logger.debug(f"Calculating score for device {p_id} with ramfree_value {target['ramava']}")
            sum_ram = sum(stats['ram'])
            logger.debug(f"Device {p_id} - Corrected: {' + '.join(map(str, stats['ram']))} = {sum_ram}")
            logger.debug(f"    Weight value for RAM: {w['ram']}")
            s_ram = round(sum_ram * w['ram'], 3)
            logger.debug(f"    {sum_ram} * {w['ram']} = {s_ram}")
            logger.debug(f"Device {p_id} - ramfree_value calculated: {s_ram}")

            logger.debug(f"Calculating score for device {p_id} with diskfree_value {target['diskava']}")
            sum_disk = sum(stats['disk'])
            logger.debug(f"Device {p_id} - Corrected: {' + '.join(map(str, stats['disk']))} = {sum_disk}")
            logger.debug(f"    Weight value for Disk: {w['disk']}")
            s_disk = round(sum_disk * w['disk'], 3)
            logger.debug(f"    {sum_disk} * {w['disk']} = {s_disk}")
            logger.debug(f"Device {p_id} - diskfree_value calculated: {s_disk}")

            logger.debug(f"Calculating score for device {p_id} with iops_value {target['iops']}")
            sum_iops = sum(stats['iops'])
            logger.debug(f"Device {p_id} - Corrected: {' + '.join(map(str, stats['iops']))} = {sum_iops}")
            logger.debug(f"    Weight value for IOPS: {w['iops']}")
            s_iops = round(sum_iops * w['iops'], 3)
            logger.debug(f"    {sum_iops} * {w['iops']} = {s_iops}")
            logger.debug(f"Device {p_id} - iops_value calculated: {s_iops}")

            logger.debug(f"Calculating score for device {p_id} with bw_value {target['bw']}")
            sum_bw = sum(stats['bw'])
            logger.debug(f"Device {p_id} - Corrected: {' + '.join(map(str, stats['bw']))} = {sum_bw}")
            logger.debug(f"    Weight value for Bandwidth: {w['bw']}")
            s_bw = round(sum_bw * w['bw'], 3)
            logger.debug(f"    {sum_bw} * {w['bw']} = {s_bw}")
            logger.debug(f"Device {p_id} - bw_value calculated: {s_bw}")

            logger.debug(f"Calculating score for device {p_id} with latency {target['_lat_val']}")
            sum_lat = sum(stats['lat'])
            logger.debug(f"Device {p_id} - Corrected: {' + '.join(map(str, stats['lat']))} = {sum_lat}")
            logger.debug(f"    Weight value for CPU: {w['latency']}")
            s_lat = round(sum_lat * w['latency'], 3)
            logger.debug(f"    {sum_lat} * {w['latency']} = {s_lat}")
            logger.debug(f"Device {p_id} - latency calculated: {s_lat}")

            total_score = round(s_cpu + s_ram + s_disk + s_iops + s_bw + s_lat, 3)
            logger.debug(f" {s_cpu} + {s_ram} + {s_disk} + {s_iops} + {s_bw} + {s_lat} = {total_score}")
            logger.debug(f"Total Score: {total_score}")

            fe = target['fedge']
            ed = target['edge']
            
            # Standard metrics sheet array
            results_for_table.append([
                fe.get('region', 'DFW'), fe.get('site'), fe.get('id'),
                ed.get('site'), ed.get('id'), "Active", 1,
                float(target['_lat_val']), float(s_lat), float(target['cpu']), float(s_cpu),
                float(target['ramava']), float(s_ram), float(target['diskava']), float(s_disk),
                int(target['iops']), float(s_iops), float(target['bw']), float(s_bw),
                float(total_score), fe.get('manufacturer'), fe.get('platform'),
                fe.get('cluster'), fe.get('location'), float(target['_dist_mi'])
            ])

            # Audit Trail metrics sheet array with granular latency hop breakdowns
            results_details.append([
                fe.get('site'), fe.get('id'), ed.get('site'), ed.get('id'),
                float(target['fe_cpu']), float(target['ed_cpu']), float(target['cpu']),
                float(target['fe_ram']), float(target['ed_ram']), float(target['ramava']),
                float(target['fe_disk']), float(target['ed_disk']), float(target['diskava']),
                int(target['fe_iops']), int(target['ed_iops']), int(target['iops']),
                float(target['fe_bw']), float(target['ed_bw']), float(target['bw']),
                float(target['d1']), float(target['d2']), float(target['d3']), float(target['_dist_mi']),
                float(target['lat1']), float(target['lat2']), float(target['lat3']),
                float(target['_lat_val']), float(total_score)
            ])

            final_results.append({
                "path_id": f"{fe.get('site')}=={ed.get('site')}", "score": total_score, 
                "fedge_id": fe.get('id'), "edge_id": ed.get('id'),
                "fedge_site": fe.get('site'), "edge_site": ed.get('site')
            })

        # Generate sorted duplicate array for Tab 4 (Sorted descending by total score column index)
        results_details_sorted = sorted(results_details, key=lambda x: x[-1], reverse=True)

        # --- 4. EXCEL STYLING AND EXPORT ---
        headers_out = ["Region", "FEDGE Site", "FEDGE UUID", "EDGE Site", "EDGE UUID", "Status", "CNF", "Path Latency", "Lat Score", "Path CPU Usage %", "CPU Score", "Path RAM free %", "RAM Score", "Path Disk free %", "Disk Score", "Path IOPS", "IOPS Score", "Path BW", "BW Score", "TOTAL SCORE", "Manufacturer", "Platform", "Cluster", "Location", "Total Distance"]
        
        headers_details = [
            "FEDGE Site", "FEDGE UUID", "EDGE Site", "EDGE UUID",
            "FEDGE CPU", "EDGE CPU", "Path CPU (Worst)",
            "FEDGE RAM Free", "EDGE RAM Free", "Path RAM (Worst)",
            "FEDGE Disk Free", "EDGE Disk Free", "Path Disk (Worst)",
            "FEDGE IOPS", "EDGE IOPS", "Path IOPS (Worst)",
            "FEDGE BW", "EDGE BW", "Path BW (Worst)",
            "Dist SMU->FE", "Dist FE->ED", "Dist ED->UTSW", "Total Distance",
            "Lat SMU->FE (Micro)", "Lat FE->ED (Fiber)", "Lat ED->UTSW (Fiber)",
            "Calculated Latency", "TOTAL SCORE"
        ]

        folder = config["paths"]["excel_output"]
        if not os.path.exists(folder): os.makedirs(folder)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#        file_path = f"{folder}/network_inventory_{timestamp}.xlsx"
        file_path = f"{folder}/sim_{num_of_sim}_original_algorithm-{timestamp}.xlsx"

        # Order by column B 'Site'
        table_in.sort(key=lambda row: row[1])

        df_in = pd.DataFrame(table_in, columns=headers_in)
        df_out = pd.DataFrame(results_for_table, columns=headers_out)
        df_det = pd.DataFrame(results_details, columns=headers_details)
        df_det_srt = pd.DataFrame(results_details_sorted, columns=headers_details)

        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            df_in.to_excel(writer, sheet_name='InputData', index=False)
            df_out.to_excel(writer, sheet_name='OutputResults', index=False)
            df_det.to_excel(writer, sheet_name='OutputResultsDetails', index=False)
            df_det_srt.to_excel(writer, sheet_name='OutputResultsDetails_Sorted', index=False)
            
            consolas_font = Font(name='Consolas', size=10)
            highlight_font = Font(name='Consolas', size=10, bold=True, color="FF0000")
            
            best_val_fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
            soft_orange_fill = PatternFill(start_color="FFCC99", end_color="FFCC99", fill_type="solid")
            
            thin_border = Border(
                left=Side(style='thin'), right=Side(style='thin'), 
                top=Side(style='thin'), bottom=Side(style='thin')
            )

            for sheetname in writer.sheets:
                ws = writer.sheets[sheetname]
                
                # FEATURE: Freeze the first row (headers) for scroll stability across all sheets
                ws.freeze_panes = 'A2'
                
                # Global column width configuration and font assignment
                for col in ws.columns:
                    max_length = 0
                    column_letter = col[0].column_letter
                    for cell in col:
                        cell.border = thin_border
                        cell.font = consolas_font
                        try:
                            if len(str(cell.value)) > max_length: max_length = len(str(cell.value))
                        except: pass
                    ws.column_dimensions[column_letter].width = max_length + 2

                # Stylize standard Output and both Detail tabs
                if sheetname in ['OutputResults', 'OutputResultsDetails', 'OutputResultsDetails_Sorted']:
                    current_headers = headers_out if sheetname == 'OutputResults' else headers_details
                    col_idx = {h: i+1 for i, h in enumerate(current_headers)}
                    score_idx = col_idx["TOTAL SCORE"]
                    
                    # 1. Parse maximum total score for highlighting rows
                    scores_raw = []
                    for r in range(2, ws.max_row + 1):
                        val = ws.cell(row=r, column=score_idx).value
                        if val is not None: scores_raw.append((val, r))
                    
                    best_total = max(s[0] for s in scores_raw) if scores_raw else None

                    # 2. LAYER 1: Base Orange Highlights (Score Column & Winning Combo Row)
                    for r in range(2, ws.max_row + 1):
                        ws.cell(row=r, column=score_idx).fill = soft_orange_fill
                        if best_total is not None and ws.cell(row=r, column=score_idx).value == best_total:
                            for c in range(1, ws.max_column + 1):
                                ws.cell(row=r, column=c).fill = soft_orange_fill

                    # 3. LAYER 2: Metrics Overrides (Yellow Background + Red Font)
                    def highlight_metric(name, find_max=True):
                        if name not in col_idx: return
                        idx = col_idx[name]
                        vals = [(ws.cell(row=r, column=idx).value, r) for r in range(2, ws.max_row + 1) if ws.cell(row=r, column=idx).value is not None]
                        if not vals: return
                        target = max(v[0] for v in vals) if find_max else min(v[0] for v in vals)
                        for v, r in vals:
                            if v == target:
                                cell = ws.cell(row=r, column=idx)
                                cell.fill = best_val_fill
                                cell.font = highlight_font

                    metrics_to_paint = [
                        ("Path Latency", False), ("Calculated Latency", False),
                        ("Path CPU Usage %", False), ("Path CPU (Worst)", False),
                        ("Path RAM free %", True), ("Path RAM (Worst)", True),
                        ("Path Disk free %", True), ("Path Disk (Worst)", True),
                        ("Path IOPS", True), ("Path IOPS (Worst)", True),
                        ("Path BW", True), ("Path BW (Worst)", True)
                    ]
                    
                    for m, is_max in metrics_to_paint:
                        highlight_metric(m, is_max)
                    
                    # Lock absolute winning metric score cell with maximum prominence
                    if best_total is not None:
                        for val, r in scores_raw:
                            if val == best_total:
                                cell_score = ws.cell(row=r, column=score_idx)
                                cell_score.fill = best_val_fill
                                cell_score.font = highlight_font

        # 5. Infrastructure Logs & Output Reporting
        logger.info(f"Excel report generated with sorted audit trails: {file_path}")
        
        sorted_results = sorted(final_results, key=lambda x: x['score'], reverse=True)
        if sorted_results:
            top_path = sorted_results[0]
            logger.info(f"🏆 TOP SCORING PATH -> FEDGE Site: {top_path['fedge_site']} ({top_path['fedge_id']}) "
                        f"--> EDGE Site: {top_path['edge_site']} ({top_path['edge_id']}) "
                        f"| Score: {top_path['score']}")

        print("\n--- OUTPUT RESULTS ---")
        print(tabulate(results_for_table, headers=headers_out, tablefmt="fancy_grid"))

        return sorted_results, table_in, headers_in, file_path
        
        
    @staticmethod
    def calculate_pareto_efficiency(candidates: List[PathCandidate]) -> List[PathCandidate]:
        """
        Step 1: Evaluate Pareto dominance over all combined path alternatives.
        """
        logger.debug("============================================================")
        logger.debug("# C3 - PARETO + TOPSIS ANALYSIS FOR COMBINED PATHS")
        logger.debug("============================================================")
        logger.debug("")
        logger.debug("Starting C3-TOPSIS-Pareto analysis for Paths (SMU -> FE -> EDGE -> UTSW)")
        
        is_better_greater = {
            'latency': False,
            'cpu': False,
            'iops': True,
            'ram': True,
            'bw': True,
            'disk': True
        }
        
        # Cross-comparison matrix loop
        for i, c1 in enumerate(candidates):
            for j, c2 in enumerate(candidates):
                if i == j:
                    continue
                    
                c2_dominates_c1 = True
                at_least_one_strictly_better = False
                
                for metric in is_better_greater.keys():
                    v1 = c1.metrics[metric]
                    v2 = c2.metrics[metric]
                    
                    if is_better_greater[metric]:
                        if v2 < v1:
                            c2_dominates_c1 = False
                            break
                        if v2 > v1:
                            at_least_one_strictly_better = True
                    else:
                        if v2 > v1:
                            c2_dominates_c1 = False
                            break
                        if v2 < v1:
                            at_least_one_strictly_better = True
                
                if c2_dominates_c1 and at_least_one_strictly_better:
                    c1.pareto_efficient = False
                    break
                    
        # --- LOG STEP 1: Pareto Results Table ---
        logger.debug("")
        logger.debug("+-------------------------------------+")
        logger.debug("+ STEP 1 - Pareto Results - Combined Paths")
        logger.debug("+-------------------------------------+")
        logger.debug("")
        logger.debug("STEP 1 - PARETO RESULTS")
        
        pareto_table_data = [[c.path_id, str(c.pareto_efficient)] for c in candidates]
        logger.debug("\n" + tabulate(pareto_table_data, headers=["id", "pareto_efficient"], tablefmt="fancy_grid"))
        
        # --- LOG STEP 1 (Cont): Efficient Only Table ---
        logger.debug("")
        logger.debug("+-------------------------------------+")
        logger.debug("+ Pareto Efficient Candidates - Paths:")
        logger.debug("+-------------------------------------+")
        logger.debug("")
        logger.debug("Pareto Efficient Candidates - Combined")
        
        efficient_table_data = [[c.path_id] for c in candidates if c.pareto_efficient]
        logger.debug("\n" + tabulate(efficient_table_data, headers=["id"], tablefmt="fancy_grid"))
        
        return candidates
        
        

    @staticmethod
    def build_weighted_matrix(candidates: List[PathCandidate], weights: Dict[str, float]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Step 2 & 3: Convert path candidates to a Pandas DataFrame, perform vector normalization,
        and apply the criteria weights. Returns a tuple of (norm_df, weighted_df).
        """
        data = []
        for c in candidates:
            row = {
                'path_id': c.path_id,
                'cpu_usage': c.metrics['cpu'],
                'ramfree_value': c.metrics['ram'],
                'diskfree_value': c.metrics['disk'],
                'iops_value': c.metrics['iops'],
                'bw_value': c.metrics['bw'],
                'latency_value': c.metrics['latency'],
                'pareto_efficient': c.pareto_efficient
            }
            data.append(row)
            
        df = pd.DataFrame(data)
        df.set_index('path_id', inplace=True)
        
        # --- LOG STEP 0: Raw Data Matrix ---
        logger.debug("")
        logger.debug("+-------------------------------------+")
        logger.debug("+ STEP 0 - Raw Data - Combined Paths")
        logger.debug("+-------------------------------------+")
        logger.debug("")
        logger.debug("STEP 0 - RAW DATA - Combined Paths")
        
        raw_log_df = df.copy()
        raw_log_df['cpu_usage'] = raw_log_df['cpu_usage'].map('{:.3f}'.format)
        raw_log_df['ramfree_value'] = raw_log_df['ramfree_value'].map('{:.3f}'.format)
        raw_log_df['diskfree_value'] = raw_log_df['diskfree_value'].map('{:.3f}'.format)
        raw_log_df['iops_value'] = raw_log_df['iops_value'].map('{:,.0f}'.format)
        raw_log_df['bw_value'] = raw_log_df['bw_value'].map('{:.3f}'.format)
        raw_log_df['latency_value'] = raw_log_df['latency_value'].map('{:.3f}'.format)
        
        logger.debug("\n" + tabulate(raw_log_df.drop(columns=['pareto_efficient']), headers='keys', tablefmt='fancy_grid'))
        
        columns_to_process = ['cpu_usage', 'ramfree_value', 'diskfree_value', 'iops_value', 'bw_value', 'latency_value']
        norm_df = df.copy() # Numeric version
        
        # Step 2: Vector Normalization
        for col in columns_to_process:
            norm_factor = np.sqrt(np.sum(df[col] ** 2))
            norm_df[col] = df[col] / norm_factor if norm_factor > 0 else 0.0
            
        # --- LOG STEP 2: Normalized Matrix ---
        logger.debug("")
        logger.debug("+-------------------------------------+")
        logger.debug("+ STEP 2 - Normalized Matrix - Combined")
        logger.debug("+-------------------------------------+")
        logger.debug("")
        logger.debug("STEP 2 - NORMALIZED MATRIX - Combined")
        
        norm_log_df = norm_df.copy()
        for col in columns_to_process: # String formatted for logging
            norm_log_df[col] = norm_log_df[col].map('{:.3f}'.format)
        logger.debug("\n" + tabulate(norm_log_df, headers='keys', tablefmt='fancy_grid'))
            
        # Step 3: Weight Allocation
        weight_mapping = {
            'cpu_usage': weights['cpu'],
            'ramfree_value': weights['ram'],
            'diskfree_value': weights['disk'],
            'iops_value': weights['iops'],
            'bw_value': weights['bw'],
            'latency_value': weights['latency']
        }
        
        weighted_df = norm_df.copy() # Numeric version
        for col in columns_to_process:
            weighted_df[col] = norm_df[col] * weight_mapping[col]
            
        # --- LOG STEP 3: Weighted Matrix ---
        logger.debug("")
        logger.debug("+-------------------------------------+")
        logger.debug("+ STEP 3 - Weighted Matrix - Combined")
        logger.debug("+-------------------------------------+")
        logger.debug("")
        logger.debug("STEP 3 - WEIGHTED MATRIX - Combined")
        
        weighted_log_df = weighted_df.copy()
        for col in columns_to_process: # String formatted for logging
            weighted_log_df[col] = weighted_log_df[col].map('{:.3f}'.format)
        logger.debug("\n" + tabulate(weighted_log_df, headers='keys', tablefmt='fancy_grid'))
        
        # Return both matrices as a tuple to avoid data reference omission
        return df, norm_df, weighted_df, raw_log_df, norm_log_df, weighted_log_df
        

    @staticmethod
    def calculate_ideal_solutions(weighted_df: pd.DataFrame) -> tuple[dict, dict, list, list]:
        """
        Step 4: Determine the Ideal Positive (A+) and Ideal Negative (A-) solutions.
        """
        efficient_df = weighted_df[weighted_df['pareto_efficient'] == True]
        
        # Optimization configuration layout direction: True to maximize, False to minimize
        is_better_greater = {
            'latency_value': False,
            'cpu_usage': False,
            'iops_value': True,
            'ramfree_value': True,
            'bw_value': True,
            'diskfree_value': True
        }
        
        ideal_positive = {}
        ideal_negative = {}
        
        for col, maximize in is_better_greater.items():
            if maximize:
                ideal_positive[col] = efficient_df[col].max()
                ideal_negative[col] = efficient_df[col].min()
            else:
                ideal_positive[col] = efficient_df[col].min()
                ideal_negative[col] = efficient_df[col].max()
                
        # --- LOG STEP 4: Ideal Solutions Table ---
        logger.debug("")
        logger.debug("╔══════════════════════════════════════════════════════╗")
        logger.debug("║ STEP 4 - IDEAL SOLUTIONS (TOPSIS) - Combined Paths   ║")
        logger.debug("╚══════════════════════════════════════════════════════╝")
        logger.debug("STEP 4 - IDEAL SOLUTIONS (TOPSIS) - Combined Paths")
        
        columns_ordered = ['cpu_usage', 'ramfree_value', 'diskfree_value', 'iops_value', 'bw_value', 'latency_value']
        ideal_table_data = [
            ["Ideal Positive"] + [f"{ideal_positive[c]:.3f}" for c in columns_ordered],
            ["Ideal Negative"] + [f"{ideal_negative[c]:.3f}" for c in columns_ordered]
        ]
        logger.debug("\n" + tabulate(ideal_table_data, headers=["Type"] + columns_ordered, tablefmt="fancy_grid"))
        
        return ideal_positive, ideal_negative, ideal_table_data, ["Type"] + columns_ordered
        
        

    @staticmethod
    def calculate_closeness_coefficient(weighted_df: pd.DataFrame, ideal_positive: dict, ideal_negative: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Step 5: Calculate Euclidean distances and compute final Closeness Coefficient (C-Score).
        """
        columns_to_process = ['cpu_usage', 'ramfree_value', 'diskfree_value', 'iops_value', 'bw_value', 'latency_value']
        
        distance_positive = np.zeros(len(weighted_df))
        distance_negative = np.zeros(len(weighted_df))
        
        for col in columns_to_process:
            distance_positive += (weighted_df[col] - ideal_positive[col]) ** 2
            distance_negative += (weighted_df[col] - ideal_negative[col]) ** 2
            
        weighted_df['D_plus'] = np.sqrt(distance_positive)
        weighted_df['D_minus'] = np.sqrt(distance_negative)
        
        denominator = weighted_df['D_plus'] + weighted_df['D_minus']
        weighted_df['C_score'] = np.where(denominator > 0, weighted_df['D_minus'] / denominator, 0.0)
        
        # Filter non-Pareto efficient candidates before sorting for final ranking
        final_ranked_df = weighted_df[weighted_df['pareto_efficient'] == True].copy()
        final_ranked_df.sort_values(by='C_score', ascending=False, inplace=True)
        
        # --- LOG STEP 5: Final Ranking Table ---
        logger.debug("")
        logger.debug("+-------------------------------------+")
        logger.debug("+ STEP 5 - Final TOPSIS Ranking - Paths")
        logger.debug("+-------------------------------------+")
        logger.debug("")
        logger.debug("STEP 5 - FINAL TOPSIS RANKING")
        
        ranking_log_df = pd.DataFrame(index=final_ranked_df.index)
        ranking_log_df['D_plus'] = final_ranked_df['D_plus'].map('{:.3f}'.format)
        ranking_log_df['D_minus'] = final_ranked_df['D_minus'].map('{:.3f}'.format)
        ranking_log_df['C_score'] = final_ranked_df['C_score'].map('{:.3f}'.format)
        
        logger.debug("\n" + tabulate(ranking_log_df, headers='keys', tablefmt='fancy_grid'))
        
        # Highlight best candidate
        if not final_ranked_df.empty:
            best_id = final_ranked_df.index[0]
            best_score = final_ranked_df['C_score'].iloc[0]
            logger.debug("")
            logger.debug("+------------------------------------------------------------------------+")
            logger.debug(f"BEST COMBINED PATH (C3-TOPSIS-Pareto): {best_id} | Score: {best_score:.6f}")
            logger.debug("+------------------------------------------------------------------------+")
            logger.debug("")
        else:
            logger.warning("No Pareto efficient candidates found to rank.")
        
        return final_ranked_df, ranking_log_df
        
        

    def evaluate_paths(self, candidates: List[PathCandidate], weights: Dict[str, float],num_of_sim: int,) -> tuple[List[Dict[str, Any]], List[List[Any]], List[str], str]:
        """ 
        Main orchestrator that executes the full C3-Pareto-TOPSIS pipeline
        to find the optimal path combination based on latency and hardware.
        """
        if not candidates:
            logger.warning("No path candidates provided for evaluation")
            return []
            
        # Step 1: Filter and mark Pareto-efficient paths
        logger.info(f"Executing Step 1: Pareto filtering for {len(candidates)} candidates")
        processed_candidates = self.calculate_pareto_efficiency(candidates)
        
        # Step 2 & 3: Build matrix, normalize it, and apply weights
        logger.info("Executing Steps 2 & 3: Matrix building, normalization, and weight scaling")
        raw_df, norm_df, weighted_df, raw_log_df, norm_log_df, weighted_log_df = self.build_weighted_matrix(processed_candidates, weights)
        
        # Step 4: Calculate ideal solutions using only efficient paths
        logger.info("Executing Step 4: Ideal solutions extraction")
        ideal_pos, ideal_neg, ideal_table_data, ideal_table_headers = self.calculate_ideal_solutions(weighted_df)
        
        # Step 5: Calculate Euclidean distances and final C-Score ranking
        logger.info("Executing Step 5: Closeness Coefficient scoring and ranking")
        final_df, topsis_ranking_df = self.calculate_closeness_coefficient(weighted_df, ideal_pos, ideal_neg)
        
        # 6. Format the final output as a structured list of dictionaries
        ranked_results = []
        candidates_map = {c.path_id: c for c in candidates} # Map to recover raw metrics

        file_path = ""
        for path_id, row in final_df.iterrows():
            fe_id, edge_id = path_id.split("==")
            c = candidates_map[path_id]
            
            # Extract Site names from candidate source data
            raw_source = getattr(c, 'raw_source', {})
            fedge_site = raw_source.get('fe', {}).get('site', fe_id)
            edge_site = raw_source.get('ed', {}).get('site', edge_id)
            
            result_item = {
                "path_id": f"{fedge_site}=={edge_site}",
                "fedge_id": fe_id,
                "edge_id": edge_id,
                "fedge_site": fedge_site,
                "edge_site": edge_site,
                "c_score": float(row["C_score"]),
                "pareto_efficient": bool(row["pareto_efficient"]),
                "distance_positive": float(row["D_plus"]),
                "distance_negative": float(row["D_minus"]),
                "metrics": {
                    "latency": float(c.metrics['latency']),
                    "cpu": float(c.metrics['cpu']),
                    "iops": float(c.metrics['iops']),
                    "ram": float(c.metrics['ram']),
                    "bw": float(c.metrics['bw']),
                    "disk": float(c.metrics['disk'])
                }
            }
            ranked_results.append(result_item)
            
        # Try to automatically export data records into corporate multi-sheet spreadsheet layouts
        try:
            folder = "excel"
            if not os.path.exists(folder): os.makedirs(folder)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#            file_path = f"{folder}/c3_pareto_topsis_placement_report{timestamp}.xlsx"
            file_path = f"{folder}/sim_{num_of_sim}_c3_pareto_topsis_algorithm_{timestamp}.xlsx"

            file_path = self.export_to_excel(
                candidates=processed_candidates,
                final_df=final_df,
                norm_df=norm_df,
                weighted_df=weighted_df,
                ideal_positive=ideal_pos,
                ideal_negative=ideal_neg,
                filename=file_path,
                raw_df_log=raw_log_df,
                norm_df_log=norm_log_df,
                weighted_df_log=weighted_log_df,
                ideal_solutions_data=ideal_table_data,
                ideal_solutions_headers=ideal_table_headers,
                topsis_ranking_df=topsis_ranking_df
            )
        except Exception as e:
            logger.error(f"Failed to automatically export Excel report: {str(e)}")

        logger.info(f"Path evaluation completed successfully. Best path: {ranked_results[0]['path_id']} with C-Score: {ranked_results[0]['c_score']:.4f}")

        # Prepare input data for JSON response
        input_headers = [
            "Region", "Site", "Device UUID", "Status", "Role", "CNF", 
            "CPU Usage %", "RAM free %", "Disk free %", "IOPS", "Bandwidth (Gbps)", 
            "Manufacturer", "Platform", "Cluster", "Location", "ShortName", "Type", "Latitude", "Longitude"
        ]
        
        input_rows = []
        seen_nodes = set()
        
        for c in candidates:
            fe_id, edge_id = c.fe_id, c.edge_id
            raw_source_data = getattr(c, 'raw_source', None)
            
            fe_info = raw_source_data['fe'] if (raw_source_data and 'fe' in raw_source_data) else c.metrics
            ed_info = raw_source_data['ed'] if (raw_source_data and 'ed' in raw_source_data) else c.metrics
            
            if fe_id not in seen_nodes:
                seen_nodes.add(fe_id)
                input_rows.append([
                    "DFW", fe_info.get('site', fe_id), fe_id, fe_info.get('status', 'Active'), "FEServer", 1,
                    float(fe_info.get('cpu', 0)), float(fe_info.get('ramava', fe_info.get('ram', 0))), float(fe_info.get('diskava', fe_info.get('disk', 0))),
                    int(str(fe_info.get('iops', 0)).replace(',', '')), float(fe_info.get('bw', 0)),
                    fe_info.get('manufacturer', 'HPE'), fe_info.get('platform', 'RHOCP'), 
                    fe_info.get('cluster', 'RT_CaaS_CS'), fe_info.get('location', 'Unknown Location'), 
                    fe_info.get('shortname', 'N/A'), "DL360", 
                    float(fe_info.get('latitude', 0.0)), float(fe_info.get('longitude', 0.0))
                ])
            if edge_id not in seen_nodes:
                seen_nodes.add(edge_id)
                input_rows.append([
                    "DFW", ed_info.get('site', edge_id), edge_id, ed_info.get('status', 'Active'), "EdgeServer", 0,
                    float(ed_info.get('cpu', 0)), float(ed_info.get('ramava', ed_info.get('ram', 0))), float(ed_info.get('diskava', ed_info.get('disk', 0))),
                    int(str(ed_info.get('iops', 0)).replace(',', '')), float(ed_info.get('bw', 0)),
                    ed_info.get('manufacturer', 'HPE'), ed_info.get('platform', 'WRCP'), 
                    ed_info.get('cluster', 'RT_CaaS_EDC'), ed_info.get('location', 'Unknown Location'), 
                    ed_info.get('shortname', 'N/A'), "e910t", 
                    float(ed_info.get('latitude', 0.0)), float(ed_info.get('longitude', 0.0))
                ])
                
        # Sort InputData alphabetically by the 'Site' column (index 1)
        input_rows.sort(key=lambda x: str(x[1]))

        return ranked_results, input_rows, input_headers, file_path


    def generate_path_candidates(self, all_nodes: List[Any]) -> List[PathCandidate]:
        """
        Processes raw nodes from database, separates them into FEDGE and EDGE layers...
        """
        logger.info("Starting Path Candidates generation and metrics aggregation")
        
        # 1. Load configurations using the correct NetworkService static method
        config = NetworkService._load_config()
        weights = config["scoring_weights"]
        lat_factors = config["latency_factors"]
        smu_ref = config["smu_reference"]        
        utsw_ref = config["network_anchors"]["utsw"]
        lat_f_micro = lat_factors["fedge_microwave"]
        lat_f_fiber = lat_factors["edge_fiber"]
        
        # Fixed reference coordinates
        smu_coords = (smu_ref["lat"], smu_ref["lon"])
        utsw_coords = (utsw_ref["latitude"], utsw_ref["longitude"])
        
        # 2. Separate nodes into FEDGE and EDGE layers based on their "Role" field
        fedge_nodes = []
        edge_nodes = []
        
        for node in all_nodes:
            # Safely extract the role attribute or dict key, making it case-insensitive just in case
            node_role = getattr(node, 'role', '') or node.get('role', '')
            node_role_str = str(node_role).strip()
            
            if node_role_str == 'FEServer':
                fedge_nodes.append(node)
            elif node_role_str == 'EdgeServer':
                edge_nodes.append(node)
                
        logger.info(f"Layer separation complete: Found {len(fedge_nodes)} FEDGE nodes (FEServer) and {len(edge_nodes)} EDGE nodes (EdgeServer)")
        
        path_candidates = []
        
        # Helper function to parse formatted string data back to numeric values for math operations
        def clean_metric(val: Any) -> float:
            if isinstance(val, str):
                return float(val.replace(',', ''))
            return float(val)

        # 3. Cross-combine all FEDGE and EDGE nodes to create the paths (O(N*M))
        for fe in fedge_nodes:
            fe_lat = float(getattr(fe, 'latitude', 0.0) or fe.get('latitude', 0.0))
            fe_lon = float(getattr(fe, 'longitude', 0.0) or fe.get('longitude', 0.0))
            fe_id = getattr(fe, 'id', '') or fe.get('id', '')
            
            # Clean FEDGE hardware values
            fe_cpu = clean_metric(getattr(fe, 'cpu', 0.0) or fe.get('cpu', 0.0))
            fe_ram = clean_metric(getattr(fe, 'ramava', 0.0) or fe.get('ramava', 0.0))
            fe_disk = clean_metric(getattr(fe, 'diskava', 0.0) or fe.get('diskava', 0.0))
            fe_iops = clean_metric(getattr(fe, 'iops', 0.0) or fe.get('iops', 0.0))
            fe_bw = clean_metric(getattr(fe, 'bw', 0.0) or fe.get('bw', 0.0))
            
            for ed in edge_nodes:
                ed_lat = float(getattr(ed, 'latitude', 0.0) or ed.get('latitude', 0.0))
                ed_lon = float(getattr(ed, 'longitude', 0.0) or ed.get('longitude', 0.0))
                ed_id = getattr(ed, 'id', '') or ed.get('id', '')
                
                # Clean EDGE hardware values
                ed_cpu = clean_metric(getattr(ed, 'cpu', 0.0) or ed.get('cpu', 0.0))
                ed_ram = clean_metric(getattr(ed, 'ramava', 0.0) or ed.get('ramava', 0.0))
                ed_disk = clean_metric(getattr(ed, 'diskava', 0.0) or ed.get('diskava', 0.0))
                ed_iops = clean_metric(getattr(ed, 'iops', 0.0) or ed.get('iops', 0.0))
                ed_bw = clean_metric(getattr(ed, 'bw', 0.0) or ed.get('bw', 0.0))
                
                # 4. Geodetic calculations per hop (using Haversine)
                # Hop 1: SMU -> FEDGE (Microwave)
                d1 = NetworkService.calculate_haversine(smu_coords[0], smu_coords[1], fe_lat, fe_lon, unit='miles')
                lat1 = d1 * lat_f_micro
                
                # Hop 2: FEDGE -> EDGE (Fiber)
                d2 = NetworkService.calculate_haversine(fe_lat, fe_lon, ed_lat, ed_lon, unit='miles')
                lat2 = d2 * lat_f_fiber
                
                # Hop 3: EDGE -> UTSW (Fiber)
                d3 = NetworkService.calculate_haversine(ed_lat, ed_lon, utsw_coords[0], utsw_coords[1], unit='miles')
                lat3 = d3 * lat_f_fiber
                
                total_latency = round(lat1 + lat2 + lat3, 3)
                
                # 5. Bottleneck and Aggregation logic for Hardware Metrics
                # - CPU: Worst case scenario or maximum utilization between the nodes
                combined_cpu = max(fe_cpu, ed_cpu)
                # - RAM and Disk Free %: Combined bottleneck is the minimum space available
                combined_ram = min(fe_ram, ed_ram)
                combined_disk = min(fe_disk, ed_disk)
                # - IOPS and Bandwidth: Throughput bottleneck is the lowest capacity link/node
                combined_iops = min(fe_iops, ed_iops)
                combined_bw = min(fe_bw, ed_bw)
                
                metrics_payload = {
                    'latency': total_latency,
                    'cpu': combined_cpu,
                    'iops': combined_iops,
                    'ram': combined_ram,
                    'bw': combined_bw,
                    'disk': combined_disk
                }
                
                # Instantiating the candidate
                candidate = PathCandidate(fe_id=fe_id, edge_id=ed_id, metrics=metrics_payload)
                
                # Store raw source data for comprehensive Excel reporting
                candidate.raw_source = {
                    'fe': fe.model_dump() if hasattr(fe, 'model_dump') else fe,
                    'ed': ed.model_dump() if hasattr(ed, 'model_dump') else ed,
                    'hops': {
                        'd1_smu_fe': d1,
                        'lat1': lat1,
                        'd2_fe_ed': d2,
                        'lat2': lat2,
                        'd3_ed_utsw': d3,
                        'lat3': lat3,
                        'total_distance': round(d1 + d2 + d3, 3)
                    }
                }
                path_candidates.append(candidate)
                
        logger.info(f"Successfully generated {len(path_candidates)} combined Path Candidates")
        return path_candidates        
        
        
    @staticmethod
    def export_to_excel(
        candidates: List[PathCandidate], 
        final_df: pd.DataFrame, 
        norm_df: pd.DataFrame, 
        weighted_df: pd.DataFrame, 
        ideal_positive: dict, 
        ideal_negative: dict, 
        filename: str = "c3_pareto_topsis_report.xlsx",
        raw_df_log: pd.DataFrame = None,
        norm_df_log: pd.DataFrame = None,
        weighted_df_log: pd.DataFrame = None,
        ideal_solutions_data: list = None,
        ideal_solutions_headers: list = None,
        topsis_ranking_df: pd.DataFrame = None
    ) -> str:
        """
        Generates an enterprise-grade Excel workbook for C3-Pareto-TOPSIS mirroring
        the aesthetic design, grid layout, percentages scale, and typography of the original algorithm.
        Ensures rows are alphabetically ordered by FEDGE Site and EDGE Site keys.
        """
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter
        import numpy as np
        import pandas as pd

        wb = openpyxl.Workbook()
        
        # --- AESTHETIC CONFIGURATION (CONSOLAS 10 & GRID STYLE) ---
        font_header = Font(name="Consolas", size=10, bold=True, color="FFFFFF")
        font_data = Font(name="Consolas", size=10)
        
        fill_header = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
        fill_zebra = PatternFill(start_color="F7F9FC", end_color="F7F9FC", fill_type="solid")
        
        grid_border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin")
        )

        # Pareto Efficiency highlighting fills
        good_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid") # Light Green
        bad_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid") # Light Red

        def apply_sheet_formatting(ws, headers, row_data_list):
            """Internal helper to apply standard formatting, grid borders, freeze panes, and auto-fit columns."""
            ws.views.sheetView[0].showGridLines = True
            ws.freeze_panes = "A2"  # Freeze header row
            
            # Write and format Headers
            for col_idx, header_text in enumerate(headers, start=1):
                cell = ws.cell(row=1, column=col_idx, value=header_text)
                cell.font = font_header
                cell.fill = fill_header
                cell.alignment = openpyxl.styles.Alignment(horizontal="center", vertical="center", wrap_text=False)
                cell.border = grid_border
            
            # Write and format Data Rows
            for r_idx, row_values in enumerate(row_data_list, start=2):
                is_zebra = (r_idx % 2 == 0)
                for c_idx, val in enumerate(row_values, start=1):
                    cell = ws.cell(row=r_idx, column=c_idx, value=val)
                    cell.font = font_data
                    cell.border = grid_border
                    
                    if is_zebra:
                        cell.fill = fill_zebra

                    # Highlight 'pareto_efficient' column with Green/Red
                    if headers[c_idx-1] == 'pareto_efficient':
                        if str(val).upper() == 'TRUE':
                            cell.fill = good_fill
                        elif str(val).upper() == 'FALSE':
                            cell.fill = bad_fill
                        cell.alignment = openpyxl.styles.Alignment(horizontal="center")
                        
                    # Standard numeric and text layout configuration
                    if isinstance(val, (int, float, np.number)):
                        cell.alignment = openpyxl.styles.Alignment(horizontal="right")
                        if isinstance(val, (float, np.floating)):
                            cell.number_format = "0.000" if any(term in headers[c_idx-1] for term in ["Score", "SCORE", "Distance", "Latency", "Dist", "Lat"]) else "0.00"
                    elif isinstance(val, (bool, np.bool_)):
                        cell.alignment = openpyxl.styles.Alignment(horizontal="center")
                    else:
                        cell.alignment = openpyxl.styles.Alignment(horizontal="left")
            
            # Dynamic Column Auto-Adjustment Fit
            for col in ws.columns:
                max_len = 0
                col_letter = get_column_letter(col[0].column)
                for cell in col:
                    if cell.value is not None:
                        max_len = max(max_len, len(str(cell.value)))
                ws.column_dimensions[col_letter].width = max(max_len + 3, 11)

        # Map candidates by their ID to extract original metrics cleanly
        candidates_map = {c.path_id: c for c in candidates}

        # ----------------------------------------------------
        # PRE-PROCESSING: Sort DataFrame by FEDGE Site & EDGE Site
        # ----------------------------------------------------
        sorting_records = []
        for path_id, row in final_df.iterrows():
            fe_id, edge_id = path_id.split("==")
            c = candidates_map[path_id]
            raw_source_data = getattr(c, 'raw_source', None)
            fe_site = raw_source_data['fe'].get('site', fe_id) if raw_source_data else fe_id
            ed_site = raw_source_data['ed'].get('site', edge_id) if raw_source_data else edge_id
            
            sorting_records.append({
                'path_id': path_id,
                'fedge_site': fe_site,
                'edge_site': ed_site,
                'C_score': row['C_score']
            })
            
        sorting_df = pd.DataFrame(sorting_records)
        sorting_df = sorting_df.sort_values(by=['fedge_site', 'edge_site'], ascending=[True, True])

        # ----------------------------------------------------
        # SHEET 1: InputData
        # ----------------------------------------------------
        ws_input = wb.active
        ws_input.title = "InputData"
        
        input_headers = [
            "Region", "Site", "Device UUID", "Status", "Role", "CNF", 
            "CPU Usage %", "RAM free %", "Disk free %", "IOPS", "Bandwidth (Gbps)", 
            "Manufacturer", "Platform", "Cluster", "Location", "ShortName", "Type", "Latitude", "Longitude"
        ]
        
        input_rows = []
        seen_nodes = set()
        
        for c in candidates:
            fe_id, edge_id = c.fe_id, c.edge_id
            raw_source_data = getattr(c, 'raw_source', None)
            
            fe_info = raw_source_data['fe'] if (raw_source_data and 'fe' in raw_source_data) else c.metrics
            ed_info = raw_source_data['ed'] if (raw_source_data and 'ed' in raw_source_data) else c.metrics
            
            if fe_id not in seen_nodes:
                seen_nodes.add(fe_id)
                input_rows.append([
                    "DFW", fe_info.get('site', fe_id), fe_id, fe_info.get('status', 'Active'), "FEServer", 1,
                    float(fe_info.get('cpu', 0)), float(fe_info.get('ramava', fe_info.get('ram', 0))), float(fe_info.get('diskava', fe_info.get('disk', 0))),
                    int(str(fe_info.get('iops', 0)).replace(',', '')), float(fe_info.get('bw', 0)),
                    fe_info.get('manufacturer', 'HPE'), fe_info.get('platform', 'RHOCP'), 
                    fe_info.get('cluster', 'RT_CaaS_CS'), fe_info.get('location', 'Unknown Location'), 
                    fe_info.get('shortname', 'N/A'), "DL360", 
                    float(fe_info.get('latitude', 0.0)), float(fe_info.get('longitude', 0.0))
                ])
            if edge_id not in seen_nodes:
                seen_nodes.add(edge_id)
                input_rows.append([
                    "DFW", ed_info.get('site', edge_id), edge_id, ed_info.get('status', 'Active'), "EdgeServer", 0,
                    float(ed_info.get('cpu', 0)), float(ed_info.get('ramava', ed_info.get('ram', 0))), float(ed_info.get('diskava', ed_info.get('disk', 0))),
                    int(str(ed_info.get('iops', 0)).replace(',', '')), float(ed_info.get('bw', 0)),
                    ed_info.get('manufacturer', 'HPE'), ed_info.get('platform', 'WRCP'), 
                    ed_info.get('cluster', 'RT_CaaS_EDC'), ed_info.get('location', 'Unknown Location'), 
                    ed_info.get('shortname', 'N/A'), "e910t", 
                    float(ed_info.get('latitude', 0.0)), float(ed_info.get('longitude', 0.0))
                ])
    
        # Sort InputData alphabetically by the 'Site' column (index 1)
        input_rows.sort(key=lambda x: str(x[1]))
        apply_sheet_formatting(ws_input, input_headers, input_rows)

        # ----------------------------------------------------
        # SHEET 2: OutputResults
        # ----------------------------------------------------
        ws_output = wb.create_sheet(title="OutputResults")
        output_headers = [
            "Region", "FEDGE Site", "FEDGE UUID", "EDGE Site", "EDGE UUID", "Status", "CNF", 
            "Path Latency", "Lat Score", "Path CPU Usage %", "CPU Score", "Path RAM free %", "RAM Score", 
            "Path Disk free %", "Disk Score", "Path IOPS", "IOPS Score", "Path BW", "BW Score", 
            "TOTAL SCORE", "Manufacturer", "Platform", "Cluster", "Location", "Total Distance"
        ]
        
        output_rows = []
        for idx, sort_row in sorting_df.iterrows():
            path_id = sort_row['path_id']
            fe_id, edge_id = path_id.split("==")
            c = candidates_map[path_id]
            raw_source_data = getattr(c, 'raw_source', None)
            fe_info = raw_source_data['fe'] if raw_source_data else {}
            
            hop_data = raw_source_data.get('hops', {}) if raw_source_data else {}
            total_dist_val = hop_data.get('total_distance', 0.0)
            
            w_row = weighted_df.loc[path_id]
            final_score_row = final_df.loc[path_id]
            
            output_rows.append([
                "DFW", sort_row['fedge_site'], fe_id, sort_row['edge_site'], edge_id,
                "Active", 1, 
                float(c.metrics['latency']), float(w_row['latency_value']),
                float(c.metrics['cpu']), float(w_row['cpu_usage']),
                float(c.metrics['ram']), float(w_row['ramfree_value']),
                float(c.metrics['disk']), float(w_row['diskfree_value']),
                int(c.metrics['iops']), float(w_row['iops_value']),
                float(c.metrics['bw']), float(w_row['bw_value']),
                float(final_score_row["C_score"]), 
                fe_info.get('manufacturer', 'HPE'), fe_info.get('platform', 'RHOCP'), 
                fe_info.get('cluster', 'RT_CaaS'), fe_info.get('location', 'Location Details'), 
                float(total_dist_val)
            ])
            
        apply_sheet_formatting(ws_output, output_headers, output_rows)

        # ----------------------------------------------------
        # SHEET 3: OutputResultsDetails
        # ----------------------------------------------------
        ws_details = wb.create_sheet(title="OutputResultsDetails")
        details_headers = [
            "Region", "FEDGE Site", "FEDGE UUID", "EDGE Site", "EDGE UUID", "Status", "CNF",
            "Dist SMU -> FE", "Lat SMU -> FE", "Dist FE -> EDGE", "Lat FE -> EDGE",
            "Dist EDGE -> UTSW", "Lat EDGE -> UTSW", "Total Distance",
            "Path Latency", "Lat Score", 
            "FEDGE CPU Usage %", "EDGE CPU Usage %", "Path CPU Usage %", "CPU Score", 
            "FEDGE RAM Free %", "EDGE RAM Free %", "Path RAM free %", "RAM Score", 
            "FEDGE Disk Free %", "EDGE Disk Free %", "Path Disk free %", "Disk Score", 
            "FEDGE IOPS", "EDGE IOPS", "Path IOPS", "IOPS Score", 
            "FEDGE Bandwidth (Gbps)", "EDGE Bandwidth (Gbps)", "Path BW", "BW Score", 
            "TOTAL SCORE", "Manufacturer", "Platform", "Cluster" # "Location" was removed here
        ]

        details_rows = []
        # Helper to parse numeric values from raw info (handling potential strings with commas)
        def clean_val(info, key):
            val = info.get(key, 0.0)
            if isinstance(val, str):
                return float(val.replace(',', ''))
            return float(val)

        for idx, sort_row in sorting_df.iterrows():
            path_id = sort_row['path_id']
            fe_id, edge_id = path_id.split("==")
            c = candidates_map[path_id]
            raw_source_data = getattr(c, 'raw_source', None)
            fe_info = raw_source_data['fe'] if raw_source_data else {}
            ed_info = raw_source_data['ed'] if raw_source_data else {}

            hop_data = raw_source_data.get('hops', {}) if raw_source_data else {}

            w_row = weighted_df.loc[path_id]
            final_score_row = final_df.loc[path_id]

            details_rows.append([
                "DFW", sort_row['fedge_site'], fe_id, sort_row['edge_site'], edge_id,
                "Active", 1,
                float(hop_data.get('d1_smu_fe', 0.0)), float(hop_data.get('lat1', 0.0)),
                float(hop_data.get('d2_fe_ed', 0.0)), float(hop_data.get('lat2', 0.0)),
                float(hop_data.get('d3_ed_utsw', 0.0)), float(hop_data.get('lat3', 0.0)),
                float(hop_data.get('total_distance', 0.0)),
                float(c.metrics['latency']), float(w_row['latency_value']),
                clean_val(fe_info, 'cpu'), clean_val(ed_info, 'cpu'),
                float(c.metrics['cpu']), float(w_row['cpu_usage']),
                clean_val(fe_info, 'ramava'), clean_val(ed_info, 'ramava'),
                float(c.metrics['ram']), float(w_row['ramfree_value']),
                clean_val(fe_info, 'diskava'), clean_val(ed_info, 'diskava'),
                float(c.metrics['disk']), float(w_row['diskfree_value']),
                int(clean_val(fe_info, 'iops')), int(clean_val(ed_info, 'iops')),
                int(c.metrics['iops']), float(w_row['iops_value']),
                clean_val(fe_info, 'bw'), clean_val(ed_info, 'bw'),
                float(c.metrics['bw']), float(w_row['bw_value']),
                float(final_score_row["C_score"]),
                fe_info.get('manufacturer', 'HPE'), fe_info.get('platform', 'RHOCP'),
                fe_info.get('cluster', 'RT_CaaS')
            ])
            
        apply_sheet_formatting(ws_details, details_headers, details_rows)

        # Define custom fills and fonts for conditional formatting
        yellow_fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
        red_font = Font(color="FF0000", bold=True)
        green_fill = PatternFill(start_color="00FF00", end_color="00FF00", fill_type="solid")
        orange_fill = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")
        blue_fill = PatternFill(start_color="0000FF", end_color="0000FF", fill_type="solid") # New blue color
        white_font = Font(color="FFFFFF", bold=True) # New white font

        # Helper to apply conditional formatting
        def apply_highlight(ws, headers, column_name, criteria, fill, font=None):
            try:
                col_idx = headers.index(column_name) + 1 # Excel columns are 1-indexed
            except ValueError:
                logger.warning(f"Column '{column_name}' not found for highlighting.")
                return

            values = []
            for r_idx in range(2, ws.max_row + 1): # Data starts from row 2
                cell_value = ws.cell(row=r_idx, column=col_idx).value
                if isinstance(cell_value, (int, float)):
                    values.append(cell_value)
            
            if not values:
                return

            target_value = None
            if criteria == "min":
                target_value = min(values)
            elif criteria == "max":
                target_value = max(values)
            
            if target_value is None:
                return

            for r_idx in range(2, ws.max_row + 1):
                cell = ws.cell(row=r_idx, column=col_idx)
                # Ensure we compare numbers to numbers, and handle potential rounding issues for floats
                if isinstance(cell.value, (int, float)):
                    # For floats, compare with a small tolerance
                    if isinstance(target_value, float):
                        if abs(cell.value - target_value) < 1e-9: # Using a small epsilon for float comparison
                            cell.fill = fill
                            if font:
                                cell.font = font
                    else: # For integers or exact matches
                        if cell.value == target_value:
                            cell.fill = fill
                            if font:
                                cell.font = font

        # Apply Yellow/Red highlights
        yellow_red_highlights = [
            ("Dist SMU -> FE", "min"), ("Dist FE -> EDGE", "min"), ("Dist EDGE -> UTSW", "min"),
            ("Path Latency", "min"), ("FEDGE CPU Usage %", "min"), ("EDGE CPU Usage %", "min"),
            ("FEDGE RAM Free %", "max"), ("EDGE RAM Free %", "max"), ("FEDGE Disk Free %", "max"),
            ("EDGE Disk Free %", "max"), ("FEDGE IOPS", "max"), ("EDGE IOPS", "max"),
            ("FEDGE Bandwidth (Gbps)", "max"), ("EDGE Bandwidth (Gbps)", "max")
        ]
        for col_name, criteria in yellow_red_highlights:
            apply_highlight(ws_details, details_headers, col_name, criteria, yellow_fill, red_font)

        # Apply Green highlights
        green_highlights = [
            ("Total Distance", "min"), ("Path CPU Usage %", "min"),
            ("Path RAM free %", "max"), ("Path Disk free %", "max"),
            ("Path IOPS", "max"), ("Path BW", "max")
        ]
        for col_name, criteria in green_highlights:
            apply_highlight(ws_details, details_headers, col_name, criteria, green_fill)

        # Apply Orange highlights
        orange_highlights = [
            ("Lat Score", "max"), ("CPU Score", "max"), ("RAM Score", "max"),
            ("Disk Score", "max"), ("IOPS Score", "max"), ("BW Score", "max")
        ]
        for col_name, criteria in orange_highlights:
            apply_highlight(ws_details, details_headers, col_name, criteria, orange_fill)

        # ----------------------------------------------------
        # SHEET 4: OutputResultsDetails_Sorted
        # ----------------------------------------------------
        ws_details_sorted = wb.create_sheet(title="OutputResultsDetails_Sorted")

        # Sort details_rows by 'TOTAL SCORE' in descending order
        total_score_col_idx = details_headers.index("TOTAL SCORE")
        details_rows_sorted = sorted(details_rows, key=lambda x: x[total_score_col_idx], reverse=True)

        apply_sheet_formatting(ws_details_sorted, details_headers, details_rows_sorted)

        # Apply the same yellow/red, green, orange highlights to the sorted sheet
        for col_name, criteria in yellow_red_highlights:
            apply_highlight(ws_details_sorted, details_headers, col_name, criteria, yellow_fill, red_font)
        for col_name, criteria in green_highlights:
            apply_highlight(ws_details_sorted, details_headers, col_name, criteria, green_fill)
        for col_name, criteria in orange_highlights:
            apply_highlight(ws_details_sorted, details_headers, col_name, criteria, orange_fill)

        # Apply blue/white highlight to the top row of the sorted sheet, only if background is white/zebra
        top_row_idx = 2 # Data starts at row 2
        for c_idx in range(1, ws_details_sorted.max_column + 1):
            cell = ws_details_sorted.cell(row=top_row_idx, column=c_idx)
            current_fill_color_rgb = cell.fill.start_color.rgb
            # Check if the cell background color is the default (white '00000000') or zebra ('00F7F9FC')
            if current_fill_color_rgb in ['00000000', '00F7F9FC', None]:
                cell.fill = blue_fill
                cell.font = white_font

        # ----------------------------------------------------
        # SHEET 5: RAW_DATA-Combined Paths
        # ----------------------------------------------------
        if raw_df_log is not None:
            ws_raw_data = wb.create_sheet(title="RAW_DATA-Combined Paths")
            # Include path_id as first column via reset_index() and exclude 'pareto_efficient'
            df_to_export = raw_df_log.reset_index()
            raw_data_headers = [col for col in df_to_export.columns if col != 'pareto_efficient']
            raw_data_rows = df_to_export[raw_data_headers].values.tolist()
            apply_sheet_formatting(ws_raw_data, raw_data_headers, raw_data_rows)

        # ----------------------------------------------------
        # SHEET 6: NORMALIZED_MATRIX
        # ----------------------------------------------------
        if norm_df_log is not None:
            ws_norm_matrix = wb.create_sheet(title="NORMALIZED_MATRIX")
            # Include path_id as first column
            df_to_export = norm_df_log.reset_index()
            norm_matrix_headers = df_to_export.columns.tolist()
            norm_matrix_rows = df_to_export.values.tolist()
            apply_sheet_formatting(ws_norm_matrix, norm_matrix_headers, norm_matrix_rows)

        # ----------------------------------------------------
        # SHEET 7: WEIGHTED_MATRIX
        # ----------------------------------------------------
        if weighted_df_log is not None:
            ws_weighted_matrix = wb.create_sheet(title="WEIGHTED_MATRIX")
            # Include path_id as first column
            df_to_export = weighted_df_log.reset_index()
            weighted_matrix_headers = df_to_export.columns.tolist()
            weighted_matrix_rows = df_to_export.values.tolist()
            apply_sheet_formatting(ws_weighted_matrix, weighted_matrix_headers, weighted_matrix_rows)

        # ----------------------------------------------------
        # SHEET 8: IDEAL_SOLUTIONS
        # ----------------------------------------------------
        if ideal_solutions_data is not None and ideal_solutions_headers is not None:
            ws_ideal_solutions = wb.create_sheet(title="IDEAL_SOLUTIONS")
            # The ideal_solutions_data is already a list of lists, ready for apply_sheet_formatting
            apply_sheet_formatting(ws_ideal_solutions, ideal_solutions_headers, ideal_solutions_data)
            # Ensure numeric format for ideal values
            for r_idx in range(2, ws_ideal_solutions.max_row + 1):
                for c_idx in range(2, ws_ideal_solutions.max_column + 1): # Skip 'Type' column
                    cell = ws_ideal_solutions.cell(row=r_idx, column=c_idx)
                    if isinstance(cell.value, (float, np.floating)):
                        cell.number_format = "0.000"
                        cell.alignment = openpyxl.styles.Alignment(horizontal="right")
                    elif isinstance(cell.value, str) and cell.value.replace('.', '', 1).isdigit(): # Handle string floats
                        cell.number_format = "0.000"
                        cell.alignment = openpyxl.styles.Alignment(horizontal="right")

        # ----------------------------------------------------
        # SHEET 9: TOPSIS_RANKING
        # ----------------------------------------------------
        if topsis_ranking_df is not None:
            ws_topsis_ranking = wb.create_sheet(title="TOPSIS_RANKING")
            topsis_ranking_headers = topsis_ranking_df.columns.tolist()
            # Reset index to make 'path_id' a regular column for export
            topsis_ranking_rows = topsis_ranking_df.reset_index().values.tolist()
            # Prepend 'path_id' to headers
            topsis_ranking_headers.insert(0, 'path_id')
            apply_sheet_formatting(ws_topsis_ranking, topsis_ranking_headers, topsis_ranking_rows)


        # Save and log
        wb.save(filename)
        logger.info(f"Geographically aligned report successfully saved at: {filename}")
        return filename


    def generate_path_candidates(self, all_nodes: List[Any]) -> List[PathCandidate]:
        """
        Processes raw nodes from database, separates them into FEDGE and EDGE layers...
        """
        logger.info("Starting Path Candidates generation and metrics aggregation")
        
        # 1. Load configurations using the correct NetworkService static method
        config = NetworkService._load_config()
        weights = config["scoring_weights"]
        lat_factors = config["latency_factors"]
        smu_ref = config["smu_reference"]        
        utsw_ref = config["network_anchors"]["utsw"]
        lat_f_micro = lat_factors["fedge_microwave"]
        lat_f_fiber = lat_factors["edge_fiber"]
        
        # Fixed reference coordinates
        smu_coords = (smu_ref["lat"], smu_ref["lon"])
        utsw_coords = (utsw_ref["latitude"], utsw_ref["longitude"])
        
        # 2. Separate nodes into FEDGE and EDGE layers based on their "Role" field
        fedge_nodes = []
        edge_nodes = []
        
        for node in all_nodes:
            # Safely extract the role attribute or dict key, making it case-insensitive just in case
            node_role = getattr(node, 'role', '') or node.get('role', '')
            node_role_str = str(node_role).strip()
            
            if node_role_str == 'FEServer':
                fedge_nodes.append(node)
            elif node_role_str == 'EdgeServer':
                edge_nodes.append(node)
                
        logger.info(f"Layer separation complete: Found {len(fedge_nodes)} FEDGE nodes (FEServer) and {len(edge_nodes)} EDGE nodes (EdgeServer)")
        
        path_candidates = []
        
        # Helper function to parse formatted string data back to numeric values for math operations
        def clean_metric(val: Any) -> float:
            if isinstance(val, str):
                return float(val.replace(',', ''))
            return float(val)

        # 3. Cross-combine all FEDGE and EDGE nodes to create the paths (O(N*M))
        for fe in fedge_nodes:
            fe_lat = float(getattr(fe, 'latitude', 0.0) or fe.get('latitude', 0.0))
            fe_lon = float(getattr(fe, 'longitude', 0.0) or fe.get('longitude', 0.0))
            fe_id = getattr(fe, 'id', '') or fe.get('id', '')
            
            # Clean FEDGE hardware values
            fe_cpu = clean_metric(getattr(fe, 'cpu', 0.0) or fe.get('cpu', 0.0))
            fe_ram = clean_metric(getattr(fe, 'ramava', 0.0) or fe.get('ramava', 0.0))
            fe_disk = clean_metric(getattr(fe, 'diskava', 0.0) or fe.get('diskava', 0.0))
            fe_iops = clean_metric(getattr(fe, 'iops', 0.0) or fe.get('iops', 0.0))
            fe_bw = clean_metric(getattr(fe, 'bw', 0.0) or fe.get('bw', 0.0))
            
            for ed in edge_nodes:
                ed_lat = float(getattr(ed, 'latitude', 0.0) or ed.get('latitude', 0.0))
                ed_lon = float(getattr(ed, 'longitude', 0.0) or ed.get('longitude', 0.0))
                ed_id = getattr(ed, 'id', '') or ed.get('id', '')
                
                # Clean EDGE hardware values
                ed_cpu = clean_metric(getattr(ed, 'cpu', 0.0) or ed.get('cpu', 0.0))
                ed_ram = clean_metric(getattr(ed, 'ramava', 0.0) or ed.get('ramava', 0.0))
                ed_disk = clean_metric(getattr(ed, 'diskava', 0.0) or ed.get('diskava', 0.0))
                ed_iops = clean_metric(getattr(ed, 'iops', 0.0) or ed.get('iops', 0.0))
                ed_bw = clean_metric(getattr(ed, 'bw', 0.0) or ed.get('bw', 0.0))
                
                # 4. Geodetic calculations per hop (using Haversine)
                # Hop 1: SMU -> FEDGE (Microwave)
                d1 = NetworkService.calculate_haversine(smu_coords[0], smu_coords[1], fe_lat, fe_lon, unit='miles')
                lat1 = d1 * lat_f_micro
                
                # Hop 2: FEDGE -> EDGE (Fiber)
                d2 = NetworkService.calculate_haversine(fe_lat, fe_lon, ed_lat, ed_lon, unit='miles')
                lat2 = d2 * lat_f_fiber
                
                # Hop 3: EDGE -> UTSW (Fiber)
                d3 = NetworkService.calculate_haversine(ed_lat, ed_lon, utsw_coords[0], utsw_coords[1], unit='miles')
                lat3 = d3 * lat_f_fiber
                
                total_latency = round(lat1 + lat2 + lat3, 3)
                
                # 5. Bottleneck and Aggregation logic for Hardware Metrics
                # - CPU: Worst case scenario or maximum utilization between the nodes
                combined_cpu = max(fe_cpu, ed_cpu)
                # - RAM and Disk Free %: Combined bottleneck is the minimum space available
                combined_ram = min(fe_ram, ed_ram)
                combined_disk = min(fe_disk, ed_disk)
                # - IOPS and Bandwidth: Throughput bottleneck is the lowest capacity link/node
                combined_iops = min(fe_iops, ed_iops)
                combined_bw = min(fe_bw, ed_bw)
                
                metrics_payload = {
                    'latency': total_latency,
                    'cpu': combined_cpu,
                    'iops': combined_iops,
                    'ram': combined_ram,
                    'bw': combined_bw,
                    'disk': combined_disk
                }
                
                # Instantiating the candidate
                candidate = PathCandidate(fe_id=fe_id, edge_id=ed_id, metrics=metrics_payload)
                
                # Store raw source data for comprehensive Excel reporting
                candidate.raw_source = {
                    'fe': fe.model_dump() if hasattr(fe, 'model_dump') else fe,
                    'ed': ed.model_dump() if hasattr(ed, 'model_dump') else ed,
                    'hops': {
                        'd1_smu_fe': d1,
                        'lat1': lat1,
                        'd2_fe_ed': d2,
                        'lat2': lat2,
                        'd3_ed_utsw': d3,
                        'lat3': lat3,
                        'total_distance': round(d1 + d2 + d3, 3)
                    }
                }
                path_candidates.append(candidate)
                
        logger.info(f"Successfully generated {len(path_candidates)} combined Path Candidates")
        return path_candidates        

        
    @staticmethod
    def export_to_excel(
        candidates: List[PathCandidate], 
        final_df: pd.DataFrame, 
        norm_df: pd.DataFrame, 
        weighted_df: pd.DataFrame, 
        ideal_positive: dict, 
        ideal_negative: dict, 
        filename: str = "c3_pareto_topsis_report.xlsx",
        raw_df_log: pd.DataFrame = None,
        norm_df_log: pd.DataFrame = None,
        weighted_df_log: pd.DataFrame = None,
        ideal_solutions_data: list = None,
        ideal_solutions_headers: list = None,
        topsis_ranking_df: pd.DataFrame = None
    ) -> str:
        """
        Generates an enterprise-grade Excel workbook for C3-Pareto-TOPSIS mirroring
        the aesthetic design, grid layout, percentages scale, and typography of the original algorithm.
        Ensures rows are alphabetically ordered by FEDGE Site and EDGE Site keys.
        """
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter
        import numpy as np
        import pandas as pd

        wb = openpyxl.Workbook()
        
        # --- AESTHETIC CONFIGURATION (CONSOLAS 10 & GRID STYLE) ---
        font_header = Font(name="Consolas", size=10, bold=True, color="FFFFFF")
        font_data = Font(name="Consolas", size=10)
        
        fill_header = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
        fill_zebra = PatternFill(start_color="F7F9FC", end_color="F7F9FC", fill_type="solid")
        
        grid_border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin")
        )

        # Pareto Efficiency highlighting fills
        good_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid") # Light Green
        bad_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid") # Light Red

        def apply_sheet_formatting(ws, headers, row_data_list):
            """Internal helper to apply standard formatting, grid borders, freeze panes, and auto-fit columns."""
            ws.views.sheetView[0].showGridLines = True
            ws.freeze_panes = "A2"  # Freeze header row
            
            # Write and format Headers
            for col_idx, header_text in enumerate(headers, start=1):
                cell = ws.cell(row=1, column=col_idx, value=header_text)
                cell.font = font_header
                cell.fill = fill_header
                cell.alignment = openpyxl.styles.Alignment(horizontal="center", vertical="center", wrap_text=False)
                cell.border = grid_border
            
            # Write and format Data Rows
            for r_idx, row_values in enumerate(row_data_list, start=2):
                is_zebra = (r_idx % 2 == 0)
                for c_idx, val in enumerate(row_values, start=1):
                    cell = ws.cell(row=r_idx, column=c_idx, value=val)
                    cell.font = font_data
                    cell.border = grid_border
                    
                    if is_zebra:
                        cell.fill = fill_zebra

                    # Highlight 'pareto_efficient' column with Green/Red
                    if headers[c_idx-1] == 'pareto_efficient':
                        if str(val).upper() == 'TRUE':
                            cell.fill = good_fill
                        elif str(val).upper() == 'FALSE':
                            cell.fill = bad_fill
                        cell.alignment = openpyxl.styles.Alignment(horizontal="center")
                        
                    # Standard numeric and text layout configuration
                    if isinstance(val, (int, float, np.number)):
                        cell.alignment = openpyxl.styles.Alignment(horizontal="right")
                        if isinstance(val, (float, np.floating)):
                            cell.number_format = "0.000" if any(term in headers[c_idx-1] for term in ["Score", "SCORE", "Distance", "Latency", "Dist", "Lat"]) else "0.00"
                    elif isinstance(val, (bool, np.bool_)):
                        cell.alignment = openpyxl.styles.Alignment(horizontal="center")
                    else:
                        cell.alignment = openpyxl.styles.Alignment(horizontal="left")
            
            # Dynamic Column Auto-Adjustment Fit
            for col in ws.columns:
                max_len = 0
                col_letter = get_column_letter(col[0].column)
                for cell in col:
                    if cell.value is not None:
                        max_len = max(max_len, len(str(cell.value)))
                ws.column_dimensions[col_letter].width = max(max_len + 3, 11)

        # Map candidates by their ID to extract original metrics cleanly
        candidates_map = {c.path_id: c for c in candidates}

        # ----------------------------------------------------
        # PRE-PROCESSING: Sort DataFrame by FEDGE Site & EDGE Site
        # ----------------------------------------------------
        sorting_records = []
        for path_id, row in final_df.iterrows():
            fe_id, edge_id = path_id.split("==")
            c = candidates_map[path_id]
            raw_source_data = getattr(c, 'raw_source', None)
            fe_site = raw_source_data['fe'].get('site', fe_id) if raw_source_data else fe_id
            ed_site = raw_source_data['ed'].get('site', edge_id) if raw_source_data else edge_id
            
            sorting_records.append({
                'path_id': path_id,
                'fedge_site': fe_site,
                'edge_site': ed_site,
                'C_score': row['C_score']
            })
            
        sorting_df = pd.DataFrame(sorting_records)
        sorting_df = sorting_df.sort_values(by=['fedge_site', 'edge_site'], ascending=[True, True])

        # ----------------------------------------------------
        # SHEET 1: InputData
        # ----------------------------------------------------
        ws_input = wb.active
        ws_input.title = "InputData"
        
        input_headers = [
            "Region", "Site", "Device UUID", "Status", "Role", "CNF", 
            "CPU Usage %", "RAM free %", "Disk free %", "IOPS", "Bandwidth (Gbps)", 
            "Manufacturer", "Platform", "Cluster", "Location", "ShortName", "Type", "Latitude", "Longitude"
        ]
        
        input_rows = []
        seen_nodes = set()
        
        for c in candidates:
            fe_id, edge_id = c.fe_id, c.edge_id
            raw_source_data = getattr(c, 'raw_source', None)
            
            fe_info = raw_source_data['fe'] if (raw_source_data and 'fe' in raw_source_data) else c.metrics
            ed_info = raw_source_data['ed'] if (raw_source_data and 'ed' in raw_source_data) else c.metrics
            
            if fe_id not in seen_nodes:
                seen_nodes.add(fe_id)
                input_rows.append([
                    "DFW", fe_info.get('site', fe_id), fe_id, fe_info.get('status', 'Active'), "FEServer", 1,
                    float(fe_info.get('cpu', 0)), float(fe_info.get('ramava', fe_info.get('ram', 0))), float(fe_info.get('diskava', fe_info.get('disk', 0))),
                    int(str(fe_info.get('iops', 0)).replace(',', '')), float(fe_info.get('bw', 0)),
                    fe_info.get('manufacturer', 'HPE'), fe_info.get('platform', 'RHOCP'), 
                    fe_info.get('cluster', 'RT_CaaS_CS'), fe_info.get('location', 'Unknown Location'), 
                    fe_info.get('shortname', 'N/A'), "DL360", 
                    float(fe_info.get('latitude', 0.0)), float(fe_info.get('longitude', 0.0))
                ])
            if edge_id not in seen_nodes:
                seen_nodes.add(edge_id)
                input_rows.append([
                    "DFW", ed_info.get('site', edge_id), edge_id, ed_info.get('status', 'Active'), "EdgeServer", 0,
                    float(ed_info.get('cpu', 0)), float(ed_info.get('ramava', ed_info.get('ram', 0))), float(ed_info.get('diskava', ed_info.get('disk', 0))),
                    int(str(ed_info.get('iops', 0)).replace(',', '')), float(ed_info.get('bw', 0)),
                    ed_info.get('manufacturer', 'HPE'), ed_info.get('platform', 'WRCP'), 
                    ed_info.get('cluster', 'RT_CaaS_EDC'), ed_info.get('location', 'Unknown Location'), 
                    ed_info.get('shortname', 'N/A'), "e910t", 
                    float(ed_info.get('latitude', 0.0)), float(ed_info.get('longitude', 0.0))
                ])
                
        # Sort InputData alphabetically by the 'Site' column (index 1)
        input_rows.sort(key=lambda x: str(x[1]))
        apply_sheet_formatting(ws_input, input_headers, input_rows)

        # ----------------------------------------------------
        # SHEET 2: OutputResults
        # ----------------------------------------------------
        ws_output = wb.create_sheet(title="OutputResults")
        output_headers = [
            "Region", "FEDGE Site", "FEDGE UUID", "EDGE Site", "EDGE UUID", "Status", "CNF", 
            "Path Latency", "Lat Score", "Path CPU Usage %", "CPU Score", "Path RAM free %", "RAM Score", 
            "Path Disk free %", "Disk Score", "Path IOPS", "IOPS Score", "Path BW", "BW Score", 
            "TOTAL SCORE", "Manufacturer", "Platform", "Cluster", "Location", "Total Distance"
        ]
        
        output_rows = []
        for idx, sort_row in sorting_df.iterrows():
            path_id = sort_row['path_id']
            fe_id, edge_id = path_id.split("==")
            c = candidates_map[path_id]
            raw_source_data = getattr(c, 'raw_source', None)
            fe_info = raw_source_data['fe'] if raw_source_data else {}
            
            hop_data = raw_source_data.get('hops', {}) if raw_source_data else {}
            total_dist_val = hop_data.get('total_distance', 0.0)
            
            w_row = weighted_df.loc[path_id]
            final_score_row = final_df.loc[path_id]
            
            output_rows.append([
                "DFW", sort_row['fedge_site'], fe_id, sort_row['edge_site'], edge_id,
                "Active", 1, 
                float(c.metrics['latency']), float(w_row['latency_value']),
                float(c.metrics['cpu']), float(w_row['cpu_usage']),
                float(c.metrics['ram']), float(w_row['ramfree_value']),
                float(c.metrics['disk']), float(w_row['diskfree_value']),
                int(c.metrics['iops']), float(w_row['iops_value']),
                float(c.metrics['bw']), float(w_row['bw_value']),
                float(final_score_row["C_score"]), 
                fe_info.get('manufacturer', 'HPE'), fe_info.get('platform', 'RHOCP'), 
                fe_info.get('cluster', 'RT_CaaS'), fe_info.get('location', 'Location Details'), 
                float(total_dist_val)
            ])
            
        apply_sheet_formatting(ws_output, output_headers, output_rows)

        # ----------------------------------------------------
        # SHEET 3: OutputResultsDetails
        # ----------------------------------------------------
        ws_details = wb.create_sheet(title="OutputResultsDetails")
        details_headers = [
            "Region", "FEDGE Site", "FEDGE UUID", "EDGE Site", "EDGE UUID", "Status", "CNF",
            "Dist SMU -> FE", "Lat SMU -> FE", "Dist FE -> EDGE", "Lat FE -> EDGE",
            "Dist EDGE -> UTSW", "Lat EDGE -> UTSW", "Total Distance",
            "Path Latency", "Lat Score", 
            "FEDGE CPU Usage %", "EDGE CPU Usage %", "Path CPU Usage %", "CPU Score", 
            "FEDGE RAM Free %", "EDGE RAM Free %", "Path RAM free %", "RAM Score", 
            "FEDGE Disk Free %", "EDGE Disk Free %", "Path Disk free %", "Disk Score", 
            "FEDGE IOPS", "EDGE IOPS", "Path IOPS", "IOPS Score", 
            "FEDGE Bandwidth (Gbps)", "EDGE Bandwidth (Gbps)", "Path BW", "BW Score", 
            "TOTAL SCORE", "Manufacturer", "Platform", "Cluster" # "Location" was removed here
        ]

        details_rows = []
        # Helper to parse numeric values from raw info (handling potential strings with commas)
        def clean_val(info, key):
            val = info.get(key, 0.0)
            if isinstance(val, str):
                return float(val.replace(',', ''))
            return float(val)

        for idx, sort_row in sorting_df.iterrows():
            path_id = sort_row['path_id']
            fe_id, edge_id = path_id.split("==")
            c = candidates_map[path_id]
            raw_source_data = getattr(c, 'raw_source', None)
            fe_info = raw_source_data['fe'] if raw_source_data else {}
            ed_info = raw_source_data['ed'] if raw_source_data else {}

            hop_data = raw_source_data.get('hops', {}) if raw_source_data else {}

            w_row = weighted_df.loc[path_id]
            final_score_row = final_df.loc[path_id]

            details_rows.append([
                "DFW", sort_row['fedge_site'], fe_id, sort_row['edge_site'], edge_id,
                "Active", 1,
                float(hop_data.get('d1_smu_fe', 0.0)), float(hop_data.get('lat1', 0.0)),
                float(hop_data.get('d2_fe_ed', 0.0)), float(hop_data.get('lat2', 0.0)),
                float(hop_data.get('d3_ed_utsw', 0.0)), float(hop_data.get('lat3', 0.0)),
                float(hop_data.get('total_distance', 0.0)),
                float(c.metrics['latency']), float(w_row['latency_value']),
                clean_val(fe_info, 'cpu'), clean_val(ed_info, 'cpu'),
                float(c.metrics['cpu']), float(w_row['cpu_usage']),
                clean_val(fe_info, 'ramava'), clean_val(ed_info, 'ramava'),
                float(c.metrics['ram']), float(w_row['ramfree_value']),
                clean_val(fe_info, 'diskava'), clean_val(ed_info, 'diskava'),
                float(c.metrics['disk']), float(w_row['diskfree_value']),
                int(clean_val(fe_info, 'iops')), int(clean_val(ed_info, 'iops')),
                int(c.metrics['iops']), float(w_row['iops_value']),
                clean_val(fe_info, 'bw'), clean_val(ed_info, 'bw'),
                float(c.metrics['bw']), float(w_row['bw_value']),
                float(final_score_row["C_score"]),
                fe_info.get('manufacturer', 'HPE'), fe_info.get('platform', 'RHOCP'),
                fe_info.get('cluster', 'RT_CaaS')
            ])
            
        apply_sheet_formatting(ws_details, details_headers, details_rows)

        # Define custom fills and fonts for conditional formatting
        yellow_fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
        red_font = Font(color="FF0000", bold=True)
        green_fill = PatternFill(start_color="00FF00", end_color="00FF00", fill_type="solid")
        orange_fill = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")
        blue_fill = PatternFill(start_color="0000FF", end_color="0000FF", fill_type="solid") # New blue color
        white_font = Font(color="FFFFFF", bold=True) # New white font

        # Helper to apply conditional formatting
        def apply_highlight(ws, headers, column_name, criteria, fill, font=None):
            try:
                col_idx = headers.index(column_name) + 1 # Excel columns are 1-indexed
            except ValueError:
                logger.warning(f"Column '{column_name}' not found for highlighting.")
                return

            values = []
            for r_idx in range(2, ws.max_row + 1): # Data starts from row 2
                cell_value = ws.cell(row=r_idx, column=col_idx).value
                if isinstance(cell_value, (int, float)):
                    values.append(cell_value)
            
            if not values:
                return

            target_value = None
            if criteria == "min":
                target_value = min(values)
            elif criteria == "max":
                target_value = max(values)
            
            if target_value is None:
                return

            for r_idx in range(2, ws.max_row + 1):
                cell = ws.cell(row=r_idx, column=col_idx)
                # Ensure we compare numbers to numbers, and handle potential rounding issues for floats
                if isinstance(cell.value, (int, float)):
                    # For floats, compare with a small tolerance
                    if isinstance(target_value, float):
                        if abs(cell.value - target_value) < 1e-9: # Using a small epsilon for float comparison
                            cell.fill = fill
                            if font:
                                cell.font = font
                    else: # For integers or exact matches
                        if cell.value == target_value:
                            cell.fill = fill
                            if font:
                                cell.font = font

        # Apply Yellow/Red highlights
        yellow_red_highlights = [
            ("Dist SMU -> FE", "min"), ("Dist FE -> EDGE", "min"), ("Dist EDGE -> UTSW", "min"),
            ("Path Latency", "min"), ("FEDGE CPU Usage %", "min"), ("EDGE CPU Usage %", "min"),
            ("FEDGE RAM Free %", "max"), ("EDGE RAM Free %", "max"), ("FEDGE Disk Free %", "max"),
            ("EDGE Disk Free %", "max"), ("FEDGE IOPS", "max"), ("EDGE IOPS", "max"),
            ("FEDGE Bandwidth (Gbps)", "max"), ("EDGE Bandwidth (Gbps)", "max")
        ]
        for col_name, criteria in yellow_red_highlights:
            apply_highlight(ws_details, details_headers, col_name, criteria, yellow_fill, red_font)

        # Apply Green highlights
        green_highlights = [
            ("Total Distance", "min"), ("Path CPU Usage %", "min"),
            ("Path RAM free %", "max"), ("Path Disk free %", "max"),
            ("Path IOPS", "max"), ("Path BW", "max")
        ]
        for col_name, criteria in green_highlights:
            apply_highlight(ws_details, details_headers, col_name, criteria, green_fill)

        # Apply Orange highlights
        orange_highlights = [
            ("Lat Score", "max"), ("CPU Score", "max"), ("RAM Score", "max"),
            ("Disk Score", "max"), ("IOPS Score", "max"), ("BW Score", "max")
        ]
        for col_name, criteria in orange_highlights:
            apply_highlight(ws_details, details_headers, col_name, criteria, orange_fill)

        # ----------------------------------------------------
        # SHEET 4: OutputResultsDetails_Sorted
        # ----------------------------------------------------
        ws_details_sorted = wb.create_sheet(title="OutputResultsDetails_Sorted")

        # Sort details_rows by 'TOTAL SCORE' in descending order
        total_score_col_idx = details_headers.index("TOTAL SCORE")
        details_rows_sorted = sorted(details_rows, key=lambda x: x[total_score_col_idx], reverse=True)

        apply_sheet_formatting(ws_details_sorted, details_headers, details_rows_sorted)

        # Apply the same yellow/red, green, orange highlights to the sorted sheet
        for col_name, criteria in yellow_red_highlights:
            apply_highlight(ws_details_sorted, details_headers, col_name, criteria, yellow_fill, red_font)
        for col_name, criteria in green_highlights:
            apply_highlight(ws_details_sorted, details_headers, col_name, criteria, green_fill)
        for col_name, criteria in orange_highlights:
            apply_highlight(ws_details_sorted, details_headers, col_name, criteria, orange_fill)

        # Apply blue/white highlight to the top row of the sorted sheet, only if background is white/zebra
        top_row_idx = 2 # Data starts at row 2
        for c_idx in range(1, ws_details_sorted.max_column + 1):
            cell = ws_details_sorted.cell(row=top_row_idx, column=c_idx)
            current_fill_color_rgb = cell.fill.start_color.rgb
            # Check if the cell background color is the default (white '00000000') or zebra ('00F7F9FC')
            if current_fill_color_rgb in ['00000000', '00F7F9FC', None]:
                cell.fill = blue_fill
                cell.font = white_font

        # ----------------------------------------------------
        # SHEET 5: RAW_DATA-Combined Paths
        # ----------------------------------------------------
        if raw_df_log is not None:
            ws_raw_data = wb.create_sheet(title="RAW_DATA-Combined Paths")
            # Include path_id as first column via reset_index() and exclude 'pareto_efficient'
            df_to_export = raw_df_log.reset_index()
            raw_data_headers = [col for col in df_to_export.columns if col != 'pareto_efficient']
            raw_data_rows = df_to_export[raw_data_headers].values.tolist()
            apply_sheet_formatting(ws_raw_data, raw_data_headers, raw_data_rows)

        # ----------------------------------------------------
        # SHEET 6: NORMALIZED_MATRIX
        # ----------------------------------------------------
        if norm_df_log is not None:
            ws_norm_matrix = wb.create_sheet(title="NORMALIZED_MATRIX")
            # Include path_id as first column
            df_to_export = norm_df_log.reset_index()
            norm_matrix_headers = df_to_export.columns.tolist()
            norm_matrix_rows = df_to_export.values.tolist()
            apply_sheet_formatting(ws_norm_matrix, norm_matrix_headers, norm_matrix_rows)

        # ----------------------------------------------------
        # SHEET 7: WEIGHTED_MATRIX
        # ----------------------------------------------------
        if weighted_df_log is not None:
            ws_weighted_matrix = wb.create_sheet(title="WEIGHTED_MATRIX")
            # Include path_id as first column
            df_to_export = weighted_df_log.reset_index()
            weighted_matrix_headers = df_to_export.columns.tolist()
            weighted_matrix_rows = df_to_export.values.tolist()
            apply_sheet_formatting(ws_weighted_matrix, weighted_matrix_headers, weighted_matrix_rows)

        # ----------------------------------------------------
        # SHEET 8: IDEAL_SOLUTIONS
        # ----------------------------------------------------
        if ideal_solutions_data is not None and ideal_solutions_headers is not None:
            ws_ideal_solutions = wb.create_sheet(title="IDEAL_SOLUTIONS")
            # The ideal_solutions_data is already a list of lists, ready for apply_sheet_formatting
            apply_sheet_formatting(ws_ideal_solutions, ideal_solutions_headers, ideal_solutions_data)
            # Ensure numeric format for ideal values
            for r_idx in range(2, ws_ideal_solutions.max_row + 1):
                for c_idx in range(2, ws_ideal_solutions.max_column + 1): # Skip 'Type' column
                    cell = ws_ideal_solutions.cell(row=r_idx, column=c_idx)
                    if isinstance(cell.value, (float, np.floating)):
                        cell.number_format = "0.000"
                        cell.alignment = openpyxl.styles.Alignment(horizontal="right")
                    elif isinstance(cell.value, str) and cell.value.replace('.', '', 1).isdigit(): # Handle string floats
                        cell.number_format = "0.000"
                        cell.alignment = openpyxl.styles.Alignment(horizontal="right")

        # ----------------------------------------------------
        # SHEET 9: TOPSIS_RANKING
        # ----------------------------------------------------
        if topsis_ranking_df is not None:
            ws_topsis_ranking = wb.create_sheet(title="TOPSIS_RANKING")
            topsis_ranking_headers = topsis_ranking_df.columns.tolist()
            # Reset index to make 'path_id' a regular column for export
            topsis_ranking_rows = topsis_ranking_df.reset_index().values.tolist()
            # Prepend 'path_id' to headers
            topsis_ranking_headers.insert(0, 'path_id')
            apply_sheet_formatting(ws_topsis_ranking, topsis_ranking_headers, topsis_ranking_rows)


        # Guardar y registrar
        wb.save(filename)
        logger.info(f"Geographically aligned report successfully saved at: {filename}")
        return filename

    @staticmethod
    def export_simulations_summary(summaries: List[Dict], overall_stats: Dict, filename: str) -> str:
        """
        Consolidates multiple simulation results into a single executive summary Excel file.
        """
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Border, Side
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Simulations Summary"
        
        headers = [
            "Sim #", "Timestamp", 
            "Orig Best Path", "Orig Fedge", "Orig Edge", "Orig Score", 
            "C3 Best Path", "C3 Fedge", "C3 Edge", "C3 Score"
        ]
        
        # Style Definitions
        f_header = Font(name="Consolas", size=10, bold=True, color="FFFFFF")
        fill_h = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
        f_data = Font(name="Consolas", size=10)
        border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
        
        # Set Headers
        for c_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=c_idx, value=h)
            cell.font = f_header
            cell.fill = fill_h
            cell.border = border
            
        # Set Data
        for r_idx, sim in enumerate(summaries, 2):
            summary = sim.get("comparison_summary", {})
            orig = summary.get("original_best", {})
            c3 = summary.get("c3_best", {})
            
            row_values = [
                sim.get("simulation_number"),
                sim.get("timestamp"),
                orig.get("path_id"),
                orig.get("fedge"),
                orig.get("edge"),
                orig.get("score"),
                c3.get("path_id"),
                c3.get("fedge"),
                c3.get("edge"),
                c3.get("score")
            ]
            
            for c_idx, val in enumerate(row_values, 1):
                cell = ws.cell(row=r_idx, column=c_idx, value=val)
                cell.font = f_data
                cell.border = border
                if isinstance(val, float):
                    cell.number_format = "0.000"
        
        # --- NEW SHEET: Comparison Analysis ---
        ws_analysis = wb.create_sheet(title="Comparison Analysis")

        # Helper to write a section title
        def write_section_title(ws, row, title, font=None, fill=None):
            cell = ws.cell(row=row, column=1, value=title)
            if font: cell.font = font
            if fill: cell.fill = fill
            return row + 1

        # Helper to write key-value pairs
        def write_key_value(ws, row, key, value, key_font=None, value_font=None):
            key_cell = ws.cell(row=row, column=1, value=key)
            value_cell = ws.cell(row=row, column=2, value=value)
            if key_font: key_cell.font = key_font
            if value_font: value_cell.font = value_font
            return row + 1

        # Helper to write a table of cases
        def write_cases_table(ws, start_row, cases, title_font=None, header_font=None, data_font=None, header_fill=None, border=None):
            if not cases:
                ws.cell(row=start_row, column=1, value="No cases in this category.").font = data_font
                return start_row + 2

            table_headers = [
                "Sim #",
                "Original Fedge", "Original Edge", "Original Path ID", "Original Score",
                "C3 Fedge", "C3 Edge", "C3 Path ID", "C3 Score"
            ]
            
            current_row = start_row
            for c_idx, h in enumerate(table_headers, 1):
                cell = ws.cell(row=current_row, column=c_idx, value=h)
                if header_font: cell.font = header_font
                if header_fill: cell.fill = header_fill
                if border: cell.border = border
            current_row += 1

            for case in cases:
                orig = case["original_choice"]
                c3 = case["c3_choice"]
                row_values = [
                    case["simulation_number"],
                    orig["fedge"], orig["edge"], orig["path_id"], orig["score"],
                    c3["fedge"], c3["edge"], c3["path_id"], c3["score"]
                ]
                for c_idx, val in enumerate(row_values, 1):
                    cell = ws.cell(row=current_row, column=c_idx, value=val)
                    if data_font: cell.font = data_font
                    if border: cell.border = border
                    if isinstance(val, float):
                        cell.number_format = "0.000"
                current_row += 1
            return current_row + 1 # Add a blank row after table

        # Helper to write ranking tables
        def write_ranking_table(ws, start_row, rankings, title, header_font=None, data_font=None, header_fill=None, border=None):
            current_row = write_section_title(ws, start_row, title, header_font, header_fill)
            if not rankings:
                ws.cell(row=current_row, column=1, value="No ranking data available.").font = data_font
                return current_row + 2

            table_headers = ["Rank", "Item", "Count", "Percentage"]
            
            for c_idx, h in enumerate(table_headers, 1):
                cell = ws.cell(row=current_row, column=c_idx, value=h)
                if header_font: cell.font = header_font
                if header_fill: cell.fill = header_fill
                if border: cell.border = border
            current_row += 1

            for rank, entry in enumerate(rankings, 1):
                row_values = [
                    rank,
                    entry["item"],
                    entry["count"],
                    entry["percentage"]
                ]
                for c_idx, val in enumerate(row_values, 1):
                    cell = ws.cell(row=current_row, column=c_idx, value=val)
                    if data_font: cell.font = data_font
                    if border: cell.border = border
                    if isinstance(val, float):
                        cell.number_format = "0.00%" # For percentage
                    elif isinstance(val, str) and "%" in val: # Fallback if calc_pct returns string
                        cell.number_format = "0.00%"
                current_row += 1
            return current_row + 1 # Add a blank row after table


        current_row = 1
        # Section: Overall Statistics
        current_row = write_section_title(ws_analysis, current_row, "Overall Simulation Statistics", f_header, fill_h)
        current_row = write_key_value(ws_analysis, current_row, "Total Successful Simulations:", overall_stats["total_successful_simulations"], f_data, f_data)
        current_row = write_key_value(ws_analysis, current_row, "Same Result Count:", overall_stats["same_result"]["count"], f_data, f_data)
        current_row = write_key_value(ws_analysis, current_row, "Same Result Percentage:", overall_stats["same_result"]["percentage"], f_data, f_data)
        current_row = write_key_value(ws_analysis, current_row, "Different Result Count:", overall_stats["different_result"]["count"], f_data, f_data)
        current_row = write_key_value(ws_analysis, current_row, "Different Result Percentage:", overall_stats["different_result"]["percentage"], f_data, f_data)
        current_row += 2

        # Section: Cases with Same Result
        current_row = write_section_title(ws_analysis, current_row, "Cases where Original and C3-Pareto-TOPSIS results were the same", f_header, fill_h)
        current_row = write_cases_table(ws_analysis, current_row, overall_stats["same_result"]["cases"], f_header, f_header, f_data, fill_h, border)
        current_row += 2

        # Section: Cases with Different Result - Neither FEDGE nor EDGE Match
        current_row = write_section_title(ws_analysis, current_row, "Cases where neither FEDGE nor EDGE matched", f_header, fill_h)
        current_row = write_cases_table(ws_analysis, current_row, overall_stats["different_result"]["analysis_of_mismatches"]["neither_fedge_nor_edge_match"]["cases"], f_header, f_header, f_data, fill_h, border)
        current_row += 2

        # Section: Cases with Different Result - Same FEDGE Only
        current_row = write_section_title(ws_analysis, current_row, "Cases where only FEDGE matched", f_header, fill_h)
        current_row = write_cases_table(ws_analysis, current_row, overall_stats["different_result"]["analysis_of_mismatches"]["same_fedge_only"]["cases"], f_header, f_header, f_data, fill_h, border)
        current_row += 2

        # Section: Cases with Different Result - Same EDGE Only
        current_row = write_section_title(ws_analysis, current_row, "Cases where only EDGE matched", f_header, fill_h)
        current_row = write_cases_table(ws_analysis, current_row, overall_stats["different_result"]["analysis_of_mismatches"]["same_edge_only"]["cases"], f_header, f_header, f_data, fill_h, border)
        current_row += 2

        # NEW SECTIONS FOR RANKINGS
        current_row = write_ranking_table(ws_analysis, current_row, overall_stats["original_algorithm_rankings"]["path_id_ranking"], "Original Algorithm: Path ID Ranking", f_header, f_data, fill_h, border)
        current_row = write_ranking_table(ws_analysis, current_row, overall_stats["original_algorithm_rankings"]["fedge_ranking"], "Original Algorithm: FEDGE Ranking", f_header, f_data, fill_h, border)
        current_row = write_ranking_table(ws_analysis, current_row, overall_stats["original_algorithm_rankings"]["edge_ranking"], "Original Algorithm: EDGE Ranking", f_header, f_data, fill_h, border)
        current_row = write_ranking_table(ws_analysis, current_row, overall_stats["c3_pareto_topsis_algorithm_rankings"]["path_id_ranking"], "C3-Pareto-TOPSIS Algorithm: Path ID Ranking", f_header, f_data, fill_h, border)
        current_row = write_ranking_table(ws_analysis, current_row, overall_stats["c3_pareto_topsis_algorithm_rankings"]["fedge_ranking"], "C3-Pareto-TOPSIS Algorithm: FEDGE Ranking", f_header, f_data, fill_h, border)
        current_row = write_ranking_table(ws_analysis, current_row, overall_stats["c3_pareto_topsis_algorithm_rankings"]["edge_ranking"], "C3-Pareto-TOPSIS Algorithm: EDGE Ranking", f_header, f_data, fill_h, border)

        # Auto-fit columns for the new sheet
        for col in ws_analysis.columns:
            max_len = 0
            col_letter = col[0].column_letter
            for cell in col:
                try:
                    if cell.value:
                        max_len = max(max_len, len(str(cell.value)))
                except:
                    pass
            adjusted_width = (max_len + 2)
            ws_analysis.column_dimensions[col_letter].width = adjusted_width

        # Auto-fit columns
        for col in ws.columns:
            max_len = 0
            for cell in col:
                if cell.value: max_len = max(max_len, len(str(cell.value)))
            ws.column_dimensions[col[0].column_letter].width = max_len + 3
            
        wb.save(filename)
        return filename

    @staticmethod
    def generate_simulation_plots(overall_stats: Dict, filename: str):
        """
        Generates a diagnostic dashboard image for algorithm comparison.
        """
        try:
            # Setup the figure with 3 subplots
            sns.set_theme(style="whitegrid")
            fig = plt.figure(figsize=(16, 10))
            fig.suptitle(f"Algorithm Comparison Dashboard - {overall_stats['total_successful_simulations']} Simulations", 
                         fontsize=20, fontweight='bold', y=0.98)

            # 1. PIE CHART: Overall Convergence
            ax1 = plt.subplot(2, 2, 1)
            same = int(overall_stats["same_result"]["count"])
            diff = int(overall_stats["different_result"]["count"])
            
            if same + diff > 0:
                colors = ['#4CAF50', '#F44336']
                ax1.pie([same, diff], labels=['Same Path', 'Different Path'], autopct='%1.1f%%', 
                        startangle=140, colors=colors, explode=(0.05, 0), shadow=True)
                ax1.set_title("Path Selection Convergence", fontsize=14, fontweight='bold')

            # 2. BAR CHART: Mismatch Analysis
            ax2 = plt.subplot(2, 2, 2)
            mismatch_data = overall_stats["different_result"]["analysis_of_mismatches"]
            m_labels = ['Neither Match', 'Same FEDGE', 'Same EDGE']
            m_counts = [
                mismatch_data["neither_fedge_nor_edge_match"]["count"],
                mismatch_data["same_fedge_only"]["count"],
                mismatch_data["same_edge_only"]["count"]
            ]
            sns.barplot(x=m_labels, y=m_counts, ax=ax2, palette="viridis", hue=m_labels, legend=False)
            ax2.set_title("Root Cause of Differences", fontsize=14, fontweight='bold')
            ax2.set_ylabel("Occurrences")

            # 3. COMPARATIVE BAR CHART: Top Paths
            ax3 = plt.subplot(2, 1, 2)
            
            # Extract Top 5 from Original
            orig_ranks = overall_stats["original_algorithm_rankings"]["path_id_ranking"][:5]
            c3_ranks = overall_stats["c3_pareto_topsis_algorithm_rankings"]["path_id_ranking"][:5]
            
            # Prepare data for plotting
            plot_data = []
            for item in orig_ranks:
                # Shorten path_id for display if too long
                label = item['item'].replace('==', '\nvs\n')
                plot_data.append({'Path': label, 'Count': item['count'], 'Algorithm': 'Original'})
            for item in c3_ranks:
                label = item['item'].replace('==', '\nvs\n')
                plot_data.append({'Path': label, 'Count': item['count'], 'Algorithm': 'C3-Pareto-TOPSIS'})
            
            if plot_data:
                df_plot = pd.DataFrame(plot_data)
                sns.barplot(data=df_plot, x='Path', y='Count', hue='Algorithm', ax=ax3, palette=['#1D4ED8', '#DC2626'])
                ax3.set_title("Winner Popularity Comparison (Top 5 Paths)", fontsize=14, fontweight='bold')
                ax3.set_xlabel("Network Path (FEDGE vs EDGE)")
                ax3.set_ylabel("Selection Count")
                plt.xticks(rotation=0)

            plt.tight_layout(rect=[0, 0.03, 1, 0.95])
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            plt.savefig(filename, dpi=150)
            plt.close(fig)
            logger.info(f"Comparison dashboard saved to {filename}")
            
        except Exception as e:
            logger.error(f"Failed to generate simulation plots: {e}")
            if 'fig' in locals(): plt.close(fig)