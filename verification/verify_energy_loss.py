from playwright.sync_api import sync_playwright, expect
import time

def verify_energy_loss_tooltip(page):
    # 1. Load the main page
    page.goto("http://localhost:8001/")
    print("Page loaded")

    # 2. Wait for the tree to load. The user instructions mention a 'Carregar árvore original' button.
    # We should look for it and click it if necessary, or see if it auto-loads.
    # Inspecting memory: "The frontend tree visualization is loaded via a manual POST request to `/tree` triggered by the 'Carregar árvore original' button."

    # Locate the button using Portuguese text as per memory
    load_button = page.get_by_role("button", name="Carregar árvore original")
    expect(load_button).to_be_visible()
    load_button.click()
    print("Clicked load button")

    # 3. Wait for the tree container to be populated.
    # The SVG container usually has an id or class. Let's assume there are circle elements for nodes.
    # Wait for at least one circle.
    page.wait_for_selector("circle")
    print("Tree rendered")

    # 4. Find a consumer node to hover over.
    # Consumer nodes are usually leaves. In d3 trees, they are at the end.
    # Let's try to find a circle that has 'Consumidor' in its data or tooltip.
    # The tooltips are often implemented as a `title` attribute or a separate div appearing on hover.
    # Let's try hovering over the last circle (likely a leaf).

    circles = page.locator("circle").all()
    if not circles:
        print("No circles found!")
        return

    # Hover over a few circles until we find one that shows "Perda Energética" in the body text (if tooltip is a div).
    found = False
    for i in range(len(circles) - 1, -1, -1): # Start from end (leaves)
        circle = circles[i]
        # Move mouse to circle
        box = circle.bounding_box()
        if box:
            page.mouse.move(box['x'] + box['width']/2, box['y'] + box['height']/2)
            time.sleep(0.5) # Wait for tooltip

            # Check if "Perda Energética" is visible anywhere on the page (assuming tooltip is appended to body)
            if page.get_by_text("Perda Energética").is_visible():
                print(f"Found tooltip on node index {i}")
                found = True
                break

    if not found:
        print("Could not find 'Perda Energética' in any tooltip.")
    else:
        print("Verification successful: 'Perda Energética' found.")

    # 5. Take screenshot
    page.screenshot(path="verification/energy_loss_tooltip.png")
    print("Screenshot saved to verification/energy_loss_tooltip.png")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            verify_energy_loss_tooltip(page)
        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path="verification/error.png")
        finally:
            browser.close()
