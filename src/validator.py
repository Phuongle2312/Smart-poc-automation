"""
Phase 1: Data Validation & Schema enforcement (Pydantic v2)
This module defines the validation models and schemas for raw order data harvested by the crawler.
"""

from typing import List
from pydantic import BaseModel, Field, field_validator
import datetime
import logging

logger = logging.getLogger(__name__)

class OrderItem(BaseModel):
    """
    Schema representing a single order record.
    """
    order_id: str = Field(..., description="Unique order identifier")
    vendor: str = Field(..., description="Vendor name")
    order_date: str = Field(..., description="Order placement date in YYYY-MM-DD format")
    total_amount: float = Field(..., gt=0, description="Total amount of the order, must be positive")
    barcodes: List[str] = Field(default_factory=list, description="List of product barcodes in this order")

    @field_validator("order_date")
    @classmethod
    def validate_order_date(cls, value: str) -> str:
        """
        Validate that the order date is in correct YYYY-MM-DD format and is a valid calendar date.
        """
        try:
            datetime.datetime.strptime(value, "%Y-%m-%d")
            return value
        except ValueError:
            raise ValueError(f"Order date '{value}' must be in YYYY-MM-DD format.")

    @field_validator("barcodes")
    @classmethod
    def validate_barcodes(cls, value: List[str]) -> List[str]:
        """
        Validate that barcodes are not empty strings and conform to general barcode standards (alphanumeric).
        """
        cleaned_barcodes = []
        for code in value:
            stripped = code.strip()
            if not stripped:
                raise ValueError("Barcode cannot be empty")
            if not stripped.isalnum():
                raise ValueError(f"Barcode '{stripped}' must contain only alphanumeric characters")
            cleaned_barcodes.append(stripped)
        return cleaned_barcodes


def validate_raw_orders(raw_data: List[dict]) -> List[dict]:
    """
    Validates a list of raw order dictionaries and filters out invalid ones.
    
    Args:
        raw_data: List of raw dictionaries parsed from crawler output.
        
    Returns:
        List of validated order dictionaries conforming to OrderItem schema.
    """
    validated_orders = []
    
    for index, raw_order in enumerate(raw_data):
        try:
            # Parse and validate the dict against OrderItem schema
            order = OrderItem(**raw_order)
            validated_orders.append(order.model_dump())
        except Exception as e:
            logger.error(f"Validation failed for order at index {index} (data: {raw_order}): {e}")
            
    logger.info(f"Validated {len(validated_orders)} out of {len(raw_data)} raw orders.")
    return validated_orders
