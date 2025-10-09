"""
Generate a static HTML dashboard from your portfolio data
This runs via GitHub Actions and outputs to public/index.html
"""
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime
import os
from stgeo_v1 import PortfolioManager


def generate_static_dashboard(portfolio_manager, output_file="public/index.html"):
    """Generate a beautiful static HTML dashboard"""

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    pm = portfolio_manager

    # Load data
    try:
        df = pd.read_csv(pm.logger.csv_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    except Exception as e:
        print(f"Error loading CSV: {e}")
        df = pd.DataFrame()

    # Get current stats
    stats = pm.calculate_portfolio_stats()

    # Calculate performance metrics
    metrics = calculate_performance_metrics(df, pm)

    # Create comprehensive dashboard with subplots
    fig = make_subplots(
        rows=4, cols=2,
        subplot_titles=(
            "📊 Portfolio Allocation",
            "💰 Portfolio Value Over Time",
            "📈 Stock Prices",
            "📉 Returns Distribution",
            "🎯 Stock Performance",
            "📋 Key Metrics",
            "🔔 Recent Trades",
            "💹 Daily Returns"
        ),
        specs=[
            [{"type": "pie"}, {"type": "scatter"}],
            [{"type": "scatter"}, {"type": "histogram"}],
            [{"type": "bar"}, {"type": "table"}],
            [{"type": "table"}, {"type": "scatter"}]
        ],
        row_heights=[0.25, 0.25, 0.25, 0.25],
        vertical_spacing=0.08,
        horizontal_spacing=0.12
    )

    # 1. Portfolio Allocation (Pie Chart)
    pie_data = []
    pie_labels = []
    pie_colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c']

    for stock, data in stats['stock_values'].items():
        if data['value'] > 0:
            pie_data.append(data['value'])
            pie_labels.append(stock)

    if stats['cash'] > 0:
        pie_data.append(stats['cash'])
        pie_labels.append('Cash')

    fig.add_trace(
        go.Pie(
            labels=pie_labels,
            values=pie_data,
            marker_colors=pie_colors[:len(pie_data)],
            hole=0.4,
            textinfo='label+percent',
            hovertemplate='<b>%{label}</b><br>$%{value:,.2f}<br>%{percent}<extra></extra>'
        ),
        row=1, col=1
    )

    # 2. Portfolio Value Timeline
    if not df.empty and 'cash_after' in df.columns:
        portfolio_data = []
        for timestamp in df['timestamp'].dt.floor('D').unique():
            timestamp_data = df[df['timestamp'].dt.floor('D') == timestamp]
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
                    'timestamp': timestamp,
                    'value': stock_value + latest_cash
                })

        if portfolio_data:
            portfolio_df = pd.DataFrame(portfolio_data)

            # Color points based on performance
            colors = ['#27ae60' if v >= pm.initial_value else '#e74c3c'
                      for v in portfolio_df['value']]

            fig.add_trace(
                go.Scatter(
                    x=portfolio_df['timestamp'],
                    y=portfolio_df['value'],
                    mode='lines+markers',
                    name='Portfolio Value',
                    line=dict(color='#3498db', width=3),
                    marker=dict(size=6, color=colors),
                    fill='tozeroy',
                    fillcolor='rgba(52, 152, 219, 0.1)',
                    hovertemplate='<b>%{x|%Y-%m-%d}</b><br>$%{y:,.2f}<extra></extra>'
                ),
                row=1, col=2
            )

            # Add initial value reference line
            fig.add_hline(
                y=pm.initial_value,
                line_dash="dash",
                line_color="#e74c3c",
                line_width=2,
                row=1, col=2
            )

    # 3. Stock Prices
    if not df.empty:
        colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6']
        for i, stock in enumerate(pm.stocks):
            stock_data = df[df['ticker'] == stock].copy()
            if not stock_data.empty:
                fig.add_trace(
                    go.Scatter(
                        x=stock_data['timestamp'],
                        y=stock_data['close'],
                        mode='lines',
                        name=stock,
                        line=dict(color=colors[i % len(colors)], width=2),
                        hovertemplate=f'<b>{stock}</b><br>%{{x|%Y-%m-%d}}<br>${{y:.2f}}<extra></extra>'
                    ),
                    row=2, col=1
                )

    # 4. Returns Distribution
    if not df.empty and len(portfolio_data) > 1:
        values = [p['value'] for p in portfolio_data]
        returns = np.diff(values) / values[:-1] * 100

        fig.add_trace(
            go.Histogram(
                x=returns,
                nbinsx=30,
                marker=dict(
                    color=returns,
                    colorscale=[[0, '#e74c3c'], [0.5, '#f39c12'], [1, '#27ae60']],
                    line=dict(color='white', width=1)
                ),
                showlegend=False,
                hovertemplate='Return: %{x:.2f}%<br>Count: %{y}<extra></extra>'
            ),
            row=2, col=2
        )

        # Add mean line
        if len(returns) > 0:
            mean_return = np.mean(returns)
            fig.add_vline(
                x=mean_return,
                line_dash="dash",
                line_color="#3498db",
                line_width=2,
                row=2, col=2
            )

    # 5. Stock Performance (Bar Chart)
    if not df.empty:
        stock_performance = {}
        for stock in pm.stocks:
            stock_data = df[df['ticker'] == stock].copy()
            if not stock_data.empty and len(stock_data) > 1:
                first_price = stock_data['close'].iloc[0]
                last_price = stock_data['close'].iloc[-1]
                ret = ((last_price - first_price) / first_price) * 100
                stock_performance[stock] = ret

        if stock_performance:
            stocks = list(stock_performance.keys())
            returns_bar = list(stock_performance.values())
            colors_bar = ['#27ae60' if r >= 0 else '#e74c3c' for r in returns_bar]

            fig.add_trace(
                go.Bar(
                    x=stocks,
                    y=returns_bar,
                    marker=dict(color=colors_bar, line=dict(color='white', width=2)),
                    text=[f"{r:+.1f}%" for r in returns_bar],
                    textposition='outside',
                    showlegend=False,
                    hovertemplate='<b>%{x}</b><br>Return: %{y:.2f}%<extra></extra>'
                ),
                row=3, col=1
            )

            fig.add_hline(y=0, line_dash="solid", line_color="#95a5a6", line_width=2, row=3, col=1)

    # 6. Key Metrics Table
    pnl_color = '#27ae60' if stats['total_pnl'] >= 0 else '#e74c3c'

    metrics_data = [
        ["💰 Total Value", f"${stats['total_portfolio_value']:,.2f}"],
        ["💵 Cash", f"${stats['cash']:,.2f}"],
        ["📊 Stock Value", f"${stats['total_stock_value']:,.2f}"],
        ["📈 Total P&L", f"${stats['total_pnl']:,.2f}"],
        ["📊 P&L %", f"{stats['pnl_percent']:+.2f}%"],
        ["🔢 Total Trades", str(len(pm.trades))],
        ["🎯 Win Rate", f"{metrics.get('win_rate', 0):.1f}%"],
        ["📉 Volatility", f"{metrics.get('volatility', 0):.1f}%"],
        ["📉 Max Drawdown", f"{metrics.get('max_drawdown', 0):.1f}%"],
        ["🏆 Best Stock", metrics.get('best_stock', 'N/A')],
        ["📉 Worst Stock", metrics.get('worst_stock', 'N/A')]
    ]

    fig.add_trace(
        go.Table(
            header=dict(
                values=["<b>Metric</b>", "<b>Value</b>"],
                fill_color='#3498db',
                font=dict(color='white', size=13),
                align='left',
                height=30
            ),
            cells=dict(
                values=[[m[0] for m in metrics_data], [m[1] for m in metrics_data]],
                fill_color='white',
                align='left',
                font=dict(size=12),
                height=25
            )
        ),
        row=3, col=2
    )

    # 7. Recent Trades Table
    recent_trades = pm.trades[-10:] if pm.trades else []
    if recent_trades:
        trades_display = []
        for trade in reversed(recent_trades):
            trade_time = datetime.fromisoformat(trade['timestamp']).strftime('%m/%d %H:%M')
            trades_display.append([
                trade_time,
                trade['stock'],
                str(trade['shares']),
                f"${trade['price']:.2f}",
                f"${trade['total_cost']:,.2f}"
            ])

        fig.add_trace(
            go.Table(
                header=dict(
                    values=["<b>Time</b>", "<b>Stock</b>", "<b>Shares</b>", "<b>Price</b>", "<b>Total</b>"],
                    fill_color='#3498db',
                    font=dict(color='white', size=12),
                    align='left',
                    height=30
                ),
                cells=dict(
                    values=[
                        [t[0] for t in trades_display],
                        [t[1] for t in trades_display],
                        [t[2] for t in trades_display],
                        [t[3] for t in trades_display],
                        [t[4] for t in trades_display]
                    ],
                    fill_color='white',
                    align='left',
                    font=dict(size=11),
                    height=25
                )
            ),
            row=4, col=1
        )

    # 8. Daily Returns (Line Chart)
    if not df.empty and len(portfolio_data) > 1:
        values = [p['value'] for p in portfolio_data]
        dates = [p['timestamp'] for p in portfolio_data[1:]]
        returns_daily = (np.diff(values) / values[:-1] * 100).tolist()

        colors_returns = ['#27ae60' if r >= 0 else '#e74c3c' for r in returns_daily]

        fig.add_trace(
            go.Scatter(
                x=dates,
                y=returns_daily,
                mode='lines+markers',
                name='Daily Return',
                line=dict(color='#3498db', width=2),
                marker=dict(size=6, color=colors_returns),
                showlegend=False,
                hovertemplate='<b>%{x|%Y-%m-%d}</b><br>%{y:.2f}%<extra></extra>'
            ),
            row=4, col=2
        )

        fig.add_hline(y=0, line_dash="solid", line_color="#95a5a6", line_width=1, row=4, col=2)

    # Update overall layout
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    fig.update_layout(
        title={
            'text': f"📊 Portfolio Dashboard - Last Updated: {current_time}",
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 24, 'color': '#2c3e50'}
        },
        height=2000,
        showlegend=True,
        paper_bgcolor='#f8f9fa',
        plot_bgcolor='white',
        font=dict(family='Arial, sans-serif', size=11)
    )

    # Update axes
    fig.update_xaxes(showgrid=True, gridcolor='#ecf0f1')
    fig.update_yaxes(showgrid=True, gridcolor='#ecf0f1')

    # Save to HTML with custom styling
    html_string = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Portfolio Dashboard</title>
        <style>
            body {{
                margin: 0;
                padding: 20px;
                font-family: Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
            .header {{
                text-align: center;
                margin-bottom: 30px;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 15px;
                color: white;
            }}
            .header h1 {{
                margin: 0;
                font-size: 36px;
            }}
            .header p {{
                margin: 10px 0 0 0;
                opacity: 0.9;
            }}
            .info-box {{
                background: #f8f9fa;
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 20px;
                border-left: 4px solid #3498db;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📊 Portfolio Dashboard</h1>
                <p>Automated updates via GitHub Actions</p>
                <p>Last updated: {current_time}</p>
            </div>
            <div class="info-box">
                <strong>ℹ️ Note:</strong> This dashboard automatically updates every hour. 
                Data is pulled from your trading log and processed via GitHub Actions.
            </div>
            {fig.to_html(include_plotlyjs='cdn', full_html=False, config={{'displayModeBar': True, 'displaylogo': False}})}
        </div>
    </body>
    </html>
    """

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_string)

    print(f"✅ Static dashboard generated successfully!")
    print(f"📁 Output: {output_file}")
    print(f"🕐 Last updated: {current_time}")


def calculate_performance_metrics(df, pm):
    """Calculate advanced performance metrics"""
    if df.empty:
        return {}

    # Get portfolio values over time
    portfolio_values = []
    for timestamp in df['timestamp'].dt.floor('D').unique():
        timestamp_data = df[df['timestamp'].dt.floor('D') == timestamp]
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

    # Calculate metrics
    returns = np.diff(portfolio_values) / portfolio_values[:-1]

    # Win rate
    trades = df[df['action'] == 'BUY'].copy()
    winning_trades = 0
    if not trades.empty:
        for _, trade in trades.iterrows():
            future_prices = df[(df['ticker'] == trade['ticker']) &
                               (df['timestamp'] > trade['timestamp'])]['close']
            if not future_prices.empty and future_prices.iloc[-1] > trade['close']:
                winning_trades += 1
        win_rate = (winning_trades / len(trades)) * 100 if len(trades) > 0 else 0
    else:
        win_rate = 0

    # Max drawdown
    peak = portfolio_values[0]
    max_dd = 0
    for value in portfolio_values:
        if value > peak:
            peak = value
        dd = ((peak - value) / peak) * 100
        if dd > max_dd:
            max_dd = dd

    # Best/worst stocks
    best_stock = "N/A"
    worst_stock = "N/A"
    best_return = -float('inf')
    worst_return = float('inf')

    for stock in pm.stocks:
        stock_data = df[df['ticker'] == stock]
        if not stock_data.empty and len(stock_data) > 1:
            first_price = stock_data['close'].iloc[0]
            last_price = stock_data['close'].iloc[-1]
            ret = ((last_price - first_price) / first_price) * 100

            if ret > best_return:
                best_return = ret
                best_stock = f"{stock} (+{ret:.1f}%)"

            if ret < worst_return:
                worst_return = ret
                worst_stock = f"{stock} ({ret:+.1f}%)"

    return {
        'win_rate': win_rate,
        'volatility': np.std(returns) * np.sqrt(252) * 100 if len(returns) > 0 else 0,
        'max_drawdown': max_dd,
        'best_stock': best_stock,
        'worst_stock': worst_stock
    }


if __name__ == "__main__":
    print("🚀 Generating static portfolio dashboard...")

    # Initialize portfolio manager
    portfolio = PortfolioManager(csv_path="trading_log.csv")

    # Generate dashboard
    generate_static_dashboard(portfolio, output_file="public/index.html")

    print("✅ Done! Dashboard ready for deployment.")