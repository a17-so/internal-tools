import streamlit as st

# Layout configuration
st.set_page_config(layout="wide")

def calculate_influencer_deal(avg_views, likes, comments, comment_quality, num_posts, base_cpm):
    """
    Calculates the influencer deal structure, including engagement rate, predicted RPM,
    total cost, revenue, minimum views for profitability, and bonus structure.
    """

    # Step 1: Engagement Metrics
    engagement_rate = (likes + comments) / avg_views  # Engagement rate calculation
    engagement_quality_factor = (engagement_rate * 0.5) + (comment_quality / 10)  # Adjusted for comment quality

    
    # Step 2: Engagement-Adjusted CPM
    benchmark_engagement = 0.05  # 5% baseline engagement rate
    weight_factor = 0.5  # Sensitivity multiplier
    adjusted_cpm = base_cpm * (1 + ((engagement_rate - benchmark_engagement) * weight_factor))
    adjusted_cpm = max(adjusted_cpm, base_cpm * 0.5)  # Ensure CPM doesn't drop too low
    adjusted_cpm = min(adjusted_cpm, base_cpm * 1.5)  # Cap increase

    
    # Step 2: Revenue per 1000 views (RPM)
    base_rpm = 6  # Default RPM assumption
    predicted_rpm = base_rpm * (1 + engagement_quality_factor)  # Adjusted RPM based on engagement

    # Step 3: Total Expected Views
    total_expected_views = avg_views * num_posts  # Total deal reach

    # Step 4: Cost Calculation
    total_cost = (total_expected_views / 1000) * adjusted_cpm  # Cost based on CPM model
    cost_per_post = total_cost / num_posts  # New: Calculate cost per post

    # Step 5: Minimum Views for Profit (MVC)
    min_views_for_profit = (total_cost / predicted_rpm) * 1000  # Views needed to break even

    # Step 6: Bonus Threshold Calculation (Dynamic)
    bonus_trigger_factor = 0.15  # Bonus triggers at 15% more than MVC
    bonus_threshold_views = min_views_for_profit * (1 + bonus_trigger_factor)  # Calculate threshold dynamically


    # Step 7: Extra Views Calculation
    extra_views = max(total_expected_views - min_views_for_profit, 0)  # Only positive values considered

    # Step 8: Bonus Calculation (Updated Bonus Logic)
    if extra_views > 0:
        if extra_views < 500000:
            bonus_amount = (extra_views / 500000) * 500  # Scale bonus up to $500 at 500k extra views
        elif extra_views <= 1000000:
            bonus_amount = 500  # Fixed bonus for extra views between 500k and 1M
        else:
            bonus_amount = 500 + ((extra_views - 1000000) / 500000) * 250  # Additional bonus above 1M views
    else:
        bonus_amount = 0  # No bonus if no extra views


    # Step 9: Revenue Calculation
    total_revenue = (total_expected_views / 1000) * predicted_rpm  # Revenue generated
    revenue_per_post = total_revenue / num_posts  # Revenue per individual post

    # Step 10: Profit Calculation
    profit = total_revenue - total_cost  # Final profit margin

    return {
        "Engagement Rate (%)": round(engagement_rate * 100, 2),
        "Predicted RPM": round(predicted_rpm, 2),
        "Total Expected Views": total_expected_views,
        "Total Cost ($)": round(total_cost, 2),
        "Cost per Post ($)": round(cost_per_post, 2),
        "Min Views for Profit": round(min_views_for_profit),
        "Bonus Threshold Views": round(bonus_threshold_views),  # Now dynamically calculated
        "Bonus Amount ($)": round(bonus_amount, 2),
        "Total Revenue ($)": round(total_revenue, 2),
        "Revenue per Post ($)": round(revenue_per_post, 2),
        "Total Profit ($)": round(profit, 2)
    }


st.title("Influencer Deal Calculator")

st.sidebar.header("Input Parameters")
st.sidebar.markdown("Over their last 30 posts")
avg_views = st.sidebar.number_input("Average Views per Post", min_value=1, value=5000, step=1000)
likes = st.sidebar.number_input("Average Likes per Post", min_value=0, value=100, step=10)
comments = st.sidebar.number_input("Average Comments per Post", min_value=0, value=50, step=10)
comment_quality = st.sidebar.slider("Average Comment Quality (1-10)", min_value=1, max_value=10, value=5)
num_posts = st.sidebar.number_input("Number of Posts in Deal", min_value=1, value=4, step=1)
base_cpm = st.sidebar.number_input("CPM (Cost per 1000 Views)", min_value=1.0, value=3.0, step=0.5)

if st.sidebar.button("Calculate Deal"):
    result = calculate_influencer_deal(avg_views, likes, comments, comment_quality, num_posts, base_cpm)
    
    col1, col2, col3 = st.columns([1, 1, 1], gap="large")
    
    with col1:
        st.subheader("Creator Metrics")
        st.markdown("---")
        st.markdown(f"<div style='background-color:#1E1E2F; padding:20px; border-radius:10px; text-align:center; color:white; margin-bottom:10px;'><h4>Engagement Rate</h4><h1>{result['Engagement Rate (%)']}%</h1></div>", unsafe_allow_html=True)
        st.markdown(f"<div style='background-color:#1E1E2F; padding:20px; border-radius:10px; text-align:center; color:white;'><h4>Total Expected Views</h4><h1>{result['Total Expected Views']:,}</h1></div>", unsafe_allow_html=True)
    
    with col2:
        st.subheader("Cost Metrics")
        st.markdown("---")
        st.markdown(f"<div style='background-color:#1E1E2F; padding:20px; border-radius:10px; text-align:center; color:white; margin-bottom:10px;'><h4>Total Deal Cost</h4><h1>${result['Total Cost ($)']}</h1></div>", unsafe_allow_html=True)
        st.markdown(f"<div style='background-color:#1E1E2F; padding:20px; border-radius:10px; text-align:center; color:white; margin-bottom:10px;'><h4>Cost per Post ({num_posts} Posts)</h4><h1>${result['Cost per Post ($)']}</h1></div>", unsafe_allow_html=True)  # New card
        st.markdown(f"<div style='background-color:#1E1E2F; padding:20px; border-radius:10px; text-align:center; color:white; margin-bottom:10px;'><h4>Minimum Views for Profit (MVC)</h4><h1>{result['Min Views for Profit']:,}</h1></div>", unsafe_allow_html=True)
        st.markdown(f"<div style='background-color:#1E1E2F; padding:20px; border-radius:10px; text-align:center; color:white;'><h4>Potential Bonus</h4><h1>${result['Bonus Amount ($)']} at {result['Bonus Threshold Views']:,} extra views</h1></div>", unsafe_allow_html=True)
    
    with col3:
        st.subheader("Revenue Metrics")
        st.markdown("---")
        st.markdown(f"<div style='background-color:#1E1E2F; padding:20px; border-radius:10px; text-align:center; color:white; margin-bottom:10px;'><h4>Total Revenue Off of Deal</h4><h1>${result['Total Revenue ($)']}</h1></div>", unsafe_allow_html=True)
        st.markdown(f"<div style='background-color:#1E1E2F; padding:20px; border-radius:10px; text-align:center; color:white; margin-bottom:10px;'><h4>Revenue Per Post</h4><h1>${result['Revenue per Post ($)']}</h1></div>", unsafe_allow_html=True)
        st.markdown(f"<div style='background-color:#1E1E2F; padding:20px; border-radius:10px; text-align:center; color:white; margin-bottom:10px;'><h4>Predicted RPM</h4><h1>${result['Predicted RPM']}</h1></div>", unsafe_allow_html=True)
        st.markdown(f"<div style='background-color:#1E1E2F; padding:20px; border-radius:10px; text-align:center; color:white;'><h4>Total Profit for Deal</h4><h1>${result['Total Profit ($)']}</h1></div>", unsafe_allow_html=True)
