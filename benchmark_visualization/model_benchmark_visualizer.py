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
    elif "Claude 3" in model_name:
        return 'Anthropic Claude 3'
    elif "Gemini 1.5" in model_name:
        return 'Google Gemini 1.5'
    return 'Other'


def create_benchmark_visualization(df: pd.DataFrame):
    fig = go.Figure()

    def categorize_model(model_name):
        """Categories models based on name"""
        if "GPT-4" in model_name:
            return 'GPT-4'
        elif "Claude 3" in model_name:
            return 'Claude 3'
        elif "Gemini 1.5" in model_name:
            return 'Gemini 1.5'
        return 'Other'

    # Categorize each model in the DataFrame
    df['Category'] = df['Model'].apply(categorize_model)

    # Set order for legend
    category_order = ['GPT-4', 'Claude 3'] # Add 'Gemini 1.5'
    df['Category'] = pd.Categorical(
        df['Category'], categories=category_order, ordered=True)
    df = df.sort_values('Category')

    # Set colors for different providers
    colors = {'GPT-4': '#00cbbf', 'Claude 3': '#d97857', 'Gemini 1.5': '#5da9ff', 'Other': 'gray'}

    for category, group_df in df.groupby('Category'):
        if category not in ['GPT-4', 'Claude 3', 'Gemini 1.5', 'Other']:
            continue

        x = group_df['Cost'].astype(float)
        y = group_df['Overall'].astype(float)

        # Fit a polynomial
        z = np.polyfit(x, y, 2)
        p = np.poly1d(z)

        x_poly = np.linspace(x.min(), x.max(), 100)
        y_poly = p(x_poly)

        # Plot the poly line
        fig.add_trace(go.Scatter(x=x_poly, y=y_poly, mode='lines',
                      name=f"{category_name(category)}", line=dict(color=colors[category], width=6, dash='dash'), opacity=0.5))

    # plot the actual datapoints
    # plot the actual datapoints
    for index, model in df.iterrows():
        try:
            fig.add_trace(go.Scatter(x=[model['Cost']], y=[model['Overall']],
                        mode='markers', # Removed 'text' from mode
                        name=model['Model'], marker=dict(size=15, color=colors[model['Category']])))
        except Exception as e:
            continue
    
        # Add model name
        fig.add_annotation(x=model['Cost'], y=model['Overall'],
                           text=model['Model'],
                           showarrow=False,
                           yshift=-40)

    fig.update_layout(title='Performance of Cloud-Based Models in gpt4vision',
                      xaxis_title='$/1M Input Tokens', yaxis_title='MMMU Score Average',
                      paper_bgcolor='#0d1117', plot_bgcolor='#161b22',
                      font=dict(color='white', family='Product Sans', size=25),
                      xaxis=dict(color='white', linecolor='grey',
                                 showgrid=False, zeroline=False),
                      yaxis=dict(color='white', linecolor='grey',
                                 showgrid=False, zeroline=False)
                      )
    # Save the plot as an image
    fig.write_image("benchmark_visualization/benchmark_visualization.jpg",
                    width=1920, height=1080, scale=1)


if __name__ == "__main__":
    df = read_benchmark_data()
    create_benchmark_visualization(df)
