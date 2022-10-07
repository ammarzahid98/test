#!/bin/bash



DIR_TARGET=/home/pi/SmartPowerManagerSlave
RPI_USER_NAME="pi@"
SLASH_VAR="/"

RED="\e[31m"
GREEN="\e[32m"
YELLOW="\e[33m"
ENDCOLOR="\e[0m"
BLUE="\e[36m"
WHITE="\e[37m"


clear


echo ""
echo "#######################################"
echo "||                                   ||"
echo "||   SMART POWER MANAGER DEPLOYER    ||"
echo "||        100% USER FRIENDLY         ||"
echo "||                                   ||"
echo "#######################################"
echo ""
echo ""
echo -e "${RED}WARNING: Before we start, be sure: ${ENDCOLOR}"
echo ""
echo -e "${RED}->${ENDCOLOR}${ENDCOLOR}${YELLOW}You have enabled ssh on the 1 or 2 Rasperry  ${ENDCOLOR}"
echo -e "${RED}->${ENDCOLOR}${YELLOW}You know there IP address${ENDCOLOR}"
echo -e "${RED}->${ENDCOLOR}${YELLOW}Your raspberry are well connected to the internet (only required during the installation)${ENDCOLOR}"
echo -e "${RED}->${ENDCOLOR}${YELLOW}You have not installed Smart Power Manager already (otherwise you will lose device list and scenario list)${ENDCOLOR}"
echo ""


read -r -p "I have read all the instruction and I want to continue ? [y/N] " response
echo ""

echo -e "${YELLOW}Enter Raspberry Pi IP adress (SECOND board) : ${ENDCOLOR}"
read RPI_TARGET
echo ""



case "$response" in
    [yY][eE][sS]|[yY]) 


		
		ssh $RPI_USER_NAME$RPI_TARGET mkdir -p $DIR_TARGET &&


		#-----create folder-------
		echo -e "${WHITE}Creating following directory on RPI: $DIR_TARGET ${ENDCOLOR}" &&
		echo "" &&

		#------copy file------
		rsync -r ./SmartPowerManagerSlave/WebServeur $RPI_USER_NAME$RPI_TARGET:$DIR_TARGET --progress &&

		echo -e "" &&
		echo -e "" &&

		echo -e "${RED}Files were copied sucessfully${ENDCOLOR}"

        ;;
esac



ssh $RPI_USER_NAME$RPI_TARGET 'bash -s' <<ENDSSH
  # The following commands run on the remote host
  
  sudo su 
	echo -e "" 
	echo -e "${RED}Installing pip, cron, flask and all python packages needed${ENDCOLOR}" 
	sudo apt-get -y update 
  sudo apt-get -y install cron 
  sudo apt-get -y install pip3 
  sudo pip3 install --upgrade Flask 
  sudo pip3 install -r $DIR_TARGET/WebServeur/requirements.txt 
  crontab -l | { cat; echo "@reboot cd /home/pi/SmartPowerManagerSlave/WebServeur/ ; sudo bash start.sh"; } | crontab - 
  crontab -l | { cat; echo "@reboot cd /home/pi/SmartPowerManagerSlave/WebServeur/ ; sudo bash start.sh"; } | crontab - 
  sudo reboot

ENDSSH



