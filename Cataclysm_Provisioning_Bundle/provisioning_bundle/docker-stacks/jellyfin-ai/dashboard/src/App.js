import React, { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch('/api/analytics')
      .then(response => {
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }
        return response.json();
      })
      .then(data => {
        setAnalytics(data);
        setLoading(false);
      })
      .catch(error => {
        setError(error);
        setLoading(false);
      });
  }, []);

  return (
    <div className="App">
      <header className="App-header">
        <h1>Media Analysis Dashboard</h1>
      </header>
      <main>
        <h2>Analytics Data</h2>
        {loading && <p>Loading...</p>}
        {error && <p>Error: {error.message}</p>}
        {analytics && (
          <pre>{JSON.stringify(analytics, null, 2)}</pre>
        )}
      </main>
    </div>
  );
}

export default App;
