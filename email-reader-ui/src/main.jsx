import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import App from './App.jsx'

class EmailReaderUIRoot extends HTMLElement {
  constructor() {
    super();
    this.root = null;
  }

  connectedCallback() {
    if (!this.root) {
      const mountPoint = document.createElement('div');
      this.attachShadow({ mode: 'open' }).appendChild(mountPoint);

      // Copy styles into shadow DOM
      const style = document.createElement('style');
      style.textContent = `
        :host {
          display: block;
          font-family: Inter, system-ui, Avenir, Helvetica, Arial, sans-serif;
        }
      `;
      this.shadowRoot.appendChild(style);

      this.root = ReactDOM.createRoot(mountPoint);
    }
    this.render();
  }

  static get observedAttributes() {
    return ['backend-origin'];
  }

  attributeChangedCallback() {
    this.render();
  }

  render() {
    if (this.root) {
      const backendOrigin = this.getAttribute('backend-origin') || 'http://localhost:8000';
      this.root.render(
        <React.StrictMode>
          <App backendOrigin={backendOrigin} />
        </React.StrictMode>
      );
    }
  }

  disconnectedCallback() {
    if (this.root) {
      this.root.unmount();
      this.root = null;
    }
  }
}

if (!customElements.get('email-reader-ui-root')) {
  customElements.define('email-reader-ui-root', EmailReaderUIRoot);
}
