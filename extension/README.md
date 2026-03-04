# Scout to Giglz - Browser Extension

One-click show scouting while browsing ticket sites.

## Installation (Local Development)

1. Open `brave://extensions` or `chrome://extensions`
2. Enable "Developer mode" (top right toggle)
3. Click "Load unpacked"
4. Select this `extension/` folder

## Usage

1. Browse to a ticket page (Eventbrite, venue site, etc.)
2. Click the Giglz extension icon
3. Click "Scout"
4. Show is extracted and added to your playlist

## Configuration

Click the extension icon → Settings → Enter your Giglz API URL:
- Development: `http://localhost:5001`
- Production: `https://your-app.railway.app`

## Requirements

- Must be logged into Giglz in your browser (extension uses your session)
- Works on Chrome, Brave, Edge (Chromium-based browsers)

## Icons
Replace the placeholder icons in `icons/` with proper PNG files:
- `icon16.png` - 16x16px
- `icon48.png` - 48x48px
- `icon128.png` - 128x128px
