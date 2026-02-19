import { useEffect, useState } from 'react'
import './App.css'

function App() {
  const [isLoaded, setIsLoaded] = useState(false)

  useEffect(() => {
    const scriptId = 'email-reader-ui-script';
    if (!document.getElementById(scriptId)) {
      const script = document.createElement('script');
      script.id = scriptId;
      script.src = 'http://localhost:3000/assets/email-reader-ui.js';
      script.type = 'module';
      script.onload = () => setIsLoaded(true);
      script.onerror = () => setError('Failed to load Email Reader UI script. Please check if the service is running and accessible.');
      document.body.appendChild(script);
    } else {
      setIsLoaded(true);
    }
  }, []);

  return (
    <div className="react-shell">
      <header className="shell-header">
        <h1>The Email Crew</h1>
        <p>Federating microservices & Orchestrating AI Agents</p>
      </header>

      <main className="shell-content">
        <section className="mfe-container">
          {isLoaded ? (
            <email-reader-ui-root backend-origin="http://localhost:8000"></email-reader-ui-root>
          ) : (
            <div className="loading-placeholder">Loading Email Reader UI...</div>
          )}
        </section>

        {/* Placeholder for future MFEs */}
        <section className="mfe-placeholder">
          <div className="placeholder-card">
            <h3>Future Services</h3>
            <p>This space is reserved for other features.</p>
          </div>
        </section>
      </main>

      <footer className="shell-footer">
        <p>&copy; 2026 The Email Crew - An Agentic AI System</p>
      </footer>
    </div>
  )
}

export default App
