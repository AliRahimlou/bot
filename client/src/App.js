import React, { useState } from 'react';
import axios from 'axios';

function App() {
  const [command, setCommand] = useState('');
  const [token, setToken] = useState('');
  const [amount, setAmount] = useState('');
  const [response, setResponse] = useState(null);

  const sendMessage = async () => {
    try {
      const res = await axios.post('http://localhost:5000/api/sendMessage', { command, token, amount });
      setResponse(res.data);
    } catch (error) {
      console.error('Error in frontend request:', error);
      setResponse(error.message);
    }
  };

  return (
    <div className="App">
      <h1>Telegram Bot Command Sender</h1>
      <input
        type="text"
        placeholder="Command (buy/sell)"
        value={command}
        onChange={(e) => setCommand(e.target.value)}
      />
      <input
        type="text"
        placeholder="Token"
        value={token}
        onChange={(e) => setToken(e.target.value)}
      />
      <input
        type="text"
        placeholder="Amount"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
      />
      <button onClick={sendMessage}>Send Command</button>
      {response && <div><pre>{JSON.stringify(response, null, 2)}</pre></div>}
    </div>
  );
}

export default App;
