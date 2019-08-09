#!/usr/bin/python3
  
# Copyright 2018 Blade M. Doyle
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
import json
import time
import socket
import getpass
import requests
import datetime
import argparse
import subprocess

class Pool_Payout:
    def __init__(self):
        self.POOL_MINIMUM_PAYOUT = 0.1
        self.payout_method = None
        # Calculate the pool name and API url
        script = os.path.basename(__file__)
        if script.startswith("MWGP"):
            self.payout_methods = ["Grin Wallet", "Grin++ Wallet", "Wallet713", "Slate Files"]
            self.poolname = "MWGrinPool"
            self.walletprefix = "grin"
            self.mwURL = "https://api.mwgrinpool.com"
            self.walletflags = None
        elif script.startswith("BGP"):
            self.payout_methods = ["BitGrin Wallet", "Slate Files"]
            self.poolname = "BitGrinPool"
            self.walletprefix = "bitgrin"
            self.mwURL = "https://api.pool.bitgrin.dev"
            self.walletflags = None
        elif script.startswith("MWFP"):
            self.payout_methods = ["Grin Wallet", "Wallet713", "Slate Files"]
            self.poolname = "MWFlooPool"
            self.walletprefix = "grin"
            self.mwURL = "https://api.mwfloopool.com"
            self.walletflags = "--floonet"
        self.unsigned_slatefile = "payment_slate.json"
        self.signed_slatefile = "payment_slate.json.response"
        self.args = None
        self.prompted = False
        self.username = None
        self.password = None
        self.wallet_pass = None
        self.user_id = None
        self.wallet_cmd = None
        self.wallet713_cmd = None
        self.balance = 0.0
        self.unsigned_slate = None
        self.signed_slate = None
        self.wallet_user = None
        self.wallet_session_token = None

       
    # Print Indented
    def print_indent(self, message="", indent_level=1, newline=True):
        for index in range(0, indent_level):
            sys.stdout.write("   ")
        sys.stdout.write(message)
        if newline is True:
            sys.stdout.write("\n")
        sys.stdout.flush()

    # Print tool head banner
    def print_banner(self):
        print(" ")
        print("#############  {} Payout Request Script  #############".format(self.poolname))
        print("## Started: {} ".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M")))
        print("## ")

    # Print tool footer
    def print_footer(self):
        print("## ")
        print("## Complete: {} ".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M")))
        print("############# {} Payout Request Complete #############".format(self.poolname))
        print(" ")

    # Print progress message
    def print_progress(self, message):
        sys.stdout.write("   ... {}:  ".format(message))
        sys.stdout.flush()

    # Print success message
    def print_success(self, message=None):
        if message is None:
            sys.stdout.write("Ok\n")
        else:
            message = str(message)
            sys.stdout.write(message)
            if not message.endswith("\n"):
                sys.stdout.write("\n")
        sys.stdout.flush()
    # Print an error message, footer, and exit
    def error_exit(self, message):
        self.error(message, True)

    # Print an error message, optionally print footer, and exit
    def error(self, message, exit=False):
        print(" ")
        print(" ")
        print("   *** Error: {}".format(message))
        if exit == True:
            self.print_footer()
            sys.exit(1)

    # Print menu, prompt for selection
    def prompt_menu(self, message, options, default):
        ok = False
        while ok == False:
            print(" ")
            self.print_indent(message)
            for key, value in options.items():
                self.print_indent("{}. {}".format(key, value))
            print(" ")
            self.print_indent("Choice [{}]".format(default), 1, False)
            selection = input(" ")
            if selection == "":
                selection = default
            if selection in options.keys():
                ok = True
            else:
                self.error("Invalid Choice, please try again")
        return options[selection]
        
    # Delete any existing slate and slate response
    def clean_slate_files(self):
        for slatefile in [self.unsigned_slatefile, self.signed_slatefile]:
            if os.path.exists(slatefile):
                os.remove(slatefile)

    # Find the wallet executable, from the path, cwd, and build directories
    def find_grin_wallet(self):
        ##
        # Find Grin Wallet Command
        grin_wallet_cmd = None
        cwd = os.getcwd()
        path = os.environ.get('PATH')
        path_add = [
            path,
            cwd,
            cwd + "/{}-wallet".format(self.walletprefix),
            cwd + "/{}-wallet/target/debug".format(self.walletprefix),
            cwd + "/{}-wallet/target/release".format(self.walletprefix),
        ]
        path = ":".join(path_add)
        for directory in path.split(":"):
            if os.path.isfile(directory + "/{}-wallet".format(self.walletprefix)):
                grin_wallet_cmd = [directory + "/{}-wallet".format(self.walletprefix)]
            elif os.path.isfile(directory + "/{}-wallet.exe".format(self.walletprefix)):
                grin_wallet_cmd = [directory + "/{}-wallet.exe".format(self.walletprefix)]
        if grin_wallet_cmd is None:
            return("Could not find wallet executable, please add it to your PATH or copy it into this directory.")

        # Add any wallet flag
        if self.walletflags is not None:
            grin_wallet_cmd = grin_wallet_cmd + [ self.walletflags ]

        self.wallet_cmd = grin_wallet_cmd

    def test_grin_wallet(self):
        ##
        # Sanity check the grin wallet executable and password
        wallettest_cmd = self.wallet_cmd + [ "-p", self.wallet_pass, "info" ]
        try:
            message = subprocess.check_output(wallettest_cmd, stderr=subprocess.STDOUT, shell=False)
        except subprocess.CalledProcessError as exc:
            return "Wallet test failed with output: {}".format(exc.output.decode("utf-8"))
        except Exception as e:
            return "Wallet test failed with error {}".format(str(e))

    # Get my pool user_id
    def get_user_id(self):
        get_user_id_url = self.mwURL + "/pool/users"
        r = requests.get(
                url = get_user_id_url,
                auth = (self.username, self.password),
        )
        message = None
        if r.status_code != 200:
            message = "Failed to get your account information from {}: {}".format(self.poolname, r.text)
            return message
        self.user_id = str(r.json()["id"])
        return None

    # Get the users balance
    def get_balance(self):
        get_user_balance = self.mwURL + "/worker/utxo/" + self.user_id
        r = requests.get(
                url = get_user_balance,
                auth = (self.username, self.password),
        )
        if r.status_code != 200:
            return "Failed to get your account balance: {}".format(r.text)
        if r.json() is None:
            balance_nanogrin = 0
        else:
            balance_nanogrin = r.json()["amount"]
        self.balance = balance_nanogrin / 1000000000.0
        if self.balance < 0:
            self.balance = 0.0

    def get_unsigned_slate(self):
        ##
        # Get the initial tx slate and write it to a file
        get_tx_slate_url = self.mwURL + "/pool/payment/get_tx_slate/" + self.user_id
        r = requests.post(
                url = get_tx_slate_url,
                auth = (self.username, self.password),
        )
        if r.status_code != 200:
            return "Failed to get a payment slate: {}".format(r.text)
        self.unsigned_slate = r.text

    # Write json slate to a file
    def write_unsigned_slate_file(self):
        try:
            f = open(self.unsigned_slatefile, "w")
            f.write(self.unsigned_slate) 
            f.flush()
            f.close()
            return None
        except Exception as e:
            return "Error saving payment slate to file: {}".format(str(e))
        
    # Write signed json slate to a file
    def write_signed_slate_file(self):
        try:
            f = open(self.signed_slatefile, "w")
            f.write(self.signed_slate) 
            f.flush()
            f.close()
            return None
        except Exception as e:
            return "Error saving signed payment slate to file: {}".format(str(e))
        
    def sign_slate_with_wallet_cli(self):
        ##
        # Call the wallet CLI to receive and sign the slate
        recv_cmd = self.wallet_cmd + [
                "-p", self.wallet_pass,
              "receive",
                "-i", self.unsigned_slatefile,
        ]
        try:
            output = subprocess.check_output(recv_cmd, stderr=subprocess.STDOUT, shell=False)
            with open(self.signed_slatefile, 'r') as tx_slate_response:
                self.signed_slate = tx_slate_response.read()
        except subprocess.CalledProcessError as exc:
            return "Signing slate failed with output: {}".format(exc.output.decode("utf-8"))
        except Exception as e:
            return "Wallet receive failed with error: {}".format(str(e))

    def test_grinplusplus_wallet(self):
        ##
        # Test that the grin++ wallet API is available
        s = socket.socket()
        s.settimeout(2)
        try:
            s.connect(("localhost", 3420))
            s.close()
        except Exception as e:
            return "Could not connect to Grin++ wallet port.  Is the wallet running?"

    def login_grinplusplus_wallet(self):
        ##
        # Log into Grin++ wallet and get a session token
        login_url = "http://localhost:3420/v1/wallet/owner/login"
        r = requests.post(
                url = login_url,
                headers = {
                        "username": self.wallet_user,
                        "password": self.wallet_pass,
                    }
            )
        if r.status_code != 200:
            return "Failed to log into wallet - {}".format(r.text)
        self.wallet_session_token = r.json()["session_token"]

    def logout_grinplusplus_wallet(self):
        ##
        # Log out of Grin++ wallet
        login_url = "http://localhost:3420/v1/wallet/owner/logout"
        r = requests.post(
                url = login_url,
                headers = { "session_token": self.wallet_session_token },
            )
        if r.status_code != 200:
            return "Failed to log out of wallet - {}".format(r.text)
        self.wallet_session_token = None

    def sign_slate_with_grinplusplus_wallet_api(self):
        ##
        # Call Grin++ wallet API to sign the slate file
        sign_slate_url = "http://localhost:3420/v1/wallet/owner/receive_tx"
        r = requests.post(
                url = sign_slate_url,
                headers = { "session_token": self.wallet_session_token },
                data = '{ "slate": ' + self.unsigned_slate + '}'
            )
        if r.status_code != 200:
            return "Failed to receive slate - {}".format(r.text)
        self.signed_slate = r.text

    # Find the wallet713 executable, from the path, cwd, and build directories
    def find_wallet713(self):
        ##
        # Find wallet713 Command
        wallet713_cmd = None
        cwd = os.getcwd()
        path = os.environ.get('PATH')
        path_add = [
            path,
            cwd,
            cwd + "/wallet713",
            cwd + "/wallet713/target/debug",
            cwd + "/wallet713/target/release",
        ]
        path = ":".join(path_add)
        for directory in path.split(":"):
            if os.path.isfile(directory + "/wallet713"):
                wallet713_cmd = [directory + "/wallet713"]
            elif os.path.isfile(directory + "/wallet713.exe"):
                wallet713_cmd = [directory + "/wallet713.exe"]
        if wallet713_cmd is None:
            return("Could not find wallet713 executable, please add it to your PATH or copy it into this directory.")

        # Add any wallet flag
        if self.walletflags is not None:
            wallet713_cmd = wallet713_cmd + [ self.walletflags ]

        self.wallet713_cmd = wallet713_cmd

    def test_wallet713(self):
        ##
        # Sanity check the wallet713 executable and password
        try:
            w713_handle = subprocess.Popen(self.wallet713_cmd,
                                           stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE,
                                           bufsize=0)
            output = w713_handle.stdout.read(1).decode("utf-8")
            while "Password:" not in output and output[-1] != ">":
                output += w713_handle.stdout.read(1).decode("utf-8")
            if 'new wallet' in output:
                return("You must initialize your wallet first")
            password = self.wallet_pass + '\n'
            w713_handle.stdin.write(password.encode())
            w713_handle.stdin.write("help\n".encode())
            output = w713_handle.stdout.read(1).decode("utf-8")
            while w713_handle.poll() is None and output[-10:] != 'wallet713>':
                output += w713_handle.stdout.read(1).decode("utf-8")
            if w713_handle.poll() is not None:
                output += w713_handle.stdout.read().decode("utf-8")
                return("Wallet test failed with output: {}".format(output))
            self.wallet713_cmd = self.wallet713_cmd
        except PermissionError as e:
            return "Wallet test failed with output: {}".format(str(e))
        except Exception as e:
            err = w713_handle.stderr.read().decode("utf-8")
            if "error" in err or "Error" in err:
                return "Wallet test failed with: {}".format(err)
            else:
                return "Wallet test failed with error: {}".format(str(e))

    def sign_slate_with_wallet713_cli(self):
        ##
        # Call the wallet713 command and use "expect"-like text processing to
        # sign the slate file
        try:
            w713_handle = subprocess.Popen(self.wallet713_cmd,
                                           stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE,
                                           bufsize=0)
            output = w713_handle.stdout.read(1).decode("utf-8")
            while "Password:" not in output and output[-1] != ">":
                output += w713_handle.stdout.read(1).decode("utf-8")
            if 'new wallet' in output:
                return("You must initialize your wallet first")
            password = self.wallet_pass + '\n'
            w713_handle.stdin.write(password.encode())
            receive_cmd = "receive {}\n".format(self.unsigned_slatefile)
            w713_handle.stdin.write(receive_cmd.encode())
            time.sleep(2)
            output = w713_handle.stdout.read(1).decode("utf-8")
            while w713_handle.poll() is None and output[-10:] != 'wallet713>':
                output += w713_handle.stdout.read(1).decode("utf-8")
            for line in output.split("\n"):
                if "Error" in line:
                    err = line.split(' ', 1)
                    return("Slate receive failed with: {}".format(err[1]))
            w713_handle.stdin.write("exit\n".encode())
            count = 0
            while w713_handle.poll() is None and count < 50:
                time.sleep(0.1)
                count += 1
            if count >= 50:
                return("Slate receive failed")
            with open(self.signed_slatefile, 'r') as tx_slate_response:
                self.signed_slate = tx_slate_response.read()
        except Exception as e:
            err = w713_handle.stderr.read().decode("utf-8")
            if "error" in err or "Error" in err:
                return "Slate receive failed with error: {}".format(err)
            else:
                return "Slate receive failed with error {}".format(str(e))


    def return_payment_slate(self):
        ##
        # Submit the signed slate back to the pool to be finalized and posted to the network
        submit_tx_slate_url = self.mwURL + "/pool/payment/submit_tx_slate/" + self.user_id
        r = requests.post(
                url = submit_tx_slate_url,
                data = self.signed_slate,
                auth = (self.username, self.password),
        )
        if r.status_code != 200:
            return "Failed to submit signed slate - {}".format(r.text)

    ##
    # Get Payout using local grin wallet
    def run_grin_wallet(self):
        if self.args.wallet_pass is None:
            self.wallet_pass = getpass.getpass("   Wallet Password: ")
            self.prompted = True
        else:
            self.wallet_pass = self.args.wallet_pass
    
        # Cleanup
        self.clean_slate_files()
    
        # Find wallet Command
        self.print_progress("Locating your grin wallet command");
        message = self.find_grin_wallet()
        if self.wallet_cmd is None:
            self.error_exit(message)
        message = self.test_grin_wallet()
        if message is not None:
            self.error_exit(message)
        self.print_success()

	# Find User ID 
        self.print_progress("Getting your pool User ID");
        message = self.get_user_id()
        if self.user_id is None:
            self.error_exit(message)
        self.print_success()

#        # Check for existing slates and ask if we should process it
#        if os.path.exists(self.signed_slatefile):
#            xxx
    
        # Find balance
        self.print_progress("Getting your Avaiable Balance");
        message = self.get_balance()
        if self.balance == None:
            self.error_exit(message)
        self.print_success(self.balance)
        # Only continue if there are funds available
        if self.balance < self.POOL_MINIMUM_PAYOUT:
            self.error_exit("Insufficient Available Balance for payout: Minimum: {}, Available: {}".format(self.POOL_MINIMUM_PAYOUT, self.balance))

        # Get payment slate from Pool
        self.print_progress("Requesting a Payment from the pool");
        message = self.get_unsigned_slate()
        if self.unsigned_slate is None:
            self.error_exit(message)
        # Write the slate to file
        message = self.write_unsigned_slate_file()
        if not os.path.isfile(self.unsigned_slatefile):
            self.error_exit(message)
        self.print_success()

        # Call grin wallet to receive the slate and sign it
        self.print_progress("Processing the payment with your wallet")
        message = self.sign_slate_with_wallet_cli()
        if message is not None:
            self.error_exit(message)
        self.print_success()

        # Return the signed slate to the pool
        self.print_progress("Returning the signed payment slate to the pool");
        message = self.return_payment_slate()
        if message is not None:
            self.error_exit(message)
        self.print_success()

        # Cleanup
        self.clean_slate_files()


    ##
    # Get Payout using local wallet713
    def run_wallet713(self):
        if self.args.wallet_pass is None:
            self.wallet_pass = getpass.getpass("   Wallet Password: ")
            self.prompted = True
        else:
            self.wallet_pass = self.args.wallet_pass
    
        # Cleanup
        self.clean_slate_files()
    
        # Find wallet Command
        self.print_progress("Locating your wallet713 command");
        message = self.find_wallet713()
        if self.wallet713_cmd is None:
            self.error_exit(message)
        message = self.test_wallet713()
        if message is not None:
            self.error_exit(message)
        self.print_success()

	# Find User ID 
        self.print_progress("Getting your pool User ID");
        message = self.get_user_id()
        if self.user_id is None:
            self.error_exit(message)
        self.print_success()

#        # Check for existing slates and ask if we should process it
#        if os.path.exists(self.signed_slatefile):
#            xxx
    
        # Find balance
        self.print_progress("Getting your Avaiable Balance");
        message = self.get_balance()
        if self.balance == None:
            self.error_exit(message)
        self.print_success(self.balance)
        # Only continue if there are funds available
        if self.balance < self.POOL_MINIMUM_PAYOUT:
            self.error_exit("Insufficient Available Balance for payout: Minimum: {}, Available: {}".format(self.POOL_MINIMUM_PAYOUT, self.balance))

        # Get payment slate from Pool
        self.print_progress("Requesting a Payment from the pool");
        message = self.get_unsigned_slate()
        if self.unsigned_slate is None:
            self.error_exit(message)
        # Write the slate to file
        message = self.write_unsigned_slate_file()
        if not os.path.isfile(self.unsigned_slatefile):
            self.error_exit(message)
        self.print_success()

        # Call grin wallet to receive the slate and sign it
        self.print_progress("Processing the payment with your wallet")
        message = self.sign_slate_with_wallet713_cli()
        if message is not None:
            self.error_exit(message)
        self.print_success()

        # Return the signed slate to the pool
        self.print_progress("Returning the signed payment slate to the pool");
        message = self.return_payment_slate()
        if message is not None:
            self.error_exit(message)
        self.print_success()

        # Cleanup
        self.clean_slate_files()



    ##
    # Get Payout using grin++ wallet
    def run_grinplusplus_wallet(self):
        if self.args.wallet_user is None:
            self.wallet_user = input("   Wallet Username: ")
            self.prompted = True
        else:
            self.wallet_user = self.args.wallet_user

        if self.args.wallet_pass is None:
            self.wallet_pass = getpass.getpass("   Wallet Password: ")
            self.prompted = True
        else:
            self.wallet_pass = self.args.wallet_pass
    
        # Cleanup
        self.clean_slate_files()
    
        # Test Wallet API
        self.print_progress("Testing your Grin++ wallet API");
        message = self.test_grinplusplus_wallet()
        if message is not None:
            self.error_exit(message)
        self.print_success()

        # Log into Wallet Account
        self.print_progress("Logging in to your Grin++ wallet");
        message = self.login_grinplusplus_wallet()
        if message is not None:
            self.error_exit(message)
        self.print_success()

	# Find User ID 
        self.print_progress("Getting your pool User ID");
        message = self.get_user_id()
        if self.user_id is None:
            self.error_exit(message)
        self.print_success()

#        # Check for existing slates and ask if we should process it
#        if os.path.exists(self.signed_slatefile):
#            xxx
    
        # Find balance
        self.print_progress("Getting your Avaiable Balance");
        message = self.get_balance()
        if self.balance == None:
            self.error_exit(message)
        self.print_success(self.balance)
        # Only continue if there are funds available
        if self.balance < self.POOL_MINIMUM_PAYOUT:
            self.error_exit("Insufficient Available Balance for payout: Minimum: {}, Available: {}".format(self.POOL_MINIMUM_PAYOUT, self.balance))

        # Get payment slate from Pool
        self.print_progress("Requesting a Payment from the pool");
        message = self.get_unsigned_slate()
        if self.unsigned_slate is None:
            self.error_exit(message)
        # Write the slate to file
        message = self.write_unsigned_slate_file()
        if not os.path.isfile(self.unsigned_slatefile):
            self.error_exit(message)
        self.print_success()

        # Call Grin++ wallet to receive the slate and sign it
        self.print_progress("Processing the payment with your wallet")
        message = self.sign_slate_with_grinplusplus_wallet_api()
        if message is not None:
            self.error_exit(message)
        self.print_success()

        # Return the signed slate to the pool
        self.print_progress("Returning the signed payment slate to the pool");
        message = self.return_payment_slate()
        if message is not None:
            self.error_exit(message)
        self.print_success()

        # Cleanup
        self.clean_slate_files()

        # Log out of wallet
        self.print_progress("Logging out of your Grin++ wallet");
        message = self.logout_grinplusplus_wallet()
        if message is not None:
            self.error_exit(message)
        self.print_success()



    ##
    # Get Payout using slate
    def run_slate(self):
	# Find User ID 
        self.print_progress("Getting your pool User ID");
        message = self.get_user_id()
        if self.user_id is None:
            self.error_exit(message)
        self.print_success()
    
        # Check for existing signed slate and ask if we should process it
        if os.path.exists(self.signed_slatefile):
            #print("xxx: loading {}".format(self.signed_slatefile))
            try:
                with open(self.signed_slatefile, 'r') as tx_slate_response:
                    content = tx_slate_response.read().rstrip()
                    json.loads(content)
                self.signed_slate = content
            except:
                #print("xxx: Failed to load valid json: {}".format(content))
                pass
        if self.signed_slate is not None:
            options = {
                    "y": "Yes",
                    "n": "No",
                }
            choice = self.prompt_menu("Found a signed slate file.  Process it?", options, "y")
            print(" ")
            if choice == "Yes":
                # Return the signed slate to the pool
                self.print_progress("Returning the signed payment slate to the pool");
                message = self.return_payment_slate()
                if message is not None:
                    self.error_exit(message)
                self.print_success()

                # Cleanup
                self.clean_slate_files()
                return
            else:
                self.signed_slate = None

        # Check for existing unsigned slate and ask if we should process it
        if os.path.exists(self.unsigned_slatefile):
            try:
                with open(self.unsigned_slatefile, 'r') as tx_slate:
                    content = tx_slate.read().rstrip()
                json.loads(content)
                self.unsigned_slate = content
            except:
                self.clean_slate_files()
        if self.unsigned_slate is not None:
            options = {
                    "y": "Yes",
                    "n": "No",
                }
            choice = self.prompt_menu("Found a unsigned slate file.  Process it?", options, "y")
            print(" ")
            if choice == "No":
                self.unsigned_slate = None
                self.clean_slate_files()

        # Find balance
        if self.unsigned_slate is None:
            self.print_progress("Getting your Avaiable Balance");
            message = self.get_balance()
            if self.balance == None:
                self.error_exit(message)
            self.print_success(self.balance)
            # Only continue if there are funds available
            if self.balance < self.POOL_MINIMUM_PAYOUT:
                self.error_exit("Insufficient Available Balance for payout: Minimum: {}, Available: {}".format(self.POOL_MINIMUM_PAYOUT, self.balance))

            # Get payment slate from Pool
            self.print_progress("Requesting a Payment from the pool");
# XXX UNCOMMENT
#            self.unsigned_slate = "{this is the unsigned slate}"
            message = self.get_unsigned_slate()
            if self.unsigned_slate is None:
                self.error_exit(message)
            # Write the slate to file
            message = self.write_unsigned_slate_file()
            if not os.path.isfile(self.unsigned_slatefile):
                self.error_exit(message)
            self.print_success()
            print(" ")
            self.print_progress("Payment slate file written to")
            self.print_success("{}".format(self.unsigned_slatefile))

#        # Prompt for user to: print unsigned slate, paste in signed slate or for response filename
#        options = {
#                "y": "Yes",
#                "n": "No",
#            }
#        choice = self.prompt_menu("Print the payment slate to screen?", options, "y")
#        print(" ")
#        if choice == "Yes":
#            print("# -------------------------------------- ")
#            print("{}".format(self.unsigned_slate))
#            print("# -------------------------------------- ")

        # Get the signed slate
        while self.signed_slate is None:
            print(" ")
#            self.print_indent("Paste the signed slate response JSON now, or enter the filename containing the response JSON:")
            self.print_indent("Enter the filename with signed slate response:", 1, False)
            print(" ")
            choice = input("")
            if os.path.exists(choice):
                try:
                    with open(choice, 'r') as tx_slate_response:
                        content = tx_slate_response.read()
                    json.loads(content)
                    self.signed_slate = content
                except:
                    self.error("Invalid slate, please try again")
#            else:
#                try:
#                    json.loads(choice)
#                    self.signed_slate = choice.rstrip()
#                except:
#                    self.error("Invalid slate, please try again")
#        fh = open(self.signed_slatefile, "w")
#        fh.write(self.signed_slate)

        # Return the signed slate to the pool
        self.print_progress("Returning the signed payment slate to the pool");
        message = self.return_payment_slate()
        if message is not None:
            self.error_exit(message)
        self.print_success()

        # Cleanup
        self.clean_slate_files()
    


    def run(self):
        ##
        # Get configuration - either from commandline or by prompting the user
        parser = argparse.ArgumentParser()
        parser.add_argument("--payout_method", help="Which payout method to use: {}".format(self.payout_methods))
        parser.add_argument("--pool_user", help="Username on {}".format(self.poolname))
        parser.add_argument("--pool_pass", help="Password on {}".format(self.poolname))
        parser.add_argument("--wallet_user", help="Your grin++ wallet username")
        parser.add_argument("--wallet_pass", help="Your grin wallet password")
        self.args = parser.parse_args()
    
        self.print_banner()
    
        ##
        # Process commandline Arguments
        if self.args.payout_method is None:
            payout_method_options = {}
            index = 1
            for method in self.payout_methods:
                payout_method_options[str(index)] = method
                index += 1
            self.payout_method = self.prompt_menu("Choose a method of payment:", payout_method_options, "1")
            self.prompted = True
        else:
            self.payout_method = self.args.payout_method

        if self.prompted:
            print(" ")
    
        self.print_indent("** Requesting a payment from the pool using method: {}".format(self.payout_method))

        if self.prompted:
            print(" ")
    
        if self.args.pool_user is None:
            self.username = input("   {} Username: ".format(self.poolname))
            self.prompted = True
        else:
            self.username = self.args.pool_user
    
        if self.args.pool_pass is None:
            self.password = getpass.getpass("   {} Password: ".format(self.poolname))
            self.prompted = True
        else:
            self.password = self.args.pool_pass
    
        if self.prompted:
            print(" ")
    

        ##
        # Execute the requested payment method
        if self.payout_method == "Grin Wallet" or self.payout_method == "BitGrin Wallet":
            self.run_grin_wallet()
        elif self.payout_method == "Grin++ Wallet":
            self.run_grinplusplus_wallet()
        elif self.payout_method == "Wallet713":
            self.run_wallet713()
        elif self.payout_method == "Slate Files":
            self.run_slate()
        else:
            self.error_exit("Invalid payout method requested: {}".format(self.payout_method))

        # Done
        self.print_footer()



if __name__ == "__main__":
    # Disable "bracketed paste mode"
    try:
        os.system('printf "\e[?2004l"')
    except:
        pass

    payout = Pool_Payout()
    payout.run()
    sys.exit(0)

