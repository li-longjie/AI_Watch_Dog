import asyncio
import websockets
import json
import logging

logging.basicConfig(level=logging.INFO)

async def connect_with_retry(uri, handler, max_retries=3, delay=2):
    retries = 0
    while retries < max_retries:
        try:
            async with websockets.connect(uri) as websocket:
                logging.info(f"Connected to {uri}")
                await handler(websocket)
        except websockets.exceptions.ConnectionClosed as e:
            logging.warning(f"Connection to {uri} closed: {e}")
            retries += 1
            if retries < max_retries:
                logging.info(f"Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
            else:
                logging.error(f"Max retries reached for {uri}")
        except Exception as e:
            logging.error(f"Error on {uri}: {e}")
            break

async def handle_alerts(websocket):
    while True:
        try:
            message = await websocket.recv()
            logging.info(f"Received alert: {message}")
        except websockets.exceptions.ConnectionClosed:
            raise

async def handle_video(websocket):
    while True:
        try:
            frame_data = await websocket.recv()
            logging.info(f"Received video frame: {len(frame_data)} bytes")
        except websockets.exceptions.ConnectionClosed:
            raise

async def main():
    tasks = [
        connect_with_retry("ws://localhost:16532/alerts", handle_alerts),
        connect_with_retry("ws://localhost:16532/video_feed", handle_video)
    ]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Test client stopped by user") 