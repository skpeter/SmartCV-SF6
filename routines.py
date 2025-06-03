import configparser
from PIL import Image, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES=True
import cv2
import numpy as np
import threading
import time
import easyocr
import sf6
import re
import smartcv_core.core as core
from smartcv_core.matching import findBestMatch
from datetime import datetime
client_name = "smartcv-sf6"
payload_lock = threading.Lock()
config = configparser.ConfigParser()
config.read('config.ini')
previous_states = [None] # list of previous states to be used for state change detection
reader = easyocr.Reader(['en'])


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

def get_state():
    with payload_lock:
        return payload['state']

def detect_character_select_screen(payload, lock):
    
    img, scale_x, scale_y = core.capture_screen()
    if not img: return
    pixel = img.getpixel((int(115 * scale_x), int(55 * scale_y))) #white tournament mode icon
    pixel2 = img.getpixel((int(1805 * scale_x), int(55 * scale_y))) #back button area
    
    # Define the target color and deviation
    target_color = (128, 30, 29)  #red player 1 side
    target_color2 = (18, 77, 107)  #blue player 2 side
    target_color3 = (187, 0, 3)  #red player 1 side
    target_color4 = (10, 108, 173)  #blue player 2 side

    deviation = 0.1
    
    conditions = [
        core.is_within_deviation(pixel, target_color, deviation),
        core.is_within_deviation(pixel2, target_color2, deviation),
        core.is_within_deviation(pixel, target_color3, deviation),
        core.is_within_deviation(pixel2, target_color4, deviation)
    ]
    with lock:
        if sum(conditions) == 2:
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

def detect_characters(payload, lock):
    img, scale_x, scale_y = core.capture_screen()
    if not img: return
    time.sleep(core.refresh_rate)

    # signal to the main loop that character and tag detection is in progress
    if payload['state'] != "loading": return
    # Initialize the reader
    region1 = (int(215 * scale_x), int(410 * scale_y), int(565 * scale_x), int(100 * scale_y))
    region2 = (int(215 * scale_x), int(600 * scale_y), int(565 * scale_x), int(100 * scale_y))
    character1 = core.read_text(img, region1)
    character2 = core.read_text(img, region2)
    with lock:
        if character1 is not None and character2 is not None:
            c1, c2 = findBestMatch(character1, sf6.characters), findBestMatch(character2, sf6.characters)
        else: return detect_characters()
        payload['players'][0]['character'], payload['players'][1]['character'] = c1, c2
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "- Player 1 character:", c1)
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "- Player 2 character:", c2)

    time.sleep(core.refresh_rate)
    return

def detect_versus_screen(payload, lock):
    img, scale_x, scale_y = core.capture_screen()
    if not img: return
    pixel1 = img.getpixel((int(1050 * scale_x), int(185 * scale_y))) #black letterbox
    pixel2 = img.getpixel((int(1050 * scale_x), int(195 * scale_y))) #blue sky
    
    # Define the target color and deviation
    target_color = (0, 0, 0)  #black letterbox
    target_color2 = (64, 132, 207)  #blue sky
    deviation = 0.1
    
    with lock:
        if core.is_within_deviation(pixel1, target_color, deviation) and core.is_within_deviation(pixel2, target_color2, deviation):
            payload['state'] = "loading"
            if payload['state'] != previous_states[-1]:
                previous_states.append(payload['state'])
                print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "- Match is now loading...")
                detect_characters()
    return

def detect_player_tags(payload, lock):
    time.sleep(core.refresh_rate)
    if payload['players'][0]['name'] != None and payload['players'][1]['name'] != None: return
    img, scale_x, scale_y = core.capture_screen()
    if not img: return

    tag1 = core.read_text(img, (int(575 * scale_x), int(35 * scale_y), int(770 * scale_x), int(115 * scale_y)))
    tag2 = core.read_text(img, (int(575 * scale_x), int(880 * scale_y), int(770 * scale_x), int(115 * scale_y)))
    
    with lock:
        if tag1 is not None and tag2 is not None:
            payload['players'][0]['name'], payload['players'][1]['name'] = tag1.strip(), tag2.strip()
            print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "- Player 1 tag:", payload['players'][0]['name'])
            print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "- Player 2 tag:", payload['players'][1]['name'])
        else:
            for player in payload['players']:
                player['name'] = False
        return

def detect_round_start(payload, lock):
    img, scale_x, scale_y = core.capture_screen()
    if not img: return

    box = (int(960 * scale_x), int(475 * scale_y), int((960 + 10) * scale_x), int((475 + 180) * scale_y))
    cropped_area = img.crop(box)
    target_red = (190, 0, 0)
    deviation = 0.15
    width, height = cropped_area.size
    total_pixels = width * height
    red_pixels = 0

    for i in range(width):
        for j in range(height):
            if core.is_within_deviation(cropped_area.getpixel((i, j)), target_red, deviation):
                red_pixels += 1
    with lock:
        if red_pixels / total_pixels >= 0.9:
            print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "- Game starting")
            for player in payload['players']:
                player['rounds'] = 2
            payload['state'] = "in_game"
            if payload['state'] != previous_states[-1]:
                previous_states.append(payload['state'])


def detect_rounds(payload, lock):
    if payload['players'][0]['rounds'] < 2 and payload['players'][1]['rounds'] < 2: return
        
    img, scale_x, scale_y = core.capture_screen()
    if not img: return
    pixel1 = img.getpixel((int(800 * scale_x), int(90 * scale_y))) #p1 heart
    pixel2 = img.getpixel((int(1120 * scale_x), int(90 * scale_y))) #p2 heart

    if config.getboolean('settings', 'debug_mode', fallback=False):
        print("Player 1 heart pixel:", pixel1, "Player 2 heart pixel:", pixel2)
    
    # Define the target color and deviation
    target_color = (213, 33, 48)  #red heart (still has round)
    target_color2 = (150, 156, 163)  #gray heart (lost round)
    deviation = 0.15

    with lock:
        if core.is_within_deviation(pixel1, target_color, deviation):
            if payload['players'][0]['rounds'] == 1: print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "- Correcting previous round loss report")
            payload['players'][0]['rounds'] = 2
        if core.is_within_deviation(pixel2, target_color, deviation):
            if payload['players'][1]['rounds'] == 1: print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "- Correcting previous round loss report")
            payload['players'][1]['rounds'] = 2
        if core.is_within_deviation(pixel1, target_color2, deviation):
            if payload['players'][0]['rounds'] != 1: print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "- Player 1 lost a round")
            payload['players'][0]['rounds'] = 1
            return
        if core.is_within_deviation(pixel2, target_color2, deviation):
            if payload['players'][1]['rounds'] != 1: print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "- Player 2 lost a round")
            payload['players'][1]['rounds'] = 1
    return

def determine_winner(payload, lock, img, scale_x, scale_y, perfect=False):
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
        if (result[0] == 1 and payload['players'][0]['rounds'] == 1) or (result[0] == 2 and payload['players'][1]['rounds'] == 1):
            return True
    return False


def detect_game_end(payload, lock):
    """
    Possibly will be deprecated soon. Only use to switch scenes.
    """
    if payload['players'][0]['rounds'] > 1 and payload['players'][1]['rounds'] > 1: return

    img, scale_x, scale_y = core.capture_screen()
    if not img: return
    pixel1 = img.getpixel((int(666 * scale_x), int(740 * scale_y))) #"SLASH" white text
    pixel2 = img.getpixel((int(1140 * scale_x), int(655 * scale_y))) #"SLASH" white text
    pixelperfect1 = img.getpixel((int(640 * scale_x), int(765 * scale_y))) #red overlay around text
    pixelperfect2 = img.getpixel((int(55 * scale_x), int(295 * scale_y))) #"PERFECT" white text
            
    target_color = (255, 255, 255) #white text
    target_color2 = (255, 0, 0) #red overlay around text
    deviation = 0.2
    
    perfect = None
    with lock:
        if core.is_within_deviation(pixel1, target_color, deviation) and core.is_within_deviation(pixel2, target_color, deviation):
            perfect = False
        if core.is_within_deviation(pixelperfect1, target_color2, deviation) and core.is_within_deviation(pixelperfect2, target_color, deviation):
            perfect = True
        if perfect is not None:
            print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "- Perfect!" if perfect else "- Slash!")
            if determine_winner(payload, lock, img, scale_x, scale_y, perfect):
                payload['state'] = "game_end"
                if payload['state'] != previous_states[-1]:
                    previous_states.append(payload['state'])
            time.sleep(core.refresh_rate)
    return

def detect_result_screen(payload, lock):
    if payload['players'][0]['rounds'] == 0 or payload['players'][1]['rounds'] == 0: return
    img, scale_x, scale_y = core.capture_screen()
    if not img: return
    pixel = img.getpixel((int(1 * scale_x), int(105 * scale_y))) #the win/lose text for player 1
    pixel2 = img.getpixel((int(1 * scale_x), int(975 * scale_y))) #the win/lose text for player 1
    # Define the target color and deviation
    target_color = (140, 19, 5)  # red area on the top
    target_color2 = (36, 36, 36)  # gray area on the bottom
    deviation = 0.2
    if config.getboolean('settings', 'debug_mode', fallback=False):
        print("Detected result screen pixels - player 1:", pixel, "player 2:", pixel2)
    with lock:
        if ((core.is_within_deviation(pixel, target_color, deviation) and core.is_within_deviation(pixel2, target_color2, deviation))):
            if payload['players'][0]['rounds'] == 0 or payload['players'][1]['rounds'] == 0: return
            pixel = img.getpixel((int(450 * scale_x), int(730 * scale_y))) # win box for player 1
            pixel2 = img.getpixel((int(1735 * scale_x), int(730 * scale_y))) # lose box for player 2
            target_color = (190, 0, 0)  # red
            target_color2 = (0, 80, 144) # blue
            if ((core.is_within_deviation(pixel, target_color, deviation) and core.is_within_deviation(pixel2, target_color2, deviation))):
                payload['players'][1]['rounds'] = 0
                print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), f"- {payload['players'][0]['character']} wins!")
            pixel = img.getpixel((int(555 * scale_x), int(730 * scale_y))) # lose box for player 1
            pixel2 = img.getpixel((int(1630 * scale_x), int(730 * scale_y))) # win box for player 2
            if ((core.is_within_deviation(pixel, target_color2, deviation) and core.is_within_deviation(pixel2, target_color, deviation))):
                payload['players'][0]['rounds'] = 0
                print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), f"- {payload['players'][1]['character']} wins!")
            else: 
                pixel = img.getpixel((int(1700 * scale_x), int(730 * scale_y))) # win box for online player
                pixel2 = img.getpixel((int(1815 * scale_x), int(730 * scale_y))) # lose box for online player
                if (core.is_within_deviation(pixel, target_color, deviation)):
                    payload['players'][1]['rounds'] = 0
                    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), f"- {payload['players'][0]['character']} wins!")
                elif (core.is_within_deviation(pixel2, target_color2, deviation)):
                    payload['players'][0]['rounds'] = 0
                    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), f"- {payload['players'][1]['character']} wins!")
            if payload['players'][0]['rounds'] == 0 or payload['players'][1]['rounds'] == 0:
                payload['state'] = "game_end"
                if payload['state'] != previous_states[-1]:
                    previous_states.append(payload['state'])
            time.sleep(core.refresh_rate)

states_to_functions = {
    None: [detect_character_select_screen, detect_versus_screen],
    "character_select": [detect_versus_screen],
    "loading": [detect_player_tags, detect_round_start, detect_rounds],
    "in_game": [detect_character_select_screen, detect_rounds, detect_game_end, detect_result_screen],
    "game_end": [detect_result_screen, detect_character_select_screen, detect_round_start],
}