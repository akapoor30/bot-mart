import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import { AuthProvider } from "react-oidc-context";
import './index.css';

const oidcConfig = {
  authority: "http://localhost:8080/realms/bot-mart",
  client_id: "bot-mart-app",
  redirect_uri: "http://localhost:5173/",
  // Automatically renew the token in the background when it expires
  automaticSilentRenew: true,
};

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AuthProvider {...oidcConfig}>
      <App />
    </AuthProvider>
  </React.StrictMode>,
);