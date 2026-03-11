#!/bin/bash

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to install Homebrew
install_homebrew() {
    echo "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH for Apple Silicon Macs
    if [[ $(uname -m) == 'arm64' ]]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zshrc
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
}

# Check if Python is installed
if command_exists python3; then
    echo "Python is already installed"
else
    # Check if Homebrew is installed
    if ! command_exists brew; then
        install_homebrew
    fi
    
    # Install Python using Homebrew
    echo "Installing Python..."
    brew install python@3.11
    
    # Verify installation
    if ! command_exists python3; then
        echo "Failed to install Python"
        exit 1
    fi
fi

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip and install requirements
echo "Installing required packages..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Setup complete! Python and required packages have been installed."
echo "To activate the virtual environment in the future, run: source venv/bin/activate"

python3 download_driver.py