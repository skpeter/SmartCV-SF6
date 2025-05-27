import tkinter as tk
import threading, time
from inputs import get_gamepad
import tkinter.font as tkFont

def on_focus_in(event):
    current_font = tkFont.Font(font=event.widget.cget("font"))
    current_font.configure(weight="bold")
    event.widget.config(font=current_font)

def on_focus_out(event):
    current_font = tkFont.Font(font=event.widget.cget("font"))
    current_font.configure(weight="normal")
    event.widget.config(font=current_font)

def choose_player_side(player1: str, player2: str):
    chosen_player = {"name": None}

    def select_player(name):
        chosen_player["name"] = name
        root.destroy()

    root = tk.Tk()
    root.configure(bg="dark gray")
    root.overrideredirect(True)  # removes the title bar and close button
    root.title("Choose Player 1")
    root.attributes("-topmost", True)  # keep the window always active

    # Calculate the position for centering the window
    # Set an initial width and height for the window
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

    prompt = tk.Label(container, font=("Helvetica", 24), text="Select which player will be Player 1:\n⬅️ (left side)\nControllers are enabled!", bg="dark gray")
    prompt.pack(pady=10)

    button1 = tk.Button(container, text=player1, width=50, font=("Helvetica", 32), command=lambda: select_player(player1))
    button1.pack(padx=10, pady=5)

    button2 = tk.Button(container, text=player2, width=50, font=("Helvetica", 32), command=lambda: select_player(player2))
    button2.pack(padx=10, pady=5)

    # Set initial focus to button1
    button1.focus_set()

    

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
            while True:
                try:
                    events = get_gamepad()
                except Exception as e:
                    time.sleep(2)
                    continue
                for event in events:
                    print(event.code, event.state, event.ev_type)
                    if event.ev_type in ['Key', 'Absolute']:
                    # dpad up/down, compatible with both xinput and DS4
                        if event.code == 'ABS_HAT0Y':
                            if event.state == -1:
                                root.after(0, button1.focus_set)
                            elif event.state == 1:
                                root.after(0, button2.focus_set)
                        # Mapped to A and X xinput buttons (must test on DS4)
                        if (event.code == 'BTN_SOUTH' or event.code == 'BTN_WEST') and event.state:
                            root.after(0, lambda: button1.invoke() if root.focus_get() == button1 else button2.invoke())
                time.sleep(0.02)
        threading.Thread(target=poll_gamepad, daemon=True).start()
    root.after(2000, enable_controls)

    root.mainloop()
    return chosen_player["name"]

# choose_player_side("CamposJL", "Andromeda")