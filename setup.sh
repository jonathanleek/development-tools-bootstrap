#!/bin/zsh
# setup development environment
# os x catalina 10.15
# michael orlando

echo "Setup.sh requires xcode to be installed"

echo "Setup homebrew"
which -s brew
if [[ $? != 0 ]] ; then
    echo "Installing homebrew"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install.sh)"
else
    echo "Updating homebrew"
    brew update
    brew upgrade
    brew cleanup
fi

echo "Setup ohmyzsh"
/bin/bash -c "$(curl -fsSL https://raw.github.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"

echo "Setup nvm (node version manager)"
which -s nvm
if [[ $? != 0 ]] ; then
    echo "Installing nvm"
    curl -o- https://raw.githubusercontent.com/creationix/nvm/v0.33.0/install.sh | bash
    export NVM_DIR="/Users/michaelorlando/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
else
    echo "nvm exists, no updating or installing"
fi

echo "Setup and use LTS version of nodejs using nvm"
nvm install --lts
nvm use --lts

echo "Setup amazon web services aws cli version 2"
brew install awscli@2

echo "Setup pyenv to manage system and context python versions"
brew install pyenv

echo "Setup jenv to manage SYSTEM java versions"
brew install jenv

echo "Setup SDKMan for Java JVMs"
which -s sdk
if [[ $? != 0 ]] ; then
    echo "Installing SDKMan"
    curl -s "https://get.sdkman.io" | zsh
    source ~/.sdkman/bin/sdkman-init.sh
else
    echo "SDKMan exists, no updating or installing"
fi

brew install kubectl

brew tap weaveworks/tap
brew install weaveworks/tap/eksctl

brew install helm@3

brew cask install lens

brew install jq

echo "Setup nerd fonts to get powerline fonts"
brew tap homebrew/cask-fonts
brew cask install font-hack-nerd-font

echo "Setup iterm2 to get powerline fonts"
brew cask install iterm2

echo "Setup powerlevel10k for theme"
brew install romkatv/powerlevel10k/powerlevel10k

# echo "Configure powerlevel10k"
# p10k configure

#set default python
pyenv install 3.8.3
pyenv global 3.8.3

echo "Setup pip"
which -s pip
if [[ $? != 0 ]] ; then
    echo "Installing pip"
    curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
else
    echo "Upgrading pip"
    pip install --upgrade pip
fi

echo "Setup terraform"
brew install terraform

echo "Setup netdata"
brew install netdata
brew services start netdata

echo "Setup minikube"
brew install minikube

echo "Setup glances"
pip install glances

echo "Setup fluxctl"
brew install fluxctl

echo "Setup Go"
brew install go
