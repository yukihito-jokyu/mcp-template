import axios from 'axios';
import { useEffect, useState } from 'react';

function App() {
  const [message, setMessage] = useState<string>('');

  useEffect(() => {
    // API呼び出し
    axios
      .get('http://localhost:8000/api/hello')
      .then((response) => {
        setMessage(response.data.message);
      })
      .catch((error) => {
        console.error('API呼び出しエラー:', error);
      });
  }, []);

  return (
    <div>
      <h1>FastAPIからのメッセージ:</h1>
      <p>{message}</p>
    </div>
  );
}

export default App;
