from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException, TimeoutException


class SeleniumBase:
    """
    Shared Selenium helper methods inherited by Login, Search, and Download.

    Subclasses must set self.driver and self.timeout in their __init__.
    These helpers reduce boilerplate for the common patterns of
    waiting for an element and clicking/typing into it.
    """

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

    def _click_from_xpath(self, xpath):
        try:
            element = WebDriverWait(self.driver, self.timeout).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            element.click()
        except TimeoutException:
            raise NoSuchElementException(f"Element with xpath '{xpath}' not found")

    def _send_keys_from_xpath(self, xpath, keys):
        element = WebDriverWait(self.driver, self.timeout).until(
            EC.element_to_be_clickable((By.XPATH, xpath))
        )
        self.driver.execute_script("arguments[0].scrollIntoView();", element)
        element.send_keys(keys)

    def _is_element_present_css(self, css_selector):
        try:
            self.driver.find_element(By.CSS_SELECTOR, css_selector)
            return True
        except NoSuchElementException:
            return False

    def _try_click(self, button):
        """Attempt to click an element using multiple methods.

        Tries standard click first, then JavaScript click, then ActionChains.
        Returns True if any method succeeded, False if all failed.
        Useful when overlays or timing issues make standard clicks unreliable.
        """
        try:
            button.click()
            return True
        except Exception:
            pass
        try:
            self.driver.execute_script("arguments[0].click();", button)
            return True
        except Exception:
            pass
        try:
            ActionChains(self.driver).move_to_element(button).click().perform()
            return True
        except Exception:
            pass
        return False
