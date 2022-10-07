import os
from flask import Flask, render_template, abort, url_for, json, jsonify, request
import RPi.GPIO as GPIO            
from time import sleep   
import time      
import json
from flask_socketio import SocketIO
from ping3 import ping
import threading
import iptools

GPIO.setmode(GPIO.BOARD)             
app = Flask(__name__)


socketio = SocketIO(app, async_handlers=True, pingTimeout=900)

@app.route("/")
@app.route("/index/", methods=['POST'])
def index():
    
    return render_template('index.html')
    
@app.route('/SET_REMOTE_GPIO_ON/<gpiopin>', methods=['POST', 'GET'])
@app.route("/index/SET_REMOTE_GPIO_ON/<gpiopin>", methods=['POST', 'GET'])
def SET_REMOTE_GPIO_ON(gpiopin):

    print('GPIO called ON : '+str(gpiopin))
    
    GPIO.setup(int(gpiopin), GPIO.OUT)          
    GPIO.output(int(gpiopin),GPIO.HIGH)
    stringToreturn = str(GPIO.input(int(gpiopin)))
    return jsonify(stringToreturn)
    
@app.route('/SET_REMOTE_GPIO_OFF/<gpiopin>', methods=['POST', 'GET'])
@app.route("/index/SET_REMOTE_GPIO_OFF/<gpiopin>", methods=['POST', 'GET'])
def SET_REMOTE_GPIO_OFF(gpiopin):

    print('GPIO called ON : '+str(gpiopin))
    
    GPIO.setup(int(gpiopin), GPIO.OUT)          
    GPIO.output(int(gpiopin),GPIO.LOW)
    stringToreturn = str(GPIO.input(int(gpiopin)))
    return jsonify(stringToreturn)  
    
@app.route('/GET_REMOTE_GPIO_STATE/<gpiopin>', methods=['POST', 'GET'])
@app.route("/index/GET_REMOTE_GPIO_STATE/<gpiopin>", methods=['POST', 'GET'])
def GET_REMOTE_GPIO_STATE(gpiopin):
    
    GPIO.setup(int(gpiopin), GPIO.OUT)   
    return jsonify(GPIO.input(int(gpiopin))  )
    
    
if __name__ == '__main__':
    socketio.debug = True
    #app.run(host="0.0.0.0") 
    socketio.run(threaded=True, host="0.0.0.0", port=80)




