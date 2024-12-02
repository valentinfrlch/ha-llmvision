import numpy as np
import plotly.graph_objects as go
import pandas as pd
import csv


def read_benchmark_data(file_path="./benchmark_visualization/benchmark_data.csv"):
    with open(file_path, 'r') as file:
        reader = csv.reader(file)
        benchmark_data = list(reader)
        df = pd.DataFrame(benchmark_data[1:], columns=benchmark_data[0])
        # filter out rows with empty Cost value
        df = df[df['Cost'] != '']
        df['Cost'] = df['Cost'].astype(float)
    return df


def category_name(model_name):
    if "GPT-4" in model_name:
        return 'OpenAI GPT-4'
    elif "Claude 3.5" in model_name:
        return 'Anthropic Claude 3.5'
    elif "Claude 3" in model_name:
        return 'Anthropic Claude 3'
    elif "Gemini 1.5" in model_name:
        return 'Google Gemini 1.5'
    elif "Llama 3.2" in model_name:
        return 'Meta Llama 3.2'
    return 'Other'


def create_benchmark_visualization(df: pd.DataFrame):
    fig = go.Figure()

    def categorize_model(model_name):
        """Categories models based on name"""
        if "GPT-4" in model_name:
            return 'GPT-4'
        elif "Claude 3.5" in model_name:
            return 'Claude 3.5'
        elif "Claude 3" in model_name:
            return 'Claude 3'
        elif "Gemini 1.5" in model_name:
            return 'Gemini 1.5'
        return 'Other'

    # Categorize each model in the DataFrame
    df['Category'] = df['Model'].apply(categorize_model)

    # Set order for legend
    category_order = ['GPT-4', 'Claude 3',
                      'Claude 3.5', 'Gemini 1.5']
    df['Category'] = pd.Categorical(
        df['Category'], categories=category_order, ordered=True)
    df = df.sort_values('Category')

    # Set colors for different providers
    colors = {'GPT-4': '#00cbbf', 'Claude 3': '#d97857',
              'Gemini 1.5': '#5da9ff', 'Claude 3.5': '#d4a27f', 'Other': 'gray'}

    for category, group_df in df.groupby('Category'):
        if category not in ['GPT-4', 'Claude 3', 'Claude 3.5', 'Gemini 1.5', 'Other']:
            continue

        x = group_df['Cost'].astype(float)
        y = group_df['Overall'].astype(float)

        try:
            # Fit a polynomial
            z = np.polyfit(x, y, 2)
            p = np.poly1d(z)

            x_poly = np.linspace(x.min(), x.max(), 100)
            y_poly = p(x_poly)

            # Plot the poly line
            fig.add_trace(go.Scatter(x=x_poly, y=y_poly, mode='lines',
                          name=f"{category_name(category)}", line=dict(color=colors[category], width=6, dash='dash'), opacity=0.5))
        except np.linalg.LinAlgError:
            print(f"LinAlgError: SVD did not converge for category {category}")
            continue

    # plot the actual datapoints
    for index, model in df.iterrows():
        try:
            fig.add_trace(go.Scatter(x=[model['Cost']], y=[model['Overall']],
                                     mode='markers',  # Removed 'text' from mode
                                     name=model['Model'], marker=dict(size=20, color=colors[model['Category']])))
        except Exception as e:
            continue

        # Add model name
        fig.add_annotation(x=model['Cost'], y=model['Overall'],
                           text=model['Model'],
                           showarrow=False,
                           yshift=-35)

    fig.update_layout(title={'text': 'Performance vs Cost of Cloud-Based Models in LLM Vision',
                             'font': {'size': 50}},
                      xaxis_title='$/1M Input Tokens', yaxis_title='MMMU Score Average',
                      paper_bgcolor='#0d1117', plot_bgcolor='#161b22',
                      font=dict(color='white', family='Product Sans', size=25),
                      xaxis=dict(color='white', linecolor='grey',
                                 showgrid=False, zeroline=False),
                      yaxis=dict(color='white', linecolor='grey',
                                 showgrid=False, zeroline=False))
    # Save the plot as an image
    fig.write_image("benchmark_visualization/benchmark_visualization.jpg",
                    width=1920, height=1080, scale=1)

    # Create a second visualization for open source models
    fig_open_source = go.Figure()

    def categorize_open_source_model(model_name):
        """Categories open source models based on name"""
        if "Llama" in model_name:
            return 'Llama'
        elif "LLaVA" in model_name:
            return 'LLaVA'
        elif "MiniCPM" in model_name:
            return 'MiniCPM'
        return 'Other'

    # Categorize each open source model in the DataFrame
    df['OpenSourceCategory'] = df['Model'].apply(categorize_open_source_model)

    # Set order for legend
    open_source_category_order = ['Llama', 'LLaVA', 'MiniCPM']
    df['OpenSourceCategory'] = pd.Categorical(
        df['OpenSourceCategory'], categories=open_source_category_order, ordered=True)
    df = df.sort_values('OpenSourceCategory')

    # Set colors for different open source models
    open_source_colors = {'Llama': '#0081fb',
                          'LLaVA': '#ff7f0e', 'MiniCPM': '#2ca02c', 'Other': 'gray'}

    # Convert 'Size' column to float
    def convert_size_to_float(size_str):
        """Convert model size string to float"""
        size_str = size_str.strip()  # Remove leading/trailing spaces
        if size_str == "-":
            return 0
        if size_str.endswith('B'):
            return float(size_str[:-1]) * 1e9
        elif size_str.endswith('M'):
            return float(size_str[:-1]) * 1e6
        return float(size_str)

    df['Size'] = df['Size'].apply(convert_size_to_float)

    for category, group_df in df.groupby('OpenSourceCategory'):
        if category not in ['Llama', 'LLaVA', 'MiniCPM']:
            continue

        x = group_df['Size'].astype(float)
        y = group_df['Overall'].astype(float)

        if len(x) == 0 or len(y) == 0:
            continue

        try:
            # Fit a polynomial
            z = np.polyfit(x, y, 2)
            p = np.poly1d(z)

            x_poly = np.linspace(x.min(), x.max(), 100)
            y_poly = p(x_poly)

            # Plot the poly line
            fig_open_source.add_trace(go.Scatter(x=x_poly, y=y_poly, mode='lines',
                          name=f"{category_name(category)}", line=dict(color=open_source_colors[category], width=6, dash='dash'), opacity=0.5))
        except np.linalg.LinAlgError:
            print(f"LinAlgError: SVD did not converge for category {category}")
            continue

    # plot the actual datapoints
    for index, model in df.iterrows():
        try:
            fig_open_source.add_trace(go.Scatter(x=[model['Size']], y=[model['Overall']],
                                     mode='markers',  # Removed 'text' from mode
                                     name=model['Model'], marker=dict(size=20, color=open_source_colors[model['OpenSourceCategory']])))

        except Exception as e:
            continue

        # Add model name
        fig_open_source.add_annotation(x=model['Size'], y=model['Overall'],
                           text=model['Model'],
                           showarrow=False,
                           yshift=-35)

    fig_open_source.update_layout(title={'text': 'Performance vs Model Size of Open Source Models in LLM Vision',
                             'font': {'size': 50}},
                      xaxis_title='Model Size (Parameters)', yaxis_title='MMMU Score Average',
                      paper_bgcolor='#0d1117', plot_bgcolor='#161b22',
                      font=dict(color='white', family='Product Sans', size=25),
                      xaxis=dict(color='white', linecolor='grey',
                                 showgrid=False, zeroline=False),
                      yaxis=dict(color='white', linecolor='grey',
                                 showgrid=False, zeroline=False))
    # Save the plot as an image
    fig_open_source.write_image("benchmark_visualization/open_source_benchmark_visualization.jpg",
                    width=1920, height=1080, scale=1)


if __name__ == "__main__":
    df = read_benchmark_data()
    create_benchmark_visualization(df)