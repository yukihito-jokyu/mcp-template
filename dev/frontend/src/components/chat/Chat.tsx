import React, { useState } from 'react';
import styles from './Chat.module.css';

const Chat: React.FC = () => {
  const [message, setMessage] = useState<string>('');
  const [chatHistory, setChatHistory] = useState<string[]>([]);

  const sendMessage = async () => {
    if (message.trim() === '') return;

    setChatHistory((prev) => [...prev, `You: ${message}`]);

    try {
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setChatHistory((prev) => [...prev, `Echo: ${data.message}`]);
    } catch (error) {
      console.error('Error sending message:', error);
      setChatHistory((prev) => [...prev, `Error: Could not connect to backend.`]);
    }

    setMessage('');
  };

  return (
    <div className={styles.chatContainer}>
      <div className={styles.chatHistory}>
        {chatHistory.map((entry, index) => (
          <div key={index} className={styles.chatMessage}>
            {entry}
          </div>
        ))}
      </div>
      <div className={styles.chatInput}>
        <input
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyPress={(e) => {
            if (e.key === 'Enter') {
              sendMessage();
            }
          }}
          placeholder="Type your message..."
          className={styles.messageInput}
        />
        <button onClick={sendMessage} className={styles.sendButton}>
          Send
        </button>
      </div>
    </div>
  );
};

export default Chat;
