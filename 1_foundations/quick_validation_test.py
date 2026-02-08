#!/usr/bin/env python3
"""Quick validation test."""
from aca_var_tool import ACFinancialDataInput

print("Test 1: Missing symbol with company action")
try:
    result = ACFinancialDataInput(action="company")
    print(f"  ✗ FAILED: Created successfully (should have failed)")
except Exception as e:
    print(f"  ✓ PASSED: {str(e)[:80]}")

print("\nTest 2: Missing sector with sector_comparison action")
try:
    result = ACFinancialDataInput(action="sector_comparison")
    print(f"  ✗ FAILED: Created successfully (should have failed)")
except Exception as e:
    print(f"  ✓ PASSED: {str(e)[:80]}")

print("\nTest 3: Valid company action with symbol")
try:
    result = ACFinancialDataInput(action="company", symbol="RELIANCE.NS")
    print(f"  ✓ PASSED: Created successfully")
except Exception as e:
    print(f"  ✗ FAILED: {e}")

print("\nTest 4: Invalid symbol format")
try:
    result = ACFinancialDataInput(action="company", symbol="RELIANCE")
    print(f"  ✗ FAILED: Created successfully (should have failed)")
except Exception as e:
    print(f"  ✓ PASSED: {str(e)[:80]}")
