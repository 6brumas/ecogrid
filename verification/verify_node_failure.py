
from playwright.sync_api import Page, expect, sync_playwright
import time

def test_node_failure_visuals(page: Page):
    # 1. Arrange: Go to the app homepage
    page.goto("http://localhost:8000")

    # 2. Click load tree and wait
    page.click("#btn-load-tree")
    page.wait_for_selector(".node")

    # 3. Choose a consumer node to fail.
    node_id = "C_0"

    # Fill the form
    page.fill("#chosen-node", node_id)

    # Select Node Failure
    page.click("label[for='node-failure']")

    # 4. Act: Click Simulate
    page.click("button[type='submit'][form='simulation-form']")

    # 5. Wait for the update
    # The status color for failure is black (#000000)
    # Note: simulateEvent.js clears logs and rebuilds tree on response
    time.sleep(2)

    # Check if a node with that ID has a black rect
    # We can inspect the status text in the tooltip or the color

    # Screenshot of the failed state
    page.screenshot(path="/home/jules/verification/node_failure.png")

    # 6. Act: Click Finalizar
    page.click("#stop-simulation")

    # Wait for restore
    time.sleep(2)

    # Screenshot of restored state
    page.screenshot(path="/home/jules/verification/node_restored.png")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            test_node_failure_visuals(page)
        finally:
            browser.close()
