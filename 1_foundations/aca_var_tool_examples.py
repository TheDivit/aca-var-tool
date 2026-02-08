"""
AC Financial Data Tool - LangChain Integration Examples

Demonstrates how to integrate the AC Financial Data tool with:
  - ReAct agents
  - Structured Chat agents
  - Function-calling LLMs
  - Custom tool composition

Read this for patterns to use in your AI agent implementation.
"""

import json
import os
from typing import Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# LangChain imports
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain.tools import Tool

# Import the tool factory
from aca_var_tool import create_ac_financial_tool


# ============================================================================
# EXAMPLE 1: ReAct Agent with AC Financial Data Tool
# ============================================================================

def create_react_stock_analyzer() -> AgentExecutor:
    """
    Create a ReAct (Reasoning + Acting) agent for stock analysis.
    
    The agent can:
      - Query financial data
      - Reason over statements
      - Ask follow-up questions
      - Build multi-step analyses
    
    Requires:
      - OPENAI_API_KEY in .env file
      - AC_API_KEY in .env file
    """
    
    # Create LLM
    llm = ChatOpenAI(model="gpt-4", temperature=0)
    
    # Create tool
    ac_tool = create_ac_financial_tool()
    tools = [ac_tool]
    
    # ReAct prompt template
    prompt = PromptTemplate.from_template("""
You are a financial analyst AI agent specializing in Indian stock market analysis.
You have access to the AC Financial Data API tool for fetching company financials.

Use the tool to answer questions about Indian stocks (NSE/BSE).

When querying:
  1. Always use correct symbol format: SYMBOL.NS (NSE) or SYMBOL.BO (BSE)
  2. For multi-year analysis, make separate queries for each year
  3. Return raw data to the user without heavy interpretation

Question: {input}

{agent_scratchpad}
""")
    
    # Create agent
    agent = create_react_agent(llm, tools, prompt)
    
    # Return executor
    return AgentExecutor.from_agent_and_tools(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=10,
        handle_parsing_errors=True
    )


# ============================================================================
# EXAMPLE 2: Structured Chat Agent for Portfolio Analysis
# ============================================================================

def create_portfolio_analyzer() -> AgentExecutor:
    """
    Create a structured chat agent for analyzing stock portfolios.
    
    Demonstrates how the tool can be used in a more controlled environment
    with explicit message flow.
    """
    
    from langchain.agents import AgentType, initialize_agent
    
    # Create LLM
    llm = ChatOpenAI(model="gpt-4", temperature=0)
    
    # Create tool
    ac_tool = create_ac_financial_tool()
    
    # Initialize structured chat agent
    agent = initialize_agent(
        tools=[ac_tool],
        llm=llm,
        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
        max_iterations=15,
        early_stopping_method="generate"
    )
    
    return agent


# ============================================================================
# EXAMPLE 3: Custom Tool Wrapper for Specific Workflows
# ============================================================================

def create_valuation_tool() -> Tool:
    """
    Create a specialized tool that uses AC Financial Data tool internally
    for DCF valuation analysis.
    
    This demonstrates composition: wrapping the API tool for domain-specific use.
    """
    
    ac_tool = create_ac_financial_tool()
    
    def valuation_analysis(symbol: str, years: int = 3) -> str:
        """
        Fetch data needed for DCF valuation analysis.
        
        Returns raw financials (cash flow, revenue, margins) for a stock.
        """
        
        try:
            # Fetch cash flow (needed for FCF calculation)
            cfs_result = ac_tool.invoke({
                "action": "cfs",
                "symbol": symbol,
                "year": 2025
            })
            cfs_data = json.loads(cfs_result)
            
            # Fetch income statement (needed for margins)
            pnl_result = ac_tool.invoke({
                "action": "pnl",
                "symbol": symbol,
                "year": 2025
            })
            pnl_data = json.loads(pnl_result)
            
            # Fetch balance sheet (needed for WACC)
            bs_result = ac_tool.invoke({
                "action": "balancesheet",
                "symbol": symbol,
                "year": 2025
            })
            bs_data = json.loads(bs_result)
            
            # Combine results
            combined = {
                "symbol": symbol,
                "cfs": cfs_data.get("data"),
                "pnl": pnl_data.get("data"),
                "balancesheet": bs_data.get("data"),
                "status": "success" if all([
                    cfs_data.get("status") == "success",
                    pnl_data.get("status") == "success",
                    bs_data.get("status") == "success"
                ]) else "partial"
            }
            
            return json.dumps(combined)
        
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": str(e),
                "symbol": symbol
            })
    
    return Tool(
        name="valuation_analysis_tool",
        func=valuation_analysis,
        description="Fetch complete financial data (CFS, P&L, Balance Sheet) needed for DCF valuation. "
                    "Requires symbol in format SYMBOL.NS or SYMBOL.BO"
    )


# ============================================================================
# EXAMPLE 4: Sector Comparison Tool
# ============================================================================

def create_sector_analyzer_tool() -> Tool:
    """
    Create a specialized tool for sector analysis and comparisons.
    
    Wraps the sector_comparison endpoint for easier agent reasoning.
    """
    
    ac_tool = create_ac_financial_tool()
    
    def compare_sectors(sector: str, metric: str = "marketCapitalization", limit: int = 10) -> str:
        """
        Compare top companies in a sector by specified metric.
        """
        
        result = ac_tool.invoke({
            "action": "sector_comparison",
            "sector": sector,
            "metric": metric,
            "limit": limit
        })
        
        return result
    
    return Tool(
        name="sector_comparison_tool",
        func=compare_sectors,
        description="Compare top companies within a sector. "
                    "Sectors: Technology, Banking, Pharma, Automobiles, etc. "
                    "Metrics: marketCapitalization, revenue, netIncome, eps, etc.",
        return_direct=True
    )


# ============================================================================
# EXAMPLE 5: Multi-Year Financial Analysis Tool
# ============================================================================

def create_historical_analysis_tool() -> Tool:
    """
    Create a tool that fetches multi-year historical data for trend analysis.
    
    Demonstrates handling of the year parameter for time-series analysis.
    """
    
    ac_tool = create_ac_financial_tool()
    
    def get_historical_financials(symbol: str, metric: str = "revenue") -> str:
        """
        Fetch historical data for 2022-2025 for trend analysis.
        
        metric: One of 'revenue', 'netIncome', 'eps', 'totalAssets'
        """
        
        try:
            results = {}
            
            for year in [2022, 2023, 2024, 2025]:
                # Fetch company data for each year
                result = ac_tool.invoke({
                    "action": "company",
                    "symbol": symbol,
                    "year": year
                })
                
                data = json.loads(result)
                
                if data.get("status") == "success":
                    # Extract specific metric
                    if isinstance(data.get("data"), list) and len(data["data"]) > 0:
                        value = data["data"][0].get(metric)
                        results[year] = value
            
            return json.dumps({
                "symbol": symbol,
                "metric": metric,
                "historical_data": results,
                "status": "success" if results else "no_data"
            })
        
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": str(e)
            })
    
    return Tool(
        name="historical_analysis_tool",
        func=get_historical_financials,
        description="Get historical financial metrics (2022-2025) for trend analysis. "
                    "Metrics: revenue, netIncome, eps, totalAssets, etc. "
                    "Symbol format: SYMBOL.NS or SYMBOL.BO",
        return_direct=False
    )


# ============================================================================
# EXAMPLE 6: Risk Analysis Tool
# ============================================================================

def create_risk_analysis_tool() -> Tool:
    """
    Create a tool that gathers data for solvency and leverage analysis.
    """
    
    ac_tool = create_ac_financial_tool()
    
    def analyze_financial_risk(symbol: str) -> str:
        """
        Fetch balance sheet and P&L for leverage, solvency, liquidity analysis.
        """
        
        try:
            # Get balance sheet (debt, cash, current assets/liabilities)
            bs_result = ac_tool.invoke({
                "action": "balancesheet",
                "symbol": symbol,
                "year": 2025
            })
            bs_data = json.loads(bs_result)
            
            # Get P&L (EBIT, interest expense for coverage ratio)
            pnl_result = ac_tool.invoke({
                "action": "pnl",
                "symbol": symbol,
                "year": 2025
            })
            pnl_data = json.loads(pnl_result)
            
            # Get financial ratios (Debt/Equity, Interest Coverage)
            ratios_result = ac_tool.invoke({
                "action": "ratios",
                "symbol": symbol,
                "year": 2025
            })
            ratios_data = json.loads(ratios_result)
            
            return json.dumps({
                "symbol": symbol,
                "balance_sheet": bs_data.get("data"),
                "pnl": pnl_data.get("data"),
                "ratios": ratios_data.get("data"),
                "status": "success"
            })
        
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": str(e)
            })
    
    return Tool(
        name="risk_analysis_tool",
        func=analyze_financial_risk,
        description="Analyze financial risk: leverage, debt service coverage, liquidity. "
                    "Returns balance sheet, P&L, and calculated ratios. "
                    "Symbol format: SYMBOL.NS or SYMBOL.BO",
        return_direct=False
    )


# ============================================================================
# EXAMPLE 7: Complete Multi-Tool Agent
# ============================================================================

def create_complete_agent() -> AgentExecutor:
    """
    Create a comprehensive agent with multiple specialized tools.
    
    Demonstrates how to compose multiple tools for complex analysis tasks.
    """
    
    from langchain.agents import AgentType, initialize_agent
    
    llm = ChatOpenAI(model="gpt-4", temperature=0)
    
    # Create multiple specialized tools
    tools = [
        create_ac_financial_tool(),           # Raw API access
        create_valuation_tool(),              # DCF data gathering
        create_sector_analyzer_tool(),        # Sector comparison
        create_historical_analysis_tool(),    # Trend analysis
        create_risk_analysis_tool(),          # Risk assessment
    ]
    
    # Initialize agent with all tools
    agent = initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
        max_iterations=20,
        early_stopping_method="generate"
    )
    
    return agent


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    """
    Test the integration examples.
    
    Requires:
      - OPENAI_API_KEY
      - AC_API_KEY
    """
    
    print("=" * 80)
    print("AC Financial Data Tool - Integration Examples")
    print("=" * 80)
    
    # Check API key
    if not os.getenv("AC_API_KEY"):
        print("\n✗ AC_API_KEY not set")
        print("  export AC_API_KEY=your_key")
        exit(1)
    
    # Example 1: Test basic tool
    print("\n[Example 1] Basic Tool Test")
    print("-" * 80)
    
    try:
        tool = create_ac_financial_tool()
        
        result = tool.invoke({
            "action": "company",
            "symbol": "RELIANCE.NS"
        })
        
        data = json.loads(result)
        print(f"Status: {data['status']}")
        print(f"Tool works: ✓")
    except Exception as e:
        print(f"Error: {e}")
    
    # Example 2: Test sector analyzer tool
    print("\n[Example 2] Sector Analyzer Tool")
    print("-" * 80)
    
    try:
        sector_tool = create_sector_analyzer_tool()
        
        result = sector_tool.func("Technology", "marketCapitalization", 5)
        
        data = json.loads(result)
        print(f"Status: {data['status']}")
        print(f"Tool works: ✓")
    except Exception as e:
        print(f"Error: {e}")
    
    # Example 3: Test historical analysis tool
    print("\n[Example 3] Historical Analysis Tool")
    print("-" * 80)
    
    try:
        hist_tool = create_historical_analysis_tool()
        
        result = hist_tool.func("TCS.NS", "revenue")
        
        data = json.loads(result)
        print(f"Status: {data['status']}")
        print(f"Historical data: {data.get('historical_data')}")
        print(f"Tool works: ✓")
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "=" * 80)
    print("Integration examples ready for use!")
    print("=" * 80)
