import tkinter as tk
import threading, time
import pygame
import pygetwindow as gw
import tkinter.font as tkFont
import configparser
config = configparser.ConfigParser()
config.read('config.ini')

def on_focus_in(event):
    current_font = tkFont.Font(font=event.widget.cget("font"))
    current_font.configure(weight="bold")
    event.widget.config(font=current_font)

def on_focus_out(event):
    current_font = tkFont.Font(font=event.widget.cget("font"))
    current_font.configure(weight="normal")
    event.widget.config(font=current_font)

def focus_game_window():
    windows = gw.getWindowsWithTitle(config.get('settings', 'executable_title'))
    if windows: # Check if the list is not empty
        window = windows[0]
        window.minimize()
        window.restore()
    else:
        pass

def unfocus_game(delay=500):
    temp = tk.Tk()
    temp.overrideredirect(True)      # No window decorations
    temp.attributes("-alpha", 1)  # Almost invisible
    temp.geometry("1x1+50+50")         # Tiny size, top-left corner
    temp.lift()
    temp.attributes("-topmost", True)
    temp.after(delay, temp.destroy)  # Destroy after a short delay
    temp.mainloop()

def choose_player_side(player1: str, player2: str):
    pygame.init()
    pygame.joystick.init()

    chosen_player = {"name": None}
    current_selection = {"option": None}


    def select_player(name):
        chosen_player["name"] = name
        fade_out()

    unfocus_game()
    time.sleep(1)
    root = tk.Tk()
    root.configure(bg="dark gray")
    root.overrideredirect(True)  # removes the title bar and close button
    root.attributes("-topmost", True)  # keep the window always active

    root.attributes("-alpha", 0.0)
    def fade_in(alpha=0.0):
        alpha += 0.05
        if alpha > 1.0:
            alpha = 1.0
        root.attributes("-alpha", alpha)
        if alpha < 1.0:
            root.after(25, fade_in, alpha)
        else:
            root.focus_force()  # Force focus to this window
            button1.focus_set()
    fade_in()

    def fade_out(alpha=1.0):
        alpha -= 0.05
        if alpha <= 0:
            root.destroy()
            time.sleep(0)
            focus_game_window()
        else:
            root.attributes("-alpha", alpha)
            root.after(10, fade_out, alpha)

    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    width = int(screen_width - screen_width / 5)
    height = int(screen_height - screen_height / 5)
    x = int((screen_width / 2) - (width / 2))
    y = int((screen_height / 2) - (height / 2))
    root.geometry(f"{width}x{height}+{x}+{y}")

    container = tk.Frame(root)
    container.configure(bg="dark gray")
    container.pack(expand=True)

    prompt = tk.Label(container, font=("Helvetica", 24), text="Select which player will be Player 1:\n⬅️ (left side)\nControllers are enabled!    Press X / A / Square to select", bg="dark gray")
    prompt.pack(pady=10)

    button1 = tk.Button(container, text=player1, width=50, font=("Helvetica", 32), command=lambda: select_player(player1))
    button1.pack(padx=10, pady=5)

    button2 = tk.Button(container, text=player2, width=50, font=("Helvetica", 32), command=lambda: select_player(player2))
    button2.pack(padx=10, pady=5)

    confirmation_label = tk.Label(
        container,
        text="",
        font=("Helvetica", 24),
        bg="dark gray",
        fg="black"
    )
    confirmation_label.pack(pady=10)

    def handle_selection(option):
        if current_selection["option"] == option:
            select_player(option)
        else:
            current_selection["option"] = option
            confirmation_label.config(text="Press again to confirm")

    def clear_confirmation(event):
        # Hide the confirmation if focus changes to a button that isn’t the one already selected
        if current_selection["option"] and event.widget.cget("text") != current_selection["option"]:
            current_selection["option"] = None
            confirmation_label.config(text="")

    button1.config(command=lambda: handle_selection(player1))
    button2.config(command=lambda: handle_selection(player2))
    button1.bind("<FocusIn>", clear_confirmation, add="+")
    button2.bind("<FocusIn>", clear_confirmation, add="+")

    button1.bind("<FocusIn>", on_focus_in)
    button1.bind("<FocusOut>", on_focus_out)
    button2.bind("<FocusIn>", on_focus_in)
    button2.bind("<FocusOut>", on_focus_out)

    def enable_controls():
        # keyboard
        container.bind_all("<Up>", lambda event: button1.focus_set())
        container.bind_all("<Down>", lambda event: button2.focus_set())
        container.bind_all("<Return>", lambda event: (button1.invoke() if root.focus_get() == button1 else button2.invoke()))
        def poll_gamepad():
            pygame.joystick.get_count()
            while True:
                try:
                    for event in pygame.event.get():
                        # allow hot-plug by reinitializing joysticks when a device is added
                        if event.type == pygame.JOYDEVICEADDED:
                            joystick = pygame.joystick.Joystick(event.device_index)
                            joystick.init()
                        # left analog stick vertical movement (axis 1) for focus control
                        if event.type == pygame.JOYAXISMOTION:
                            if event.axis == 1:
                                if event.value < -0.5:
                                    root.after(0, button1.focus_set)
                                elif event.value > 0.5:
                                    root.after(0, button2.focus_set)
                        # d-pad vertical movement for focus control
                        if event.type == pygame.JOYHATMOTION:
                            hat_x, hat_y = event.value
                            if hat_y == 1:
                                root.after(0, button1.focus_set)
                            elif hat_y == -1:
                                root.after(0, button2.focus_set)
                        # assuming button 0 is the "A"/"X" button to select
                        if event.type == pygame.JOYBUTTONDOWN:
                            if event.button == 0:
                                root.after(0, lambda: button1.invoke() if root.focus_get() == button1 else button2.invoke())
                    time.sleep(0.01)
                except Exception as e:
                    pass
        threading.Thread(target=poll_gamepad, daemon=True).start()
    root.after(100, enable_controls)

    root.mainloop()
    return chosen_player["name"]

if __name__ == "__main__": # for testing only
    choose_player_side("Juliana", "Andromeda")