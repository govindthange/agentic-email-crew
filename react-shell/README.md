# React Shell

This is the main orchestration container for The Email Crew microservices. It federates microfrontends from various services into a single, unified interface using custom elements.

## Features
- **Dynamic Orchestration**: Loads microfrontend JS bundles at runtime.
- **Custom Element Integration**: Seamlessly renders `<email-reader-ui-root>`.
- **Framework Agnostic**: The integration contract is based on standard Web Components.

## Setup

1.  **Run with Docker Compose**:
    From the project root:
    ```bash
    docker compose up --build -d
    ```
    The shell will be available at `http://localhost:4000`.

## Architecture

The shell uses a dynamic script loading pattern to fetch microfrontend bundles. In this project, it fetches `email-reader-ui.js` from the `email-reader-ui` service.

```javascript
// Example loading logic
const script = document.createElement('script');
script.src = 'http://localhost:3000/assets/email-reader-ui.js';
document.body.appendChild(script);
```

## Testing
- Open `http://localhost:4000` in your browser.
- Verify that the Email Reader UI appears within the shell's content area.
