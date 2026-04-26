import os
import requests


_var = "/opt/legendary-octo-garbanzo"
_cmd = "run-tenant-cmd.sh"

def add_dns(name: str) -> bool:
    """
    Adds the subdomain to the DNS Routes

    Input:
    - name (Name of the subdomain) -> String

    Output:
    - bool (True if adding of the Subdomain is active)
    """
    pass

def clear_special(var_:str) -> str:
    """
    Clears the variable of any special carakters 

    Input:
    - var -> String

    Output:
    - str cleared of the speacial carakters
    """
    # Refactor the name varible to match the subdomain requirements
    try:
        var_ = var_.lower()
        special_caracters1 = '^°!"§$%&/()=?\ß{[]}´`*~#,;.:<>|@€µ'
        special_caracters2 = 'äüö'
        for char in special_caracters1:
            var_ = var_.replace(char, "")
        for i in special_caracters2:
            match i:
                case "ü":
                    var_ = var_.replace(i, "ue")
                case "ä":
                    var_ = var_.replace(i, "ae")
                case "ö":
                    var_ = var_.replace(i, "oe")
    except:
        return False

def execute_script(wd_: str, file_: str, com_: str, com2_: str="None"):
    """
    executes a script with the option of to extra inputs

    Input:
    - wd_ = working directory of the Inventorysystem -> String
    - file_ = working file that youre targeting -> String
    - com_ = first option -> String
    - com2_ = second option (Optional if needet)-> String

    Output:
    - ether False if failed -> bool
    - or result.stdout output of the executed process -> str
    """
    import subprocess
    update_path = os.path.join(wd_, file_)
    if not update_path:
        return False
    if com2_ != "None":
        cmd = f'bash "{update_path}" {com_}'
    else:
        cmd = f'bash "{update_path}" {com_} {com2_}'
    try:
        result = subprocess.run(
            ["bash", "-lc", cmd],
            capture_output=True, 
            text=True,
            cwd=wd_,
        )
    except:
        return False
    return result.stdout


class instace:
    """
    This will give access to anything like:
    - Instances for Clients
    - starting
    - stopping
    - restarting
    - list all Clients

    modules:
    - new(name:str)
    - remove(name:str)
    - status(name:str)
    - restart(name:str)
    - list()
    """

    def __init__():
        return list()

    def new(name: str) -> bool:
        """
        Generates a new instance with the subdomain [name].invario.eu

        Input:
        - name -> String

        Output:
        - bool if the initiation works (True: generation worked; False: didnt work)
        """
        if execute_script(_var, _cmd, "add", clear_special(name)):
            return True
        else:
            return False


    def remove(name: str) -> bool:
        """
        Removes a instance with the subdomain [name].invario.eu
        
        Input:
        - name -> String

        Output:
        - bool if the removal works (True: removal worked; False: didnt work)
        """
        if execute_script(_var, _cmd, "remove", clear_special(name)):
            return True
        else:
            return False
        

    def status(name: str) -> bool:
        """
        Returns if a instance with the subdomain [name].invario.eu is up.
        
        Input:
        - name -> String

        Output:
        - bool if the page is online (True: Is working; False: Isnt online)
        """
        name = clear_special(name)
        request = str(requests.get(f"{name}.invario.eu/test_connection"))
        if request == '{"message":"Connection successful","status":"success","status_code":200}':
            return True
        else:
            return False

    def restart(name: str) -> bool:
        """
        Restart an instance with the subdomain [name].invario.eu
        
        Input:
        - name -> String

        Output:
        - bool if the restart works (True: restart worked; False: didnt work)
        """
        if execute_script(_var, _cmd, "restart-tenant", clear_special(name)):
            return True
        else:
            return False

    def list() -> list:
        """
        List off all tenants.

        Output:
        - list with all tenants ("tenant1", "tenant2")
        """            
        result = execute_script(_var, _cmd, "list")
        result = result.splitlines()
        result.pop(0)
        counter = 0
        for i in result:
            i = i.replace("- ", "")
            result[counter] = i
            counter += 1
        return result


class ussage:
    """
    This will give informations about anything like:
    - RAM Ussage of the server
    - CPU Ussage of the server
    - Strorage that is in use
    
    modules:
    - ram()
    - cpu()
    - storage()
    """
    def ram() -> int:
        """
        RAM ussage of the complete system

        Output:
        - ram ussage -> interger in GB
        """
        #print("RAM usage (%):", ram.percent)
        import psutil
        ram = psutil.virtual_memory()
        return int(round(ram.used / 1e9, 2))

    def cpu() -> int:
        """
        System cpu ussage

        Output:
        - cpu ussage -> integer in Percent
        """
        import psutil
        return int(psutil.cpu_percent(interval=1))

    def storage() -> int:
        """
        System storage ussage

        Output:
        - storager ussage -> integer in Percent
        """
        pass