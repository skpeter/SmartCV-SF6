import configparser
import time
import sf6
import threading
import numpy as np
import core.core as core
from core.matching import findBestMatch
import re
client_name = "smartcv-sf6"
config = configparser.ConfigParser()
config.read('config.ini')
previous_states = [None] # list of previous states to be used for state change detection

payload = {
    "state": None,
    "round": 0,
    "players": [
        {
            "name": None,
            "character": None,
            "games": 0,
            "rounds": 0,
        },
        {
            "name": None,
            "character": None,
            "games": 0,
            "rounds": 0,
        }
    ]
}

def detect_character_select_screen(payload:dict, img, scale_x:float, scale_y:float):
    
    pixel = img.getpixel((int(15 * scale_x), int(860 * scale_y))) #boxes on the back
    pixel2 = img.getpixel((int(1840 * scale_x), int(485 * scale_y))) #blue paint
    
    target_color = (163, 51, 68)  #red
    target_color2 = (4, 65, 249)  #blue

    deviation = 0.15
    if config.getboolean('settings', 'debug_mode', fallback=False):
        print("Character select screen pixels - player 1:", pixel, "player 2:", pixel2)
    
    if (core.is_within_deviation(pixel, target_color, deviation)
    and core.is_within_deviation(pixel2, target_color2, deviation)):
        payload['state'] = "character_select"
        if payload['round'] == 0:
            for player in payload['players']: player['name'] = None
        core.print_with_time("- Character select screen detected")
        if payload['state'] != previous_states[-1]:
            previous_states.append(payload['state'])
    return

def detect_characters(payload:dict, img, scale_x:float, scale_y:float, is_online_match=False):
    t1, t2, c1, c2 = None, None, None, None
    characters = []
    stitched = []
    img = np.array(img)
    if payload['state'] != "loading" or payload['players'][0]['character']: return
    if not is_online_match:
        try:
            x,y,w,h = (int(225 * scale_x), int(915 * scale_y), int(1475 * scale_x), int(90 * scale_y))
            cropped = img[int(y):int(y+h), int(x):int(x+w)]
            stitched = core.stitch_text_regions(cropped, int(80 * scale_y), (255,255,255), margin=50, deviation=0.4) 
            cropped = stitched.copy()
            characters = core.read_text(cropped, contrast=2)
            if not characters:
                payload['state'] = previous_states[-1]
                return
        except:
            pass
        if characters and len(characters) == 2:
            c1, _ = findBestMatch(characters[0], sf6.characters)
            c2, _ = findBestMatch(characters[1], sf6.characters)
    else: 
        x,y,w,h = (int(105 * scale_x), int(820 * scale_y), int(1814 * scale_x), int(127 * scale_y))
        cropped = img[int(y):int(y+h), int(x):int(x+w)]
        characters = core.read_text(cropped, contrast=2)
        if characters: characters = [ch for ch in characters if "win" not in ch.lower()]
        if characters and len(characters) >= 4:
            c1, _ = findBestMatch(characters[0], sf6.characters)
            c2, _ = findBestMatch(characters[1], sf6.characters)
            t1 = characters[2]
            t2 = characters[3]
        payload['players'][0]['name'], payload['players'][1]['name'] = t1, t2
    if not c1: return False
    payload['players'][0]['character'], payload['players'][1]['character'] = c1, c2
    core.print_with_time(f"{payload['players'][0]['name'] if payload['players'][0]['name'] else "Player 1"} as:", c1)
    core.print_with_time(f"{payload['players'][1]['name'] if payload['players'][1]['name'] else "Player 2"} as:", c2)
    return True

def detect_versus_screen(payload:dict, img, scale_x:float, scale_y:float):
    target_color = (86, 13, 143) #classic icon
    target_color2 = (159, 67, 15) # modern icon
    pixel = img.getpixel((int(62 * scale_x), int(859 * scale_y)))
    pixel2 = img.getpixel((int(1834 * scale_x), int(859 * scale_y)))
    deviation = 0.125
    if config.getboolean('settings', 'debug_mode', fallback=False):
        print("Versus screen pixels:", pixel, pixel2)
    conditions = [
        core.is_within_deviation(pixel, target_color, deviation),
        core.is_within_deviation(pixel2, target_color, deviation),
        core.is_within_deviation(pixel, target_color2, deviation),
        core.is_within_deviation(pixel2, target_color2, deviation)
    ]
    if sum(conditions) == 2:
        payload['state'] = "loading"
        if payload['state'] != previous_states[-1]:
            previous_states.append(payload['state'])
            core.print_with_time("- Match is now loading...")
            payload['round'] = 0
            for player in payload['players']:
                player['rounds'] = 0
                player['character'] = None
            pixel = img.getpixel((int(62 * scale_x), int(840 * scale_y)))
            is_online_match = True if core.is_within_deviation(pixel, target_color, deviation) or core.is_within_deviation(pixel, target_color2, 0.1) else False
            if not detect_characters(payload, img, scale_x, scale_y, is_online_match):
                payload['state'] = previous_states[-2]
    return

round_start_lock = False
def detect_round_start(payload:dict, img, scale_x:float, scale_y:float):
    global round_start_lock, ko_passes
    if round_start_lock: return
    target_color1 = (130, 1, 46)
    target_color2 = (18, 54, 140)
    pixel1 = img.getpixel((int(195 * scale_x), int(80 * scale_y)))  # left side
    pixel2 = img.getpixel((int(1725 * scale_x), int(80 * scale_y)))  # left side
    if core.is_within_deviation(pixel1, target_color1, 0.1) and core.is_within_deviation(pixel2, target_color2, 0.1):
        round_start_lock = True
        ko_passes = [0, 0]
        if len([player for player in payload['players'] if player['rounds'] == 2]) > 1: payload['round'] = 0
        payload['round'] += 1
        if payload['round'] == 1:
            for player in payload['players']: player['rounds'] = 0
        detect_scoreboard(payload, img, scale_x, scale_y)
        core.print_with_time(f"Round {payload['round']} starting")
        payload['state'] = "in_game"
        if payload['state'] != previous_states[-1]:
            previous_states.append(payload['state'])
        threading.Thread(target=round_start_unlock).start()

def round_start_unlock():
    global round_start_lock
    time.sleep(20)
    round_start_lock = False
    
def detect_scoreboard(payload:dict, img, scale_x:float, scale_y:float):
    offsets = [
        (int(635 * scale_x), int(15 * scale_y), int(40 * scale_x), int(30 * scale_y)),
        (int(1250 * scale_x), int(15 * scale_y), int(40 * scale_x), int(30 * scale_y))
    ]
    images = [
        "img/0.png",
        "img/1.png",
        "img/2.png",
    ]
    results1 = {im: core.detect_image(img, scale_x, scale_y, im, offsets[0]) for im in images}
    results2 = {im: core.detect_image(img, scale_x, scale_y, im, offsets[1]) for im in images}
    score1_img = max(results1, key=results1.get)
    score2_img = max(results2, key=results2.get)
    match1 = results1[score1_img]
    match2 = results2[score2_img]
        
    if config.getboolean('settings', 'debug_mode', fallback=False):
        core.print_with_time("Game template matching results:", (score1_img, match1), (score2_img, match2), end=' ')
        
    if match1 > 0.5 and match2 > 0.5:
        print("Detected score")
        payload['players'][0]['games'] = re.sub(r'[^012]', '', score1_img)
        payload['players'][1]['games'] = re.sub(r'[^012]', '', score2_img)
    else:
        if config.getboolean('settings', 'debug_mode', fallback=False) == True:
            print("No match")
    return

ko_passes = [0, 0]

ko_passes = [0, 0]
def detect_ko(payload:dict, img, scale_x:float, scale_y:float):
    global ko_passes
    if len([p for p in ko_passes if p > 3]) > 0: return
    # pixel = img.getpixel((int(770 * scale_x), int(500 * scale_y))) # KO
    # target_color = (230, 237, 235)
    # if not core.is_within_deviation(pixel, target_color, 0.2): return

    pixel = img.getpixel((int(870 * scale_x), int(96 * scale_y)))
    pixel2 = img.getpixel((int(850 * scale_x), int(63 * scale_y)))
    pixel3 = img.getpixel((int(1049 * scale_x), int(96 * scale_y)))
    pixel4 = img.getpixel((int(1074 * scale_x), int(63 * scale_y)))
    if config.getboolean('settings', 'debug_mode', fallback=False):
        print("KO detection pixels:", max(sum(pixel), sum(pixel2)), max(sum(pixel3), sum(pixel4)), "KO Check:", ko_passes)
    dark_bar1 = True if max(sum(pixel), sum(pixel2)) < (500 - (100 * ko_passes[0])) else False
    dark_bar2 = True if max(sum(pixel3), sum(pixel4)) < (500 - (100 * ko_passes[1])) else False
    if dark_bar1 ^ dark_bar2:
        if dark_bar1: ko_passes[1] += 1
        if dark_bar2: ko_passes[0] += 1
        if ko_passes[0] > 3 or ko_passes[1] > 3:
            core.print_with_time("K.O.", end=" ")
            winner = 0 if ko_passes[0] > 0 else 1
            payload['players'][winner]['rounds'] += 1
            print(f"by {payload['players'][winner]['character']}")
            if payload['players'][0]['rounds'] == 2 or payload['players'][1]['rounds'] == 2:
                core.print_with_time(f"{payload['players'][winner]['character']} wins!")
                payload['state'] = "game_end"
                payload['round'] = 0
                if payload['state'] != previous_states[-1]:
                    previous_states.append(payload['state'])
        return
    ko_passes = [max(p - 1, 0) for p in ko_passes]
    return


def detect_results(payload:dict, img, scale_x:float, scale_y:float):
    if len([player for player in payload['players'] if player['rounds'] == 2]): return
    if int(payload['players'][0]['games']) > 0 or int(payload['players'][1]['games']) > 0: return
    # this function only works when players don't mash the result screen so only really viable to validate end of a set 
    pixel = img.getpixel((int(963 * scale_x), int(855 * scale_y)))
    pixel2 = img.getpixel((int(784 * scale_x), int(927 * scale_y))) # win rate
    target_color = (173, 161, 157)
    target_color2 = (164, 16, 86)
    target_color3 = (48, 71, 187)
    if core.is_within_deviation(pixel, target_color, 0.25) and core.is_within_deviation(pixel2, target_color2, 0.25) and core.is_within_deviation(pixel2, target_color3, 0.25):
        result = core.read_text(img, (int(912 * scale_x), int(833 * scale_y), int(100 * scale_x), int(50 * scale_y)), low_text=0.2)
        if result and len(result) > 1: 
            if config.getboolean('settings', 'debug_mode', fallback=False): 
                core.print_with_time("Result text detected - validating results", result, end='')
            result = result[0].split('-')
            payload['players'][0]['games'] = result[0]
            payload['players'][1]['games'] = result[1]
            payload['round'] = 0

states_to_functions = {
    None: [detect_character_select_screen, detect_versus_screen],
    "character_select": [detect_versus_screen, detect_round_start],
    "loading": [detect_round_start],
    "in_game": [detect_character_select_screen, detect_round_start, detect_ko, detect_results],
    "game_end": [detect_results, detect_character_select_screen, detect_round_start, detect_versus_screen],
}