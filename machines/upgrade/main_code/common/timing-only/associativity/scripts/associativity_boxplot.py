import pandas as pd
import matplotlib.pyplot as plt

# Load the data
l1_data = pd.read_csv('/home/pgpatel/ECE592-HW1/timing-only/associativity/scripts/raw_data/l1_associativity.csv')
l2_data = pd.read_csv('/home/pgpatel/ECE592-HW1/timing-only/associativity/scripts/raw_data/l2_associativity.csv')
llc_data = pd.read_csv('/home/pgpatel/ECE592-HW1/timing-only/associativity/scripts/raw_data/llc_associativity.csv')

# Define cache boundaries for each level
cache_boundaries = {
    "L1": 8,  # inferred from data
    "L2": 8,  # inferred from data
    "LLC": 8  # inferred from data
}

# Function to create box plots
def create_boxplot(data, cache_boundary, title):
    # Select representative points
    below_boundary = data[data['K'] == cache_boundary - 1]
    at_boundary = data[data['K'] == cache_boundary]
    above_boundary = data[data['K'] == cache_boundary + 1]

    # Combine the data for box plot
    combined_data = pd.concat([below_boundary, at_boundary, above_boundary])
    labels = ['Below Boundary', 'At Boundary', 'Above Boundary']

    # Create box plot
    plt.figure(figsize=(8, 6))
    plt.boxplot([below_boundary['median_latency'], at_boundary['median_latency'], above_boundary['median_latency']],
                tick_labels=labels, patch_artist=True)  # Updated 'labels' to 'tick_labels'
    plt.title(title)
    plt.ylabel('Median Latency')
    plt.xlabel('Cache Boundary')
    plt.grid(axis='y')
    plt.savefig(f"{title.replace(' ', '_').lower()}.png")  # Save the plot as a PNG file
    plt.close()  # Close the plot to avoid overlapping

# Generate box plots for each cache level
create_boxplot(l1_data, cache_boundaries["L1"], "L1 Cache Associativity")
create_boxplot(l2_data, cache_boundaries["L2"], "L2 Cache Associativity")
create_boxplot(llc_data, cache_boundaries["LLC"], "LLC Cache Associativity")