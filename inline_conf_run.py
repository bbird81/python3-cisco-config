# Originally forked by Alex Munoz "Python-Cisco-Backup" script https://github.com/AlexMunoz905/ by Ste Giraldo https://github.com/ste-giraldo
# Refactoring + auto discover ssh/telnet by Blackbird
ver = "python3-cisco-config ver. 1.5.0i - 2022-03-06 | https://github.com/bbird81/python3-cisco-config"

# All pre-installed besides Netmiko.
import csv
from datetime import date, datetime
from netmiko import ConnectHandler
from netmiko import ssh_exception, Netmiko
from paramiko.ssh_exception import AuthenticationException
from netmiko.ssh_exception import NetMikoAuthenticationException
from ping3 import ping, verbose_ping 
import getpass, os, os.path, sys, getopt, time, cmd
import socket

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

sys.tracebacklimit = 0

# Checks if the folder exists, if not, it creates it.
if not os.path.exists('result-config'):
    os.makedirs('result-config')

# Current date and time in format: Year-Month-Day_Hours-Minutes
now = datetime.now()
dt_string = now.strftime("%Y-%m-%d_%H-%M")

def check_port(ip):
    '''
    Verifica quale porta fra ssh-telnet è aperta e restituisce il nome del driver corrispondente (con preferenza su ssh)
    '''
    cp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ip_ssh = (ip, 22)
    ip_telnet = (ip, 23)
    try:
        check = cp.connect_ex(ip_ssh)
        if check == 0:
            return 'cisco_ios'
    except: #in case of closed ssh, telnet will be tested
        try:
            check = cp.connect_ex(ip_telnet)
            if check == 0:
                return 'cisco_ios_telnet'
        except:
            return '' #no port is open, implement raise exception and continue

def print_help():
    '''
    Just prints the help message
    '''
    print(ver)
    print()
    print('Usage: conf_run.py -c <config_filename> -s <host_list.csv> (Opt --verbose)')
    print('Note: Default output filename is DNS based (check README.md)')
    print()
    print('       -c, --conf <config_filename>')
    print('       -s, --csv <host_list.csv>')
    print('       Optional -v, --verbose')
    print('       Optional -n, --host    Output filename use hostname retrived from device')
    #print('       Device connection method: --ssh (SSH: default), --tnet (telnet)')
    print('       -h, --help    Print this help and exit')

def test_devices():
    '''
    Reads the CSV file, writes a file with non-pingable devices and returns a list of active_devices
    '''
    active_devices = []
    with open(csv_name, 'r') as csvfile:
        csv_reader = csv.DictReader(csvfile, delimiter=',')
        for ip in csv_reader:
            print('Pinging '+str(ip['IP'])+'...', end='')
            ip_ping = ping(str(ip['IP']))
            if ip_ping == None:
                fileName = "downDevices_" + dt_string + ".txt"
                downDeviceOutput = open("result-config/" + fileName, "a")
                downDeviceOutput.write(str(ip['IP']) + "\n")
                print(" is DOWN!")
            else:
                active_devices.append(str(ip['IP']))
                print(" is UP!")
    return active_devices

def get_saved_config(host, username, password, enable_secret, flag_host):
    '''
    Executes commands and saves config file
    '''
    try:
        cisco_ios = {
            'device_type': check_port(host), #checks whichever port 22-23 is open and returns name of corresponding netmiko driver
            'host': host,
            'username': username,
            'password': password,
            'secret': enable_secret
        }
    except:
        #gestione del caso in cui entrambe le porte ssh/telnet sono chiuse
        print('Error creating socket: ssh and telnet closed')
        sys.exit(2)
    # Creates connection to the device.
    try:
        net_connect = ConnectHandler(**cisco_ios)
        net_connect.enable()
        # Configuring from commands in variable config file.
        output = net_connect.send_config_from_file(conf_name)
        time.sleep(0.5)
        print()
        print(output)
        print()
        # Creates the file name with either hostname/ip and date and time.
        if flag_host:
            # Gets and splits the hostname for the output file name.
            hostname = net_connect.send_command("show ver | i uptime")
            hostname = hostname.split()
            hostname = hostname[0]
            fileName = hostname + "_" + dt_string
        else:
            fileName = host + "_" + dt_string
        # Creates the text file in the result-config folder with the special name and writes to it.
        backupFile = open("result-config/" + fileName + ".txt", "w+")
        backupFile.write(output)
        print("Outputted to " + fileName + ".txt")
    # Handle an authentication error.
    except (AuthenticationException, NetMikoAuthenticationException):
        print("Login failed " + host)

# Define command arguments for inline options
def main(argv):
    global conf_name
    global csv_name
    try:
        # Set host or DNS mode flag to Flase
        flag_host = False
        opts, args = getopt.getopt(argv,"hnc:vs:",["conf=","csv=","help","host","verbose"])
    except getopt.GetoptError:
        print_help()
        sys.exit(2)
    for opt, arg in opts:
#        if opt == ("-h"):
        if opt in ("-h", "--help"):
            print_help()
            sys.exit()
        elif opt in ("-c", "--conf"):
            conf_name = arg
        elif opt in ("-s", "--csv"):
            csv_name = arg
        elif opt in ("-v", "--verbose"):
            print("Config filename is: " + bcolors.OKGREEN + conf_name + bcolors.ENDC)
            print("CSV filename is: " + bcolors.WARNING + csv_name + bcolors.ENDC)
        # Choose if run in IP address or DNS mode. If no flag is set, default option is DNS mode.
        elif opt in ("-n", "--host"):
            flag_host = True
    
    #funzione che testa quali ip rispondono e crea un file con gli apparati down --> restituisce una lista di apparati up
    active_devices = test_devices()

    #ciclo sugli apparati UP: retrieve delle credenziali ed esecuzione dei comandi + backup config.
    for ip in active_devices:
        print('Eseguo le operazioni su: '+ip)
        with open(csv_name, 'r') as csvfile:
            csv_reader = csv.DictReader(csvfile)
            #retrieve username/password
            '''
            Every row of csv file will look like this dictionary:

                {
                "IP": "10.0.0.1",
                "Username": "admin",
                "Password": "password",
                "Enable Secret": "enable_secret_password"
                }
            '''
            for row in csv_reader: #cerco la riga relativa all'apparato
                if row['IP'] == ip: #abbiamo trovato l'entry, estraggo le info
                    username = row['Username']
                    password = row['Password']
                    enable_secret =row['Enable Secret']
                    get_saved_config(ip, username, password, enable_secret, flag_host)
                    continue #esco dal ciclo interno di ricerca credenziali nel CSV, passo all'ip attivo successivo

if __name__ == "__main__": #runs only from the command line
   main(sys.argv[1:])
   conf_name=''
   csv_name=''
