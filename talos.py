from pyvisa import ResourceManager,constants
from Netio import Netio as net
from time import sleep


def querySite(inst):
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
    path = "C:/Users/saschama/Desktop/Talos/cache"
    with open(path+"sitestatus.txt","w") as f:
        f.write(status)
    return
def checkBoardPwr(n):
    outputs = n.get_outputs()
    states = [outputs[i].State for i in range(len(outputs))]
    
    return states

def controlBoardPwr(n,newstate):
    '''
        function to control the powerline from Netio
        Input:
        newstate=0 : turn OFF
        newstate=1 : turn ON
        newstate=2 : toggle to the other state
        
        Return:
        None
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
    return None 

def start_handling(inst,n):
    stat_Socket = False
    ready = False
    print(inst.query("TMP?"))
    inst.write("RESTART")
    print("Waiting for SRQ")
    inst.wait_for_srq(None)
    print("SRQ has been received")
    stat_Socket = querySite(inst) #wird nur ausgeführt wenn SRQ eingegangen ist
    ready = True
    if stat_Socket:
        controlBoardPwr(n,1)
        stat_Board = checkBoardPwr(n)
        if all(stat_Board) == 1:
            ready = True
    return ready

def initialize(temp,debug):
    # global inst, n
    global inst
    
    #Initialize the Instrument -> Talos
    rm = ResourceManager()
    address = "GPIB0::3::INSTR"
    
    # ID fragen -- vergleichen -- errorhandling    
    try:
        inst = rm.open_resource(address)
        print("Instument has ben initialized correctly")
    except:
        raise Exception("Check Connection or GPIB-Address.")
    inst.read_termination = "\r\n"
    inst.write_termination = "\r\n"
    inst.query_delay = 0.5
    inst.timeout = None
    
    if not temp:
        inst.query("TMPM 1,amb")
    else:
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
    
    stat_Board = checkBoardPwr(n)
    print(f"Current Status Power: {stat_Board}")
    if any(stat_Board) == 1:
        print("Shutting off Power")
        controlBoardPwr(n,0)
        stat_Board = checkBoardPwr(n)
        print(f"Current Status Power: {stat_Board}")
        
        if any(stat_Board) == 1:
            raise Exception("Plug Connector not shut off correctly - Check Status")
        
    
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

def end_of_cycle(inst,n, BIN: int, eot: bool):
    '''
    BIN: bin-class in which to sort the sample, acts as continue-command for Talos
    debug: When debug-mode is enabled, Talos ends the process after handling current sample (states: 1|0)
    eot: (states: 1|0) set to 1 when # of planned testsamples have been handled
    '''
    bin_class = str(BIN)
    if len(bin_class)<2:
        bin_class = "0"+bin_class
    bin_command = "01BIN"+bin_class
    
    controlBoardPwr(n,0)
    stat_Board = checkBoardPwr(n)
    
    if all(stat_Board) == False:
        inst.write(bin_command)
        updateCache("0")
    
    if eot:
        inst.query("TMPM 1,amb")
        inst.write("EOCH")
        print("=========================")
        print("Testing concluded - Going to sleep")

def temperaturecontrol(inst, temp: float) -> float:
    '''
    mode: ambient = 0; temperature = 1
    temp: used for numerical temperature
    
    RETURN: current temperature
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
            socket_status = querySite(inst)
            if socket_status == True:
                break
            else:
                print("Wait for Socket")
                sleep(1)
    current_temp = inst.query("TMP?")
    print("Current temperature: "+current_temp+" °C")
    current_temp = float(current_temp)
    return current_temp 

def temperaturefeedback(inst):
    current_temp = inst.query("TMP?")
    temp = float(current_temp)
    return temp

def safe_shutdown(inst,n):
    states = checkBoardPwr(n)
    if any(states)!=False:
        controlBoardPwr(n,0)
        sleep(15)
        states = checkBoardPwr(n)
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
    path = "C:/Users/saschama/Desktop/Talos/cache"
    inst,n = initialize(temp_program,debugmode)
    querySite(inst)
    print("Measurement Program has been initialized")
    with open(path+"/sitestatus.txt","r") as f:
        state_site = int(f.readline())
        if state_site == 0:
            status = start_handling(inst,n)
        else:
            print("Check for errors")
    return status
