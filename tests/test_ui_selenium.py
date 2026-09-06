"""
CodeSense AI - Selenium Automated UI & End-to-End Browser Test
Validates Streamlit UI rendering, headless browser capability, and interface elements.
"""
import pytest
import socket


def is_server_running(host="127.0.0.1", port=8501):
    """Check if the Streamlit development server is active on the expected port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex((host, port)) == 0


def get_webdriver():
    """Initialize a headless Chrome or Edge WebDriver."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.edge.options import Options as EdgeOptions

    # Try Chrome first
    try:
        chrome_options = ChromeOptions()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except Exception:
        pass

    # Fallback to Edge (default on Windows)
    try:
        edge_options = EdgeOptions()
        edge_options.add_argument("--headless=new")
        edge_options.add_argument("--no-sandbox")
        edge_options.add_argument("--disable-dev-shm-usage")
        edge_options.add_argument("--window-size=1920,1080")
        driver = webdriver.Edge(options=edge_options)
        return driver
    except Exception as e:
        pytest.skip(f"No compatible browser driver available: {e}")


def test_selenium_webdriver_initialization():
    """Verify that Selenium WebDriver initializes headlessly on the host system."""
    driver = get_webdriver()
    assert driver is not None
    driver.quit()


def test_streamlit_ui_live_render():
    """
    If the Streamlit app is running (http://localhost:8501),
    verify page title, layout, and essential UI components.
    """
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By

    server_url = "http://localhost:8501"
    if not is_server_running("127.0.0.1", 8501):
        pytest.skip("Streamlit app is not currently running on port 8501. Start with: streamlit run app.py")

    driver = get_webdriver()
    try:
        driver.get(server_url)

        # Wait for Streamlit React app to load and set page title dynamically
        WebDriverWait(driver, 15).until(
            lambda d: "CodeSense AI" in d.title or len(d.find_elements(By.TAG_NAME, "h1")) > 0
        )

        # Verify page title or presence of primary header
        assert ("CodeSense AI" in driver.title) or ("Streamlit" in driver.title)

        # Verify main container or body rendered
        body = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        assert body is not None
        assert len(body.text) > 0
    finally:
        driver.quit()
