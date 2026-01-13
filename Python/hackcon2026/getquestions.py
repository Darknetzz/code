"""
Scraper for HackCon 2026 Round1 form.
Fills in random valid values and extracts the contents of the next page.
"""

import time
import random
import string
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException


def generate_random_name():
    """Generate a random valid name."""
    first_names = ["John", "Jane", "Alex", "Sarah", "Michael", "Emily", "David", "Lisa", 
                   "Chris", "Anna", "James", "Maria", "Robert", "Emma", "William", "Olivia"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", 
                  "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Wilson", "Anderson", "Thomas", "Taylor"]
    return f"{random.choice(first_names)} {random.choice(last_names)}"


def generate_random_email():
    """Generate a random valid email address."""
    domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "example.com"]
    username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{username}@{random.choice(domains)}"


def generate_random_phone():
    """Generate a random valid phone number (Norwegian format)."""
    # Norwegian phone numbers: 8 digits, can start with various prefixes
    prefixes = ["4", "9", "2", "3", "5", "6", "7", "8"]
    prefix = random.choice(prefixes)
    number = ''.join(random.choices(string.digits, k=7))
    return f"{prefix}{number}"


def scrape_form():
    """Main scraper function."""
    url = "https://nettskjema.no/a/581602#/page/1"
    
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in background (remove if you want to see the browser)
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Initialize the driver
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        print(f"Navigating to {url}...")
        driver.get(url)
        
        # Wait for the page to load
        time.sleep(3)  # Give the page time to fully load
        
        # Generate random values
        name = generate_random_name()
        email = generate_random_email()
        phone = generate_random_phone()
        
        print(f"Generated values:")
        print(f"  Name: {name}")
        print(f"  Email: {email}")
        print(f"  Phone: {phone}")
        
        # Wait for form fields to be present and fill them in
        wait = WebDriverWait(driver, 15)
        
        # Wait for form to be fully loaded
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "input")))
        time.sleep(2)  # Additional wait for dynamic content
        
        def find_input_by_label(label_text):
            """Find input field by its associated label text."""
            try:
                # Try multiple XPath strategies
                xpaths = [
                    f"//label[contains(., '{label_text}')]/following-sibling::input[1]",
                    f"//label[contains(., '{label_text}')]/../input",
                    f"//label[contains(., '{label_text}')]/parent::*/input",
                    f"//label[contains(., '{label_text}')]/ancestor::*[contains(@class, 'field') or contains(@class, 'form')]//input",
                    f"//*[contains(text(), '{label_text}')]/following::input[1]",
                ]
                for xpath in xpaths:
                    try:
                        element = driver.find_element(By.XPATH, xpath)
                        if element and element.is_displayed():
                            return element
                    except:
                        continue
            except:
                pass
            return None
        
        # Fill Name field
        name_field = None
        try:
            name_field = find_input_by_label("Name")
            if not name_field:
                # Try direct selectors
                name_field = driver.find_element(By.CSS_SELECTOR, "input[type='text'][placeholder*='name' i], input[name*='name' i], input[id*='name' i]")
        except:
            pass
        
        if name_field:
            try:
                name_field.clear()
                name_field.send_keys(name)
                print("✓ Filled in Name field")
            except Exception as e:
                print(f"Warning: Error filling Name field: {e}")
        else:
            print("⚠ Could not locate Name field")
        
        # Fill Email field
        email_field = None
        try:
            email_field = find_input_by_label("Email")
            if not email_field:
                email_field = driver.find_element(By.CSS_SELECTOR, "input[type='email'], input[name*='email' i], input[id*='email' i]")
        except:
            pass
        
        if email_field:
            try:
                email_field.clear()
                email_field.send_keys(email)
                print("✓ Filled in Email field")
            except Exception as e:
                print(f"Warning: Error filling Email field: {e}")
        else:
            print("⚠ Could not locate Email field")
        
        # Fill Phone field
        phone_field = None
        try:
            phone_field = find_input_by_label("Phone")
            if not phone_field:
                phone_field = driver.find_element(By.CSS_SELECTOR, "input[type='tel'], input[name*='phone' i], input[id*='phone' i]")
        except:
            pass
        
        if phone_field:
            try:
                phone_field.clear()
                phone_field.send_keys(phone)
                print("✓ Filled in Phone field")
            except Exception as e:
                print(f"Warning: Error filling Phone field: {e}")
        else:
            print("⚠ Could not locate Phone field")
        
        # Fallback: if we couldn't find fields by label, try filling all empty text inputs in order
        if not all([name_field, email_field, phone_field]):
            print("\nAttempting fallback method: filling inputs in order...")
            try:
                all_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='email'], input[type='tel']")
                empty_inputs = [inp for inp in all_inputs if not inp.get_attribute("value") and inp.is_displayed()]
                
                if len(empty_inputs) >= 3:
                    empty_inputs[0].clear()
                    empty_inputs[0].send_keys(name)
                    print("✓ Filled first empty input with Name")
                    
                    empty_inputs[1].clear()
                    empty_inputs[1].send_keys(email)
                    print("✓ Filled second empty input with Email")
                    
                    empty_inputs[2].clear()
                    empty_inputs[2].send_keys(phone)
                    print("✓ Filled third empty input with Phone")
            except Exception as e:
                print(f"Fallback method also failed: {e}")
        
        # Wait a bit before clicking next
        time.sleep(1)
        
        # Find and click "Next page" button
        try:
            next_button = wait.until(EC.element_to_be_clickable((
                By.XPATH, 
                "//button[contains(text(), 'Next page')] | //button[contains(text(), 'Next')] | //a[contains(text(), 'Next page')]"
            )))
            next_button.click()
            print("✓ Clicked 'Next page' button")
        except TimeoutException:
            # Try alternative selectors
            try:
                buttons = driver.find_elements(By.TAG_NAME, "button")
                for btn in buttons:
                    if "next" in btn.text.lower() or "neste" in btn.text.lower():
                        btn.click()
                        print("✓ Clicked 'Next page' button (alternative method)")
                        break
            except Exception as e:
                print(f"Error clicking Next button: {e}")
                return None
        
        # Wait for the next page to load
        print("Waiting for next page to load...")
        time.sleep(5)
        
        # Extract the contents of the next page
        page_content = driver.page_source
        page_text = driver.find_element(By.TAG_NAME, "body").text
        
        print("\n" + "="*60)
        print("NEXT PAGE CONTENT:")
        print("="*60)
        print(page_text)
        print("="*60)
        
        # Save to file
        with open("next_page_content.html", "w", encoding="utf-8") as f:
            f.write(page_content)
        print("\n✓ Saved HTML content to 'next_page_content.html'")
        
        with open("next_page_content.txt", "w", encoding="utf-8") as f:
            f.write(page_text)
        print("✓ Saved text content to 'next_page_content.txt'")
        
        return {
            "html": page_content,
            "text": page_text,
            "url": driver.current_url
        }
        
    except Exception as e:
        print(f"Error during scraping: {e}")
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        driver.quit()
        print("\nBrowser closed.")


if __name__ == "__main__":
    result = scrape_form()
    if result:
        print(f"\n✓ Scraping completed successfully!")
        print(f"  Final URL: {result['url']}")
    else:
        print("\n✗ Scraping failed or encountered issues.")
