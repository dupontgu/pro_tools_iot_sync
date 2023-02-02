from rtmidi.midiutil import open_midiinput, open_midioutput
import sys
import os
import time
import requests
import asyncio
import websockets
import json
import http.server
import socketserver
import threading
import webbrowser

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=".", **kwargs)

PORT = 8090
WS_PORT = 8089
CC_CODE = 176
DEBOUNCE_TIME_SECONDS = 0.10
WS_CONNECTIONS = set()

record_enabled = False
playing = False
scheduled_event = None
event_loop = asyncio.get_event_loop()

# Need debouncing because PT may not send play/record events in order
def schedule_debounced(task, arg):
    global scheduled_event
    if scheduled_event:
        scheduled_event.cancel()
    scheduled_event = event_loop.call_later(DEBOUNCE_TIME_SECONDS, task, arg)

def start_http_server():
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print("serving at port", PORT)
        httpd.serve_forever()

def send_message_to_front_end(msg):
    websockets.broadcast(WS_CONNECTIONS, json.dumps(msg))

def on_play_changed(midi_val):
    global record_enabled, playing
    playing = midi_val > 0
    if not record_enabled:
        # get rid of this 'if' if you want to trigger on any play/pause change
        return
    schedule_debounced(send_message_to_front_end, { 'recording' : playing })

def on_record_enabled(midi_val):
    global record_enabled, playing
    record_enabled = midi_val > 0
    if not playing:
        return
    schedule_debounced(send_message_to_front_end, { 'recording' : record_enabled })

def process_message(message):
    if message[0] != CC_CODE:
        # only care about MIDI CC messages for now
        return
    if message[1] not in CC_ACTION_MAP:
        # only use messages for which we have a defined action
        return
    CC_ACTION_MAP[message[1]](message[2])

CC_ACTION_MAP = {
    118: on_record_enabled,
    117: on_play_changed
}

async def main_loop():
    while True:
        msg = midiin.get_message()
        if msg:
            message, deltatime = msg
            process_message(message)
        await asyncio.sleep(0.005)

async def ws_handler(websocket):
    WS_CONNECTIONS.add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        WS_CONNECTIONS.remove(websocket)

async def websocket_loop():
    async with websockets.serve(ws_handler, "localhost", WS_PORT):
        await asyncio.Future()  

try:
    midiin, port_name = open_midiinput(None, port_name="MIDI to IOT", use_virtual=True, interactive=False)
except (EOFError, KeyboardInterrupt):
    sys.exit()

print("MIDI to IOT monitor running. Press Control-C to exit.")

try:
    asyncio.ensure_future(main_loop())
    asyncio.ensure_future(websocket_loop())
    threading.Thread(target=start_http_server).start()
    webbrowser.open(f'http://localhost:{PORT}/recording.html')
    event_loop.run_forever()
except KeyboardInterrupt:
    print('')
finally:
    print("Exit.")
    event_loop.stop()
    midiin.close_port()
    del midiin
