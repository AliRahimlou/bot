const express = require('express');
const cors = require('cors');
const axios = require('axios');

const app = express();
const PORT = process.env.PORT || 5000;
const TELEGRAM_BOT_TOKEN = '7168301922:AAF1ewEwPrrsIEIG33QIjhO5Do9ee-ChnPs'
// const TELEGRAM_CHAT_ID = '@Trojan_On_Solana_Bot';
const TELEGRAM_CHAT_ID = '7168301922';


// Enable CORS
app.use(cors());

// Parse JSON and URL-encoded data
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Enable pre-flight for all routes
app.options('*', cors());

app.post('/api/sendMessage', async (req, res) => {
  const { command, token, amount } = req.body;

  try {
    const response = await axios.post(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`, {
      chat_id: TELEGRAM_CHAT_ID,
      text: `/${command} ${token} ${amount}`
    });

    res.status(200).send(response.data);
  } catch (error) {
    console.error('Error sending message:', error); // Detailed error logging
    if (error.response) {
      console.error('Error response:', error.response.data);
      res.status(error.response.status).send(error.response.data);
    } else if (error.request) {
      console.error('Error request:', error.request);
      res.status(500).send('No response received from Telegram API');
    } else {
      console.error('Error message:', error.message);
      res.status(500).send('Error in setting up the request');
    }
  }
});

app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});
