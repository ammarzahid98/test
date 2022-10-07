
#-----------------------------------------#
#      Main relay Board Server Script     # 
#-----------------------------------------#

from ast import arg
from concurrent.futures import thread
import ipaddress
import os
from ssl import SSL_ERROR_EOF
from termios import IXOFF
from flask import Flask, render_template, abort, url_for, json, jsonify, request, send_file, redirect
import RPi.GPIO as GPIO            # import RPi.GPIO module  
from time import sleep   
import time      
import json
from flask_socketio import SocketIO
from ping3 import ping
import threading
import iptools
import requests
import socket
import fileinput
from werkzeug.utils import secure_filename
from zipfile import ZipFile
from multiprocessing import Pool
import multiprocessing
import subprocess
import paramiko

UPLOAD_FOLDER = '/home/pi/SmartPowerManager/WebServeur'
ALLOWED_EXTENSIONS = {'txt'}

GPIO.setmode(GPIO.BOARD)             
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
socketio = SocketIO(app, async_handlers=True, pingTimeout=900)


GPIODeviceListInOrder = []

#------------------------------------------------------------------------------------
#   Get timout value (it's the timout for all "main to second board request")
#------------------------------------------------------------------------------------

SettingTimoutValue = 2
filename='settings.txt'
with open(filename,'r+') as file:
    file_data = json.load(file)
    SettingTimoutValue = float(file_data["settings"][0]["secondBoardTimout"])

#------------------------------------------------------------------------------------
#   Upload/dowload device and scenario file
#------------------------------------------------------------------------------------
@app.route('/download_device_file')
def download_device_file():

    path = "device_list.txt"

    return send_file(path, as_attachment=True)

@app.route('/download_both')
def download_both():

    path = "settings_backup_power_manager.zip"
    zipObj = ZipFile(path, 'w')
    zipObj.write('scenario.txt')
    zipObj.write('device_list.txt')
    zipObj.close()

    return send_file(path, as_attachment=True)

@app.route('/download_scenario_file')
def download_scenario_file():

    path = "scenario.txt"

    return send_file(path, as_attachment=True)

@app.route('/uploader', methods = ['GET', 'POST'])
def upload_file():
   if request.method == 'POST':
    f = request.files['file']
    f.save(secure_filename(f.filename))

    file_name = "settings_backup_power_manager.zip"
    
    if(f.filename == file_name):     
        with ZipFile(file_name, 'r') as zip:
            zip.printdir()
            zip.extractall()
        os.remove(file_name)


    return redirect(url_for('index'))

#------------------------------------------------------------------------------------
#   Add a new device to 'device_list.txt' with "new_data" the device to add
#------------------------------------------------------------------------------------
def write_json(new_data, filename='device_list.txt'):

    with open(filename,'r+') as file:
        file_data = json.load(file)
        file_data["devices"].append(new_data)
        file.seek(0)
        json.dump(file_data, file, indent = 4)
        file.close()


#------------------------------------------------------------------------------------
#   Change IP in the ip json file settings
#------------------------------------------------------------------------------------
def write_json_IP_settings(settings_value,settings_name, filename='settings.txt'):

    filename='settings.txt'
    with open(filename,'r+') as file:
        file_data = json.load(file)
        for i in range (0, len(file_data["settings"])):
            file_data["settings"][i][str(settings_name)]=settings_value

        json_object = json.dumps(file_data, indent = 4) 
        print(json_object)
        file = open(filename,'w')
        file.write(json_object)
        file.close()   
        
#-----------------------------------------------------------------------------------
#   Remove a device of 'device_list.txt' (use the device name to find the device to remove)
#-----------------------------------------------------------------------------------    
def del_json(name_device): 

    filename='device_list.txt'
    with open(filename,'r+') as file:
        file_data = json.load(file)
        for i in range (0, len(file_data["devices"])):
                if(str(file_data["devices"][i]["device_name"]) == str(name_device)):
                        print(file_data["devices"][i])
                        file_data["devices"].pop(i)
                        break
        print(file_data)
        json_object = json.dumps(file_data, indent = 4) 
        print(json_object)
        file = open(filename,'w')
        file.write(json_object)
        file.close()

#-----------------------------------------------------------------------------------
#  Check if a device is remote (connected to second board) or not (use the GPIO Pin to find the device to remove)
#-----------------------------------------------------------------------------------   
def IsdeviceRemote(gpiopin):
    
    filename='device_list.txt'
    with open(filename,'r+') as file:
        file_data = json.load(file)
        for i in range (0, len(file_data["devices"])):
                if(int(file_data["devices"][i]["GPIO_pin"]) == int(gpiopin)):
                        dev_type = file_data["devices"][i]["device_type"]
                        file.close()
                        if(dev_type == "remote_dev"):
                            return True
                        elif(dev_type == "not_remote_dev"):
                            return False                            
                        else:
                            return("ERROR : MISSING TYPE (REMOTE OR NOT REMOTE) FOR DEVICE REQUIRED")

        
#-----------------------------------------------------------------------------------
#  Get SECOND board ip value from settings.txt
#-----------------------------------------------------------------------------------   
def getSecondBoardIpValue():
    
    filename='settings.txt'
    with open(filename,'r+') as file:
        file_data = json.load(file)
        file.close()
        return file_data["settings"][0]["second_board_ip"]           

#-----------------------------------------------------------------------------------
#  Get THIRD board ip value from settings.txt
#-----------------------------------------------------------------------------------   
def getThirdBoardIpValue():
    
    filename='settings.txt'
    with open(filename,'r+') as file:
        file_data = json.load(file)
        file.close()
        return file_data["settings"][0]["third_board_ip"]          

#-----------------------------------------------------------------------------------
#   Generate a correspondancy list beetween the button "ON/OFF" id (= index of the list) and the GPIO PIN (include the device type)
#-----------------------------------------------------------------------------------      
def generateCorrepondancyListBeetweenGPIOAndButtonONOffID():
    
    GPIODeviceListInOrder.clear()
    filename='device_list.txt'
    with open(filename,'r+') as file:
        file_data = json.load(file)
        file.close()
        for i in range (0, len(file_data["devices"])):
                GPIODeviceListInOrder.append(str(file_data["devices"][i]["GPIO_pin"])+(str(file_data["devices"][i]["device_type"])))

    print("-------------------")
    print(GPIODeviceListInOrder)
                
#-----------------------------------------------------------------------------------
#   Send a Socket Message, for exemple to say hello, we write : handle_message("hello")
#-----------------------------------------------------------------------------------      
@socketio.on('message', namespace='/ping_status')
def handle_message(message):
    socketio.send(message)

#-----------------------------------------------------------------------------------
#   Put GPIO "GPIONumber" on the second relay bord ON (3.3V)
#-----------------------------------------------------------------------------------      
def putRemoteGpio_HIGH(GPIONumber):
    try:
        url = 'http://'+getSecondBoardIpValue()+'/SET_REMOTE_GPIO_ON/'
        url=url+str(GPIONumber)
        x = requests.post(url, timeout=(SettingTimoutValue, SettingTimoutValue))
        return str(x.text)
    except Exception:
        pass

#-----------------------------------------------------------------------------------
#   Put GPIO "GPIONumber" on the second relay bord OFF (0V)
#-----------------------------------------------------------------------------------      
def putRemoteGpio_LOW(GPIONumber):
    
    try:
        url = 'http://'+getSecondBoardIpValue()+'/SET_REMOTE_GPIO_OFF/'
        url=url+str(GPIONumber)
        print(url)
        x = requests.post(url, timeout=(SettingTimoutValue, SettingTimoutValue))
        return str(x.text)
    except Exception:
        pass
 
#-----------------------------------------------------------------------------------
#   get remote GPIO state number GPIONumber
#------------------------------------------------------------------------------------        
def getRemoteGpio_STATE(GPIONumber):
    
    try:
        url = 'http://'+getSecondBoardIpValue()+'/GET_REMOTE_GPIO_STATE/'
        url=url+str(GPIONumber)
        print(url)
        x = requests.post(url, timeout=(SettingTimoutValue, SettingTimoutValue))
        return str(x.text)
    except Exception:
        return str("3")
        pass

#-----------------------------------------------------------------------------------
#   Put GPIO "GPIONumber" on the third relay bord ON (3.3V)
#-----------------------------------------------------------------------------------      
def putRemoteGpio3_HIGH(GPIONumber):
    try:
        url = 'http://'+getThirdBoardIpValue()+'/SET_REMOTE_GPIO_ON/'
        url=url+str(GPIONumber)
        x = requests.post(url, timeout=(SettingTimoutValue, SettingTimoutValue))
        return str(x.text)
    except Exception:
        pass

#-----------------------------------------------------------------------------------
#   Put GPIO "GPIONumber" on the third relay bord OFF (0V)
#-----------------------------------------------------------------------------------      
def putRemoteGpio3_LOW(GPIONumber):
    
    try:
        url = 'http://'+getThirdBoardIpValue()+'/SET_REMOTE_GPIO_OFF/'
        url=url+str(GPIONumber)
        print(url)
        x = requests.post(url, timeout=(SettingTimoutValue, SettingTimoutValue))
        return str(x.text)
    except Exception:
        pass

#-----------------------------------------------------------------------------------
#   get remote GPIO state number GPIONumber
#------------------------------------------------------------------------------------        
def getRemoteGpio3_STATE(GPIONumber):
    
    try:
        url = 'http://'+getThirdBoardIpValue()+'/GET_REMOTE_GPIO_STATE/'
        url=url+str(GPIONumber)
        print(url)
        x = requests.post(url, timeout=(SettingTimoutValue, SettingTimoutValue))
        return str(x.text)
    except Exception:
        return str("3")
        pass

#-----------------------------------------------------------------------------------
#   ping Ip adress "host" return a float (ping latency) if sucess 
#------------------------------------------------------------------------------------    
def myping(host):
    resp = ping(host)
    return resp

#-----------------------------------------------------------------------------------
#   Generate IP list with all the device's IP in order
#------------------------------------------------------------------------------------        
IP_list = []
PING_status = ""

def fill_ip_list():
    
    IP_list.clear()
    filename='device_list.txt'
    with open(filename,'r+') as file:
        file_data = json.load(file)
        for i in range (0, len(file_data["devices"])):
                IP_list.append(file_data["devices"][i]["IP_adress"])                   
        file.close()
        print(IP_list)   
#-----------------------------------------------------------------------------------
#  Verify if IPV4 adress is valid
#------------------------------------------------------------------------------------   

def is_valid_ipv4_address(address):
    try:
        socket.inet_pton(socket.AF_INET, address)
    except AttributeError:  # no inet_pton here, sorry
        try:
            socket.inet_aton(address)
        except socket.error:
            return False
        return address.count('.') == 3
    except socket.error:  # not a valid address
        return False
    return True

#-----------------------------------------------------------------------------------
#  Ping Thread : ping all device every 1 second
#------------------------------------------------------------------------------------   
def pingStatus(y):

    #for y in range(0, len(IP_list)):
        #print("ping !")        
        #if the device has an IP
        if(is_valid_ipv4_address(IP_list[y])):
            ping_cache = myping(IP_list[y])
            if(type(ping_cache) is float):
                PING_status=str(y)+"TRUE"
            else:
                PING_status=str(y)+"FALSE"
        #if the device has no IP
        else:
            PING_status=str(y)+"No_IP"               
            
        time.sleep(0.5)
        handle_message(PING_status)   
    #print(PING_status)
    #threading.Timer(1, pingStatus).start()
        return PING_status[y]

def pingStatusThread():
    #print("test")

    myThread = []
    for y in range(0, len(IP_list)):
        t=threading.Thread(target=pingStatus, args=(y,))
        myThread.append(t)
        t.start()

    for t in myThread:
        t.join()

    threading.Timer(1,pingStatusThread).start()

#------------------------------------------------------------------------------------
#SSH Thread
#------------------------------------------------------------------------------------
def sendSSHCommand (ipadress) :
    print("Shutting down device using SSH...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=ipadress, port=22, username='pi', password='raspberry')
                    
    stdin, stdout, stderr = client.exec_command('sudo poweroff')

    # Get return code from command (0 is default for success)
    print(f'Return code: {stdout.channel.recv_exit_status()}')

    # Because they are file objects, they need to be closed
    stdin.close()
    stdout.close()
    stderr.close()

    # Close the client itself
    client.close()
    ipadress = ipadress.replace(ipadress," ")
    print("Device is turned off, safe to cut power supply !")
    time.sleep(20)

def SSH(y):
    if(IP_list[y] != ""):
        try :
            sendSSHCommand(IP_list[y])
        except Exception :
            pass

def SSHThread():
    myThread2 = []
    for y in range(0,len(IP_list)):
        t2=threading.Thread(target=SSH, args=(y,))
        myThread2.append(t2)
        t2.start()

    for t2 in myThread2:
        t2.join()  

#-----------------------------------------------------------------------------------
#  function launched when user arrived on home page
#------------------------------------------------------------------------------------  
@app.route("/", methods=['GET','POST'])
@app.route("/index/", methods=['GET','POST'])
def index():

    #for line in fileinput.FileInput("scenario.txt",inplace=1):
    #    if line.rstrip():
    #        print(line)

    
    generateCorrepondancyListBeetweenGPIOAndButtonONOffID()
    fill_ip_list()

    print("#########################")
    print(GPIODeviceListInOrder)
    pingStatusThread()
    
    data = ""
    with open('device_list.txt', 'r') as file:
        data = file.read().replace('\n', '')  
        file.close()
    data_scenar = ""
    with open('scenario.txt', 'r') as file:
        data_scenar = file.read().replace('\n', '{}')   
        file.close()
        #print(data_scenar)
    return render_template('index.html', name=data, datascenario=data_scenar, secondBoardIpSettings=getSecondBoardIpValue(), thirdBoardIpSettings=getThirdBoardIpValue(), scenarioOnboot=str(getbootsettings()))
 
 

#-----------------------------------------------------------------------------------
#  Get a device name with his GPIO Pin and his status : remote or not (parameter : gpio=devicetype
#-----------------------------------------------------------------------------------   
@app.route('/get_device_name/<gpiopinandtype>', methods=['POST','GET'])
@app.route('/scenario/get_device_name/<gpiopinandtype>', methods=['POST','GET'])
def IsdeviceRemote(gpiopinandtype):
    
    dev_name=""
    filename='device_list.txt'
    with open(filename,'r+') as file:
        file_data = json.load(file)
        file.close()       
        gpiopinandtype = gpiopinandtype.split("=")
        
        GPIOnumber = gpiopinandtype[1]
        DeviceType = gpiopinandtype[0]
        
        for i in range (0, len(file_data["devices"])):
            
                if(int(file_data["devices"][i]["GPIO_pin"]) == int(GPIOnumber) and (file_data["devices"][i]["device_type"]) == (DeviceType)):
                    
                        dev_name = file_data["devices"][i]["device_name"]
                    
        print(dev_name)
        
    return jsonify(dev_name)


#-----------------------------------------------------------------------------------
#  verifiy If Ad evice name Exist
#-----------------------------------------------------------------------------------   
@app.route('/is_this_device_name_exist/<device_name>', methods=['POST','GET'])
@app.route('/newdevice/is_this_device_name_exist/<device_name>', methods=['POST','GET'])
def is_this_device_name_exist(device_name):
    
    print("received following device name : "+str(device_name))
    dev_name=""
    filename='device_list.txt'
    returnState = "FALSE"
    with open(filename,'r+') as file:
        file_data = json.load(file) 
        file.close()   
        for i in range (0, len(file_data["devices"])):           
            if(str(file_data["devices"][i]["device_name"]) == str(device_name)):                   
                print("FOUND THIS DEVICE IN FILE : "+str(device_name))
                returnState = "TRUE"
        return jsonify(returnState)

#-----------------------------------------------------------------------------------
#  verifiy If a gpio is already used : as parameter "remoteornotvalue"+"="+"GPIO"
#-----------------------------------------------------------------------------------   
@app.route('/is_this_gpio_is_used/<gpio_param>', methods=['POST','GET'])
@app.route('/newdevice/is_this_gpio_is_used/<gpio_param>', methods=['POST','GET'])
def is_this_gpio_is_used(gpio_param):


    IsgpioUsed="FALSE"
    filename='device_list.txt'
    with open(filename,'r+') as file:
        file_data = json.load(file)
        file.close()
        gpiopinandtypeCheck = gpio_param.split("=")
        
        GPIOnumber = gpiopinandtypeCheck[1]
        DeviceType = gpiopinandtypeCheck[0]
        
        for i in range (0, len(file_data["devices"])):
            
                if(int(file_data["devices"][i]["GPIO_pin"]) == int(GPIOnumber) and (file_data["devices"][i]["device_type"]) == (DeviceType)):
                    
                    IsgpioUsed="TRUE"
                    dev_name = file_data["devices"][i]["device_name"]
                
    return jsonify(IsgpioUsed)
                                   
                                                
#-----------------------------------------------------------------------------------
#  Function activated when a button ON/OFF is pushed
#------------------------------------------------------------------------------------  
@app.route('/ON_OFF_GPIO/<gpiopinandid>')
@app.route("/index/ON_OFF_GPIO/<gpiopinandid>")
def ON_OFF_GPIO(gpiopinandid):

    x = gpiopinandid.split(" ")
    gpiopin=x[0]
    id=int(x[1])

    filename='device_list.txt'
    with open(filename) as file:
        file_data = json.load(file)
        file.close()
        ipadress = file_data["devices"][id]["IP_adress"]

    if("rm_dev" in gpiopin):
        gpiopin = gpiopin.replace("rm_dev","")
        print('Remote GPIO called : '+str(gpiopin))
        GPIO.setup(int(gpiopin), GPIO.OUT)
        print("--------------getRemoteGpio_STATE-------------"+str(type(getRemoteGpio_STATE(gpiopin)))+"   "+str(getRemoteGpio_STATE(gpiopin)))              
        if int(getRemoteGpio_STATE(gpiopin))==1:
            print("📒"+gpiopin+" put LOW SLAVE")
            putRemoteGpio_LOW(int(gpiopin))    
        elif int(getRemoteGpio_STATE(gpiopin))==0:
            if (ipadress != " ") :
                try :
                    sendSSHCommand(ipadress)
                except  Exception :
                    pass
            print("📒"+gpiopin+" put HIGH SLAVE")
            putRemoteGpio_HIGH(int(gpiopin))
        else:
            print("ECHEC : la valeur retournée par l'esclave est incorrecte")
        stringToreturn = str(getRemoteGpio_STATE(gpiopin))
        
    if("rm_DP" in gpiopin):
        gpiopin = gpiopin.replace("rm_DP","")
        print('Remote GPIO called : '+str(gpiopin))
        GPIO.setup(int(gpiopin), GPIO.OUT)
        print("--------------getRemoteGpio3_STATE-------------"+str(type(getRemoteGpio3_STATE(gpiopin)))+"   "+str(getRemoteGpio3_STATE(gpiopin)))              
        if int(getRemoteGpio3_STATE(gpiopin))==1:
            print("📒"+gpiopin+" put LOW SLAVE 2")
            putRemoteGpio3_LOW(int(gpiopin))    
        elif int(getRemoteGpio3_STATE(gpiopin))==0:
            if (ipadress != " ") :
                try :
                    sendSSHCommand(ipadress)
                except  Exception :
                    pass
            print("📒"+gpiopin+" put HIGH SLAVE 2")
            putRemoteGpio3_HIGH(int(gpiopin))
        else:
            print("ECHEC : la valeur retournée par l'esclave est incorrecte")
        stringToreturn = str(getRemoteGpio3_STATE(gpiopin))
        
    if("not_dev_rm" in gpiopin):
        gpiopin = gpiopin.replace("not_dev_rm","")
        print('GPIO called : '+str(gpiopin))
        GPIO.setup(int(gpiopin), GPIO.OUT)              
        if GPIO.input(int(gpiopin)):
            GPIO.output(int(gpiopin),GPIO.LOW)
            print("📒"+gpiopin+" put LOW MAIN ")
        else:
            if (ipadress != " ") :
                try :
                    sendSSHCommand(ipadress)
                except  Exception :
                    pass 
            GPIO.output(int(gpiopin),GPIO.HIGH)
            print("📒"+gpiopin+" put HIGH MAIN")

        stringToreturn = str(GPIO.input(int(gpiopin)))

    return jsonify(stringToreturn)
    
#-----------------------------------------------------------------------------------
#   Function reboot GPIO pin (received gpiopin_reboottime as parameter)
#------------------------------------------------------------------------------------     
@app.route('/reboot/<gpiopinandreboottome>')
@app.route("/index/reboot/<gpiopinandreboottome>")
def reboot(gpiopinandreboottome):
    
    x = gpiopinandreboottome.split(" ")
    gpiopin = x[0]
    reboottime = x[1]
    id = x[2]
    id = id.replace("reb","")
    id = int(id)

    filename='device_list.txt'
    with open(filename) as file:
        file_data = json.load(file)
        file.close()
        ipadress = file_data["devices"][id]["IP_adress"]
    print(ipadress)

    if("rm_dev" in gpiopin):
        gpiopin = gpiopin.replace("rm_dev","")
        print("rebooting a device, pin : "+gpiopin+" reboot time : "+reboottime )
        if int(getRemoteGpio_STATE(gpiopin))==0:
            if (ipadress != "") :
                try :
                    sendSSHCommand(ipadress)
                except  Exception :
                    time.sleep(20.5)
                    pass
            putRemoteGpio_HIGH(int(gpiopin))
            time.sleep(int(reboottime))
            putRemoteGpio_LOW(int(gpiopin))
        else :
            putRemoteGpio_LOW(int(gpiopin))
        
    if("rm_DP" in gpiopin):
        gpiopin = gpiopin.replace("rm_DP","")
        print("rebooting a device, pin : "+gpiopin+" reboot time : "+reboottime )
        if int(getRemoteGpio3_STATE(gpiopin))==0:
            if (ipadress != "") :
                try :
                    sendSSHCommand(ipadress)
                except  Exception :
                    time.sleep(20.5)
                    pass
            putRemoteGpio3_HIGH(int(gpiopin))
            time.sleep(int(reboottime))
            putRemoteGpio3_LOW(int(gpiopin)) 
        else :
            putRemoteGpio3_LOW(int(gpiopin))  
            
    if("not_dev_rm" in gpiopin):
        gpiopin = gpiopin.replace("not_dev_rm","")

        print("rebooting a device, pin : "+gpiopin+" reboot time : "+reboottime )
        GPIO.setup(int(gpiopin), GPIO.OUT)
        if GPIO.input(int(gpiopin)):
            GPIO.output(int(gpiopin),GPIO.LOW)
        else :
            if (ipadress != "") :
                try :
                    sendSSHCommand(ipadress)
                except  Exception :
                    time.sleep(20.5)
                    pass 
            GPIO.output(int(gpiopin),GPIO.HIGH)
            time.sleep(int(reboottime))
            GPIO.output(int(gpiopin),GPIO.LOW)         

    return jsonify("rebootdone")
    
#-----------------------------------------------------------------------------------
#   remove a device (with GPIO pin)
#------------------------------------------------------------------------------------ 
@app.route('/remove_device/<name_device>')
@app.route("/index/remove_device/<name_device>")
def remove_device(name_device):

    print("the device's gpio pin to remove is : " + name_device);
    del_json(str(name_device))
    
    return "null"
    
#-----------------------------------------------------------------------------------
#   remove a scenario (with scenario number)
#------------------------------------------------------------------------------------     
@app.route('/remove_scenario/<nb_scenar>')
@app.route("/index/remove_scenario/<nb_scenar>")
def remove_scenario(nb_scenar):

    print("THE SCENARIO to remove is : " + nb_scenar);
    
    with open("scenario.txt", "r") as f:
        lines = f.readlines()
        f.close()
        print(lines)
        lines.pop(int(nb_scenar.replace("rm_scenario","")));
        print(lines)
    with open("scenario.txt", "w") as f:
        for line in lines:
            f.write(line) 
        f.close()     
    return "null"

#-----------------------------------------------------------------------------------
#   remove a scenario with his line before writing his new version
#------------------------------------------------------------------------------------    
@app.route("/erase_a_scenario/<valueSelected>", methods=['POST','GET'])
@app.route("/scenario/erase_a_scenario/<valueSelected>", methods=['POST','GET'])
def erase_a_scenario(valueSelected):
        
    with open("scenario.txt", "r") as f:
        lines = f.readlines()
        f.close()
        print(lines)
        lines.pop(int(valueSelected.replace("erase_this","")));
        print(lines)

    with open("scenario.txt", "w") as f:
        for line in lines:
            f.write(line)   
        f.close()   
    

    return "null"
 
#-----------------------------------------------------------------------------------
#   display scenario.html page when called
#------------------------------------------------------------------------------------    
@app.route("/scenario/", methods=['POST'])
def move_forward():
    
    data = ""
    with open('device_list.txt', 'r') as file:
        data = file.read().replace('\n', '')  
        file.close()

    
    data_scenar = ""
    with open('scenario.txt', 'r') as file:
        data_scenar = file.read().replace('\n', 'B') 
        file.close()  
  
    return render_template('scenario.html', name=data, datascenario=data_scenar);
 
#-----------------------------------------------------------------------------------
#   get a line of scenario txt
#------------------------------------------------------------------------------------    
@app.route("/get_a_scenario/<valueSelected>", methods=['POST','GET'])
@app.route("/scenario/get_a_scenario/<valueSelected>", methods=['POST','GET'])
def get_a_scenario(valueSelected):
    
    print(valueSelected)
    
    #open scenario file
    data_scenar = ""
    with open('scenario.txt', 'r') as file:
        data_scenar = file.readlines()
        file.close()
   
    #get the "nbscenario" line (referencing to scenario selected)
    #nbscenario = nbscenario.replace("scenario","")
    newscenario = data_scenar[int(valueSelected)]
    print(newscenario)
    #newscenario = newscenario.split()
  
    return jsonify(newscenario)
        
#-----------------------------------------------------------------------------------
#   forward to new device page
#------------------------------------------------------------------------------------
@app.route("/newdevice/", methods=['POST'])
def newdevice():
    
    data = ""
    with open('device_list.txt', 'r') as file:
        data = file.read().replace('\n', '') 
        file.close() 

    return render_template('add.html', name=data);
    
#-----------------------------------------------------------------------------------
#   Launch a scenario
#------------------------------------------------------------------------------------ 
@app.route('/index/launch_scenario/<nbscenario>')
@app.route('/launch_scenario/<nbscenario>')
def launch_scenario(nbscenario):

    
    #open scenario file
    data_scenar = ""
    with open('scenario.txt', 'r') as file:
        data_scenar = file.readlines()
        file.close()
    #get the "nbscenario" line (referencing to scenario selected)
    nbscenario = nbscenario.replace("scenario","")
    newscenario = data_scenar[int(nbscenario)]
    print(newscenario)
    if ("OFF" in newscenario):
        SSHThread()
    #new scenario is the line of the scenario we execute 
    newscenario = newscenario.split()
    for i in range(1,len(newscenario)):
        #time.sleep(0.3)
        #element est un TEMPS 
        new_string = newscenario[i].replace("wait", "")
        #si l'element du tableau est un temps
        if(new_string != newscenario[i]):
            time.sleep(int(new_string))
        
        #element n'est PAS un TEMPS
        else:
            #Si le device à commander EST REMOTE
            if("rm_dev" in new_string):
                new_string = new_string.replace("rm_dev","")
                if("ON" in new_string):
                    new_string = new_string.replace("ON", "")
                    putRemoteGpio_LOW(int(new_string))
                    if(getRemoteGpio_STATE(int(new_string))!="3"):
                        handle_message("GPIO_ON:"+str(GPIODeviceListInOrder.index(str(new_string+"rm_dev"))))  
                if("OFF" in new_string):
                    new_string = new_string.replace("OFF", "")
                    putRemoteGpio_HIGH(int(new_string))
                    if(getRemoteGpio_STATE(int(new_string))!="3"):
                        handle_message("GPIO_OFF:"+str(GPIODeviceListInOrder.index(str(new_string+"rm_dev"))))

            #Si le device à commander EST REMOTE (power manager3)
            if("rm_DP" in new_string):
                new_string = new_string.replace("rm_DP","")
                if("ON" in new_string):
                    new_string = new_string.replace("ON", "")
                    putRemoteGpio3_LOW(int(new_string))
                    if(getRemoteGpio3_STATE(int(new_string))!="3"):
                        handle_message("GPIO_ON:"+str(GPIODeviceListInOrder.index(str(new_string+"rm_DP"))))  
                if("OFF" in new_string):
                    new_string = new_string.replace("OFF", "")
                    putRemoteGpio3_HIGH(int(new_string))
                    if(getRemoteGpio3_STATE(int(new_string))!="3"):
                        handle_message("GPIO_OFF:"+str(GPIODeviceListInOrder.index(str(new_string+"rm_DP"))))
            
            #Si le device à commander n'est PAS REMOTE
            if("not_dev_rm" in new_string):
                
                new_string = new_string.replace("not_dev_rm","")
                #mettre le device 
                new_string_state = new_string.replace("ON", "")
                if(new_string_state != new_string):
                    #changer la couleur du boutton ON/OFF en rouge sur l'interface
                    GPIO.output(int(new_string_state),GPIO.LOW)
                    handle_message("GPIO_ON:"+str(GPIODeviceListInOrder.index(str(new_string_state+"not_dev_rm"))))
                new_string_state = new_string.replace("OFF", "")
                if(new_string_state != new_string):
                    #set pin off                
                    GPIO.output(int(new_string_state),GPIO.HIGH)
                    handle_message("GPIO_OFF:"+str(GPIODeviceListInOrder.index(str(new_string_state+"not_dev_rm"))))

    #time.sleep(3)   
    #handle_message("reloadWebPage")
    file.close()
    return "null"
    
#-----------------------------------------------------------------------------------
#   Save a new scenario in scenario.txt
#------------------------------------------------------------------------------------ 
@app.route('/scenario/save_scenario/<newscenario>')
def save_scenario(newscenario):
    
    print(newscenario)
    file1 = open('scenario.txt', 'a')
    file1.write("\n"+newscenario)
    file1.close()

    return "null"

#-----------------------------------------------------------------------------------
#   Add a device to device.txt
#------------------------------------------------------------------------------------  

def del_device_from_json(name_device): 

    filename='device_list.txt'
    with open(filename,'r+') as file:
        file_data = json.load(file)
        for i in range (0, len(file_data["devices"])):
                if(str(file_data["devices"][i]["device_name"]) == str(name_device)):
                        print(file_data["devices"][i])
                        file_data["devices"].pop(i)
                        break
        print(file_data)
        json_object = json.dumps(file_data, indent = 4) 
        print(json_object)
        file = open(filename,'w')
        file.write(json_object)
        file.close()

def isDeviceNameExist(device_name):
    
    filename='device_list.txt'
    returnState = False
    with open(filename,'r+') as file:
        file_data = json.load(file) 
        file.close()   
        for i in range (0, len(file_data["devices"])):           
            if(str(file_data["devices"][i]["device_name"]) == str(device_name)):                   
                print("FOUND THIS DEVICE IN FILE : "+str(device_name))
                returnState = True
        return returnState



@app.route('/resultat',methods = ['POST','GET'])
def resultat():

    if(isDeviceNameExist(request.form['dev_name'])):
        del_device_from_json(request.form['dev_name'])

    print("new_device...")
    dev_name = request.form['dev_name'] 
    dev_ip = request.form['dev_ip'] 
    pin_gpio = request.form['pin_gpio'] 
    reboot_time = request.form['reboot_time'] 
    #dev_type = request.form['dev_type'] 
    dev_type = request.form.get('dev_type')
    print(dev_name + dev_ip + pin_gpio +dev_type) 
    y = {"device_name": dev_name,"device_type": dev_type,"reboot_time": reboot_time,"GPIO_pin": pin_gpio,"IP_adress": dev_ip}       
    write_json(y) 


    data = ""
    with open('device_list.txt', 'r') as file:
        data = file.read().replace('\n', '')  
        file.close()

    return render_template('add.html', name=data);

#-----------------------------------------------------------------------------------
#   Save new Ip setting
#------------------------------------------------------------------------------------  

@app.route('/saveip',methods = ['POST'])
def save_ip():
    
    second_board_ip = request.form['secondBoardIpSettings'] 
    y = {"second_board_ip": second_board_ip}       
    write_json_IP_settings(second_board_ip, "second_board_ip")
    third_board_ip = request.form['thirdBoardIpSettings'] 
    y = {"third_board_ip": third_board_ip}       
    write_json_IP_settings(third_board_ip, "third_board_ip")
    return redirect(url_for('index'))

#-----------------------------------------------------------------------------------
#   Save new Boot settings
#------------------------------------------------------------------------------------  

@app.route('/saveboot',methods = ['POST'])
def saveboot():
    
    #open('scenario_on_boot_name.txt', 'w').close()
    #text_file = open("scenario_on_boot_name.txt", "w")
    #text_file.write(request.form.get('scenario_boot_selector'))#dev_type = request.form.get('dev_type')
    #text_file.close()

    scenarioOnBootSelected = request.form.get('scenario_boot_selector')

    y = {"scenario_on_boot": scenarioOnBootSelected}       
    write_json_IP_settings(scenarioOnBootSelected, "scenario_on_boot")

    return redirect(url_for('index'))

#-----------------------------------------------------------------------------------
#  Get Boot settings 
#------------------------------------------------------------------------------------  

def getbootsettings():

    filename='settings.txt'
    with open(filename,'r+') as file:
        file_data = json.load(file)
        file.close()

        print(str(file_data["settings"][0]["scenario_on_boot"]))
        return file_data["settings"][0]["scenario_on_boot"]  
    
#-----------------------------------------------------------------------------------
#   Get a GPIO status
#------------------------------------------------------------------------------------     
@app.route('/check_status/<gpiopin>')
@app.route('/index/check_status/<gpiopin>')
def check_status(gpiopin):
    
    if("rm_dev" in gpiopin):
        gpiopin = gpiopin.replace("rm_dev","")
                    
        stringToreturn = str(getRemoteGpio_STATE(gpiopin))
        print("GPIO required a startup "+str(stringToreturn))

    if("rm_DP" in gpiopin):
        gpiopin = gpiopin.replace("rm_DP","")
                    
        stringToreturn = str(getRemoteGpio3_STATE(gpiopin))
        print("GPIO required a startup "+str(stringToreturn))
         
            
    if("not_dev_rm" in gpiopin):
        gpiopin = gpiopin.replace("not_dev_rm","")

        GPIO.setup(int(gpiopin), GPIO.OUT)
        print('GPIO status required number : '+str(gpiopin))
        stringToreturn = str(GPIO.input(int(gpiopin)))
        print("GPIO required a startup "+str(stringToreturn))
 
    return jsonify(stringToreturn)

#-----------------------------------------------------------------------------------
#  Launching on boot scenario
#------------------------------------------------------------------------------------  

def launch_scenario_boot():

    boot_scenar_name = ""
    filename='settings.txt'
    with open(filename,'r+') as file:
        file_data = json.load(file)
        file.close()
        print(str(file_data["settings"][0]["scenario_on_boot"]))
        boot_scenar_name = file_data["settings"][0]["scenario_on_boot"]  

    line_number="not_found_boot_scenario_line_error"
    #open scenario file
    data_scenar = ""
    with open('scenario.txt', 'r') as file:
        data_scenar = file.readlines()
        file.close()

        for i in range(0, len(data_scenar)): 
            print(data_scenar[i])
            cache_split = data_scenar[i].split()
            print(cache_split)

            if(len(cache_split)>0):
                if(str(cache_split[0]).replace('\n',"") == boot_scenar_name):
                    line_number = i
                    break

    print(line_number)

    if(line_number!="not_found_boot_scenario_line_error"):

        #open scenario file
        data_scenar = ""
        with open('scenario.txt', 'r') as file:
            data_scenar = file.readlines()
            file.close()

        
        newscenario = data_scenar[int(line_number)]
        print(newscenario)
        #new scenario is the line of the scenario we execute 
        newscenario = newscenario.split()
     
        for i in range(1,len(newscenario)):

            #element est un TEMPS 
            new_string = newscenario[i].replace("wait", "")
            #si l'element du tableau est un temps
            if(new_string != newscenario[i]):
                time.sleep(int(new_string))
            
            #element n'est PAS un TEMPS
            else:
                
                #Si le device à commander EST REMOTE
                if("rm_dev" in new_string):
                    new_string = new_string.replace("rm_dev","")
                    if("ON" in new_string):
                        new_string = new_string.replace("ON", "")
                        print("GPIO_ON handle :>>"+str(new_string+"rm_dev"))
                        putRemoteGpio_LOW(int(new_string))
                        if(getRemoteGpio_STATE(int(new_string))!="3"):
                            handle_message("GPIO_ON:"+str(GPIODeviceListInOrder.index(str(new_string+"rm_dev")))) 
                        
                    if("OFF" in new_string):
                        new_string = new_string.replace("OFF", "")
                        print("GPIO_OFF handle :>>"+str(new_string+"rm_dev"))
                        putRemoteGpio_HIGH(int(new_string))
                        if(getRemoteGpio_STATE(int(new_string))!="3"):
                            handle_message("GPIO_OFF:"+str(GPIODeviceListInOrder.index(str(new_string+"rm_dev")))) 

                #Si le device à commander EST REMOTE (power manager3)
                if("rm_DP" in new_string):
                    new_string = new_string.replace("rm_DP","")
                    if("ON" in new_string):
                        new_string = new_string.replace("ON", "")
                        print("GPIO_ON handle :>>"+str(new_string+"rm_DP"))
                        putRemoteGpio3_LOW(int(new_string))
                        if(getRemoteGpio3_STATE(int(new_string))!="3"):
                            handle_message("GPIO_ON:"+str(GPIODeviceListInOrder.index(str(new_string+"rm_DP")))) 
                        
                    if("OFF" in new_string):
                        new_string = new_string.replace("OFF", "")
                        print("GPIO_OFF handle :>>"+str(new_string+"rm_DP"))
                        putRemoteGpio3_HIGH(int(new_string))
                        if(getRemoteGpio3_STATE(int(new_string))!="3"):
                            handle_message("GPIO_OFF:"+str(GPIODeviceListInOrder.index(str(new_string+"rm_DP")))) 
                                
                #Si le device à commander n'est PAS REMOTE
                if("not_dev_rm" in new_string):
                    
                    new_string = new_string.replace("not_dev_rm","")
                    #mettre le device 
                    new_string_state = new_string.replace("ON", "")
                    if(new_string_state != new_string):
                        #changer la couleur du boutton ON/OFF en rouge sur l'interface
                        GPIO.setup(int(new_string_state), GPIO.OUT)
                        print("GPIO_ON handle :>>"+str(new_string_state+"not_dev_rm"))
                        handle_message("GPIO_ON:"+str(GPIODeviceListInOrder.index(str(new_string_state+"not_dev_rm"))))
                        GPIO.output(int(new_string_state),GPIO.LOW)

                    new_string_state = new_string.replace("OFF", "")
                    if(new_string_state != new_string):
                        #set pin off       
                        GPIO.setup(int(new_string_state), GPIO.OUT)    
                        print("GPIO_OFF handle :>>"+str(new_string_state+"not_dev_rm"))
                        handle_message("GPIO_OFF:"+str(GPIODeviceListInOrder.index(str(new_string_state+"not_dev_rm"))))        
                        GPIO.output(int(new_string_state),GPIO.HIGH)

#-----------------------------------------------------------------------------------
#  flask setting
#------------------------------------------------------------------------------------     
if __name__ == '__main__':
    socketio.debug = True
    #app.run(host="0.0.0.0") 
    socketio.run(threaded=True, host="0.0.0.0", port=80)

#--------------------------------------------------------
#   Run ping status
#--------------------------------------------------------   



#----------------------------------------------------
# All gpio are by default at 3.3V (off state for relay)
#-----------------------------------------------------

def setIntialGpioState():
    
    filename='device_list.txt'
    with open(filename,'r+') as file:
        file_data = json.load(file)
        file.close()
        for i in range (0, len(file_data["devices"])):
            
            gpioNb = int(file_data["devices"][i]["GPIO_pin"])
            
            deviceTypeStr = str(file_data["devices"][i]["device_type"])

            if(deviceTypeStr=="not_dev_rm"):
                GPIO.setup(int(gpioNb), GPIO.OUT) 
                GPIO.output(int(gpioNb),GPIO.HIGH) 

            if(deviceTypeStr=="rm_dev"):
                putRemoteGpio_HIGH(int(gpioNb))
            
            if(deviceTypeStr=="rm_DP"):
                putRemoteGpio3_HIGH(int(gpioNb))


setIntialGpioState()

#----------------------------------------------------
# Thread for scenario on boot
#-----------------------------------------------------

class BootThread (threading.Thread):
        
    def __init__(self):                         
        threading.Thread.__init__(self)
        generateCorrepondancyListBeetweenGPIOAndButtonONOffID()
        #print("GPIO_ON:"+str(new_string.index(str("5not_dev_rm"))))
        

    def run(self):

        launch_scenario_boot()


bootThread = BootThread()
if not (bootThread.is_alive()):  

        bootThread.start()  




def sendSSHCommand (ipadress) :
    print("Shutting down device using SSH...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=ipadress, port=22, username='pi', password='raspberry')
                    
    stdin, stdout, stderr = client.exec_command('sudo poweroff')

    # Get return code from command (0 is default for success)
    print(f'Return code: {stdout.channel.recv_exit_status()}')

    # Because they are file objects, they need to be closed
    stdin.close()
    stdout.close()
    stderr.close()

    # Close the client itself
    client.close()
    ipadress = ipadress.replace(ipadress," ")
    print("Device is turned off, save to cut power supply !")
    time.sleep(20)

