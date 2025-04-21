const express = require('express');
const { ProfileNetworthCalculator } = require('skyhelper-networth');
const app = express();
const port = 3000;

app.use(express.json({ limit: '50mb' }));

app.post('/calculate-networth', async (req, res) => {
  try {
    const { playerUUID, profileData, museumData, bankBalance } = req.body;

    if (!profileData || !playerUUID) {
      return res.status(400).json({
        success: false,
        error: 'Missing required data'
      });
    }

    // Extract the member data for this specific player
    const memberData = profileData.members[playerUUID];

    if (!memberData) {
      return res.status(400).json({
        success: false,
        error: 'Player not found in profile'
      });
    }

    // Initialize the ProfileNetworthCalculator with the correct parameters
    const networthManager = new ProfileNetworthCalculator(
      memberData,                // profileData: The player's data within the profile
      museumData,                // museumData: The player's museum data
      profileData.banking?.balance || 0  // bankBalance: The profile's bank balance
    );

    // Calculate the networth
    const networth = await networthManager.getNetworth();

    // Return the calculation results
    res.json({
      success: true,
      networth: networth.networth,
      categories: networth.categories,
      items: networth.items,
      purse: networth.purse,
      bank: networth.bank
    });

  } catch (error) {
    console.error('Error calculating networth:', error);
    res.status(500).json({
      success: false,
      error: error.message || 'Internal server error'
    });
  }
});

app.listen(port, () => {
  console.log(`Networth service listening at http://localhost:${port}`);
  console.log(`Make sure skyhelper-networth is installed: npm install skyhelper-networth`);
});