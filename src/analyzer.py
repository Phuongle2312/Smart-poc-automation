"""
Phase 2: RAG Analyzer with LLM.
Reads orders from raw_orders.json, performs semantic search in Qdrant Local
to fetch relevant rules, and analyzes violations using Gemini API or a local rule engine.
Produces structured outputs in report.json and report.txt.
"""

import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models

# Import get_embedding helper
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.embed_knowledge import get_embedding, QDRANT_PATH, COLLECTION_NAME, get_qdrant_client

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("analyzer")

RAW_ORDERS_FILE = "data/raw_orders.json"
REPORT_JSON_FILE = "data/report.json"
REPORT_TXT_FILE = "data/report.txt"

def query_relevant_rules(client: QdrantClient, order: Dict[str, Any], limit: int = 2) -> List[Dict[str, Any]]:
    """
    Formulates a semantic search query from order data, generates its vector,
    and retrieves matching rules from Qdrant.
    """
    query_text = (
        f"Order from vendor '{order['vendor']}' placed on date '{order['order_date']}' "
        f"with total amount {order['total_amount']}. Barcodes: {', '.join(order['barcodes'])}."
    )
    
    # Generate query embedding vector
    query_vector = get_embedding(query_text)
    
    try:
        response = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=limit
        )
        
        rules = []
        for hit in response.points:
            rules.append({
                "score": hit.score,
                "title": hit.payload.get("title", ""),
                "content": hit.payload.get("content", "")
            })
        return rules
    except Exception as e:
        logger.error(f"Error querying Qdrant: {e}")
        return []

def local_offline_analyze(order: Dict[str, Any], relevant_rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    A smart local rule-based engine that mocks LLM reasoning for the PoC offline mode.
    Correctly matches the rules set in knowledge.md.
    """
    vendor = order["vendor"].lower()
    total_amount = order["total_amount"]
    barcodes = order["barcodes"]
    
    # Check date formatting & delay
    # Assume analysis date (current date) is 2026-05-25 for testing consistency
    analysis_date = datetime.strptime("2026-05-25", "%Y-%m-%d")
    
    try:
        order_date = datetime.strptime(order["order_date"], "%Y-%m-%d")
        days_delay = (analysis_date - order_date).days
    except ValueError:
        days_delay = 0 # Handled by G1 validator, but fallback
        
    # Rule 1: SLA delivery timeline
    # Assume Global Tech Solutions & Sino Logistics are foreign vendors (5 days limit)
    # Assume others are domestic (2 days limit)
    is_foreign = "global" in vendor or "sino" in vendor
    allowed_delay = 5 if is_foreign else 2
    
    if days_delay > allowed_delay:
        return {
            "has_violation": True,
            "rule_violated": "SLA Delivery Timeline",
            "reason": f"Order from {'foreign' if is_foreign else 'domestic'} vendor '{order['vendor']}' took {days_delay} days to deliver, exceeding SLA limit of {allowed_delay} days.",
            "severity": "High" if is_foreign else "Medium"
        }
        
    # Rule 2: Barcode đầu số cho Global Tech Solutions (must start with 978 or 893)
    if "global tech" in vendor:
        invalid_barcodes = [b for b in barcodes if not (b.startswith("978") or b.startswith("893"))]
        if invalid_barcodes:
            return {
                "has_violation": True,
                "rule_violated": "Product Barcode Regulations",
                "reason": f"Vendor 'Global Tech Solutions' barcodes must start with 978 or 893. Found invalid barcodes: {', '.join(invalid_barcodes)}.",
                "severity": "Medium"
            }
            
    # Rule 3: Hạn mức tài chính cho Vina Supply Corp (max 10,000.00 USD)
    if "vina supply" in vendor:
        if total_amount > 10000.00:
            return {
                "has_violation": True,
                "rule_violated": "Order Financial Limits",
                "reason": f"Vendor 'Vina Supply Corp' order total amount {total_amount} USD exceeds maximum threshold of 10,000.00 USD.",
                "severity": "High"
            }
            
    # Rule 4: Số tiền âm
    if total_amount <= 0:
        return {
            "has_violation": True,
            "rule_violated": "Order Financial Limits",
            "reason": "Order total amount must be a positive number greater than 0.",
            "severity": "High"
        }
        
    # No violation found
    return {
        "has_violation": False,
        "rule_violated": None,
        "reason": None,
        "severity": None
    }

def analyze_violations(order: Dict[str, Any], relevant_rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyzes an order against retrieved rules using Google Gemini API.
    Falls back to local rule-based analyzer if no API key is configured.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.info("Using local Offline Analyzer (Mock LLM) due to missing GEMINI_API_KEY.")
        return local_offline_analyze(order, relevant_rules)
        
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        # Construct rules context block
        rules_context = "\n\n".join([f"--- RULE SECTION: {r['title']} ---\n{r['content']}" for r in relevant_rules])
        
        prompt = f"""
You are an AI Compliance Auditor analyzing supplier order compliance against internal regulations.

[INTERNAL REGULATIONS]
{rules_context}

[ORDER DATA TO AUDIT]
Order ID: {order['order_id']}
Vendor: {order['vendor']}
Order Date: {order['order_date']}
Total Amount: {order['total_amount']}
Product Barcodes: {', '.join(order['barcodes'])}
Current Analysis Date (for delay calculation): 2026-05-25

Evaluate the order against the provided regulations. You MUST respond ONLY with a JSON object containing these exact keys:
{{
  "has_violation": true/false (boolean),
  "rule_violated": "Name of the rule section violated or null if none",
  "reason": "Detailed description of why it violates the rule or null if none",
  "severity": "High"/"Medium"/"Low" or null if none
}}
"""
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        # Parse JSON output
        result = json.loads(response.text.strip())
        return result
    except Exception as e:
        logger.warning(f"Error during Gemini API call: {e}. Falling back to local offline analyzer.")
        return local_offline_analyze(order, relevant_rules)

def generate_reports(analyzed_orders: List[Dict[str, Any]]):
    """Generates JSON and formatted text reports from the analysis results."""
    # 1. Save JSON Report
    with open(REPORT_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(analyzed_orders, f, indent=4)
    logger.info(f"Saved structured JSON report to {REPORT_JSON_FILE}")
    
    # 2. Build and save Text Report
    violations = [o for o in analyzed_orders if o["analysis"]["has_violation"]]
    total_orders = len(analyzed_orders)
    total_violations = len(violations)
    
    report_lines = [
        "==============================================================================",
        "                    COMPLIANCE AUDIT REPORT (RAG SYSTEM)                      ",
        f"                    Date of Audit: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}             ",
        "==============================================================================",
        f"Total Orders Scanned      : {total_orders}",
        f"Compliant Orders          : {total_orders - total_violations}",
        f"Non-Compliant (Violated)  : {total_violations}",
        "==============================================================================",
        "\nDETAILED AUDIT LOGS:\n"
    ]
    
    for idx, order in enumerate(analyzed_orders):
        status = "[❌ VIOLATED]" if order["analysis"]["has_violation"] else "[✅ COMPLIANT]"
        report_lines.append(f"{idx + 1}. Order ID: {order['order_id']} | Vendor: {order['vendor']} | Status: {status}")
        if order["analysis"]["has_violation"]:
            report_lines.append(f"   - Rule Violated: {order['analysis']['rule_violated']}")
            report_lines.append(f"   - Severity     : {order['analysis']['severity']}")
            report_lines.append(f"   - Reason       : {order['analysis']['reason']}")
        report_lines.append("-" * 80)
        
    with open(REPORT_TXT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    logger.info(f"Saved human-readable text report to {REPORT_TXT_FILE}")

def run_analysis():
    """Orchestrates Phase 2 compliance auditing workflow."""
    logger.info("Starting compliance analysis run...")
    
    # Check if raw orders exist
    if not os.path.exists(RAW_ORDERS_FILE):
        logger.error(f"Raw orders file not found: {RAW_ORDERS_FILE}. Run Phase 1 first.")
        return
        
    with open(RAW_ORDERS_FILE, "r", encoding="utf-8") as f:
        orders = json.load(f)
        
    if not orders:
        logger.warning("No orders found in raw_orders.json to analyze.")
        return
        
    # Connect to local Qdrant VectorDB
    if not os.path.exists(QDRANT_PATH):
        logger.error(f"Vector Database not found at {QDRANT_PATH}. Run embed_knowledge.py first.")
        return
        
    client = get_qdrant_client()
    
    analyzed_orders = []
    for order in orders:
        logger.info(f"Auditing Order ID: {order['order_id']}...")
        
        # 1. Retrieve relevant clauses using vector semantic search
        relevant_rules = query_relevant_rules(client, order)
        
        # 2. Audit order against rules using AI (or local rule-engine fallback)
        audit_result = analyze_violations(order, relevant_rules)
        
        analyzed_orders.append({
            "order_id": order["order_id"],
            "vendor": order["vendor"],
            "order_date": order["order_date"],
            "total_amount": order["total_amount"],
            "barcodes": order["barcodes"],
            "analysis": audit_result
        })
        
    # 3. Generate outputs
    generate_reports(analyzed_orders)
    logger.info("Compliance analysis completed successfully.")

if __name__ == "__main__":
    run_analysis()
