import numpy as np
import pandas as pd

def get_input(prompt, default):
    """Get user input with a default fallback."""
    value = input(f"{prompt} (Press Enter to use default: {default}): ")
    return float(value) if value.strip() else default

def calculate_rpm(monthly_price, yearly_price, monthly_split, yearly_split, conversion_rate, min_views_clause, wes):
    """
    Calculates Revenue Per Mille (RPM) based on subscription revenue and adjusts for MVC and WES.
    """
    monthly_revenue = monthly_price * monthly_split
    yearly_revenue = (yearly_price / 12) * yearly_split
    
    rpm = conversion_rate * (monthly_revenue + yearly_revenue) * 1000
    adjusted_rpm = rpm * (min_views_clause / 1000000) * (wes / 10)  # Adjusting revenue based on MVC and WES
    
    return adjusted_rpm

def calculate_effective_cpm(total_payment, expected_views):
    """
    Calculates the effective Cost Per Mille (CPM) based on influencer payment and expected views.
    """
    return (total_payment / expected_views) * 1000

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

# Default values
default_monthly_price = 5.70
default_yearly_price = 10.00
default_monthly_split = 0.80  # 80% of users choose monthly
default_yearly_split = 0.20  # 20% of users choose yearly
default_conversion_rate = 0.02  # 2% conversion rate
default_avg_views_per_post = 100000
default_posts_per_month = 4

# User inputs with default fallback
monthly_price = get_input("Enter Monthly Subscription Price", default_monthly_price)
yearly_price = get_input("Enter Yearly Subscription Price", default_yearly_price)
monthly_split = get_input("Enter Monthly Subscription Split (0-1)", default_monthly_split)
yearly_split = get_input("Enter Yearly Subscription Split (0-1)", default_yearly_split)
conversion_rate = get_input("Enter Conversion Rate (0-1)", default_conversion_rate)

influencer_name = input("Enter Influencer Name: ")
total_payment = get_input("Enter Total Payment for Influencer", 4000)
avg_views_per_post = get_input("Enter Influencer's Average Views Per Post", default_avg_views_per_post)
posts_per_month = get_input("Enter Expected Posts Per Month", default_posts_per_month)
wes = get_input("Enter Weighted Engagement Score (WES) for Influencer (0-10)", 5.0)
min_views_clause = get_input("Enter Minimum View Clause for Influencer", avg_views_per_post * posts_per_month * 0.8)  # 80% of estimated views

expected_views = estimate_expected_views(avg_views_per_post, posts_per_month, wes)
rpm = calculate_rpm(monthly_price, yearly_price, monthly_split, yearly_split, conversion_rate, min_views_clause, wes)
effective_cpm = calculate_effective_cpm(total_payment, expected_views)
revenue_per_post = calculate_revenue_per_post(rpm, avg_views_per_post, wes)
profitability = effective_cpm <= rpm

result = {
    "Influencer": influencer_name,
    "Total Payment": total_payment,
    "Expected Views": expected_views,
    "Effective CPM": effective_cpm,
    "Revenue Per Post": revenue_per_post,
    "Profitability": profitability,
    "Minimum Views Required": min_views_clause,
    "Weighted Engagement Score (WES)": wes,
    "RPM Adjusted": rpm
}

df = pd.DataFrame([result])
import ace_tools as tools
tools.display_dataframe_to_user(name="Influencer Payment & Profitability Report", dataframe=df)

