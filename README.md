# SmartCV-RoA2

https://github.com/user-attachments/assets/f1c46930-3639-43b1-b6b0-a7d512f58d5a

SmartCV-RoA2 is a tool designed to provide data on Rivals of Aether II without the need for installing mods on your game, or the need for a powerful PC to read game data in real time. 

It's a project that uses pixel detection to recognize certain situations in the game to take the opportunity to read data from using OCR. Due to this, it's able to gather enough data to report the results on a match (some assumptions given). Look for the **How does it work?** section to get a more in-depth explanation.

## Requirements
- [OBS (optional if streaming)](https://obsproject.com/download)
- [Advanced Scene Switcher OBS Plugin (optional if streaming)](https://github.com/WarmUpTill/SceneSwitcher/releases)
- Your copy of Rivals of Aether II must be in **English**. Support for other languages is being looked into.

### Step 1.1: Installing the CPU version
- Installing the CPU version is very easy. Just download the compiled release.zip [here](https://github.com/skpeter/smartcv/releases).
- You can skip to step 2 from here.
### Step 1.2: Installing the GPU version
- You will need to download the **source code** zip [here](https://github.com/skpeter/smartcv/releases).
- Install Python if you haven't done so already [here](https://www.python.org/downloads/). **Recommended version is 3.12**.
- You will need to then install PyTorch, which is done through command prompt/terminal. Go to Pytorch's "Start Locally" section [here](https://pytorch.org/get-started/locally/), pick the **Stable** build, select the OS you use (**Windows, Mac or Linux**), **Pip** as packaging system, **Python** as language and then select the **Compute Platform** available on your GPU. You can check which version of CUDA your GPU supports [here](https://en.wikipedia.org/wiki/CUDA#GPUs_supported).
![PyTorch installation page](img/install1.jpg)
- - Choosing these options will generate a command that you should copy and paste on your terminal/command prompt. PyTorch weighs around 3GB, so take your time.

## Step 2: OBS Setup
### If you are running the game from the same PC and not receiving game feed from a capture card / console, you can skip this step!

SmartCV will read from a separate feed from OBS that will be provided to it. This is where Advanced Scene Switcher comes in. Once you have it installed, open it on the Tools tab:
![Advanced Scene Switcher Setup](img/guide1.jpg)
- On the window that opens, go to the Macros tab and click on the plus sign to add a new macro (you can name it anything you want). Click on the other plus signs to add a condition and an action to this macro. I've attached a screenshot so you can mimic the settings:

![Advanced Scene Switcher Setup](img/guide2.jpg)
- - "SSBU" should be the Video Capture Device source that is using your capture card.
- - You can set the path to save the screenshot anywhere you'd like (SmartCV must have access to it), but it is **highly recommended** that you save the screenshot as a **WEBP**. This image format causes the least amount of issues and is very lightweight, however if for some reason you can't use WEBPs, you can save it as a JPG instead. 
- Go to SmartCV's `config.ini` file, set the `capture_mode` setting to `obs` and set the `feed_path` setting to the path where OBS is saving the screenshots.

## Step 3: Usage
- To run the GPU version of the app, open the `smartcv.bat` file. To run the CPU version just open `smartcv.exe`.
**From here all you need to do is follow the on-screen instructions for the game detection to start.**
**If using OBS, make sure it is open and do not disable the game capture source!**

## Troubleshooting
- **When I run the app it says a bunch of code that ends with `ModuleNotFoundError: No module named 'torch'"` at the end! What do I do?**

Try restarting your system. If that doesn't work, append `py -m` to the code that installs PyTorch. For example: `py -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118`

## Where do I use this?
SmartCV opens a websocket server (on port 6565 by default) to send data to.
As of this writing, only [S.M.A.R.T.](https://skpeter.github.io/smart-user-guide) has integrations to it. If you want to integrate SmartCV into your own app, you can look at what the data output looks like on the example JSON files.

## Known Issues

- The app sometimes isn't able to read the stage that the match is being played.

- The app doesn't know how to differentiate handwarmers from actual matches. Please instruct your players to use the Restart or Quit options in the menu when being done with handwarmers. [S.M.A.R.T.](https://skpeter.github.io/smart-user-guide) (the companion app) may be able to handle some cases where that doesn't happen.

## How does it work?

Explanation coming soon

## Check out also:
- [SmartCV-SSBU for Super Smash Bros. Ultimate](https://github.com/skpeter/SmartCV-SSBU)

## Contact

[I am mostly available on my team's Discord Server if you'd like to talk about SmartCV or have any additional questions.](https://discord.gg/zecMKvF8b5)
