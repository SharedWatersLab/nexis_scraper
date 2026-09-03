import time
import platform
import pandas as pd
import os

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.keys import Keys

from classes.BaseClass import SeleniumBase


class Search(SeleniumBase):

    # Nexis Uni rejects searches above ~2500 total chars with a "simplify" error.
    # 2400 gives a small safety buffer.
    MAX_TOTAL_SEARCH_STRING = 2400

    def __init__(self, driver: webdriver, basin_code, username, nexis_scraper_folder, timeout=20, url=None):
        self.driver = driver
        self.url = url
        self.timeout = timeout
        self.basin_code = basin_code
        self.username = username  
        self.nexis_scraper_folder = nexis_scraper_folder  

        # this can manually be set to True if we want to try with narrower search terms/fewer results
        self.use_riparian = False # range count >500 will "flip this switch" to proceed with riparian country search
        self.riparian_txt = os.path.join(self.nexis_scraper_folder, "data", "downloads", self.basin_code, "riparian_names_used.txt")

        # Load tracking sheet - note the path might need adjustment
        tracking_sheet = pd.read_excel(f'{self.nexis_scraper_folder}nexis_scraper/basins_searchterms_tracking.xlsx')
        
        self.row = tracking_sheet[tracking_sheet['BCODE'] == basin_code.upper()]
        self.search_term = self.row['Basin_Specific_Terms'].values[0]

        # The Nexis Uni advanced search uses four boolean “boxes” combined with AND/NOT:
        #   box_1: water-related geography terms (river, lake, dam, aquifer…)
        #   box_2: cooperation/conflict action terms (treaty, negotiate, war, sanction…)
        #   box_3: basin-specific terms from the tracking spreadsheet (e.g. country/river names)
        #   box_4: exclusion terms — false-positive water references to filter out
        self.box_1_keys = 'water* OR river* OR lake* OR dam* OR stream OR streams OR tributar* OR irrigat* OR flood* OR drought* OR canal* OR hydroelect* OR reservoir* OR groundwater* OR aquifer* OR riparian* OR pond* OR wadi* OR creek* OR oas*s OR spring*'
        self.box_2_keys = 'treaty OR treaties OR agree* OR negotiat* OR mediat* OR resolv* OR facilitat* OR resolution OR commission* OR council* OR dialog* OR meet* OR discuss* OR secretariat* OR manag* OR peace* OR accord OR settle* OR cooperat* OR collaborat* OR diplomacy OR diplomat* OR statement OR “memo” OR “memos” OR memorand* OR convers* OR convene* OR convention* OR declar* OR allocat*OR share*OR sharing OR apportion* OR distribut* OR ration* OR administ* OR trade* OR trading OR communicat* OR notif* OR trust* OR distrust* OR mistrust*OR support* OR relations* OR consult* OR alliance* OR ally OR allies OR compensat* OR disput* OR conflict* OR disagree* OR sanction* OR war* OR troop* OR skirmish OR hostil* OR attack* OR violen* OR boycott* OR protest* OR clash* OR appeal* OR intent* OR reject* OR threat* OR forc* OR coerc* OR assault* OR fight OR demand* OR disapprov*  OR bomb* OR terror* OR assail* OR insurg* OR counterinsurg* OR destr* OR agitat* OR aggrav* OR veto* OR ban* OR exclud* OR prohibit* OR withdraw* OR suspect* OR combat* OR milit* OR refus* OR deteriorat* OR spurn* OR invad* OR invasion* OR blockad* OR debat* OR refugee* OR migrant* OR violat*'
        self.box_4_keys = 'ocean* OR “bilge water” OR “flood of refugees” OR waterproof OR “water resistant” OR streaming OR streame*'
        self.box_3_keys = self.search_term
        self.box_3_keys = self._truncate_box3()  # Truncate box 3 to fit within MAX_TOTAL_SEARCH_STRING

    def NexisHome(self):
        try:
            ignore_button = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button#proceed-button.secondary-button.small-link"))
            )
            ignore_button.click()
            print("Safety page, click to ignore")
            time.sleep(3)
        except TimeoutException:
            pass

        self.nexis_home_substring = 'bisnexishome'
        if self.nexis_home_substring in self.driver.current_url:
            print('already on Nexis Uni home page')
        else:
            print("Navigate to Nexis Uni home page")
            self.driver.get("https://login.libdata.lib.ua.edu/login?qurl=http%3a%2f%2fwww.nexisuni.com")

        # Wait for the nav's tab-menu container to actually render before returning, instead
        # of a flat sleep - on the first search after login (already on bisnexishome, no
        # driver.get() above) the SPA can still be cold-bootstrapping the nav even though the
        # URL already looks right, which was timing out _init_search()'s News-tab click.
        try:
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#nexissearchbutton"))
            )
        except TimeoutException:
            print(f"[WARN] Nav menu never appeared; current_url={self.driver.current_url}")

    def _init_search(self):
        if self.url:
            self.driver.get(self.url)
        #news_button = 'body > main > div > ln-navigation > navigation > div.global-nav.light.margin-bottom-30 > div.zones.pagewrapper.product-switcher-navigation.pagewrapper-nexis > nexissearchtabmenu > div > tabmenucomponent > div > div > ul > li:nth-child(3) > button'
        news_button = '#nexissearchbutton > tabmenucomponent > div > div > ul > li:nth-child(3) > button' # new selector for UA search
        self._click_from_css(news_button) # click to search in News
        #news_advancedsearch_button = '#wxbhkkk > ul > li:nth-child(1) > button'
        news_advancedsearch_button = '.advancesearch > li:nth-child(1) > button:nth-child(1)'
        self._click_from_xpath("//button[contains(text(), 'Advanced Search')]")  # click advanced search
        #self._click_from_css(news_advancedsearch_button) # click advanced search, PN: NOT WORKING FOR ME
        self.driver.execute_script("window.scrollTo(0,102)")
        print("Initializing search for " + self.basin_code)
        #print(f"Initializing search for {row['Basin_Name']})

    def _box3_budget(self, extra_terms_len=0):
        """How many chars box 3 can use without exceeding MAX_TOTAL_SEARCH_STRING.

        The full search string template is:
          hlead(b1) and hlead(b2) and hlead(b3) [and hlead(extra)] and not hlead(b4)
        Overhead for the default (4-box) template is 47 chars; each additional box
        (e.g. riparian) adds 12 chars for the extra ') and hlead(' connector.
        """
        overhead = 47 + (12 if extra_terms_len > 0 else 0)
        fixed = len(self.box_1_keys) + len(self.box_2_keys) + len(self.box_4_keys) + extra_terms_len + overhead
        return self.MAX_TOTAL_SEARCH_STRING - fixed

    def _truncate_to_budget(self, terms, budget):
        """Truncate terms to fit within budget chars, cutting at the last OR boundary."""
        if len(terms) <= budget:
            return terms
        truncated = terms[:budget]
        last_or = truncated.rfind(" OR ")
        result = terms[:last_or] if last_or != -1 else truncated
        print(f"Box 3 truncated: {len(terms)} → {len(result)} chars (budget: {budget})")
        return result

    def _truncate_box3(self):
        """Truncate box 3 to fit within the available budget for the default search."""
        if self.use_riparian:
            return self.box_3_keys  # riparian_search handles its own truncation
        return self._truncate_to_budget(self.box_3_keys, self._box3_budget())
    
    def riparian_search(self):
        """Build a narrower search string that includes riparian country names.

        Used when the default search returns too many results (> 150k) to download
        efficiently. By adding country names (e.g. 'Egypt OR Sudan OR Ethiopia') the
        result set is narrowed to articles that explicitly mention the relevant nations.

        Box 3 is truncated to whatever budget remains after accounting for the riparian
        terms and all other fixed content, keeping the total under MAX_TOTAL_SEARCH_STRING.
        """
        box_5_keys = self.row['Riparian_country_term'].values[0]
        budget = self._box3_budget(extra_terms_len=len(box_5_keys))
        box_3_truncated = self._truncate_to_budget(self.box_3_keys, budget)
        return (
            'hlead(' + self.box_1_keys + ')'
            + ' and hlead(' + self.box_2_keys + ')'
            + ' and hlead(' + box_3_truncated + ')'
            + ' and hlead(' + box_5_keys + ')'
            + ' and not hlead(' + self.box_4_keys + ')'
        )

    def default_search(self):
        default_string = 'hlead(' + self.box_1_keys + ') and hlead(' + self.box_2_keys + ') and hlead(' + self.box_3_keys + ') and not hlead(' + self.box_4_keys + ')'
        return default_string

    def groundwater_search(self):
        groundwater_keys = 'groundwater* OR aquifer* OR "ground water" OR spring* OR borehole OR "bore hole"'
        groundwater_string = 'hlead(' + self.box_2_keys + ') and hlead(' + groundwater_keys + ') and not hlead(' + self.box_4_keys + ')'
        return groundwater_string

    def _search_box(self):
        self.search_box = '#searchTerms' # css
        #self.search_box = "//input[@type='text' and @id='searchTerms']"
        
        # GRND basin uses a special groundwater query instead of the standard box structure
        if self.basin_code == 'GRND':
            search_string = self.groundwater_search()
            print("performing groundwater search")
        elif self.use_riparian:
            # use_riparian is set when result count exceeds 150k (see utils.py)
            # riparian adds country names to narrow results
            search_string = self.riparian_search()
            print("adding riparian country terms to search terms")
        else:
            search_string = self.default_search()
            print("using default search terms")
        
        self._send_keys_from_css(self.search_box, search_string)
        #self._send_keys_from_xpath(self.search_box, self.search_string)
        
        time.sleep(5)

    # XPath and CSS selectors for the search button (Nexis Uni has two variants)
    _SEARCH_BUTTON_XPATHS = [
        "//button[@class='btn search' and @data-action='search']",
        "//button[@data-action='search' and @id='mainSearch' and @aria-label='Search']",
    ]
    _SEARCH_BUTTON_CSS = ["button.btn.search[data-action='search']", "#mainSearch"]

    # Elements that only appear on the results page — used to verify search succeeded
    _RESULT_INDICATORS = [
        "//li[contains(@class, 'active') and @data-actualresultscount]",
        "//button[@data-id='urb:hlct:16']",
        "//div[contains(@class, 'results-list')]",
    ]

    def _is_on_results_page(self):
        """Return True if any results-page indicator element is visible."""
        for indicator in self._RESULT_INDICATORS:
            try:
                if self.driver.find_element(By.XPATH, indicator).is_displayed():
                    return True
            except Exception:
                continue
        return False

    def _wait_for_results_page(self, timeout=10):
        """Wait up to `timeout` seconds for the results page to appear."""
        for indicator in self._RESULT_INDICATORS:
            try:
                WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((By.XPATH, indicator))
                )
                return True
            except Exception:
                continue
        return False

    def _find_and_click_search_button(self):
        """Try all known search button selectors and click the first one found.

        Uses _try_click() (from SeleniumBase) which attempts standard click,
        JS click, and ActionChains in sequence.
        Returns True if a button was successfully clicked.
        """
        # Try XPath selectors
        for xpath in self._SEARCH_BUTTON_XPATHS:
            try:
                button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                time.sleep(1)
                if self._try_click(button):
                    print(f"Clicked search button (xpath: {xpath})")
                    return True
            except Exception:
                continue

        # Try CSS selectors
        for css in self._SEARCH_BUTTON_CSS:
            try:
                button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, css))
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                time.sleep(1)
                if self._try_click(button):
                    print(f"Clicked search button (css: {css})")
                    return True
            except Exception:
                continue

        # Last resort: find any visible button with "Search" text
        try:
            buttons = self.driver.find_elements(
                By.XPATH, "//button[contains(text(), 'Search') or contains(@aria-label, 'Search')]"
            )
            for button in buttons:
                if button.is_displayed():
                    self.driver.execute_script("arguments[0].click();", button)
                    print("Clicked search button (text fallback)")
                    return True
        except Exception:
            pass

        return False

    def complete_search(self, max_attempts=3):
        """Click the search button and verify we land on the results page.

        Retries up to max_attempts times. Returns True on success, False if
        the results page never loads after all attempts.
        """
        for attempt in range(max_attempts):
            try:
                if self._is_on_results_page():
                    print("Already on results page, search was successful")
                    return True

                self._find_and_click_search_button()

                time.sleep(5)

                if self._wait_for_results_page():
                    print("Successfully verified we're on results page")
                    return True

                if attempt < max_attempts - 1:
                    print(f"Search attempt {attempt+1} failed — results page not loaded. Retrying...")
                    if "error" in self.driver.title.lower() or "problem" in self.driver.title.lower():
                        self.driver.refresh()
                        time.sleep(5)
                else:
                    print("All search attempts failed. Could not reach results page.")
                    return False

            except Exception as e:
                print(f"Search attempt {attempt+1} failed with error: {str(e)}")
                if attempt < max_attempts - 1:
                    print(f"Retrying search (attempt {attempt+2}/{max_attempts})...")
                    time.sleep(2)
                else:
                    print("All search attempts failed.")
                    return False

        return False

    def switch_to_riparian(self):
        """Switch this basin permanently to riparian search mode.

        Sets use_riparian=True and writes a marker file so future runs
        (after a restart) automatically pick up the riparian mode without
        having to re-detect the high result count.
        """
        if self.basin_code != 'GRND':
            print("Switching to riparian search mode...")
            self.use_riparian = True
            # Create a .txt file marker in the downloads/bcode folder
            if not os.path.exists(self.riparian_txt):
                # First ensure parent directory exists
                os.makedirs(os.path.dirname(self.riparian_txt), exist_ok=True)
                # Then create the file
                with open(self.riparian_txt, 'w') as f:
                    f.write("Riparian search terms used\n")
        
        else:
            pass

    def check_riparian_already_used(self):
        """Check if riparian search was already used for this basin.
        
        Checks for either:
        - The file riparian_names_used.txt (correct format)
        - A folder named riparian_names_used.txt (Windows bug from old code)
        
        Returns True if found, automatically switches to riparian mode.
        """
        # Check if it exists as either file or folder
        if os.path.exists(self.riparian_txt):
            if os.path.isfile(self.riparian_txt):
                print(f"Found existing riparian marker file for {self.basin_code}")
                self.use_riparian = True
                return True
            elif os.path.isdir(self.riparian_txt):
                print(f"Found existing riparian marker folder for {self.basin_code} (old Windows bug)")
                print("Converting folder to file...")
                # Remove the folder, create the file
                import shutil
                shutil.rmtree(self.riparian_txt)
                with open(self.riparian_txt, 'w') as f:
                    f.write("Riparian search terms used\n")
                self.use_riparian = True
                return True
        return False
    
    def search_process(self, start_date, end_date):
        self.check_riparian_already_used()
        self.NexisHome()
        self._init_search()
        self._search_box()
        time.sleep(10)
        startdate_field = "//input[@class='dateFrom' and @aria-label='From']"
        enddate_field = "//input[@class='dateTo' and @aria-label='To']"

        system = platform.system().lower()
        if system == "darwin":
            select_all = Keys.COMMAND, "a"
        elif system == "windows":
            select_all = Keys.CONTROL, "a"

        self._send_keys_from_xpath(startdate_field, select_all)
        self._send_keys_from_xpath(startdate_field, start_date)

        self._send_keys_from_xpath(enddate_field, select_all)
        self._send_keys_from_xpath(enddate_field, end_date)

        #continue
        self.complete_search()
        time.sleep(5)
