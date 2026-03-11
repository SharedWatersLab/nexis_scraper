from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys 
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.common.exceptions import ElementNotInteractableException

import os
import sys
import pandas as pd
import time
import getpass

import tempfile
import uuid

# this all just to get the paths correct for the imports
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), '..')))
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

#from driverTest import SetupDriver  # noqa: E402

class PasswordManager:
    def __init__(self):
        # initialize the password attribute to None
        self.password = None

    def get_password(self):
        # Check if the password is already set
        if self.password is None:
            # Prompt for the password and store it
            self.password = getpass.getpass()
        # Return the stored password
        return self.password

class WebDriverManager:
    def __init__(self):
        self.driver = None
        self.options = ChromeOptions()
        self.setup_options()
        
        # Use webdriver_manager for automatic driver version management
        driver_path = ChromeDriverManager().install()
        self.service = Service(driver_path)
    
    def setup_options(self):
        self.options = webdriver.ChromeOptions()
        self.options.page_load_strategy = 'normal'
        self.options.add_argument("--start-maximized")
        #self.options.add_argument("user-data-dir=/tmp/storedLoginInformation")  
            
        temp_dir = tempfile.mkdtemp(prefix=f"chrome_profile_{uuid.uuid4().hex[:8]}_")
        self.options.add_argument(f"user-data-dir={temp_dir}")

        # disable GCM/push notifications
        self.options.add_argument("--disable-background-networking")
        self.options.add_argument("--disable-background-timer-throttling")
        self.options.add_argument("--disable-backgrounding-occluded-windows")
        self.options.add_argument("--disable-push-messaging")
        self.options.add_argument("--disable-notifications")

        self.options.add_argument("--disable-logging")
        self.options.add_argument("--log-level=3")  # Only fatal errors

        # disable bounce tracking protection
        self.options.add_argument('--disable-blink-features=AutomationControlled')
        self.options.add_argument('--disable-features=BounceTrackingMitigations')
        self.options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.options.add_experimental_option('useAutomationExtension', False)

        prefs = {'download.prompt_for_download': False}
        self.options.add_experimental_option('prefs', prefs)   
    
    def start_driver(self):
        if not self.driver:
            self.driver = webdriver.Chrome(service=self.service, options=self.options)
        return self.driver

    def stop_driver(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

class Login:
    def __init__(self, user_name, password, driver_manager= WebDriverManager, timeout=20, url=None):
        self.driver_manager = driver_manager
        self.driver = driver_manager.start_driver() 
        self.user_name = user_name
        self.password = password
        self.url = url
        self.timeout = timeout

    def _click_from_css(self, css_selector):
        element = WebDriverWait(self.driver, self.timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, css_selector))
        )
        element.click()
    
    def _send_keys_from_css(self, css_selector, keys):
        element = WebDriverWait(self.driver, self.timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, css_selector))
        )
        element.send_keys(keys)

    def _is_element_present_css(self, css_selector):
        try:
            self.driver.find_element_by_css_selector(css_selector)
            return True
        except NoSuchElementException:
            return False
    
    # def reset(self):
    #     self.number += 1 # self.number = self.number + 1
    #     self.temp_foldername = "storedLoginInformation" + str(self.number)

    def login_page(self):
        
        try:
            # First check which elements are present

            bama_element = 'body > div.content > div > div.col1 > div.mybama-login > a'
            self._click_from_css(bama_element)
            print("logging in with myBama credentials")
            
            time.sleep(3)
            print("entering login information")
            self._send_keys_from_css("#username", self.user_name)
            self._send_keys_from_css("#password", self.password)
            self._click_from_css("#login-form-controls > div > button > span")
            
            #print("Entered Tufts username and password")
            print("Entered UA username and password")
            time.sleep(3)
            
            return True
            
        except TimeoutException:
            print("No login page variant detected")
            return False

    def _init_login(self):
        
        loggedin_home = 'https://login.libdata.lib.ua.edu/login?qurl=http%3a%2f%2fwww.nexisuni.com'
        self.driver.get(self.url or loggedin_home)
        time.sleep(5)
        
        try:
            loggedin_element = "co-branding-display-name" # class name
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, loggedin_element)))
            print("User is already logged in.")
        except TimeoutException:
            print("User is not logged in. Proceeding with login...")
            try:
                self.login_page()
            
            #in case update chrome page comes up
                try:
                    update_chrome_substring = "https://api-58712eef.duosecurity.com/frame/frameless/v4/auth?sid=frameless-"
                    if update_chrome_substring in self.driver.current_url:
                        self._click_from_css("body > div > div > div > div.display-flex.flex-direction-column.flex-value-one.size-padding-left-large.size-padding-right-large > div > button")
                        print("skipped update chrome page")
                    else:
                        pass

                except NoSuchElementException:
                    print("update chrome page not prompted")
                    pass

                self.duo_page_substring = "duosecurity.com/frame/v4/auth/prompt?sid=frameless-"
                if self.duo_page_substring in self.driver.current_url:
                    print("DUO authentication prompted")
                    self.handle_duo_2fa()
                    time.sleep(2)

                    if self.handle_duo_2fa():
                        print("DUO authentication successful")
                    else:
                        print("DUO authentication failed")
                        return False  # Exit the method if DUO fails
                else:
                    #print("DUO authentication not prompted")
                    pass

                time.sleep(5)
                # then this clicks reload if we're not brought to the home page
                self.handle_reload_error()
                # this might be a good place to also test out if it arrived to the correct home page.
                time.sleep(5)

            except TimeoutException:
                pass

    def handle_duo_2fa(self):
        max_attempts = 2
        attempt = 0

        while attempt < max_attempts:
            try:
                if self.duo_page_substring in self.driver.current_url:
                    print('DUO push code to device')
                    time.sleep(10)  # Reduced initial wait time

                    try:
                        self._click_from_css("#trust-browser-button")
                        print("DUO push entered, skipping trust browser page")
                        time.sleep(2)
                    except: NoSuchElementException
                    
                    if self.duo_page_substring not in self.driver.current_url:
                        #print("DUO authentication completed")
                        return True
                    
                    else:
                    
                        if self.duo_page_substring in self.driver.current_url:
                            other_options_selector = "#auth-view-wrapper > div:nth-child(2) > div.row.display-flex.other-options-link.align-flex-justify-content-center.size-margin-bottom-large.size-margin-top-small"
                            print("waited for push, now calling")
                            self._click_from_css(other_options_selector)
                                
                            DUO_phone_call = 'body > div > div > div.card.card--white-label.uses-white-label-border-color.display-flex.flex-direction-column > div > div.all-auth-methods.display-flex.flex-value-one > ul > li:nth-child(2) > a > span.method-select-chevron > svg'
                            self._click_from_css(DUO_phone_call)
                            print('DUO calling')
                            time.sleep(20)

                            try:
                                self._click_from_css("#trust-browser-button")
                                print("skipping trust browser page")
                            except: NoSuchElementException
                            
                            if self.duo_page_substring not in self.driver.current_url:
                                print("DUO authentication completed")
                                return True
                    
                # Check if we're still on the DUO page after waiting
                if self.duo_page_substring not in self.driver.current_url:
                    print("DUO authentication successful")
                    break

                else:
                    pass   
                
            except NoSuchElementException:
                print(f"An element was not found during attempt {attempt + 1}")
            
            attempt += 1
        
        if attempt == max_attempts:
            print("Failed to complete DUO authentication after maximum attempts")
            return False

        return True
    
    def handle_reload_error(self, timeout=10):
        try:
            # Wait for the element to be clickable
            reload_error = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((By.ID, "reload-button"))
            )
            # If the element is found and clickable, click it
            reload_error.click()
            print("Reload button found and clicked")
            return True
        except TimeoutException:
            print("login successful")
            return False
