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
from classes.BaseClass import SeleniumBase


class DownloadFailedException(Exception):
    def __init__(self, message="Download persistently failing to complete"):
        self.message = message
        super().__init__(self.message)

class Download(SeleniumBase):

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
        # Button text changed from "Actions" to "More" in a Nexis Uni UI update — match by ID only
        actions_dropdown_xpath = "//button[@id='resultlistactionmenubuttonhc-yk']"
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

    # Nexis Uni stores result count in data-actualresultscount on the active content-type tab.
    # The attribute name sometimes has leading/trailing spaces (website inconsistency).
    _RESULT_COUNT_ATTRIBUTES = [
        "data-actualresultscount",
        " data-actualresultscount",
        "data-actualresultscount ",
        " data-actualresultscount ",
    ]
    _RESULT_COUNT_CSS_SELECTORS = [
        # Specific selector for the active tab in the sidebar filter panel
        "#sidebar > div.search-controls > div.content-type-container.isBisNexisRedesign > ul > li.active",
        # Broader fallback in case the sidebar structure changes
        "li.active",
    ]

    # JavaScript that polls the DOM for the result count attribute (handles delayed rendering)
    _RESULT_COUNT_JS = """
    function waitForResultCount(maxWait) {
        maxWait = maxWait || 15000;
        return new Promise(function(resolve) {
            var startTime = Date.now();
            var selectors = [
                '#sidebar > div.search-controls > div.content-type-container.isBisNexisRedesign > ul > li.active',
                'li.active',
                'li[class*="active"]'
            ];
            var attrs = ['data-actualresultscount', ' data-actualresultscount', 'data-actualresultscount ', ' data-actualresultscount '];

            function check() {
                for (var i = 0; i < selectors.length; i++) {
                    var el = document.querySelector(selectors[i]);
                    if (el) {
                        for (var j = 0; j < attrs.length; j++) {
                            var val = el.getAttribute(attrs[j]);
                            if (val && val.trim() && !isNaN(parseInt(val.trim()))) {
                                resolve({ value: parseInt(val.trim()), selector: selectors[i], attribute: attrs[j] });
                                return;
                            }
                        }
                    }
                }
                if (Date.now() - startTime < maxWait) {
                    setTimeout(check, 500);
                } else {
                    resolve(null);
                }
            }
            check();
        });
    }
    return waitForResultCount();
    """

    def _get_count_via_css(self):
        """Try reading the result count from known CSS selectors.

        Returns the count as an int, or None if not found.
        """
        for selector in self._RESULT_COUNT_CSS_SELECTORS:
            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
            for element in elements:
                if not element.is_displayed():
                    continue
                for attr in self._RESULT_COUNT_ATTRIBUTES:
                    try:
                        value = element.get_attribute(attr)
                        if value and value.strip().isdigit():
                            print(f"Result count via CSS ({selector}): {value.strip()}")
                            return int(value.strip())
                    except Exception:
                        continue
        return None

    def _get_count_via_js(self):
        """Try reading the result count by running JavaScript that polls the DOM.

        More reliable than CSS when the attribute loads asynchronously.
        Returns the count as an int, or None if not found.
        """
        js_result = self.driver.execute_script(self._RESULT_COUNT_JS)
        if js_result and js_result.get("value"):
            count = js_result["value"]
            print(f"Result count via JS ({js_result.get('selector')}): {count}")
            return count
        return None

    def get_result_count(self, max_attempts=4):
        """Return the total number of results for the current search.

        Tries CSS selectors first, then a JavaScript fallback. Retries up to
        max_attempts times with increasing waits, refreshing the page on the
        second retry to handle cases where the count loads slowly on the backend.

        Returns the count as an int, or None if it could not be retrieved.
        """
        for attempt in range(max_attempts):
            try:
                # Wait for the page to finish loading (counts can be slow on large result sets)
                WebDriverWait(self.driver, 40).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
                time.sleep(2)

                # Let any pending jQuery requests settle (not all pages use jQuery)
                try:
                    WebDriverWait(self.driver, 20).until(
                        lambda d: d.execute_script("return jQuery.active == 0")
                        if d.execute_script("return typeof jQuery !== 'undefined'")
                        else True
                    )
                except Exception:
                    pass

                result_count = self._get_count_via_css() or self._get_count_via_js()

                if result_count and result_count > 0:
                    self.result_count = result_count
                    return result_count

                # No count found — decide how long to wait before retrying
                if attempt < max_attempts - 1:
                    if attempt == 0:
                        print(f"No result count on attempt {attempt+1}, waiting and retrying...")
                        time.sleep(30)
                    elif attempt == 1:
                        print("Refreshing page to reload result count...")
                        self.driver.refresh()
                        time.sleep(30)
                    else:
                        print("Final retry: waiting for backend to finish processing...")
                        time.sleep(60)
                else:
                    print("Could not retrieve result count after all attempts.")
                    return None

            except Exception:
                print(f"Attempt {attempt+1} to get result count failed")
                if attempt < max_attempts - 1:
                    if attempt == 0:
                        time.sleep(10)
                    else:
                        self.driver.refresh()
                        time.sleep(10)
                else:
                    print("Max attempts reached. data-actualresultscount may not be populating.")
                    return None

        return None

    def get_ranges(self):
        """Return the list of result ranges that still need to be downloaded.

        Nexis Uni uses 1-based result indices (results 1–500, 501–1000, etc.).
        Each range string like "1-500" maps to the download dialog's range field.

        Already-downloaded ranges are identified by scanning the basin's download
        folder for files named '<BCODE>_results_<start>-<end>.ZIP'. The final range
        gets special treatment: its start number is compared instead of the full
        string, because the last range may have fewer than 500 results and the exact
        end number can shift if the result count updates between runs.

        Returns a sorted list of range strings not yet downloaded.
        """
        full_count = self.get_result_count()
        # Nexis Uni caps downloads at 500 documents per request for Word/full-text format
        download_limit = 500

        # Generate all expected ranges for the full result set (1-indexed)
        ranges = []
        for i in range(1, full_count, download_limit):
            end = min(i + (download_limit - 1), full_count)
            ranges.append(f"{i}-{end}")

        # Parse already-downloaded range strings from filenames like BCODE_results_1-500.ZIP
        downloaded_ranges = [
            f.split("_")[-1].replace(".ZIP", "")
            for f in os.listdir(self.download_folder)
            if f.endswith(".ZIP")
        ]

        # Find ranges not yet downloaded
        not_downloaded_ranges = []
        for range_str in ranges:
            if range_str in downloaded_ranges:
                continue
            # For the final range, match on start number only (end may differ if count changed)
            if range_str == ranges[-1]:
                start_num = range_str.split('-')[0]
                if any(dr.split('-')[0] == start_num for dr in downloaded_ranges):
                    continue
            not_downloaded_ranges.append(range_str)

        return sorted(not_downloaded_ranges, key=lambda x: int(x.split('-')[0]))
    
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
        range_element.clear()

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

    
    def move_file(self, r, poll_timeout=60):
        # Poll for the file — the download UI disappearing doesn't guarantee the file
        # is on disk yet, so we check repeatedly rather than giving up immediately.
        deadline = time.time() + poll_timeout
        matching_downloads = []
        while time.time() < deadline:
            matching_downloads = [f for f in os.listdir(self.download_folder_temp) if re.match(r"Files \(\d+\)\.ZIP", f)]
            if matching_downloads:
                break
            time.sleep(2)

        if not matching_downloads:
            print(f"file containing range {r} was not downloaded")
            raise DownloadFailedException

        print("Download completed!")
        default_download_path = os.path.join(self.download_folder_temp, matching_downloads[0])
        nexis_scraper_download_path = os.path.join(self.download_folder, f"{self.basin_code}_results_{r}.ZIP")

        if os.path.isfile(default_download_path):
            os.rename(default_download_path, nexis_scraper_download_path)
            print(f"moving file to {nexis_scraper_download_path}")

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


    def check_clear_downloads(self, r, prev_r=None):
        """Check for and handle unsorted downloads.

        If a stray file is found and the previous range's ZIP is missing from the
        basin folder, the file is probably that download arriving late — so it gets
        sorted correctly instead of being discarded to the unsorted folder.
        """
        default_download_pattern = r"Files \(\d+\)\.ZIP"
        matching_files = [f for f in os.listdir(self.download_folder_temp) if re.match(default_download_pattern, f)]

        if not matching_files:
            return

        print("There's an unsorted file in downloads")

        # If the previous range's file is missing, assume this is that late-arriving download
        if prev_r is not None:
            prev_dest = os.path.join(self.download_folder, f"{self.basin_code}_results_{prev_r}.ZIP")
            if not os.path.exists(prev_dest):
                source = os.path.join(self.download_folder_temp, matching_files[0])
                os.rename(source, prev_dest)
                print(f"Late-arriving file attributed to previous range {prev_r}, moved correctly")
                return

        # Can't attribute it to a known range — move to unsorted
        self.create_unsorted_folder(r)
        self.move_unsorted(r, matching_files[0])

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