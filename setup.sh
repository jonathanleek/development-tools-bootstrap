#!/bin/zsh
# setup development environment
# os x catalina 10.15
# jonathan leek

echo "Setup.sh requires xcode to be installed"

echo "Checking Xcode CLI tools"
xcode-select --install

echo "Setup homebrew"
which -s brew
if [[ $? != 0 ]] ; then
    echo "Installing homebrew"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install.sh)"
else
    echo "Updating homebrew"
    git -C /usr/local/Homebrew/Library/Taps/homebrew/homebrew-core fetch --unshallow
    brew update
    brew upgrade
    brew cleanup
fi

echo "Setup ohmyzsh"
/bin/bash -c "$(curl -fsSL https://raw.github.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"

echo "Setup amazon web services aws cli version 2"
brew install awscli@2

echo "Setup pyenv to manage system and context python versions"
brew install pyenv

echo "Setup nerd fonts to get powerline fonts"
brew tap homebrew/cask-fonts
brew install font-hack-nerd-font

echo "Setup iterm2 to get powerline fonts"
brew install iterm2

echo "Setup powerlevel10k for theme"
brew install romkatv/powerlevel10k/powerlevel10k

# echo "Configure powerlevel10k"
# p10k configure

#set default python
pyenv install 3.8.3
pyenv rehash
pyenv global 3.8.3

echo "Setup pip"
which -s pip
if [[ $? != 0 ]] ; then
    echo "Installing pip"
    curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
    python get-pip.py
else
    echo "Upgrading pip"
    pip install --upgrade pip
fi

echo "Setup tfenv"
brew install tfenv

echo "Setup version pinned terraform using tfenv"
tfenv install 0.14.9
tfenv use 0.14.9

echo "Setup Mac App Store Commandline Interface"
brew install mas

echo "Install Slack from App Store"
mas lucky Slack

echo "Install Termius from App Store"
mas lucky Termius

echo "Install Magnet from App Store"
mas lucky Magnet

echo "Install Fantastical from App Store"
mas lucky Fantastical

echo "Install Bitwaden from App Store"
mas lucky Bitwarden

echo "Install Jetbrains Toolbox"
brew install --cask jetbrains-toolbox

echo "Install Arq Backup"
brew install --cask arq

echo "Install MacUpdater"
brew install --cask macupdater

echo "Install Authy"
brew install --cask authy

echo "Install Bitwarden"
brew install --cask bitwarden

echo "Install Brave"
brew install --cask brave-browser