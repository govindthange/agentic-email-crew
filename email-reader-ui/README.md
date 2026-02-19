# Email Reader UI Microfrontend

This is a React-based microfrontend built with Vite. It is designed to be consumed as a custom element.

## Features
- Registered as a custom element: `<email-reader-ui-root>`.
- Supports `backend-origin` attribute (e.g., `http://localhost:8000`).
- Interactive buttons to fetch the last email and check archive counts.
- Real-time JSON display of API responses.
- Premium UI with glassmorphism effects.

## How to Build and Run

### Using Docker Compose (Recommended)
From the project root:
```bash
docker compose up --build -d email-reader-ui
```
The UI will be available at `http://localhost:3000`.

### Manual Development
1. Install dependencies:
   ```bash
   npm install
   ```
2. Run development server:
   ```bash
   npm run dev
   ```

## Custom Element Usage
To use this microfrontend in a host application (like the React Shell):

```html
<!-- Include the microfrontend bundle -->
<script type="module" src="http://localhost:3000/assets/index-HASH.js"></script>

<!-- Use the custom element -->
<email-reader-ui-root backend-origin="http://localhost:8000"></email-reader-ui-root>
```

## Testing
1. Ensure `email-reader-service` is running.
2. Open `http://localhost:3000` in your browser.
3. Click "Fetch Last Email" to trigger an API call and see the result.
