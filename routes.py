"""
UPF Optimal Placer (UOP) - v2.0

File: routes.py

Description:
Defines the RESTful API routing layer, mapping HTTP endpoints to business logic and coordinating simulation workflows.

@authors: R. Rodriguez <raul.rodriguez@hcltech.com>, Y. Aldoori <yaseen.aldoori@windriver.com>, L. Popokh <leo.popokh@asato.ai>
@license: MIT
@copyright: Copyright (c) 2026 R. Rodriguez, Y. Aldoori, L. Popokh
"""

# Standard library imports
import time
import os
from datetime import datetime
from typing import List, Optional
from collections import defaultdict

# Third-party libraries
from loguru import logger
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

# Local application imports
from database import DB_PATH
from schemas import NodeBase, SiteBase, SiteDistanceResponse
from services import NetworkService, PlacementService

# Initialize APIRouter
router = APIRouter()

# Initialize Services
network_service = NetworkService()
placement_service = PlacementService()

@router.get("/", tags=["Health"])
async def health_check():
    """
    Service health check and basic info.
    """
    return {
        "status": "online",
        "version": "2.0.0",
        "database": str(DB_PATH)
    }

@router.get("/api/v1/nodes", response_model=List[NodeBase], tags=["Inventory"])
async def get_nodes():
    """
    Retrieve all network nodes.
    """
    try:
        nodes = network_service.get_all_nodes()
        return nodes
    except Exception as e:
        loguru.logger.error(f"Error retrieving nodes: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/api/v1/nodes/{node_id}", response_model=NodeBase, tags=["Inventory"])
async def get_node(node_id: int):
    """
    Retrieve a specific node by its ID.
    """
    node = network_service.get_node_by_id(node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    return node

@router.get("/api/v1/debug/tables", tags=["Debug"])
async def debug_tables():
    """
    Endpoint to check which tables actually exist in the DB.
    """
    from database import get_all_tables
    tables = get_all_tables()
    return {"tables_in_db": tables}

@router.get("/api/v1/debug/columns/{table_name}", tags=["Debug"])
async def debug_columns(table_name: str):
    """
    Endpoint to check the columns of a specific table.
    """
    from database import get_table_columns
    columns = get_table_columns(table_name)
    return {
        "table": table_name,
        "columns": columns
    }

@router.get("/api/v1/sites", response_model=List[SiteBase], tags=["Infrastructure"])
async def get_sites():
    """
    Retrieve all network sites.
    """
    try:
        sites = network_service.get_all_sites()
        return sites
    except Exception as e:
        loguru.logger.error(f"Error retrieving sites: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/api/v1/sites/{site_id}", response_model=SiteBase, tags=["Infrastructure"])
async def get_site(site_id: str):
    """
    Retrieve a specific site by its ID.
    """
    site = network_service.get_site_by_id(site_id)
    if not site:
        raise HTTPException(status_code=404, detail=f"Site {site_id} not found")
    return site    

@router.get("/api/v1/sites/{site_id}/nodes", response_model=List[NodeBase], tags=["Infrastructure"])
async def get_nodes_by_site(site_id: str):
    """
    Get all devices hosted in a specific site.
    """
    nodes = network_service.get_nodes_by_site(site_id)
    if not nodes:
        loguru.logger.warning(f"No nodes found for site: {site_id}")
    return nodes

@router.get("/api/v1/optimize/closest-sites", response_model=List[SiteDistanceResponse], tags=["Optimization"])
async def get_closest_sites(lat: float, lon: float, limit: int = 3):
    """
    Search for the closest network sites to a given geographical point.
    Example: ?lat=40.41&lon=-3.70&limit=3
    """
    try:
        closest = network_service.find_closest_sites(lat, lon, limit)
        return closest
    except Exception as e:
        loguru.logger.error(f"Optimization error: {e}")
        raise HTTPException(status_code=500, detail="Error calculating distances")

@router.get("/api/v1/visualize/map2", tags=["Visualization"])
async def get_interactive_map2():
    """
    Generates and serves an interactive HTML map of all network sites.
    """
    try:
        map_file = network_service.generate_network_map()
        return FileResponse(map_file)
    except Exception as e:
        loguru.logger.error(f"Error generating map: {e}")
        raise HTTPException(status_code=500, detail="Could not generate map")

@router.get("/api/v1/visualize/map", tags=["Visualization"])
async def get_interactive_map():
    """
    Generates and serves an interactive HTML map highlighting the top scoring network path.
    Uses get_all_nodes() to match production data integrity, fixing zeroed benchmarks,
    mismatched equipment UUID fields, and scaling fractional metrics dynamically.
    """
    try:
        # Logic moved to service for better maintainability
        enriched_data = network_service.get_enriched_nodes_for_visualization()
        sorted_results, _, _, _ = placement_service.algorithm_original(enriched_data,1) # Unpack the tuple
        top_path = sorted_results[0] if sorted_results else None # Get the first result from the list
        
        map_file = network_service.generate_network_map(top_path=top_path, enriched_nodes=enriched_data)
        return FileResponse(map_file)
        
    except Exception as e:
        logger.error(f"Error generating map with normalized metrics: {e}")
        raise HTTPException(status_code=500, detail="Could not generate synchronized map layout")

@router.get("/api/v1/visualize/compare-map", tags=["Visualization"])
async def get_comparison_map():
    """
    Generates and serves an interactive HTML map comparing 'original' and 'c3-pareto-topsis' paths.
    """
    try:
        # 1. Fetch current network state (this triggers metric simulation)
        enriched_data = network_service.get_enriched_nodes_for_visualization()
        # 2. Run both algorithms on the single network state
        comparison_data = await _run_single_comparison(network_service, placement_service)
        # 3. Generate map using the comparison summary
        summary = comparison_data.get("comparison_summary")
        map_file = network_service.generate_network_map(enriched_nodes=enriched_data, comparison_results=summary)
        
        return FileResponse(map_file)
    except Exception as e:
        logger.error(f"Error generating comparison map: {e}")
        raise HTTPException(status_code=500, detail="Could not generate algorithm comparison map")

@router.get("/api/v1/nodes/{node_id}/telemetry", tags=["Simulation"])
async def get_node_telemetry(node_id: str):
    """
    Get real-time simulated telemetry for a specific node.
    """
    node = network_service.get_node_by_id(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    is_deployed = True if node.cnf and node.cnf.lower() == 'yes' else False
    metrics = network_service.simulate_node_metrics(is_deployed)
    
    return {"node_id": node_id, "telemetry": metrics}
    
async def _run_single_comparison(network_service: NetworkService, placement_service: PlacementService, num_of_sim: int = 1 ):
    """
    Helper function to run a single comparison between 'original' and 'c3-pareto-topsis' algorithms.
    """
    # 1. Fetch all nodes from the database (this simulates telemetry metrics)
    all_nodes = network_service.get_all_nodes()
    
    if not all_nodes:
        raise HTTPException(status_code=404, detail="No network nodes found in database")

    # 2. Extract configuration
    try:
        config = NetworkService._load_config()
        weights = config["scoring_weights"]
        lat_factors = config.get("latency_factors")
    except Exception as e:
        logger.error(f"Failed to load scoring weights from config: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal configuration error")

    # 3. Execute 'Original' algorithm
    # algorithm_original returns (results, input_table_data, input_table_headers)
#    logger.info(f"Running 'original' - START ...")
    start_time_orig = time.time()
    orig_results, input_data_rows, input_data_headers, orig_excel = placement_service.algorithm_original(all_nodes,num_of_sim)
    end_time_orig = time.time()
    elapsed_orig = end_time_orig - start_time_orig
#    logger.info(f"Running 'original' - END ...")
    
    # 4. Execute 'C3-Pareto-TOPSIS' algorithm
    # First generate candidates, then evaluate them with the same set of weights
#    logger.info(f"Running 'C3-Pareto-TOPSIS' - START ")
    start_time_c3 = time.time()
    path_candidates = placement_service.generate_path_candidates(all_nodes)
    c3_results, _, _, c3_excel = placement_service.evaluate_paths(path_candidates, weights,num_of_sim)
    end_time_c3 = time.time()
    elapsed_c3 = end_time_c3 - start_time_c3
#    logger.info(f"Running 'C3-Pareto-TOPSIS' - END ")

    def format_time(seconds):
      if seconds < 60:
        return f"{seconds:.2f} sec"
      else:
        mins = int(seconds // 60)
        secs = seconds % 60
        return f"{mins} min {secs:.2f} sec"

#    time_exec_orig=format_time(elapsed_orig)
#    time_exec_c3=format_time(elapsed_c3)
    # --- Mostrar resultados en el log ---
    logger.info(f"Time 'original': {format_time(elapsed_orig)}")
    logger.info(f"Time 'C3-Pareto-TOPSIS': {format_time(elapsed_c3)}")
#    logger.info(f"Time 'original': {format_time(time_exec_orig)}")
#    logger.info(f"Time 'C3-Pareto-TOPSIS': {time_exec_c3}")

    # 5. Build combined response structure
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "config": {
            "scoring_weights": weights,
            "latency_factors": lat_factors
        },
        "input_data": {
            "headers": input_data_headers,
            "rows": input_data_rows
        },
        "comparison_summary": {
            "original_best": {
                "path_id": orig_results[0]["path_id"] if orig_results else None,
                "fedge": orig_results[0]["fedge_site"] if orig_results else None,
                "edge": orig_results[0]["edge_site"] if orig_results else None,
                "score": orig_results[0]["score"] if orig_results else None
            },
            "c3_best": {
                "path_id": c3_results[0]["path_id"] if c3_results else None,
                "fedge": c3_results[0]["fedge_site"] if c3_results else None,
                "edge": c3_results[0]["edge_site"] if c3_results else None,
                "score": c3_results[0]["c_score"] if c3_results else None
            }
        },
        "execution_time": {
                "original_execution_time_seconds": round(elapsed_orig, 4),
                "c3_execution_time_seconds": round(elapsed_c3, 4),
                "original_execution_time_formatted": format_time(elapsed_orig),
                "c3_execution_time_formatted": format_time(elapsed_c3),
            },
        "results": {
                "original": {
                    "algorithm_id": "original_v1",
                    "execution_time_seconds": round(elapsed_orig, 4),
                    "execution_time_formatted": format_time(elapsed_orig),
                    "total_paths": len(orig_results),
                    "data": orig_results,
                },
                "c3_pareto_topsis": {
                    "algorithm_id": "c3_pareto_topsis_v1",
                    "execution_time_seconds": round(elapsed_c3, 4),
                    "execution_time_formatted": format_time(elapsed_c3),
                    "total_paths": len(c3_results),
                    "data": c3_results,
                },
            },
        "files": {
            "original_excel": orig_excel,
            "c3_excel": c3_excel
        }
    }

@router.get("/api/v1/placement/original", tags=["Placement"])
async def get_placement_original():
    """
    Execute the original ranking algorithm for FEDGE nodes.
    Includes full debug traces in the console.
    """
    # 1. Fetch all nodes from the database
    all_nodes = network_service.get_all_nodes() 
    
    # 2. Load configuration for weights and latency factors
    try:
        config = NetworkService._load_config()
        weights = config["scoring_weights"]
        lat_factors = config.get("latency_factors")
    except Exception as e:
        logger.error(f"Failed to load scoring weights or latency factors from config: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal configuration error")

    # 3. Execute the original placement algorithm
    results, input_table_data, input_table_headers, excel_path = placement_service.algorithm_original(all_nodes,1)
    
    if not results:
        raise HTTPException(status_code=404, detail="No FEDGE nodes found to rank")

    # Identify the top-performing candidate for the summary section
    best_path = results[0] if results else None

    return {
        "status": "success",
        "algorithm": "original_v1",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "config": {
            "scoring_weights": weights,
            "latency_factors": lat_factors
        },
        "best_combined_path": {
            "fedge_site": best_path["fedge_site"],
            "edge_site": best_path["edge_site"],
            "path_id": best_path["path_id"],
            "c_score": best_path["score"]
        } if best_path else None,
        "total_paths_evaluated": len(results), # This now reflects only the ranked results
        "input_data": {
            "headers": input_table_headers,
            "rows": input_table_data
        },
        "excel_report": excel_path,
        "data": results
    }

@router.get("/api/v1/placement/compare-algorithms", tags=["Placement"])
async def compare_algorithms():
    """
    Compares 'original' and 'c3-pareto-topsis' algorithms using the same set of input nodes.
    Fetches nodes once (with simulated metrics) and passes them to both algorithms.
    """
    comparison_result = await _run_single_comparison(network_service, placement_service)
    return {
        "status": "success",
        **comparison_result
    }

@router.get("/api/v1/placement/simulate-comparison", tags=["Placement"])
async def simulate_comparison(num_of_sim: int = 1):
    """
    Runs multiple simulations comparing 'original' and 'c3-pareto-topsis' algorithms.
    Each simulation uses a fresh set of (simulated) input data.
    """
    if num_of_sim <= 0:
        raise HTTPException(status_code=400, detail="Number of simulations must be a positive integer.")

    all_simulations_results = []
    for i in range(num_of_sim):
        logger.info(f"Running simulation {i+1}/{num_of_sim}...")
        try:
#            single_run_result = await _run_single_comparison(network_service, placement_service)
            single_run_result = await _run_single_comparison(network_service, placement_service,i+1)
            all_simulations_results.append({
                "simulation_number": i + 1,
                "status": "success",
                **single_run_result
            })
        except HTTPException as e:
            logger.error(f"Simulation {i+1} failed: {e.detail}")
            all_simulations_results.append({
                "simulation_number": i + 1,
                "status": "failed",
                "error": e.detail
            })
        except Exception as e:
            logger.error(f"An unexpected error occurred during simulation {i+1}: {str(e)}")
            all_simulations_results.append({
                "simulation_number": i + 1,
                "status": "failed",
                "error": str(e)
            })

    # Load config for the root summary
    try:
        config = NetworkService._load_config()
        weights = config.get("scoring_weights")
        lat_factors = config.get("latency_factors")
    except Exception:
        weights, lat_factors = {}, {}

    return {
        "status": "success",
        "total_simulations_requested": num_of_sim,
        "total_simulations_completed": len(all_simulations_results),
        "config": {
            "scoring_weights": weights,
            "latency_factors": lat_factors
        },
        "simulation_results": all_simulations_results
    }

@router.get("/api/v1/placement/simulate-comparison-summary", tags=["Placement"])
async def simulate_comparison_summary(num_of_sim: int = 1, include_graph: str = "no"):
    """
    Runs multiple simulations and returns a simplified summary.
    Also exports the consolidated results to a single Excel file.
    """
    if num_of_sim <= 0:
        raise HTTPException(status_code=400, detail="Number of simulations must be a positive integer.")

    summary_results = []
    
    # Fetch config for the response
    try:
        config = NetworkService._load_config()
        weights = config.get("scoring_weights")
        lat_factors = config.get("latency_factors")
    except Exception:
        weights, lat_factors = {}, {}

    for i in range(num_of_sim):
        logger.info(f"Running summary simulation {i+1}/{num_of_sim}...")
        try:
            # Run the existing logic but filter the output
#            full_run = await _run_single_comparison(network_service, placement_service)
            full_run = await _run_single_comparison(network_service, placement_service,i+1)
            summary_results.append({
                "simulation_number": i + 1,
                "status": "success",
                "timestamp": full_run["timestamp"],
                "comparison_summary": full_run["comparison_summary"],
                "execution_time": full_run["execution_time"],
                "files": full_run["files"]
            })
        except Exception as e:
            logger.error(f"Simulation {i+1} failed: {str(e)}")
            summary_results.append({
                "simulation_number": i + 1,
                "status": "failed",
                "error": str(e)
            })

    # --- Statistics Calculation for 'summary_of_simulations' ---
    successful_runs = [s for s in summary_results if s["status"] == "success"]
    total_success = len(successful_runs)
    
    same_count = 0
    diff_count = 0
    same_match_cases = [] # NEW: List to store details of same results
    neither_match_cases = []
    fedge_match_cases = []
    edge_match_cases = []
    
    # New dictionaries for ranking statistics
    original_path_counts = defaultdict(int)
    original_fedge_counts = defaultdict(int)
    original_edge_counts = defaultdict(int)
    c3_path_counts = defaultdict(int)
    c3_fedge_counts = defaultdict(int)
    c3_edge_counts = defaultdict(int)
    
    for sim in successful_runs:
        orig = sim["comparison_summary"]["original_best"]
        c3 = sim["comparison_summary"]["c3_best"]

        case_info = { # Prepare detailed info for all cases
            "simulation_number": sim["simulation_number"],
            "original_choice": {"fedge": orig["fedge"], "edge": orig["edge"], "path_id": orig["path_id"], "score": orig["score"]},
            "c3_choice": {"fedge": c3["fedge"], "edge": c3["edge"], "path_id": c3["path_id"], "score": c3["score"]}
        }

        # Collect data for ranking statistics
        if orig["path_id"]:
            original_path_counts[orig["path_id"]] += 1
        if orig["fedge"]:
            original_fedge_counts[orig["fedge"]] += 1
        if orig["edge"]:
            original_edge_counts[orig["edge"]] += 1

        if c3["path_id"]:
            c3_path_counts[c3["path_id"]] += 1
        if c3["fedge"]:
            c3_fedge_counts[c3["fedge"]] += 1
        if c3["edge"]:
            c3_edge_counts[c3["edge"]] += 1

        if orig["path_id"] == c3["path_id"]: # Check for exact path_id match
            same_count += 1
            same_match_cases.append(case_info) # Add to new list
        else: # Paths are different
            diff_count += 1
            f_match = (orig["fedge"] == c3["fedge"])
            e_match = (orig["edge"] == c3["edge"])
            
            if not f_match and not e_match:
                neither_match_cases.append(case_info)
            elif f_match:
                fedge_match_cases.append(case_info)
            elif e_match:
                edge_match_cases.append(case_info)

    def calc_pct(count, total):
        return (count / total) if total > 0 else 0.0

    def _format_ranking_stats(counts_dict, total_sims):
        ranked_list = []
        for item, count in sorted(counts_dict.items(), key=lambda item: item[1], reverse=True):
            ranked_list.append({
                "item": item,
                "count": count,
                "percentage": f"{(calc_pct(count, total_sims) * 100):.2f}%"
            })
        return ranked_list

    summary_of_simulations = {
        "total_successful_simulations": total_success,
        "same_result": {
            "count": same_count,
            "percentage": f"{(calc_pct(same_count, total_success) * 100):.2f}%", # Format for API response
            "cases": same_match_cases # NEW: Include details here
        },
        "different_result": {
            "count": diff_count,
            "percentage": f"{(calc_pct(diff_count, total_success) * 100):.2f}%",
            "analysis_of_mismatches": {
                "neither_fedge_nor_edge_match": {
                    "count": len(neither_match_cases),
                    "percentage": f"{(calc_pct(len(neither_match_cases), total_success) * 100):.2f}%",
                    "cases": neither_match_cases
                },
                "same_fedge_only": {
                    "count": len(fedge_match_cases),
                    "percentage": f"{(calc_pct(len(fedge_match_cases), total_success) * 100):.2f}%",
                    "cases": fedge_match_cases
                },
                "same_edge_only": {
                    "count": len(edge_match_cases),
                    "percentage": f"{(calc_pct(len(edge_match_cases), total_success) * 100):.2f}%",
                    "cases": edge_match_cases
                }
            }
        },
        "original_algorithm_rankings": {
            "path_id_ranking": _format_ranking_stats(original_path_counts, total_success),
            "fedge_ranking": _format_ranking_stats(original_fedge_counts, total_success),
            "edge_ranking": _format_ranking_stats(original_edge_counts, total_success)
        },
        "c3_pareto_topsis_algorithm_rankings": {
            "path_id_ranking": _format_ranking_stats(c3_path_counts, total_success),
            "fedge_ranking": _format_ranking_stats(c3_fedge_counts, total_success),
            "edge_ranking": _format_ranking_stats(c3_edge_counts, total_success)
        }
    }

    # Export consolidated summary to Excel
    folder = "excel"
    if not os.path.exists(folder): os.makedirs(folder)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_filename = f"{folder}/simulations_summary_{timestamp}.xlsx"
    placement_service.export_simulations_summary(summary_results, summary_of_simulations, excel_filename)

    # --- Conditional Graph Generation ---
    graph_filename = None
    if include_graph.lower() == "yes":
        graph_filename = f"{folder}/simulations_dashboard_{timestamp}.png"
        placement_service.generate_simulation_plots(summary_of_simulations, graph_filename)

    return {
        "status": "success",
        "total_simulations_requested": num_of_sim,
        "total_simulations_completed": len(summary_results),
        "summary_report_excel": excel_filename,
        "summary_report_graph": graph_filename,
        "config": {
            "scoring_weights": weights,
            "latency_factors": lat_factors
        },
        "summary_of_simulations": summary_of_simulations,
        "simulation_results": summary_results
    }

@router.get("/api/v1/placement/c3-pareto-topsis", tags=["Placement"])
async def get_placement_c3_pareto_topsis():
    """
    Execute the advanced C3-Pareto-TOPSIS ranking algorithm 
    for combined paths (SMU -> FEDGE -> EDGE -> UTSW).
    """
    # 1. Fetch all nodes from the database using your existing network service
    all_nodes = network_service.get_all_nodes()
    
    if not all_nodes:
        raise HTTPException(status_code=404, detail="No network nodes found in database")

    # 2. Extract weights from config.yaml using NetworkService
    try:
        # Changed placement_service to NetworkService
        config = NetworkService._load_config()
        weights = config["scoring_weights"]
        lat_factors = config.get("latency_factors")
    except Exception as e:
        logger.error(f"Failed to load scoring weights from config: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal configuration error")
        
    # 3. Step 1: Generate the uncentralized cross-combined path candidates
    path_candidates = placement_service.generate_path_candidates(all_nodes)
    
    if not path_candidates:
        raise HTTPException(status_code=404, detail="No valid FEDGE-EDGE combinations could be formed")

    # 4. Step 2 to 5: Run the core pipeline (Pareto + Weighted Matrix + Ideals + C-Score)
    results, input_table_data, input_table_headers, excel_path = placement_service.evaluate_paths(path_candidates, weights,1)

    # Identify the top-performing candidate for the summary section
    best_path = results[0] if results else None

    # 5. Return the structured final ranking matching your system standards
    return {
        "status": "success",
        "algorithm": "c3_pareto_topsis_v1",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "config": {
            "scoring_weights": weights,
            "latency_factors": lat_factors
        },
        "best_combined_path": {
            "fedge_site": best_path["fedge_site"],
            "edge_site": best_path["edge_site"],
            "path_id": best_path["path_id"],
            "c_score": best_path["c_score"]
        } if best_path else None,
        "total_paths_evaluated": len(path_candidates), # This is the total number of candidates generated
        "input_data": {
            "headers": input_table_headers,
            "rows": input_table_data
        },
        "excel_report": excel_path,
        "data": results
    }