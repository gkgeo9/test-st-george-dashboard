# export_dashboard.py
"""
Export dashboard to static HTML for GitHub Pages deployment
"""
# import dash
# from dash import dcc, html
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

from stgeo_v1 import PortfolioManager


def export_static_dashboard():
    """Generate and export dashboard as static HTML"""
    
    print("=" * 60)
    print("EXPORTING DASHBOARD TO HTML")
    print("=" * 60)
    
    # Initialize portfolio manager
    print("\n[1/4] Initializing portfolio manager...")
    pm = PortfolioManager(csv_path="trading_log.csv")
    
    # Auto-backfill and update
    print("[2/4] Backfilling historical data...")
    pm.logger.autobackfill_on_start(default_lookback_days=365)
    
    # Recalculate portfolio state
    print("[3/4] Recalculating portfolio state...")
    recalculate_portfolio_from_csv(pm)
    
    # Take snapshot
    pm.snapshot_now(note="GitHub Actions export")
    
    # Generate HTML
    print("[4/4] Generating HTML dashboard...")
    html_content = generate_dashboard_html(pm)
    
    # Write to file
    output_file = "dashboard.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"\n✓ Dashboard exported to: {output_file}")
    print(f"✓ File size: {os.path.getsize(output_file) / 1024:.2f} KB")
    print(f"✓ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60 + "\n")


def recalculate_portfolio_from_csv(pm):
    """Reconstruct portfolio state from CSV"""
    try:
        df = pd.read_csv(pm.logger.csv_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        
        last_complete = df[df['position_after'].notna() & df['cash_after'].notna()]
        
        if not last_complete.empty:
            latest_timestamp = last_complete['timestamp'].max()
            latest_state = df[df['timestamp'] == latest_timestamp]
            
            new_portfolio = {}
            for _, row in latest_state.iterrows():
                if pd.notna(row['position_after']):
                    new_portfolio[row['ticker']] = int(row['position_after'])
            
            latest_cash = latest_state['cash_after'].dropna().iloc[-1]
            
            for stock in pm.stocks:
                pm.portfolio[stock] = new_portfolio.get(stock, 0)
            pm.cash = float(latest_cash)
            
            trades = []
            buy_actions = df[df['action'] == 'BUY'].copy()
            for _, row in buy_actions.iterrows():
                trades.append({
                    'timestamp': row['timestamp'].isoformat(),
                    'stock': row['ticker'],
                    'shares': int(row['quantity']),
                    'price': float(row['close']),
                    'total_cost': float(row['quantity'] * row['close'])
                })
            
            pm.trades = trades
            pm.save_data()
            
            print(f"  → Portfolio state loaded from {latest_timestamp}")
            print(f"  → Cash: ${pm.cash:,.2f}")
            print(f"  → Positions: {sum(pm.portfolio.values())} shares")
            
    except Exception as e:
        print(f"  ✗ Error recalculating portfolio: {e}")


def generate_dashboard_html(pm):
    """Generate static HTML dashboard"""
    
    # Load data
    df = pd.read_csv(pm.logger.csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Calculate stats
    stats = pm.calculate_portfolio_stats()
    metrics = calculate_performance_metrics(pm, df)
    
    # Generate charts
    pie_chart_json = create_pie_chart(pm, stats)
    timeline_chart_json = create_timeline_chart(pm, df)
    prices_chart_json = create_prices_chart(pm, df)
    
    # Build HTML
    pnl_color = '#27ae60' if stats['total_pnl'] >= 0 else '#e74c3c'
    last_update = datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
    
    html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Portfolio Dashboard</title>
    <script src="https://cdn.plot.ly/plotly-2.26.0.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }}
        h1 {{
            text-align: center;
            color: #2c3e50;
            margin-bottom: 10px;
            font-size: 2.5em;
        }}
        .last-update {{
            text-align: center;
            color: #7f8c8d;
            margin-bottom: 30px;
            font-size: 0.9em;
        }}
        .kpi-container {{
            display: flex;
            justify-content: space-around;
            flex-wrap: wrap;
            margin-bottom: 30px;
            gap: 15px;
        }}
        .kpi-card {{
            background: white;
            padding: 20px;
            border-radius: 12px;
            text-align: center;
            min-width: 180px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            border: 2px solid #ecf0f1;
        }}
        .kpi-icon {{
            font-size: 32px;
            margin-bottom: 10px;
        }}
        .kpi-value {{
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        .kpi-label {{
            font-size: 12px;
            color: #7f8c8d;
        }}
        .content-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }}
        .card {{
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .card h3 {{
            color: #34495e;
            margin-bottom: 15px;
            text-align: center;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th {{
            background: #3498db;
            color: white;
            padding: 12px;
            font-weight: bold;
        }}
        td {{
            padding: 10px;
            text-align: center;
            border-bottom: 1px solid #ecf0f1;
        }}
        .chart-container {{
            width: 100%;
            height: 400px;
            margin-top: 10px;
        }}
        .trade-item {{
            padding: 12px;
            margin: 4px 0;
            border-radius: 8px;
            border-left: 4px solid #3498db;
        }}
        .trade-time {{
            font-weight: bold;
            color: #3498db;
        }}
        .trade-stock {{
            color: #2c3e50;
            font-weight: bold;
            margin-left: 10px;
        }}
        .trade-details {{
            color: #7f8c8d;
            margin-top: 5px;
        }}
        @media (max-width: 768px) {{
            .content-grid {{
                grid-template-columns: 1fr;
            }}
            .kpi-container {{
                flex-direction: column;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Portfolio Dashboard</h1>
        <div class="last-update">Last updated: {last_update}</div>
        
        <!-- KPI Cards -->
        <div class="kpi-container">
            <div class="kpi-card">
                <div class="kpi-icon">💰</div>
                <div class="kpi-value" style="color: {pnl_color}">${stats['total_pnl']:,.2f}</div>
                <div class="kpi-label">Total P&L</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-icon">📈</div>
                <div class="kpi-value" style="color: {pnl_color}">{stats['pnl_percent']:+.2f}%</div>
                <div class="kpi-label">Return %</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-icon">🎯</div>
                <div class="kpi-value" style="color: #3498db">{metrics.get('win_rate', 0):.1f}%</div>
                <div class="kpi-label">Win Rate</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-icon">📊</div>
                <div class="kpi-value" style="color: #9b59b6">{metrics.get('volatility', 0):.1f}%</div>
                <div class="kpi-label">Volatility</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-icon">🔢</div>
                <div class="kpi-value" style="color: #1abc9c">{len(pm.trades)}</div>
                <div class="kpi-label">Total Trades</div>
            </div>
        </div>
        
        <!-- Main Content -->
        <div class="content-grid">
            <!-- Portfolio Overview -->
            <div class="card">
                <h3>💼 Portfolio Overview</h3>
                <div style="text-align: center; margin: 20px 0;">
                    <div style="font-size: 36px; font-weight: bold; color: #2980b9;">
                        ${stats['total_portfolio_value']:,.2f}
                    </div>
                    <div style="color: #7f8c8d; margin-top: 5px;">Total Portfolio Value</div>
                </div>
                <div style="display: flex; justify-content: space-around; margin-top: 20px;">
                    <div style="text-align: center;">
                        <div style="font-size: 18px; font-weight: bold;">${stats['cash']:,.2f}</div>
                        <div style="font-size: 14px; color: #7f8c8d;">💵 Cash</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 18px; font-weight: bold;">${stats['total_stock_value']:,.2f}</div>
                        <div style="font-size: 14px; color: #7f8c8d;">📊 Stock Value</div>
                    </div>
                </div>
                <div id="pieChart" class="chart-container"></div>
            </div>
            
            <!-- Holdings & Trades -->
            <div class="card">
                <h3>📈 Current Holdings</h3>
                {generate_holdings_table(stats)}
                
                <h3 style="margin-top: 30px;">🔔 Recent Activity</h3>
                {generate_recent_trades(pm)}
            </div>
        </div>
        
        <!-- Charts -->
        <div class="content-grid">
            <div class="card">
                <h3>📊 Portfolio Value Over Time</h3>
                <div id="timelineChart" class="chart-container"></div>
            </div>
            <div class="card">
                <h3>💹 Stock Prices</h3>
                <div id="pricesChart" class="chart-container"></div>
            </div>
        </div>
    </div>
    
    <script>
        // Render charts
        Plotly.newPlot('pieChart', {pie_chart_json}, {{responsive: true}});
        Plotly.newPlot('timelineChart', {timeline_chart_json}, {{responsive: true}});
        Plotly.newPlot('pricesChart', {prices_chart_json}, {{responsive: true}});
    </script>
</body>
</html>
"""
    
    return html_template


def generate_holdings_table(stats):
    """Generate holdings table HTML"""
    holdings_data = []
    for stock, data in stats['stock_values'].items():
        if data['shares'] > 0:
            weight = (data['value'] / stats['total_portfolio_value']) * 100
            holdings_data.append((stock, data['shares'], data['price'], data['value'], weight))
    
    if not holdings_data:
        return '<div style="text-align: center; padding: 30px; color: #95a5a6;">No current holdings</div>'
    
    table_html = '<table><thead><tr><th>Stock</th><th>Shares</th><th>Price</th><th>Value</th><th>Weight</th></tr></thead><tbody>'
    for stock, shares, price, value, weight in holdings_data:
        table_html += f'<tr><td style="font-weight: bold;">{stock}</td><td>{shares}</td><td>${price:.2f}</td><td>${value:,.2f}</td><td>{weight:.1f}%</td></tr>'
    table_html += '</tbody></table>'
    
    return table_html


def generate_recent_trades(pm):
    """Generate recent trades HTML"""
    if not pm.trades:
        return '<div style="text-align: center; padding: 30px; color: #95a5a6;">No recent trades</div>'
    
    trades_html = ''
    for trade in reversed(pm.trades[-5:]):
        trade_time = datetime.fromisoformat(trade['timestamp']).strftime('%m/%d %H:%M')
        trades_html += f'''
        <div class="trade-item">
            <div>
                <span class="trade-time">{trade_time}</span>
                <span class="trade-stock">• {trade['stock']}</span>
            </div>
            <div class="trade-details">
                {trade['shares']} shares @ ${trade['price']:.2f} = ${trade['total_cost']:,.2f}
            </div>
        </div>
        '''
    
    return trades_html


def create_pie_chart(pm, stats):
    """Create pie chart JSON"""
    labels, values = [], []
    colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#34495e']
    
    for stock, data in stats['stock_values'].items():
        if data['value'] > 0:
            labels.append(stock)
            values.append(data['value'])
    
    if stats['cash'] > 0:
        labels.append('Cash')
        values.append(stats['cash'])
    
    data = [{
        'type': 'pie',
        'labels': labels,
        'values': values,
        'marker': {'colors': colors[:len(labels)]},
        'textinfo': 'label+percent',
        'hole': 0.4
    }]
    
    layout = {
        'showlegend': True,
        'height': 350,
        'margin': {'t': 20, 'b': 20, 'l': 20, 'r': 20}
    }
    
    return str({'data': data, 'layout': layout}).replace("'", '"')


def create_timeline_chart(pm, df):
    """Create timeline chart JSON"""
    if df.empty:
        return '{}'
    
    portfolio_data = []
    for timestamp in df['timestamp'].dt.floor('h').unique():
        timestamp_data = df[df['timestamp'].dt.floor('h') == timestamp]
        if not timestamp_data['cash_after'].isna().all():
            latest_cash = timestamp_data['cash_after'].dropna().iloc[-1]
            stock_value = 0
            for stock in pm.stocks:
                stock_rows = timestamp_data[timestamp_data['ticker'] == stock]
                if not stock_rows.empty and not stock_rows['position_after'].isna().all():
                    position = stock_rows['position_after'].dropna().iloc[-1]
                    price = stock_rows['close'].dropna().iloc[-1]
                    if not pd.isna(position) and not pd.isna(price):
                        stock_value += position * price
            portfolio_data.append({
                'x': timestamp.strftime('%Y-%m-%d %H:%M'),
                'y': stock_value + latest_cash
            })
    
    data = [{
        'type': 'scatter',
        'mode': 'lines+markers',
        'x': [p['x'] for p in portfolio_data],
        'y': [p['y'] for p in portfolio_data],
        'line': {'color': '#3498db', 'width': 3},
        'marker': {'size': 8}
    }]
    
    layout = {
        'xaxis': {'title': 'Time'},
        'yaxis': {'title': 'Portfolio Value ($)'},
        'height': 350,
        'margin': {'t': 20, 'b': 50, 'l': 60, 'r': 20}
    }
    
    return str({'data': data, 'layout': layout}).replace("'", '"')


def create_prices_chart(pm, df):
    """Create prices chart JSON"""
    if df.empty:
        return '{}'
    
    colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6']
    data = []
    
    for i, stock in enumerate(pm.stocks):
        stock_data = df[df['ticker'] == stock].copy()
        if not stock_data.empty:
            data.append({
                'type': 'scatter',
                'mode': 'lines',
                'name': stock,
                'x': stock_data['timestamp'].dt.strftime('%Y-%m-%d %H:%M').tolist(),
                'y': stock_data['close'].tolist(),
                'line': {'color': colors[i % len(colors)], 'width': 2.5}
            })
    
    layout = {
        'xaxis': {'title': 'Time'},
        'yaxis': {'title': 'Stock Price ($)'},
        'height': 350,
        'margin': {'t': 20, 'b': 50, 'l': 60, 'r': 20},
        'showlegend': True
    }
    
    return str({'data': data, 'layout': layout}).replace("'", '"')


def calculate_performance_metrics(pm, df):
    """Calculate performance metrics"""
    if df.empty:
        return {}
    
    portfolio_values = []
    for timestamp in df['timestamp'].dt.floor('h').unique():
        timestamp_data = df[df['timestamp'].dt.floor('h') == timestamp]
        if not timestamp_data['cash_after'].isna().all():
            latest_cash = timestamp_data['cash_after'].dropna().iloc[-1]
            stock_value = 0
            for stock in pm.stocks:
                stock_rows = timestamp_data[timestamp_data['ticker'] == stock]
                if not stock_rows.empty and not stock_rows['position_after'].isna().all():
                    position = stock_rows['position_after'].dropna().iloc[-1]
                    price = stock_rows['close'].dropna().iloc[-1]
                    if not pd.isna(position) and not pd.isna(price):
                        stock_value += position * price
            portfolio_values.append(stock_value + latest_cash)
    
    if len(portfolio_values) < 2:
        return {}
    
    returns = np.diff(portfolio_values) / portfolio_values[:-1]
    
    # Calculate win rate
    trades = df[df['action'] == 'BUY'].copy()
    winning_trades = 0
    if not trades.empty:
        for _, trade in trades.iterrows():
            future_prices = df[(df['ticker'] == trade['ticker']) &
                               (df['timestamp'] > trade['timestamp'])]['close']
            if not future_prices.empty and future_prices.iloc[-1] > trade['close']:
                winning_trades += 1
        win_rate = (winning_trades / len(trades)) * 100
    else:
        win_rate = 0
    
    return {
        'volatility': np.std(returns) * np.sqrt(252) * 100,
        'win_rate': win_rate
    }


if __name__ == "__main__":
    export_static_dashboard()
