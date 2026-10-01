"""
UPF Optimal Placer (UOP) - v2.0

File: schemas.py

Description:
Contains Pydantic data models and class definitions used for data validation, serialization, and API response structures.

@authors: R. Rodriguez <raul.rodriguez@hcltech.com>, Y. Aldoori <yaseen.aldoori@windriver.com>, L. Popokh <leo.popokh@asato.ai>
@license: MIT
@copyright: Copyright (c) 2026 R. Rodriguez, Y. Aldoori, L. Popokh
"""

# Standard library imports
from typing import Optional, List, Union, Dict
from datetime import datetime

# Third-party libraries
from pydantic import BaseModel, ConfigDict


class NodeBase(BaseModel):
    """
    Flat schema representing a Node joined with its Site information.
    """
    model_config = ConfigDict(coerce_numbers_to_str=True, from_attributes=True)

    id: str
    status: Optional[str] = None
    cnf: Optional[Union[str, int]] = None
    
    # Telemetry
    cpu: Optional[str] = None      # Changed to str to keep decimals
    ramava: Optional[str] = None   # Changed to str to keep decimals
    diskava: Optional[str] = None  # Changed to str to keep decimals
    iops: Optional[str] = None     # Changed to str for the thousands separator
    bw: Optional[str] = None       # Changed to str to keep decimals
    
    
    # Hardware Info
    ramtot: Optional[float] = None
    disktot: Optional[float] = None
    manufacturer: Optional[str] = None
    type: Optional[str] = None
    role: Optional[str] = None
    
    # Joined Site Information
    site: Optional[str] = None
    location: Optional[str] = None
    shortname: Optional[str] = None
    region: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    # Infrastructure details
    cluster: Optional[str] = None
    platform: Optional[str] = None
    description: Optional[str] = None    
    
    
class NetworkResponse(BaseModel):
    """
    Standard API response wrapper for network operations.
    """
    status: str
    message: str
    data: Optional[List] = None
    

class SiteBase(BaseModel):
    """
    Schema for Network Sites.
    Matches the Sites table DDL.
    """
    model_config = ConfigDict(coerce_numbers_to_str=True, from_attributes=True)

    id: str
    type: Optional[str] = None
    status: Optional[str] = None
    location: Optional[str] = None
    short_name: Optional[str] = None
    region: Optional[str] = None
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
 

class SiteDistanceResponse(SiteBase):
    """
    Extends SiteBase to include the calculated distance.
    """
    distance_km: float


class PathCandidate:
    """
    Represents a unique combined network path: SMU -> FEDGE -> EDGE -> UTSW.
    Stores consolidated metrics for multi-criteria decision analysis.
    """
    def __init__(self, fe_id: str, edge_id: str, metrics: dict):
        self.fe_id = fe_id
        self.edge_id = edge_id
        # Unique identifier for the combined path (e.g., "FE_1==EDGE_3")
        self.path_id = f"{fe_id}=={edge_id}"
        # Dictionary containing keys: 'latency', 'cpu', 'iops', 'ram', 'bw', 'disk'
        self.metrics = metrics  
        self.pareto_efficient = True
        
        