import pandas as pd

# Define test influencer categories (Small, Medium, Big)
influencers = [
    {
        "category": "Small",
        "avg_views": 5000,   # Average views per post
        "likes": 80,     # Likes per post
        "comments": 30,     # Comments per post
        "comment_quality": 5,  # Comment quality score (1-10)
        "num_posts": 4,    # Number of posts in the deal
    },
    {
        "category": "Medium",
        "avg_views": 50000,  # Average views per post
        "likes": 3000,    # Likes per post
        "comments": 100,     # Comments per post
        "comment_quality": 7,  # Comment quality score (1-10)
        "num_posts": 4,      # Number of posts in the deal
    },
    {
        "category": "Big",
        "avg_views": 900000,  # Average views per post
        "likes": 45000,    # Likes per post
        "comments": 500,     # Comments per post
        "comment_quality": 9,  # Comment quality score (1-10)
        "num_posts": 4,       # Number of posts in the deal
    },
]

# Constants
BASE_CPM = 3  # Cost per 1000 views (fixed input)

def calculate_rpm(avg_views, engagement_rate, comment_quality):
    # Base subscription model values
    default_monthly_price = 5.70
    base_conversion_rate = 0.02  # 2% base conversion rate

    # Adjust conversion rate based on influencer engagement stats
    conversion_boost = max((engagement_rate * 0.1) + (comment_quality * 0.005), 0.02)
    adjusted_conversion_rate = base_conversion_rate * (1 + conversion_boost)

    # Calculate average revenue per user (monthly only)
    avg_revenue_per_user = (default_monthly_price) * adjusted_conversion_rate

    return avg_revenue_per_user * 1000 * (avg_views / 1000000)  # Scale RPM based on views



def calculate_influencer_deal(influencer):
    # Extract input values
    avg_views = influencer["avg_views"]
    likes = influencer["likes"]
    comments = influencer["comments"]
    comment_quality = influencer["comment_quality"]
    num_posts = influencer["num_posts"]

    # Step 1: Calculate Engagement Rate
    engagement_rate = (likes + comments) / avg_views

    # Step 2: Compute Engagement Quality Factor
    engagement_quality_factor = (engagement_rate * 0.5) + (comment_quality / 10)

    # Step 3: Determine Predicted RPM
    predicted_rpm = calculate_rpm(avg_views, engagement_rate, comment_quality) * (1 + engagement_quality_factor)

    # Step 4: Compute Total Expected Views
    total_expected_views = avg_views * num_posts

    # Step 5: Calculate Total Cost of the Deal (CPM remains fixed)
    total_cost = (total_expected_views / 1000) * BASE_CPM

    # Step 6: Compute Minimum Views for Profitability (MVC)
    min_views_for_profit = (total_cost / predicted_rpm) * 1000

    # Step 7: Calculate Bonus for Exceeding MVC with tiered bonus system
    extra_views = max(total_expected_views - min_views_for_profit, 0)

    if extra_views > 0:
        if extra_views <= min_views_for_profit * 0.25:  # Small bonus if extra views < 25% of MVC
            bonus_amount = (extra_views / 100000) * 100  
        elif extra_views <= min_views_for_profit:  # Medium bonus if extra views 25-100% of MVC
            bonus_amount = (extra_views / 100000) * 250  
        else:  # Cap maximum bonus for excessive views
            bonus_amount = (min_views_for_profit / 100000) * 400  
    else:
        bonus_amount = 0  

    # Step 8: Calculate Total Revenue
    total_revenue = (total_expected_views / 1000) * predicted_rpm

    # Step 9: Calculate Revenue Per Post
    revenue_per_post = total_revenue / num_posts

    return {
        "category": influencer["category"],
        "avg_views": avg_views,
        "engagement_rate": round(engagement_rate * 100, 2),
        "comment_quality": comment_quality,
        "predicted_rpm": round(predicted_rpm, 2),
        "total_expected_views": total_expected_views,
        "total_cost": round(total_cost, 2),
        "min_views_for_profit": round(min_views_for_profit),
        "bonus_amount": round(bonus_amount, 2),
        "total_revenue": round(total_revenue, 2),
        "revenue_per_post": round(revenue_per_post, 2),
    }

# Process each influencer
final_results_with_revenue_per_post = [
    calculate_influencer_deal(influencer) for influencer in influencers
]

# Display results
df_final_results_with_revenue_per_post = pd.DataFrame(final_results_with_revenue_per_post)
print(df_final_results_with_revenue_per_post)
