import asyncio
import websockets

async def receive_messages(websocket):
    while True:
        # Receive message from the server
        message = await websocket.recv()

        # Print only select messages
        if message.startswith("SWAP:"):
            print(message)

async def send_messages(websocket):
    loop = asyncio.get_event_loop()
    while True:
        # Wait for user input
        user_input = await loop.run_in_executor(None, input, "Enter your message: ")
        
        # Send the user input to the server
        await websocket.send(user_input)
        print(f"Sent: {user_input}")
        
        # Check for exit condition
        if user_input.lower() == "exit":
            break

async def connect_and_interact(uri):
    async with websockets.connect(uri) as websocket:
        # Create tasks for receiving and sending messages
        receive_task = asyncio.create_task(receive_messages(websocket))
        send_task = asyncio.create_task(send_messages(websocket))
        
        # Wait for both tasks to complete
        await asyncio.gather(receive_task, send_task)

# Define the URI of the WebSocket server
uri = "ws://192.168.4.1:81"

# Run the WebSocket connection and interaction function
asyncio.run(connect_and_interact(uri))

print("Message sending script has ended.")