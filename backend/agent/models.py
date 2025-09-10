from __future__ import annotations
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# These are the data structures that hold everything together
class Product(BaseModel):
    # Everything that needs to be know about a product from the catalog
    id: str  
    title: str
    description: str
    category: str  
    brand: str  
    price: float
    currency: str  
    image_url: str  
    product_url: Optional[str] = None  
    tags: str  

class FilterSpec(BaseModel):
    # What the user is looking for 
    brand: Optional[str] = None  
    category: Optional[str] = None 
    price_min: Optional[float] = Field(default=None, ge=0)  
    price_max: Optional[float] = Field(default=None, ge=0)  
    tags_contains: Optional[str] = None

class ChatRequest(BaseModel):
    # What comes from the frontend when the user sends a message
    messages: List[Dict[str, Any]]  
    image_base64: Optional[str] = None  
    top_k: int = 8  
    filters: Optional[FilterSpec] = None  

class ChatResponse(BaseModel):
    # What we send back to the frontend
    reply: str  
    products: List[Product]  
    trace: Dict[str, Any]  

class ProductsResponse(BaseModel):
    # For API endpoints that just return products without chat
    products: List[Product]
