'''
    This is a mainfunction to test the handling
    process of the Talos-Handler
'''
from talos import (start_handling,temperaturecontrol,querySite,end_of_cycle,initialize, temperaturefeedback)
from time import sleep
import random 


def testing():
    print("Device is at the doctor")
    bin = random.randint(1,31)
    
    print(f"Sorting device to Bin class {bin}")
    return bin



def main():
    
    # ==============================================
    #               Set-up of Test
    temp_program = []
    debugmode = 1
    end_of_test = 0
    num_TC = 3
    # ==============================================
    
    print("Measurement Program has been initialized")
    
    inst,n = initialize(temp_program,debugmode)
    status = start_handling(inst,n) #Muss bei erneutem start des Programms auskommentiert werden
    num_TC_finished = 0
    
    while status == True:
        # Measurement Programm wird hier durchgeführt
        if not temp_program: #ambient measurement
            while True:
                status = querySite(inst)
                if status:
                    break
            temp = temperaturecontrol(inst,temp_program)
            sleep(10)
            bin_class = testing()
        else:
            for item in temp_program:
                while True:
                    status = querySite(inst)
                    if status:
                        break
                temp = temperaturecontrol(inst,item)
                print("Necessary temperture reached")
                sleep(10)
            bin_class =  () #placeholder for dataaquisition between temperaturesettings        
        
        num_TC_finished += 1
        if num_TC_finished == (num_TC):
            end_of_test = 1
            status == False
        
        end_of_cycle(inst,n,bin_class,end_of_test)
            
    

if __name__ == "__main__":
    main()