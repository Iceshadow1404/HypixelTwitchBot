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
    const nonCosmeticNetworth = await networthManager.getNonCosmeticNetworth();

    // Debug logging for the nonCosmeticNetworth object
    console.log('Debug - nonCosmeticNetworth object structure:');
    console.log(JSON.stringify(nonCosmeticNetworth, null, 2));

    // Debug specific properties
    console.log('Debug - nonCosmeticNetworth.networth:', nonCosmeticNetworth.networth);
    console.log('Debug - nonCosmeticNetworth.nonCosmeticNetworth:', nonCosmeticNetworth.nonCosmeticNetworth);

    // Debug logging for the networth object for comparison
    console.log('Debug - networth object reference:');
    console.log('networth.networth:', networth.networth);

    // Return the calculation results
    const response = {
      success: true,
      networth: networth.networth,
      categories: networth.categories,
      items: networth.items,
      purse: networth.purse,
      bank: networth.bank
    };

    // Add the nonCosmeticNetworth based on what we found in the debug logs
    if (nonCosmeticNetworth.nonCosmeticNetworth !== undefined) {
      response.nonCosmeticNetworth = nonCosmeticNetworth.nonCosmeticNetworth;
    } else if (nonCosmeticNetworth.networth !== undefined) {
      response.nonCosmeticNetworth = nonCosmeticNetworth.networth;
    } else {
      console.log('Debug - Attempting to find nonCosmeticNetworth in the root object:');
      // Try to find the property in the object itself
      const nonCosmeticKeys = Object.keys(nonCosmeticNetworth);
      console.log('Available keys in nonCosmeticNetworth:', nonCosmeticKeys);

      if (nonCosmeticKeys.length > 0) {
        // Use the first numeric property if we can find one
        const numericalValue = nonCosmeticKeys.find(key =>
          !isNaN(nonCosmeticNetworth[key]) && typeof nonCosmeticNetworth[key] === 'number'
        );

        if (numericalValue) {
          response.nonCosmeticNetworth = nonCosmeticNetworth[numericalValue];
          console.log(`Found numerical value in key '${numericalValue}':`, response.nonCosmeticNetworth);
        } else {
          // Last resort - check if the object itself is a number
          if (typeof nonCosmeticNetworth === 'number') {
            response.nonCosmeticNetworth = nonCosmeticNetworth;
            console.log('Using nonCosmeticNetworth as a number directly:', response.nonCosmeticNetworth);
          } else {
            console.log('Could not find a suitable nonCosmeticNetworth value');
            response.nonCosmeticNetworth = 0;
          }
        }
      } else {
        console.log('No keys found in nonCosmeticNetworth object');
        response.nonCosmeticNetworth = 0;
      }
    }

    console.log('Final response object:');
    console.log(JSON.stringify(response, null, 2));

    res.json(response);

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