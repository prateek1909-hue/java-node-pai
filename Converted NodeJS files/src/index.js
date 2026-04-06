const express = require('express');
const reportsRouter = require('./presentation/controllers/reports.controller');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Routes
app.use('/api/reports', reportsRouter);

app.get('/health', (req, res) => res.json({ status: 'ok' }));

app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});

module.exports = app;
