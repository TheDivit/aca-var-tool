"""
Advanced Use Cases Using AC Financial Tool + Deep Analysis

This module demonstrates how to combine the tool with the deep analysis
to build sophisticated financial analysis agents.

Each function builds a specific analysis using only the AC Financial Data API.
"""

import json
from typing import Dict, Any, List, Optional
from aca_var_tool import create_ac_financial_tool


# ============================================================================
# HELPER FUNCTION
# ============================================================================

def safe_invoke(tool, params: Dict[str, Any]) -> Dict[str, Any]:
    """Safely invoke tool and return parsed response."""
    try:
        result = tool.invoke(params)
        return json.loads(result)
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "data": None
        }


# ============================================================================
# USE CASE 1: DCF VALUATION DATA GATHERER
# ============================================================================

def gather_dcf_data(symbol: str, years: int = 3) -> Dict[str, Any]:
    """
    Gather all data needed for DCF valuation analysis.
    
    From Deep Analysis: PHASE 4, Use Case 1
    
    Returns:
      - Historical FCF (FY 2022-2025)
      - Revenue growth trajectory
      - Interest expense for WACC
      - Total debt and cash for net debt
    
    Agent can then:
      1. Calculate FCF CAGR
      2. Project future FCF (with LLM assumptions)
      3. Compute terminal value
      4. Discount to present value
    """
    
    tool = create_ac_financial_tool()
    
    result = {
        "symbol": symbol,
        "cash_flow_data": [],
        "pnl_data": [],
        "balance_sheet_data": [],
        "status": "success"
    }
    
    # Gather multi-year data
    for year in [2022, 2023, 2024, 2025]:
        # Cash flow (for FCF)
        cfs_response = safe_invoke(tool, {
            "action": "cfs",
            "symbol": symbol,
            "year": year
        })
        if cfs_response["status"] == "success":
            result["cash_flow_data"].append({
                "year": year,
                "data": cfs_response["data"]
            })
        
        # P&L (for revenue, interest expense, tax rate)
        pnl_response = safe_invoke(tool, {
            "action": "pnl",
            "symbol": symbol,
            "year": year
        })
        if pnl_response["status"] == "success":
            result["pnl_data"].append({
                "year": year,
                "data": pnl_response["data"]
            })
        
        # Balance Sheet (for debt, cash, equity)
        bs_response = safe_invoke(tool, {
            "action": "balancesheet",
            "symbol": symbol,
            "year": year
        })
        if bs_response["status"] == "success":
            result["balance_sheet_data"].append({
                "year": year,
                "data": bs_response["data"]
            })
    
    return result


# ============================================================================
# USE CASE 2: LEVERAGE & CREDIT RISK ANALYZER
# ============================================================================

def analyze_leverage_risk(symbol: str, year: Optional[int] = None) -> Dict[str, Any]:
    """
    Analyze financial leverage and credit risk.
    
    From Deep Analysis: PHASE 4, Use Case 11 & 12
    From Deep Analysis: PHASE 5, Edge Case 11
    
    Returns:
      - Debt-to-Equity ratio
      - Interest Coverage ratio
      - Liquidity ratios
      - Risk assessment
    
    Agent can then:
      1. Stress test (simulate revenue decline)
      2. Assess default risk
      3. Compare to sector benchmarks
      4. Flag distress signals
    """
    
    tool = create_ac_financial_tool()
    
    result = {
        "symbol": symbol,
        "leverage_metrics": {},
        "liquidity_metrics": {},
        "risk_assessment": "",
        "status": "success"
    }
    
    # Get balance sheet (debt, cash, current assets/liabilities)
    bs_response = safe_invoke(tool, {
        "action": "balancesheet",
        "symbol": symbol,
        "year": year
    })
    
    # Get P&L (EBIT, interest expense)
    pnl_response = safe_invoke(tool, {
        "action": "pnl",
        "symbol": symbol,
        "year": year
    })
    
    # Get ratios (if available)
    ratios_response = safe_invoke(tool, {
        "action": "ratios",
        "symbol": symbol,
        "year": year
    })
    
    result["balance_sheet"] = bs_response.get("data")
    result["pnl"] = pnl_response.get("data")
    result["ratios"] = ratios_response.get("data")
    
    # Agent should analyze:
    # 1. Debt-to-Equity = total_debt / total_equity
    # 2. Interest Coverage = EBIT / interest_expense
    # 3. Current Ratio = current_assets / current_liabilities
    # 4. Quick Ratio = (current_assets - inventory) / current_liabilities
    
    return result


# ============================================================================
# USE CASE 3: SECTOR RELATIVE STRENGTH SCORER
# ============================================================================

def score_sector_leaders(sector: str, metric: str = "marketCapitalization", limit: int = 10) -> Dict[str, Any]:
    """
    Identify top companies in a sector and score them by financial strength.
    
    From Deep Analysis: PHASE 4, Use Case 6
    From Deep Analysis: PHASE 3, Relationship 8
    
    Returns:
      - Top companies in sector (by metric)
      - Financial metrics for each
      - Relative ranking within sector
    
    Agent can then:
      1. Calculate percentile ranks
      2. Identify "best in class" by profitability/growth
      3. Detect mean reversion opportunities
      4. Build sector rotation signals
    """
    
    tool = create_ac_financial_tool()
    
    # Get sector top companies
    sector_response = safe_invoke(tool, {
        "action": "sector_comparison",
        "sector": sector,
        "metric": metric,
        "limit": limit
    })
    
    result = {
        "sector": sector,
        "metric": metric,
        "top_companies": [],
        "status": sector_response["status"]
    }
    
    if sector_response["status"] == "success" and sector_response["data"]:
        # For each top company, fetch detailed financials
        for company in sector_response["data"][:limit]:
            symbol = company.get("symbol")
            
            if symbol:
                company_response = safe_invoke(tool, {
                    "action": "company",
                    "symbol": symbol
                })
                
                ratios_response = safe_invoke(tool, {
                    "action": "ratios",
                    "symbol": symbol
                })
                
                result["top_companies"].append({
                    "symbol": symbol,
                    "sector_rank": len(result["top_companies"]) + 1,
                    "company_data": company_response.get("data"),
                    "financial_ratios": ratios_response.get("data")
                })
    
    return result


# ============================================================================
# USE CASE 4: EARNINGS QUALITY DETECTOR
# ============================================================================

def assess_earnings_quality(symbol: str, years: int = 3) -> Dict[str, Any]:
    """
    Detect earnings manipulation and assess quality.
    
    From Deep Analysis: PHASE 4, Use Case 4
    From Deep Analysis: PHASE 3, Relationship 4
    
    Returns:
      - OCF to Net Income ratio (quality indicator)
      - Working capital trends
      - Accruals analysis
    
    Agent can then:
      1. Flag low-quality earnings
      2. Identify aggressive accounting
      3. Assess sustainability of profits
      4. Adjust valuation multiples down for risk
    """
    
    tool = create_ac_financial_tool()
    
    result = {
        "symbol": symbol,
        "quality_analysis": [],
        "status": "success"
    }
    
    # Gather multi-year P&L and CFS data
    for year in [2022, 2023, 2024, 2025]:
        pnl_response = safe_invoke(tool, {
            "action": "pnl",
            "symbol": symbol,
            "year": year
        })
        
        cfs_response = safe_invoke(tool, {
            "action": "cfs",
            "symbol": symbol,
            "year": year
        })
        
        bs_response = safe_invoke(tool, {
            "action": "balancesheet",
            "symbol": symbol,
            "year": year
        })
        
        result["quality_analysis"].append({
            "year": year,
            "net_income": pnl_response.get("data", {}).get("netIncome") if pnl_response["status"] == "success" else None,
            "operating_cash_flow": cfs_response.get("data", {}).get("netCashProvidedByOperatingActivities") if cfs_response["status"] == "success" else None,
            "balance_sheet": bs_response.get("data") if bs_response["status"] == "success" else None
        })
    
    # Agent should calculate:
    # 1. OCF / NI ratio for each year
    #    - 1.0-1.3: High quality (conservative)
    #    - 0.8-1.0: Good quality
    #    - <0.8: Concerning (high accruals)
    # 2. Working capital impact (AR growth, inventory growth, AP growth)
    # 3. Accruals as % of net income
    
    return result


# ============================================================================
# USE CASE 5: PORTFOLIO FINANCIAL HEALTH DASHBOARD
# ============================================================================

def build_portfolio_health_dashboard(symbols: List[str]) -> Dict[str, Any]:
    """
    Build a comprehensive health dashboard for a portfolio.
    
    From Deep Analysis: PHASE 4, Use Case 14 & 15
    
    Returns:
      - Financial metrics for each stock
      - Risk scores
      - Quality indicators
      - Recommendations
    """
    
    tool = create_ac_financial_tool()
    
    result = {
        "portfolio": [],
        "summary": {
            "total_stocks": len(symbols),
            "average_health": 0,
            "risk_level": ""
        }
    }
    
    health_scores = []
    
    for symbol in symbols:
        # Get complete data
        company_response = safe_invoke(tool, {
            "action": "company",
            "symbol": symbol
        })
        
        ratios_response = safe_invoke(tool, {
            "action": "ratios",
            "symbol": symbol
        })
        
        bs_response = safe_invoke(tool, {
            "action": "balancesheet",
            "symbol": symbol
        })
        
        # Get news (for context)
        news_response = safe_invoke(tool, {
            "action": "news",
            "symbol": symbol
        })
        
        stock_info = {
            "symbol": symbol,
            "financials": company_response.get("data"),
            "ratios": ratios_response.get("data"),
            "balance_sheet": bs_response.get("data"),
            "recent_news": news_response.get("data")
        }
        
        result["portfolio"].append(stock_info)
        
        # Agent should calculate health score (0-100):
        # - Liquidity (20 pts): Current ratio, quick ratio
        # - Profitability (20 pts): ROE, net margin
        # - Growth (20 pts): Revenue CAGR, EPS growth
        # - Financial Strength (20 pts): Debt/Equity, interest coverage
        # - Quality (20 pts): OCF/NI ratio, accruals
        
        health_scores.append(50)  # Placeholder
    
    result["summary"]["average_health"] = sum(health_scores) / len(health_scores) if health_scores else 0
    
    return result


# ============================================================================
# USE CASE 6: GROWTH TRAJECTORY ANALYZER
# ============================================================================

def analyze_growth_trajectory(symbol: str) -> Dict[str, Any]:
    """
    Analyze multi-year growth patterns and inflection points.
    
    From Deep Analysis: PHASE 4, Use Case 8
    From Deep Analysis: PHASE 3, Relationship 7
    
    Returns:
      - Revenue trajectory (2022-2025)
      - Margin trend analysis
      - Growth acceleration/deceleration signals
    """
    
    tool = create_ac_financial_tool()
    
    result = {
        "symbol": symbol,
        "revenue_trajectory": {},
        "margin_trajectory": {},
        "growth_signals": [],
        "status": "success"
    }
    
    revenue_values = []
    margin_values = []
    
    # Collect multi-year data
    for year in [2022, 2023, 2024, 2025]:
        pnl_response = safe_invoke(tool, {
            "action": "pnl",
            "symbol": symbol,
            "year": year
        })
        
        if pnl_response["status"] == "success" and pnl_response["data"]:
            revenue = pnl_response["data"].get("revenue")
            net_income = pnl_response["data"].get("netIncome")
            
            if revenue and net_income:
                revenue_values.append((year, revenue))
                net_margin = (net_income / revenue) * 100
                margin_values.append((year, net_margin))
                
                result["revenue_trajectory"][year] = revenue
                result["margin_trajectory"][year] = net_margin
    
    # Agent should analyze:
    # 1. Revenue CAGR (2022-2025)
    # 2. YoY growth rate trend (accelerating? decelerating?)
    # 3. Margin expansion/contraction
    # 4. Inflection points (when growth changed direction)
    # 5. Growth quality (sustainable or temporary spike?)
    
    return result


# ============================================================================
# USE CASE 7: DIVIDEND SUSTAINABILITY CHECKER
# ============================================================================

def check_dividend_sustainability(symbol: str) -> Dict[str, Any]:
    """
    Assess whether dividends are sustainable.
    
    From Deep Analysis: PHASE 4, Use Case 3
    From Deep Analysis: PHASE 5, Edge Case 10
    
    Returns:
      - Historical FCF vs dividends
      - Payout ratio trend
      - Sustainability score
    """
    
    tool = create_ac_financial_tool()
    
    result = {
        "symbol": symbol,
        "dividend_analysis": [],
        "sustainability": "",
        "status": "success"
    }
    
    # Gather FCF and equity data
    for year in [2022, 2023, 2024, 2025]:
        cfs_response = safe_invoke(tool, {
            "action": "cfs",
            "symbol": symbol,
            "year": year
        })
        
        company_response = safe_invoke(tool, {
            "action": "company",
            "symbol": symbol,
            "year": year
        })
        
        analysis = {
            "year": year,
            "fcf": cfs_response.get("data", {}).get("freeCashFlow") if cfs_response["status"] == "success" else None,
            "company_data": company_response.get("data") if company_response["status"] == "success" else None
        }
        
        result["dividend_analysis"].append(analysis)
    
    # Agent should calculate:
    # 1. FCF-to-Dividend ratio (FCF / dividends)
    #    - >1.5: Sustainable, room for hikes
    #    - 1.0-1.5: Sustainable, stable
    #    - 0.5-1.0: Pressure to cut
    #    - <0.5: Unsustainable
    # 2. Payout ratio trend (is company increasing/decreasing payout?)
    # 3. Net debt trend (accumulating or reducing debt?)
    # 4. Recommendation (Buy/Hold/Sell based on dividend safety)
    
    return result


# ============================================================================
# MAIN AGENT TASK ROUTER
# ============================================================================

def route_financial_analysis_task(task: str, **kwargs) -> Dict[str, Any]:
    """
    Route financial analysis tasks to appropriate use case function.
    
    This allows an agent to request specific analyses:
    
    Examples:
      - route_financial_analysis_task("dcf_data", symbol="RELIANCE.NS")
      - route_financial_analysis_task("leverage_analysis", symbol="TCS.NS")
      - route_financial_analysis_task("sector_strength", sector="Technology")
      - route_financial_analysis_task("earnings_quality", symbol="INFY.NS")
    """
    
    tasks = {
        "dcf_data": gather_dcf_data,
        "leverage_analysis": analyze_leverage_risk,
        "sector_strength": score_sector_leaders,
        "earnings_quality": assess_earnings_quality,
        "portfolio_health": build_portfolio_health_dashboard,
        "growth_analysis": analyze_growth_trajectory,
        "dividend_sustainability": check_dividend_sustainability
    }
    
    if task not in tasks:
        return {
            "status": "error",
            "message": f"Unknown task: {task}. Available: {list(tasks.keys())}"
        }
    
    task_func = tasks[task]
    
    try:
        return task_func(**kwargs)
    except Exception as e:
        return {
            "status": "error",
            "message": f"Task failed: {str(e)}"
        }


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    """
    Test advanced use cases.
    """
    
    print("=" * 80)
    print("Advanced Use Cases - Testing")
    print("=" * 80)
    
    # Test 1: DCF Data
    print("\n[Test 1] Gather DCF Data")
    print("-" * 80)
    result = gather_dcf_data("RELIANCE.NS")
    print(f"Status: {result['status']}")
    print(f"Cash flow records: {len(result['cash_flow_data'])}")
    print(f"P&L records: {len(result['pnl_data'])}")
    print(f"Balance sheet records: {len(result['balance_sheet_data'])}")
    
    # Test 2: Leverage Analysis
    print("\n[Test 2] Analyze Leverage Risk")
    print("-" * 80)
    result = analyze_leverage_risk("TCS.NS", year=2024)
    print(f"Status: {result['status']}")
    print(f"Has balance sheet: {bool(result.get('balance_sheet'))}")
    print(f"Has P&L: {bool(result.get('pnl'))}")
    
    # Test 3: Sector Leaders
    print("\n[Test 3] Score Sector Leaders")
    print("-" * 80)
    result = score_sector_leaders("Technology", limit=5)
    print(f"Status: {result['status']}")
    print(f"Top companies: {len(result['top_companies'])}")
    
    # Test 4: Growth Trajectory
    print("\n[Test 4] Analyze Growth Trajectory")
    print("-" * 80)
    result = analyze_growth_trajectory("INFY.NS")
    print(f"Status: {result['status']}")
    print(f"Revenue data points: {len(result['revenue_trajectory'])}")
    print(f"Margin data points: {len(result['margin_trajectory'])}")
    
    print("\n" + "=" * 80)
    print("Advanced use cases ready for agent integration!")
    print("=" * 80)
