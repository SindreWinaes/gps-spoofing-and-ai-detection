# gps-spoofing-and-ai-detection
This is a Bachelor Thesis researching how an ML algorithm can detect GPS Spoofing attempts, this will be done with IoT Pycom devices recieving GPS signals and communicating it to a different Pycom that will run the ML and try to detect spoofing attempts.

## Pycom Development Environment

This Guide will help you setup your development environment for working with Pycom devices (LoPy4, FiPy etc.).

## Prerequisits

### 1. Python

#### Windows:

1. Download Python from  https://www.python.org/downloads/
2. Run the installer
3. Important; Check "Add Python to PATH" during installation
4. Verify installation: Open Comand Prompt/Terminal and run: python --verison

#### Linux(Ubuntu/Debian):

sudo apt update
sudo apt install python3 python3-pip python3-venv
python3 --version

#### MacOS:

Homebrew recomended:
brew install python
python3 --version



### 2. Node.js

Node.js is required for Pymakr extension to fucntion. 

#### Windows:

1. Download LTS version from https://nodejs.org/
2. Run installer with default settings
3. Restart your computer
4. Verify: Open Command Promt and run node --version

#### Linux (Ubuntu/Debian):

curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt install -y nodejs
node --version

#### MacOS:

brew install node
node --version

### 3. Git

#### Windows

1. Download from https://git-scm.com/download/win
2. Install with default settings
3. Verify: Open Command Prompt and run git --version


#### Linux (Ubuntu/Debian)

sudo apt install git
git --version

#### MacOS

brew install git
git --version

### 4. VS Code
Download and install from https://code.visualstudio.com/

Install the following extensions:

#### Requierd
| Extension  | Publisher | Description |
|------------|-----------|-------------|
| Python     | Microsoft | Python language support, debugging, Intellisense
| Pylance      | Microsoft   | Better Python autocomplete and type checking
| Pymakr       | Pycom       | Upload code to Pycom devices, REPL access, device management

#### Recomended
| Extension  | Publisher | Description |
|------------|-----------|-------------|
| Python Indent | Kevin Rose | Fixes Python indentation |
| GitLens | GitKraken | Enhanced Git integration history| 
| Git Graph | mhutchie | Visualize Git Branches | 


## Project Setup

1. Clone Repository:
     - git clone git@github.com:SindreWinaes/gps-spoofing-and-ai-detection.git
     - 
2. Create virtual environment, this keeps project dependencies. Make sure you are in the projectfolder:

     **cd to project folder**
     - cd gps-spoofing-and-ai-detectio
       
     **Command prompt:**
     python -m venv venv
     venv\Scripts\activate
     pip install -r requirements.txt

     **Powershell:**
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     pip install -r requirements.txt

   **Linux/MacOS:**
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt

5. Open project in VS code, it will automatically detect the virtual environment (venv) and ask to use it as the interpreter, click Yes.

If it doesn't ask automatically:
1. Press Ctrl+Shift+P (Cmd+Shift+P on MacOS)
2. Type "Python:Select Interpreter"
3. Choose interpreter from your venv folder.
    
VS Code remembers your interpreter selection. When you open the project folder again:

VS Code automatically uses the correct virtual environment
Open a new terminal in VS Code (Ctrl+` or View → Terminal)
The terminal should automatically activate the venv (you'll see (venv) in the prompt)
If it doesn't activate automatically, you can manually activate it:

Windows: venv\Scripts\activate
Linux/macOS: source venv/bin/activate

VS Code GUI for virtual environments:
VS Code shows the current Python interpreter in the bottom status bar (bottom right). Click on it to:

See which interpreter/venv is active
Switch to a different interpreter
Select a virtual environmen

Manually deactivating (optional):
If you want to manually deactivate the virtual environment, type deactivate in the same terminal where you activated it and press Enter. This works the same on all operating systems.


## Pycom Device Setup
1. Connect Your Device via USB to you computer.
2. While in your project folder, look for Pymakr panel in the sidebar.
3. Click "List all devices".
4. Your Device should apear, click "Connect"
5. Click "Sync project to device" in the Pymakr panel. 
6. Press the reset button on your device.


## Troubleshooting

**Pymakr commands not working**
- Make sure Node.js is installed and restart VS Code.
- Try uninstalling and reinstalling the Pymakr extension
- Check view -> Output -> Pymakr for error messages.

**Device not detected**
- Try different USB cables (some are power only)
- Try different USB port.
- Check device manager.









