const express = require('express');
const path = require('path');
const app = express();

// The specific port you requested
const PORT = 5173;

// Route for the /join path
app.get('/join', (req, res) => {
    res.sendFile(path.join(__dirname, 'join.html'));
});

// Start the server
app.listen(PORT, () => {
    console.log(`Server is running! Click here: http://localhost:${PORT}/join`);
});
