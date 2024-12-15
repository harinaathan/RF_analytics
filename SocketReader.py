import asyncio
import websockets
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, dcc, html
from dash.dependencies import Input, Output
import threading
import webbrowser
from flask import Flask

# Initialize an empty DataFrame to store the messages
df = pd.DataFrame(columns=["Material", "TxPower", "RTT", "RSSI"])

powerLevels = [76, 70, 58, 50, 32, 26, 18, 6]

async def receive_messages(uri):
    async with websockets.connect(uri) as websocket:
        while True:
            # Receive message from the server
            message = await websocket.recv()
            
            # Print the received message
            print(f"Received: {message}")
            if message.startswith("DATA:"):
                # Append the message to the DataFrame
                global df
                mat = str.strip((message.split("MATERIAL:")[-1]).split("Power:")[0])
                txPow = str.strip((message.split("Power:")[-1]).split("dBm\tRTT:")[0])
                rtt = str.strip((message.split("RTT:")[-1]).split("ms\tRSSI:")[0])
                rssi = str.strip((message.split("RSSI:")[-1]).split("dBm")[0])
                
                if df.loc[(df["Material"] == mat) & (df["TxPower"] == txPow)].shape[0] < 30:
                    tdf = pd.DataFrame(dict(Material=mat, TxPower=txPow,
                                            RTT=rtt, RSSI=rssi), index=[0])
                    df = pd.concat([df, tdf], ignore_index=True)

                if df.loc[(df["Material"] == mat)].shape[0] >= 30 * len(powerLevels):
                    reply = f"SWAP: recording for {mat} complete"
                    await websocket.send(reply)
            
            # Check for exit condition
            if message.lower() == "exit":
                break

# Define the URI of the WebSocket server
uri = "ws://192.168.4.1:81"
# uri = "ws://192.168.0.108:8080"

async def main():
    while True:
        try:
            # Run the WebSocket connection and receiving function
            await receive_messages(uri)
        except websockets.ConnectionClosed:
            print("Connection closed, retrying...")
        except KeyboardInterrupt:
            # Save the DataFrame to a CSV file
            df.to_csv('received_messages.csv', index=False)
            print("Messages have been recorded and saved to received_messages.csv")            
            print("Exiting...")
            break

# Initialize Dash app with Flask server
server = Flask(__name__)
app = Dash(__name__, server=server)

app.layout = html.Div([
    dcc.Graph(id='live-graph'),
    dcc.Interval(
        id='interval-component',
        interval=1*1000,  # in milliseconds
        n_intervals=0
    )
])

@app.callback(Output('live-graph', 'figure'),
              Input('interval-component', 'n_intervals'))
def update_plot(n):
    global df
    if df.empty:
        return go.Figure()

    tdf = df.iloc[-100:]

    fig = go.Figure()

    fig.add_trace(go.Scatter(x=tdf.index, y=tdf['TxPower'], mode='lines', name='TxPower', line=dict(color='green')))
    fig.add_trace(go.Scatter(x=tdf.index, y=tdf['RSSI'], mode='lines', name='RSSI', line=dict(color='blue'), yaxis='y2'))
    fig.add_trace(go.Scatter(x=tdf.index, y=tdf['RTT'], mode='lines', name='RTT', line=dict(color='red'), yaxis='y3'))

    # Update layout for clarity
    material_title = tdf['Material'].iloc[-1] if not tdf.empty else "<unknown>"
    fig.update_layout(
        title=f'Live Data Visualization - {material_title}',
        xaxis=dict(title='Index'),
        yaxis=dict(title='TxPower (dBm)', titlefont=dict(color='green'), tickfont=dict(color='green'), anchor="free", overlaying='y', side='left', position=0, range=[0, 100]),
        yaxis2=dict(title='RSSI (dBm)', titlefont=dict(color='blue'), tickfont=dict(color='blue'), anchor="free", overlaying='y', side='right', position=0, range=[-100, 0]),
        yaxis3=dict(title='RTT (ms)', titlefont=dict(color='red'), tickfont=dict(color='red'), anchor="free", overlaying='y', side='right', position=1, range=[0, 10]),
        legend=dict(x=0, y=1.1, orientation='h')
    )

    return fig

def open_browser():
    webbrowser.open_new("http://127.0.0.1:8050/")

# Start the WebSocket connection in a separate thread
loop = asyncio.get_event_loop()
threading.Thread(target=loop.run_until_complete, args=(main(),)).start()

if __name__ == '__main__':
    threading.Timer(1, open_browser).start()
    app.run_server(debug=True)
