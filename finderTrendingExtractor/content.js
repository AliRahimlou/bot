(function() {
    const loggedContracts = new Set();
    const contractPairs = [];
    const contractRegex = /https:\/\/solscan\.io\/token\/([a-zA-Z0-9]+)/;
    const marketCap = "$40.7k"; // Hardcoded market cap value

    async function sendContractPairsToServer(pair) {
        try {
            const response = await fetch('http://127.0.0.1:5001/save_contracts', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(pair),
            });
            const result = await response.json();
            console.log(`Server response: ${JSON.stringify(result)}`);
        } catch (error) {
            console.error('Error sending contract pair to server:', error);
        }
    }

    function extractDataFromElement(element) {
        const links = element.querySelectorAll('a[href*="https://solscan.io/token/"]');
        links.forEach(link => {
            const href = link.getAttribute('href');
            const contractMatch = href.match(contractRegex);
            if (contractMatch) {
                const contractKey = contractMatch[1];
                if (!loggedContracts.has(contractKey)) {
                    loggedContracts.add(contractKey);
                    console.log(`Contract: ${contractKey}, Market Cap: ${marketCap}`);
                    const pair = { contractKey, marketCap };
                    contractPairs.push(pair);
                    sendContractPairsToServer(pair);
                }
            }
        });
    }

    function extractDataFromContainer() {
        const messages = document.querySelectorAll('[id^="message"]');
        messages.forEach(message => {
            extractDataFromElement(message);
        });
    }

    function processMutations(mutations) {
        mutations.forEach((mutation) => {
            mutation.addedNodes.forEach((node) => {
                if (node.nodeType === Node.ELEMENT_NODE) {
                    extractDataFromElement(node);
                }
            });
        });
    }

    // Initial extraction from the container
    extractDataFromContainer();

    // Observe new elements being added to the container
    const observer = new MutationObserver(processMutations);
    observer.observe(document.body, { childList: true, subtree: true });

    // Re-extract data from the container every 10 seconds to catch updates
    setInterval(extractDataFromContainer, 10000); // 10 seconds in milliseconds

    // Set interval to reload the page every 1 hour
    setInterval(() => {
        console.log('Reloading page automatically every 1 hour...');
        location.reload();
    }, 3600000); // 1 hour in milliseconds
})();
