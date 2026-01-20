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
Extension  | Publisher | Description
Python       Microsoft   Python language support, debugging, Intellisense
Pylance      Microsoft   Better Python autocomplete and type checking
Pymakr       Pycom       Upload code to Pycom devices, REPL access, device management

#### Recomended
Extension  | Publisher | Description
Python Indent


















