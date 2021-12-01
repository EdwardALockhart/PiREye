"""
Pi PIR Eye (PiREye)

Copyright Edward Alan Lockhart
2021

Requires:
    Raspberry Pi
    Camera module
    PIR sensor connected via GPIO
Optional:
    Internet connection (ethernet cable)
    
Functionality:
    Output directory creation
    Detects if WiFi is up (interferes with the PIR sensor on higher sensitivities)
    Timestamped captures
    Image burst capture (locally saved with attempted data transmission)
    Checks for free space remaining (5GB cutoff)
    Attempts armed, disarmed and daily scheduled status update transmission
    Not disrupted if the internet connection is lost
"""
print("PiREye\n\nCtrl+C to abort")



#-----DEPENDENCIES
import subprocess
from os.path import basename
from pathlib import Path
import time
from datetime import datetime
from shutil import disk_usage
from picamera import PiCamera
import RPi.GPIO as GPIO
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText



#-----SETTINGS
GPIO_PIR = 4 # PIR sensor GPIO pin number (BCM)

RECIPIENT = "" # Email address to send data to
USER = "@gmail.com" # Raspberry Pi's email account
APP_PWD = "" # App password
SERVER = "smtp.gmail.com" # STMP server
PORT = 587 # STMP server port

DIRECTORY = "/media/pi/STORAGE" # Output detections folder location
TIMES = ["09:00:00", "21:00:00"] # Times in HH:MM:SS to send daily status updates



#-----FUNCTIONS
def send_mail(user, app_pwd, recipient, subject, body, files, server, port):
    msg = MIMEMultipart()
    msg["From"] = user
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(body))

    for i in files or []:
        with open(i, "rb") as file:
            part = MIMEApplication(file.read(), Name = basename(i))
        part["Content-Disposition"] = 'attachment; filename = "%s"' % basename(i)
        msg.attach(part)
        
    with smtplib.SMTP(server, port, timeout = 15) as mail:
        mail.ehlo() # Identify ourselves
        mail.starttls() # Start encryption
        mail.ehlo() # Identify ourselves as encrypted
        mail.login(user, app_pwd)
        mail.sendmail(user, recipient, msg.as_string())
        mail.close()
    
    print("Transmitted")



#-----SETUP
# Set up the PIR sensor
GPIO.setmode(GPIO.BCM)
GPIO.setup(GPIO_PIR, GPIO.IN)

# Set PIR mode jumper to H (repeat trigger)
# Point both PIR adjustments towards each other
# Increase time delay (knob furthest from jumper) to ensure the repeat trigger 
# captures continued motion and does not stop until motion stops

#detected = 0
#while True:
#    if detected == 0 and GPIO.input(GPIO_PIR) == 1:
#        print("Detected")
#        detected = 1
#    elif detected == 1 and GPIO.input(GPIO_PIR) == 0:
#        print("Not detected")
#        detected = 0

# Set up the camera
camera = PiCamera()
camera.rotation = 180
time.sleep(2)



#-----SYSTEM
try:
    # Not yet armed
    armed = False
    
    
    
    #-----CHECKS
    # Check if the WiFi is up
    if "wlan0:" in str(subprocess.check_output("ifconfig", shell = True)):
        print("\nWiFi appears to be up, turn it off to prevent interference with the PIR sensor")
        raise Exception
    
    # Check that the datetime is correct
    while True:
        data = input("Datetime Check\n" + "Is " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " correct?\n(y) Yes\n(n) No\n: ").lower()
        if data not in ("y", "n"):
            print("\nInvalid input, try again")
        else:
            break
    if data == "n":
        print("\nSet with 'sudo date -s YYYY-MM-DD HH:MM' or sync over the network")
        raise Exception
    


    #-----SETUP
    # Create the output directory
    out_directory = DIRECTORY + "/Detections/"
    Path(out_directory).mkdir(parents = True, exist_ok = True)

    # Generate a preview for camera placement
    camera.start_preview()
    camera.annotate_text = "Preview (15 seconds)"
    time.sleep(15)
    camera.stop_preview()



    #-----ACTIVATION
    print("\nArming in 60 seconds...")
    time.sleep(60)
    armed = True
    armed_time = datetime.now().strftime("*** ARMED *** %Y-%m-%d %H:%M:%S")
    print(armed_time)
    try:
        send_mail(user = USER,
                  app_pwd = APP_PWD,
                  recipient = RECIPIENT,
                  subject = armed_time,
                  body = armed_time,
                  files = None,
                  server = SERVER,
                  port = PORT)
    except Exception:
        pass
    
    # Start monitoring
    while True:
        if datetime.now().strftime("%H:%M:%S") in TIMES:
            update_time = datetime.now().strftime("Active %Y-%m-%d %H:%M:%S")
            print(update_time)
            time.sleep(1) # Prevent retriggering
            try:
                send_mail(user = USER,
                          app_pwd = APP_PWD,
                          recipient = RECIPIENT,
                          subject = update_time,
                          body = update_time,
                          files = None,
                          server = SERVER,
                          port = PORT)
            except Exception:
                pass
        
        # While the PIR detects motion
        while GPIO.input(GPIO_PIR) == 1:
            detection_time = datetime.now().strftime("Detection %Y-%m-%d %H:%M:%S")
            print(detection_time)
            
            camera.annotate_text = detection_time
            sequence = [out_directory + detection_time.replace(":", "-") + "_" + str(i+1) + ".jpg" for i in range(5)]
            camera.capture_sequence(sequence)
            
            try:
                send_mail(user = USER,
                          app_pwd = APP_PWD,
                          recipient = RECIPIENT,
                          subject = detection_time,
                          body = detection_time,
                          files = sequence,
                          server = SERVER,
                          port = PORT)
            except Exception:
                pass
            
            if disk_usage(DIRECTORY)[2]/1000000000 <= 5:
                print("\nLow free space")
                raise Exception


          
except Exception:
    pass
except KeyboardInterrupt:
    pass

finally:
    camera.close()
    GPIO.cleanup()
    if not armed:
        print(datetime.now().strftime("Cancelled"))
    else:
        disarmed_time = datetime.now().strftime("*** DISARMED *** %Y-%m-%d %H:%M:%S")
        print(disarmed_time)
        try:
            send_mail(user = USER,
                      app_pwd = APP_PWD,
                      recipient = RECIPIENT,
                      subject = disarmed_time,
                      body = disarmed_time,
                      files = None,
                      server = SERVER,
                      port = PORT)
            print("Status Transmitted")
        except Exception:
            pass

