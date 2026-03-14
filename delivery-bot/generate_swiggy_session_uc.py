import undetected_chromedriver as uc
import time
import json
import os

SESSION_FILE = os.path.join(os.path.dirname(__file__), "sessions", "swiggy_auth_uc.json")

def main():
    os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
    print(f"Session will be saved to {SESSION_FILE}")
    
    options = uc.ChromeOptions()
    # options.add_argument('--headless') # keep headed for login
    
    print("Launching regular Chrome to bypass protection...")
    driver = uc.Chrome(options=options, version_main=122) # Trying to match a recent version
    
    try:
        driver.get("https://www.swiggy.com/")
        
        print("\n*** ACTION REQUIRED ***")
        print("Please log in to Swiggy using your phone number and OTP.")
        print("Set your delivery location (e.g., Koramangala) in the browser.")
        print("Once you are fully logged in and the location is set on the homepage,")
        print("press ENTER in this terminal to save the session and continue.")
        print("***********************\n")
        
        input("Press ENTER here when ready to save session...")
        
        print("Saving cookies...")
        cookies = driver.get_cookies()
        with open(SESSION_FILE, 'w') as f:
            json.dump(cookies, f)
            
        print("Session saved successfully!")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
