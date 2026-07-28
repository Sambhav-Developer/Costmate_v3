import os
import json
from typing import Dict, Any, Optional
from app.config import settings
from app.core.logging import logger
from app.services.dsr.floor_escalation import get_floor_escalation_pct

class DSRLoader:
    def __init__(self):
        self.dsr_path = settings.DSR_PATH
        self.rates: Dict[str, Any] = {}
        self.load_rates()

    def load_rates(self):
        """Loads DSR rates from local JSON database."""
        if not os.path.exists(self.dsr_path):
            logger.error(f"DSR rate file not found at: {self.dsr_path}")
            # Fallback inline mini-db
            self.rates = {
                "2.8": {"description": "Excavation", "unit": "cum", "rate": 180.5},
                "5.2": {"description": "PCC 1:4:8", "unit": "cum", "rate": 4850.0},
                "5.9": {"description": "RCC 1:1.5:3", "unit": "cum", "rate": 6750.0},
                "5.22": {"description": "Steel reinforcement Fe-500D", "unit": "tonne", "rate": 62000.0},
                "6.4": {"description": "Brickwork 1:6", "unit": "cum", "rate": 5400.0},
                "13.1": {"description": "Plastering 1:6", "unit": "sqm", "rate": 210.0},
                "11.38": {"description": "Vitrified tiling", "unit": "sqm", "rate": 950.0}
            }
            return
            
        try:
            with open(self.dsr_path, "r", encoding="utf-8") as f:
                self.rates = json.load(f)
            logger.info(f"Loaded {len(self.rates)} DSR rates from {self.dsr_path}")
        except Exception as e:
            logger.error(f"Failed to parse DSR rates from JSON: {e}")
            raise e

    def get_dsr_item(self, item_code: str) -> Optional[Dict[str, Any]]:
        """Retrieves a rate item from the database."""
        item = self.rates.get(str(item_code))
        if not item:
            logger.warning(f"DSR item code {item_code} not found in database.")
            return None
        return item

    def get_rate(self, item_code: str, floor_number: int = 1) -> float:
        """
        Gets the rate for an item, applying floor level escalation.
        """
        item = self.get_dsr_item(item_code)
        if not item:
            return 0.0
            
        base_rate = item.get("rate", 0.0)
        escalation_pct = get_floor_escalation_pct(floor_number)
        
        escalated_rate = base_rate * (1 + (escalation_pct / 100.0))
        return round(escalated_rate, 2)

# Global loader singleton
dsr_loader = DSRLoader()
