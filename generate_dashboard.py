"""
ULTRA-SIMPLE MVP: Generate static dashboard from existing CSV data
No API calls, no complexity, just reads CSV and makes pretty charts
"""
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import os

# Configuration
CSV_FILE = "trading_log.csv"
OUTPUT_FILE = "public/index.html"

def main():
    print("📊 Generating dashboard...")
    
    # Create output directory
    os.makedirs("public", exist_ok=True)
    
    # Load CSV
    df = pd.read_csv(CSV_FILE)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    print(f"✅ Loaded {len(df)} rows")
    
    # Get latest values for each stock
    latest_data = df.sort_values('timestamp').groupby('ticker').last()
    
    # Calculate portfolio value
    total_value = 0
    holdings = []
    
    for ticker in latest_data.index:
        row = latest_data.loc[ticker]
        if pd.notna(row['position_after']) and pd.notna(row['cash_after']):
            value = row['position_after'] * row['close']
            total_value += value
            if row['position_after'] > 0:
                holdings.append({
                    'ticker': ticker,
                    'shares': row['position_after'],
                    'price': row['close'],
                    'value': value
                })
    
    cash = latest_data['cash_after'].dropna().iloc[-1] if not latest_data['cash_after'].dropna().empty else 0
    total_value += cash
    
    print(f"💰 Total Value: ${total_value:,.2f}")
    
    # Create 2x2 dashboard
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=("Portfolio Allocation", "Portfolio Value", "Stock Prices", "Holdings"),
        specs=[
            [{"type": "pie"}, {"type": "scatter"}],
            [{"type": "scatter"}, {"type": "table"}]
        ]
    )
    
    # 1. Pie Chart - Portfolio Allocation
    pie_labels = [h['ticker'] for h in holdings] + ['Cash']
    pie_values = [h['value'] for h in holdings] + [cash]
    
    fig.add_trace(
        go.Pie(labels=pie_labels, values=pie_values, hole=0.4),
        row=1, col=1
    )
    
    # 2. Portfolio Value Over Time
    daily = df.groupby(df['timestamp'].dt.date).last()
    portfolio_values = []
    
    for date in daily.index:
        day_data = df[df['timestamp'].dt.date == date]
        cash_val = day_data['cash_after'].dropna().iloc[-1] if not day_data['cash_after'].dropna().empty else 0
        stock_val = 0
        
        for ticker in df['ticker'].unique():
            ticker_data = day_data[day_data['ticker'] == ticker]
            if not ticker_data.empty:
                pos = ticker_data['position_after'].dropna().iloc[-1] if not ticker_data['position_after'].dropna().empty else 0
                price = ticker_data['close'].dropna().iloc[-1] if not ticker_data['close'].dropna().empty else 0
                stock_val += pos * price
        
        portfolio_values.append(cash_val + stock_val)
    
    fig.add_trace(
        go.Scatter(x=list(daily.index), y=portfolio_values, mode='lines+markers', name='Value'),
        row=1, col=2
    )
    
    # 3. Stock Prices
    for ticker in df['ticker'].unique():
        ticker_data = df[df['ticker'] == ticker]
        fig.add_trace(
            go.Scatter(x=ticker_data['timestamp'], y=ticker_data['close'], 
                      mode='lines', name=ticker),
            row=2, col=1
        )
    
    # 4. Holdings Table
    if holdings:
        fig.add_trace(
            go.Table(
                header=dict(values=['Stock', 'Shares', 'Price', 'Value']),
                cells=dict(values=[
                    [h['ticker'] for h in holdings],
                    [f"{h['shares']:.0f}" for h in holdings],
                    [f"${h['price']:.2f}" for h in holdings],
                    [f"${h['value']:,.2f}" for h in holdings]
                ])
            ),
            row=2, col=2
        )
    
    # Layout
    fig.update_layout(
        title=f"Portfolio Dashboard - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        height=800,
        showlegend=True
    )
    
    # Save HTML
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Portfolio Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ margin: 0; padding: 20px; font-family: Arial; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Portfolio Dashboard</h1>
        <p>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Total Value: <strong>${total_value:,.2f}</strong> | Cash: ${cash:,.2f}</p>
        {fig.to_html(include_plotlyjs='cdn', full_html=False)}
    </div>
</body>
</html>"""
    
    with open(OUTPUT_FILE, 'w') as f:
        f.write(html)
    
    print(f"✅ Dashboard saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
