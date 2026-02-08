"""
AC Financial Data API Tool for LangChain Agents

Production-grade tool for fetching Indian stock market financial data (NSE/BSE).
Designed for use within AgentExecutor and ReAct agents.

Core Design Principles:
  1. No hallucination: Return raw API responses only
  2. Validation-first: Enforce API constraints upfront
  3. Agent-friendly: Structured input/output, explicit errors
  4. Stateless: No caching or side effects
  5. Timeout-safe: Explicit timeout handling
"""

import os
import json
import requests
from typing import Optional, Dict, Any
from enum import Enum

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator, model_validator
from langchain.tools import tool

# Load environment variables from .env file
load_dotenv()


# ============================================================================
# INPUT VALIDATION & SCHEMA
# ============================================================================

class ActionEnum(str, Enum):
    """Supported API actions."""
    STATUS = "status"
    COMPANY = "company"
    BALANCESHEET = "balancesheet"
    PNL = "pnl"
    CFS = "cfs"
    RATIOS = "ratios"
    NEWS = "news"
    LINKS = "links"
    SECTOR_COMPARISON = "sector_comparison"


class ACFinancialDataInput(BaseModel):
    """
    Structured input schema for AC Financial Data API tool.
    
    Validates:
      - Symbol format (.NS / .BO suffix when required)
      - Year range (2022-2025 when provided)
      - Required parameters per action
      - Parameter combinations
    """
    
    action: ActionEnum = Field(
        ...,
        description="Action to perform on AC Financial Data API"
    )
    
    symbol: Optional[str] = Field(
        None,
        description="Indian stock symbol with exchange suffix (.NS for NSE, .BO for BSE). "
                    "Required for: company, balancesheet, pnl, cfs, ratios, news, links"
    )
    
    year: Optional[int] = Field(
        None,
        description="Calendar year (2022-2025). Optional for financial statements."
    )
    
    sector: Optional[str] = Field(
        None,
        description="Sector name (e.g., 'Technology', 'Banking'). Required for sector_comparison."
    )
    
    metric: Optional[str] = Field(
        None,
        description="Comparison metric (e.g., 'marketCapitalization', 'revenue'). Optional for sector_comparison."
    )
    
    limit: Optional[int] = Field(
        None,
        ge=1,
        le=100,
        description="Number of results to return. Optional for sector_comparison. Default: 10, Max: 100"
    )
    
    @field_validator("symbol", mode="before")
    @classmethod
    def validate_symbol_format(cls, v, info):
        """
        Enforce symbol format when symbol is required.
        
        Rules:
          - Must include .NS (NSE) or .BO (BSE) suffix
          - Required for all actions except sector_comparison and status
        """
        data = info.data
        action = data.get("action")
        
        # Actions that require symbol
        symbol_required_actions = {
            ActionEnum.COMPANY,
            ActionEnum.BALANCESHEET,
            ActionEnum.PNL,
            ActionEnum.CFS,
            ActionEnum.RATIOS,
            ActionEnum.NEWS,
            ActionEnum.LINKS,
        }
        
        if action in symbol_required_actions:
            if v is None:
                raise ValueError(
                    f"symbol is required for action '{action.value}'. "
                    f"Format: SYMBOL.NS (NSE) or SYMBOL.BO (BSE)"
                )
            
            if not isinstance(v, str):
                raise ValueError(f"symbol must be a string. Got: {type(v)}")
            
            if not (v.endswith(".NS") or v.endswith(".BO")):
                raise ValueError(
                    f"symbol must end with .NS (NSE) or .BO (BSE). Got: {v}. "
                    f"Example: RELIANCE.NS or RELIANCE.BO"
                )
        
        return v
    
    @field_validator("year", mode="before")
    @classmethod
    def validate_year_range(cls, v):
        """Enforce supported year range (2022-2025)."""
        if v is not None:
            if not isinstance(v, int):
                raise ValueError(f"year must be an integer. Got: {type(v)}")
            
            if v not in (2022, 2023, 2024, 2025):
                raise ValueError(
                    f"year must be 2022-2025 (API data availability). Got: {v}"
                )
        
        return v
    
    @field_validator("sector", mode="before")
    @classmethod
    def validate_sector_required(cls, v, info):
        """Enforce sector parameter for sector_comparison action."""
        data = info.data
        action = data.get("action")
        
        if action == ActionEnum.SECTOR_COMPARISON:
            if v is None:
                raise ValueError(
                    f"sector is required for action 'sector_comparison'. "
                    f"Example: 'Technology', 'Banking', 'Pharma', 'Automobiles'"
                )
        
        return v
    
    @model_validator(mode="after")
    def validate_required_fields(self):
        """Validate that required fields are present for each action."""
        # Actions that require symbol
        symbol_required_actions = {
            ActionEnum.COMPANY,
            ActionEnum.BALANCESHEET,
            ActionEnum.PNL,
            ActionEnum.CFS,
            ActionEnum.RATIOS,
            ActionEnum.NEWS,
            ActionEnum.LINKS,
        }
        
        if self.action in symbol_required_actions and not self.symbol:
            raise ValueError(
                f"symbol is required for action '{self.action.value}'. "
                f"Format: SYMBOL.NS (NSE) or SYMBOL.BO (BSE)"
            )
        
        if self.action == ActionEnum.SECTOR_COMPARISON and not self.sector:
            raise ValueError(
                f"sector is required for action 'sector_comparison'. "
                f"Example: 'Technology', 'Banking', 'Pharma', 'Automobiles'"
            )
        
        return self


# ============================================================================
# API CLIENT (CORE)
# ============================================================================

class ACFinancialAPIClient:
    """
    HTTP client for AC Financial Data API.
    
    Responsibilities:
      - URL construction
      - Header management (x-api-key)
      - Request execution with timeout
      - HTTP error handling (400, 401, 404, 500)
      - Response parsing
    
    Design: Stateless, single responsibility
    """
    
    BASE_URL = "https://ac-api-server.vercel.app"
    DEFAULT_TIMEOUT = 10  # seconds
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize API client.
        
        Args:
            api_key: API key for authentication. 
                     If None, attempts to read from AC_API_KEY environment variable.
        
        Raises:
            ValueError: If no API key is available.
        """
        self.api_key = api_key or os.getenv("AC_API_KEY")
        
        if not self.api_key:
            raise ValueError(
                "AC_API_KEY not provided. Either pass api_key parameter "
                "or set AC_API_KEY environment variable. "
                "Get your key from: https://ac-api-server.vercel.app"
            )
    
    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute HTTP GET request to API.
        
        Args:
            endpoint: API endpoint path (e.g., "/server/company/RELIANCE.NS")
            params: Query parameters dict
        
        Returns:
            Parsed JSON response matching API response schema:
            {
              "status": "success" | "error" | "not_found" | "bad_request",
              "message": str,
              "data": Any
            }
        
        Raises:
            ValueError: On HTTP errors or network issues
        """
        url = f"{self.BASE_URL}{endpoint}"
        headers = {"x-api-key": self.api_key}
        
        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=self.DEFAULT_TIMEOUT
            )
            
            # Explicit HTTP error handling per API contract
            if response.status_code == 401:
                raise ValueError(
                    "401 Unauthorized: Invalid or missing API key. "
                    "Verify AC_API_KEY in .env file is correct."
                )
            elif response.status_code == 400:
                raise ValueError(
                    f"400 Bad Request: Invalid parameters. Response: {response.text[:200]}"
                )
            elif response.status_code == 404:
                raise ValueError(
                    f"404 Not Found: Symbol or endpoint not found. "
                    f"Response: {response.text[:200]}"
                )
            elif response.status_code == 500:
                raise ValueError(
                    f"500 Server Error: API internal error. "
                    f"Try again in a few moments."
                )
            
            # Raise for any other HTTP errors
            response.raise_for_status()
            
            # Parse and return JSON response
            api_response = response.json()
            
            # Ensure response has all required fields for consistency
            if not isinstance(api_response, dict):
                api_response = {"status": "success", "message": "Data retrieved", "data": api_response}
            
            # Ensure message field exists in response
            if "message" not in api_response:
                if api_response.get("status") == "success":
                    api_response["message"] = "Request successful"
                elif api_response.get("status") == "error":
                    api_response["message"] = "An error occurred"
                else:
                    api_response["message"] = "Unknown status"
            
            # Convert string revenue values to numbers if present in data
            if isinstance(api_response.get("data"), list):
                numeric_fields = ["revenue", "netIncome", "totalAssets", "totalLiabilities", 
                                "operatingCashFlow", "investingCashFlow", "financingCashFlow",
                                "marketCapitalization", "roe", "roa", "eps"]
                for item in api_response["data"]:
                    if isinstance(item, dict):
                        for field in numeric_fields:
                            if field in item:
                                val = item[field]
                                if isinstance(val, str) and val.isdigit():
                                    try:
                                        item[field] = int(val)
                                    except (ValueError, TypeError):
                                        pass
                                elif isinstance(val, str) and '.' in val:
                                    try:
                                        item[field] = float(val)
                                    except (ValueError, TypeError):
                                        pass
            
            return api_response
        
        except requests.exceptions.Timeout:
            raise ValueError(
                f"Request timeout: API did not respond within {self.DEFAULT_TIMEOUT}s. "
                f"Try again later."
            )
        except requests.exceptions.ConnectionError as e:
            raise ValueError(
                f"Connection error: Unable to reach API at {self.BASE_URL}. "
                f"Check network connectivity."
            )
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Request failed: {str(e)}")
        except json.JSONDecodeError:
            raise ValueError(
                f"Invalid JSON response from API. Status: {response.status_code}"
            )
    
    # ========================================================================
    # ENDPOINT METHODS (Route to specific API endpoints)
    # ========================================================================
    
    def get_status(self) -> Dict[str, Any]:
        """
        Check API status (no authentication required).
        
        Endpoint: GET /
        
        Returns: API status and available routes
        """
        return self._make_request("/")
    
    def get_company(
        self,
        symbol: str,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get complete financial data for a company.
        
        Endpoint: GET /server/company/{symbol}
        
        Args:
            symbol: Stock symbol (e.g., RELIANCE.NS)
            year: Optional calendar year (2022-2025)
        
        Returns: Array of financial data snapshots
        """
        params = {}
        if year is not None:
            params["calendarYear"] = year
        
        return self._make_request(f"/server/company/{symbol}", params=params)
    
    def get_balancesheet(
        self,
        symbol: str,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get balance sheet data (assets, liabilities, equity).
        
        Endpoint: GET /server/company/balancesheet/{symbol}
        
        Args:
            symbol: Stock symbol
            year: Optional calendar year
        
        Returns: Balance sheet financial data
        """
        params = {}
        if year is not None:
            params["calendarYear"] = year
        
        return self._make_request(
            f"/server/company/balancesheet/{symbol}",
            params=params
        )
    
    def get_pnl(
        self,
        symbol: str,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get profit & loss statement (income statement).
        
        Endpoint: GET /server/company/pnl/{symbol}
        
        Args:
            symbol: Stock symbol
            year: Optional calendar year
        
        Returns: P&L financial data (revenue, expenses, net income)
        """
        params = {}
        if year is not None:
            params["calendarYear"] = year
        
        return self._make_request(f"/server/company/pnl/{symbol}", params=params)
    
    def get_cfs(
        self,
        symbol: str,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get cash flow statement.
        
        Endpoint: GET /server/company/cfs/{symbol}
        
        Args:
            symbol: Stock symbol
            year: Optional calendar year
        
        Returns: Cash flow data (OCF, ICF, FCF)
        """
        params = {}
        if year is not None:
            params["calendarYear"] = year
        
        return self._make_request(f"/server/company/cfs/{symbol}", params=params)
    
    def get_ratios(
        self,
        symbol: str,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get financial ratios and performance metrics.
        
        Endpoint: GET /server/company/ratios/{symbol}
        
        Args:
            symbol: Stock symbol
            year: Optional calendar year
        
        Returns: Calculated financial ratios (ROE, ROA, margins, etc.)
        """
        params = {}
        if year is not None:
            params["calendarYear"] = year
        
        return self._make_request(f"/server/company/ratios/{symbol}", params=params)
    
    def get_links(
        self,
        symbol: str,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get document links to NSE/BSE original filings.
        
        Endpoint: GET /server/company/links/{symbol}
        
        Args:
            symbol: Stock symbol
            year: Optional calendar year
        
        Returns: URLs to official financial documents
        """
        params = {}
        if year is not None:
            params["calendarYear"] = year
        
        return self._make_request(f"/server/company/links/{symbol}", params=params)
    
    def get_news(self, symbol: str) -> Dict[str, Any]:
        """
        Get latest company news articles.
        
        Endpoint: GET /server/news/{symbol}
        
        Args:
            symbol: Stock symbol
        
        Returns: Latest news articles with publication dates
        """
        return self._make_request(f"/server/news/{symbol}")
    
    def get_sector_comparison(
        self,
        sector: str,
        metric: Optional[str] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Compare top companies within a sector by specified metric.
        
        Endpoint: GET /server/comparison/sector/{sector}
        
        Args:
            sector: Sector name (e.g., Technology, Banking)
            metric: Comparison metric (e.g., marketCapitalization, revenue)
            limit: Number of results (default: 10, max: 100)
        
        Returns: Top N stocks in sector sorted by metric
        
        Note: This endpoint may return 500 errors due to backend database issues.
              In such cases, returns error response with empty data list.
        """
        params = {}
        if metric is not None:
            params["metric"] = metric
        if limit is not None:
            params["limit"] = int(limit)  # Ensure limit is integer
        
        try:
            result = self._make_request(
                f"/server/comparison/sector/{sector}",
                params=params
            )
        except ValueError as e:
            # Handle backend errors gracefully by returning error response
            result = {
                "status": "error",
                "message": str(e),
                "data": []  # Return empty list instead of None for consistency
            }
        
        # Ensure data is a list for consistency
        if result.get("data") is None:
            result["data"] = []
        elif not isinstance(result["data"], list):
            result["data"] = [result["data"]] if result["data"] else []
        
        return result


# ============================================================================
# LANGCHAIN TOOL FACTORY
# ============================================================================

def create_ac_financial_tool(api_key: Optional[str] = None) -> Any:
    """
    Factory function to create a LangChain tool for AC Financial Data API.
    
    Creates a stateless, agent-safe tool that can be used with:
      - AgentExecutor
      - ReAct agents
      - Function-calling LLMs
    
    Args:
        api_key: Optional API key. If None, reads from AC_API_KEY in .env file.
    
    Returns:
        LangChain Tool instance ready for agent integration
    
    Raises:
        ValueError: If API key not available
    
    Example Usage:
        tool = create_ac_financial_tool()
        
        # Use with LangChain agent
        tools = [tool]
        agent = initialize_agent(
            tools,
            llm,
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION
        )
    """
    
    # Initialize API client once (reused across tool invocations)
    client = ACFinancialAPIClient(api_key=api_key)
    
    @tool(
        "ac_financial_data_tool",
        args_schema=ACFinancialDataInput,
        return_direct=False
    )
    def ac_financial_data(
        action: str,
        symbol: Optional[str] = None,
        year: Optional[int] = None,
        sector: Optional[str] = None,
        metric: Optional[str] = None,
        limit: Optional[int] = None
    ) -> str:
        """
        Fetch financial data from AC Financial Data API (Indian Stock Market - NSE/BSE).
        
        Routes requests to specific API endpoints based on action parameter.
        Returns raw JSON responses exactly as received from API.
        
        ========================================================================
        ACTIONS (use exactly):
        ========================================================================
        
        status
          - Get API health status (no auth required)
          - No parameters needed
          
        company
          - Get complete financial data for a stock (all statements)
          - Required: symbol (e.g., RELIANCE.NS)
          - Optional: year (2022-2025)
          
        balancesheet
          - Get balance sheet (assets, liabilities, equity)
          - Required: symbol
          - Optional: year
          
        pnl
          - Get profit & loss statement (income statement)
          - Required: symbol
          - Optional: year
          
        cfs
          - Get cash flow statement (OCF, ICF, FCF)
          - Required: symbol
          - Optional: year
          
        ratios
          - Get calculated financial ratios (ROE, ROA, margins, etc.)
          - Required: symbol
          - Optional: year
          
        links
          - Get URLs to NSE/BSE official financial documents
          - Required: symbol
          - Optional: year
          
        news
          - Get latest company news articles
          - Required: symbol
          - No optional parameters
          
        sector_comparison
          - Compare top companies in a sector by metric
          - Required: sector (e.g., Technology, Banking)
          - Optional: metric (e.g., marketCapitalization, revenue)
          - Optional: limit (default 10, max 100)
        
        ========================================================================
        SYMBOL FORMAT:
        ========================================================================
        
        Indian stocks must include exchange suffix:
          - .NS for NSE (National Stock Exchange)
          - .BO for BSE (Bombay Stock Exchange)
          
        Examples:
          - RELIANCE.NS (Reliance on NSE)
          - TCS.NS (Tata Consultancy Services on NSE)
          - INFY.BO (Infosys on BSE)
          - HDFC BANK.NS (HDFC Bank on NSE)
        
        ========================================================================
        YEAR PARAMETER:
        ========================================================================
        
        Supported years: 2022, 2023, 2024, 2025
        Fiscal year runs April 1 - March 31 in India
        If omitted, most recent available year is returned
        
        ========================================================================
        RESPONSE FORMAT:
        ========================================================================
        
        All responses returned as JSON string with structure:
        {
          "status": "success" | "error" | "not_found" | "bad_request",
          "message": "Human-readable status message",
          "data": { ... raw data from API ... }
        }
        
        Parse JSON string to access data:
        import json
        response = json.loads(tool_output)
        financial_data = response["data"]
        
        ========================================================================
        AGENT USAGE EXAMPLES:
        ========================================================================
        
        Example 1: Get latest financials for a stock
          action="company", symbol="RELIANCE.NS"
          
        Example 2: Get FY2024 balance sheet
          action="balancesheet", symbol="TCS.NS", year=2024
          
        Example 3: Find top 5 Technology companies by market cap
          action="sector_comparison", sector="Technology", 
          metric="marketCapitalization", limit=5
          
        Example 4: Get news about Infosys
          action="news", symbol="INFY.NS"
          
        Example 5: Get cash flow statement for past 3 years
          (Make 3 separate calls with year=2023, 2024, 2025)
          action="cfs", symbol="HDFCBANK.NS", year=2024
        
        ========================================================================
        """
        
        try:
            # Input validation happens via Pydantic schema (ACFinancialDataInput)
            # No extra validation needed here
            
            # Route request based on action
            if action == "status":
                result = client.get_status()
            
            elif action == "company":
                result = client.get_company(symbol, year)
            
            elif action == "balancesheet":
                result = client.get_balancesheet(symbol, year)
            
            elif action == "pnl":
                result = client.get_pnl(symbol, year)
            
            elif action == "cfs":
                result = client.get_cfs(symbol, year)
            
            elif action == "ratios":
                result = client.get_ratios(symbol, year)
            
            elif action == "links":
                result = client.get_links(symbol, year)
            
            elif action == "news":
                result = client.get_news(symbol)
            
            elif action == "sector_comparison":
                result = client.get_sector_comparison(sector, metric, limit)
            
            else:
                # Should not reach here due to Pydantic enum validation
                raise ValueError(f"Unknown action: {action}")
            
            # Return raw API response as JSON string
            return json.dumps(result)
        
        except ValueError as e:
            # Validation or API error
            error_response = {
                "status": "error",
                "message": str(e),
                "data": None
            }
            return json.dumps(error_response)
        
        except Exception as e:
            # Unexpected error
            error_response = {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
                "data": None
            }
            return json.dumps(error_response)
    
    return ac_financial_data


# ============================================================================
# TESTING & EXAMPLES (not executed in production)
# ============================================================================

if __name__ == "__main__":
    """
    Local testing examples. Requires AC_API_KEY in .env file.
    
    Setup: Create .env file with: AC_API_KEY=your_key
    Run: python ac_financial_tool.py
    """
    
    print("=" * 80)
    print("AC Financial Data Tool - Testing")
    print("=" * 80)
    
    try:
        # Create tool instance
        tool = create_ac_financial_tool()
        print("\n✓ Tool created successfully")
        
        # Test 1: API Status
        print("\n[Test 1] API Status")
        result = tool.invoke({"action": "status"})
        response = json.loads(result)
        print(f"Status: {response['status']}")
        print(f"Message: {response['message']}")
        
        # Test 2: Company Data
        print("\n[Test 2] Company Data (RELIANCE.NS)")
        result = tool.invoke({"action": "company", "symbol": "RELIANCE.NS"})
        response = json.loads(result)
        print(f"Status: {response['status']}")
        if response['status'] == 'success':
            data = response['data']
            if isinstance(data, list) and len(data) > 0:
                first = data[0]
                print(f"Symbol: {first.get('symbol')}")
                print(f"Year: {first.get('calendarYear')}")
                print(f"Revenue: {first.get('revenue')}")
        
        # Test 3: Sector Comparison
        print("\n[Test 3] Sector Comparison (Technology)")
        result = tool.invoke({
            "action": "sector_comparison",
            "sector": "Technology",
            "limit": 5
        })
        response = json.loads(result)
        print(f"Status: {response['status']}")
        if response['status'] == 'success':
            data = response['data']
            print(f"Results: {len(data) if isinstance(data, list) else 'N/A'}")
        
        # Test 4: Input Validation
        print("\n[Test 4] Input Validation (bad symbol)")
        result = tool.invoke({
            "action": "company",
            "symbol": "RELIANCE"  # Missing .NS/.BO
        })
        response = json.loads(result)
        print(f"Status: {response['status']}")
        print(f"Message: {response['message']}")
        
        print("\n" + "=" * 80)
        print("Testing complete!")
        print("=" * 80)
    
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nMake sure AC_API_KEY is set in .env file:")
        print("  Create a .env file with: AC_API_KEY=your_api_key")
        print("  python ac_financial_tool.py")
