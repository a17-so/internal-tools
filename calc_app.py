import streamlit as st

# Layout configuration
st.set_page_config(layout="wide")

def calculate_influencer_deal(avg_views, likes, comments, comment_quality, num_posts, base_cpm):
    engagement_rate = (likes + comments) / avg_views
    engagement_quality_factor = (engagement_rate * 0.5) + (comment_quality / 10)
    base_rpm = 6  # Base Revenue per 1000 views
    predicted_rpm = base_rpm * (1 + engagement_quality_factor)
    total_expected_views = avg_views * num_posts
    total_cost = (total_expected_views / 1000) * base_cpm
    min_views_for_profit = (total_cost / predicted_rpm) * 1000
    extra_views = max(total_expected_views - min_views_for_profit, 0)
    
    if extra_views > 0:
        if extra_views <= min_views_for_profit * 0.25:
            bonus_amount = (extra_views / 100000) * 100  
        elif extra_views <= min_views_for_profit:
            bonus_amount = (extra_views / 100000) * 250  
        else:
            bonus_amount = (min_views_for_profit / 100000) * 400  
    else:
        bonus_amount = 0  
    
    total_revenue = (total_expected_views / 1000) * predicted_rpm
    revenue_per_post = total_revenue / num_posts
    cost_for_bonus = 4000  # Fixed cost for potential bonus based on extra views
    bonus_threshold_views = 100000  # Fixed threshold for additional views
    profit = total_revenue - total_cost  # Profit Calculation
    
    return {
        "Engagement Rate (%)": round(engagement_rate * 100, 2),
        "Predicted RPM": round(predicted_rpm, 2),
        "Total Expected Views": total_expected_views,
        "Total Cost ($)": round(total_cost, 2),
        "Min Views for Profit": round(min_views_for_profit),
        "Bonus Amount ($)": round(bonus_amount, 2),
        "Total Revenue ($)": round(total_revenue, 2),
        "Revenue per Post ($)": round(revenue_per_post, 2),
        "Cost for Bonus ($)": cost_for_bonus,
        "Bonus Threshold Views": bonus_threshold_views,
        "Total Profit ($)": round(profit, 2)
    }

st.title("Influencer Deal Calculator")

st.sidebar.header("Input Parameters")
avg_views = st.sidebar.number_input("Average Views per Post", min_value=1, value=5000, step=1000)
likes = st.sidebar.number_input("Likes per Post", min_value=0, value=100, step=10)
comments = st.sidebar.number_input("Comments per Post", min_value=0, value=50, step=10)
comment_quality = st.sidebar.slider("Comment Quality (1-10)", min_value=1, max_value=10, value=5)
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
        st.markdown(f"<div style='background-color:#8B0000; padding:20px; border-radius:10px; text-align:center; color:white; margin-bottom:10px;'><h4>Total Deal Cost</h4><h1>${result['Total Cost ($)']}</h1></div>", unsafe_allow_html=True)
        st.markdown(f"<div style='background-color:#8B0000; padding:20px; border-radius:10px; text-align:center; color:white; margin-bottom:10px;'><h4>Minimum Views for Profit (MVC)</h4><h1>{result['Min Views for Profit']:,}</h1></div>", unsafe_allow_html=True)
        st.markdown(f"<div style='background-color:#8B0000; padding:20px; border-radius:10px; text-align:center; color:white;'><h4>Cost for Potential Bonus</h4><h1>${result['Cost for Bonus ($)']} at {result['Bonus Threshold Views']:,} more views</h1></div>", unsafe_allow_html=True)
    
    with col3:
        st.subheader("Revenue Metrics")
        st.markdown("---")
        st.markdown(f"<div style='background-color:#006400; padding:20px; border-radius:10px; text-align:center; color:white; margin-bottom:10px;'><h4>Total Revenue Off of Deal</h4><h1>${result['Total Revenue ($)']}</h1></div>", unsafe_allow_html=True)
        st.markdown(f"<div style='background-color:#006400; padding:20px; border-radius:10px; text-align:center; color:white; margin-bottom:10px;'><h4>Revenue Per Post</h4><h1>${result['Revenue per Post ($)']}</h1></div>", unsafe_allow_html=True)
        st.markdown(f"<div style='background-color:#006400; padding:20px; border-radius:10px; text-align:center; color:white; margin-bottom:10px;'><h4>Predicted RPM</h4><h1>${result['Predicted RPM']}</h1></div>", unsafe_allow_html=True)
        st.markdown(f"<div style='background-color:#006400; padding:20px; border-radius:10px; text-align:center; color:white;'><h4>Total Profit for Deal</h4><h1>${result['Total Profit ($)']}</h1></div>", unsafe_allow_html=True)