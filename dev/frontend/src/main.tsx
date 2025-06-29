import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import '@assets/index.css';
import App from '@components/App';
import Chat from '@components/chat/Chat';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
    <Chat />
  </StrictMode>
);
