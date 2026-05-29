from nexis_scraper.classes.LoginClass import PasswordManager, WebDriverManager, Login
from nexis_scraper.classes.DownloadClass import Download, DownloadFailedException
from nexis_scraper.classes.SearchClass import Search
from selenium.common.exceptions import TimeoutException, NoSuchElementException

import os
import time
from tqdm import tqdm

# Default date range for all Nexis Uni queries — update END_DATE when new data is needed
DEFAULT_START_DATE = '06/30/2008'
DEFAULT_END_DATE = '04/30/2025'


def _year_label(start_date, end_date):
    """Return 'MM-DD-YYYY_MM-DD-YYYY' subfolder label, or None when using the full default range."""
    if start_date == DEFAULT_START_DATE and end_date == DEFAULT_END_DATE:
        return None
    return start_date.replace('/', '-') + '_' + end_date.replace('/', '-')

_password_cache = None


def get_user(basin_code, uname):
    # Use standard paths that work for any user
    base_path = os.path.expanduser("~")
    nexis_scraper_folder = "./"
    download_folder_temp = os.path.join(base_path, "Downloads")
    download_folder = os.path.join(nexis_scraper_folder, "data", "downloads", basin_code)

    paths = {
        "base_path": base_path,
        "user_name": uname,
        "nexis_scraper_folder": nexis_scraper_folder,
        "download_folder_temp": download_folder_temp,
        "download_folder": download_folder,
    }

    return paths, uname


def logout_clearcookies(download):
    sign_in_button = "//button[@id='NexisUniMipNewSignIn']"
    try:
        download._click_from_xpath(sign_in_button)
        print("logging out")
    except Exception as e:
        find_sign_in = download.driver.find_element_by_xpath(sign_in_button)
        download.driver.execute_script("return arguments[0].scrollIntoView(true);", find_sign_in)
    download.driver.delete_all_cookies()
    print("deleting cookies")


def reset(download, login, search, start_date, end_date):
    """Re-login and re-run search to refresh the session between download ranges."""
    logout_clearcookies(download)
    time.sleep(3)
    login._init_login()
    search.search_process(start_date, end_date)
    time.sleep(5)
    download.DownloadSetup()


def _ensure_download_folder(download_folder):
    """Create the basin download folder if it doesn't already exist."""
    if os.path.exists(download_folder):
        print(f"{download_folder} already exists")
    else:
        os.makedirs(download_folder, exist_ok=True)
        print(f"created folder {download_folder}")


def _get_or_cache_password():
    """Return the user's password, prompting once and caching for the session.

    Checks NEXIS_PASSWORD environment variable first — if set, no prompt needed.
    Set it once per terminal session with: export NEXIS_PASSWORD=yourpassword
    """
    global _password_cache
    if _password_cache is None:
        env_password = os.environ.get("NEXIS_PASSWORD")
        if env_password:
            print("Using password from environment variable")
            _password_cache = env_password
        else:
            pm = PasswordManager()
            if not pm.password:
                print("No password found, please enter your password")
                password = pm.get_password()
                print("Password saved successfully")
            else:
                password = pm.password
            _password_cache = password
    return _password_cache


def _start_driver():
    """Start the Firefox WebDriver.

    GeckoDriverManager (used by WebDriverManager) auto-downloads and caches the
    correct geckodriver version, so no manual driver update step is needed.
    """
    manager = WebDriverManager()
    driver = manager.start_driver()
    return manager, driver


def _run_download_loop(download, login, search, basin_code, download_folder, pbar, start_date, end_date):
    """Execute the main per-range download loop for a single basin.

    For each pending range:
    - Resets the session (re-login + re-search) between ranges to avoid timeouts
    - Downloads the range and moves the file to the basin folder
    - Tracks consecutive failures; aborts the basin after failure_threshold in a row

    Returns when all ranges are downloaded or the failure threshold is reached.
    """
    consecutive_failures = 0
    # How many consecutive failures in a row before giving up on this basin entirely
    failure_threshold = 3
    completed_ranges = set()
    process_start_time = time.time()

    while True:
        ranges_to_download = download.get_ranges()

        if not ranges_to_download:
            print(f"All ranges for basin {basin_code} downloaded!")
            logout_clearcookies(download)
            download.driver.close()
            return

        print(f"Attempting to download {len(ranges_to_download)} ranges")

        for i, r in enumerate(ranges_to_download):
            try:
                prev_r = ranges_to_download[i - 1] if i > 0 else None
                if i > 0:
                    # Re-login and re-run search between ranges to keep the session fresh
                    reset(download, login, search, start_date, end_date)

                download.check_clear_downloads(r, prev_r=prev_r)
                try:
                    download.download_dialog(r)
                except TimeoutException as te:
                    print(f"[ERROR] TimeoutException in download_dialog for range {r}: {te}")
                    try:
                        prefix = f"timeout_{basin_code}_{r}"
                        download.driver.save_screenshot(os.path.join(download_folder, f"{prefix}.png"))
                        with open(os.path.join(download_folder, f"{prefix}.html"), "w", encoding="utf-8") as f:
                            f.write(download.driver.page_source)
                    except Exception:
                        pass
                    raise
                except Exception as e:
                    print(f"[ERROR] Exception during download_dialog for range {r}: {e}")
                    try:
                        download.driver.save_screenshot(os.path.join(download_folder, f"err_{basin_code}_{r}.png"))
                    except Exception:
                        pass
                    raise

                print(f"preparing to download range {r}")
                download.wait_for_download()
                download.move_file(r)

                elapsed_minutes = (time.time() - process_start_time) / 60
                consecutive_failures = 0
                print(f"Time elapsed since process began (minutes): {elapsed_minutes:.1f}")

                if r not in completed_ranges:
                    completed_ranges.add(r)
                    pbar.update(1)

            except DownloadFailedException:
                consecutive_failures += 1
                print(f"Download failed for range {r} ({consecutive_failures} consecutive failure(s))")
                if consecutive_failures >= failure_threshold:
                    print(f"{basin_code} downloads failed {failure_threshold} times in a row, please try another basin")
                    logout_clearcookies(download)
                    download.driver.close()
                    return

                try:
                    reset(download, login, search, start_date, end_date)
                except Exception:
                    pass  # If reset itself fails, let the failure counter handle it
                continue

            except Exception:
                continue  # Skip this range and try the next


def full_process(basin_code, username, paths, start_date=DEFAULT_START_DATE, end_date=DEFAULT_END_DATE):
    """Orchestrate the full download pipeline for a single basin.

    Phases:
      1. Folder setup
      2. Authentication (password + Chrome driver + Nexis login)
      3. Search execution
      4. Download setup (sort/group results; switch to riparian search if count > 150k)
      5. Range-by-range download loop

    Args:
        basin_code: The basin code (e.g. 'NILE', 'GRND') used for folder naming and search terms
        username: UA username from the Streamlit input
        paths: Dict of folder paths produced by get_user()
        start_date: Search start date string MM/DD/YYYY (default: full-range start)
        end_date: Search end date string MM/DD/YYYY (default: full-range end)
    """
    print("~" * 27)
    print(f"Starting download for {basin_code}!")
    print("~" * 27)

    # When a non-default date range is used, store downloads in a year-range subfolder
    # so result-range numbers (1-500 etc.) don't collide across separate year runs.
    base_download_folder = paths["download_folder"]
    label = _year_label(start_date, end_date)
    download_folder = os.path.join(base_download_folder, label) if label else base_download_folder
    download_folder_temp = paths["download_folder_temp"]

    # Phase 1: Folder setup
    _ensure_download_folder(download_folder)

    # Phase 2: Authentication
    password = _get_or_cache_password()
    manager, driver = _start_driver()
    login = Login(user_name=username, password=password, driver_manager=manager, url=None)
    login._init_login()

    # Phase 3: Search
    search = Search(driver, basin_code, username, paths["nexis_scraper_folder"])
    search.search_process(start_date, end_date)

    # Phase 4: Download setup
    download = Download(
        driver=driver,
        basin_code=basin_code,
        username=username,
        login=login,
        search=search,
        download_folder=download_folder,
        download_folder_temp=download_folder_temp,
        finished=False,
        url=None,
        timeout=20,
    )

    time.sleep(5)
    try:
        download.DownloadSetup()
    except (TimeoutException, NoSuchElementException, DownloadFailedException):
        check_count = download.get_result_count()
        if check_count is None:
            zero_txt = os.path.join(download_folder, 'noresults.txt')
            if not os.path.exists(zero_txt):
                os.makedirs(zero_txt)
            print(f"Zero results to download for basin {basin_code}")

    if download.get_result_count is None:
        logout_clearcookies(download)
        driver.close()
        return

    # If result count exceeds 150k, narrow results by adding riparian country names to the search
    if download.get_result_count() > 150000 and not getattr(search, 'already_switched_to_riparian', False):
        search.switch_to_riparian()
        search.already_switched_to_riparian = True
        if search.use_riparian:
            search.search_process(start_date, end_date)
            download.DownloadSetup()

    # Phase 5: Download loop
    initial_ranges = download.get_ranges()
    with tqdm(total=len(initial_ranges), desc=f"Overall Progress on {basin_code}") as pbar:
        _run_download_loop(download, login, search, basin_code, download_folder, pbar, start_date, end_date)
