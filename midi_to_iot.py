from rtmidi.midiutil import open_midiinput, open_midioutput
import sys
import os
import time
import requests
import asyncio

dir_path = os.path.dirname(os.path.realpath(__file__))
lamp_on_url_path = os.path.join(dir_path, "lamp_on_url.txt")
lamp_off_url_path = os.path.join(dir_path, "lamp_off_url.txt")

CC_CODE = 176
DEBOUNCE_TIME_SECONDS = 0.25
TRIGGER_ON_URL = next(open(lamp_on_url_path))
TRIGGER_OFF_URL = next(open(lamp_off_url_path))

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

def switch_lamp(on):
    url = TRIGGER_ON_URL if on else TRIGGER_OFF_URL
    response = requests.post(url=url)
    if response.ok:
        print("Set recording lamp to", "on" if on else "off")
    else:
        print("Unable to change lamp. HTTP status code:", response.status_code)

def on_play_changed(midi_val):
    global record_enabled, playing
    playing = midi_val > 0
    if not record_enabled:
        # get rid of this 'if' if you want to trigger on any play/pause change
        return
    schedule_debounced(switch_lamp, playing)

def on_record_enabled(midi_val):
    global record_enabled, playing
    record_enabled = midi_val > 0
    if not playing:
        return
    schedule_debounced(switch_lamp, record_enabled)

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

try:
    midiin, port_name = open_midiinput(None, port_name="MIDI to IOT", use_virtual=True, interactive=False)
except (EOFError, KeyboardInterrupt):
    sys.exit()

print("MIDI to IOT monitor running. Press Control-C to exit.")

try:
    asyncio.ensure_future(main_loop())
    event_loop.run_forever()
except KeyboardInterrupt:
    print('')
finally:
    print("Exit.")
    event_loop.stop()
    midiin.close_port()
    del midiin
