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
df = pd.DataFrame(columns=["timeStamp", "Material", "TxPower", "RTT", "RSSI"])

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
                tStamp = int(str.strip((message.split("TIMESTAMP:")[-1]).split("ms\tMATERIAL:")[0]))
                mat = str.strip((message.split("MATERIAL:")[-1]).split("Power:")[0])
                txPow = int(str.strip((message.split("Power:")[-1]).split("dBm\tRTT:")[0]))
                rtt = int(str.strip((message.split("RTT:")[-1]).split("ms\tRSSI:")[0]))
                rssi = int(str.strip((message.split("RSSI:")[-1]).split("dBm")[0]))
                
                if df.loc[(df["Material"] == mat) & (df["TxPower"] == txPow)].shape[0] < 30:
                    tdf = pd.DataFrame(dict(timeStamp=tStamp,
                                            Material=mat,
                                            TxPower=txPow,
                                            RTT=rtt,
                                            RSSI=rssi), index=[0])
                    df = pd.concat([df, tdf], ignore_index=True)

                if df.loc[(df["Material"] == mat)].shape[0] >= 30 * len(powerLevels):
                    reply = f"SWAP: recording for {mat} complete"
                    await websocket.send(reply)
            
            # Check for exit condition
            if message.lower() == "exit":
                df.to_csv('received_messages.csv', index=False)
                print("Messages have been recorded and saved to received_messages.csv")            
                print("Exiting...")
                return -1

# Define the URI of the WebSocket server
uri = "ws://192.168.4.1:81"
# uri = "ws://192.168.0.108:8080"

async def main():
    while True:
        try:
            # Run the WebSocket connection and receiving function
            rtState = await receive_messages(uri)
            if rtState == -1:
                df.to_csv('received_messages.csv', index=False)
                print("Messages have been recorded and saved to received_messages.csv")            
                print("Exiting...")
        except websockets.ConnectionClosed:
            print("Connection closed, retrying...")
        except KeyboardInterrupt:
            # Save the DataFrame to a CSV file
            df.to_csv('received_messages.csv', index=False)
            print("Messages have been recorded and saved to received_messages.csv")            
            print("Exiting...")
            return

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

    lastTimeStamp = df["timeStamp"].iloc[-1]
    renderBeginTimeStamp = lastTimeStamp - 30000
    tdf = df.loc[df["timeStamp"] >= renderBeginTimeStamp]

    fig = go.Figure()

    power_color = '#636EFA'
    rssi_color = '#EF553B'
    rtt_color = '#00CC96'
    grid_color = "rgb(75,75,75)"

    fig.update_layout(font_color="rgb(150,150,150)")

    fig.add_trace(go.Scatter(x=tdf["timeStamp"], y=tdf["TxPower"], name="TxPower", mode="lines", line=dict(color=power_color)))
    fig.add_trace(go.Scatter(x=tdf["timeStamp"], y=tdf["RSSI"], name="RSSI", mode="lines", line=dict(color=rssi_color), yaxis="y2"))
    fig.add_trace(go.Scatter(x=tdf["timeStamp"], y=tdf["RTT"], name="RTT", mode="lines", line=dict(color=rtt_color), yaxis="y3"))

    fig.update_layout(
                    title=dict(text=f"Radio Transmission metrics {tdf.iloc[-1]["MATERIAL"]}", font_size=24),
                    width=1750,
                    height=800,
                    legend=dict(x=0, y=1.07, orientation='h'),
                    plot_bgcolor='rgb(35,35,35)',
                    paper_bgcolor ='rgb(10,10,10)',
                    xaxis=dict(domain=[0.05,1], linecolor=grid_color, gridcolor=grid_color, mirror=True),
                    yaxis=dict(title=dict(text="TxPower (dBm)", font=dict(color=power_color)), tickfont=dict(color=power_color), range=[0,100], linecolor=grid_color, gridcolor=grid_color),
                    yaxis2=dict(title=dict(text="RSSI (dBm)", font=dict(color=rssi_color)), tickfont=dict(color=rssi_color), anchor="free", overlaying="y", side="left", position=0, range=[-100,0], linecolor=grid_color, gridcolor=grid_color),
                    yaxis3=dict(title=dict(text="RTT (ms)", font=dict(color=rtt_color)), tickfont=dict(color=rtt_color), anchor="x", overlaying="y", side="right", range=[0,5], linecolor=grid_color, gridcolor=grid_color)
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
