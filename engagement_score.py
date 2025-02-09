import numpy as np
import pandas as pd

# Default Normalization Bounds (Customize as needed)
DEFAULT_V_MIN, DEFAULT_V_MAX = 50000, 500000  # View count range
DEFAULT_E_MIN, DEFAULT_E_MAX = 7, 15  # Engagement rate range (%)
C_MIN, C_MAX = 1, 10  # Comment quality range

# Define Weights (Adjust as needed)
WEIGHT_V = 0.2  # View count weight
WEIGHT_E = 0.5  # Engagement rate weight
WEIGHT_C = 0.3  # Comment quality weight

def log_normalize(value, min_val, max_val):
    """Applies log normalization to a given value."""
    return ((np.log(value) - np.log(min_val)) / (np.log(max_val) - np.log(min_val))) * 10

def normalize(value, min_val, max_val):
    """Normalizes a value linearly between 0 and 10."""
    return ((value - min_val) / (max_val - min_val)) * 10

def calculate_engagement_score(data, V_MIN, V_MAX, E_MIN, E_MAX):
    """
    Computes the Weighted Engagement Score (WES) for a batch of influencers.

    Parameters:
    data (list of dicts): Each dictionary should have:
        - 'name': Influencer name
        - 'avg_views': Average view count
        - 'engagement_rate': Engagement rate (likes + comments per view in %)
        - 'comment_quality': Comment quality score (1-10 scale)
    V_MIN, V_MAX: Min and Max values for View Count normalization
    E_MIN, E_MAX: Min and Max values for Engagement Rate normalization

    Returns:
    Pandas DataFrame with calculated scores.
    """
    df = pd.DataFrame(data)

    # Apply Log Normalization for Views
    df["S_V"] = df["avg_views"].apply(lambda x: log_normalize(x, V_MIN, V_MAX))

    # Normalize Engagement Rate
    df["S_E"] = df["engagement_rate"].apply(lambda x: normalize(x, E_MIN, E_MAX))

    # Normalize Comment Quality Score
    df["S_C"] = df["comment_quality"].apply(lambda x: normalize(x, C_MIN, C_MAX))

    # Calculate Weighted Engagement Score (WES)
    df["WES"] = (WEIGHT_V * df["S_V"]) + (WEIGHT_E * df["S_E"]) + (WEIGHT_C * df["S_C"])

    return df[["name", "S_V", "S_E", "S_C", "WES"]]

# User Input for a Single Influencer
name = input("Enter Influencer Name: ")
avg_views = float(input("Enter Average View Count: "))
engagement_rate = float(input("Enter Average Engagement Rate (%): "))
comment_quality = float(input("Enter Average Comment Quality Score (1-10): "))

# Allow users to override default normalization bounds
V_MIN = input(f"Enter Min View Count (leave black to use default {DEFAULT_V_MIN}): ") or DEFAULT_V_MIN
V_MAX = input(f"Enter Max View Count (leave black to use default {DEFAULT_V_MAX}): ") or DEFAULT_V_MAX
E_MIN = input(f"Enter Min Engagement Rate % (leave black to use default {DEFAULT_E_MIN}): ") or DEFAULT_E_MIN
E_MAX = input(f"Enter Max Engagement Rate % (leave black to use default {DEFAULT_E_MAX}): ") or DEFAULT_E_MAX

# Convert bounds to numeric values
V_MIN, V_MAX = float(V_MIN), float(V_MAX)
E_MIN, E_MAX = float(E_MIN), float(E_MAX)

# Calculate Engagement Score for the Input Influencer
data = [{"name": name, "avg_views": avg_views, "engagement_rate": engagement_rate, "comment_quality": comment_quality}]
result_df = calculate_engagement_score(data, V_MIN, V_MAX, E_MIN, E_MAX)

# Display the Results
import ace_tools as tools
tools.display_dataframe_to_user(name="Calculated Influencer Engagement Scores", dataframe=result_df)
