from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
# is all this above only useful in full process?

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.keys import Keys 
from datetime import datetime

from selenium.common.exceptions import (
    StaleElementReferenceException, TimeoutException, 
    ElementClickInterceptedException, ElementNotInteractableException, 
    NoSuchElementException)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import Select
from pathlib import Path

import pandas as pd
import time
import sys
import os
import re

from classes.LoginClass import Login
from classes.SearchClass import Search


class DownloadFailedException(Exception):
    def __init__(self, message="Download persistently failing to complete"):
        self.message = message
        super().__init__(self.message)

class Download:

    def __init__(self, driver, basin_code, username, login, search, download_folder: str, download_folder_temp, finished, url=None, timeout=20):

        self.driver = driver
        self.basin_code = basin_code
        self.username = username
        self.login = login
        self.search = search
        self.finished = finished 
        self.url = url
        self.timeout = timeout
        self.download_folder = download_folder
        self.download_folder_temp = download_folder_temp

    
    def _click_from_xpath(self, xpath):
        try:
            element = WebDriverWait(self.driver, self.timeout).until(
                EC.element_to_be_clickable((By.XPATH, xpath)))
            element.click()
        except TimeoutException:
            raise NoSuchElementException(f"Element with xpath '{xpath}' not found")

    def _send_keys_from_xpath(self, xpath, keys):
        wait = WebDriverWait(self.driver, self.timeout)
        element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath))) 
        self.driver.execute_script("arguments[0].scrollIntoView();", element)
        element.send_keys(keys)

    def _click_from_css(self, css_selector):
        try:
            element = WebDriverWait(self.driver, self.timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, css_selector))
            )
            element.click()
        except TimeoutException:
            raise NoSuchElementException(f"Element with selector '{css_selector}' not found")

       
    def _send_keys_from_css(self, css_selector, keys):
        element = WebDriverWait(self.driver, self.timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, css_selector))
        )
        element.send_keys(keys)

    def open_timeline(self):
        timeline_button = '#podfiltersbuttondatestr-news' # this is CSS selector
        self._click_from_css(timeline_button)
        time.sleep(10)
        # if we need to try with XPath
        #timeline_button = WebDriverWait(self.driver, self.timeout).until(EC.element_to_be_clickable((By.XPATH, "/html/body/main/div/main/ln-gns-resultslist/div[2]/div/div[1]/div[1]/div[2]/div/aside/button[2]")))
        #timeline_button.click()
        #time.sleep(5)

    def parse_date(self, date_string):
        date_formats = [
            '%m/%d/%y',  # 8/1/08
            '%m/%d/%Y',  # 8/1/2008
            '%Y-%m-%d',  # 2008-08-01
            '%d-%m-%Y',  # 01-08-2008
            '%Y/%m/%d',  # 2008/08/01
            # Add more formats as needed
        ]
        
        for date_format in date_formats:
            try:
                return datetime.strptime(date_string, date_format)
            except ValueError:
                continue
        
        # If no format worked, raise an error
        raise ValueError(f"Unable to parse date string: {date_string}")

    def group_duplicates(self):
        actions_dropdown_xpath = "//button[@id='resultlistactionmenubuttonhc-yk' and text()='Actions']"
        time.sleep(5)
        self._click_from_xpath(actions_dropdown_xpath)
        time.sleep(5)
        moderate_button = "//button[contains(@class, 'action') and @data-action='changeduplicates' and @data-value='moderate']"
        high_button = "//button[contains(@class, 'action') and @data-action='changeduplicates' and @data-value='high']"
        duplicates_button = moderate_button # changed this August 2025
        self._click_from_xpath(duplicates_button)
        print("group duplicate results")
        time.sleep(10)

    def handle_popups(self, max_popups=5):
        # Counter to prevent infinite loops
        popups_closed = 0
        
        # A collection of common popup identifiers
        popup_patterns = [
            # Pendo popups with various IDs
            #"//button[contains(@class, '_pendo-close-guide') and contains(@id, 'pendo-close-guide')]", # analytics, from july 2024 not there anymore
            "//button[contains(@class, 'pendo-close-guide')]",
            "//button[contains(@id, 'pendo-close-guide')]",
            "//div[contains(@id, 'pendo-guide-container')]//button[contains(@aria-label, 'Close')]",
            
            # General close buttons for popups/modals
            "//button[@aria-label='Close']",
            "//button[contains(@class, 'close')]",
            "//*[contains(@class, 'modal')]//button[contains(@class, 'close')]",
            "//div[contains(@class, 'popup')]//button",
            "//div[contains(@class, 'modal')]//button",
            
            # Common close icons
            "//*[contains(@class, 'close-icon')]",
            "//i[contains(@class, 'fa-times')]",
            "//span[contains(@class, 'close')]",
            
            # X buttons (common in popups)
            "//button[text()='✕' or text()='×' or text()='X' or text()='x']",
            "//*[text()='✕' or text()='×' or text()='X' or text()='x']"
        ]
        
        while popups_closed < max_popups:
            found_popup = False
            
            # First check if any popups are visible
            for pattern in popup_patterns:
                try:
                    # Find all elements matching the pattern
                    elements = self.driver.find_elements(By.XPATH, pattern)
                    
                    for element in elements:
                        try:
                            if element.is_displayed():
                                # Try scrolling to make sure it's in view
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                                time.sleep(0.5)
                                
                                # Try different click methods
                                try:
                                    element.click()
                                except:
                                    try:
                                        self.driver.execute_script("arguments[0].click();", element)
                                    except:
                                        try:
                                            ActionChains(self.driver).move_to_element(element).click().perform()
                                        except:
                                            continue
                                
                                print(f"Closed popup using pattern: {pattern}")
                                found_popup = True
                                popups_closed += 1
                                time.sleep(1)  # Short wait after closing a popup
                                break  # Break the inner loop after closing one popup
                        except:
                            continue
                    
                    if found_popup:
                        break  # Break the outer loop to restart from the beginning
                        
                except Exception as e:
                    continue
            
            # If no popup was found and closed, we're done
            if not found_popup:
                break
        
        print(f"Total popups closed: {popups_closed}")
        return popups_closed
    
    def sort_by_date(self):
        sortby_dropdown_css = '#select'
        oldestnewest_option_text = 'Date (oldest-newest)'

        for attempt in range(3):  # Try up to 3 times
            try:
                # Check for and close popup before interacting with dropdown
                self.handle_popups()

                # Wait for the dropdown to be clickable
                dropdown = WebDriverWait(self.driver, 20).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, sortby_dropdown_css))
                )
                
                # Use Select class to interact with the dropdown
                select = Select(dropdown)
                select.select_by_visible_text(oldestnewest_option_text)
                
                print("Selected 'Date (oldest-newest)' option")
                time.sleep(5)  # Wait for the page to update

                return  # Success, exit the function
                
            except StaleElementReferenceException:
                print("Stale element, retrying...")
                time.sleep(2)
                continue
                
            except (TimeoutException, NoSuchElementException):
                print(f"Attempt {attempt + 1}: Can't find sort-by dropdown, refreshing the page")
                self.driver.refresh()
                time.sleep(5)
                continue
                
            except ElementClickInterceptedException:
                print("Popup is in the way, attempting to close it")
                self.handle_popups()
                continue
                
            except ElementNotInteractableException:
                print("Element not interactable, attempting to close popup if present")
                self.handle_popups()
                continue
        
        print("Failed to sort by date after multiple attempts")

    def DownloadSetup(self):
        self.group_duplicates()
        self.sort_by_date()

    def get_result_count(self, max_attempts=4):
        """
        Resilient function to get result count that handles:
        - Attribute name variations (with/without spaces)
        - Multiple possible element structures  
        - Timing issues with large result sets
        - Future website changes
        """
        # doubled all timeouts in this method

        for attempt in range(max_attempts): 
            try:
                #time.sleep(2)
                #print(f"Attempt {attempt + 1} to get result count...")
                
                # Wait for page to be fully loaded and stable
                WebDriverWait(self.driver, 40).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
                
                # Additional wait for any JavaScript to finish (especially important for large result sets)
                time.sleep(2)
                
                # Try to wait for network activity to settle (helps with large result sets)
                try:
                    WebDriverWait(self.driver, 20).until(
                        lambda d: d.execute_script("return jQuery.active == 0") if d.execute_script("return typeof jQuery !== 'undefined'") else True
                    )
                except:
                    pass  # jQuery might not be available
                
                # Focus on the core strategies that matter for the data-actualresultscount attribute
                strategies = [
                    # Strategy 1: Original specific selector with attribute variations
                    {
                        "name": "Original CSS selector",
                        "method": "css_with_attributes",
                        "selector": "#sidebar > div.search-controls > div.content-type-container.isBisNexisRedesign > ul > li.active",
                        "attributes": ["data-actualresultscount", " data-actualresultscount", "data-actualresultscount ", " data-actualresultscount "]
                    },
                    
                    # Strategy 2: More generic CSS selector
                    {
                        "name": "Generic li.active selector",
                        "method": "css_with_attributes", 
                        "selector": "li.active",
                        "attributes": ["data-actualresultscount", " data-actualresultscount", "data-actualresultscount ", " data-actualresultscount "]
                    },
                    
                    # Strategy 3: JavaScript-based extraction (most reliable for dynamic content)
                    {
                        "name": "JavaScript extraction",
                        "method": "javascript"
                    }
                ]
                
                result_count = None
                successful_strategy = None
                
                for strategy in strategies:
                    try:
                        if strategy["method"] == "css_with_attributes":
                            elements = self.driver.find_elements(By.CSS_SELECTOR, strategy["selector"])
                            for element in elements:
                                if element.is_displayed():
                                    for attr in strategy["attributes"]:
                                        try:
                                            value = element.get_attribute(attr)
                                            if value and value.strip() and value.strip().isdigit():
                                                result_count = int(value.strip())
                                                successful_strategy = f"{strategy['name']} - attribute: '{attr}'"
                                                break
                                        except:
                                            continue
                                    if result_count:
                                        break
                        
                        elif strategy["method"] == "javascript":
                            # Use JavaScript to search for the element and attribute
                            js_script = """
                            // Function to wait for the attribute to be populated
                            function waitForResultCount(maxWait = 15000) {
                                return new Promise((resolve) => {
                                    const startTime = Date.now();
                                    
                                    function checkForCount() {
                                        // Try multiple approaches to find the result count
                                        var possibleSelectors = [
                                            '#sidebar > div.search-controls > div.content-type-container.isBisNexisRedesign > ul > li.active',
                                            'li.active',
                                            'li[class*="active"]'
                                        ];
                                        
                                        for (var i = 0; i < possibleSelectors.length; i++) {
                                            var element = document.querySelector(possibleSelectors[i]);
                                            if (element) {
                                                var attrs = ['data-actualresultscount', ' data-actualresultscount', 'data-actualresultscount ', ' data-actualresultscount '];
                                                for (var j = 0; j < attrs.length; j++) {
                                                    var value = element.getAttribute(attrs[j]);
                                                    if (value && value.trim() && !isNaN(parseInt(value.trim()))) {
                                                        resolve({
                                                            value: parseInt(value.trim()), 
                                                            selector: possibleSelectors[i], 
                                                            attribute: attrs[j]
                                                        });
                                                        return;
                                                    }
                                                }
                                            }
                                        }
                                        
                                        // If not found and we haven't exceeded max wait time, try again
                                        if (Date.now() - startTime < maxWait) {
                                            setTimeout(checkForCount, 500);
                                        } else {
                                            resolve(null);
                                        }
                                    }
                                    
                                    checkForCount();
                                });
                            }
                            
                            return waitForResultCount();
                            """
                            
                            js_result = self.driver.execute_script(js_script)
                            if js_result and js_result.get('value'):
                                result_count = js_result['value']
                                successful_strategy = f"{strategy['name']} - {js_result.get('selector')} with attribute '{js_result.get('attribute')}'"
                        
                        if result_count:
                            print(f"Successfully found result count: {result_count} using {successful_strategy}")
                            self.result_count = result_count
                            return result_count
                            
                    except Exception as e:
                        print(f"Strategy '{strategy['name']}' failed")
                        continue
                
                if result_count:
                    # Validate the result count makes sense (remove upper bound for large datasets)
                    if result_count > 0:
                        self.result_count = result_count
                        print(f"Final result count: {result_count:,}")  # Format with commas for readability
                        return self.result_count
                    else:
                        print(f"Result count {result_count} is not positive, treating as invalid")
                        result_count = None
                
                if result_count is None:
                    if attempt < max_attempts - 1:
                        if attempt == 0:
                            # First retry: just wait longer (common case)
                            print(f"No result count found on attempt {attempt + 1}, waiting longer and retrying...")
                            time.sleep(30)  # Longer wait for large result sets
                        elif attempt == 1:
                            # Second retry: refresh the page
                            print("Refreshing page to reload result count data...")
                            self.driver.refresh()
                            time.sleep(30)  # Wait for page to reload
                        else:
                            # Final retry: longer wait after refresh
                            print("Final attempt: waiting for backend processing to complete...")
                            time.sleep(60)
                    else:
                        print("Could not retrieve result count after all attempts.")
                        print("The element may exist but the data-actualresultscount attribute is not being populated.")
                        return None
                        
            except Exception as e:
                print(f"Attempt {attempt + 1} to get result count failed")
                if attempt < max_attempts - 1:
                    if attempt == 0:
                        print("First exception, waiting and retrying...")
                        time.sleep(10)
                    else:
                        print("Exception after previous attempts, refreshing page...")
                        self.driver.refresh()
                        time.sleep(10)
                else:
                    print("Max attempts reached due to exceptions.")
                    print("Could not retrieve result count - the data-actualresultscount attribute may not be populating.")
                    return None
        
        return None

    # def reset(self):
    #     sign_in_button = "//button[@id='SignInRegisterBisNexis']"
    #     try:
    #         self._click_from_xpath(sign_in_button)
    #         print("logging out")
    #     except ElementClickInterceptedException:
    #         find_sign_in = self.driver.find_element_by_xpath(sign_in_button)
    #         self.driver.execute_script("return arguments[0].scrollIntoView(true);", find_sign_in)        
    #     self.driver.delete_all_cookies()
    #     print("deleting cookies before logging in again")
    #     time.sleep(3)
    #     self.login._init_login()
    #     self.search.search_process(start_date, end_date)
    #     time.sleep(5)
    #     self.DownloadSetup()

    #  get_ranges as an instance method
    def get_ranges(self):
        """Get ranges based on result count and download limit"""
        # get full count from site
        full_count = self.get_result_count() 
        # hard-coding limit of 500 to it because that's the nexis uni limit for word full text
        download_limit = 500 

        # this generates a list of ranges that will be used in the download dialog box
        ranges = []
        for i in range(1, full_count, download_limit):
            end = min(i + (download_limit - 1), full_count)
            ranges.append(f"{i}-{end}")

        # this matches downloaded files to the ranges
        downloaded_ranges = [f.split("_")[-1].replace(".ZIP", "") for f in os.listdir(self.download_folder) if f.endswith(".ZIP")]

        # this compares those lists and creates a new list of ranges to be downloaded
        not_downloaded_ranges = []
        for r in ranges:
            if r in downloaded_ranges:
                continue
            # For final range, check if any downloaded range has same start number
            if r == ranges[-1]:
                start_num = r.split('-')[0]
                if any(dr.split('-')[0] == start_num for dr in downloaded_ranges):
                    continue
            not_downloaded_ranges.append(r)
        not_downloaded_ranges = sorted(not_downloaded_ranges, key=lambda x: int(x.split('-')[0]))
        return not_downloaded_ranges
    
    def check_for_download_restriction(self):
        """Monitor for the yellow download restriction banner that appears briefly"""
        try:
            # Create a MutationObserver using JavaScript to watch for the banner
            script = """
            return new Promise((resolve) => {
                const observer = new MutationObserver((mutations) => {
                    for (const mutation of mutations) {
                        for (const node of mutation.addedNodes) {
                            if (node.nodeType === Node.ELEMENT_NODE) {
                                // Look for any element that might contain error text
                                const text = node.textContent.toLowerCase();
                                if (text.includes("can't download") || 
                                    text.includes("cannot download") ||
                                    text.includes("download limit") ||
                                    text.includes("restricted")) {
                                    observer.disconnect();
                                    resolve({found: true, message: text});
                                    return;
                                }
                            }
                        }
                    }
                });
                
                // Watch the entire document for changes
                observer.observe(document.body, { childList: true, subtree: true });
                
                // Resolve after 5 seconds if nothing is found (shorter for retries)
                setTimeout(() => {
                    observer.disconnect();
                    resolve({found: false});
                }, 5000);
            });
            """
            result = self.driver.execute_script(script)
            return result
        except Exception as e:
            print(f"Error checking for download limit banner")
            return {"found": False}


    # Moving dialog methods into Download class
    def download_dialog(self, r):
        """Download dialog with multiple selector fallbacks and explicit state checks"""
        
        # Primary and fallback XPath/CSS selectors for the range input field
        range_field_selectors = [
            {"type": "xpath", "value": "//input[@id='SelectedRange']"},
            {"type": "xpath", "value": "//input[@name='SelectedRange']"},
            {"type": "css", "value": "input#SelectedRange"},
            {"type": "css", "value": "input[name='SelectedRange']"},
        ]
        
        # Primary and fallback selectors for download button
        download_btn_selectors = [
            {"type": "xpath", "value": "//button[@data-action='downloadopt' and @aria-label='Download']"},
            {"type": "xpath", "value": "//button[@data-action='downloadopt']"},
            {"type": "css", "value": "button[data-action='downloadopt']"},
        ]
        
        # Wait for page readiness
        try:
            WebDriverWait(self.driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            print("[WARNING] Page did not reach 'complete' state; proceeding anyway")
        
        # Step 1: Find and click download button
        download_btn = None
        for selector in download_btn_selectors:
            try:
                by_type = By.XPATH if selector["type"] == "xpath" else By.CSS_SELECTOR
                download_btn = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((by_type, selector["value"]))
                )
                break
            except TimeoutException:
                continue
        
        if not download_btn:
            raise TimeoutException("Could not find download button with any selector")
        
        # Clear any overlays before clicking
        self.handle_popups()
        
        # Click download button (with JS fallback)
        try:
            download_btn.click()
        except (ElementClickInterceptedException, ElementNotInteractableException):
            self.driver.execute_script("arguments[0].click();", download_btn)
        
        # Wait briefly for dialog to appear
        import time
        time.sleep(1)
        
        # Step 2: Find range input field with fallbacks
        range_element = None
        for selector in range_field_selectors:
            try:
                by_type = By.XPATH if selector["type"] == "xpath" else By.CSS_SELECTOR
                range_element = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((by_type, selector["value"]))
                )
                break
            except TimeoutException:
                continue
        
        if not range_element:
            try:
                self.driver.save_screenshot(f"error_range_field_{r}.png")
            except:
                pass
            raise TimeoutException(f"Range input field not found for range {r}")
        
        # Step 3: Ensure field is visible and clear it
        self.driver.execute_script("arguments[0].scrollIntoView(true);", range_element)
        time.sleep(0.5)
        
        # Clear field (triple-click + delete to ensure it's cleared)
        try:
            range_element.triple_click()
        except:
            range_element.send_keys(Keys.CONTROL + "a")
        
        range_element.send_keys(Keys.DELETE)
        time.sleep(0.3)
        
        # Step 4: Enter the range
        range_element.send_keys(str(r))
        time.sleep(1)


        # click MS word option
        MSWord_option = "//input[@type= 'radio' and @id= 'Docx']"
        self._click_from_xpath(MSWord_option)

        separate_files_option = "//input[@type= 'radio' and @id= 'SeparateFiles']"
        self._click_from_xpath(separate_files_option)

        # click on download
        download_button = "//button[@type='submit' and @class='button primary' and @data-action='download']"
        self._click_from_xpath(download_button)

    def wait_for_download(self, download_start_timeout=120, download_complete_timeout=400):
        """Wait for download to complete with better timeout handling"""
        start_time = time.time()
        
        try:
            # First, wait for UI indication that download started
            print("Waiting for download to start...")
            WebDriverWait(self.driver, download_start_timeout).until(
                EC.presence_of_element_located((By.ID, "delivery-popin"))
            )
            #print("Download started, processing...")
            elapsed_time = time.time() - start_time # want to check how long it takes when it works
            print(f"Download started after {elapsed_time:.2f} seconds, processing...")
            
        except TimeoutException as e:
            elapsed_time = time.time() - start_time
            print(f"Download did not start after {elapsed_time:.2f} seconds")
            raise DownloadFailedException
        
        try:
            # Wait for UI indication that browser finished
            WebDriverWait(self.driver, download_complete_timeout).until_not(
                EC.presence_of_element_located((By.ID, "delivery-popin"))
            )
            
            end_time = time.time()
            elapsed_time = end_time - start_time
            #print(f"Download completed in {elapsed_time:.2f} seconds") #
            # this is kind of a misleading printout, as sometimes UI popup presence changes but download did not complete
            # note: it might be nice to be able to detect what type of UI response appears, to determine whether a download occurred or not
            return True
            
        except TimeoutException as e:
            elapsed_time = time.time() - start_time
            print(f"Download started but didn't complete within {download_complete_timeout} seconds")
            print(f"Total elapsed time: {elapsed_time:.2f} seconds")
            # raise DownloadTimeoutException(
            #     f"Download timed out after {elapsed_time:.2f} seconds (started but didn't finish)"
            # )
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            print(f"Unexpected error during download: {str(e)}")
            print(f"Failed after {elapsed_time:.2f} seconds")
            raise  # Re-raise the unexpected exception

    
    def move_file(self, r):
        # Find matching file
        default_filename = [f for f in os.listdir(self.download_folder_temp) if re.match(r"Files \(\d+\)\.ZIP", f)]

        if default_filename:  # If we found any matching files
            print("Download completed!")
            # Use the first matching file
            default_download_path = os.path.join(self.download_folder_temp, default_filename[0])
            nexis_scraper_download_path = os.path.join(self.download_folder, f"{self.basin_code}_results_{r}.ZIP")

            # Check if file exists and move it
            if os.path.isfile(default_download_path):
                os.rename(default_download_path, nexis_scraper_download_path)
                print(f"moving file to {nexis_scraper_download_path}")

                
            # Wait for Box Drive to sync the file
            # self.wait_for_box_sync(nexis_scraper_download_path)

        else:
            print(f"file containing range {r} was not downloaded")
            raise DownloadFailedException

    def wait_for_box_sync(self, file_path, max_wait=30):
        """Wait for file to be fully synced to Box Drive"""
        print("Waiting for Box Drive sync...")
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                # File exists and has content, likely synced
                time.sleep(2)  # Small buffer for sync completion
                print("File synced to Box Drive!")
                return True
            time.sleep(1)
        
        print("Warning: Box sync may not be complete")
        return False


    def check_clear_downloads(self, r):
        """Check for and handle unsorted downloads"""
        # Find file matching pattern
        default_download_pattern = r"Files \(\d+\)\.ZIP"
        matching_files = [f for f in os.listdir(self.download_folder_temp) if re.match(default_download_pattern, f)]
        
        if matching_files:  # If any matching files found
            print("There's an unsorted file in downloads")
            self.create_unsorted_folder(r)
            self.move_unsorted(r, matching_files[0])  # Pass the filename to move_unsorted

    def create_unsorted_folder(self, r):
        """Create folder for unsorted downloads"""
        self.unsorted_folder = Path(f"{self.download_folder}/{self.basin_code}_unsorted")
        if not os.path.exists(self.unsorted_folder):
            print(f"Creating unsorted folder {self.unsorted_folder}")
            os.makedirs(self.unsorted_folder)

        print("+" * 48)
        print(f"Check unsorted download found in range {r}")
        print("+" * 48)

    def move_unsorted(self, r, original_filename):
        """Move unsorted files to the unsorted folder"""
        # Use the original file's full path
        original_path = os.path.join(self.download_folder_temp, original_filename)
        
        unsorted_filename = f"foundinrange_{r}.ZIP"
        unsorted_moved_path = os.path.join(self.unsorted_folder, unsorted_filename)
        
        os.rename(original_path, unsorted_moved_path)
        print(f"File {unsorted_filename} moved to {self.basin_code} download folder")