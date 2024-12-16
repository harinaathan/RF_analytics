import logging
import asyncio
import websockets
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, dcc, html, no_update
from dash.dependencies import Input, Output, State
import threading
import webbrowser
from flask import Flask, request
import sys

# Initialize logging
logging.basicConfig(level=logging.INFO)

# Initialize an empty DataFrame to store the messages
df = pd.DataFrame(columns=["timeStamp", "Material", "TxPower", "RTT", "RSSI"])
powerLevels = [76, 70, 58, 50, 32, 26, 18, 6]

exit_event = threading.Event()

async def receive_messages(uri):
    async with websockets.connect(uri) as websocket:
        while not exit_event.is_set():
            try:
                message = await websocket.recv()
                logging.info(f"Received: {message}")
                if message.startswith("DATA:"):
                    global df
                    tStamp = int(str.strip((message.split("TIMESTAMP:")[-1]).split("ms\tMATERIAL:")[0]))
                    mat = str.strip((message.split("MATERIAL:")[-1]).split("Power:")[0])
                    txPow = int(str.strip((message.split("Power:")[-1]).split("dBm\tRTT:")[0]))
                    rtt = int(str.strip((message.split("RTT:")[-1]).split("ms\tRSSI:")[0]))
                    rssi = int(str.strip((message.split("RSSI:")[-1]).split("dBm")[0]))

                    if mat != "DEMO":
                        if df.loc[(df["Material"] == mat) & (df["TxPower"] == txPow)].shape[0] < 30:
                            tdf = pd.DataFrame(dict(timeStamp=tStamp,
                                                    Material=mat,
                                                    TxPower=txPow,
                                                    RTT=rtt,
                                                    RSSI=rssi), index=[0])
                            df = pd.concat([df, tdf], ignore_index=True)
                    elif mat == "DEMO":
                        tdf = pd.DataFrame(dict(timeStamp=tStamp,
                                                Material=mat,
                                                TxPower=txPow,
                                                RTT=rtt,
                                                RSSI=rssi), index=[0])
                        df = pd.concat([df, tdf], ignore_index=True)

            except websockets.exceptions.ConnectionClosed:
                logging.warning("Connection closed, retrying...")

async def main():
    uri = "ws://192.168.4.1:81"
    while not exit_event.is_set():
        try:
            await receive_messages(uri)
        except websockets.exceptions.ConnectionClosed:
            logging.warning("Connection closed, retrying...")
        except KeyboardInterrupt:
            break

def start_websocket():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())

server = Flask(__name__)
app = Dash(__name__, server=server)

app.layout = html.Div([
    dcc.Graph(id='live-graph'),
    dcc.Interval(
        id='interval-component',
        interval=1*1000,  # in milliseconds
        n_intervals=0
    ),
    html.Div(id='status-box', style={'color': 'white', 'margin': '10px 0', 'height': 'auto', 'maxHeight': '300px', 'overflowY': 'scroll', 'backgroundColor': 'rgb(35,35,35)', 'padding': '10px'}),
    html.Div([
        dcc.Input(id='material-input', type='text', placeholder='Enter material name...', style={'height': 'auto', 'backgroundColor': 'rgb(35,35,35)', 'color': 'white', 'padding': '10px', 'margin': '10px 0'}),
        html.Button('SEND', id='send-button', n_clicks=0, style={'marginLeft': '10px'}),
    ], style={'display': 'flex', 'alignItems': 'center'}),
    html.Button('EXIT', id='exit-button', n_clicks=0, style={'position': 'absolute', 'right': '10px', 'bottom': '10px'}),
    html.Div(id='dummy-output', style={'display': 'none'}),
    html.Div(id='dummy-input-output', style={'display': 'none'})
], style={'backgroundColor': 'black', 'height': '100vh'})

@app.callback(
    Output('dummy-input-output', 'children'),
    [Input('send-button', 'n_clicks')],
    [State('material-input', 'value')]
)
def send_material(n_clicks, material_name):
    if n_clicks > 0 and material_name:
        asyncio.run(send_message(f"RENAME:{material_name}"))
        return f"Renaming to: {material_name}"

    return ""

@app.callback(
    Output('material-input', 'value'),
    Input('send-button', 'n_clicks')
)
def reset_input(n_clicks):
    if n_clicks > 0:
        return ""
    return no_update

@app.callback(
    Output('dummy-output', 'children'),
    Input('exit-button', 'n_clicks')
)
def on_exit(n_clicks):
    if n_clicks > 0:
        exit_event.set()
        df.to_csv('received_messages.csv', index=False)
        logging.info("Messages have been recorded and saved to received_messages.csv")
        func = request.environ.get('werkzeug.server.shutdown')
        if func:
            func()
        sys.exit() # Explicitly exit the program
        return "Exiting..."

@app.callback(
    [Output('live-graph', 'figure'), Output('status-box', 'children')],
    Input('interval-component', 'n_intervals')
)
def update_plot(n):
    global df
    if df.empty:
        return go.Figure(), "No Data"

    lastTimeStamp = df["timeStamp"].iloc[-1]
    renderBeginTimeStamp = lastTimeStamp - 15000
    tdf = df.loc[df["timeStamp"] >= renderBeginTimeStamp]

    fig = go.Figure()

    power_color = '#636EFA'
    rssi_color = '#EF553B'
    rtt_color = '#00CC96'
    grid_color = "rgb(75,75,75)"

    material_name = tdf.iloc[-1]['Material']

    fig.update_layout(font_color="rgb(150,150,150)")

    fig.add_trace(go.Scatter(x=tdf["timeStamp"], y=tdf["TxPower"], name="TxPower", mode="lines", line=dict(color=power_color)))
    fig.add_trace(go.Scatter(x=tdf["timeStamp"], y=tdf["RSSI"], name="RSSI", mode="lines", line=dict(color=rssi_color), yaxis="y2"))
    fig.add_trace(go.Scatter(x=tdf["timeStamp"], y=tdf["RTT"], name="RTT", mode="lines", line=dict(color=rtt_color), yaxis="y3"))

    fig.update_layout(
        title=dict(text=f"Radio Transmission metrics - {material_name}", font_size=24),
        width=1500,
        height=600,
        legend=dict(x=0, y=1.07, orientation='h'),
        plot_bgcolor='rgb(35,35,35)',
        paper_bgcolor='rgb(10,10,10)',
        xaxis=dict(domain=[0.05,1], linecolor=grid_color, gridcolor=grid_color, mirror=True),
        yaxis=dict(title=dict(text="TxPower (dBm)", font=dict(color=power_color)), tickfont=dict(color=power_color), range=[0,100], linecolor=grid_color, gridcolor=grid_color),
        yaxis2=dict(title=dict(text="RSSI (dBm)", font=dict(color=rssi_color)), tickfont=dict(color=rssi_color), anchor="free", overlaying="y", side="left", position=0, range=[-100,-15], linecolor=grid_color, gridcolor=grid_color),
        yaxis3=dict(title=dict(text="RTT (ms)", font=dict(color=rtt_color)), tickfont=dict(color=rtt_color), anchor="x", overlaying="y", side="right", range=[0,5], linecolor=grid_color, gridcolor=grid_color)
    )    

    status_message = f"Measuring {material_name}\n"
    record_count = df.loc[df["Material"] == material_name].shape[0]
    powerLevels = df.TxPower.sort_values().unique()
    for power in powerLevels:
        count = df.loc[(df["Material"] == material_name) & (df["TxPower"] == power)].shape[0]
        status_message += f"{power}dBm: {count} records\n"

    status_message = status_message.rstrip("\n")

    if record_count >= 30 * len(powerLevels):
        status_message = f"SWAP: recording for {material_name} is complete"

    return fig, status_message

async def send_message(message):
    uri = "ws://192.168.4.1:81"
    async with websockets.connect(uri) as websocket:
        await websocket.send(message)

def open_browser():
    webbrowser.open_new("http://127.0.0.1:8050/")

if __name__ == '__main__':
    websocket_thread = threading.Thread(target=start_websocket)
    websocket_thread.start()
    threading.Timer(1, open_browser).start()
    app.run_server(debug=True, use_reloader=False)
