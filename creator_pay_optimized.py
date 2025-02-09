import numpy as np
import pandas as pd

def calculate_rpm(monthly_price, yearly_price, monthly_split, yearly_split, conversion_rate, min_views_clause, wes):
    """
    Calculates Revenue Per Mille (RPM) based on subscription revenue and adjusts for MVC and WES.
    """
    monthly_revenue = monthly_price * monthly_split
    yearly_revenue = (yearly_price / 12) * yearly_split
    
    rpm = conversion_rate * (monthly_revenue + yearly_revenue) * 1000
    adjusted_rpm = rpm * (min_views_clause / 1000000) * (wes / 10)  # Adjusting revenue based on MVC and WES
    
    return adjusted_rpm

def estimate_realistic_cpm(wes, rpm):
    """
    Estimates an optimal CPM based on WES and ensures profitability.
    """
    max_safe_cpm = rpm * 0.8  # Ensures at least 20% profit margin
    wes_modifier = 0.8 + (wes / 10) * 0.4  # Adjusts CPM based on engagement quality
    
    return max_safe_cpm * wes_modifier

def estimate_expected_views(avg_views_per_post, posts_per_month, wes):
    """
    Estimates the expected views based on influencer's historical performance and engagement.
    """
    return avg_views_per_post * posts_per_month * (wes / 10)

def calculate_revenue_per_post(rpm, avg_views_per_post, wes):
    """
    Calculates the estimated revenue per post based on RPM and influencer engagement.
    """
    return (rpm / 1000) * avg_views_per_post * (wes / 10)

def calculate_total_payment(optimal_cpm, expected_views):
    """
    Calculates the total payment to the influencer based on optimal CPM and expected views.
    """
    return (optimal_cpm / 1000) * expected_views

# Default values
default_monthly_price = 5.70
default_yearly_price = 10.00
default_monthly_split = 0.80  # 80% of users choose monthly
default_yearly_split = 0.20  # 20% of users choose yearly
default_conversion_rate = 0.02  # 2% conversion rate
default_avg_views_per_post = 100000
default_posts_per_month = 4

# User inputs with default fallback
monthly_price = default_monthly_price
yearly_price = default_yearly_price
monthly_split = default_monthly_split
yearly_split = default_yearly_split
conversion_rate = default_conversion_rate
avg_views_per_post = default_avg_views_per_post
posts_per_month = default_posts_per_month
wes = 7.5  # Higher engagement score
min_views_clause = avg_views_per_post * posts_per_month * 0.8  # 80% of estimated views

expected_views = estimate_expected_views(avg_views_per_post, posts_per_month, wes)
rpm = calculate_rpm(monthly_price, yearly_price, monthly_split, yearly_split, conversion_rate, min_views_clause, wes)
optimal_cpm = estimate_realistic_cpm(wes, rpm)
revenue_per_post = calculate_revenue_per_post(rpm, avg_views_per_post, wes)
total_payment = calculate_total_payment(optimal_cpm, expected_views)
profitability = optimal_cpm <= rpm

result = {
    "Influencer": "Optimized Deal",
    "Expected Views": expected_views,
    "Optimal CPM": optimal_cpm,
    "Total Payment": total_payment,
    "Revenue Per Post": revenue_per_post,
    "Profitability": profitability,
    "Minimum Views Required": min_views_clause,
    "Weighted Engagement Score (WES)": wes,
    "RPM Adjusted": rpm
}

df = pd.DataFrame([result])
import ace_tools as tools
tools.display_dataframe_to_user(name="Optimal Influencer CPM & Profitability Report", dataframe=df)
