from pyvisa import ResourceManager,constants
from Netio import Netio as net
from time import sleep

# ----------------------------------------------------#
#   Functions for the ESMO Talos2.0 Package Handler   #
#                                                     #      
#      |====================================|         #      
#      | currently implemented as functions |         #      
#      |   after testing will be adapted    |         #  
#      |  to a class "Talos" with methods   |         #  
#      |====================================|         #  
# ----------------------------------------------------#



def querySite():
    '''
    Check if the Site is ready (Package and thermohead in place)
    
    Input: ~ 
    Output: site -> Boolean
    '''
    
    site=False
    status = str(inst.query("CRT?"))
    print(status)
    if status == "01":
        site = True
        updateCache("1")
    else:
        updateCache("0")
    return site

def updateCache(status):
    '''
    Writes site status into file
    
    Input: status -> Boolean
    Output: ~
    '''
    
    path = "./cache"
    with open(path+"sitestatus.txt","w") as f:
        f.write(status)
    return

def checkBoardPwr():
    '''
    Check for powerstates of the Netio-PowerStrip
    
    Input: ~
    Output: List(states) -> Boolean
    '''
    
    outputs = n.get_outputs()
    states = [outputs[i].State for i in range(len(outputs))]
    return states

def controlBoardPwr(newstate):
    '''
    Control the powerline from Netio
    
    Input: 
    newstate=0 : turn OFF
    newstate=1 : turn ON
    newstate=2 : toggle to the other state
    
    Output: ~
    '''
    
    if newstate==0:
        n.set_output(1,net.ACTION.OFF)
        n.set_output(2,net.ACTION.OFF)
        n.set_output(3,net.ACTION.OFF)
    elif newstate==1:
        n.set_output(1,net.ACTION.ON)
        n.set_output(2,net.ACTION.ON)
        n.set_output(3,net.ACTION.ON)
    elif newstate==2:
        n.set_output(1,net.ACTION.TOGGLE)
        n.set_output(2,net.ACTION.TOGGLE)
        n.set_output(3,net.ACTION.TOGGLE)
        
    sleep(2) #arbiträre Zeit die gewartet wird bis steckdose angeschalltet sein sollte
    return  

def start_handling():
    '''
    Start of handling process - Start signal and stop program until site is ready; Power to the Board is enabled
    
    Input: ~ 
    Output: ready -> boolean
    '''
    
    stat_Socket = False
    ready = False
    print(inst.query("TMP?"))
    inst.write("RESTART")
    print("Waiting for SRQ")
    inst.wait_for_srq(None)
    print("SRQ has been received")
    stat_Socket = querySite() #wird nur ausgeführt wenn SRQ eingegangen ist
    ready = True
    if stat_Socket:
        controlBoardPwr(1)
        stat_Board = checkBoardPwr()
        if all(stat_Board) == 1:
            ready = True
    return ready

def initialize(temp,debug):
    '''
    Configuration of the system
    
    Input: 
        List(temp) -> float
        debug -> boolean
    
    Output:
        inst -> object
        n -> object
    '''
    
    global inst, n 
    
    #Initialize the Instrument -> Talos
    rm = ResourceManager()
    address = "GPIB0::3::INSTR" #change when needed
    
    # ID fragen -- vergleichen -- errorhandling    
    try:
        inst = rm.open_resource(address)
        print("Instument has ben initialized correctly")
    except:
        raise Exception("Check Connection or GPIB-Address (in function 'initialize')")
    # setup of the communication, ensures no timeout until srq is received during handling
    inst.read_termination = "\r\n"
    inst.write_termination = "\r\n"
    inst.query_delay = 0.5
    inst.timeout = None
    
    
    if not temp:
        inst.query("TMPM 1,amb")
    else:
        #set mode to temperature, needed to change temperatures later on
        inst.query("TMPM 1,tmp")

    # test_mode = inst.query("TestMode?")
    # if debug==1 and test_mode!='Bin Sort Mode':
    #     raise Exception("Please choose 'Bin Sort Mode' to be able to choose starting position")
    # elif debug==1 and test_mode=='Bin Sort Mode':
    #     print("Please choose the pick position for the next device")
    #     tray = str(input("Tray number > "))
    #     row = (input("Row index >"))
    #     column = (input("Column index >"))
    #     if len(row) < 2:
    #         row = "0"+row
    #     if len(column) < 2:
    #         column = "0"+column
    #     confirmation = inst.query("StartPosition "+tray+";"+row+";"+column)
    #     if confirmation != 'OK':
    #         raise Exception("Something went wrong with the starting position")

    #Initialize the powerline and make sure it is turned off
    try: 
        n = net('http://10.62.199.7/netio.json', auth_rw=('netio', 'netio'), verify=False)
    except:
        raise Exception("Check for correct IP, User, Pw, Ethernet-Connection")
    
    # ensures board is shut down
    stat_Board = checkBoardPwr()
    print(f"Current Status Power: {stat_Board}")
    if any(stat_Board) == 1:
        print("Shutting off Power")
        controlBoardPwr(0)
        stat_Board = checkBoardPwr()
        print(f"Current Status Power: {stat_Board}")
        
        if any(stat_Board) == 1:
            raise Exception("Power Strip is not shut off correctly - Check Status")
        
    
    #Loading the correct recipe
    # recipe = "UUC"
    # current_recipe = inst.query("RecipeName?")
    # print(current_recipe)
    # if current_recipe != recipe:
    #     print("I'm in!")
    #     # load_recipe = "LoadRecipe "+recipe
    #     # print("Recipe to load: "+load_recipe)
    #     # inst.write(load_recipe)
    # print("correct recipe loaded")
    
    # return inst,n
    return inst,n

def end_of_cycle(BIN: int, eot: bool):
    '''
    Controlls the events after the test has been concluded
    
    Input:
        BIN: bin-class in which to sort the sample, acts as continue-command for Talos -> int
        
        eot: (states: 1|0) set to 1 when # of planned testsamples have been handled -> boolean
        
    Output: ~
    
    '''
    #correct formating
    bin_class = str(BIN)
    if len(bin_class)<2:
        bin_class = "0"+bin_class
    bin_command = "01BIN"+bin_class
    
    controlBoardPwr(0)
    stat_Board = checkBoardPwr()
    
    if all(stat_Board) == False:
        inst.write(bin_command)
        updateCache("0")
    
    if eot:
        inst.query("TMPM 1,amb")
        inst.write("EOCH")
        print("=========================")
        print("Testing concluded - Going to sleep")
    return

def temperaturecontrol(temp: float) -> float:
    '''
    setting the correct temperature for the test

    Input:
        temp: used for numerical temperature -> float
    
    RETURN: current_temp -> float
    '''
    print("=========================")
    if not temp:
        print("Ambient Mode activated")
    else:
        print("Temperature Mode activated")
        new_temp = round(temp,2)
        while True:
            set_temp = inst.query("Temperature?")
            if set_temp == 'busy':
                continue
            else:
                set_temp = float(set_temp)
                break
        soaktime = float(inst.query("Soaktime?"))
        print(f"Next Temperature: {new_temp}°C - Soaktime: {soaktime}")
        
        if new_temp != set_temp:
            if new_temp>=0:
                s = "+"
            else:
                s = "-"
            new_temp = "{:.2f}".format(round(new_temp,2))
            tmp_command = "TMP 1,"+s+new_temp
            inst.write(tmp_command)
            sleep(soaktime) #wait for x seconds until soaktime has elapsed
        
        while True:
            socket_status = querySite()
            if socket_status == True:
                break
            else:
                print("Wait for Socket")
                sleep(1)
    current_temp = inst.query("TMP?")
    print("Current temperature: "+current_temp+" °C")
    current_temp = float(current_temp)
    return current_temp 

def temperaturefeedback() -> float:
    '''
    Returns current thermohead temperature
    
    Input: ~
    Output: temp -> float
    '''
    
    current_temp = inst.query("TMP?")
    temp = float(current_temp)
    return temp

def safe_shutdown():
    states = checkBoardPwr()
    if any(states)!=False:
        controlBoardPwr(0)
        sleep(15)
        states = checkBoardPwr()
    if all(states) == False:
        updateCache("0")
        inst.query("01BIN31")
    else:
        raise Exception("Could not cut POWER - Turn off POWER manually")
    return



'''
    for external calls
'''
def talos_startup(temp_program,debugmode):
    path = "./cache"
    inst,n = initialize(temp_program,debugmode)
    querySite()
    print("Measurement Program has been initialized")
    with open(path+"/sitestatus.txt","r") as f:
        state_site = int(f.readline())
        if state_site == 0:
            status = start_handling()
        else:
            print("Check for errors")
    return status
