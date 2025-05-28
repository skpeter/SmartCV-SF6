print("Initializing...")
import configparser
from PIL import Image, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES=True
import cv2
import numpy as np
import threading
import time
import easyocr
import gc
import json
import websockets
import asyncio
import ggst
import re
from tag_matching import findBestMatch
import mss
import pygetwindow as gw
import traceback
import dialog
from datetime import datetime
config = configparser.ConfigParser()
config.read('config.ini')
previous_states = [None] # list of previous states to be used for state change detection

reader = easyocr.Reader(['en'])

refresh_rate = config.getfloat('settings', 'refresh_rate')
capture_mode = config.get('settings', 'capture_mode')
executable_title = config.get('settings', 'executable_title')
feed_path = config.get('settings', 'feed_path')

base_height = 1080
base_width = 1920


payload = {
    "state": None,
    "players": [
        {
            "name": None,
            "character": None,
            "rounds": 2,
        },
        {
            "name": None,
            "character": None,
            "rounds": 2,
        }
    ]
}

# Check if the pixel color is within the deviation range
def is_within_deviation(color1, color2, deviation):
    return all(abs(c1 - c2) / 255.0 <= deviation for c1, c2 in zip(color1, color2))

def capture_screen():
    global base_height, base_width, feed_path, capture_mode, executable_title
    if capture_mode == 'obs':
        while True:
            try:
                img = Image.open(feed_path)
                break
            except (OSError, Image.UnidentifiedImageError) as e:
                if "truncated" in str(e) or "cannot identify image file" in str(e) or "could not create decoder object" in str(e):
                    # print("Image is truncated or cannot be identified. Retrying...")
                    time.sleep(0.1)
                    continue
                else:
                    raise e
    else:
        # Find the window by its title
        windows = gw.getWindowsWithTitle(executable_title)
        if windows:
            window = windows[0]
        else:
            print(f"Executable {executable_title} not found. Ensure it is running and visible.")
            return False, None, None

        # Get the window's bounding box
        # Get the window's dimensions
        width = window.right - window.left
        height = window.bottom - window.top
        
        # Calculate target height for 16:9 aspect ratio
        target_height = int(width * (9/16))
        
        # If current height is larger than target, adjust top to crop from bottom
        if height > target_height:
            adjusted_top = window.bottom - target_height
        else:
            adjusted_top = window.top
            
        bbox = (window.left, adjusted_top, window.right, window.bottom)

        with mss.mss() as sct:
            # Capture the screen using the bounding box
            screenshot = sct.grab(bbox)
            img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
    
    # also return the scale of the image based off base resolution (1080p)
    image_width, image_height = img.size
    scale_x = image_width / base_width
    scale_y = image_height / base_height
    return img, scale_x, scale_y

def detect_character_select_screen():
    global config, payload, previous_states, feed_path, capture_mode, executable_title
    
    img, scale_x, scale_y = capture_screen()
    if not img: return
    pixel = img.getpixel((int(115 * scale_x), int(20 * scale_y))) #white tournament mode icon
    pixel2 = img.getpixel((int(1805 * scale_x), int(20 * scale_y))) #back button area
    
    # Define the target color and deviation
    target_color = (128, 30, 29)  #red player 1 side
    target_color2 = (18, 77, 107)  #blue player 2 side

    deviation = 0.1
    
    if is_within_deviation(pixel, target_color, deviation) and is_within_deviation(pixel2, target_color2, deviation):
        payload['state'] = "character_select"
        print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "- Character select screen detected")
        if payload['state'] != previous_states[-1]:
            previous_states.append(payload['state'])
            #clean up some more player information
            for player in payload['players']:
                player['rounds'] = 2
                player['character'] = None
                player['name'] = None
    return

def read_text(img, region: tuple[int, int, int, int]):
    global payload, reader
    # print("Attempting to read text...")
    # Define the area to read
    x, y, w, h = region
    cropped_img = img.crop((x, y, x + w, y + h))

    # Convert image from PIL to cv2
    cropped_img = cv2.cvtColor(np.array(cropped_img), cv2.COLOR_RGB2GRAY)
        
    # Use OCR to read the text from the image
    result = reader.readtext(cropped_img, paragraph=False)

    # Extract the text
    if result:
        result = ' '.join([res[1] for res in result])
    else: result = None

    # Release memory
    del cropped_img
    gc.collect()

    return result

def detect_characters(repeat=False):
    global config, payload, refresh_rate, feed_path, capture_mode, executable_title
    img, scale_x, scale_y = capture_screen()
    if not img: return
    if repeat: time.sleep(0.1)

    def read_characters_and_names():
        # signal to the main loop that character and tag detection is in progress
        if payload['state'] != "loading": return
        # Initialize the reader
        region1 = (int(215 * scale_x), int(410 * scale_y), int(565 * scale_x), int(100 * scale_y))
        region2 = (int(215 * scale_x), int(600 * scale_y), int(565 * scale_x), int(100 * scale_y))
        cropped_img1 = img.crop((region1[0], region1[1], region1[0] + region1[2], region1[1] + region1[3]))
        cropped_img2 = img.crop((region2[0], region2[1], region2[0] + region2[2], region2[1] + region2[3]))
        cropped_img1.save(f"debug_character1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        cropped_img2.save(f"debug_character2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        character1 = read_text(img, region1)
        character2 = read_text(img, region2)
        if character1 is not None and character2 is not None:
            character1 = character1.replace("KIGO", "NAGO")
            character2 = character2.replace("KIGO", "NAGO")
            c1, c2 = findBestMatch(character1, ggst.characters), findBestMatch(character2, ggst.characters)
        else: return detect_characters(repeat=True)
        payload['players'][0]['character'], payload['players'][1]['character'] = c1, c2
        print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "- Player 1 character:", c1)
        print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "- Player 2 character:", c2)

    threading.Thread(target=read_characters_and_names).start()
    return

def detect_versus_screen():
    global config, payload, previous_states, feed_path, capture_mode, executable_title
    
    img, scale_x, scale_y = capture_screen()
    if not img: return
    pixel1 = img.getpixel((int(1050 * scale_x), int(185 * scale_y))) #black letterbox
    pixel2 = img.getpixel((int(1050 * scale_x), int(195 * scale_y))) #blue sky
    
    # Define the target color and deviation
    target_color = (0, 0, 0)  #black letterbox
    target_color2 = (64, 132, 207)  #blue sky
    deviation = 0.1
    
    if is_within_deviation(pixel1, target_color, deviation) and is_within_deviation(pixel2, target_color2, deviation):
        payload['state'] = "loading"
        if payload['state'] != previous_states[-1]:
            previous_states.append(payload['state'])
            print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "- Match is now loading...")
            detect_characters()

    return

def detect_player_tags():
    def action():
        global config, payload, previous_states, feed_path, capture_mode, executable_title
        if payload['players'][0]['name'] != None and payload['players'][1]['name'] != None: return
        img, scale_x, scale_y = capture_screen()
        if not img: return

        tag1 = read_text(img, (int(575 * scale_x), int(35 * scale_y), int(770 * scale_x), int(115 * scale_y)))
        tag2 = read_text(img, (int(575 * scale_x), int(880 * scale_y), int(770 * scale_x), int(115 * scale_y)))
        if tag1 is not None and tag2 is not None:
            payload['players'][0]['name'], payload['players'][1]['name'] = tag1.strip(), tag2.strip()
            print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "- Player 1 tag:", payload['players'][0]['name'])
            print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "- Player 2 tag:", payload['players'][1]['name'])
        else:
            for player in payload['players']:
                player['name'] = False
        return
    time.sleep(0.5)
    threading.Thread(target=action).start()
    return

def detect_rounds(red_only=False):
    global config, payload, previous_states, feed_path, capture_mode, executable_title
    if payload['players'][0]['rounds'] < 2 and payload['players'][1]['rounds'] < 2 and not red_only: return
        
    img, scale_x, scale_y = capture_screen()
    if not img: return
    pixel1 = img.getpixel((int(800 * scale_x), int(95 * scale_y))) #p1 heart
    pixel2 = img.getpixel((int(1120 * scale_x), int(95 * scale_y))) #p2 heart
    
    # Define the target color and deviation
    target_color = (213, 33, 48)  #red heart (still has round)
    target_color2 = (150, 156, 163)  #gray heart (lost round)
    deviation = 0.15
    
    if payload['state'] == "in_game":
        if is_within_deviation(pixel1, target_color, deviation):
            if payload['players'][0]['rounds'] == 1: print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "- Correcting previous round loss report")
            payload['players'][0]['rounds'] = 2
        if is_within_deviation(pixel2, target_color, deviation):
            if payload['players'][0]['rounds'] == 1: print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "- Correcting previous round loss report")
            payload['players'][0]['rounds'] = 2
    if is_within_deviation(pixel1, target_color, deviation) and is_within_deviation(pixel2, target_color, deviation):
        payload['state'] = "in_game"
        if payload['state'] != previous_states[-1]:
            previous_states.append(payload['state'])
            print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "- Match has started!")
            return
    elif not red_only:
        if is_within_deviation(pixel1, target_color2, deviation):
            if payload['players'][0]['rounds'] != 1: print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "- Player 1 lost a round")
            payload['players'][0]['rounds'] = 1
            return
        if is_within_deviation(pixel2, target_color2, deviation):
            if payload['players'][1]['rounds'] != 1: print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "- Player 2 lost a round")
            payload['players'][1]['rounds'] = 1
    return

def determine_winner(img, scale_x, scale_y, perfect=False):
    global payload, previous_states, feed_path, capture_mode, executable_title
    # Define the area to read
    x, y, w, h = (int(1600 * scale_x), int(135 * scale_y), int(290 * scale_x), int(570 * scale_y))
    if perfect: x, y, w, h = (int(90 * scale_x), int(180 * scale_y), int(355 * scale_x), int(160 * scale_y))

    # crop image to the area of interest
    img = img.crop((x, y, x + w, y + h))
    # the text showing the winner is in the corner of the screen rotated by 70 degrees
    img = img.rotate(70 if not perfect else 344, expand=True)
    # Convert image from PIL to cv2
    img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
    # The text is too transparent, so we need to increase the contrast of the image
    img = cv2.convertScaleAbs(img, alpha=2, beta=0)
    # Use OCR to read the text from the image
    result = reader.readtext(img, paragraph=False, allowlist='12', text_threshold=0.3, low_text=0.2)

    # strip all non-numeric characters from the result
    if result:
        result = [res[1] for res in result]
        result = [re.sub(r'[^0-9]', '', res) for res in result]
        result = [int(res) for res in result if res.isdigit() and int(res) <= 2]
        if len(result) == 0: return False
        if result[0] == 1: payload['players'][1]['rounds'] -= 1
        elif result[0] == 2: payload['players'][0]['rounds'] -= 1
        if payload['players'][0]['rounds'] == 0 or payload['players'][1]['rounds'] == 0:
            return True
    return False


def detect_game_end():
    """
    DEPRECATED
    """
    global config, payload, previous_states, feed_path, capture_mode, executable_title
    if payload['players'][0]['rounds'] > 1 and payload['players'][1]['rounds'] > 1: return

    img, scale_x, scale_y = capture_screen()
    if not img: return
    pixel1 = img.getpixel((int(666 * scale_x), int(740 * scale_y))) #"SLASH" white text
    pixel2 = img.getpixel((int(1140 * scale_x), int(655 * scale_y))) #"SLASH" white text
    pixelperfect1 = img.getpixel((int(640 * scale_x), int(765 * scale_y))) #red overlay around text
    pixelperfect2 = img.getpixel((int(55 * scale_x), int(295 * scale_y))) #"PERFECT" white text
            
    target_color = (255, 255, 255) #white text
    target_color2 = (255, 0, 0) #red overlay around text
    deviation = 0.1
    
    perfect = None
    if is_within_deviation(pixel1, target_color, deviation) and is_within_deviation(pixel2, target_color, deviation):
        perfect = False
    if is_within_deviation(pixelperfect1, target_color2, deviation) and is_within_deviation(pixelperfect2, target_color, deviation):
        perfect = True
    if perfect is not None:
        if determine_winner(img, scale_x, scale_y, perfect):
            payload['state'] = "game_end"
            if payload['state'] != previous_states[-1]:
                previous_states.append(payload['state'])
                print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "- Game has ended!")
                if payload['players'][0]['rounds'] == 0:
                    print(f"Player 1 ({payload['players'][1]['character']}) wins!")
                elif payload['players'][1]['rounds'] == 0:
                    print(f"Player 2 ({payload['players'][0]['character']}) wins!")
    return

def detect_result_screen():
    global config, payload, previous_states, feed_path, capture_mode, executable_title
    if payload['players'][0]['rounds'] == 0 or payload['players'][1]['rounds'] == 0: return
    img, scale_x, scale_y = capture_screen()
    if not img: return
    pixel = img.getpixel((int(263 * scale_x), int(390 * scale_y))) #the win/lose text for player 1
    pixel2 = img.getpixel((int(263 * scale_x), int(447 * scale_y))) #the win/lose text for player 1
    # pixel2 = img.getpixel((int(1440 * scale_x), int(390 * scale_y))) #the win/lose text for player 2
    
    # Define the target color and deviation
    target_color = (222, 61, 2)  #red "WIN" text
    target_color2 = (14, 111, 156)  #blue "LOSE" text
    deviation = 0.1

    if ((is_within_deviation(pixel, target_color, deviation) or is_within_deviation(pixel, target_color2, deviation))
        and (is_within_deviation(pixel2, target_color, deviation) or is_within_deviation(pixel2, target_color2, deviation))):
        payload['state'] = "game_end"
        if payload['state'] != previous_states[-1]:
            previous_states.append(payload['state'])
        print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "- Result screen detected")
        if is_within_deviation(pixel, target_color, deviation) and is_within_deviation(pixel2, target_color, deviation):
            payload['players'][1]['rounds'] = 0
            print(f"{payload['players'][0]['character']} wins!")
        elif is_within_deviation(pixel, target_color2, deviation) and is_within_deviation(pixel2, target_color2, deviation):
            payload['players'][0]['rounds'] = 0
            print(f"{payload['players'][1]['character']} wins!")

def run_detection():
    global payload, previous_states, refresh_rate
    while True:
        try:
            if payload['state'] == None:
                detect_character_select_screen()
                detect_versus_screen()
            elif payload['state'] == "character_select":
                detect_versus_screen()
                gc.collect()
            elif payload['state'] == "loading":
                detect_rounds(red_only=True)
                detect_player_tags()
            elif payload['state'] == "in_game":
                detect_character_select_screen()
                detect_rounds()
                # detect_game_end()
                detect_result_screen()
            elif payload['state'] == "game_end":
                detect_character_select_screen()
                detect_rounds(red_only=True)
        except Exception as e:
            print(f"Error: {str(e)}")
            print("Stack trace:")
            print(traceback.format_exc())
        time.sleep(refresh_rate)

async def send_data(websocket):
    global payload, config
    try:
        while True:
            data = json.dumps(payload)
            size = len(data.encode('utf-8'))
            if size > 1024 * 1024:  # 1MB
                print(f"Warning: Large payload size ({size} bytes)")
            refresh_rate = config.getfloat('settings', 'refresh_rate')
            await websocket.send(json.dumps(payload))
            await asyncio.sleep(refresh_rate)
    except websockets.exceptions.ConnectionClosedOK:
        pass
    except websockets.exceptions.ConnectionClosedError as e:
        if "no close frame received or sent" not in str(e):
            print(f"Connection error from client: {e}")

processing_data = False
async def receive_data(websocket):
    try:
        async for message in websocket:
            if "confirm-entrants:" in message and processing_data == False: # and config.get('settings', 'capture_mode') == 'game':
                if str(payload['players'][0]['name']) in str(message) and str(payload['players'][1]['name']) in str(message): return
                def doTask():
                    global processing_data
                    processing_data = True
                    players = str(message).replace("confirm-entrants:", "").strip().split(":")
                    chosen_player = dialog.choose_player_side(players[0], players[1])
                    if chosen_player == players[0]:
                        payload['players'][0]['name'] = players[0]
                        payload['players'][1]['name'] = players[1]
                    elif chosen_player == players[1]:
                        payload['players'][0]['name'] = players[1]
                        payload['players'][1]['name'] = players[0]
                    processing_data = False
                threading.Thread(target=doTask, daemon=True).start()
    except websockets.exceptions.ConnectionClosedOK:
        pass
    except websockets.exceptions.ConnectionClosedError as e:
        if "no close frame received or sent" not in str(e):
            print(f"Connection error from client: {e}")

async def handle_connection(websocket):
    send_task = asyncio.create_task(send_data(websocket))
    receive_task = asyncio.create_task(receive_data(websocket))
    done, pending = await asyncio.wait(
        [send_task, receive_task],
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()

def start_websocket_server():
    async def start_server():
        async with websockets.serve(
            handle_connection,
            "localhost",
            config.getint('settings', 'server_port'),
            ping_interval=60,  # Send ping every 60 seconds
            ping_timeout=90,   # Wait 90 seconds for pong response
            close_timeout=15   # Wait 15 seconds for close handshake
        ):
            await asyncio.Future()  # run forever

    asyncio.run(start_server())

if __name__ == "__main__":    
    # Start the detection thread
    detection_thread = threading.Thread(target=run_detection, daemon=True).start()
    
    # Start the websocket server thread
    websocket_thread = threading.Thread(target=start_websocket_server, daemon=True).start()

    print("All systems go. Please head to the character selection screen to start detection.")

    # Keep the main thread alive
    while True:
        time.sleep(1)