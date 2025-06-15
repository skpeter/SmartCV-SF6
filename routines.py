import configparser
import time
import sf6
import numpy as np
import core.core as core
from core.matching import findBestMatch
from PIL import ImageEnhance
client_name = "smartcv-sf6"
config = configparser.ConfigParser()
config.read('config.ini')
previous_states = [None] # list of previous states to be used for state change detection

payload = {
    "state": None,
    "round": 1,
    "players": [
        {
            "name": None,
            "character": None,
            "rounds": 2,
            "health": 99
        },
        {
            "name": None,
            "character": None,
            "rounds": 2,
            "health": 99,
        }
    ]
}

def detect_character_select_screen(payload:dict, img, scale_x:float, scale_y:float):
    
    pixel = img.getpixel((int(15 * scale_x), int(860 * scale_y))) #boxes on the back
    pixel2 = img.getpixel((int(1840 * scale_x), int(485 * scale_y))) #blue paint
    
    target_color = (163, 51, 68)  #red
    target_color2 = (4, 65, 249)  #blue

    deviation = 0.15
    # if config.getboolean('settings', 'debug_mode', fallback=False):
    #     print("Character select screen pixels - player 1:", pixel, "player 2:", pixel2)
    
    if (core.is_within_deviation(pixel, target_color, deviation)
    and core.is_within_deviation(pixel2, target_color2, deviation)):
        payload['state'] = "character_select"
        core.print_with_time("- Character select screen detected")
        if payload['state'] != previous_states[-1]:
            previous_states.append(payload['state'])
    return

def detect_characters(payload:dict, img, scale_x:float, scale_y:float):
    t1, t2, c1, c2 = None, None, None, None
    characters = []
    stitched = []
    x,y,w,h = (int(100 * scale_x), int(915 * scale_y), int(1880 * scale_x), int(90 * scale_y))
    img = np.array(img)
    cropped = img[int(y):int(y+h), int(x):int(x+w)]
    # signal to the main loop that character and tag detection is in progress
    if payload['state'] != "loading" or payload['players'][0]['character']: return
    try:
        stitched = core.stitch_text_regions(cropped, int(80 * scale_y), (255,255,255), margin=30, deviation=0.4) 
        cropped = stitched.copy()
        characters = core.read_text(cropped, contrast=2)
        if characters: characters = characters.lower().replace('chun li', 'chun-li').split(' ')
    except:
        pass
    if 'stitched' not in locals() or len(stitched) != 2:
        core.print_with_time("- Could not read characters. This is probably an online match...")
    if characters and len(characters) == 2:
        c1, _ = findBestMatch(characters[0], sf6.characters)
        c2, _ = findBestMatch(characters[1], sf6.characters)
    else: 
        x,y,w,h = (int(105 * scale_x), int(820 * scale_y), int(1713 * scale_x), int(127 * scale_y))
        cropped = img[int(y):int(y+h), int(x):int(x+w)]
        characters = core.read_text(cropped, contrast=2)
        if characters: characters = characters.lower().replace('chun li', 'chun-li').split(' ')
        if characters and len(characters) == 4:
            c1, _ = findBestMatch(characters[0], sf6.characters)
            c2, _ = findBestMatch(characters[1], sf6.characters)
            t1 = characters[2]
            t2 = characters[3]
    payload['players'][0]['character'], payload['players'][1]['character'], payload['players'][0]['name'], payload['players'][1]['name'] = c1, c2, t1, t2
    core.print_with_time(f"{payload['players'][0]['name'] if payload['players'][0]['name'] else "Player 1"} as:", c1)
    core.print_with_time(f"{payload['players'][1]['name'] if payload['players'][1]['name'] else "Player 2"} as:", c2)
    return True

def detect_versus_screen(payload:dict, img, scale_x:float, scale_y:float):
    
    box = (int(928 * scale_x), int(50 * scale_y), int(26 * scale_x), int(187 * scale_y))
    if core.get_color_match_in_region(img, box, (34, 7, 9), 0.1) >= 0.9:
        payload['state'] = "loading"
        if payload['state'] != previous_states[-1]:
            previous_states.append(payload['state'])
            core.print_with_time("- Match is now loading...")
            payload['round'] = 1
            for player in payload['players']:
                player['health'] = 99
                player['rounds'] = 2
                player['character'] = None
                player['name'] = None
            detect_characters(payload, img, scale_x, scale_y)
    return

def detect_round_start(payload:dict, img, scale_x:float, scale_y:float):
    box = (int(1347 * scale_x), int(381 * scale_y), int(40 * scale_x), int(40 * scale_y))

    if core.get_color_match_in_region(img, box, (230, 230, 230), 0.1) >= 0.9:
        if any(player['rounds'] == 0 for player in payload['players']): payload['round'] = 1
        if payload['players'][0]['health'] > 99 and payload['players'][0]['health'] == 100: return
        core.print_with_time(f"Round {payload['round']} starting")
        for player in payload['players']: player['health'] = 100
        if payload['round'] == 1:
            for player in payload['players']: player['rounds'] = 2
        payload['state'] = "in_game"
        if payload['state'] != previous_states[-1]:
            previous_states.append(payload['state'])

def detect_health_bars(payload:dict, img, scale_x:float, scale_y:float, detect_ko=False):
    if not detect_ko and (payload['players'][0]['health'] == 0 or payload['players'][1]['health'] == 0): return
    img = img.convert("L")
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(3.0)  # adjust the factor as needed
    img.save('temp.png')
    healthbar1 = core.get_color_match_in_region(img, (int(167 * scale_x), int(63 * scale_y), int(680 * scale_x), 1), (210, 210, 210), 0.2)
    healthbar2 = core.get_color_match_in_region(img, (int(1071 * scale_x), int(63 * scale_y), int(680 * scale_x), 1), (210, 210, 210), 0.2)
    payload['players'][0]['health'] = int(healthbar1 * 100)
    payload['players'][1]['health'] = int(healthbar2 * 100)

    if config.getboolean('settings', 'debug_mode', fallback=False):
        print("Player 1 health bar:", healthbar1, "Player 2 health bar:", healthbar2, "KO Check:", detect_ko)
    
    if np.floor(healthbar1 * 100) / 100 == 0 or np.floor(healthbar2 * 100) / 100 == 0:
        if detect_ko:
            core.print_with_time("- K.O.", end=" ")
            if healthbar1 < healthbar2:
                payload['players'][0]['rounds'] -= 1
                print(f"by {payload['players'][1]['character']}")
            elif healthbar2 < healthbar1:
                payload['players'][1]['rounds'] -= 1
                print(f"by {payload['players'][0]['character']}")
            else:
                time.sleep(0.5)
                return # detect_health_bars(payload, img, scale_x, scale_y, detect_ko=True)
            payload['round'] += 1
            if payload['players'][0]['rounds'] == 0 or payload['players'][1]['rounds'] == 0:
                core.print_with_time(f"{payload['players'][0]['character'] if payload['players'][0]['rounds'] > 0 else payload['players'][1]['character']} wins!")
                payload['state'] = "game_end"
                payload['round'] = 1
                if payload['state'] != previous_states[-1]:
                    previous_states.append(payload['state'])
            return
        time.sleep(1.25)
        return detect_health_bars(payload, img, scale_x, scale_y, detect_ko=True)
            
    return

def detect_results(payload:dict, img, scale_x:float, scale_y:float):
    # this function only works when players don't mash the result screen so only really viable to validate end of a set 
    if payload['players'][0]['rounds'] == 0 or payload['players'][1]['rounds'] == 0: return
    result = core.read_text(img, (int(811 * scale_x), int(833 * scale_y), int(290 * scale_x), int(50 * scale_y)))
    
    if result: 
        print("- Result text detected - validating results", result)
        result = result.split(' ')
        if len(result) >= 2:
            if findBestMatch(result[0], ["WIN", "LOSE"]) == "WIN" and payload['players'][0]['rounds'] == 0:
                payload['players'][0]['rounds'] = 1
                payload['players'][1]['rounds'] = 0
                core.print_with_time("- Corrected result - Player 1 won the match")
            elif findBestMatch(result[0], ["WIN", "LOSE"]) == "LOSE" and payload['players'][1]['rounds'] == 0:
                payload['players'][1]['rounds'] = 1
                payload['players'][0]['rounds'] = 0
                core.print_with_time("- Corrected result - Player 2 won the match")

states_to_functions = {
    None: [detect_character_select_screen, detect_versus_screen],
    "character_select": [detect_versus_screen],
    "loading": [detect_round_start],
    "in_game": [detect_character_select_screen, detect_round_start, detect_health_bars],
    "game_end": [detect_results, detect_character_select_screen, detect_round_start, detect_versus_screen], # remove detect_versus_screen when releasing v1
}